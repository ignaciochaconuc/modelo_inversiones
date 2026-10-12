"""Opt-in ONE-article real interpretation; never run during normal validation."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4

import yaml

from investment_system.agents.news_interpretation.inputs import build_interpretation_request
from investment_system.agents.news_interpretation.runtime_schemas import InterpretationRuntimeSettings
from investment_system.agents.news_interpretation.runtime_schemas import GroundedRuntimeSettings
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.service import NewsInterpretationService, prepare_invocation, reservation_bound
from investment_system.data.news_entities import load_entity_registry
from investment_system.data.storage.news_store import NewsStore
from investment_system.llm.openai_client import OpenAIClient
from investment_system.llm.router import LLMRouter
from investment_system.core.environment import load_repository_environment, EnvironmentBootstrapError, safe_cli_errors


@safe_cli_errors
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-real-inference",action="store_true")
    parser.add_argument("--validate-only",action="store_true",help="Offline preflight; no provider or persistence initialization")
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--budget-usd",type=float,required=True)
    parser.add_argument("--revision-id",required=True)
    parser.add_argument("--as-of",required=True)
    args=parser.parse_args()
    if args.validate_only and args.confirm_real_inference:
        print(json.dumps({"status":"blocked","error":"conflicting_execution_modes","provider_calls":0}))
        return 2
    if not args.confirm_real_inference and not args.validate_only:
        print(json.dumps({"status":"disabled","error":"explicit_confirmation_required","provider_calls":0}))
        return 2
    # Credential bootstrap is forbidden for offline validation, even with a key.
    if not args.validate_only:
        try:
            load_repository_environment(real_operation_authorized=args.confirm_real_inference)
        except EnvironmentBootstrapError:
            print(json.dumps({"status":"blocked","error":"repository_environment_load_failed","provider_calls":0}))
            return 2
    if not args.validate_only and not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status":"blocked","error":"missing_api_key","provider_calls":0}))
        return 2
    try:
        raw=yaml.safe_load(args.config.read_text(encoding="utf-8"))
        secret = os.getenv("OPENAI_API_KEY")
        if secret and secret in json.dumps(raw,default=str):
            raise ValueError("secrets are not configuration")
        if raw["adapter"]["model"] != args.model:
            raise ValueError("model flag must match the explicit profile")
        settings_type=GroundedRuntimeSettings if raw.get("settings_version")=="news-inference-settings-v3" else InterpretationRuntimeSettings
        settings=settings_type.model_validate(raw)
        if args.budget_usd <= 0 or args.budget_usd > settings.run_budget_usd:
            raise ValueError("flag cannot expand the configured budget")
        settings=settings_type.model_validate({**settings.model_dump(mode="json"),
            "run_budget_usd":args.budget_usd,"request_budget_usd":min(settings.request_budget_usd,args.budget_usd)})
        cutoff=datetime.fromisoformat(args.as_of.replace("Z","+00:00"))
        request=build_interpretation_request(NewsStore("data/raw","data/processed"),args.revision_id,cutoff,registry=load_entity_registry())
        now=datetime.now().astimezone()
        if not settings.pricing.valid_from <= now < settings.pricing.valid_until:
            raise ValueError("pricing validity required")
        if settings.adapter.capabilities_verified_at > now or request.inputs_available_at > now:
            raise ValueError("future inputs or capability attestation")
        if secret and secret in request.model_dump_json():
            raise ValueError("secret in source content")
        # This single-article CLI now requires fully accounted four-lane pricing.
        # Original v1 manifests/records remain available for offline replay.
        if settings.settings_version not in {"news-inference-settings-v2","news-inference-settings-v3"} or settings.max_attempts != 1:
            raise ValueError("smoke requires v2 pricing and one attempt")
        _, wire, key = prepare_invocation(request, settings)
        input_bound, maximum = reservation_bound(wire, settings)
        if maximum > min(settings.request_budget_usd, settings.run_budget_usd):
            raise ValueError("insufficient conservative budget")
    except (ValueError,TypeError,KeyError,OSError,yaml.YAMLError):
        print(json.dumps({"status":"blocked","error":"invalid_or_missing_critical_configuration","provider_calls":0}))
        return 2
    if args.validate_only:
        print(json.dumps({"status":"validated_offline","provider_calls":0,"persistence_writes":0,
            "revision_id":request.revision_id,"cutoff":request.decision_time.isoformat(),
            "inputs_available_at":request.inputs_available_at.isoformat(),"cache_key":key,
            "model":args.model,"effective_parameters":settings.adapter.effective_parameters,
            "strict_structured_output":wire["text"]["format"]["strict"],
            "input_token_upper_bound":input_bound,"maximum_reserved_usd":maximum,
            "run_budget_usd":settings.run_budget_usd,"max_attempts":settings.max_attempts,
            "model_output_version":getattr(settings,"model_output_version","news-interpretation-v1"),
            "api_key_present":bool(secret),"experimental":True,"operational":False}))
        return 0
    client=OpenAIClient(settings.adapter,enabled=True)
    router=LLMRouter({"openai":client},{"news_interpretation":{"provider":"openai","model":args.model}})
    service=NewsInterpretationService(router,settings,LocalInterpretationStore(),uuid4().hex,execution_authorized=True)
    try:
        delivery=service.interpret(request)
    except Exception:
        # Never expose exception strings/payloads; durable reservations remain.
        print(json.dumps({"status":"failed","error":"safe_execution_failure","experimental":True}))
        return 1
    record=delivery.record
    print(json.dumps({"status":record.outcome if record else "blocked","error":delivery.error_code,
        "retrieval_mode":delivery.retrieval_mode,"attempts":delivery.additional_attempts,
        "cost_usd":delivery.additional_provider_cost_usd,"conservative_accounted_usd":service.budget.accounted(),
        "unknown_cost_attempts":service.tracker.unknown_cost_count(),
        "tokens": [{"input":r.input_tokens,"cached":r.cached_input_tokens,"output":r.output_tokens} for r in service.tracker.records],
        "record_id":delivery.record_id,"cache_key":delivery.cache_key,
        "cache_write_tokens":getattr(record,"cache_write_tokens",None),
        "rejection_diagnostics":[d.model_dump(mode="json") for d in getattr(record,"rejection_diagnostics",())],
        "requested_model":args.model,"actual_model":record.actual_model if record else None,
        "experimental":True,"operational":False,"articles":1}))
    return 0 if record and record.outcome in {"interpreted","abstained"} else 1


if __name__=="__main__":
    raise SystemExit(main())
