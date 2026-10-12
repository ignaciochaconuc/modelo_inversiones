"""Budgeted existing-router orchestration; outputs remain strictly experimental."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import time

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import fingerprint
from investment_system.llm.router import LLMRouter
from investment_system.llm.openai_client import OpenAIClient
from investment_system.llm.openai_settings import LLMProviderError
from investment_system.llm.pricing import PricingRegistry
from investment_system.llm.cost_tracker import CostTracker, LLMCallRecord
from investment_system.agents.news_interpretation.schemas import (
    ModelConfiguration, InterpretationPayload, NewsInterpretationRequest, VALIDATION_VERSION,
)
from investment_system.agents.news_interpretation.replay import prepare_llm_request, replay_response, ReplayEnvelope
from investment_system.agents.news_interpretation.budget import RunBudget, BudgetExceeded
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.runtime_schemas import (
    InterpretationRuntimeSettings, StoredInterpretationAttempt, InterpretationDelivery,
    StoredInterpretationAttemptV2, CacheWritePriceSchedule,
)


def prepare_invocation(request: NewsInterpretationRequest, settings: InterpretationRuntimeSettings):
    """Pure preparation shared by offline preflight and actual execution."""
    a = settings.adapter
    configuration = ModelConfiguration(provider="openai", model=a.model, temperature=a.temperature,
        max_output_tokens=a.max_output_tokens, max_estimated_cost_usd=settings.request_budget_usd)
    llm = prepare_llm_request(request, configuration)
    llm.response_schema = InterpretationPayload.model_json_schema()
    wire = OpenAIClient(a).wire_payload(llm, a.model)
    key = fingerprint({"request": request.request_id, "evidence": request.evidence_fingerprint,
        "validation_version": VALIDATION_VERSION, "settings": settings.model_dump(mode="json"), "wire": wire})
    return llm, wire, key


def reservation_bound(wire: dict, settings: InterpretationRuntimeSettings) -> tuple[int, float]:
    """Conservative UTF-8 bound, never a remote token-counting request."""
    input_bound = len(json.dumps(wire, ensure_ascii=False, sort_keys=True).encode("utf-8")) + 256
    a, price = settings.adapter, settings.pricing
    if input_bound + a.max_output_tokens > a.context_window_tokens:
        raise ValueError("estimated_input_exceeds_model_context")
    rates = [price.input_per_million, price.cached_input_per_million]
    if isinstance(price, CacheWritePriceSchedule):
        if input_bound > min(price.short_context_max_input_tokens, a.capability_max_input_tokens):
            raise ValueError("estimated_input_exceeds_verified_price_band")
        rates.append(price.cache_write_per_million)
    return input_bound, (input_bound * max(rates) + a.max_output_tokens * price.output_per_million) / 1_000_000


class NewsInterpretationService:
    def __init__(self,router: LLMRouter,settings: InterpretationRuntimeSettings,
                 storage: LocalInterpretationStore,run_id: str,*,
                 execution_authorized: bool=False,simulated: bool=False,
                 tracker: CostTracker | None=None,prices: PricingRegistry | None=None,
                 clock=None,sleep=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",run_id):
            raise ValueError("invalid run identity")
        self.router,self.settings,self.storage,self.run_id=router,settings,storage,run_id
        self.execution_authorized,self.simulated=execution_authorized,simulated
        self.tracker=tracker or CostTracker()
        self.prices=prices if prices is not None else PricingRegistry({("openai",settings.adapter.model):settings.pricing.token_price()})
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.sleep=sleep or time.sleep
        self.budget=RunBudget(storage.root/"budgets"/(run_id+".sqlite"),settings.run_budget_usd,settings.request_budget_usd)

    def _configuration(self) -> ModelConfiguration:
        a=self.settings.adapter
        return ModelConfiguration(provider="openai",model=a.model,temperature=a.temperature,
                                  max_output_tokens=a.max_output_tokens,max_estimated_cost_usd=self.settings.request_budget_usd)

    def invocation(self,request: NewsInterpretationRequest):
        return prepare_invocation(request, self.settings)

    def _price(self,now):
        schedule=self.settings.pricing
        price=self.prices.get_price("openai",self.settings.adapter.model)
        if price is None:
            raise ValueError("unknown_price")
        if price != schedule.token_price() or not schedule.valid_from <= now < schedule.valid_until:
            raise ValueError("price_configuration_stale_or_mismatched")
        if self.settings.adapter.capabilities_verified_at > now:
            raise ValueError("future_capability_attestation")
        return price

    def interpret_revision(self,store,revision_id,decision_time,**kwargs):
        from investment_system.agents.news_interpretation.inputs import build_interpretation_request
        return self.interpret(build_interpretation_request(store,revision_id,decision_time,**kwargs))

    def interpret(self,request: NewsInterpretationRequest,*,force_new: bool=False) -> InterpretationDelivery:
        request=NewsInterpretationRequest.model_validate(request.model_dump(mode="json"))
        llm,wire,key=self.invocation(request)
        secret=os.getenv("OPENAI_API_KEY")
        if secret and (secret in request.model_dump_json() or secret in self.settings.model_dump_json()):
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="secret_in_input_rejected")
        now=ensure_utc(self.clock())
        if request.inputs_available_at > now:
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="inputs_not_yet_observed")
        if not force_new:
            try:
                cached=self.storage.cache_get(key,now=now)
            except (ValueError,OSError,KeyError):
                cached=None  # Expired/corrupt cache never authorizes execution.
            if cached:
                return InterpretationDelivery(retrieval_mode="exact_cache_recovery",cache_key=key,
                    record=cached,record_id=cached.record_id,additional_provider_cost_usd=0,additional_attempts=0)
        if not self.execution_authorized:
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="execution_not_authorized")
        if not (self.router.routes.get(llm.task) or self.router.routes.get(f"{llm.agent}.{llm.task}")):
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="explicit_task_route_required")
        try:
            client,model=self.router.select(llm)
        except (ValueError,KeyError):
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="route_missing")
        if client.provider != "openai" or model != self.settings.adapter.model:
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="route_identity_mismatch")
        if not self.simulated and not isinstance(client,OpenAIClient):
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="unverified_live_client")
        # A real client must have exactly the configuration whose wire was budgeted.
        if isinstance(client,OpenAIClient) and (client.settings != self.settings.adapter or not client.enabled):
            return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="adapter_configuration_mismatch")
        ids=[];last=None;known_total=0.0;unknown=False
        for number in range(1,self.settings.max_attempts+1):
            started=ensure_utc(self.clock())
            try:
                price=self._price(started)
            except ValueError as exc:
                return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code=str(exc),attempt_record_ids=tuple(ids),record=last,record_id=last.record_id if last else None,additional_attempts=len(ids),additional_provider_cost_usd=None if unknown else known_total)
            try:
                _, maximum = reservation_bound(wire, self.settings)
            except ValueError as exc:
                return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code=str(exc),attempt_record_ids=tuple(ids),record=last,record_id=last.record_id if last else None,additional_attempts=len(ids),additional_provider_cost_usd=None if unknown else known_total)
            try:
                attempt_id=self.budget.reserve(key,maximum)
            except BudgetExceeded:
                return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,error_code="request_or_run_budget_insufficient",attempt_record_ids=tuple(ids),record=last,record_id=last.record_id if last else None,additional_attempts=len(ids),additional_provider_cost_usd=None if unknown else known_total)
            response=None;error=None;retryable=False;envelope=None
            try:
                response=self.router.complete(llm)
                if response.provider != "openai" or response.model != model:
                    raise LLMProviderError("model_identity_mismatch",response=response)
                if response.raw.get("effective_parameters",self.settings.adapter.effective_parameters) != self.settings.adapter.effective_parameters:
                    raise LLMProviderError("effective_parameters_mismatch",response=response)
            except LLMProviderError as exc:
                safe={"timeout","disconnect","authentication","authorization","rate_limit","server_error","permanent_http_error","invalid_provider_envelope","model_identity_mismatch","provider_refusal","incomplete_response","missing_api_key","secret_echo_rejected","effective_parameters_mismatch","unexpected_provider_tool","permanent_provider_error","unexpected_pending_or_cancelled_response"}
                error=exc.code if exc.code in safe else "provider_error"
                retryable=exc.retryable and error in {"timeout","disconnect","rate_limit","server_error","invalid_provider_envelope","incomplete_response"}
                response=exc.response
            except Exception:
                error="unexpected_client_error"  # Reservation remains; never echo exception text.
            received=ensure_utc(self.clock())
            if response and secret and (secret in response.content or secret in response.model):
                response=response.model_copy(update={"content":"","model":"redacted_unknown_model" if secret in response.model else response.model})
                error="secret_echo_rejected";retryable=False
            known_usage=response is not None and {"input_tokens","cached_input_tokens","output_tokens"}.issubset(response.model_fields_set) and response.raw.get("usage_reported",True)
            if known_usage and not (0 <= response.cached_input_tokens <= response.input_tokens and response.output_tokens >= 0):
                known_usage=False;error="invalid_usage_telemetry";retryable=False
            attempt_prices=PricingRegistry({("openai",model):price})
            cost=attempt_prices.estimate("openai",model,response.input_tokens,response.cached_input_tokens,response.output_tokens) if known_usage and response.provider=="openai" and response.model==model else None
            write_tokens = None
            v2 = isinstance(self.settings.pricing, CacheWritePriceSchedule)
            if v2:
                written = response.raw.get("cache_write_tokens") if response else None
                write_tokens = written if type(written) is int and written >= 0 else None
                known_usage = bool(known_usage and write_tokens is not None)
                cost = None
                if known_usage and response.provider == "openai" and response.model == model:
                    try:
                        cost = self.settings.pricing.estimate_usage(response.input_tokens,
                            response.cached_input_tokens, write_tokens, response.output_tokens)
                    except ValueError as exc:
                        known_usage = False; error = str(exc); retryable = False
            accounted=self.budget.settle(attempt_id,cost)
            unknown=unknown or cost is None
            if cost is not None:known_total+=cost
            if cost is not None and cost > maximum:
                error="observed_cost_exceeds_reservation";retryable=False
            if response and error is None:
                try:
                    result=replay_response(request,response,self._configuration(),validated_at=ensure_utc(self.clock()),
                        execution_mode="retrospective_reconstruction",estimated_cost_usd=cost,
                        tokens_reported=known_usage,latency_reported="latency_ms" in response.model_fields_set)
                    envelope=ReplayEnvelope(request=request,result=result)
                    if result.status == "invalid_response":
                        error="invalid_structured_evidence";retryable=self.settings.retry_invalid_response
                except ValueError:
                    error="invalid_result_provenance";retryable=False
            outcome=envelope.result.status if envelope else (error or "unexpected_client_error")
            fields=response.model_fields_set if response else set()
            input_tokens=response.input_tokens if response and "input_tokens" in fields else None
            output_tokens=response.output_tokens if response and "output_tokens" in fields else None
            cached_tokens=response.cached_input_tokens if response and "cached_input_tokens" in fields else None
            call=LLMCallRecord(timestamp=received,provider="openai",model=response.model if response else model,
                requested_model=model,actual_model=response.model if response else None,agent="NewsAgent",task="news_interpretation",
                ticker=llm.ticker,analysis_id=attempt_id,input_tokens=input_tokens,cached_input_tokens=cached_tokens,output_tokens=output_tokens,
                total_tokens=input_tokens+output_tokens if input_tokens is not None and output_tokens is not None else None,
                estimated_cost_usd=cost,latency_ms=response.latency_ms if response else (received-started).total_seconds()*1000,
                success=outcome in {"interpreted","abstained"},error_type=error,cost_quality="usage_based_estimate" if cost is not None else "unknown")
            self.tracker.add(call)
            persisted=ensure_utc(self.clock())
            # Copy only typed standard response fields; raw headers/error bodies excluded.
            durable=response.model_copy(update={"raw":{}}) if response else None
            record_type = StoredInterpretationAttemptV2 if v2 else StoredInterpretationAttempt
            record=record_type(**({"cache_write_tokens":write_tokens} if v2 else {}),attempt_id=attempt_id,cache_key=key,run_id=self.run_id,attempt_number=number,
                request=request,settings=self.settings,started_at=started,received_at=received,persisted_at=persisted,
                expires_at=persisted+timedelta(hours=self.settings.local_content_retention_hours),requested_provider="openai",requested_model=model,
                actual_model=response.model if response else None,effective_parameters=self.settings.adapter.effective_parameters,
                wire_payload=wire,wire_fingerprint=fingerprint(wire),maximum_reserved_usd=maximum,accounted_usd=accounted,
                observed_usage_cost_usd=cost,cost_record=call,provider_response=durable,interpretation=envelope,outcome=outcome,error_code=error,
                dataset_role="offline_simulated_development" if self.simulated else "exploratory_real_response")
            ids.append(self.storage.write(record));last=record
            if outcome in {"interpreted","abstained"}:
                self.storage.cache_put(record);break
            if not retryable or number == self.settings.max_attempts:break
            self.sleep(self.settings.retry_delay_seconds)
        return InterpretationDelivery(retrieval_mode="new_inference",cache_key=key,record=last,
            record_id=last.record_id if last else None,attempt_record_ids=tuple(ids),error_code=last.error_code if last else None,
            additional_provider_cost_usd=None if unknown else known_total,additional_attempts=len(ids))

    def reconstruct(self,record_id: str) -> InterpretationDelivery:
        record=self.storage.read(record_id,now=ensure_utc(self.clock()))
        return InterpretationDelivery(retrieval_mode="offline_reconstruction",cache_key=record.cache_key,
            record_id=record_id,record=record,additional_provider_cost_usd=0,additional_attempts=0)


def plan_model_comparison(request: NewsInterpretationRequest,configurations: tuple[InterpretationRuntimeSettings,...]) -> dict:
    """Freeze identical inputs/model manifests without routing, storage or inference."""
    request=NewsInterpretationRequest.model_validate(request.model_dump(mode="json"))
    candidates=[]
    for settings in configurations:
        a=settings.adapter
        config=ModelConfiguration(provider="openai",model=a.model,temperature=a.temperature,
            max_output_tokens=a.max_output_tokens,max_estimated_cost_usd=settings.request_budget_usd)
        llm=prepare_llm_request(request,config)
        llm.response_schema=InterpretationPayload.model_json_schema()
        wire=OpenAIClient(a).wire_payload(llm,a.model)
        candidates.append({"requested_model":a.model,"settings_fingerprint":fingerprint(settings.model_dump(mode="json")),
                           "wire_fingerprint":fingerprint(wire)})
    return {"request_id":request.request_id,"evidence_fingerprint":request.evidence_fingerprint,
            "status":"planned_not_executed","candidates":candidates}
