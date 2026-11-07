"""Retry lineage with temporary structural fixtures, never real pilot attempts."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("retry_workflow_fixtures",REPO/"tests/unit/test_pilot_contract_workflow.py")
fx = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fx
spec.loader.exec_module(fx)
w, START = fx.w, fx.START


@pytest.fixture
def sample(tmp_path,monkeypatch):
    return fx.sample.__wrapped__(tmp_path,monkeypatch)


def stopped_without_mapping(sample):
    repo,_,folder,_,_=sample
    fx.start(sample)
    w.clock(repo,folder,"pause",now=START+timedelta(seconds=10),reason="ai_wait")
    w.apply_mappings(repo,folder,fx.submission(sample),now=START+timedelta(seconds=15))
    w.clock(repo,folder,"resume",now=START+timedelta(seconds=20),phase="owner_review")
    w.clock(repo,folder,"stop",now=START+timedelta(seconds=30))


def retry(sample,**kwargs):
    repo,_,source,s,_=sample
    folder=repo/"retry-workspace"
    result=w.prepare_retry(repo,source,folder,s["packet"]["case_id"],
        reason=kwargs.get("reason","contract_mapping_not_timed"),now=kwargs.get("now",START+timedelta(seconds=31)))
    return folder,result


def snapshot(folder):
    return {p:p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def assert_prepared(sample,folder):
    repo,_,source,_,_=sample
    prep,form,_,_=w._load(repo,folder,now=START+timedelta(seconds=31))
    assert isinstance(prep,w.RetryPreparation)
    lineage=w.RetryLineage.model_validate(w.m.d.read_ref(repo,prep.retry_lineage))
    old_prep,old_form,_,_=w._load(repo,source,now=START+timedelta(seconds=31))
    assert prep.review_id!=old_prep.review_id
    assert lineage.predecessor_form==w._ref(repo,w.m.d.path_for(repo,old_prep.form_path))
    assert lineage.predecessor_session==old_form.session
    assert lineage.predecessor_inventory==w._inventory(repo,source)
    assert not lineage.independent_evaluation and not lineage.proposal_initially_approved
    assert not lineage.prior_times_transferred
    proposal=w.Submission.model_validate(w.m.d.read_ref(repo,lineage.derived_proposal))
    assert proposal.model_dump(mode="json")["mappings"]==old_form.model_dump(mode="json")["mappings"]
    assert proposal.rationale==old_form.rationale and proposal.allowed_outcomes==old_form.allowed_outcomes
    assert form.status=="unfilled" and not form.mappings and form.owner_decision is None
    session=w.m.ContractSession.model_validate(w.m.d.read_ref(repo,form.session))
    disposition=w.m.d.Disposition.model_validate(w.m.d.read_ref(repo,form.closed_disposition))
    assert session.model_dump(mode="json")==w.m.blank_session(disposition)
    assert not (folder/"opening").exists() and not (folder/"clock").exists()
    assert w._json(folder/"OPENING-TEMPLATE.json")["explicitly_authorized"] is None
    approval=w._json(folder/"CONTENT-APPROVAL-TEMPLATE.json")
    assert approval["explicitly_approved"] is None and approval["review_fingerprint"] is None
    with pytest.raises(w.c.ValidationError):w.m.OwnerDecision.model_validate(approval)
    return prep,form,proposal


def test_explicit_retry_preserves_predecessor_and_proposal_without_authorization(sample):
    stopped_without_mapping(sample)
    before=snapshot(sample[2]);folder,result=retry(sample)
    assert result["form_status"]=="unfilled" and not result["content_approval_recorded"]
    assert_prepared(sample,folder)
    assert before==snapshot(sample[2])
    assert w.validate(sample[0],sample[2],now=START+timedelta(seconds=31))["form_status"]=="in_progress"
    with pytest.raises(ValueError,match="contract_mapping_not_timed"):
        w.approval_plan(sample[0],sample[2],now=START+timedelta(seconds=31))


def test_ordinary_prepare_keeps_its_block(sample):
    stopped_without_mapping(sample)
    with pytest.raises(ValueError,match="source_review_still_active"):
        w.prepare(sample[0],sample[2],sample[0]/"unused",sample[3]["packet"]["case_id"],now=START+timedelta(seconds=31))
    assert not (sample[0]/"unused").exists()


@pytest.mark.parametrize("state,code",[
    ("unfilled","retry_not_eligible"), ("active","retry_not_eligible"),
    ("all_timed","retry_reason_not_observed"), ("wrong_case","retry_not_eligible"),
    ("approved","retry_not_eligible"), ("completed","retry_not_eligible"),
    ("missing_mappings","all_facts_contractual_review_required"),
])
def test_retry_refuses_unjustified_or_approved_attempt(sample,state,code):
    repo,_,source,s,_=sample
    if state=="active":fx.start(sample)
    elif state in {"all_timed","approved","completed"}:
        plan=fx.ready(sample)
        if state in {"approved","completed"}:fx.approve(sample,plan)
        if state=="completed":
            w.finalize(repo,source,fingerprint=plan["review_fingerprint"],authorized_by="SIMULATED OWNER",
                closure_source="Synthetic final closure.",authorize_final_closure=True,now=START+timedelta(seconds=52))
    elif state=="missing_mappings":
        fx.start(sample);w.clock(repo,source,"stop",now=START+timedelta(seconds=30))
    elif state!="unfilled":stopped_without_mapping(sample)
    before=snapshot(source)
    case="wrong-case" if state=="wrong_case" else s["packet"]["case_id"]
    with pytest.raises(ValueError,match=code):
        w.prepare_retry(repo,source,repo/"unused",case,reason="contract_mapping_not_timed",now=START+timedelta(seconds=60))
    assert not (repo/"unused").exists() and before==snapshot(source)


def test_expired_attempt_cannot_be_read_or_revived(sample):
    stopped_without_mapping(sample)
    with pytest.raises(ValueError,match="contract_session_metadata_expired"):
        retry(sample,now=START+timedelta(days=91))
    assert not (sample[0]/"retry-workspace").exists()


def test_retry_reason_must_match_the_actual_missing_phase(sample):
    stopped_without_mapping(sample)
    with pytest.raises(ValueError,match="retry_reason_not_observed"):
        retry(sample,reason="owner_review_not_timed")
    assert not (sample[0]/"retry-workspace").exists()


def test_completed_label_requires_a_real_stop_event(sample):
    stopped_without_mapping(sample)
    source=sample[2];repo=sample[0]
    state=w._json(source/"clock/state.json");path=w.m.d.path_for(repo,state["last_event"]["path"])
    event=w._json(path);event.update(action="phase",next_kind="active",next_phase="owner_review")
    fx.write(path,event)
    state["last_event"]=w._ref(repo,path).model_dump();fx.write(source/"clock/state.json",state)
    with pytest.raises(ValueError,match="retry_not_eligible"):
        retry(sample)
    assert not (repo/"retry-workspace").exists()


def test_missing_owner_review_is_supported_without_synthesizing_it(sample):
    repo,_,source,_,_=sample
    fx.start(sample)
    w.clock(repo,source,"phase",phase="contract_mapping",now=START+timedelta(seconds=10))
    w.apply_mappings(repo,source,fx.submission(sample),now=START+timedelta(seconds=15))
    w.clock(repo,source,"stop",now=START+timedelta(seconds=30))
    with pytest.raises(ValueError,match="owner_review_not_timed"):
        w.approval_plan(repo,source,now=START+timedelta(seconds=31))
    folder,_=retry(sample,reason="owner_review_not_timed")
    assert_prepared(sample,folder)


@pytest.mark.parametrize("target",["mapping","lineage","historical_addition","historical_event","template_source"])
def test_lineage_or_predecessor_tampering_blocks_validation(sample,target):
    stopped_without_mapping(sample);folder,_=retry(sample);repo=sample[0]
    if target=="mapping":
        path=folder/"DERIVED-PROPOSAL-v1.json";raw=w._json(path)
        raw["mappings"][0]["rationale"]="Hidden new semantic claim.";fx.write(path,raw)
        # Even if a new lineage hash is supplied, semantic equality to the predecessor must hold.
        lineage=w._json(folder/"retry-lineage-v1.json");lineage["derived_proposal"]=w._ref(repo,path).model_dump()
        fx.write(folder/"retry-lineage-v1.json",lineage)
        prep=w._json(folder/"workflow.json");prep["retry_lineage"]=w._ref(repo,folder/"retry-lineage-v1.json").model_dump()
        fx.write(folder/"workflow.json",prep)
    elif target=="lineage":
        path=folder/"retry-lineage-v1.json";raw=w._json(path);raw["predecessor_review_id"]="other-review"
        fx.write(path,raw)
        prep=w._json(folder/"workflow.json");prep["retry_lineage"]=w._ref(repo,path).model_dump();fx.write(folder/"workflow.json",prep)
    elif target=="historical_addition":(sample[2]/"unexpected.txt").write_text("fixture")
    elif target=="historical_event":
        path=next((sample[2]/"clock").glob("*.event.json"));path.write_bytes(path.read_bytes()+b" ")
    else:
        path=sample[2]/"OPENING-TEMPLATE.json";path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError):w.validate(repo,folder,now=START+timedelta(seconds=31))


def test_new_attempt_requires_new_opening_and_new_measured_phases(sample):
    repo,_,source,_,_=sample
    stopped_without_mapping(sample);before=snapshot(source);folder,_=retry(sample)
    prep,form,proposal=assert_prepared(sample,folder)
    with pytest.raises(ValueError,match="reserved_authorization_mismatch"):
        w.open_review(repo,folder,source/"opening/authorization.json",now=START+timedelta(seconds=32))
    auth=w._json(folder/"OPENING-TEMPLATE.json")
    auth.update(explicitly_authorized=True,decision_source="Separate synthetic retry opening.")
    path=fx.write(repo/"retry-opening.json",auth)
    w.open_review(repo,folder,path,now=START+timedelta(seconds=32))
    w.clock(repo,folder,"start",phase="contract_mapping",reviewer_id="fixture",reviewer_name="SIMULATED OWNER",
        context="Synthetic assisted retry, not independent.",now=START+timedelta(seconds=40))
    w.apply_mappings(repo,folder,folder/"DERIVED-PROPOSAL-v1.json",now=START+timedelta(seconds=45))
    w.clock(repo,folder,"phase",phase="owner_review",now=START+timedelta(seconds=50))
    w.clock(repo,folder,"stop",now=START+timedelta(seconds=60))
    plan=w.approval_plan(repo,folder,now=START+timedelta(seconds=60))
    _,updated,_,_=w._load(repo,folder,now=START+timedelta(seconds=60))
    session=w.m.ContractSession.model_validate(w.m.d.read_ref(repo,updated.session))
    assert session.active_seconds==20 and session.pause_seconds==0
    assert session.phase_seconds["contract_mapping"]==10 and session.phase_seconds["owner_review"]==10
    assert session.phase_seconds["material_reading"]==0
    assert plan["review_id"]==prep.review_id and updated.owner_decision is None
    assert before==snapshot(source)


def test_predecessor_times_cannot_be_inserted_into_new_session(sample):
    stopped_without_mapping(sample);folder,_=retry(sample)
    _,_,proposal=assert_prepared(sample,folder)
    raw=w._json(folder/"OPENING-TEMPLATE.json");raw.update(explicitly_authorized=True,decision_source="Synthetic opening.")
    w.open_review(sample[0],folder,fx.write(sample[0]/"retry-opening.json",raw),now=START+timedelta(seconds=31))
    # Inject through the old helper in a fixture only; the new CLI has no backdating option.
    w.c.record(sample[0],folder,"start",phase="contract_mapping",reviewer_id="fixture",reviewer_name="SIMULATED OWNER",
        context="Synthetic invalid historical clock.",now=START+timedelta(seconds=25),allow_completed_other_cases=True)
    with pytest.raises(ValueError,match="retry_time_overlap"):
        w.validate(sample[0],folder,now=START+timedelta(seconds=40))


def test_thirteen_mappings_survive_exact_derivation(tmp_path,monkeypatch):
    factory=fx.clock_fx.fx
    original=factory.make_sample
    def thirteen(repo):
        s=original(repo)
        factual=deepcopy(s["form"]["factual_snapshot"])
        for i in range(3,14):
            fact=deepcopy(factual["facts"][1]);fact["fact_id"]=f"F{i:03}"
            factual["facts"].append(fact);factual["dimension_assessments"]["identity"]["fact_ids"].append(fact["fact_id"])
        ar=factory.write(repo,"factual.json",factual)
        approval=w._json(repo/"approval.json");approval["annotation_sha256"]=ar.sha256
        approval_ref=factory.write(repo,"approval.json",approval)
        closure=w._json(repo/"closure.json");closure.update(annotation_sha256=ar.sha256,approval_sha256=approval_ref.sha256)
        closure_ref=factory.write(repo,"closure.json",closure)
        raw=s["disposition"].model_dump(mode="json")
        raw["annotation"]=ar.model_dump();raw["content"]["decision"]=approval_ref.model_dump()
        raw["closure"]["decision"]=closure_ref.model_dump()
        raw=factory.fx.identify(raw)
        dr=factory.write(repo,"disposition.json",raw);d=w.m.d.Disposition.model_validate(raw)
        session=w.m.blank_session(d);sr=factory.write(repo,"contract-session.json",session)
        technical=w.m.Ref.model_validate(s["form"]["technical_reference"])
        s.update(disposition=d,disposition_ref=dr,session=session,
            form=w.m.blank_form(dr,d,factual,technical,sr))
        return s
    monkeypatch.setattr(factory,"make_sample",thirteen)
    sample=fx.sample.__wrapped__(tmp_path,monkeypatch)
    stopped_without_mapping(sample);folder,_=retry(sample)
    _,_,proposal=assert_prepared(sample,folder)
    assert len(proposal.mappings)==13


def test_failed_retry_write_keeps_source_intact_and_does_not_retry(sample,monkeypatch):
    stopped_without_mapping(sample);before=snapshot(sample[2]);original=w._write;calls=[]
    def fail(path,payload):
        calls.append(path)
        if len(calls)==2:raise OSError("Synthetic write failure")
        return original(path,payload)
    monkeypatch.setattr(w,"_write",fail)
    with pytest.raises(OSError):retry(sample)
    assert len(calls)==2 and before==snapshot(sample[2])


def test_cli_requires_explicit_reason_and_keeps_secrets_out(monkeypatch,capsys):
    monkeypatch.setattr(sys,"argv",["workflow","--workspace","unused","prepare-retry","--source","source","--case","fixture"])
    with pytest.raises(SystemExit):w.main()
    def fail(*a,**kw):raise ValueError("PRIVATE-RESPONSE")
    monkeypatch.setattr(w,"prepare_retry",fail)
    monkeypatch.setattr(sys,"argv",["workflow","--workspace","unused","prepare-retry","--source","source","--case","fixture",
        "--reason","contract_mapping_not_timed"])
    assert w.main()==2
    assert "PRIVATE-RESPONSE" not in capsys.readouterr().out
