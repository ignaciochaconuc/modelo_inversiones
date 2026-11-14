"""Preparatory-record regression tests: fictional identities and clocks only in tmp_path."""
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from pydantic import ValidationError
import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p = load("prospective_preparation_tests", ROOT/"tools/evaluation/prospective_timing_preparation.py")
fx = load("preparation_clock_fixtures", ROOT/"tests/unit/test_prospective_timing_pilot.py")


@pytest.fixture
def sample(tmp_path):
    repo,plan,folder,historical=fx.sample.__wrapped__(tmp_path)
    # The executable-clock fixture uses toy packet IDs; preparations require SHA-256.
    corpus=fx.t.read_ref(repo,plan.corpus)
    candidates=[]
    for candidate in plan.candidates:
        sha=hashlib.sha256(candidate.packet_fingerprint.encode()).hexdigest()
        candidates.append(candidate.model_copy(update={'packet_fingerprint':sha}))
        next(x for x in corpus['cases'] if x['case_id']==candidate.case_id)['packet_fingerprint']=sha
    (repo/plan.corpus.path).write_bytes(fx.t.encoded(corpus))
    corpus_ref=fx.t.ref_for(repo,repo/plan.corpus.path)
    manifest=fx.t.read_ref(repo,plan.source_manifest)
    manifest['sha256'][corpus_ref.path]=corpus_ref.sha256
    (repo/plan.source_manifest.path).write_bytes(fx.t.encoded(manifest))
    plan=plan.model_copy(update={'candidates':tuple(candidates),'corpus':corpus_ref,
                               'source_manifest':fx.t.ref_for(repo,repo/plan.source_manifest.path)})
    (repo/'inputs/plan.json').write_bytes(fx.t.encoded(plan.model_dump(mode='json')))
    return repo,fx.t.load_plan(repo,repo/'inputs/plan.json'),folder,historical


def declaration(sample):
    _, plan, _, _ = sample
    slot = plan.sessions[0]
    candidate = next(c for c in plan.candidates if c.case_id == slot.case_id)
    return dict(version=p.VERSION, status="preparation_only", scope="preparation_and_preflight_only",
        start_authorized=False, eligibility_granted=False, plan_fingerprint=p.clock.fingerprint(plan),
        case_id=slot.case_id,session_id=slot.session_id,packet_fingerprint=candidate.packet_fingerprint,
        responsible_reference="Project owner, current conversation participant",reviewer_id=None,
        familiarity_statement="SYNTHETIC TEST: owner does not remember seeing source or variants.",
        familiarity_status="unknown",first_reading="unknown",variant_exposure="unknown",
        assistance="manual_chatgpt_owner",declaration_source="Synthetic test, no real authorization.",
        declared_at=None,source_message_id=None,independent_human_review=False,adjudication_claimed=False,
        pending_fields=["reviewer_id","familiarity_confirmed","first_reading","unseen_counterfactual","execution_authorization"])


def inventory(repo):
    return {x.relative_to(repo).as_posix():p.clock.digest(x) for x in repo.rglob('*') if x.is_file()}


def test_unknowns_valid_and_validation_readonly_without_eligibility(sample):
    repo,plan,folder,historical=sample
    record=p.Preparation.model_validate(declaration(sample));before=inventory(repo)
    result=p.validate_preparation(repo,plan,record,now=fx.AT)
    assert result['preparation_valid'] and not result['start_authorized'] and not result['eligibility_granted']
    assert result['first_reading']==result['familiarity_status']==result['variant_exposure']=='unknown'
    assert record.reviewer_id is None and record.declared_at is None and record.source_message_id is None
    assert set(result['preflight']['case_sessions'].values())=={'unfilled'}
    assert result['preflight']['administration_state']=='unfilled'
    assert result['preflight']['eligible_records']==0
    assert result['semantic_truth']=='not_assessed' and not result['integral_pilot_completed']
    assert not result['factual_timing_rehabilitated']
    assert inventory(repo)==before and not folder.exists()
    assert p.clock.digest(repo/historical.path)==historical.sha256


@pytest.mark.parametrize('field,value',[
    ('start_authorized',True),('start_authorized',0),('eligibility_granted',True),
    ('status','execution_authorized'),('scope','execution'),('first_reading',True),
    ('variant_exposure',True),('independent_human_review',True),('adjudication_claimed',True),
    ('pending_fields',[]),('reviewer_id',''),('familiarity_statement',''),
])
def test_unsafe_or_incomplete_preparation_rejected(sample,field,value):
    raw=declaration(sample);raw[field]=value
    with pytest.raises(ValueError):p.Preparation.model_validate(raw)


