"""Offline instruments, not semantic labels or tests of the held-out answers."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("attribution_review_tools", REPO / "tools/evaluation/prepare_attribution_review.py")
instrument = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(instrument)


def test_prepare_is_immutable_and_blind_without_predictions(tmp_path):
    manifest = instrument.prepare(REPO, tmp_path, include_real_metadata=False)
    assert manifest["synthetic_cases"] == 32
    assert manifest["system_predictions"] == manifest["human_references"] == 0
    assert manifest["inference_attempts"] == manifest["network_requests"] == 0
    assert instrument.prepare(REPO, tmp_path, include_real_metadata=False) == manifest
    assert instrument.verify(tmp_path, REPO)["status"] == "verified"
    blind = json.loads((tmp_path / "reviewer/blind_synthetic_evidence.json").read_bytes())
    for case in blind["cases"]:
        assert set(case) == {"case_id", "evidence_fingerprint", "evidence"}
        assert set(case["evidence"][0]) == {"evidence_id", "field", "text"}
    template = json.loads((tmp_path / "references/human_a.template.json").read_bytes())
    assert template["reviewer_id"] is None and template["assistance"] is None
    assert all(r["review_status"] == "pending" and not r["units"] for r in template["cases"])
    predictions = json.loads((tmp_path / "system/system_outputs.template.json").read_bytes())
    assert all(r["outcome"] == "not_run" and not r["units"] and r["cost_usd"] is None for r in predictions["cases"])


def test_synthetic_cases_are_unique_and_cover_all_requested_domains():
    sources = json.loads((REPO / "evaluation/phase4c2_attribution_v1/synthetic_sources.json").read_bytes())
    cases = sources["cases"]
    assert len({instrument.text_digest(c["headline"], c["summary"]) for c in cases}) == 32
    assert {c["stratum"] for c in cases} == set(instrument.PATTERNS) | {"challenge"}


def test_no_overwrite_or_tampered_artifact(tmp_path):
    instrument.prepare(REPO, tmp_path, include_real_metadata=False)
    path = tmp_path / "reviewer/blind_synthetic_evidence.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        instrument.prepare(REPO, tmp_path, include_real_metadata=False)
    with pytest.raises(ValueError, match="fingerprint"):
        instrument.verify(tmp_path)


def alignment():
    # Fictional instrument-only values; not annotations for any prepared case.
    return {"aligned_after_reference_freeze": True, "reference_file_fingerprint": "test-ref",
        "system_file_fingerprint": "test-system", "units": [{
        "case_id": "instrument-only", "unit_id": "u", "dimension": "participation",
        "system_outcome": "interpreted", "reference_status": "conclusive",
        "assistance": "none", "independence_attestation": True, "reviewer_id": "fictional-test-reviewer",
        "provenance_verified": True, "reference_evidence": [{"evidence_id": "test", "start": 0, "end": 1}],
        "has_seen_system_outputs": False, "reviewed_at": "2026-10-13T00:00:00Z",
        "reference_value": "unknown", "system_value": "unknown"}]}


@pytest.mark.parametrize("change", [
    {"assistance":"chatgpt"}, {"reviewer_id":None}, {"provenance_verified":False},
    {"has_seen_system_outputs":True}, {"reference_evidence":[]},
    {"reviewed_at":"2026-10-13T00:00:00"}, {"system_value":None},
])
def test_comparison_blocks_unverified_ai_or_missing_reference(change):
    data = alignment(); data["units"][0].update(change)
    with pytest.raises(ValueError):
        instrument.compare(data)


@pytest.mark.parametrize("outcome", ["abstained", "rejected", "invalid_response", "transport_error", "unresolved", "not_run"])
def test_technical_failure_abstention_and_no_execution_counted(outcome):
    data = alignment(); data["units"][0]["system_outcome"] = outcome
    report = instrument.compare(data)
    counts = report["dimensions"]["participation"]
    assert counts["total_units"] == 1 and counts.get("conclusive_compared", 0) == 0
    assert counts["system_not_run" if outcome == "not_run" else outcome] == 1
    assert report["population_metrics"] == "not_estimated"


def test_inconclusive_and_duplicate_units_are_not_hidden():
    data = alignment(); data["units"][0]["reference_status"] = "uncertain"
    assert instrument.compare(data)["dimensions"]["participation"]["inconclusive_reference"] == 1
    data["units"].append(deepcopy(data["units"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        instrument.compare(data)
    with pytest.raises(ValueError, match="freeze"):
        instrument.compare({"units":[]})
