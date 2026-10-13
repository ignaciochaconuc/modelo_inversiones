"""Adversarial fictional development cases, never either licensed real smoke."""
from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest

from test_news_quote_grounding import NOW, MODEL, CONFIG, settings as grounded_settings, response
from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest
from investment_system.agents.news_interpretation.economic_attribution import (
    MODEL_OUTPUT_VERSION, EconomicSelectionPayload, EconomicReplayEnvelope, ConsumerEntity,
    evaluate_economic_response, prepare_economic_request,
)
from investment_system.agents.news_interpretation.runtime_schemas import EconomicRuntimeSettings
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore, ATTEMPT_ADAPTER
from investment_system.agents.news_interpretation.service import NewsInterpretationService, prepare_invocation
from investment_system.data.news_evaluation import FIXTURE_TIME, synthetic_record, fixture_registry
from investment_system.data.storage.news_store import NewsStore
from investment_system.agents.news_interpretation.inputs import build_interpretation_request
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter
from scripts import run_phase4c2_news_smoke as cli


def registry():
    base=fixture_registry().entries[0]
    return tuple(base.model_copy(update=dict(entity_id=name.lower(),corporate_name=name,aliases=(),
        ticker=ticker,security_id=ticker+"-fictional")) for name,ticker in (("Birch","BIR"),("Pine","PIN"),("Aster","AST")))


def request(text="Birch acquired Pine.",**kwargs):
    return NewsInterpretationRequest(news=synthetic_record("attribution-case",text,""),decision_time=FIXTURE_TIME,
        registry_entries=kwargs.pop("registry_entries",registry()),**kwargs)


def quote(req,text=None):return dict(evidence_id=req.evidence[0].evidence_id,quote=text or req.news.headline)


def entity(req,name="Birch",attribution="direct_participant",role="buyer",peer="Pine",relation="transaction"):
    return dict(name=name,mention_kind="company",evidence=quote(req),registry_entity_id=name.lower(),
        identity_evidence=quote(req,name),attribution=attribution,participation_role=role,
        relation_type=relation,related_entity=peer,relation_state="reported",relationship_evidence=quote(req))


def context(req,name="Aster",kind="company",resolved=True):
    return dict(name=name,mention_kind=kind,evidence=quote(req),attribution="contextual_mention",
        registry_entity_id=name.lower() if resolved else None,identity_evidence=quote(req,name) if resolved else None)


def payload(req,entities=None,kind="ma",state_quote=None):
    q=quote(req,state_quote)
    return dict(schema_version=MODEL_OUTPUT_VERSION,status="interpreted",events=[dict(
        event_key="1",event_type=kind,description="Reported corporate event",state="confirmed",stage="unknown",
        state_evidence=q,evidence=[q],entities=entities if entities is not None else [entity(req)])])


def evaluate(req,data):
    return evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)


def views(req,data):
    resolution,result=evaluate(req,data)
    envelope=EconomicReplayEnvelope(request=req,resolution=resolution,result=result)
    return envelope.consumer_entities()


def settings():
    raw=grounded_settings().model_dump(mode="json")
    raw.update(settings_version="news-inference-settings-v4",model_output_version=MODEL_OUTPUT_VERSION,
        prompt_version="news-interpretation-prompt-v3",attribution_version="news-economic-attribution-v1")
    return EconomicRuntimeSettings.model_validate(raw)


def test_direct_party_identity_participation_and_exposure_are_different():
    req=request(); resolution,result=evaluate(req,payload(req))
    assert result.status=="interpreted"
    e=result.payload.events[0].entities[0]
    assert e.identity.ticker=="BIR" and e.attribution=="direct_participant"
    assert not hasattr(e,"ticker") and e.potential_impact.confirmed_exposure is False
    v=views(req,payload(req))[0]
    assert v.reported_participant and v.economic_ticker=="BIR"
    assert v.confirmed_exposure is False and v.operational is False


def test_acquisition_target_is_not_the_buyer():
    req=request(); data=payload(req,[entity(req),entity(req,"Pine",role="target",peer="Birch")])
    assert evaluate(req,data)[1].status=="interpreted"
    data["events"][0]["entities"][1]["participation_role"]="buyer"
    assert evaluate(req,data)[1].diagnostics[0].rule=="attribution_not_explicit"


