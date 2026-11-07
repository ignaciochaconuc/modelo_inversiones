"""Synthetic metadata fixtures only; never start or judge the six real reviews."""
from copy import deepcopy
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


m = load("contract_review_test_module", REPO/"tools/evaluation/pilot_contract_review.py")
fx = load("contract_disposition_fixtures", REPO/"tests/unit/test_pilot_review_disposition.py")
NOW = fx.NOW


def write(repo, name, value):
    return m.Ref.model_validate(fx.write(repo, name, value))


def make_sample(repo, index=1):
    sample = fx.make_sample(repo, index)
    _, packet, forms, raw = sample
    # A noncanonical fact must survive; fixtures are structural, not evaluation news.
    factual = forms["factual"]
    second = deepcopy(factual["facts"][0])
    second.update(fact_id="F002", dimension="identity", certainty="uncertain", material=False)
    factual["facts"].append(second)
    factual["dimension_assessments"]["identity"]["fact_ids"] = ["F002"]
    raw["annotation"] = fx.write(repo, "factual.json", factual)
    approval = json.loads((repo/"approval.json").read_text(encoding="utf-8"))
    approval["annotation_sha256"] = raw["annotation"]["sha256"]
    raw["content"]["decision"] = fx.write(repo, "approval.json", approval)
    raw, _ = fx.close(sample)
    raw = fx.identify(raw)
    disposition_ref = write(repo, "disposition.json", raw)
    disposition = m.d.Disposition.model_validate(raw)
    files = {}
    for name in m.REFERENCE_FILES:
        path = repo/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Technical fixture, no production import or inference.", encoding="utf-8")
        files[name] = m.d.digest(path)
    reference = write(repo, "technical.json", dict(schema_version="news-pilot-contract-technical-reference-v1",
        contract_version="news-economic-validation-v3", files=files))
    session = m.blank_session(disposition)
    session_ref = write(repo, "contract-session.json", session)
    form = m.blank_form(disposition_ref, disposition, factual, reference, session_ref)
    return dict(repo=repo, packet=packet, disposition=disposition, disposition_ref=disposition_ref,
                form=form, session=session, original=sample)


@pytest.fixture
def sample(tmp_path):
    return make_sample(tmp_path)


def validate(sample, now=NOW):
    return m.validate_form(sample["repo"], m.ContractForm.model_validate(sample["form"]),
        sample["disposition_ref"], sample["disposition"], sample["packet"], now=now)


def start(sample):
    d = sample["disposition"]
    auth = dict(schema_version="news-pilot-contract-opening-authorization-v1", case_id=d.case_id,
        review_id="contract-fixture-"+d.case_id, disposition_id=d.disposition_id, factual_sha256=d.annotation.sha256,
        closure_sha256=d.closure.decision.sha256, explicitly_authorized=True,
        authorized_by=d.content.provenance.approver_identity, decision_source="Synthetic opening, not an actual owner instruction.",
        authorized_at=None, source_message_id=None, inference_authorized=False)
    session = sample["session"]
    session.update(status="in_progress", opening_authorization=write(sample["repo"], "opening.json", auth).model_dump(),
        review_id=auth["review_id"], reviewer_id="fixture-owner", reviewer_name="SIMULATED REVIEWER",
        execution_mode="manual_chatgpt_owner", independence_context="Simulated owner, aware of development.",
        timestamp_source="owner_declared", timestamp_basis="Synthetic clock, not a real measurement.",
        started_at="2026-01-10T11:00:00+00:00")
    sample["form"]["status"] = "in_progress"
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", session).model_dump()
    return auth


