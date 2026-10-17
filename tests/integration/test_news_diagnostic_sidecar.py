"""P0 witnesses only: synthetic responses, fresh temporary stores, no historical content."""
from datetime import timedelta
from copy import deepcopy
import json
import sys

import pytest

from test_economic_entity_attribution import settings, request, payload, quote
from test_news_quote_grounding import NOW, response, CONFIG
from investment_system.agents.news_interpretation.diagnostic_events import BranchDiagnostic, capture_validation
from investment_system.agents.news_interpretation.diagnostic_sidecar import (
    DiagnosticSidecar, SidecarStore, interpret_observed, record_not_run, RETENTION_DAYS,
)
from investment_system.agents.news_interpretation.economic_attribution import evaluate_economic_response, EconomicSelectionPayload
from investment_system.agents.news_interpretation.schemas import InterpretationPayload
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.service import NewsInterpretationService
from investment_system.data.news_entities import fingerprint
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter
from investment_system.llm.openai_settings import LLMProviderError


RUN = 'eval-'+'1'*32
CASE = 'S-'+'2'*16
SECRET = 'SENSITIVE_FIXTURE_π_NEVER_PERSIST'


def evaluate(req,data):
    with capture_validation() as capture:
        result=evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)
    return result,capture


@pytest.mark.parametrize('stage,subcode',[('completed','completion_literal_missing'),
    ('announced','announced_literal_missing'),('proposed','proposed_literal_missing')])
def test_stage_branches_do_not_change_legacy_result(stage,subcode):
    req=request(); data=payload(req,entities=[]); data['events'][0]['stage']=stage
    plain=evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)
    observed,capture=evaluate(req,data)
    assert plain==observed and plain[1].status=='invalid_response'
    assert len(capture.details)==1
    detail=capture.details[0]
    assert detail.subcode==subcode and detail.field_path==('events',0,'state_evidence')
    assert detail.rule=='stage_not_supported' and detail.stage=='semantic_validation'
    # Historical coarse diagnostic path stays byte/canonical equivalent.
    assert observed[1].diagnostics[0].field_path==('events','state_evidence')


@pytest.mark.parametrize('value,value_text,changes,subcode',[
    (1,'one',{},'number_lexeme_unparseable'),(2,'1',{},'number_value_nonfinite_or_transformed'),
    (2,'2',{},'number_absent_from_context'),(1,'1',{'unit':SECRET},'unit_absent_from_context'),
    (1,'1',{'scale':'million'},'scale_absent_from_context'),(1,'1',{'period':SECRET},'period_absent_from_context')])
def test_six_numeric_branches_are_observed_without_values(value,value_text,changes,subcode):
    req=request('Birch acquired Pine for 1 USD.'); data=payload(req,entities=[])
    data['events'][0]['numbers']=[dict(metric='amount',value=value,value_text=value_text,unit=None,context=quote(req),**{
        k:v for k,v in changes.items() if k!='unit'}) | ({'unit':changes['unit']} if 'unit' in changes else {})]
    plain=evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)
    observed,capture=evaluate(req,data)
    assert observed==plain and observed[1].status=='invalid_response'
    assert len(capture.details)==1 and capture.details[0].subcode==subcode
    assert capture.details[0].field_path==('events',0,'numbers',0)
    assert SECRET not in json.dumps([d.model_dump() for d in capture.details])


def test_negation_condition_is_recorded_not_repaired():
    req=request('Birch has not acquired Pine.'); data=payload(req,entities=[])
    observed,capture=evaluate(req,data)
    assert observed[1].status=='invalid_response'
    assert capture.details[0].subcode=='negation_token_present_flag_false'
    assert capture.details[0].field_path==('events',0,'negated')


def test_unknown_evidence_id_does_not_leak_identifier_or_quote():
    req=request(); data=payload(req,entities=[])
    data['events'][0]['state_evidence']={'evidence_id':'f'*64,'quote':SECRET}
    result,capture=evaluate(req,data)
    detail=capture.details[0]
    assert detail.rule=='unknown_evidence_id' and detail.subcode=='evidence_id_not_in_request'
    assert detail.field_path==('events',0,'state_evidence')
    assert SECRET not in detail.model_dump_json() and 'f'*64 not in detail.model_dump_json()


class FakeClient(BaseLLMClient):
    provider='openai'
    def __init__(self,data):self.data=data;self.calls=0
    def complete(self,request,model):
        self.calls+=1
        if self.data is None:raise LLMProviderError('timeout')
        value=response(self.data)
        value.raw.update(usage_reported=True,cache_write_tokens=0)
        return value


def setup(tmp_path,data,*,run=RUN,authorized=True):
    fake=FakeClient(data); cfg=settings()
    router=LLMRouter({'openai':fake},{'news_interpretation':{'provider':'openai','model':cfg.adapter.model}})
    content=LocalInterpretationStore(tmp_path/'content',allowed_root=tmp_path)
    service=NewsInterpretationService(router,cfg,content,run,execution_authorized=authorized,simulated=True,clock=lambda:NOW)
    sidecars=SidecarStore(tmp_path/'diagnostics',allowed_root=tmp_path)
    return fake,service,sidecars