def test_recognized_context_company_is_not_economic_participation():
    req=request("Birch acquired Pine. Aster is mentioned for comparison.")
    data=payload(req,[entity(req),context(req)])
    result=evaluate(req,data)[1]
    assert result.status=="interpreted" and result.payload.events[0].entities[1].identity.ticker=="AST"
    v=views(req,data)[1]
    assert v.attribution=="contextual_mention" and not v.reported_participant and v.economic_ticker is None


@pytest.mark.parametrize("kind",["product","platform"])
def test_product_or_platform_cannot_inherit_manufacturer_registry_identity(kind):
    req=request("Birch acquired Pine to integrate Aster Cloud.")
    e=context(req,"Aster Cloud",kind=kind,resolved=False)
    data=payload(req,[entity(req),e]); result=evaluate(req,data)[1]
    assert result.status=="interpreted" and result.payload.events[0].entities[1].identity.state=="unknown"
    e["registry_entity_id"]="aster"; e["identity_evidence"]=quote(req,"Aster")
    assert evaluate(req,data)[1].diagnostics[0].rule=="product_identity_forbidden"


@pytest.mark.parametrize("text",[
    "Birch acquired Pine using Aster Cloud.",
    "Aster's platform is used. Birch acquired Pine.",
    "Aster sells software while Birch acquired Pine.",
    "Aster Cloud acquired Pine for its product catalog.",
])
def test_corporate_alias_inside_product_or_near_other_parties_is_not_a_buyer(text):
    req=request(text)
    e=entity(req,"Aster",role="buyer",peer="Pine")
    data=payload(req,[e])
    _,result=evaluate(req,data)
    assert result.status=="invalid_response" and result.diagnostics[0].rule=="attribution_not_explicit"


def test_words_acquisition_and_supplier_do_not_replace_entity_specific_frame():
    req=request("Birch acquired Pine; Aster is a supplier of reports for unrelated users.")
    e=entity(req,"Aster",role="supplier",peer="Birch",relation="supply_contract")
    assert evaluate(req,payload(req,[e]))[1].status=="invalid_response"


def test_supplier_with_explicit_event_contract_and_customer_roles():
    req=request("Aster will supply Birch under a supply agreement.")
    e=entity(req,"Aster",role="supplier",peer="Birch",relation="supply_contract")
    data=payload(req,[e],kind="partnership")
    assert evaluate(req,data)[1].status=="interpreted"
    req=request("Birch signed a purchase contract with Aster.")
    e=entity(req,"Birch",role="customer",peer="Aster",relation="supply_contract")
    assert evaluate(req,payload(req,[e],kind="partnership"))[1].status=="interpreted"


@pytest.mark.parametrize("relation,text",[
    ("supply_contract","Aster supplies Birch."),
    ("competition","Aster competes with Birch."),
    ("ownership","Aster is a parent company of Birch."),
    ("platform_license","Aster licenses its platform to Birch."),
])
def test_explicit_indirect_relations_never_become_direct_exposure(relation,text):
    req=request("Birch acquired Pine. "+text)
    direct=entity(req)
    direct["identity_evidence"]=quote(req,"Birch acquired Pine.")
    indirect=entity(req,"Aster",attribution="supported_indirect",role="unknown",peer="Birch",relation=relation)
    data=payload(req,[direct,indirect])
    assert evaluate(req,data)[1].status=="interpreted"
    v=views(req,data)[1]
    assert v.attribution=="supported_indirect" and v.economic_ticker is None and not v.confirmed_exposure


def test_related_peer_must_be_participant_in_this_event_not_unrelated_context():
    req=request("Birch acquired Pine. Aster competes with Willow.")
    e=entity(req,"Aster",attribution="supported_indirect",role="unknown",peer="Willow",relation="competition")
    assert evaluate(req,payload(req,[entity(req),e]))[1].diagnostics[0].rule=="attribution_not_explicit"


def test_relation_from_different_event_cannot_be_attached_to_this_subject():
    req=request("Birch acquired Pine. Aster acquired Willow.")
    data=payload(req,[entity(req,"Aster",peer="Willow")],state_quote="Birch acquired Pine.")
    data["events"][0]["entities"][0]["relationship_evidence"]=quote(req,"Aster acquired Willow.")
    assert evaluate(req,data)[1].diagnostics[0].rule=="attribution_not_explicit"


