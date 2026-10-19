"""New workshop data only; no prompts, old references or real response content."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("semantic_workshop_test", ROOT/"tools/evaluation/semantic_review_workshop.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
FIXTURES = ROOT/"evaluation/phase4c2_semantic_review_workshop_v1/examples.json"
AT = datetime(2026, 1, 12, 12, tzinfo=timezone.utc)


@pytest.fixture
def completed(tmp_path):
    result = w.run_workshop(FIXTURES, tmp_path, at=AT)
    return tmp_path, result


def test_complete_offline_flow_and_family_weighting(completed):
    root, result = completed
    report = result["summary"]
    assert len(report["cases"]) == 16 and report["eligible_families"] == 4
    assert report["delta_lower"] == report["delta_upper"] == "3/8"
    assert report["adoption"] == "not_assessed_workshop" and report["provider_calls"] == 0
    assert result["factual_disagreements"] == result["output_disagreements"] == 1
    assert all(not r["eligible"] for r in report["cases"] if r["case_id"] == "W-07")
    assert all(r["f_case"] == 0 for r in report["cases"] if r["case_id"] == "W-08")
    assert any(r["critical"] == ["false_completion"] for r in report["cases"])
    assert report["dimensions"]["v3"]["material_omissions"]["omitted"] == 1
    assert report["dimensions"]["v4"]["participation"]["unsupported"] == 1
    # This is a workshop freeze, not the reserved 96-case set.
    seal = w.load_freeze(root/"workshop-references.json", result["reference_sha256"])
    assert seal["body"]["kind"] == "simulated_development_reference_freeze"
    case = next(r for r in seal["body"]["records"] if r["source"]["case_id"] == "W-04")
    assert "7,5m" in case["source"]["headline"]
    assert any(m["mode"] == "faithful_partial_only" for m in case["contract"]["mappings"])
    assert any("7,5m" in f["meaning"] for f in case["final"]["facts"])
    for name in ("workshop-review-metadata.json", "workshop-adjudication-chain.json", "workshop-summary.json"):
        text = (root/name).read_text(encoding="utf-8")
        assert "response_text" not in text and "The purchase has closed" not in text
        assert "Neravelle" not in text and "7,5m" not in text


def material(root, result):
    seal = w.load_freeze(root/"workshop-references.json", result["reference_sha256"])
    chain = json.loads((root/"workshop-adjudication-chain.json").read_text())
    values = json.loads((root/"workshop-review-metadata.json").read_text())
    judgments = {r["blind_id"]: w.Judgment.model_validate(r) for r in values["judgments"]}
    return seal, chain, judgments


def test_post_ttl_audit_reads_only_review_metadata(completed, monkeypatch):
    root, result = completed
    original = Path.read_bytes
    allowed = (root/"workshop-review-metadata.json").resolve()
    def read_only_metadata(path):
        if path.resolve() != allowed:
            raise AssertionError("no_response_or_reference_access_for_metadata_audit")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", read_only_metadata)
    assert w.audit_reviews(allowed, result["review_sha256"], now=AT+timedelta(days=2))["content_reads"] == 0
    with pytest.raises(ValueError, match="expired"):
        w.audit_reviews(allowed, result["review_sha256"], now=AT+timedelta(days=91))


@pytest.mark.parametrize("change", ["hash", "duplicate", "free_text", "ttl"])
def test_review_metadata_tampering_is_rejected(completed, change):
    root, result = completed
    path = root/"workshop-review-metadata.json"
    data = json.loads(path.read_text())
    expected = result["review_sha256"]
    if change == "hash":
        expected = "0"*64
    else:
        if change == "duplicate":
            data["judgments"].append(data["judgments"][0])
        elif change == "free_text":
            data["judgments"][0]["raw_response"] = "SECRET_FIXTURE_ONLY"
        else:
            data["judgments"][0]["expires_at"] = (AT+timedelta(days=365)).isoformat()
        path.write_text(json.dumps(data), encoding="utf-8")
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        w.audit_reviews(path, expected, now=AT+timedelta(days=2))


def test_reference_freeze_cannot_be_overwritten_or_rehashed(completed):
    root, result = completed
    with pytest.raises(FileExistsError):
        w.run_workshop(FIXTURES, root, at=AT)
    path = root/"workshop-references.json"
    with path.open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError):
        w.load_freeze(path, result["reference_sha256"])


def test_anonymization_is_paired_and_omits_arm_metadata(completed):
    root, result = completed
    seal, _, _ = material(root, result)
    responses = []
    for record in seal["body"]["records"]:
        for arm in ("v3", "v4"):
            responses.append(w.MockResponse(case_id=record["source"]["case_id"], arm=arm, outcome="interpreted",
                body="MOCK_BODY", persisted_at=AT+timedelta(minutes=1), expires_at=AT+timedelta(hours=24, minutes=1)))
    packets, private = w.anonymize(seal, responses, now=AT+timedelta(hours=1), seed=42)
    assert len(packets) == len(private) == 16
    assert all(not {"arm", "model", "provider", "prompt", "family_id"} & set(p) for p in packets)
    # Source includes a family_id in the freeze, but reviewer packet must not leak it.
    assert all("family_id" not in p["source"] for p in packets)
    with pytest.raises(ValueError):
        w.anonymize(seal, responses[:-1], now=AT+timedelta(hours=1), seed=42)
    with pytest.raises(ValueError, match="reviewable"):
        w.anonymize(seal, responses, now=AT+timedelta(hours=24, minutes=1), seed=42)


def test_review_and_fact_disagreements_need_explicit_adjudication(completed):
    root, result = completed
    _, chain, judgments = material(root, result)
    label = next(k for k, c in chain["chains"].items() if c["disagreement"])
    a, b, resolution = [w.Judgment.model_validate(v) for v in chain["initial_and_adjudications"][label]]
    with pytest.raises(ValueError, match="adjudication"):
        w.adjudicate(a, b, None)
    assert w.adjudicate(a, b, resolution)[0] == resolution
    with pytest.raises(ValueError):
        w.adjudicate(a, a, resolution)
    with pytest.raises(ValidationError):
        w.Judgment.model_validate({**judgments[label].model_dump(), "provenance_kind": "independent_human"})


def test_endpoint_handles_indeterminate_and_missing_without_dropping_pairs(completed):
    root, result = completed
    seal, chain, judgments = material(root, result)
    packets = [dict(blind_id=k, outcome=next(r["outcome"] for r in result["summary"]["cases"]
        if r["case_id"] == b["case_id"] and r["arm"] == b["arm"])) for k, b in chain["bindings"].items()]
    label = next(k for k, b in chain["bindings"].items() if b["case_id"] == "W-01" and b["arm"] == "v4")
    old = judgments[label]
    dimensions = dict(old.dimensions)
    dimensions["event_stage"] = w.Rating(verdict="indeterminate", matched=0, omitted=0, unsupported=0)
    judgments[label] = old.model_copy(update={"dimensions": dimensions})
    report = w.summarize(seal, packets, chain["bindings"], judgments, now=AT+timedelta(days=2))
    assert report["delta_lower"] == "1/4" and report["delta_upper"] == "3/8"
    with pytest.raises(ValueError, match="inventory"):
        w.summarize(seal, packets+packets[:1], chain["bindings"], judgments, now=AT+timedelta(days=2))


def test_future_source_and_false_pass_are_blocked():
    with pytest.raises(ValidationError):
        w.Source(case_id="W-01", family_id="WF-01", headline="fiction", summary="fiction",
            available_at=AT+timedelta(seconds=1), decision_time=AT)
    with pytest.raises(ValidationError):
        w.Rating(verdict="pass", matched=0, omitted=-1, unsupported=0)


def releases():
    return [AT+timedelta(hours=block, seconds=i) for block in range(6) for i in range(32)]


def test_capacity_no_owner_commitment_and_one_person_are_not_executable():
    assert not w.capacity_plan(releases(), [[], []], [])["feasible"]
    windows = [("sim-person-a", AT, AT+timedelta(hours=8))]
    assert not w.capacity_plan(releases(), [windows, [("sim-person-b", AT, AT+timedelta(hours=8))]],
                               [("sim-adjudicator", AT, AT+timedelta(hours=8))])["feasible"]


def test_mock_parallel_capacity_covers_all_six_microblocks_not_real_availability():
    primary = [[(f"sim-lane-{lane}-{i}", AT, AT+timedelta(hours=16)) for i in range(6)] for lane in range(2)]
    adj = [(f"sim-adj-{i}", AT, AT+timedelta(hours=16)) for i in range(3)]
    result = w.capacity_plan(releases(), primary, adj)
    assert result["feasible"] and result["outputs"] == 192
    assert result["review_tasks"] == 384 and result["adjudication_tasks"] == 192
    assert datetime.fromisoformat(result["latest_finish"]) < AT+timedelta(hours=23)
    with pytest.raises(ValueError):
        w.capacity_plan(releases()[:-1], primary, adj)
    with pytest.raises(ValueError):
        w.capacity_plan(releases(), [primary[0], primary[0]], adj)


def test_review_timestamp_after_content_expiry_and_invalid_denominators(completed):
    root, result = completed
    seal, chain, judgments = material(root, result)
    label = next(k for k, b in chain["bindings"].items() if b["case_id"] == "W-01")
    j = judgments[label]
    ref = next(r for r in seal["body"]["records"] if r["source"]["case_id"] == "W-01")
    created = AT+timedelta(days=2)
    late = j.model_copy(update=dict(created_at=created, expires_at=created+timedelta(days=90)))
    with pytest.raises(ValueError, match="ttl"):
        w.validate_judgment(late, chain["bindings"], ref, now=created)
    scores = dict(j.dimensions)
    scores["events"] = w.Rating(verdict="pass", matched=999, omitted=0, unsupported=0)
    with pytest.raises(ValueError, match="denominator"):
        w.validate_judgment(j.model_copy(update={"dimensions": scores}), chain["bindings"], ref, now=AT+timedelta(hours=3))
