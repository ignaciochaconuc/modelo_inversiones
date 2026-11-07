"""Offline metadata fixtures, not new evaluation cases or reviewer judgments."""
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


m = load("disposition_tests_module", REPO / "tools/evaluation/pilot_review_disposition.py")
fixtures = load("disposition_legacy_test_fixtures", REPO / "tests/unit/test_development_pilot_review.py")
NOW = datetime(2026, 1, 11, tzinfo=timezone.utc)


def write(repo, name, value):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dict(path=name, sha256=m.digest(path))


def identify(value):
    # Hash the canonical typed representation, including nulls and numeric types.
    value["disposition_id"] = "0" * 64
    value = m.Disposition.model_validate(value).model_dump(mode="json")
    value["disposition_id"] = m.identity(value)
    return value


def make_sample(tmp_path, index=1):
    packet = fixtures.sample_packet(index)
    forms = fixtures.completed_fixture(packet)
    forms["factual"]["status"] = "in_progress"
    forms["factual"]["facts"][0]["material"] = True
    forms["factual"]["must_not_omit"] = ["F001"]
    annotation = write(tmp_path, "factual.json", forms["factual"])
    p = tmp_path / m.PROPOSAL_PATH
    p.parent.mkdir(parents=True)
    p.write_bytes((REPO / m.PROPOSAL_PATH).read_bytes())
    auth = dict(schema_version="news-pilot-methodology-authorization-v1", policy_version=m.POLICY,
        proposal=dict(path=m.PROPOSAL_PATH, sha256=m.PROPOSAL_SHA256), approved=True,
        authorized_by="SIMULATED OWNER", decision_source="Synthetic authorization fixture, not an actual decision.",
        owner_statement="Fixture only.", source_message_id=None, authorized_at=None,
        scope="development_pilot_dispositions_only", case_closures_authorized_by_this_record=False,
        contractual_adapter_authorized=False, inference_authorized=False)
    approval = dict(version=m.APPROVAL_VERSION, record_kind="documentary_owner_decision_not_protocol_completion",
        decision="approved_complete_factual_content_v1", scope="development_pilot_factual_content_only",
        case_id=packet["case_id"], packet_fingerprint=packet["packet_fingerprint"], annotation_version="fixture-v1",
        annotation_sha256=annotation["sha256"], full_content_approval=True,
        approver_identity="SIMULATED OWNER", decision_source="Synthetic content decision, not an actual review.",
        annotation_origin="chatgpt_assisted_exploratory_review", independent_human_review=False,
        adjudication_claimed=False, approval_timestamp=None)
    content_ref = write(tmp_path, "approval.json", approval)
    timing_ref = write(tmp_path, "timing-original.json", fixtures.m.templates(packet)["timing"])
    d = dict(schema_version=m.VERSION, disposition_id="0"*64, case_id=packet["case_id"],
        packet_fingerprint=packet["packet_fingerprint"], annotation=annotation, annotation_version="fixture-v1",
        annotation_schema="news-pilot-factual-form-v1", legacy_factual_status="in_progress",
        methodology_authorization=write(tmp_path, "authorization.json", auth),
        content=dict(status="owner_approved_content", decision=content_ref,
            provenance={k: approval[k] for k in m.Provenance.model_fields}),
        closure=dict(status="open", decision=None), timing=dict(status="unknown", original_form=timing_ref,
            reading=None, measurement=None, measured_scope=[]),
        effort=dict(status="excluded", scope=[], reason="No observed clock or intervals.", attestation=None), supersedes=None)
    return tmp_path, packet, forms, identify(d)


@pytest.fixture
def sample(tmp_path):
    return make_sample(tmp_path)


def validate(sample, value=None, now=NOW):
    repo, packet, _, d = sample
    return m.validate_record(repo, m.Disposition.model_validate(identify(value or d)), packet, now=now)


def close(sample, mode="closed_content_only_untimed"):
    repo, packet, _, d = sample
    decision = dict(schema_version="news-pilot-factual-closure-decision-v1", policy_version=m.POLICY,
        case_id=packet["case_id"], packet_fingerprint=packet["packet_fingerprint"],
        annotation_sha256=d["annotation"]["sha256"], approval_sha256=d["content"]["decision"]["sha256"],
        authorization_sha256=d["methodology_authorization"]["sha256"], mode=mode,
        explicitly_approved=True, decided_by="SIMULATED OWNER", decision_source="Separate synthetic closure decision.",
        decided_at=None, factual_evidence_reviewed=True, uncertainty_preserved=True,
        unresolved_semantic_changes=False, material_coverage={"F001":dict(canonical_ids=["F001"], rationale="Fixture obligation.")})
    d["closure"] = dict(status=mode, decision=write(repo, "closure.json", decision))
    return d, decision