def test_unresolved_subsidiary_does_not_get_parent_ticker():
    req=request("Birch Labs issued bonds. Aster is a parent company of Birch Labs.")
    child=entity(req,"Birch Labs",role="issuer",peer=None)
    child.update(mention_kind="subsidiary",registry_entity_id=None,identity_evidence=None)
    parent=entity(req,"Aster",attribution="supported_indirect",role="unknown",peer="Birch Labs",relation="ownership")
    data=payload(req,[child,parent],kind="financing")
    result=evaluate(req,data)[1]
    assert result.status=="interpreted" and result.payload.events[0].entities[0].identity.ticker is None
    assert all(v.economic_ticker is None for v in views(req,data))
    child["registry_entity_id"]="aster"; child["identity_evidence"]=quote(req,"Aster")
    assert evaluate(req,data)[1].diagnostics[0].rule=="identity_not_supported"


def test_unknown_relations_are_preserved_without_invented_identity():
    req=request("Birch acquired Pine. Willow is mentioned.")
    e=context(req,"Willow",resolved=False); e["attribution"]="unknown"
    data=payload(req,[entity(req),e])
    result=evaluate(req,data)[1]
    assert result.status=="interpreted" and result.payload.events[0].entities[1].identity.state=="unknown"
    assert views(req,data)[1].economic_ticker is None


def test_direct_participant_without_specific_evidence_is_rejected():
    req=request(); e=entity(req); e["relationship_evidence"]=None
    assert evaluate(req,payload(req,[e]))[1].diagnostics[0].rule=="attribution_evidence_required"


def test_context_cannot_smuggle_a_role_relation_or_potential_impact():
    req=request("Birch acquired Pine. Aster is mentioned.")
    for modification in (dict(participation_role="buyer"),dict(relationship_evidence=quote(req)),
                         dict(potential_impact=dict(status="potential",channel="commercial",evidence=quote(req),rationale="Possible channel"))):
        e=context(req); e.update(modification)
        assert evaluate(req,payload(req,[entity(req),e]))[1].diagnostics[0].rule=="contextual_participation_forbidden"


def test_potential_impact_is_conditional_and_never_confirmed_exposure():
    req=request(); e=entity(req)
    e["potential_impact"]=dict(status="potential",channel="ownership",evidence=quote(req),rationale="Ownership changes may alter integration requirements; outcomes unknown.")
    data=payload(req,[e]); result=evaluate(req,data)[1]
    assert result.status=="interpreted" and not views(req,data)[0].confirmed_exposure
    e["potential_impact"]["confirmed_exposure"]=True
    assert evaluate(req,data)[1].diagnostics[0].stage=="model_schema"


def test_unrelated_impact_quote_or_return_estimate_rejected():
    req=request("Birch acquired Pine. Aster mentioned weather."); e=entity(req)
    e["potential_impact"]=dict(status="potential",channel="commercial",evidence=quote(req,"Aster mentioned weather."),rationale="Potential benefits")
    assert evaluate(req,payload(req,[e]))[1].diagnostics[0].rule=="impact_not_supported"
    e["potential_impact"]=dict(status="potential",channel="commercial",evidence=quote(req),rationale="Expected return 10%")
    assert evaluate(req,payload(req,[e]))[1].diagnostics[0].rule=="prohibited_output"


def test_consumer_contract_rejects_context_ticker_and_confirmed_exposure():
    baseline=dict(name="Aster",attribution="contextual_mention",reported_participant=False,potential_impact="not_assessed")
    for change in (dict(economic_ticker="AST"),dict(reported_participant=True),dict(confirmed_exposure=True),dict(operational=True),dict(potential_impact="potential")):
        with pytest.raises(ValueError):ConsumerEntity.model_validate({**baseline,**change})


def test_rumor_and_negation_still_fail_closed():
    req=request("Birch may acquire Pine according to a rumor.")
    e=entity(req); data=payload(req,[e])
    assert evaluate(req,data)[1].status=="invalid_response"
    req=request("Birch announced it has not acquired Pine.")
    assert evaluate(req,payload(req))[1].status=="invalid_response"