def complete(sample):
    start(sample)
    session, form = sample["session"], sample["form"]
    begin = datetime.fromisoformat(session["started_at"])
    intervals = []
    for i, phase in enumerate(m.PHASES):
        intervals.append(dict(kind="active", phase=phase, pause_reason=None,
            started_at=(begin+timedelta(minutes=i)).isoformat(), completed_at=(begin+timedelta(minutes=i+1)).isoformat()))
    session.update(status="completed", completed_at=(begin+timedelta(minutes=5)).isoformat(), intervals=intervals,
        active_seconds=300, pause_seconds=0, phase_seconds={p:60 for p in m.PHASES})
    form.update(status="completed", session=write(sample["repo"], "contract-session.json", session).model_dump(),
        allowed_outcomes=["indeterminate"], rationale="Synthetic technical judgment, no new factual assertion.")
    factual = m.d.legacy_module().Factual.model_validate(form["factual_snapshot"])
    form["mappings"] = [dict(fact_id=f.fact_id, mode="indeterminate", rationale="Unresolved fixture representability.",
        limits_acknowledged=sorted(m.source_limits(f, factual.dimension_assessments[f.dimension]))) for f in factual.facts]
    decision = dict(schema_version="news-pilot-contract-owner-decision-v1", case_id=form["case_id"], review_id=session["review_id"],
        review_fingerprint=m.review_fingerprint(m.ContractForm.model_validate(form)), factual_sha256=sample["disposition"].annotation.sha256,
        explicitly_approved=True, decided_by=sample["disposition"].content.provenance.approver_identity,
        decision_source="Synthetic contract approval, not a real owner statement.", decided_at=None,
        independent_human_review=False, adjudication_claimed=False)
    form["owner_decision"] = write(sample["repo"], "owner-contract-decision.json", decision).model_dump()
    return decision


def test_preparation_retains_all_facts_and_does_not_start_any_session(sample):
    before = {p:m.d.digest(p) for p in sample["repo"].rglob("*") if p.is_file()}
    result = validate(sample)
    assert result["status"] == "unfilled" and result["review_id"] is None
    assert result["facts_retained"] == 2 and result["mappings_recorded"] == 0
    assert result["historical_factual_status"] == "in_progress"
    assert before == {p:m.d.digest(p) for p in sample["repo"].rglob("*") if p.is_file()}


@pytest.mark.parametrize("field", ["closed_disposition", "closure_decision", "factual", "technical_reference", "session"])
def test_wrong_source_hash_is_rejected(sample, field):
    sample["form"][field]["sha256"] = "b"*64
    with pytest.raises(ValueError):validate(sample)


def test_open_disposition_is_rejected_even_for_empty_contract(sample):
    d = sample["disposition"].model_copy(update={"closure":m.d.Closure(status="open", decision=None)})
    with pytest.raises(ValueError, match="closed_untimed_disposition_required"):
        m.validate_form(sample["repo"], m.ContractForm.model_validate(sample["form"]),
            sample["disposition_ref"], d, sample["packet"], now=NOW)


@pytest.mark.parametrize("mutation", ["meaning", "quote", "certainty", "dimension_uncertainty", "must_only", "material", "offset", "boolean_as_number", "offset_as_float"])
def test_factual_content_evidence_or_uncertainty_cannot_be_rewritten(sample, mutation):
    snapshot = sample["form"]["factual_snapshot"]
    if mutation == "meaning": snapshot["facts"][0]["meaning"] = "Invented certainty"
    if mutation == "quote": snapshot["facts"][0]["citations"][0]["quote"] = "Invented quote"
    if mutation == "certainty": snapshot["facts"][1]["certainty"] = "conclusive"
    if mutation == "dimension_uncertainty": snapshot["dimension_assessments"]["identity"]["status"] = "recorded"
    if mutation == "must_only": snapshot["facts"] = snapshot["facts"][:1]
    if mutation == "material": snapshot["facts"][0]["material"] = False
    if mutation == "offset": snapshot["facts"][0]["citations"][0]["start"] += 1
    if mutation == "boolean_as_number": snapshot["facts"][0]["material"] = 1
    if mutation == "offset_as_float": snapshot["facts"][0]["citations"][0]["start"] = 0.0
    with pytest.raises(ValueError, match="factual_snapshot_changed"):validate(sample)


