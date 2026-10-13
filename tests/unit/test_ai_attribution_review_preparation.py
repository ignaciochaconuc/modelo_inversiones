"""Mechanical tests only; no labels for the 32 prepared evaluation cases."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ai_review_instruments", REPO / "tools/evaluation/prepare_ai_attribution_review.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_prepare_preserves_blind_packet_and_never_generates_references(tmp_path):
    plan = module.prepare(REPO, tmp_path)
    assert module.prepare(REPO, tmp_path) == plan
    assert module.verify(tmp_path, REPO)["cases"] == 32
    assert not plan["paid_calls_authorized"] and plan["reference_count"] == plan["inference_attempts"] == 0
    packets = json.loads((tmp_path / "evaluator/annotation_inputs.json").read_bytes())
    assert all(set(p) == {"instructions", "case", "identity_evidence"} for p in packets)
    refs = json.loads((tmp_path / "references/ai_references.template.json").read_bytes())
    assert refs["reference_kind"] == module.ROLE and refs["independent_human_ground_truth"] is False
    assert all(c["status"] == "not_run" and c["case_provenance"] is None for c in refs["cases"])


def test_pending_reference_and_changed_packet_blocked(tmp_path):
    module.prepare(REPO, tmp_path)
    with pytest.raises(ValueError):
        module.freeze(tmp_path, tmp_path / "references/ai_references.template.json", tmp_path / "seal.json", REPO)
    path = tmp_path / "evaluator/annotation_inputs.json"
    packets = json.loads(path.read_bytes()); packets[0]["system_predictions"] = []
    path.write_text(json.dumps(packets), encoding="utf-8")
    with pytest.raises(ValueError):
        module.verify(tmp_path, REPO)


def fixture_submission(output):
    # Provenance and nonconclusive values are fictional instrument-only fixtures.
    data = json.loads((output / "references/ai_references.template.json").read_bytes())
    p = data["run_provenance"]
    p.update(provider="anthropic", model="claude-sonnet-4-6", model_version="offline-fixture-NOT-real-inference",
             parameters={"mode":"offline_instrument_test"}, authorization_id="offline-test-NOT-paid-authority",
             started_at="2026-10-13T18:00:00Z", completed_at="2026-10-13T18:01:00Z", system_outputs_seen=False)
    for case in data["cases"]:
        case.update(status="nonconclusive", response_sha256="a"*64, case_provenance={
            "started_at":p["started_at"], "completed_at":p["completed_at"], "provider":p["provider"],
            "model":p["model"], "parameters":p["parameters"], "usage":None, "cost_usd":None,
            "cost_quality":"unknown", "error_code":None})
    return data


def test_freeze_is_idempotent_does_not_upgrade_ai_to_human(tmp_path):
    module.prepare(REPO, tmp_path)
    submitted = tmp_path / "submitted.json"; sealed = tmp_path / "seal.json"
    data = fixture_submission(tmp_path); submitted.write_text(json.dumps(data), encoding="utf-8")
    first = module.freeze(tmp_path, submitted, sealed, REPO)
    assert module.freeze(tmp_path, submitted, sealed, REPO) == first
    assert json.loads(sealed.read_bytes())["independent_human_ground_truth"] is False
    data["cases"][0]["uncertainties"] = ["changed after sealing"]
    submitted.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="never overwrite"):
        module.freeze(tmp_path, submitted, sealed, REPO)


@pytest.mark.parametrize("change", ["unblinded", "missing_case", "missing_provenance", "human_claim"])
def test_freeze_rejects_incomplete_or_unblinded_reference(tmp_path, change):
    module.prepare(REPO, tmp_path); data = fixture_submission(tmp_path)
    if change == "unblinded":data["run_provenance"]["system_outputs_seen"] = True
    elif change == "missing_case":data["cases"].pop()
    elif change == "missing_provenance":data["cases"][0]["case_provenance"] = {}
    else:data["independent_human_ground_truth"] = True
    submitted = tmp_path / "submitted.json"; submitted.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        module.freeze(tmp_path, submitted, tmp_path / "seal.json", REPO)


def test_comparison_keeps_all_cases_and_blocks_pre_freeze_generation(tmp_path):
    module.prepare(REPO, tmp_path); data = fixture_submission(tmp_path)
    submitted = tmp_path / "submitted.json"; submitted.write_text(json.dumps(data), encoding="utf-8")
    sealed = tmp_path / "seal.json"; module.freeze(tmp_path, submitted, sealed, REPO)
    systems = {"cases":[{"case_id":c["case_id"], "outcome":"not_run", "units":[]} for c in data["cases"]]}
    system_file = tmp_path / "system.json"; system_file.write_text(json.dumps(systems), encoding="utf-8")
    alignment_file = tmp_path / "alignment.json"
    alignment = {"reference_freeze_sha256":module.sha(sealed), "system_file_sha256":module.sha(system_file), "matches":[]}
    alignment_file.write_text(json.dumps(alignment), encoding="utf-8")
    report = module.compare(sealed, system_file, alignment_file)
    assert report["case_outcomes"] == {"not_run":32}
    assert len(report["owner_review_queue"]) == 32 and report["population_metrics"] == "not_estimated"
    systems["cases"][0].update(outcome="interpreted", attempt_started_at="2026-10-13T18:00:00Z", generated_at="2026-10-13T18:00:00Z", record_id="x", output_fingerprint="x")
    system_file.write_text(json.dumps(systems), encoding="utf-8")
    alignment["system_file_sha256"] = module.sha(system_file)
    alignment_file.write_text(json.dumps(alignment), encoding="utf-8")
    with pytest.raises(ValueError, match="follow reference freeze"):
        module.compare(sealed, system_file, alignment_file)