def measured(sample, *, complete=False):
    repo, packet, forms, d = sample
    t = deepcopy(forms["timing"])
    if not complete:
        t.update(status="in_progress", completed_at=t["intervals"][0]["completed_at"], factual_closed_at=None,
                 intervals=t["intervals"][:1], active_seconds=60, pause_seconds=0,
                 phase_seconds={p: 60 if p == "reading" else None for p in fixtures.m.PHASES})
    d["timing"].update(status="valid_complete_measurement" if complete else "valid_measured_scope",
        measurement=write(repo, "measurement.json", t), measured_scope=list(fixtures.m.PHASES) if complete else ["reading"])
    return d, t


def eligible(sample):
    repo, packet, _, _ = sample
    d, t = measured(sample)
    a = dict(schema_version="news-pilot-effort-attestation-v1", case_id=packet["case_id"],
        measurement_sha256=d["timing"]["measurement"]["sha256"], review_id=t["review_id"], reviewer_id=t["reviewer_id"],
        scope=["reading"], clock_evidence=write(repo, "clock.json", {"fixture": "Synthetic clock evidence only"}),
        quality_reviewed_by="SIMULATED OWNER", decision_source="Fixture quality check.", population="Owner familiar with this test-only task.",
        familiarity="Prior exposure declared.", assistance="Manual test fixture, no API.", human_time_separated_from_ai_and_waits=True)
    d["effort"].update(status="eligible_for_named_scope", scope=["reading"], reason="Observed fixture reading only.",
        attestation=write(repo, "effort.json", a))
    return d


def test_content_approval_neither_closes_nor_measures(sample):
    result = validate(sample)
    assert result["content"] == "owner_approved_content" and result["closure"] == "open"
    assert result["timing"] == "unknown" and result["effort"] == "excluded"
    assert result["semantic_truth"] == "not_assessed" and result["contractual_adapter"] == "not_implemented"
    assert (sample[0]/"closure.json").exists() is False


@pytest.mark.parametrize("kind", ["annotation", "approval", "timing-original", "authorization"])
def test_tampered_sources_are_rejected(sample, kind):
    names = {"annotation": "factual", "approval":"approval", "timing-original":"timing-original", "authorization":"authorization"}
    path = sample[0]/(names[kind]+".json")
    path.write_bytes(path.read_bytes()+b" ")
    with pytest.raises(ValueError, match="reference_hash_mismatch"):
        validate(sample)


@pytest.mark.parametrize("field", ["case_id", "packet_fingerprint", "annotation_version", "legacy_factual_status"])
def test_wrong_identity_or_version_rejected(sample, field):
    d = sample[3]
    d[field] = "b"*64 if field == "packet_fingerprint" else ("completed" if field == "legacy_factual_status" else "wrong")
    with pytest.raises(ValueError, match="binding_mismatch"):
        validate(sample)


def test_identity_is_not_repaired_by_validator(sample):
    d = m.Disposition.model_validate(sample[3]).model_copy(update={"disposition_id":"b"*64})
    with pytest.raises(ValueError, match="disposition_identity_mismatch"):
        m.validate_record(sample[0], d, sample[1], now=NOW)


@pytest.mark.parametrize("field", ["approval_timestamp", "approver_identity", "decision_source"])
def test_missing_provenance_is_not_filled_in(sample, field):
    del sample[3]["content"]["provenance"][field]
    with pytest.raises(ValueError):
        validate(sample)


def test_provenance_cannot_claim_independence_or_invent_time(sample):
    d = sample[3]
    d["content"]["provenance"]["approval_timestamp"] = "2026-01-10T00:00:00Z"
    with pytest.raises(ValueError, match="provenance_mismatch"):
        validate(sample)
    d["content"]["provenance"]["approval_timestamp"] = None
    d["content"]["provenance"]["independent_human_review"] = True
    with pytest.raises(ValueError):
        validate(sample)


