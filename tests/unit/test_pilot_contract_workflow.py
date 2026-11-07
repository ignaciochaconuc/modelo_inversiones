"""Synthetic operator sessions only; no annotations or clocks of the real pilot."""
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


w = load("contract_workflow_tests", REPO/"tools/evaluation/pilot_contract_workflow.py")
clock_fx = load("workflow_clock_fixtures", REPO/"tests/unit/test_pilot_contract_clock.py")
START = clock_fx.START


@pytest.fixture
def sample(tmp_path, monkeypatch):
    repo, source, s, _ = clock_fx.sample.__wrapped__(tmp_path, monkeypatch)
    # Keep the actual per-record validators; replace only the frozen package inventory.
    monkeypatch.setattr(w.m.d.legacy_module(), "verify_packages", lambda repo: {s["packet"]["case_id"]:s["packet"]})
    original = w.m.verify
    def verify(repo, folder, *, now):
        result = original(repo, folder, now=now)
        # Models a prior completed case without weakening target-record validation.
        result["cases"].append(dict(case_id="completed-fixture", status="completed", review_id="previous-review"))
        return result
    monkeypatch.setattr(w.m, "verify", verify)
    folder = repo/"new-workspace"
    before = {p:p.read_bytes() for p in source.rglob("*") if p.is_file()}
    w.prepare(repo, source, folder, s["packet"]["case_id"], now=START)
    return repo, source, folder, s, before


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def opening(sample):
    repo, _, folder, _, _ = sample
    raw = w._json(folder/"OPENING-TEMPLATE.json")
    raw.update(explicitly_authorized=True, authorized_by="SIMULATED OWNER",
               decision_source="Synthetic explicit opening, no real authorization.")
    path = write(repo/"owner-opening.json", raw)
    return w.open_review(repo, folder, path, now=START)


def start(sample):
    opening(sample)
    return w.clock(sample[0], sample[2], "start", now=START, phase="material_reading",
        reviewer_id="fixture-owner", reviewer_name="SIMULATED OWNER", context="Synthetic assisted nonindependent fixture.")


def submission(sample):
    repo, _, folder, s, _ = sample
    raw = w._json(folder/"ANNOTATION-TEMPLATE.json")
    factual = w.m.d.legacy_module().Factual.model_validate(s["form"]["factual_snapshot"])
    raw["mappings"] = [dict(fact_id=f.fact_id, mode="indeterminate", rationale="Synthetic unresolved contract mapping.",
        limits_acknowledged=sorted(w.m.source_limits(f,factual.dimension_assessments[f.dimension]))) for f in factual.facts]
    raw.update(allowed_outcomes=["indeterminate"], rationale="Synthetic review; no claim of semantic correctness.")
    return write(repo/"annotation-v1.json", raw)


def ready(sample):
    repo, _, folder, _, _ = sample
    start(sample)
    w.clock(repo,folder,"phase",now=START+timedelta(seconds=10),phase="contract_mapping")
    w.clock(repo,folder,"pause",now=START+timedelta(seconds=20),reason="ai_wait")
    w.apply_mappings(repo,folder,submission(sample),now=START+timedelta(seconds=25))
    w.clock(repo,folder,"resume",now=START+timedelta(seconds=30),phase="evidence_check")
    w.clock(repo,folder,"phase",now=START+timedelta(seconds=40),phase="owner_review")
    w.clock(repo,folder,"stop",now=START+timedelta(seconds=50))
    return w.approval_plan(repo,folder,now=START+timedelta(seconds=50))


def approve(sample, plan):
    raw = plan["decision_template"]
    raw.update(explicitly_approved=True,decided_by="SIMULATED OWNER",
        decision_source="Synthetic content approval, separate from closure.")
    path = write(sample[0]/"content-owner-decision.json",raw)
    return w.approve_content(sample[0],sample[2],path,now=START+timedelta(seconds=51))


def test_preparation_is_not_opening_and_packet_contains_every_fact(sample):
    repo,_,folder,s,before = sample
    assert not (folder/"opening").exists() and not (folder/"clock").exists()
    result=w.validate(repo,folder,now=START)
    assert result["form_status"]=="unfilled" and not result["content_approval_recorded"]
    prep=w.Preparation.model_validate(w._json(folder/"workflow.json"))
    packet=(folder/"materials/CHATGPT-PACKET.md").read_text(encoding="utf-8")
    for fact in s["form"]["factual_snapshot"]["facts"]:
        assert fact["fact_id"] in packet and fact["meaning"] in packet
    assert all(w.m.d.bound_path(repo,ref).exists() for ref in prep.materials)
    assert all(p.read_bytes()==v for p,v in before.items())
    with pytest.raises(w.c.ValidationError):
        w.m.OpeningAuthorization.model_validate(w._json(folder/"OPENING-TEMPLATE.json"))