def observe(service,req,store):
    source=fingerprint({'headline':req.news.headline,'summary':req.news.summary or ''})
    return interpret_observed(service,req,case_id=CASE,source_evidence_fingerprint=source,store=store)


def test_persist_rejection_then_audit_after_content_ttl_without_content_reader(tmp_path,monkeypatch):
    req=request(); data=payload(req,entities=[]);data['events'][0]['stage']='completed'
    fake,service,store=setup(tmp_path,data)
    delivery,identity=observe(service,req,store)
    assert fake.calls==1 and delivery.record.outcome=='invalid_response'
    sidecar=store.read(RUN,CASE,now=NOW+timedelta(days=2),expected_id=identity)
    assert sidecar.record_id==delivery.record_id and sidecar.validation_observed
    assert sidecar.diagnostics[0].subcode=='completion_literal_missing'
    with pytest.raises(ValueError,match='retention expired'):
        service.storage.read(delivery.record_id,now=NOW+timedelta(days=2))
    def forbidden(*args,**kwargs):raise AssertionError('no content lookup allowed')
    monkeypatch.setattr(LocalInterpretationStore,'read',forbidden)
    assert store.read(RUN,CASE,now=NOW+timedelta(days=89)).sidecar_id==identity
    assert sidecar.expires_at-sidecar.created_at==timedelta(days=RETENTION_DAYS)
    with pytest.raises(ValueError,match='retention_expired'):
        store.read(RUN,CASE,now=sidecar.expires_at)
    with pytest.raises(ValueError):store.read(RUN,CASE,now=NOW-timedelta(seconds=1))


@pytest.mark.parametrize('kind',['interpreted','abstained','transport'])
def test_success_abstention_and_transport_have_bound_outcomes(tmp_path,kind):
    req=request(); data=payload(req,entities=[])
    if kind=='abstained':data=dict(schema_version='news-economic-selection-v3',status='abstained',abstention_reasons=['insufficient_evidence'])
    if kind=='transport':data=None
    fake,service,store=setup(tmp_path,data)
    delivery,identity=observe(service,req,store)
    item=store.read(RUN,CASE,now=NOW,expected_id=identity)
    assert item.outcome==('technical_error' if kind=='transport' else kind)
    assert item.validation_observed==(kind!='transport')
    assert item.record_id==delivery.record_id and fake.calls==1


def test_untrusted_extra_field_name_does_not_enter_sidecar(tmp_path):
    req=request(); data=payload(req,entities=[]);data[SECRET]=SECRET
    _,service,store=setup(tmp_path,data)
    _,identity=observe(service,req,store)
    sidecar=store.read(RUN,CASE,now=NOW)
    assert SECRET not in sidecar.model_dump_json()
    assert sidecar.diagnostics[0].field_path==('unknown_field',)


@pytest.mark.parametrize('path',[('events',SECRET),('events',True),('events',-1),('events',100000)])
def test_adversarial_paths_are_rejected(path):
    with pytest.raises(ValueError):BranchDiagnostic(stage='json',rule='invalid_json',field_path=path)


def test_integrity_immutability_and_no_sensitive_fields(tmp_path):
    req=request();data=payload(req,entities=[]);data['events'][0]['stage']='completed'
    _,service,store=setup(tmp_path,data);_,identity=observe(service,req,store)
    item=store.read(RUN,CASE,now=NOW);path=store._path(RUN,CASE);raw=path.read_bytes();mtime=path.stat().st_mtime_ns
    assert store.write(item,now=NOW)==identity and path.stat().st_mtime_ns==mtime
    with pytest.raises(ValueError):store.write(item.model_copy(update={'record_id':'8'*64}),now=NOW)
    value=json.loads(raw);value['metadata']['record_id']='9'*64;path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError):store.read(RUN,CASE,now=NOW)
    value['sidecar_id']=fingerprint(value['metadata']);path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError):store.read(RUN,CASE,now=NOW,expected_id=identity)
    value['metadata'][SECRET]=SECRET
    with pytest.raises(ValueError) as error:DiagnosticSidecar.model_validate_json(json.dumps(value['metadata']))
    assert SECRET not in str(error.value)


def test_sidecar_failure_does_not_retry_or_change_attempt_outcome(tmp_path,monkeypatch):
    req=request();data=payload(req,entities=[]);_,service,store=setup(tmp_path,data)
    def failure(*args,**kwargs):raise OSError('fixed test write failure')
    monkeypatch.setattr(store,'write',failure)
    with pytest.raises(OSError):observe(service,req,store)
    assert service.router.clients['openai'].calls==1
    paths=list((service.storage.root/'attempts').glob('*.json'));assert len(paths)==1
    assert service.storage.read(paths[0].stem,now=NOW).outcome=='interpreted'


