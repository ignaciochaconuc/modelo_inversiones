"""Entirely fictional clocks and materials in tmp_path; never real measurements."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prospective_timing_tests", REPO/"tools/evaluation/prospective_timing_pilot.py")
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)
AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def write(repo, name, data):
    path = repo/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data if isinstance(data,bytes) else t.encoded(data))
    return t.ref_for(repo,path)


@pytest.fixture
def sample(tmp_path):
    instrument = write(tmp_path,"tools/evaluation/prospective_timing_pilot.py",(REPO/"tools/evaluation/prospective_timing_pilot.py").read_bytes())
    rows=[];private=[];candidates=[];slots=[]
    for i in range(3):
        cid=f"SIMULATED-CASE-{i}"
        row=dict(case_id=cid,primary_revision_id=f"fixture-revision-{i}",
                 request=dict(news=dict(headline="FICTIONAL TEST HEADLINE",summary="Fictional test source."),
                              decision_time="2031-01-01T00:00:00Z",registry_entries=[]),
                 request_fingerprint=f"request-{i}",packet_fingerprint=f"packet-{i}",evidence_fingerprint=f"evidence-{i}",
                 evidence=[dict(evidence_id="fixture-evidence",news_id="fixture-news",revision_id=f"fixture-revision-{i}",
                                field="summary",text="Fictional test source.",available_at="2031-01-01T00:00:00Z")])
        rows.append(row);private.append(dict(case_id=cid,family_id=f"SIMULATED-FAMILY-{i}",primary_stratum="DO NOT DISCLOSE"))
        candidates.append(dict(case_id=cid,family_id=f"SIMULATED-FAMILY-{i}",packet_fingerprint=f"packet-{i}",request_fingerprint=f"request-{i}"))
        slots.extend(dict(session_id=f"pt-fixture-{stage}-{i}",case_id=cid,stage=stage) for stage in ["factual","contractual"])
    corpus=write(tmp_path,"inputs/corpus.json",dict(purpose="development_only",fictional=True,cases=rows))
    private_ref=write(tmp_path,"inputs/private.json",dict(cases=private))
    excluded=write(tmp_path,"inputs/excluded.json",dict(selected_case_ids=["HISTORICAL-CASE"]))
    manifest=write(tmp_path,"inputs/manifest.json",dict(reserved_cases_created=0,reserved_freeze_created=False,reference_status="not_created",
                   sha256={r.path:r.sha256 for r in [corpus,private_ref,excluded]}))
    technical_files={}
    for name in ['economic_attribution','grounding','replay','schemas']:
        ref=write(tmp_path,f'src/investment_system/agents/news_interpretation/{name}.py',b'# SYNTHETIC TEST ONLY\n')
        technical_files[ref.path]=ref.sha256
    plan=t.Plan(version=t.VERSION,kind="synthetic_fixture",purpose="development_workload_only",instrument=instrument,
                records_directory=(t.STORAGE/'fixture-only').as_posix(),
                protocol=write(tmp_path,"inputs/protocol.json",dict(kind="synthetic test protocol")),source_manifest=manifest,
                corpus=corpus,private_design=private_ref,historical_selection=excluded,
                technical_reference=write(tmp_path,"inputs/technical.json",dict(contract_version="news-economic-validation-v3",files=technical_files)),
                candidates=candidates,sessions=slots,administration_id="pt-fixture-administration")
    plan_ref=write(tmp_path,"inputs/plan.json",plan.model_dump(mode="json"))
    historical=write(tmp_path,"data/cache/news_development_pilot/DO-NOT-MODIFY.json",dict(kind="historical sentinel"))
    return tmp_path, t.load_plan(tmp_path,tmp_path/plan_ref.path), tmp_path/t.STORAGE/"fixture-only", historical


def auth(sample, sid, *, parent=None):
    repo,plan,folder,_=sample; stage=t.stage_for(plan,sid)
    data=dict(version="news-prospective-timing-authorization-v1",plan_fingerprint=t.fingerprint(plan),session_id=sid,
              explicitly_authorized=True,authorized_by="Project owner, current conversation participant",
              decision_source="SYNTHETIC FIXTURE authorization, never a real owner decision.",authorized_at=None,source_message_id=None,
              reviewer_id="SIMULATED-OWNER",reviewer_name="SIMULATED OWNER",assistance="manual_human",visible_model_label=None,
              familiarity_confirmed=True,first_reading=stage=="factual",unseen_counterfactual=True,
              familiarity_basis="SYNTHETIC TEST declaration",factual_tip=None,factual_source=None,factual_content_ready=False,
              independent_human_review=False,adjudication_claimed=False,inference_authorized=False)
    if parent is not None:
        slot=next(s for s in plan.sessions if s.session_id==sid)
        data.update(factual_tip=parent["tip"],factual_content_ready=True,
                    factual_source=write(repo,f"inputs/{sid}-factual.json",dict(case_id=slot.case_id,facts=["FICTIONAL TEST ARTIFACT"])).model_dump())
    ref=write(repo,f"inputs/{sid}-authorization.json",data)
    return repo/ref.path


def finish(sample, sid, at=AT, *, parent=None):
    repo,plan,folder,_=sample;stage=t.stage_for(plan,sid)
    t.record(repo,plan,folder,sid,"start",now=at,auth_path=auth(sample,sid,parent=parent),phase=t.PHASES[stage][0],confirm_start=True)
    for i,phase in enumerate(t.PHASES[stage][1:],1):
        t.record(repo,plan,folder,sid,"phase",now=at+timedelta(seconds=i),phase=phase)
    end=at+timedelta(seconds=len(t.PHASES[stage]))
    t.record(repo,plan,folder,sid,"stop",now=end)
    return t.read_session(repo,plan,folder,sid,now=end)


def eligibility(sample,sid,session,**overrides):
    _,plan,_,_=sample
    value=dict(version="news-prospective-timing-eligibility-v1",plan_fingerprint=t.fingerprint(plan),session_id=sid,
               session_tip=session["tip"],explicitly_attested=True,eligible_for_named_scope=True,
               scope=list(t.PHASES[t.stage_for(plan,sid)]),task_complete=True,recording_complete=True,
               no_unlogged_multitasking=True,decided_by="SIMULATED OWNER",decision_source="SYNTHETIC FIXTURE assessment",
               decided_at=None,independent_human_review=False)
    value.update(overrides)
    return t.Attestation.model_validate(value)


def test_preflight_is_readonly_unfilled_and_has_no_material_disclosure(sample):
    repo,plan,folder,_=sample
    before={p:t.digest(p) for p in repo.rglob('*') if p.is_file()}
    result=t.verify(repo,plan,folder,now=AT)
    assert set(result['case_sessions'].values())=={'unfilled'} and result['administration_state']=='unfilled'
    assert result['eligible_records']==0 and result['provider_calls']==result['inferences']==0
    assert before=={p:t.digest(p) for p in repo.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='authorized_reading_required'):
        t.material(repo,plan,folder,plan.sessions[0].session_id,now=AT)


def test_six_simulated_sessions_and_admin_preserve_historical_and_never_certify_truth(sample):
    repo,plan,folder,historical=sample
    original=t.digest(repo/historical.path);at=AT
    for slot in plan.sessions:
        parent=None
        if slot.stage=='contractual':
            parent_id=next(s.session_id for s in plan.sessions if s.case_id==slot.case_id and s.stage=='factual')
            parent=t.read_session(repo,plan,folder,parent_id,now=at)
        session=finish(sample,slot.session_id,at,parent=parent)
        assert session['complete_phases']
        assert t.verify(repo,plan,folder,now=at+timedelta(seconds=5))['eligible_records']==0
        at+=timedelta(seconds=10)
    result=t.verify(repo,plan,folder,now=at)
    assert set(result['case_sessions'].values())=={'stopped'} and result['eligible_records']==0
    admin=finish(sample,plan.administration_id,at)
    assert admin['active_seconds']==1
    decision=write(repo,'inputs/eligibility.json',eligibility(sample,plan.administration_id,admin).model_dump(mode='json'))
    result=t.attest(repo,plan,folder,repo/decision.path,now=at+timedelta(seconds=2))
    assert result['eligible_records']==1 and result['structural_validation_only']
    assert result['semantic_truth']=='not_assessed' and not result['integral_pilot_completed']
    assert not result['factual_timing_rehabilitated'] and t.digest(repo/historical.path)==original


@pytest.mark.parametrize('field,value',[('explicitly_authorized',False),('familiarity_confirmed',False),
    ('first_reading',False),('unseen_counterfactual',False),('plan_fingerprint','altered'),('independent_human_review',0),('inference_authorized',True)])
def test_start_rejects_missing_or_fictitious_authorization_without_writing(sample,field,value):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    path=auth(sample,sid);data=json.loads(path.read_text());data[field]=value
    bad=write(repo,'inputs/bad-authorization.json',data)
    with pytest.raises(ValueError):
        t.record(repo,plan,folder,sid,'start',now=AT,auth_path=repo/bad.path,phase='factual_reading',confirm_start=True)
    assert not folder.exists()


def test_no_confirmation_no_clock_and_protected_storage_refused(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    with pytest.raises(ValueError,match='explicit_real_start_required'):
        t.record(repo,plan,folder,sid,'start',now=AT,auth_path=auth(sample,sid),phase='factual_reading')
    with pytest.raises(ValueError,match='isolated_storage_required'):
        t.verify(repo,plan,repo/'data/cache/news_development_pilot',now=AT)
    assert not folder.exists()


def test_contract_cannot_start_without_completed_bound_factual(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[1].session_id
    with pytest.raises(ValueError,match='factual_gate_missing'):
        t.record(repo,plan,folder,sid,'start',now=AT,auth_path=auth(sample,sid),phase='contract_reading',confirm_start=True)
    assert not folder.exists()


def test_pause_excludes_wait_and_no_overlap_with_batch_administration(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    t.record(repo,plan,folder,sid,'start',now=AT,auth_path=auth(sample,sid),phase='factual_reading',confirm_start=True)
    data=t.material(repo,plan,folder,sid,now=AT)
    assert set(data)=={'case_id','primary_revision_id','headline','summary','decision_time','eligible_registry','evidence'}
    assert 'family_id' not in json.dumps(data) and 'DO NOT DISCLOSE' not in json.dumps(data)
    t.record(repo,plan,folder,sid,'pause',now=AT+timedelta(seconds=2),reason='ai_wait')
    with pytest.raises(ValueError,match='other_session_active'):
        t.record(repo,plan,folder,plan.administration_id,'start',now=AT+timedelta(seconds=3),
                 auth_path=auth(sample,plan.administration_id),phase='batch_administration',confirm_start=True)
    t.record(repo,plan,folder,sid,'resume',now=AT+timedelta(seconds=12),phase='factual_annotation')
    t.record(repo,plan,folder,sid,'stop',now=AT+timedelta(seconds=13))
    session=t.read_session(repo,plan,folder,sid,now=AT+timedelta(seconds=13))
    assert session['active_seconds']==3 and session['pause_seconds']==10
    with pytest.raises(ValueError,match='scope_not_eligible'):
        t.validate_eligibility(repo,plan,sid,eligibility(sample,sid,session),session,now=AT+timedelta(seconds=14))


def test_ttl_strict_and_no_renewal_from_later_eligibility(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    session=finish(sample,sid);end=session['last'].at
    t.verify(repo,plan,folder,now=end+timedelta(days=90,microseconds=-1))
    with pytest.raises(ValueError,match='timing_metadata_expired'):
        t.verify(repo,plan,folder,now=end+timedelta(days=90))


def test_tampered_event_and_duplicate_stop_rejected(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    finish(sample,sid)
    with pytest.raises(ValueError,match='session_not_active'):
        t.record(repo,plan,folder,sid,'stop',now=AT+timedelta(seconds=6))
    path=folder/sid/'0000.event.json';raw=json.loads(path.read_text());raw['phase']='contract_mapping';path.write_bytes(t.encoded(raw))
    with pytest.raises(ValueError):t.verify(repo,plan,folder,now=AT+timedelta(seconds=6))


@pytest.mark.parametrize('mutation',['expected','historical','family','reserved','hash'])
def test_source_contract_rejects_answers_historical_cases_and_reserved(sample,mutation):
    repo,plan,folder,_=sample;raw=plan.model_dump(mode='json')
    if mutation=='family':raw['candidates'][1]['family_id']=raw['candidates'][0]['family_id']
    elif mutation=='hash':raw['corpus']['sha256']='altered'
    else:
        ref_name='corpus' if mutation in {'expected','historical'} else 'source_manifest'
        value=json.loads((repo/raw[ref_name]['path']).read_text())
        if mutation=='expected':value['cases'][0]['expected_answer']='FORBIDDEN'
        elif mutation=='historical':value['cases'][0]['case_id']='HISTORICAL-CASE'
        else:value['reserved_freeze_created']=True
        (repo/raw[ref_name]['path']).write_bytes(t.encoded(value));raw[ref_name]['sha256']=t.digest(repo/raw[ref_name]['path'])
        if ref_name=='corpus':
            manifest=json.loads((repo/raw['source_manifest']['path']).read_text());manifest['sha256'][raw['corpus']['path']]=raw['corpus']['sha256']
            (repo/raw['source_manifest']['path']).write_bytes(t.encoded(manifest));raw['source_manifest']['sha256']=t.digest(repo/raw['source_manifest']['path'])
    path=write(repo,'inputs/bad-plan.json',raw)
    with pytest.raises(ValueError):t.load_plan(repo,repo/path.path)


def test_stale_lock_and_partial_persistence_block_without_repair(sample):
    repo,plan,folder,_=sample
    folder.mkdir(parents=True);(folder/'.lock').write_text('synthetic crash marker')
    with pytest.raises(ValueError,match='unexpected_batch_file_or_lock'):t.verify(repo,plan,folder,now=AT)
    assert (folder/'.lock').exists()


def test_real_completion_requires_explicit_attestation_and_preserves_it(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    session=finish(sample,sid)
    decision=write(repo,'inputs/approval.json',eligibility(sample,sid,session).model_dump(mode='json'))
    result=t.attest(repo,plan,folder,repo/decision.path,now=AT+timedelta(seconds=6))
    assert result['eligible_records']==1
    before={p:t.digest(p) for p in folder.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):t.attest(repo,plan,folder,repo/decision.path,now=AT+timedelta(seconds=7))
    assert before=={p:t.digest(p) for p in folder.rglob('*') if p.is_file()}


def test_reversed_or_naive_time_rejected_before_write(sample):
    repo,plan,folder,_=sample;sid=plan.sessions[0].session_id
    path=auth(sample,sid)
    with pytest.raises(ValueError,match='invalid_real_timestamp'):
        t.record(repo,plan,folder,sid,'start',now=AT.replace(tzinfo=None),auth_path=path,phase='factual_reading',confirm_start=True)
    assert not folder.exists()
    t.record(repo,plan,folder,sid,'start',now=AT,auth_path=path,phase='factual_reading',confirm_start=True)
    before={p:t.digest(p) for p in folder.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='session_not_active'):
        t.record(repo,plan,folder,sid,'phase',now=AT,phase='factual_annotation')
    assert before=={p:t.digest(p) for p in folder.rglob('*') if p.is_file()}