def test_opening_does_not_invent_a_start_and_legacy_clock_remains_strict(sample):
    repo,_,folder,_,_ = sample
    assert opening(sample)["form_status"]=="unfilled"
    assert not (folder/"clock").exists()
    assert w.clock(repo,folder,"status",now=START)["clock"]=="authorized_waiting_for_real_start"
    with pytest.raises(ValueError,match="other_cases_must_remain_unfilled"):
        w.c.status(repo,folder,now=START)


def test_end_to_end_all_facts_three_authorities_and_prospective_time(sample):
    repo,source,folder,_,before=sample
    plan=ready(sample)
    assert plan["decision_template"]["explicitly_approved"] is None
    assert w.validate(repo,folder,now=START+timedelta(seconds=50))["form_status"]=="in_progress"
    assert approve(sample,plan)["form_status"]=="in_progress"
    result=w.finalize(repo,folder,fingerprint=plan["review_fingerprint"],authorized_by="SIMULATED OWNER",
        closure_source="Synthetic separate final closure authorization.",authorize_final_closure=True,
        now=START+timedelta(seconds=52))
    assert result["form_status"]=="completed" and result["provider_calls"]==result["inferences"]==0
    prep,form,_,_=w._load(repo,folder,now=START+timedelta(seconds=52))
    session=w.m.ContractSession.model_validate(w.m.d.read_ref(repo,form.session))
    assert session.active_seconds==40 and session.pause_seconds==10
    assert session.phase_seconds["owner_review"]==10 and not session.factual_timing_reused
    assert w.m.review_fingerprint(form)==plan["review_fingerprint"]
    assert w._json(repo/form.factual.path)["status"]=="in_progress"
    assert all(p.read_bytes()==v for p,v in before.items())
    receipt=[w._json(p) for p in (folder/"workflow-history").glob("*/receipt.json")
        if w._json(p)["action"]=="final_closure_authorized_and_applied"][0]
    assert receipt["authorization"]["authorized_at"] is None