def test_historical_run_id_is_blocked_before_service_invocation(tmp_path):
    req=request();fake,service,store=setup(tmp_path,payload(req),run='nacho-synthetic-20261014-run01')
    with pytest.raises(ValueError):observe(service,req,store)
    assert fake.calls==0 and not store.root.exists()


def test_not_authorized_does_not_call_or_invent_attempt(tmp_path):
    req=request();fake,service,store=setup(tmp_path,payload(req),authorized=False)
    with pytest.raises(ValueError,match='no_new_attempt'):observe(service,req,store)
    assert fake.calls==0
    identity=record_not_run(req,service.settings,run_id=RUN,case_id=CASE,
        source_evidence_fingerprint=fingerprint({'headline':req.news.headline,'summary':req.news.summary or ''}),
        reason='not_authorized',store=store)
    item=store.read(RUN,CASE,expected_id=identity)
    assert item.outcome=='not_run' and item.record_id is None and item.lifecycle_code=='not_authorized'


def test_schema_and_wire_contracts_are_not_versioned_or_modified():
    assert fingerprint(EconomicSelectionPayload.model_json_schema())=='928e28c7a9572c983065026832d715d3080f77ee947743137c6c571bf017055d'
    assert fingerprint(InterpretationPayload.model_json_schema())=='9855dbcf2a321a1cc863d9aa444750df38c80c6e1d03b6c284243c5e2992b1b6'


def test_capture_isolation_and_non_retroactive_generation():
    req=request();data=payload(req,entities=[]);data['events'][0]['stage']='completed'
    _,a=evaluate(req,data)
    assert len(a.details)==1
    with capture_validation() as b:
        assert not b.details
        evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)
        evaluate_economic_response(req,response(data),CONFIG,validated_at=NOW)
    assert len(b.details)==1 and b.sealed


def test_offline_preflight_has_no_credential_or_provider_access(monkeypatch,capsys):
    from scripts import validate_news_diagnostic_sidecar as cli
    from investment_system.core import environment
    from investment_system.llm.openai_client import OpenAIClient
    def forbidden(*args,**kwargs):raise AssertionError('offline boundary')
    monkeypatch.setattr(environment,'load_dotenv',forbidden)
    monkeypatch.setattr(OpenAIClient,'complete',forbidden)
    monkeypatch.setattr(sys,'argv',['preflight','--validate-only'])
    assert cli.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['provider_calls']==result['persistence_writes']==result['credential_loads']==0


def test_retention_cannot_be_extended_by_rehashing(tmp_path):
    req=request();data=payload(req,entities=[]);_,service,store=setup(tmp_path,data)
    observe(service,req,store);value=store.read(RUN,CASE,now=NOW)
    with pytest.raises(ValueError,match='invalid_diagnostic_retention'):
        store.write(value.model_copy(update={'expires_at':value.expires_at+timedelta(days=1)}),now=NOW)


def test_source_binding_is_checked_before_any_provider_call(tmp_path):
    req=request();fake,service,store=setup(tmp_path,payload(req))
    with pytest.raises(ValueError,match='source_binding'):
        interpret_observed(service,req,case_id=CASE,source_evidence_fingerprint='0'*64,store=store)
    assert fake.calls==0 and not store.root.exists()


def test_new_sidecar_requires_specific_codes_not_retrospective_coarse_diagnostics(tmp_path):
    req=request();data=payload(req,entities=[]);data['events'][0]['stage']='completed'
    _,service,store=setup(tmp_path,data);observe(service,req,store)
    item=store.read(RUN,CASE,now=NOW)
    coarse=BranchDiagnostic(stage='semantic_validation',rule='stage_not_supported',field_path=('events',0,'state_evidence'))
    with pytest.raises(ValueError,match='specific_branch'):
        store.write(item.model_copy(update={'diagnostics':(coarse,)}),now=NOW)


def test_sidecar_rejects_duplicate_json_fields_and_unknown_codes(tmp_path):
    req=request();data=payload(req,entities=[]);_,service,store=setup(tmp_path,data)
    observe(service,req,store);path=store._path(RUN,CASE)
    raw=path.read_text(encoding='utf-8');path.write_text(raw.replace('{','{"sidecar_id":"0",',1),encoding='utf-8')
    with pytest.raises(ValueError):store.read(RUN,CASE,now=NOW)
    with pytest.raises(ValueError):BranchDiagnostic(stage='json',rule=SECRET)
    with pytest.raises(ValueError):BranchDiagnostic(stage=SECRET,rule='invalid_json')


def test_same_prepared_wire_and_cache_key_with_observation_enabled():
    from investment_system.agents.news_interpretation.service import prepare_invocation
    req=request();cfg=settings();first=prepare_invocation(req,cfg)
    with capture_validation():second=prepare_invocation(req,cfg)
    assert first==second
