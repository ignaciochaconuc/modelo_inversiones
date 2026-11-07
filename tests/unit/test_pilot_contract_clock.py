"""Prospective clock fixtures in temporary directories, never real pilot activity."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c = load("contract_clock_tests", REPO/"tools/evaluation/pilot_contract_clock.py")
fx = load("contract_clock_fixtures", REPO/"tests/unit/test_pilot_contract_review.py")
START = datetime(2026,1,10,11,tzinfo=timezone.utc)


@pytest.fixture
def sample(tmp_path, monkeypatch):
    s = fx.make_sample(tmp_path)
    folder = tmp_path/"workspace"
    d = s["disposition"]
    session_ref = fx.write(tmp_path,"workspace/sessions/case.json",s["session"])
    s["form"]["session"] = session_ref.model_dump()
    form_ref = fx.write(tmp_path,"workspace/forms/case.json",s["form"])
    auth = dict(schema_version="news-pilot-contract-opening-authorization-v1",case_id=d.case_id,review_id="clock-fixture-1",
        disposition_id=d.disposition_id,factual_sha256=d.annotation.sha256,closure_sha256=d.closure.decision.sha256,
        explicitly_authorized=True,authorized_by=d.content.provenance.approver_identity,
        decision_source="Synthetic fixture authorization, not a real owner instruction.",authorized_at=None,
        source_message_id=None,inference_authorized=False)
    auth_ref = fx.write(tmp_path,"workspace/opening/auth.json",auth)
    fx.write(tmp_path,"workspace/opening/reservation.json",dict(record_version="news-pilot-contract-opening-reservation-v1",
        case_id=d.case_id,review_id=auth["review_id"],opening_authorization=auth_ref.model_dump(),
        form_path=form_ref.path,session_path=session_ref.path))
    fx.write(tmp_path,"workspace/manifest.json",dict(schema_version="news-pilot-contract-adapter-manifest-v1",
        disposition_manifest=s["disposition_ref"].model_dump(),technical_reference=s["form"]["technical_reference"],forms=[form_ref.model_dump()]))
    def verify(repo, selected, *, now):
        manifest=c.m.Manifest.model_validate(json.loads((selected/"manifest.json").read_text(encoding="utf-8")))
        form=c.m.ContractForm.model_validate(c.m.d.read_ref(repo,manifest.forms[0]))
        result=c.m.validate_form(repo,form,s["disposition_ref"],d,s["packet"],now=now)
        return dict(cases=[result])
    monkeypatch.setattr(c.m,"verify",verify)
    return tmp_path,folder,s,auth


def begin(sample):
    repo,folder,_,_=sample
    return c.record(repo,folder,"start",now=START,phase="material_reading",
        reviewer_id="fixture-owner",reviewer_name="SIMULATED OWNER",context="Synthetic nonindependent owner context.")


def test_authorization_can_be_reserved_without_inventing_session_time(sample):
    repo,folder,_,_=sample
    before={p:c.m.d.digest(p) for p in repo.rglob("*") if p.is_file()}
    result=c.status(repo,folder,now=START)
    assert result["authorization_valid"] and result["clock"]=="authorized_waiting_for_real_start"
    assert result["session_status"]=="unfilled" and result["review_id"]=="clock-fixture-1"
    assert not (folder/"clock").exists()
    assert before=={p:c.m.d.digest(p) for p in repo.rglob("*") if p.is_file()}


def test_explicit_start_is_only_when_prospective_clock_and_person_are_supplied(sample):
    repo,folder,_,_=sample
    assert begin(sample)["session_status"]=="in_progress"
    session=json.loads((folder/"sessions/case.json").read_text(encoding="utf-8"))
    assert datetime.fromisoformat(session["started_at"])==START and session["intervals"]==[]
    assert session["active_seconds"] is None and session["visible_model_label"] is None
    assert session["timestamp_source"]=="manual_clock"
    assert not session["factual_timing_reused"]


def test_phases_ai_wait_and_stop_are_distinct_without_creating_contract_judgments(sample):
    repo,folder,_,_=sample
    begin(sample)
    c.record(repo,folder,"phase",now=START+timedelta(seconds=30),phase="contract_mapping")
    c.record(repo,folder,"pause",now=START+timedelta(seconds=50),reason="ai_wait")
    c.record(repo,folder,"resume",now=START+timedelta(seconds=140),phase="evidence_check")
    c.record(repo,folder,"phase",now=START+timedelta(seconds=150),phase="owner_review")
    c.record(repo,folder,"phase",now=START+timedelta(seconds=170),phase="administration")
    result=c.record(repo,folder,"stop",now=START+timedelta(seconds=180))
    session=json.loads((folder/"sessions/case.json").read_text(encoding="utf-8"))
    form=json.loads((folder/"forms/case.json").read_text(encoding="utf-8"))
    assert session["active_seconds"]==90 and session["pause_seconds"]==90
    assert session["phase_seconds"]==dict(material_reading=30,contract_mapping=20,evidence_check=10,owner_review=20,administration=10)
    assert result["clock"]=="stopped" and form["status"]=="in_progress"
    assert form["mappings"]==[] and form["owner_decision"] is None
    assert len(list((folder/"clock").glob("*.event.json")))==7


@pytest.mark.parametrize("action", ["phase","pause","resume","stop"])
def test_clock_cannot_run_before_real_start(sample,action):
    with pytest.raises(ValueError,match="clock_not_running"):
        c.record(sample[0],sample[1],action,now=START,phase="contract_mapping",reason="break")
    assert not (sample[1]/"clock").exists()


@pytest.mark.parametrize("missing", ["reviewer_id","reviewer_name","context","phase"])
def test_start_requires_real_operator_provenance_and_selected_phase(sample,missing):
    args=dict(phase="material_reading",reviewer_id="fixture",reviewer_name="SIMULATED",context="Fixture only.")
    args[missing]=None
    with pytest.raises(ValueError,match="operator_provenance_required"):
        c.record(sample[0],sample[1],"start",now=START,**args)
    assert not (sample[1]/"clock").exists()


def test_cannot_start_twice_or_resume_active_clock(sample):
    begin(sample)
    with pytest.raises(ValueError,match="clock_already_started"):begin(sample)
    with pytest.raises(ValueError,match="invalid_resume_transition"):
        c.record(sample[0],sample[1],"resume",now=START+timedelta(seconds=1),phase="owner_review")


def test_no_backdated_clock_or_silent_interval_correction(sample):
    begin(sample)
    c.record(sample[0],sample[1],"pause",now=START+timedelta(seconds=20),reason="interruption")
    before=(sample[1]/"clock/state.json").read_bytes()
    with pytest.raises(ValueError):
        c.record(sample[0],sample[1],"resume",now=START+timedelta(seconds=19),phase="material_reading")
    assert (sample[1]/"clock/state.json").read_bytes()==before


def test_clock_events_have_hash_integrity(sample):
    begin(sample)
    p=next((sample[1]/"clock").glob("*.event.json"))
    p.write_bytes(p.read_bytes()+b" ")
    with pytest.raises(ValueError,match="reference_hash_mismatch"):
        c.status(sample[0],sample[1],now=START+timedelta(seconds=1))


def test_session_backup_is_not_overwritten_by_same_basename_form(sample):
    repo,folder,_,_=sample
    previous_session=(folder/"sessions/case.json").read_bytes()
    previous_form=(folder/"forms/case.json").read_bytes()
    begin(sample)
    archive=next((folder/"clock/history").iterdir())
    assert (archive/"session.json").read_bytes()==previous_session
    assert (archive/"form.json").read_bytes()==previous_form


def test_cannot_resume_a_stopped_session(sample):
    begin(sample)
    c.record(sample[0],sample[1],"stop",now=START+timedelta(seconds=20))
    with pytest.raises(ValueError,match="clock_not_running"):
        c.record(sample[0],sample[1],"resume",now=START+timedelta(seconds=21),phase="material_reading")


def test_second_stop_reports_exact_condition_without_writes(sample, monkeypatch, capsys):
    repo,folder,_,_=sample
    begin(sample)
    c.record(repo,folder,"stop",now=START+timedelta(seconds=20))
    before={p:p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    original=c.record
    # Exercise the CLI error boundary against a temporary fixture, never the pilot.
    monkeypatch.setattr(c,"record",lambda *a, **kw: original(repo,folder,"stop",now=START+timedelta(seconds=21)))
    monkeypatch.setattr(sys,"argv",["clock","--workspace",str(folder),"stop"])
    assert c.main()==2
    assert json.loads(capsys.readouterr().out)["error_code"]=="clock_not_running"
    assert before=={p:p.read_bytes() for p in repo.rglob("*") if p.is_file()}


def test_stop_from_ai_wait_does_not_require_or_invent_owner_review(sample):
    repo,folder,_,_=sample
    begin(sample)
    c.record(repo,folder,"phase",now=START+timedelta(seconds=10),phase="contract_mapping")
    c.record(repo,folder,"pause",now=START+timedelta(seconds=20),reason="ai_wait")
    assert c.record(repo,folder,"stop",now=START+timedelta(seconds=30))["clock"]=="stopped"
    session=json.loads((folder/"sessions/case.json").read_text())
    assert session["pause_seconds"]==10 and session["phase_seconds"]["owner_review"]==0
    assert not any(i["phase"]=="owner_review" for i in session["intervals"])
    form=json.loads((folder/"forms/case.json").read_text())
    assert form["status"]=="in_progress" and form["owner_decision"] is None


@pytest.mark.parametrize("exc,expected",[
    (ValueError("invalid_resume_transition"),"invalid_resume_transition"),
    (ValueError("secret quote /private/path API_KEY"),"unclassified_clock_failure"),
    (ValueError("clock_not_running", "secret"),"unclassified_clock_failure"),
    (OSError("secret filename"),"clock_io_failed"),
    (RuntimeError("secret response"),"unclassified_clock_failure"),
])
def test_cli_error_codes_never_publish_exception_content(exc,expected,monkeypatch,capsys):
    def fail(*a,**kw):
        raise exc
    monkeypatch.setattr(c,"status",fail)
    monkeypatch.setattr(sys,"argv",["clock","--workspace","unused","status"])
    assert c.main()==2
    output=capsys.readouterr()
    assert json.loads(output.out)["error_code"]==expected
    assert "secret" not in output.out and not output.err


def test_schema_errors_expose_no_input_values():
    with pytest.raises(c.ValidationError) as caught:
        c.Reservation.model_validate({"case_id":"secret input"})
    assert c.error_code(caught.value)=="schema_validation_failed"


def test_unknown_phase_times_stay_null_until_observed_session_end(sample):
    begin(sample)
    c.record(sample[0],sample[1],"phase",now=START+timedelta(seconds=20),phase="evidence_check")
    session=json.loads((sample[1]/"sessions/case.json").read_text(encoding="utf-8"))
    assert session["phase_seconds"]["material_reading"]==20
    assert session["phase_seconds"]["owner_review"] is None and session["completed_at"] is None


@pytest.mark.parametrize("key", ["case_id","review_id","disposition_id","factual_sha256","closure_sha256"])
def test_pending_authorization_must_match_reserved_case_and_version(sample,key):
    repo,folder,_,auth=sample
    auth[key]="wrong"
    ref=fx.write(repo,"workspace/opening/auth.json",auth)
    reservation=json.loads((folder/"opening/reservation.json").read_text(encoding="utf-8"))
    reservation["opening_authorization"]=ref.model_dump()
    fx.write(repo,"workspace/opening/reservation.json",reservation)
    with pytest.raises(ValueError,match="reserved_authorization_mismatch"):
        c.status(repo,folder,now=START)


def test_status_and_import_do_not_load_credentials(sample,monkeypatch):
    from investment_system.core import environment
    monkeypatch.setattr(environment,"load_repository_environment",lambda **kw:pytest.fail("No credentials"))
    assert c.status(sample[0],sample[1],now=START)["authorization_valid"]


def test_cli_has_no_backdating_argument_and_errors_are_sanitized(tmp_path):
    script=REPO/"tools/evaluation/pilot_contract_clock.py"
    r=subprocess.run([sys.executable,str(script),"--workspace",str(tmp_path),"start","--at","2020-01-01"],capture_output=True,text=True)
    assert r.returncode!=0
    r=subprocess.run([sys.executable,str(script),"--workspace",str(tmp_path),"status"],capture_output=True,text=True)
    assert r.returncode==2 and json.loads(r.stdout)["error"]=="contract_clock_validation_failed"