@pytest.mark.parametrize("state", ["closed_content_only_untimed", "closed_under_legacy_protocol"])
def test_closure_requires_new_separate_explicit_decision(sample, state):
    sample[3]["closure"] = dict(status=state, decision=None)
    with pytest.raises(ValueError, match="separate_closure_decision_required"):
        validate(sample)
    sample[3]["closure"]["decision"] = sample[3]["content"]["decision"]
    with pytest.raises(ValueError, match="separate_closure_decision_required"):
        validate(sample)


def test_valid_untimed_closure_preserves_uncertainty_and_historical_state(sample):
    d, _ = close(sample)
    before = (sample[0]/"factual.json").read_bytes()
    assert validate(sample, d)["closure"] == "closed_content_only_untimed"
    assert (sample[0]/"factual.json").read_bytes() == before
    assert json.loads(before)["status"] == "in_progress"
    with pytest.raises(ValueError, match="factual_must_close_before_contract"):
        fixtures.m.validate_contract(fixtures.m.Contract.model_validate(sample[2]["contract"]),
            fixtures.m.Factual.model_validate(sample[2]["factual"]), d["annotation"]["sha256"])


@pytest.mark.parametrize("change", ["wrong_hash", "wrong_actor", "missing_coverage", "wrong_canonical", "not_explicit", "future_time"])
def test_fictitious_or_incomplete_closure_rejected(sample, change):
    d, c = close(sample)
    if change == "wrong_hash": c["annotation_sha256"] = "c"*64
    if change == "wrong_actor": c["decided_by"] = "ANOTHER FIXTURE"
    if change == "missing_coverage": c["material_coverage"] = {}
    if change == "wrong_canonical": c["material_coverage"]["F001"]["canonical_ids"] = ["F999"]
    if change == "not_explicit": c["explicitly_approved"] = False
    if change == "future_time": c["decided_at"] = "2099-01-01T00:00:00Z"
    d["closure"]["decision"] = write(sample[0], "closure.json", c)
    with pytest.raises(ValueError):
        validate(sample, d)


def test_legacy_closure_cannot_be_manufactured_from_untimed_content(sample):
    d, _ = close(sample, mode="closed_under_legacy_protocol")
    with pytest.raises(ValueError, match="legacy_closure_requires_real_timing"):
        validate(sample, d)


def test_estimate_and_partial_declaration_are_preserved_and_excluded(sample):
    repo, _, _, d = sample
    a = json.loads((repo/"approval.json").read_text(encoding="utf-8"))
    for reading in [dict(value=1, unit="minute", approximate=True, source="owner_estimate", exact_measurement=False),
                    dict(value=20, unit="seconds", source="owner_declaration", measurement_method=None,
                         stopwatch_used=None, is_estimate=None, independently_verified=False)]:
        a.pop("reading_estimate", None)
        a["reading_duration_declaration"] = reading
        d["content"]["decision"] = write(repo, "approval.json", a)
        d["timing"].update(reading=reading, status="estimate_only" if reading["source"] == "owner_estimate" else "declared_duration_unvalidated")
        assert validate(sample, d)["effort"] == "excluded"
        d["effort"].update(status="eligible_for_named_scope", scope=["reading"])
        with pytest.raises(ValueError, match="invalid_effort_eligibility"):
            validate(sample, d)
        d["effort"].update(status="excluded", scope=[])


def test_real_scope_requires_intervals_and_evidence_of_human_effort(sample):
    d = eligible(sample)
    assert validate(sample, d)["effort"] == "eligible_for_named_scope"
    d["effort"]["scope"] = ["factual_annotation"]
    with pytest.raises(ValueError, match="invalid_effort_eligibility"):
        validate(sample, d)


def test_scope_does_not_become_complete_measurement(sample):
    d, _ = measured(sample)
    d["timing"]["status"] = "valid_complete_measurement"
    with pytest.raises(ValueError, match="incomplete_measurement"):
        validate(sample, d)


def test_complete_measurement_is_not_automatically_effort_eligible(sample):
    d, _ = measured(sample, complete=True)
    assert validate(sample, d)["timing"] == "valid_complete_measurement"
    assert validate(sample, d)["effort"] == "excluded"


@pytest.mark.parametrize("mutation", ["gap", "overlap", "sum", "negative", "no_zone", "no_end"])
def test_invalid_clock_data_rejected(sample, mutation):
    d, t = measured(sample)
    if mutation == "gap": t["intervals"][0]["started_at"] = "2026-01-10T10:00:01+00:00"
    if mutation == "overlap": t["intervals"].append(t["intervals"][0])
    if mutation == "sum": t["active_seconds"] = 999
    if mutation == "negative": t["phase_seconds"]["reading"] = -1
    if mutation == "no_zone": t["started_at"] = "2026-01-10T10:00:00"
    if mutation == "no_end": t["completed_at"] = None
    d["timing"]["measurement"] = write(sample[0], "measurement.json", t)
    with pytest.raises(ValueError):
        validate(sample, d)