def test_annotations_require_a_separate_opening_and_new_session(sample):
    sample["form"]["status"] = "in_progress"
    with pytest.raises(ValueError, match="contract_requires_new_session"):validate(sample)
    sample["session"]["status"] = "in_progress"
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", sample["session"]).model_dump()
    with pytest.raises(ValueError, match="separate_opening_authorization_required"):validate(sample)


def test_no_authorization_to_open_follows_from_implementation_or_factual_closure(sample):
    start(sample)
    session = sample["session"]
    session["opening_authorization"] = sample["original"][3]["methodology_authorization"]
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", session).model_dump()
    with pytest.raises(ValueError):validate(sample)


@pytest.mark.parametrize("field", ["case_id", "review_id", "disposition_id", "factual_sha256", "closure_sha256", "authorized_by"])
def test_opening_authorization_is_specific_to_this_review(sample, field):
    auth = start(sample)
    auth[field] = "wrong-fixture"
    sample["session"]["opening_authorization"] = write(sample["repo"], "opening.json", auth).model_dump()
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", sample["session"]).model_dump()
    with pytest.raises(ValueError, match="opening_authorization_binding_mismatch"):validate(sample)


def test_numeric_boolean_is_not_an_explicit_authorization(sample):
    auth = start(sample)
    auth["explicitly_authorized"] = 1
    sample["session"]["opening_authorization"] = write(sample["repo"], "opening.json", auth).model_dump()
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", sample["session"]).model_dump()
    with pytest.raises(ValueError, match="explicit_boolean_required"):validate(sample)


@pytest.mark.parametrize("field", ["reviewer_id", "reviewer_name", "timestamp_source", "timestamp_basis", "independence_context", "started_at"])
def test_incomplete_active_provenance_cannot_be_filled_implicitly(sample, field):
    start(sample)
    sample["session"][field] = None
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", sample["session"]).model_dump()
    with pytest.raises(ValueError, match="new_session_provenance_required"):validate(sample)


def test_unknown_model_label_stays_null_in_manual_chatgpt_session(sample):
    start(sample)
    assert validate(sample)["status"] == "in_progress"
    assert sample["session"]["visible_model_label"] is None
    assert sample["session"]["model_snapshot"] is None


@pytest.mark.parametrize("field", ["factual_closed_at", "adjudication_seconds", "old_factual_reading_seconds"])
def test_old_factual_clock_and_adjudications_do_not_fit_the_new_session(sample, field):
    sample["session"][field] = 20
    with pytest.raises(ValueError):m.ContractSession.model_validate(sample["session"])


def test_representation_cannot_drop_uncertainty_qualifiers(sample):
    start(sample)
    sample["form"]["mappings"] = [dict(fact_id="F002", mode="structured", rationale="Fixture only.", limits_acknowledged=[])]
    with pytest.raises(ValueError, match="source_uncertainty_not_preserved"):validate(sample)
    sample["form"]["mappings"][0]["limits_acknowledged"] = ["uncertain_fact", "indeterminate_dimension"]
    assert validate(sample)["mappings_recorded"] == 1


def test_mapping_cannot_add_a_new_claim_or_certainty_field(sample):
    raw = dict(fact_id="F001", mode="structured", rationale="Fixture.", limits_acknowledged=[], certainty="conclusive")
    with pytest.raises(ValueError):m.ContractMapping.model_validate(raw)


def test_complete_review_covers_noncanonical_facts_and_needs_owner_decision(sample):
    complete(sample)
    assert validate(sample)["status"] == "completed"
    sample["form"]["mappings"] = sample["form"]["mappings"][:1]
    with pytest.raises(ValueError, match="all_facts_contractual_review_required"):validate(sample)


@pytest.mark.parametrize("mutation", ["no_decision", "wrong_fingerprint", "wrong_actor", "wrong_fact_hash"])
def test_owner_decision_cannot_be_inferred_from_a_complete_session(sample, mutation):
    decision = complete(sample)
    if mutation == "no_decision": sample["form"]["owner_decision"] = None
    else:
        decision[{"wrong_fingerprint":"review_fingerprint", "wrong_actor":"decided_by", "wrong_fact_hash":"factual_sha256"}[mutation]] = "wrong"
        sample["form"]["owner_decision"] = write(sample["repo"], "owner-contract-decision.json", decision).model_dump()
    with pytest.raises(ValueError):validate(sample)