@pytest.mark.parametrize("mutation,code",[
    ("missing_fact","all_facts_contractual_review_required"),
    ("duplicate_fact","all_facts_contractual_review_required"),
    ("certainty","source_uncertainty_not_preserved"),
    ("stale","stale_contractual_source_binding"),
    ("review_id","stale_contractual_source_binding"),
    ("foreign_field","schema"),
])
def test_import_rejects_missing_facts_hidden_changes_and_lost_uncertainty(sample,mutation,code):
    repo,_,folder,_,_=sample
    start(sample);path=submission(sample);raw=w._json(path)
    if mutation=="missing_fact":raw["mappings"].pop()
    if mutation=="duplicate_fact":raw["mappings"][1]=raw["mappings"][0]
    if mutation=="certainty":raw["mappings"][1]["limits_acknowledged"]=[]
    if mutation=="stale":raw["factual"]["sha256"]="f"*64
    if mutation=="review_id":raw["review_id"]="another-review"
    if mutation=="foreign_field":raw["factual_snapshot"]={}
    write(path,raw)
    before={p:p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    with pytest.raises((ValueError,w.c.ValidationError)) as caught:
        w.apply_mappings(repo,folder,path,now=START+timedelta(seconds=1))
    if code!="schema":assert code in str(caught.value)
    assert before=={p:p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@pytest.mark.parametrize("missing",["opening","clock","owner_review"])
def test_no_implicit_opening_start_or_completed_review(sample,missing):
    repo,_,folder,_,_=sample
    if missing=="opening":
        with pytest.raises((ValueError,FileNotFoundError)):
            w.clock(repo,folder,"start",now=START,phase="material_reading")
    elif missing=="clock":
        opening(sample)
        with pytest.raises(ValueError,match="completed_session_required"):
            w.approval_plan(repo,folder,now=START)
    else:
        start(sample)
        w.clock(repo,folder,"phase",now=START+timedelta(seconds=1),phase="contract_mapping")
        w.apply_mappings(repo,folder,submission(sample),now=START+timedelta(seconds=2))
        w.clock(repo,folder,"stop",now=START+timedelta(seconds=3))
        with pytest.raises(ValueError,match="owner_review_not_timed"):
            w.approval_plan(repo,folder,now=START+timedelta(seconds=3))


@pytest.mark.parametrize("mutation,code",[
    ("no_content_approval","contract_owner_decision_required"),
    ("no_closure","explicit_closure_authorization_required"),
    ("wrong_fingerprint","authorized_fingerprint_mismatch"),
    ("wrong_actor","explicit_closure_authorization_required"),
])
def test_closure_requires_separate_explicit_authority(sample,mutation,code):
    repo,_,folder,_,_=sample;plan=ready(sample)
    if mutation!="no_content_approval":approve(sample,plan)
    kwargs=dict(fingerprint=plan["review_fingerprint"],authorized_by="SIMULATED OWNER",
        closure_source="Synthetic explicit closure.",authorize_final_closure=True)
    if mutation=="no_closure":kwargs["authorize_final_closure"]=False
    if mutation=="wrong_fingerprint":kwargs["fingerprint"]="f"*64
    if mutation=="wrong_actor":kwargs["authorized_by"]="Other person"
    with pytest.raises(ValueError,match=code):
        w.finalize(repo,folder,now=START+timedelta(seconds=52),**kwargs)
    assert w.validate(repo,folder,now=START+timedelta(seconds=52))["form_status"]=="in_progress"


def test_content_approval_freezes_draft_but_does_not_close_it(sample):
    plan=ready(sample);approve(sample,plan)
    with pytest.raises(ValueError,match="draft_not_editable"):
        w.apply_mappings(sample[0],sample[2],sample[0]/"annotation-v1.json",now=START+timedelta(seconds=52))


def test_approval_cannot_bypass_recording_step(sample):
    plan=ready(sample)
    raw=plan["decision_template"]
    raw.update(explicitly_approved=True,decision_source="Synthetic unregistered decision.")
    write(sample[2]/"content-approval.json",raw)
    with pytest.raises(ValueError,match="workflow_receipt_mismatch"):
        w.finalize(sample[0],sample[2],fingerprint=plan["review_fingerprint"],
            authorized_by="SIMULATED OWNER",closure_source="Synthetic closure.",authorize_final_closure=True,
            now=START+timedelta(seconds=52))


@pytest.mark.parametrize("target",["material","source","receipt","approval"])
def test_integrity_tampering_blocks_read_only_validation(sample,target):
    repo,source,folder,_,_=sample
    if target=="material":path=folder/"materials/FACTUAL-APPROVED.json"
    elif target=="source":path=source/"manifest.json"
    elif target=="receipt":
        opening(sample);path=next((folder/"workflow-history").glob("*/receipt.json"))
    else:
        approve(sample,ready(sample));path=folder/"content-approval.json"
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError):w.validate(repo,folder,now=START+timedelta(seconds=52))


def test_persistence_failure_blocks_without_retry_or_clock_rewrite(sample,monkeypatch):
    repo,_,folder,_,_=sample
    start(sample);path=submission(sample)
    state=(folder/"clock/state.json").read_bytes()
    calls=[]
    def fail(*args):
        calls.append(args);raise OSError("Synthetic private path")
    monkeypatch.setattr(w.os,"replace",fail)
    with pytest.raises(OSError):w.apply_mappings(repo,folder,path,now=START+timedelta(seconds=1))
    assert len(calls)==1 and (folder/"clock/state.json").read_bytes()==state
    with pytest.raises(ValueError,match="incomplete_workflow_operation"):
        w.validate(repo,folder,now=START+timedelta(seconds=2))


def test_expired_session_not_reopened_or_exported(sample):
    ready(sample)
    with pytest.raises(ValueError,match="contract_session_metadata_expired"):
        w.approval_plan(sample[0],sample[2],now=START+timedelta(days=91))


@pytest.mark.parametrize("target",["backup","orphan","pending"])
def test_clock_archives_and_partial_operations_cannot_be_ignored(sample,target):
    repo,_,folder,_,_=sample
    start(sample)
    if target=="backup":
        path=next((folder/"clock/history").glob("*/form.json"))
        path.write_bytes(path.read_bytes()+b" ")
    elif target=="orphan":
        path=next((folder/"clock").glob("*.event.json"))
        (folder/"clock/orphan.event.json").write_bytes(path.read_bytes())
    else:(folder/"clock/unapplied.pending").write_bytes(b"fixture")
    with pytest.raises(ValueError,match="clock_history_mismatch"):
        w.validate(repo,folder,now=START+timedelta(seconds=1))


def test_partial_archive_before_receipt_blocks_next_operation(sample):
    repo,_,folder,_,_=sample
    (folder/"workflow-history/incomplete").mkdir(parents=True)
    with pytest.raises(ValueError,match="incomplete_workflow_operation"):
        opening(sample)
    assert not (folder/"opening").exists()


def test_no_overwrite_completed_case_or_existing_workspace(sample):
    repo,source,folder,s,_=sample
    with pytest.raises(ValueError,match="new_separate_workspace_required"):
        w.prepare(repo,source,folder,s["packet"]["case_id"],now=START)
    with pytest.raises(ValueError,match="case_not_available"):
        w.prepare(repo,source,repo/"unused", "not-a-case",now=START)
    assert not (repo/"unused").exists()


def test_offline_import_and_error_boundary_do_not_load_credentials(sample,monkeypatch,capsys):
    from investment_system.core import environment
    monkeypatch.setattr(environment,"load_repository_environment",lambda **kw:pytest.fail("No dotenv"))
    assert w.validate(sample[0],sample[2],now=START)["provider_calls"]==0
    def fail(*a,**kw):raise ValueError("PRIVATE-CONTENT secret")
    monkeypatch.setattr(w,"validate",fail)
    monkeypatch.setattr(sys,"argv",["workflow","--workspace","unused","validate"])
    assert w.main()==2
    text=capsys.readouterr().out
    assert "PRIVATE" not in text and "secret" not in text
