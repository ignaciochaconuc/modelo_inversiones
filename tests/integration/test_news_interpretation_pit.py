"""4C.1 simulations never execute external inference or become historical signals."""
from datetime import timedelta
import json

import pytest

from investment_system.agents.news_interpretation.inputs import build_interpretation_request
from investment_system.agents.news_interpretation.replay import ReplayEnvelope, prepare_llm_request, replay_response
from investment_system.agents.news_interpretation.schemas import ModelConfiguration, NewsInterpretationRequest, InterpretationTarget
from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry, synthetic_record
from investment_system.data.news_grouping import build_news_groups_as_of
from investment_system.data.schemas.news import AvailableAtSource, NewsQueryMode
from investment_system.data.storage.news_store import NewsStore
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter
from investment_system.llm.schemas import LLMResponse


CONFIG=ModelConfiguration(provider="simulated",model="news-fixture-v1")


def populated(tmp_path):
    store=NewsStore(tmp_path/"raw",tmp_path/"processed")
    primary=synthetic_record("individual","Cedar announced financing of 3 million USD.","")
    store.write_records([primary])
    return store,primary


def test_strict_latest_revision_selection_and_future_invariance(tmp_path):
    store,primary=populated(tmp_path)
    before=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,registry=fixture_registry())
    tomorrow=FIXTURE_TIME+timedelta(days=1)
    revised=synthetic_record("individual","Cedar completed financing of 4 million USD.","",available_at=tomorrow)
    future=synthetic_record("future","Harbor reported corporate news.","",available_at=tomorrow)
    store.write_records([revised,future])
    entry=fixture_registry().entries[0].model_copy(update={"corporate_name":"Cedar Future","known_at":tomorrow})
    registry=fixture_registry().model_copy(update={"version":"future-global-registry","entries":(*fixture_registry().entries,entry)})
    after=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,registry=registry)
    assert before.request_id == after.request_id and before.evidence_fingerprint == after.evidence_fingerprint
    with pytest.raises(ValueError,match="future, obsolete or missing"):
        build_interpretation_request(store,revised.revision_id,FIXTURE_TIME)
    with pytest.raises(ValueError,match="future, obsolete or missing"):
        build_interpretation_request(store,primary.revision_id,tomorrow)
    current=build_interpretation_request(store,revised.revision_id,tomorrow)
    assert current.news_id == before.news_id and current.revision_id != before.revision_id


def test_direct_contract_rejects_future_registry_and_after_cutoff_retrieval(tmp_path):
    store,primary=populated(tmp_path)
    tomorrow=FIXTURE_TIME+timedelta(days=1)
    entry=fixture_registry().entries[0].model_copy(update={"known_at":tomorrow})
    with pytest.raises(ValueError,match="future registry"):
        NewsInterpretationRequest(news=primary,decision_time=FIXTURE_TIME,registry_entries=(entry,))
    late=primary.model_copy(update={"first_seen_at":tomorrow,"ingested_at":tomorrow,
                                  "available_at_source":AvailableAtSource.PROVIDER_TIMESTAMP})
    with pytest.raises(ValueError,match="retrieved/ingested"):
        NewsInterpretationRequest(news=late,decision_time=FIXTURE_TIME)
    with pytest.raises(ValueError,match="timezone-aware"):
        build_interpretation_request(store,primary.revision_id,FIXTURE_TIME.replace(tzinfo=None))


def test_strict_research_separation_and_actual_late_availability(tmp_path):
    store,primary=populated(tmp_path)
    tomorrow=FIXTURE_TIME+timedelta(days=1)
    late=synthetic_record("late",primary.headline,"",available_at=tomorrow)
    late=late.model_copy(update={"historical_proxy_at":FIXTURE_TIME,"historical_proxy_source":AvailableAtSource.PUBLISHED_AT_PROXY})
    store.write_records([late])
    with pytest.raises(ValueError):
        build_interpretation_request(store,late.revision_id,FIXTURE_TIME)
    with pytest.raises(ValueError):
        build_interpretation_request(store,late.revision_id,FIXTURE_TIME,allow_historical_proxy=True)
    research=build_interpretation_request(store,late.revision_id,FIXTURE_TIME,
        mode=NewsQueryMode.HISTORICAL_RESEARCH,allow_historical_proxy=True)
    assert research.inputs_available_at == tomorrow
    resp=LLMResponse(provider="simulated",model="news-fixture-v1",content=json.dumps(dict(status="abstained",abstention_reasons=["generic_headline"])),generated_at=tomorrow)
    result=replay_response(research,resp,CONFIG,validated_at=tomorrow,execution_mode="retrospective_reconstruction")
    assert not result.operationally_eligible_at(FIXTURE_TIME) and result.available_at == tomorrow
    assert result.query_mode == NewsQueryMode.HISTORICAL_RESEARCH and result.allow_historical_proxy
    with pytest.raises(ValueError,match="generation predates"):
        replay_response(research,resp.model_copy(update={"generated_at":FIXTURE_TIME}),CONFIG,validated_at=tomorrow)
    strict=build_interpretation_request(store,late.revision_id,tomorrow)
    assert strict.request_id != research.request_id