def test_company_identity_unavailable_at_cutoff_is_never_added():
    future=registry()[0].model_copy(update={"known_at":NOW})
    with pytest.raises(ValueError):request(registry_entries=(future,))
    req=request(registry_entries=())
    assert evaluate(req,payload(req))[1].diagnostics[0].rule=="identity_not_supported"


def test_original_exact_resolver_wrong_revision_and_ambiguity_preserved():
    req=request("Birch acquired Pine. Birch acquired Pine.")
    data=payload(req); data["events"][0]["state_evidence"]=quote(req,"Birch acquired Pine.")
    assert evaluate(req,data)[1].diagnostics[0].rule=="ambiguous_quote"
    ctx=synthetic_record("context","Birch acquired Pine.","")
    req=request(context_news=(ctx,)); data=payload(req)
    src=next(e for e in req.evidence if e.revision_id==ctx.revision_id)
    data["events"][0]["entities"][0]["relationship_evidence"]=dict(evidence_id=src.evidence_id,quote=src.text)
    assert evaluate(req,data)[1].diagnostics[0].rule=="wrong_revision"


def test_replay_provenance_tampering_and_context_projection_bypass_rejected():
    req=request("Birch acquired Pine. Aster is mentioned."); data=payload(req,[entity(req),context(req)])
    resolution,result=evaluate(req,data)
    original=response(data).content
    envelope=EconomicReplayEnvelope(request=req,resolution=resolution,result=result)
    assert result.provenance.content==original
    restored=EconomicReplayEnvelope.model_validate_json(envelope.model_dump_json())
    assert restored.envelope_id==envelope.envelope_id
    malicious=envelope.model_dump(mode="json")
    malicious["result"]["payload"]["events"][0]["entities"][1]["attribution"]="direct_participant"
    with pytest.raises(ValueError):EconomicReplayEnvelope.model_validate(malicious)
    bad=result.model_copy(update={"payload":result.payload.model_copy(update={"events":()})})
    forged=envelope.model_copy(update={"result":bad})
    with pytest.raises(ValueError):forged.consumer_entities()


def test_new_output_requires_version_and_does_not_accept_old_smoke_shape():
    req=request(); data=payload(req); data["schema_version"]="news-quote-selection-v2"
    assert evaluate(req,data)[1].diagnostics[0].stage=="model_schema"
    data=payload(req); data["events"][0]["entities"][0]["ticker"]="BIR"
    assert evaluate(req,data)[1].diagnostics[0].stage=="model_schema"


def test_safe_diagnostics_do_not_echo_unknown_fields_or_claim_text(capsys,caplog):
    req=request(); data=payload(req); data["secret-field"]="private-content"
    _,result=evaluate(req,data)
    report=json.dumps([d.model_dump(mode="json") for d in result.diagnostics])
    assert "secret-field" not in report and "private-content" not in report
    assert not capsys.readouterr().out and not caplog.text


def test_runtime_cost_cache_retention_and_original_bytes(tmp_path):
    req=request(); data=payload(req)
    class Client(BaseLLMClient):
        provider="openai"
        calls=0
        def complete(self,request,model):
            self.calls+=1
            assert request.prompt.startswith("news-interpretation-prompt-v3")
            return response(data)
    client=Client(); cfg=settings(); storage=LocalInterpretationStore(tmp_path/"restricted",allowed_root=tmp_path)
    router=LLMRouter({"openai":client},{"news_interpretation":{"provider":"openai","model":MODEL}})
    service=NewsInterpretationService(router,cfg,storage,"economic-test",execution_authorized=True,simulated=True,clock=lambda:NOW)
    first=service.interpret(req); assert first.record.outcome=="interpreted" and first.record.schema_version=="news-inference-attempt-v4"
    assert first.record.provider_response.content==response(data).content
    assert service.interpret(req).retrieval_mode=="exact_cache_recovery" and client.calls==1
    assert service.reconstruct(first.record_id).record.record_id==first.record_id
    assert ATTEMPT_ADAPTER.validate_json(storage.record_path(first.record_id).read_bytes()).record_id==first.record_id
    assert first.additional_provider_cost_usd>0
    with pytest.raises(ValueError):storage.read(first.record_id,now=NOW+timedelta(days=2))


def test_cache_identity_separates_v3_and_v4():
    req=request()
    assert prepare_invocation(req,settings())[2]!=prepare_invocation(req,grounded_settings())[2]
    assert prepare_economic_request(req,CONFIG).response_schema["properties"]["schema_version"]["const"]==MODEL_OUTPUT_VERSION