def test_ttl_boundary_not_reset_by_new_disposition(sample):
    d, t = measured(sample)
    end = datetime.fromisoformat(t["completed_at"])
    assert validate(sample, d, now=end+timedelta(days=90)-timedelta(microseconds=1))
    with pytest.raises(ValueError, match="timing_metadata_expired"):
        validate(sample, d, now=end+timedelta(days=90))


def test_scope_cannot_include_an_unobserved_zero_duration_task(sample):
    d, t = measured(sample)
    t["phase_seconds"]["factual_annotation"] = 0
    d["timing"]["measured_scope"].append("factual_annotation")
    d["timing"]["measurement"] = write(sample[0], "measurement.json", t)
    with pytest.raises(ValueError, match="unobserved_measurement_scope"):
        validate(sample, d)


def test_supersession_checks_entire_chain(sample):
    repo, _, _, d = sample
    original = identify(d)
    previous = write(repo, "previous.json", original)
    newer = deepcopy(d)
    newer["supersedes"] = previous
    assert validate(sample, newer)
    (repo/"previous.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="reference_hash_mismatch"):
        validate(sample, newer)


def test_supersession_cannot_silently_reopen_closed_same_content(sample):
    d, _ = close(sample)
    previous = write(sample[0], "closed-previous.json", identify(d))
    d["supersedes"] = previous
    d["closure"] = dict(status="open", decision=None)
    with pytest.raises(ValueError, match="closure_cannot_silently_reopen"):
        validate(sample, d)


@pytest.mark.parametrize("path", ["../secret.json", "C:/secret.json", "C:secret.json", "/secret.json", "https://example.com", "file.json:stream"])
def test_reference_path_cannot_escape_repository(tmp_path, path):
    with pytest.raises(ValueError):
        m.path_for(tmp_path, path)


def test_cli_requires_explicit_selection_and_sanitizes_errors(tmp_path):
    script = REPO/"tools/evaluation/pilot_review_disposition.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert r.returncode != 0 and "--validate" in r.stderr
    sentinel = "PRIVATE-SENTINEL-NOT-FOR-REPORTS"
    folder = tmp_path/sentinel
    folder.mkdir()
    (folder/"manifest.json").write_text(sentinel, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), "--validate", str(folder)], capture_output=True, text=True)
    assert r.returncode == 2 and sentinel not in r.stdout+r.stderr
    assert json.loads(r.stdout)["error"] == "pilot_disposition_validation_failed"


def test_import_does_not_read_artifacts_credentials_or_call_network(monkeypatch):
    # The normal test fixtures already forbid network/DNS.
    from investment_system.core import environment
    monkeypatch.setattr(environment, "load_repository_environment",
                        lambda *a, **k: pytest.fail("credentials must not be loaded"))
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("import must not read review data"))
    load("fresh_disposition_import", REPO/"tools/evaluation/pilot_review_disposition.py")


@pytest.mark.parametrize("mutation,code", [("offset", "exact_unicode_citation_mismatch"),
    ("evidence", "wrong_evidence_binding"), ("dimension", "closure_unassessed_dimension")])
def test_closure_cannot_bypass_original_factual_checks(sample, mutation, code):
    repo, _, forms, d = sample
    f = deepcopy(forms["factual"])
    if mutation == "offset": f["facts"][0]["citations"][0]["start"] = 1
    if mutation == "evidence": f["facts"][0]["citations"][0]["evidence_id"] = "f"*64
    if mutation == "dimension": f["dimension_assessments"]["role"] = dict(status=None, fact_ids=[], note=None)
    d["annotation"] = write(repo, "factual.json", f)
    a = json.loads((repo/"approval.json").read_text(encoding="utf-8"))
    a["annotation_sha256"] = d["annotation"]["sha256"]
    d["content"]["decision"] = write(repo, "approval.json", a)
    d, _ = close(sample)
    with pytest.raises(ValueError, match=code):
        validate(sample, d)