def test_cluster_context_is_optional_and_cannot_be_future_computation(tmp_path):
    store,primary=populated(tmp_path)
    original=store.normalized_path.read_bytes()
    future=build_news_groups_as_of(store,FIXTURE_TIME,fixture_registry(),
        reconstruction_policy="deterministic_reconstruction_v1",computed_at=FIXTURE_TIME+timedelta(days=1))
    assert build_interpretation_request(store,primary.revision_id,FIXTURE_TIME).snapshot is None
    with pytest.raises(ValueError,match="computed cluster context"):
        build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,snapshot=future)
    observed=build_news_groups_as_of(store,FIXTURE_TIME,fixture_registry(),
        reconstruction_policy="deterministic_reconstruction_v1",computed_at=FIXTURE_TIME)
    req=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,snapshot=observed)
    assert req.snapshot.snapshot_id == observed.snapshot_id
    assert req.snapshot.cluster_ids and req.evidence[0].text == primary.headline
    assert store.normalized_path.read_bytes() == original


def test_context_latest_revision_future_and_target_scope(tmp_path):
    store,primary=populated(tmp_path)
    ctx=synthetic_record("ctx","Harbor partnership details.","",available_at=FIXTURE_TIME+timedelta(days=1))
    store.write_records([ctx])
    with pytest.raises(ValueError):
        build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,context_revision_ids=(ctx.revision_id,))
    with pytest.raises(ValueError,match="target entity"):
        build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,target=InterpretationTarget(entity_id="future"))
    req=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME,target=InterpretationTarget(ticker="AAPL"))
    assert req.target.ticker == "AAPL" and "Apple" not in req.evidence[0].text


def test_existing_router_contract_compatibility_with_only_simulated_client(monkeypatch,tmp_path):
    def blocked(*args,**kwargs):
        raise AssertionError("real network is forbidden")
    monkeypatch.setattr("httpx.Client.send",blocked)
    store,primary=populated(tmp_path)
    req=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME)
    class SimulatedClient(BaseLLMClient):
        provider="simulated"
        def complete(self,request,model):
            assert request.task == "news_interpretation"
            return LLMResponse(provider=self.provider,model=model,generated_at=FIXTURE_TIME,
                content=json.dumps(dict(status="abstained",abstention_reasons=["insufficient_evidence"])))
    router=LLMRouter({"simulated":SimulatedClient()},{"news_interpretation":{"provider":"simulated","model":"news-fixture-v1"}})
    routed=router.complete(prepare_llm_request(req,CONFIG))
    result=replay_response(req,routed,CONFIG,validated_at=FIXTURE_TIME)
    assert result.status == "abstained"
    assert not result.provenance.tokens_reported and not result.provenance.latency_reported
    assert ReplayEnvelope.model_validate_json(ReplayEnvelope(request=req,result=result).model_dump_json()).result == result
    assert not result.operationally_eligible_at(FIXTURE_TIME)


def test_replay_provider_mismatch_and_time_provenance_rejected(tmp_path):
    store,primary=populated(tmp_path)
    req=build_interpretation_request(store,primary.revision_id,FIXTURE_TIME)
    resp=LLMResponse(provider="other",model="news-fixture-v1",generated_at=FIXTURE_TIME,
        content=json.dumps(dict(status="abstained",abstention_reasons=["insufficient_evidence"])))
    with pytest.raises(ValueError,match="provider/model"):
        replay_response(req,resp,CONFIG,validated_at=FIXTURE_TIME)
    with pytest.raises(ValueError,match="validation cannot predate"):
        replay_response(req,resp.model_copy(update={"provider":"simulated"}),CONFIG,validated_at=FIXTURE_TIME-timedelta(seconds=1))
