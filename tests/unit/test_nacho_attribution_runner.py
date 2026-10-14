"""New runner tests: simulated transport only, never real evaluation outputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.service import NewsInterpretationService, prepare_invocation
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter
from investment_system.llm.schemas import LLMResponse
from investment_system.llm.openai_settings import LLMProviderError


REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("nacho_runner_test", REPO / "tools/evaluation/nacho_attribution_runner.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
NOW = datetime(2026, 10, 14, 21, tzinfo=timezone.utc)


@pytest.fixture
def repo(tmp_path):
    if not (REPO / r.FREEZE_PATH).exists():
        pytest.skip('private frozen evaluation artifact not present')
    for name in ["evaluation/phase4c2_chatgpt_review_v1", "evaluation/phase4c2_attribution_v1/prepared/reviewer"]:
        shutil.copytree(REPO / name, tmp_path / name)
    for name in [r.FREEZE_PATH, "config/news_interpretation.evaluation.yaml"]:
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(REPO / name, path)
    return tmp_path


def plan(repo, budget=1.60, now=NOW):
    return r.preflight(repo, repo / "config/news_interpretation.evaluation.yaml", budget, now=now)


def authorization(p):
    return dict(version="nacho-evaluation-authorization-v1", approved=True, authorized_by="synthetic-owner",
        authorized_at=(NOW-timedelta(minutes=5)).isoformat(), expires_at=(NOW+timedelta(hours=1)).isoformat(),
        plan_fingerprint=p["plan_fingerprint"], freeze_sha256=r.FREEZE_SHA256,
        run_id="test-only", max_provider_calls=32, budget_usd=p["run_budget_usd"])


def test_preflight_is_pure_and_reproducible(repo, monkeypatch):
    from investment_system.llm.openai_client import OpenAIClient
    from investment_system.core import environment
    def forbidden(*args, **kwargs): raise AssertionError("offline_boundary_violation")
    monkeypatch.setattr(OpenAIClient, "complete", forbidden)
    monkeypatch.setattr(environment, "load_dotenv", forbidden)
    before = {p.relative_to(repo):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
    a,s,requests = plan(repo); b,_,_ = plan(repo)
    assert a==b and len(requests)==32 and a['case_count']==32
    assert a['maximum_reserved_usd'] < 1.60
    assert a['output_token_cap_total']==32*2048
    assert s.model_output_version=='news-economic-selection-v3'
    assert before=={p.relative_to(repo):p.read_bytes() for p in repo.rglob('*') if p.is_file()}


def test_original_text_and_pit_registry_are_preserved(repo):
    evidence,identity,_=r.verified_sources(repo)
    pairs=r.build_requests(evidence,identity)
    for original,(binding,req) in zip(evidence['cases'],pairs):
        assert binding['evidence_fingerprint']==original['evidence_fingerprint']
        assert req.news.headline==original['evidence'][0]['text']
        assert req.news.summary==original['evidence'][1]['text']
        assert req.news.published_at is None and req.news.event_date is None
        assert req.news.direct_tickers==() and req.target is None and req.snapshot is None
        assert req.decision_time.isoformat()=='2026-10-13T00:05:00+00:00'
        assert all(e.known_at<=req.decision_time and not e.aliases for e in req.registry_entries)
        assert not any(e.corporate_name=='Quillan' for e in req.registry_entries)
        ambiguous=[e for e in req.registry_entries if e.corporate_name=='Seabright']
        assert len(ambiguous)==2 and ambiguous[0].entity_id==ambiguous[1].entity_id


def test_no_reference_annotations_enter_wire(repo):
    p,s,pairs=plan(repo)
    for binding,req in pairs:
        llm,wire,_=prepare_invocation(req,s)
        text=json.dumps(wire)
        assert 'raw_response_utf8' not in text and 'reference_fingerprint' not in text
        assert 'chatgpt_assisted_exploratory_review' not in text and 'unit_id' not in text
        assert r.FREEZE_SHA256 not in text and p['plan_fingerprint'] not in text
        assert wire['tools']==[] and wire['store'] is False
        assert wire['text']['format']['strict'] is True


@pytest.mark.parametrize('path',[r.FREEZE_PATH,
    'evaluation/phase4c2_attribution_v1/prepared/reviewer/blind_synthetic_evidence.json',
    'evaluation/phase4c2_attribution_v1/prepared/reviewer/identity_lookup.synthetic.json'])
def test_changed_inputs_fail_closed(repo,path):
    with (repo/path).open('ab') as f: f.write(b' ')
    with pytest.raises(ValueError): plan(repo)


@pytest.mark.parametrize('budget',[0,-1,float('nan'),float('inf'),1.61,0.01])
def test_budget_cannot_expand_or_omit_output(repo,budget):
    with pytest.raises(ValueError): plan(repo,budget)


def test_expired_prices_block_offline(repo):
    with pytest.raises(ValueError): plan(repo,now=NOW+timedelta(days=2))


@pytest.mark.parametrize('change',[{'approved':False},{'max_provider_calls':33},
    {'plan_fingerprint':'0'*64},{'freeze_sha256':'0'*64},{'budget_usd':2},
    {'expires_at':NOW.isoformat()},{'authorized_at':(NOW+timedelta(hours=1)).isoformat()},
    {'run_id':'other'},{'authorized_by':''}])
def test_explicit_authorization_cannot_be_reused_or_expanded(repo,change):
    p,_,_=plan(repo); auth=authorization(p); auth.update(change)
    with pytest.raises(ValueError): r.validate_authorization(auth,p,'test-only',NOW)


def test_authorization_accepts_only_bound_owner_declaration(repo):
    p,_,_=plan(repo); r.validate_authorization(authorization(p),p,'test-only',NOW)


def test_annotation_fields_are_rejected_by_adapter(repo):
    evidence,identity,_=r.verified_sources(repo); evidence['cases'][0]['units']=[]
    with pytest.raises(ValueError,match='annotation_fields_forbidden'): r.build_requests(evidence,identity)


class FakeClient(BaseLLMClient):
    provider='openai'
    def __init__(self,settings): self.settings=settings; self.calls=0
    def complete(self,request,model):
        self.calls+=1
        if self.calls==4: raise LLMProviderError('timeout',retryable=True)
        if self.calls==3: text='invalid-json'
        elif self.calls==2:
            text=json.dumps(dict(schema_version='news-economic-selection-v3',status='abstained',
                abstention_reasons=['insufficient_evidence']))
        else:
            envelope=json.loads(request.prompt[request.prompt.index('{'):]); ev=envelope['evidence'][0]
            q=dict(evidence_id=ev['evidence_id'],quote=ev['text'])
            text=json.dumps(dict(schema_version='news-economic-selection-v3',status='interpreted',events=[dict(
                event_key='simulated',event_type='other',other_type='observation',description='Synthetic observation',
                state='confirmed',stage='unknown',state_evidence=q,evidence=[q],entities=[dict(
                    name=ev['text'].split()[0],mention_kind='company',evidence=q,attribution='contextual_mention')])]))
        return LLMResponse(provider='openai',model=model,content=text,generated_at=NOW,
            input_tokens=100,cached_input_tokens=0,output_tokens=50,
            raw={'usage_reported':True,'cache_write_tokens':100,'effective_parameters':self.settings.adapter.effective_parameters})


def test_simulated_outputs_failures_abstention_and_unknown_cost(repo):
    p,s,pairs=plan(repo); fake=FakeClient(s)
    root=repo/'simulated-only'; storage=LocalInterpretationStore(root/'runtime',allowed_root=root)
    router=LLMRouter({'openai':fake},{'news_interpretation':{'provider':'openai','model':s.adapter.model}})
    service=NewsInterpretationService(router,s,storage,'test-only',execution_authorized=True,simulated=True,clock=lambda:NOW)
    export=r.execute_cases(pairs,service,root,p)
    assert fake.calls==4 and len(export['cases'])==32
    assert [c['outcome'] for c in export['cases'][:4]]==['interpreted','abstained','invalid_response','transport_error']
    assert export['cases'][1]['abstention_reasons']==['insufficient_evidence']
    assert set(export['cases'][0]['units'][0]['dimensions'])==set(r.review_module().DIMENSIONS)
    assert export['cases'][0]['units'][0]['confirmed_exposure'] is False
    assert export['cases'][0]['units'][0]['dimensions']['ticker_link'] is None
    assert all(c['outcome']=='not_run' for c in export['cases'][4:])
    assert export['unknown_cost_attempts']==1 and export['accounted_usd']>0
    for row in export['cases'][:4]:
        record=storage.read(row['record_id'],now=NOW)
        assert record.dataset_role=='offline_simulated_development'
        assert row['output_fingerprint']==record.record_id
        assert r.utc(row['attempt_started_at'])>r.utc(p['frozen_at'])


def test_cli_offline_and_unauthorized_modes_never_bootstrap(repo,monkeypatch,capsys):
    from scripts import run_phase4c2_attribution_evaluation as cli
    def forbidden(*args,**kwargs): raise AssertionError('must_not_bootstrap')
    monkeypatch.setattr(cli,'load_repository_environment',forbidden)
    real=cli.preflight
    monkeypatch.setattr(cli,'preflight',lambda _repo,config,budget:real(repo,config,budget,now=NOW))
    args=['runner','--config',str(repo/'config/news_interpretation.evaluation.yaml')]
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-not-a-key')
    for tail,result in [([],2),(['--validate-only'],0),(['--confirm-real-inference'],2),
                        (['--validate-only','--confirm-real-inference'],2)]:
        monkeypatch.setattr(sys,'argv',args+tail)
        assert cli.main()==result
        captured=capsys.readouterr().out
        assert 'synthetic-not-a-key' not in captured


def test_fake_failure_is_sanitized_and_records_remaining_cases(repo):
    p,s,pairs=plan(repo)
    class FailedService:
        class Budget:
            def accounted(self): return 0
        class Tracker:
            def unknown_cost_count(self): return 0
        budget=Budget(); tracker=Tracker()
        def interpret(self,*args,**kwargs): raise RuntimeError('SECRET_FIXTURE_VALUE')
    export=r.execute_cases(pairs,FailedService(),repo/'failure-only',p)
    assert len(export['cases'])==32 and 'SECRET_FIXTURE_VALUE' not in json.dumps(export)
    assert export['cases'][0]['attempt_may_have_occurred'] is True


def test_comparator_accepts_native_export_without_real_comparison(tmp_path):
    """All reference/system values below are newly fabricated test fixtures."""
    t=r.review_module(); cases=[]; system_cases=[]
    for i in range(32):
        dims={n:dict(status='conclusive',value='test-only',rationale='fixture',evidence=[]) for n in t.DIMENSIONS}
        cases.append(dict(case_id=f'test-{i}',status='annotated',units=[dict(unit_id='R1',dimensions=dims)]))
        system_cases.append(dict(case_id=f'test-{i}',outcome='interpreted',attempt_started_at=NOW.isoformat(),
            record_id='synthetic-record',output_fingerprint='synthetic-output',units=[dict(unit_id='S1',dimensions={n:'test-only' for n in t.DIMENSIONS})]))
    refs=dict(cases=cases)
    seal=dict(review_kind=t.ROLE,independent_human_ground_truth=False,references=refs,
        reference_fingerprint=t.fp(refs),frozen_at=(NOW-timedelta(minutes=1)).isoformat())
    t.write_json(tmp_path/'references.json',seal); t.write_json(tmp_path/'system.json',dict(cases=system_cases))
    t.write_json(tmp_path/'alignment.json',dict(reference_freeze_sha256=t.sha(tmp_path/'references.json'),
        system_file_sha256=t.sha(tmp_path/'system.json'),matches=[dict(case_id=f'test-{i}',reference_unit_id='R1',system_unit_id='S1') for i in range(32)]))
    report=t.compare(tmp_path/'references.json',tmp_path/'system.json',tmp_path/'alignment.json')
    assert report['population_metrics']=='not_estimated'
    assert all(d['agreement']==32 for d in report['dimensions'].values())


def test_paid_branch_with_unapproved_record_never_loads_credentials(repo,monkeypatch,capsys):
    from scripts import run_phase4c2_attribution_evaluation as cli
    p,_,_=plan(repo); auth=authorization(p); auth['approved']=False
    path=repo/'unapproved.json'; path.write_text(json.dumps(auth),encoding='utf-8')
    def forbidden(*args,**kwargs): raise AssertionError('must_not_bootstrap')
    monkeypatch.setattr(cli,'load_repository_environment',forbidden)
    monkeypatch.setattr(cli,'preflight',lambda *_:plan(repo))
    monkeypatch.setattr(sys,'argv',['runner','--config',str(repo/'config/news_interpretation.evaluation.yaml'),
        '--confirm-real-inference','--run-id','test-only','--authorization',str(path)])
    assert cli.main()==2
    assert json.loads(capsys.readouterr().out)['status']=='blocked'


def test_exactly_32_simulated_attempts_with_known_cost_and_shared_budget(repo):
    p,s,pairs=plan(repo)
    class AlwaysAbstain(BaseLLMClient):
        provider='openai'
        calls=0
        def complete(self,request,model):
            self.calls+=1
            return LLMResponse(provider='openai',model=model,generated_at=NOW,
                content=json.dumps(dict(schema_version='news-economic-selection-v3',status='abstained',
                    abstention_reasons=['insufficient_evidence'])),input_tokens=100,cached_input_tokens=0,output_tokens=50,
                raw={'usage_reported':True,'cache_write_tokens':100})
    fake=AlwaysAbstain(); root=repo/'all-32-simulated-only'
    storage=LocalInterpretationStore(root/'runtime',allowed_root=root)
    router=LLMRouter({'openai':fake},{'news_interpretation':{'provider':'openai','model':s.adapter.model}})
    service=NewsInterpretationService(router,s,storage,'all-32-test',execution_authorized=True,simulated=True,clock=lambda:NOW)
    export=r.execute_cases(pairs,service,root,p)
    assert fake.calls==32 and len(list((root/'runtime/attempts').glob('*.json')))==32
    assert all(c['outcome']=='abstained' and c['additional_attempts']==1 for c in export['cases'])
    assert len({c['case_id'] for c in export['cases']})==32
    assert export['unknown_cost_attempts']==0 and export['accounted_usd']<p['maximum_reserved_usd']