def test_legacy_factual_closure_can_validate_without_completed_contract(sample):
    repo, _, forms, d = sample
    forms["factual"]["status"] = "completed"
    d["annotation"] = write(repo, "factual.json", forms["factual"])
    a = json.loads((repo/"approval.json").read_text(encoding="utf-8"))
    a["annotation_sha256"] = d["annotation"]["sha256"]
    d["content"]["decision"] = write(repo, "approval.json", a)
    d["legacy_factual_status"] = "completed"
    t = deepcopy(forms["timing"])
    t.update(status="in_progress", intervals=t["intervals"][:3], completed_at=t["intervals"][2]["completed_at"],
        active_seconds=180, pause_seconds=0,
        phase_seconds={p:60 if p in {"reading", "factual_annotation", "citation_check"} else None for p in fixtures.m.PHASES})
    d["timing"].update(status="valid_measured_scope", measurement=write(repo, "measurement.json", t),
        measured_scope=["reading", "factual_annotation", "citation_check"])
    d, _ = close(sample, mode="closed_under_legacy_protocol")
    assert validate(sample, d)["closure"] == "closed_under_legacy_protocol"
    assert validate(sample, d)["effort"] == "excluded"


@pytest.fixture
def batch(tmp_path, monkeypatch):
    packets, refs, rows = {}, [], []
    folder_name = "dispositions"
    policy = None
    for i in range(1, 7):
        root = tmp_path / ("fixture-"+str(i))
        root.mkdir()
        _, packet, _, d = make_sample(root, i)
        packets[packet["case_id"]] = packet
        # References remain repository-relative, while annotation/approval bytes stay untouched.
        for ref in [d["annotation"], d["content"]["decision"], d["timing"]["original_form"], d["methodology_authorization"]]:
            ref["path"] = root.name+"/"+ref["path"]
        policy = policy or d["methodology_authorization"]
        d["methodology_authorization"] = policy
        refs.append(write(tmp_path, folder_name+"/"+d["case_id"]+".json", identify(d)))
        rows.append(dict(case_id=d["case_id"], annotation_path=d["annotation"]["path"], annotation_sha256=d["annotation"]["sha256"],
            approval_path=d["content"]["decision"]["path"], approval_sha256=d["content"]["decision"]["sha256"],
            timing_sha256=d["timing"]["original_form"]["sha256"]))
    p = tmp_path/m.PROPOSAL_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((REPO/m.PROPOSAL_PATH).read_bytes())
    inv = write(tmp_path, m.INVENTORY_PATH, dict(cases=rows))
    monkeypatch.setattr(m, "INVENTORY_SHA256", inv["sha256"])
    monkeypatch.setattr(m.legacy_module(), "verify_packages", lambda repo: packets)
    manifest = dict(schema_version="news-pilot-review-disposition-manifest-v1", policy=policy, source_inventory=inv, records=refs)
    write(tmp_path, folder_name+"/manifest.json", manifest)
    return tmp_path, tmp_path/folder_name, manifest


def test_six_approvals_remain_open_and_excluded_without_any_writes(batch):
    repo, folder, _ = batch
    before = {p: m.digest(p) for p in repo.rglob("*") if p.is_file()}
    result = m.verify(repo, folder, now=NOW)
    assert result["content_approved"] == 6 and result["factual_closed"] == 0
    assert result["eligible_measured_attempts"] == 0 and result["integral_pilot_completed"] is False
    assert result["provider_calls"] == result["predictions"] == 0
    assert before == {p: m.digest(p) for p in repo.rglob("*") if p.is_file()}


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "extra", "historical_source", "promoted_timing"])
def test_batch_rejects_inventory_or_historical_changes(batch, mutation):
    repo, folder, manifest = batch
    if mutation == "duplicate": manifest["records"][1] = manifest["records"][0]
    if mutation == "missing": manifest["records"].pop()
    if mutation == "extra": (folder/"extra.json").write_text("{}")
    if mutation in {"historical_source", "promoted_timing"}:
        ref = manifest["records"][0]
        d = json.loads((repo/ref["path"]).read_text(encoding="utf-8"))
        if mutation == "historical_source": d["annotation"]["sha256"] = "b"*64
        if mutation == "promoted_timing": d["effort"]["status"] = "eligible_for_named_scope"
        manifest["records"][0] = write(repo, ref["path"], identify(d))
    write(repo, folder.relative_to(repo).as_posix()+"/manifest.json", manifest)
    with pytest.raises(ValueError):
        m.verify(repo, folder, now=NOW)