@pytest.mark.parametrize("mutation", ["gap", "overlap", "sum", "negative", "no_zone", "future", "fake_phase"])
def test_new_session_requires_a_coherent_real_timeline(sample, mutation):
    complete(sample)
    session = sample["session"]
    if mutation == "gap": session["intervals"][0]["started_at"] = "2026-01-10T11:00:01Z"
    if mutation == "overlap": session["intervals"].append(session["intervals"][0])
    if mutation == "sum": session["active_seconds"] = 20
    if mutation == "negative": session["phase_seconds"]["owner_review"] = -1
    if mutation == "no_zone": session["started_at"] = "2026-01-10T11:00:00"
    if mutation == "future": session["started_at"] = "2099-01-10T11:00:00Z"
    if mutation == "fake_phase": session["intervals"][0]["phase"] = "factual_annotation"
    sample["form"]["session"] = write(sample["repo"], "contract-session.json", session).model_dump()
    with pytest.raises(ValueError):validate(sample)


def test_completed_clock_does_not_renew_ttl_from_adapter_or_owner_approval(sample):
    complete(sample)
    end = datetime.fromisoformat(sample["session"]["completed_at"])
    assert validate(sample, now=end+timedelta(days=90)-timedelta(microseconds=1))
    with pytest.raises(ValueError, match="contract_session_metadata_expired"):
        validate(sample, now=end+timedelta(days=90))


def test_historical_contract_validator_still_blocks_untimed_factual(sample):
    complete(sample)
    disposition = sample["disposition"]
    legacy = m.d.legacy_module()
    factual = legacy.Factual.model_validate(m.d.read_ref(sample["repo"], disposition.annotation))
    raw = legacy.templates(sample["packet"])["contract"]
    raw["factual_record_sha256"] = disposition.annotation.sha256
    with pytest.raises(ValueError, match="factual_must_close_before_contract"):
        legacy.validate_contract(legacy.Contract.model_validate(raw), factual, disposition.annotation.sha256)


def test_technical_reference_cannot_mix_versions_or_modified_sources(sample):
    ref = sample["form"]["technical_reference"]
    path = sample["repo"]/next(iter(m.REFERENCE_FILES))
    path.write_text("Modified fixture contract.", encoding="utf-8")
    with pytest.raises(ValueError, match="reference_hash_mismatch"):validate(sample)


def test_import_and_validation_do_not_bootstrap_credentials(sample, monkeypatch):
    from investment_system.core import environment
    monkeypatch.setattr(environment, "load_repository_environment", lambda **kw:pytest.fail("No credential loading"))
    load("fresh_contract_review_import", REPO/"tools/evaluation/pilot_contract_review.py")
    assert validate(sample)["status"] == "unfilled"


def test_explicit_cli_selection_and_sanitized_errors(tmp_path):
    script = REPO/"tools/evaluation/pilot_contract_review.py"
    r = subprocess.run([sys.executable,str(script)],capture_output=True,text=True)
    assert r.returncode != 0 and "--validate" in r.stderr
    sentinel = "SENSITIVE-UNKNOWN-TEXT"
    (tmp_path/"manifest.json").write_text(sentinel, encoding="utf-8")
    r = subprocess.run([sys.executable,str(script),"--validate",str(tmp_path)],capture_output=True,text=True)
    assert r.returncode == 2 and sentinel not in r.stdout+r.stderr
    assert json.loads(r.stdout)["error"] == "pilot_contract_adapter_validation_failed"