@pytest.mark.parametrize('field,value',[
    ('case_id','HISTORICAL-CASE'),('session_id','pt-not-a-reservation'),
    ('packet_fingerprint','a'*64),('plan_fingerprint','b'*64),
])
def test_stale_or_wrong_binding_rejected(sample,field,value):
    repo,plan,folder,_=sample;raw=declaration(sample);raw[field]=value
    before=inventory(repo)
    with pytest.raises(ValueError):p.validate_preparation(repo,plan,p.Preparation.model_validate(raw),now=fx.AT)
    assert inventory(repo)==before and not folder.exists()


def test_contractual_slot_cannot_be_mislabelled_factual_preparation(sample):
    repo,plan,_,_=sample;raw=declaration(sample);raw['session_id']=plan.sessions[1].session_id
    with pytest.raises(ValueError,match='preparation_session_mismatch'):
        p.validate_preparation(repo,plan,p.Preparation.model_validate(raw),now=fx.AT)


@pytest.mark.parametrize('path_name',[
    'preparations/fixture.json','authorizations/copied.json','renamed-authorization.json',
])
def test_original_clock_start_rejects_preparation_regardless_of_path(sample,path_name):
    repo,plan,folder,_=sample;raw=declaration(sample)
    ref=fx.write(repo,'inputs/'+path_name,raw);before=inventory(repo)
    with pytest.raises(ValidationError) as error:
        fx.t.record(repo,plan,folder,raw['session_id'],'start',now=fx.AT,
                    auth_path=repo/ref.path,phase='factual_reading',confirm_start=True)
    assert any(e['loc']==('version',) and e['type']=='literal_error' for e in error.value.errors())
    assert inventory(repo)==before and not folder.exists()


def test_simple_version_rename_or_defaults_cannot_convert_preparation(sample):
    raw=declaration(sample);raw['version']='news-prospective-timing-authorization-v1'
    with pytest.raises(ValidationError):p.clock.Authorization.model_validate(raw)
    record=p.Preparation.model_validate(declaration(sample))
    with pytest.raises(ValueError,match='preparation_is_not_execution_authorization'):
        p.reject_as_execution_authorization(record)


def test_missing_fields_are_not_supplied_by_defaults(sample):
    raw=declaration(sample);del raw['start_authorized']
    with pytest.raises(ValidationError):p.Preparation.model_validate(raw)
    raw=declaration(sample);raw['explicitly_authorized']=True
    with pytest.raises(ValidationError):p.Preparation.model_validate(raw)


def test_existing_executable_authorizations_still_require_all_original_claims(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    path=fx.auth(sample,sid)
    result=fx.t.record(repo,plan,folder,sid,'start',now=fx.AT,auth_path=path,
                       phase='factual_reading',confirm_start=True)
    assert result['case_sessions'][sid]=='active'  # Synthetic fixture only.
    fx.t.record(repo,plan,folder,sid,'stop',now=fx.AT+timedelta(seconds=1))
    assert json.loads((folder/sid/'0000.event.json').read_text())['kind']=='synthetic_fixture'


def test_draft_template_can_keep_statement_and_source_pending(sample):
    repo,plan,_,_=sample;raw=declaration(sample)
    raw.update(familiarity_statement=None,declaration_source=None)
    raw['pending_fields'] += ['familiarity_statement','declaration_source']
    assert p.validate_preparation(repo,plan,p.Preparation.model_validate(raw),now=fx.AT)['preparation_valid']


def test_more_definite_declarations_still_never_become_execution_consent(sample):
    repo,plan,_,_=sample;raw=declaration(sample)
    raw.update(reviewer_id='SIMULATED-INSTRUMENTAL-HANDLE',familiarity_status='owner_declares_unseen',
               first_reading='declared_yes',variant_exposure='owner_declares_unseen',
               pending_fields=['execution_authorization'])
    record=p.Preparation.model_validate(raw)
    result=p.validate_preparation(repo,plan,record,now=fx.AT)
    assert result['preparation_valid'] and not result['start_authorized'] and not result['eligibility_granted']
    with pytest.raises(ValidationError):p.clock.Authorization.model_validate(record.model_dump(mode='json'))
