"""Synthetic v2 selection/grounding tests; never use licensed smoke content."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from investment_system.agents.news_interpretation.grounding import (
    MODEL_OUTPUT_VERSION, QuoteSelectionPayload, evaluate_quote_response, prepare_quote_request,
    GroundedReplayEnvelope, resolve_selected_quotes, QuoteResolutionError,
)
from investment_system.agents.news_interpretation.runtime_schemas import GroundedRuntimeSettings, InterpretationRuntimeSettings
from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest, ModelConfiguration, InterpretationPayload
from investment_system.agents.news_interpretation.replay import ReplayEnvelope, replay_response, prepare_llm_request
from investment_system.agents.news_interpretation.service import NewsInterpretationService, prepare_invocation
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore, ATTEMPT_ADAPTER
from investment_system.data.news_evaluation import FIXTURE_TIME, synthetic_record, fixture_registry
from investment_system.data.storage.news_store import NewsStore
from investment_system.agents.news_interpretation.inputs import build_interpretation_request
from investment_system.llm.schemas import LLMResponse
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter
from investment_system.llm.openai_settings import strict_transport_schema
from scripts import run_phase4c2_news_smoke as cli


NOW = FIXTURE_TIME + timedelta(seconds=10)
MODEL = "offline-grounding-model"
CONFIG = ModelConfiguration(provider="openai", model=MODEL)


def request(text="Birch announced financing.", summary=None, **kwargs):
    return NewsInterpretationRequest(news=synthetic_record("quote-case", text, "", summary=summary),
        decision_time=FIXTURE_TIME, **kwargs)


def quote(req, text=None, field="headline"):
    source = next(e for e in req.evidence if e.field == field and e.revision_id == req.revision_id)
    return dict(evidence_id=source.evidence_id, quote=text or source.text)


def selection(req):
    q = quote(req)
    return dict(schema_version=MODEL_OUTPUT_VERSION, status="interpreted", events=[dict(
        event_key="1", event_type="financing", description="Reported financing event",
        state="confirmed", stage="announced", state_evidence=q, evidence=[q], entities=[])])


def response(data):
    return LLMResponse(provider="openai", model=MODEL, content=data if isinstance(data,str) else json.dumps(data),
        generated_at=NOW, input_tokens=100, cached_input_tokens=0, output_tokens=50, latency_ms=1,
        raw={"cache_write_tokens":100})


def evaluate(req, data):
    return evaluate_quote_response(req, response(data), CONFIG, validated_at=NOW,
        tokens_reported=True, latency_reported=True)


def settings():
    return GroundedRuntimeSettings(adapter=dict(provider="openai", model=MODEL,
        transport_version="openai-responses-settings-v2", endpoint="https://api.openai.com/v1/responses",
        response_mode="json_schema_strict", max_output_tokens=2048, timeout_seconds=30,
        reasoning_effort="none", service_tier="default", prompt_cache_mode="implicit", prompt_cache_ttl="30m",
        capabilities_model=MODEL, structured_outputs_supported=True, capability_max_output_tokens=128000,
        capability_max_input_tokens=922000, context_window_tokens=1050000, supported_parameters=["reasoning_effort"],
        capability_source="synthetic capability evidence", capabilities_verified_at=FIXTURE_TIME),
        pricing=dict(pricing_version="news-token-prices-v2", provider="openai", model=MODEL,
        input_per_million=0.2, cached_input_per_million=0.02, cache_write_per_million=0.25,
        output_per_million=1.2, short_context_max_input_tokens=272000, valid_from=FIXTURE_TIME,
        valid_until=NOW+timedelta(days=1), source="synthetic prices"), request_budget_usd=0.05,
        run_budget_usd=0.05, max_attempts=1, retry_invalid_response=False, retry_delay_seconds=0,
        local_content_retention_hours=24, local_restricted_storage_acknowledged=True)


class SimulatedClient(BaseLLMClient):
    provider="openai"
    def __init__(self, data): self.data=data; self.calls=0
    def complete(self, req, model):
        self.calls += 1
        assert "news-interpretation-prompt-v2" in req.prompt
        assert "start" not in req.response_schema["$defs"]["SelectedQuote"]["properties"]
        return response(self.data)


def service(tmp_path, data):
    client=SimulatedClient(data)
    storage=LocalInterpretationStore(tmp_path/"restricted", allowed_root=tmp_path)
    cfg=settings()
    router=LLMRouter({"openai":client},{"news_interpretation":{"provider":"openai","model":MODEL}})
    svc=NewsInterpretationService(router,cfg,storage,"grounding-test",execution_authorized=True,
        simulated=True,clock=lambda:NOW)
    return svc,client


def test_unique_exact_quote_offsets_provenance_and_reproducibility():
    req=request()
    original=response(selection(req))
    resolution,result=evaluate_quote_response(req,original,CONFIG,validated_at=NOW)
    assert result.status=="interpreted" and result.payload.schema_version=="news-interpretation-v1"
    assert result.provenance.content==original.content
    assert original.content==response(selection(req)).content
    assert result.prompt_version=="news-interpretation-prompt-v2"
    assert result.payload.events[0].state_evidence.start==0
    assert result.payload.events[0].state_evidence.end==len(req.news.headline)
    assert resolution.resolved_payload==result.payload and len(resolution.traces)==2
    envelope=GroundedReplayEnvelope(request=req,resolution=resolution,result=result)
    restored=GroundedReplayEnvelope.model_validate_json(envelope.model_dump_json())
    assert restored.envelope_id==envelope.envelope_id
    assert evaluate(req,selection(req))[0].resolution_id==resolution.resolution_id
    assert not result.operationally_eligible_at(NOW)


@pytest.mark.parametrize("change, rule", [
    (lambda q:q.update(quote="An invented announcement."), "quote_not_found_in_declared_field"),
    (lambda q:q.update(evidence_id="0"*64), "unknown_evidence_id"),
])
def test_missing_quote_or_source_rejected(change,rule):
    req=request(); data=selection(req)
    data=deepcopy(data); change(data["events"][0]["state_evidence"])
    resolution,result=evaluate(req,data)
    assert result.status=="invalid_response" and result.payload is None
    assert result.diagnostics[0].rule==rule
    assert result.diagnostics[0].field_path==("events",0,"state_evidence")
    assert result.diagnostics[0].stage=="evidence_resolution"


@pytest.mark.parametrize("source, selected",[("Birch announced financing. Birch announced financing.","Birch announced financing."),("aaaa", "aaa")])
def test_repeated_and_overlapping_quotes_never_choose_first(source,selected):
    req=request(source); data=selection(req)
    data["events"][0]["state_evidence"]=quote(req,selected)
    _,result=evaluate(req,data)
    assert result.diagnostics[0].rule=="ambiguous_quote"


def test_repeated_short_entity_can_use_unique_larger_quote():
    req=request("Birch announced financing. Birch expects further discussions.")
    data=selection(req)
    data["events"][0].update(state_evidence=quote(req,"Birch announced financing."),
        evidence=[quote(req,"Birch announced financing.")],
        entities=[dict(name="Birch",role="actor",evidence=quote(req,"Birch announced financing."))])
    _,result=evaluate(req,data)
    assert result.status=="interpreted"


def test_unicode_half_open_offsets_and_no_normalization():
    req=request("🚀 Intro. Élan announced financing.")
    data=selection(req)
    q=quote(req,"Élan announced financing.")
    data["events"][0].update(state_evidence=q,evidence=[q])
    resolution,result=evaluate(req,data)
    assert result.status=="interpreted"
    assert resolution.traces[0].start==req.news.headline.index(q["quote"])
    assert req.news.headline[resolution.traces[0].start:resolution.traces[0].end]==q["quote"]
    altered=deepcopy(data); altered["events"][0]["state_evidence"]["quote"]="E\u0301lan announced financing."
    assert evaluate(req,altered)[1].diagnostics[0].rule=="quote_not_found_in_declared_field"


def test_declared_field_is_authoritative_not_cross_field_search():
    req=request(summary="Birch announced a separate agreement.")
    data=selection(req)
    wrong=quote(req,"Birch announced a separate agreement.",field="headline")
    data["events"][0].update(state_evidence=wrong,evidence=[wrong])
    assert evaluate(req,data)[1].diagnostics[0].rule=="quote_not_found_in_declared_field"
    correct=quote(req,"Birch announced a separate agreement.",field="summary")
    data["events"][0].update(state_evidence=correct,evidence=[correct])
    assert evaluate(req,data)[1].status=="interpreted"


def test_same_quote_in_two_fields_uses_declared_id_only():
    req=request(summary="Birch announced financing.")
    for field in ("headline","summary"):
        data=selection(req); q=quote(req,field=field)
        data["events"][0].update(state_evidence=q,evidence=[q])
        resolution,result=evaluate(req,data)
        assert result.status=="interpreted" and resolution.traces[0].source_field==field


def test_even_eligible_context_revision_cannot_ground_primary_or_economics():
    context=synthetic_record("other-revision","Pine announced financing.","")
    req=request(context_news=(context,))
    source=next(e for e in req.evidence if e.revision_id==context.revision_id)
    q=dict(evidence_id=source.evidence_id,quote=source.text)
    for location in ("event","economic"):
        data=selection(req)
        if location=="event":data["events"][0]["state_evidence"]=q
        else:data["economics"]=dict(favorable=[dict(text="Reported expansion",category="reported_fact",evidence=[q])])
        assert evaluate(req,data)[1].diagnostics[0].rule=="wrong_revision"


def test_offsets_are_forbidden_in_new_model_output_and_tampering_detected():
    req=request(); data=selection(req)
    data["events"][0]["state_evidence"].update(start=0,end=10)
    assert evaluate(req,data)[1].diagnostics[0].stage=="model_schema"
    resolution,result=evaluate(req,selection(req))
    envelope=GroundedReplayEnvelope(request=req,resolution=resolution,result=result)
    altered=envelope.model_dump(mode="json"); altered["resolution"]["traces"][0]["start"]=1
    with pytest.raises(ValueError,match="transformation mismatch"):
        GroundedReplayEnvelope.model_validate(altered)
    altered=envelope.model_dump(mode="json")
    s=altered["result"]["payload"]["events"][0]["state_evidence"]
    s["start"]+=1; s["end"]+=1
    with pytest.raises(ValueError):GroundedReplayEnvelope.model_validate(altered)


def test_structured_schema_does_not_imply_grounding():
    req=request(); data=selection(req)
    data["events"][0]["state_evidence"]=quote(req,"Nonexistent source statement.")
    typed=QuoteSelectionPayload.model_validate(data)
    with pytest.raises(QuoteResolutionError):resolve_selected_quotes(typed,req)
    projected=strict_transport_schema(QuoteSelectionPayload.model_json_schema())
    assert projected["$defs"]["SelectedQuote"]["additionalProperties"] is False
    assert set(projected["$defs"]["SelectedQuote"]["required"])=={"evidence_id","quote"}


@pytest.mark.parametrize("name,ticker",[("OakData Cloud","OAK"),("Birch","OAK"),("OakData","WRONG")])
def test_product_and_wrong_ticker_not_mapped_to_corporation(name,ticker):
    entry=fixture_registry().entries[0].model_copy(update=dict(entity_id="oak",corporate_name="OakData",
        aliases=(),ticker="OAK",security_id="OAK-fixture"))
    req=request("Birch announced financing using OakData Cloud.",registry_entries=(entry,))
    data=selection(req)
    data["events"][0]["entities"]=[dict(name=name,role="subject",ticker=ticker,evidence=quote(req))]
    _,result=evaluate(req,data)
    assert result.status=="invalid_response" and result.diagnostics[0].rule=="entity_registry_mismatch"


def test_unresolved_product_and_eligible_corporate_identity_controls():
    entry=fixture_registry().entries[0].model_copy(update=dict(entity_id="oak",corporate_name="OakData",
        aliases=(),ticker="OAK",security_id="OAK-fixture"))
    req=request("OakData announced financing.",registry_entries=(entry,))
    data=selection(req)
    data["events"][0]["entities"]=[dict(name="OakData",role="actor",ticker="OAK",evidence=quote(req))]
    assert evaluate(req,data)[1].status=="interpreted"
    req=request("Birch announced financing using OakData Cloud.")
    data=selection(req)
    data["events"][0]["entities"]=[dict(name="OakData Cloud",role="subject",evidence=quote(req))]
    assert evaluate(req,data)[1].status=="interpreted"


def test_textual_date_stays_rejected_until_explicit_future_version():
    req=request("Birch announced financing on Jan. 02, 2026.")
    data=selection(req)
    data["events"][0].update(event_date="2026-01-02",date_evidence=quote(req,"Jan. 02, 2026"))
    resolution,result=evaluate(req,data)
    assert result.status=="invalid_response"
    assert result.diagnostics[0].stage=="internal_schema" and result.diagnostics[0].rule=="date_iso_literal_required"
    assert resolution.resolved_payload is None
    data["events"][0].update(event_date=None,date_evidence=None)
    assert evaluate(req,data)[1].status=="interpreted"


def test_literal_iso_date_and_no_publication_date_auto_attribution():
    req=request("Birch announced financing on 2026-01-02.")
    data=selection(req); data["events"][0].update(event_date="2026-01-02",date_evidence=quote(req,"2026-01-02"))
    assert evaluate(req,data)[1].status=="interpreted"
    req=request(); resolution,result=evaluate(req,selection(req))
    assert result.payload.events[0].event_date is None and result.payload.events[0].date_evidence is None


def test_rumor_cannot_become_confirmation():
    req=request("Birch may seek financing according to an unconfirmed rumor.")
    data=selection(req); data["events"][0]["stage"]="unknown"
    assert evaluate(req,data)[1].diagnostics[0].rule=="state_not_supported"
    data["events"][0]["state"]="rumor"
    assert evaluate(req,data)[1].status=="interpreted"


def test_negation_preserved():
    req=request("Birch announced it will not pursue financing.")
    data=selection(req)
    assert evaluate(req,data)[1].diagnostics[0].rule=="negation_lost"
    data["events"][0]["negated"]=True
    assert evaluate(req,data)[1].status=="interpreted"


def test_numbers_units_still_run_original_validators_after_resolution():
    req=request("Birch announced financing of 7 million USD.")
    data=selection(req)
    number=dict(metric="financing",value="7",value_text="7",unit="USD",scale="million",context=quote(req))
    data["events"][0]["numbers"]=[number]
    assert evaluate(req,data)[1].status=="interpreted"
    number["unit"]="EUR"
    assert evaluate(req,data)[1].diagnostics[0].rule=="numeric_fidelity"


def test_abstention_has_no_resolution_or_invented_neutral_result():
    req=request("Generic corporate commentary.")
    data=dict(schema_version=MODEL_OUTPUT_VERSION,status="abstained",abstention_reasons=["insufficient_evidence"])
    resolution,result=evaluate(req,data)
    assert result.status=="abstained" and resolution.traces==()
    data["economics"]=dict(stance="neutral")
    assert evaluate(req,data)[1].status=="invalid_response"


@pytest.mark.parametrize("malformed", ['not JSON','{"status":"abstained","status":"interpreted"}'])
def test_json_stage_diagnostics(malformed):
    _,result=evaluate(request(),malformed)
    assert result.diagnostics[0].stage=="json"


def test_safe_diagnostics_never_echo_unknown_keys_or_private_values(capsys,caplog):
    req=request(); data=selection(req); data["private-do-not-publish-key"]="private-do-not-publish-content"
    _,result=evaluate(req,data)
    output=json.dumps([d.model_dump(mode="json") for d in result.diagnostics])
    assert "private-do-not-publish" not in output and "unknown_field" in output
    assert not capsys.readouterr().out and not caplog.text


def test_runtime_cache_persistence_retention_and_exact_original_response(tmp_path):
    req=request(); data=selection(req); svc,client=service(tmp_path,data)
    delivery=svc.interpret(req); record=delivery.record
    assert client.calls==1 and record.outcome=="interpreted"
    assert record.schema_version=="news-inference-attempt-v3"
    assert record.provider_response.content==response(data).content
    assert record.interpretation.result.provenance.content==record.provider_response.content
    assert record.interpretation.resolution.resolved_payload==record.interpretation.result.payload
    assert svc.reconstruct(delivery.record_id).record.record_id==delivery.record_id
    assert svc.interpret(req).retrieval_mode=="exact_cache_recovery" and client.calls==1
    dumped=json.loads(svc.storage.record_path(delivery.record_id).read_text())
    assert ATTEMPT_ADAPTER.validate_python(dumped).record_id==delivery.record_id
    with pytest.raises(ValueError,match="retention expired"):
        svc.storage.read(delivery.record_id,now=NOW+timedelta(days=2))


def test_invalid_grounding_stored_sanitized_and_not_cached_or_retried(tmp_path):
    req=request(); data=selection(req); data["events"][0]["state_evidence"]=quote(req,"invented")
    svc,client=service(tmp_path,data); delivery=svc.interpret(req)
    assert client.calls==1 and delivery.record.outcome=="invalid_response"
    assert delivery.record.rejection_diagnostics[0].rule=="quote_not_found_in_declared_field"
    assert svc.storage.cache_get(delivery.cache_key,now=NOW) is None
    assert delivery.additional_provider_cost_usd>0


def test_original_request_pit_and_future_revision_invariance(tmp_path):
    store=NewsStore(tmp_path/"raw",tmp_path/"processed")
    original=synthetic_record("pit", "Birch announced financing.", "")
    store.write_records([original])
    before=build_interpretation_request(store,original.revision_id,FIXTURE_TIME)
    first=evaluate(before,selection(before))
    revised=synthetic_record("pit","Birch completed financing.","",available_at=FIXTURE_TIME+timedelta(days=1))
    store.write_records([revised])
    after=build_interpretation_request(store,original.revision_id,FIXTURE_TIME)
    second=evaluate(after,selection(after))
    assert before.request_id==after.request_id and first[0].resolution_id==second[0].resolution_id
    assert first[1].result_id==second[1].result_id
    with pytest.raises(ValueError):build_interpretation_request(store,revised.revision_id,FIXTURE_TIME)
    future=fixture_registry().entries[0].model_copy(update={"known_at":NOW})
    with pytest.raises(ValueError):request(registry_entries=(future,))


def test_timestamp_provenance_not_backdated():
    req=request()
    with pytest.raises(ValueError,match="generation predates"):
        evaluate_quote_response(req,response(selection(req)).model_copy(update={"generated_at":FIXTURE_TIME-timedelta(seconds=1)}),CONFIG,validated_at=NOW)
    _,result=evaluate(req,selection(req))
    assert result.available_at==NOW and not result.operationally_eligible_at(FIXTURE_TIME)


def test_legacy_replay_and_invocation_unchanged_new_cache_namespace():
    req=request(); legacy_data=dict(status="abstained",abstention_reasons=["insufficient_evidence"])
    old=replay_response(req,response(legacy_data),CONFIG,validated_at=NOW)
    envelope=ReplayEnvelope(request=req,result=old)
    assert ReplayEnvelope.model_validate_json(envelope.model_dump_json()).envelope_id==envelope.envelope_id
    assert prepare_llm_request(req,CONFIG).prompt.startswith("news-interpretation-prompt-v1")
    cfg=settings(); raw=cfg.model_dump(mode="json")
    for field in ("model_output_version","prompt_version","resolver_version"):raw.pop(field)
    raw["settings_version"]="news-inference-settings-v2"
    old_settings=InterpretationRuntimeSettings.model_validate(raw)
    old_wire=prepare_invocation(req,old_settings)
    new_wire=prepare_invocation(req,cfg)
    assert old_wire[2]!=new_wire[2] and old_wire[1]!=new_wire[1]
    assert "start" in old_wire[1]["text"]["format"]["schema"]["$defs"]["EvidenceSpan"]["properties"]
    assert "start" not in new_wire[1]["text"]["format"]["schema"]["$defs"]["SelectedQuote"]["properties"]


def test_legacy_attempt_v2_still_readable_without_migrating_identity(tmp_path):
    req=request(); cfg=settings(); raw=cfg.model_dump(mode="json")
    for field in ("model_output_version","prompt_version","resolver_version"):raw.pop(field)
    raw["settings_version"]="news-inference-settings-v2"
    legacy_cfg=InterpretationRuntimeSettings.model_validate(raw)
    class LegacyClient(BaseLLMClient):
        provider="openai"
        def complete(self, req, model):
            return response(dict(status="abstained",abstention_reasons=["insufficient_evidence"]))
    storage=LocalInterpretationStore(tmp_path/"legacy",allowed_root=tmp_path)
    router=LLMRouter({"openai":LegacyClient()},{"news_interpretation":{"provider":"openai","model":MODEL}})
    svc=NewsInterpretationService(router,legacy_cfg,storage,"legacy",execution_authorized=True,
        simulated=True,clock=lambda:NOW)
    delivery=svc.interpret(req)
    original_bytes=storage.record_path(delivery.record_id).read_bytes()
    restored=ATTEMPT_ADAPTER.validate_json(original_bytes)
    assert restored.record_id==delivery.record_id and restored.schema_version=="news-inference-attempt-v2"
    assert restored.interpretation.schema_version=="news-interpretation-replay-v1"
    assert "rejection_diagnostics" not in restored.model_dump()
    assert storage.read(delivery.record_id,now=NOW).record_id==delivery.record_id
    assert storage.record_path(delivery.record_id).read_bytes()==original_bytes


def test_new_settings_offline_cli_does_not_load_credentials_or_persist(tmp_path,monkeypatch,capsys):
    import yaml
    from datetime import datetime
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return NOW
    req=request(); path=tmp_path/"v3.yaml"
    path.write_text(yaml.safe_dump(settings().model_dump(mode="json")))
    monkeypatch.setattr(cli,"datetime",FrozenDateTime)
    monkeypatch.setattr(cli,"build_interpretation_request",lambda *a,**k:req)
    monkeypatch.setattr(cli,"load_entity_registry",lambda:None)
    monkeypatch.setattr(cli,"NewsStore",lambda *a:None)
    def forbidden(*args,**kwargs):pytest.fail("offline preflight must not initialize external state")
    monkeypatch.setattr(cli,"load_repository_environment",forbidden)
    monkeypatch.setattr(cli,"LocalInterpretationStore",forbidden)
    monkeypatch.setattr("sys.argv",["smoke","--config",str(path),"--model",MODEL,"--budget-usd","0.05",
        "--revision-id",req.revision_id,"--as-of",FIXTURE_TIME.isoformat(),"--validate-only"])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["provider_calls"]==result["persistence_writes"]==0
    assert result["model_output_version"]==MODEL_OUTPUT_VERSION


def test_excessive_json_nesting_fails_closed_with_safe_diagnostic():
    nested="["*2000+"0"+"]"*2000
    resolution,result=evaluate(request(),nested)
    assert result.status=="invalid_response"
    assert result.diagnostics[0].rule in {"invalid_json","structural_contract_violation"}


def test_new_setting_bindings_reject_mixed_or_unknown_versions():
    raw=settings().model_dump(mode="json")
    raw["resolver_version"]="future-unapproved"
    with pytest.raises(ValueError):GroundedRuntimeSettings.model_validate(raw)
    raw=settings().model_dump(mode="json")
    raw["settings_version"]="news-inference-settings-v2"
    with pytest.raises(ValueError):GroundedRuntimeSettings.model_validate(raw)


def test_new_model_contract_requires_explicit_version_no_legacy_guessing():
    req=request(); data=selection(req); data.pop("schema_version")
    assert evaluate(req,data)[1].diagnostics[0].stage=="model_schema"


def test_runtime_stamps_availability_after_resolution_and_validation(tmp_path):
    req=request(); svc,_=service(tmp_path,selection(req))
    values=[NOW+timedelta(seconds=i) for i in range(10)]
    moments=iter(values)
    svc.clock=lambda:next(moments)
    result=svc.interpret(req).record
    assert result.interpretation.resolution.resolved_at==NOW+timedelta(seconds=4)
    assert result.interpretation.result.available_at==result.interpretation.resolution.resolved_at
    assert result.persisted_at>result.interpretation.result.available_at