def test_future_revision_does_not_change_historical_attribution(tmp_path):
    from datetime import timedelta
    store=NewsStore(tmp_path/"raw",tmp_path/"processed"); req=request()
    store.write_records([req.news]); before=build_interpretation_request(store,req.revision_id,FIXTURE_TIME,
        registry=fixture_registry().model_copy(update={"entries":registry()}))
    first=evaluate(before,payload(before))
    tomorrow=FIXTURE_TIME+timedelta(days=1)
    store.write_records([synthetic_record("attribution-case","Aster acquired Birch.","",available_at=tomorrow)])
    after=build_interpretation_request(store,req.revision_id,FIXTURE_TIME,registry=fixture_registry().model_copy(update={"entries":registry()}))
    assert before==after and evaluate(after,payload(after))[1].result_id==first[1].result_id


def test_abstention_preserved():
    req=request(); data=dict(schema_version=MODEL_OUTPUT_VERSION,status="abstained",abstention_reasons=["insufficient_evidence"])
    resolution,result=evaluate(req,data)
    assert result.status=="abstained" and not EconomicReplayEnvelope(request=req,resolution=resolution,result=result).consumer_entities()


def test_ambiguous_security_registry_ref_never_selects_last_or_first():
    entries=registry()
    other_share=entries[0].model_copy(update={"security_id":"BIR-other-class","ticker":"BIRB"})
    req=request(registry_entries=(*entries,other_share))
    assert evaluate(req,payload(req))[1].diagnostics[0].rule=="identity_ambiguous"
    data=payload(req); data["events"][0]["entities"][0].update(registry_entity_id=None,identity_evidence=None)
    assert evaluate(req,data)[1].status=="interpreted" and views(req,data)[0].economic_ticker is None


def test_signed_contract_does_not_identify_supplier_direction_automatically():
    req=request("Aster signed a supply contract with Birch.")
    e=entity(req,"Aster",role="contract_party",peer="Birch",relation="supply_contract")
    data=payload(req,[e],kind="partnership")
    assert evaluate(req,data)[1].status=="interpreted"
    e["participation_role"]="supplier"
    assert evaluate(req,data)[1].diagnostics[0].rule=="attribution_not_explicit"


def test_all_new_fields_remain_strictly_source_grounded_and_dates_unexpanded():
    req=request("Birch acquired Pine on Jan. 02, 2026.")
    data=payload(req); data["events"][0].update(event_date="2026-01-02",date_evidence=quote(req,"Jan. 02, 2026"))
    assert evaluate(req,data)[1].diagnostics[0].rule=="date_iso_literal_required"
    data=payload(req); data["events"][0]["entities"][0]["identity_evidence"]=quote(req,"Invented corporate identity")
    assert evaluate(req,data)[1].diagnostics[0].rule=="quote_not_found_in_declared_field"


def test_new_cli_preflight_never_initializes_credentials_storage_or_provider(tmp_path,monkeypatch,capsys):
    import yaml
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return NOW
    req=request(); cfg=tmp_path/"v4.yaml"
    cfg.write_text(yaml.safe_dump(settings().model_dump(mode="json")))
    monkeypatch.setattr(cli,"datetime",FrozenDateTime)
    monkeypatch.setattr(cli,"build_interpretation_request",lambda *a,**k:req)
    monkeypatch.setattr(cli,"load_entity_registry",lambda:None)
    monkeypatch.setattr(cli,"NewsStore",lambda *a:None)
    def forbidden(*a,**k):pytest.fail("offline preflight cannot initialize external state")
    monkeypatch.setattr(cli,"load_repository_environment",forbidden)
    monkeypatch.setattr(cli,"LocalInterpretationStore",forbidden)
    monkeypatch.setattr("sys.argv",["smoke","--config",str(cfg),"--model",MODEL,"--budget-usd","0.05",
        "--revision-id",req.revision_id,"--as-of",FIXTURE_TIME.isoformat(),"--validate-only"])
    assert cli.main()==0
    data=json.loads(capsys.readouterr().out)
    assert data["provider_calls"]==data["persistence_writes"]==0 and data["model_output_version"]==MODEL_OUTPUT_VERSION