@pytest.fixture
def batch(tmp_path, monkeypatch):
    packets, selected, form_refs = {}, [], []
    reference = None

    def prefix_refs(value, prefix):
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                return dict(path=prefix+"/"+value["path"], sha256=value["sha256"])
            return {k:prefix_refs(v, prefix) for k,v in value.items()}
        if isinstance(value, list):
            return [prefix_refs(v, prefix) for v in value]
        return value

    for i in range(1, 7):
        root = tmp_path/("fixture-"+str(i))
        root.mkdir()
        s = make_sample(root, i)
        packets[s["packet"]["case_id"]] = s["packet"]
        # Test only the aggregate boundary here; per-record tests above exercise full chains.
        raw = prefix_refs(s["disposition"].model_dump(mode="json"), root.name)
        dr = write(tmp_path, "selected/"+raw["case_id"]+".json", raw)
        selected.append(dr.model_dump())
        f = prefix_refs(s["form"], root.name)
        f["closed_disposition"] = dr.model_dump()
        # Each reference file is rebased while retaining its pinned fixture bytes.
        tr = json.loads((root/"technical.json").read_text(encoding="utf-8"))
        tr["files"] = {root.name+"/"+k:v for k,v in tr["files"].items()}
        reference = reference or write(tmp_path, "batch-technical.json", tr)
        f["technical_reference"] = reference.model_dump()
        form_refs.append(write(tmp_path, "forms/"+raw["case_id"]+".json", f).model_dump())
    source_path = m.CURRENT_DISPOSITION_MANIFEST
    source = write(tmp_path, source_path, dict(schema_version="news-pilot-review-disposition-manifest-v1",
        policy=selected[0], source_inventory=selected[0], records=selected))
    manifest = dict(schema_version="news-pilot-contract-adapter-manifest-v1", disposition_manifest=source.model_dump(),
        technical_reference=reference.model_dump(), forms=form_refs)
    write(tmp_path,"prepared/manifest.json",manifest)
    monkeypatch.setattr(m.d,"verify",lambda repo,folder,now:dict(factual_closed=6))
    monkeypatch.setattr(m.d.legacy_module(),"verify_packages",lambda repo:packets)
    # Full per-record validation has separate tests, independent of batch plumbing.
    monkeypatch.setattr(m,"validate_reference",lambda repo,ref:m.d.bound_path(repo,ref))
    def record(repo, form, selected_ref, disposition, packet, *, now):
        m.d.require(form.closed_disposition == selected_ref, "stale_contractual_source_binding")
        return dict(case_id=form.case_id,status=form.status,review_id=None)
    monkeypatch.setattr(m,"validate_form",record)
    return tmp_path,tmp_path/"prepared",manifest


def test_aggregate_reports_prepared_and_not_started_and_cannot_claim_completion(batch):
    repo, folder, _ = batch
    result=m.verify(repo,folder,now=NOW)
    assert result["prepared_not_started"] == 6 and result["started"] == result["completed"] == 0
    assert result["provider_calls"] == result["inferences"] == 0
    assert not result["factual_timing_rehabilitated"] and not result["integral_pilot_completed"]
    with pytest.raises(ValueError,match="contract_review_not_completed"):
        m.verify(repo,folder,now=NOW,require_completed=True)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "stale_manifest", "history_selection"])
def test_aggregate_rejects_missing_duplicate_or_stale_source_links(batch, mutation):
    repo, folder, manifest = batch
    if mutation == "missing":manifest["forms"].pop()
    if mutation == "duplicate":manifest["forms"][1]=manifest["forms"][0]
    if mutation == "stale_manifest":manifest["disposition_manifest"]["sha256"]="f"*64
    if mutation == "history_selection":manifest["disposition_manifest"]["path"]="history/manifest.json"
    write(repo,"prepared/manifest.json",manifest)
    with pytest.raises(ValueError):m.verify(repo,folder,now=NOW)


def test_aggregate_rejects_one_unclosed_factual_case(batch,monkeypatch):
    repo,folder,_=batch
    monkeypatch.setattr(m.d,"verify",lambda repo,folder,now:dict(factual_closed=5))
    with pytest.raises(ValueError,match="six_factual_closures_required"):
        m.verify(repo,folder,now=NOW)
