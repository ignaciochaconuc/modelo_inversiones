"""Simulated instrument tests; never real ChatGPT references or Nacho outputs."""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("manual_chatgpt_review", REPO / "tools/evaluation/prepare_chatgpt_review.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def completed_response(packet):
    # Only nonconclusive mechanical placeholders, no semantic reference labels.
    return {"block_id": packet["block_id"], "limitations": ["instrument test only"], "cases": [
        {"case_id": c["case_id"], "evidence_fingerprint": c["evidence_fingerprint"],
         "status": "nonconclusive", "events": [], "units": [], "uncertainties": ["fixture only"]}
        for c in packet["cases"]]}


def captured_provenance(output, bid):
    p = json.loads((output / f"templates/{bid}.provenance.json").read_bytes())
    p.update(recorded_by="offline-test-recorder-NOT-adjudicator", model_label_visibility="not_exposed",
             started_at="2026-10-13T18:00:00Z", completed_at="2026-10-13T18:01:00Z",
             fresh_conversation_declared=True, system_outputs_seen=False,
             context_limitations=["offline instrument fixture; no conversation actually executed"])
    return p


def test_prepare_blind_blocks_are_identical_to_original_cases(tmp_path):
    m = tool.prepare(REPO, tmp_path)
    assert tool.prepare(REPO, tmp_path) == m
    assert tool.verify(REPO, tmp_path) == {"status":"verified", "blocks":8, "cases":32, "api_calls":0}
    for i in range(1, 9):
        md = (tmp_path / f"packets/B{i:02d}.md").read_text(encoding="utf-8")
        assert "sampling_stratum" not in md and "Nacho" not in md and "system_predictions" not in md
    assert m["references_generated"] == 0 and m["independent_human_ground_truth"] is False


def test_tamper_and_overwrite_blocked(tmp_path):
    tool.prepare(REPO, tmp_path)
    (tmp_path / "packets/B01.md").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError):tool.verify(REPO, tmp_path)
    with pytest.raises(ValueError):tool.prepare(REPO, tmp_path)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', '{} trailing', '{"cases":[', '[]'])
def test_json_parser_rejects_ambiguous_incomplete_or_nonfinite(raw):
    with pytest.raises(ValueError):tool.parse(raw)


def test_import_preserves_raw_unicode_fence_and_unknown_api_metadata(tmp_path):
    output = tmp_path / "prepared"; tool.prepare(REPO, output)
    packet = tool.packet_for(REPO, output, "B01"); data = completed_response(packet)
    data["limitations"] = ["⚠ Instrument-only fixture"]
    raw = "```json\n" + json.dumps(data, ensure_ascii=False) + "\n```\n"
    response = tmp_path / "response.txt"; response.write_text(raw, encoding="utf-8")
    prov = tmp_path / "provenance.json"; tool.write_json(prov, captured_provenance(output, "B01"))
    target = tmp_path / "import.json"; result = tool.import_response(REPO, output, "B01", response, prov, target)
    record = json.loads(target.read_bytes())
    assert record["raw_response_utf8"].encode() == response.read_bytes()
    assert record["transformation"] == "single_json_fence_unwrapped"
    assert record["provenance"]["visible_model_label"] is None
    assert record["provenance"]["api_parameters"] is None
    assert tool.import_response(REPO, output, "B01", response, prov, target) == result


@pytest.mark.parametrize("change", ["missing_case", "wrong_fingerprint", "unknown_case", "pending", "fabricated_quote"])
def test_response_validation_does_not_fix_or_invent_annotations(tmp_path, change):
    tool.prepare(REPO, tmp_path); packet = tool.packet_for(REPO, tmp_path, "B01"); data = completed_response(packet)
    case = data["cases"][0]
    if change == "missing_case":data["cases"].pop()
    elif change == "wrong_fingerprint":case["evidence_fingerprint"] = "a"*64
    elif change == "unknown_case":case["case_id"] = "not-in-packet"
    elif change == "pending":case["status"] = "not_run"
    else:
        case["units"] = [{"unit_id":"fixture-only", "event_id":None, "name":"fixture-only",
            "dimensions": {d:{"status":"uncertain", "value":None, "rationale":"fixture", "evidence":[
                {"evidence_id":packet["cases"][0]["evidence"][0]["evidence_id"], "quote":"NEVER_PRESENT_FABRICATION"}]} for d in tool.DIMENSIONS}}]
    with pytest.raises(ValueError):tool.validate_annotations(data, packet)


@pytest.mark.parametrize("change", [
    {"api_parameters":{"temperature":0}}, {"model_snapshot":"invented"}, {"api_calls":1},
    {"system_outputs_seen":True}, {"fresh_conversation_declared":False},
    {"visible_model_label":"guessed"}, {"started_at":"2026-10-13T18:00:00"},
])
def test_unknown_or_unblinded_provenance_not_upgraded(tmp_path, change):
    tool.prepare(REPO, tmp_path); prov = captured_provenance(tmp_path, "B01"); prov.update(change)
    with pytest.raises(ValueError):tool.validate_provenance(prov, tmp_path, "B01")


def import_all(repo, output, root):
    imports = root / "imports"
    for i in range(1, 9):
        bid = f"B{i:02d}"; packet = tool.packet_for(repo, output, bid)
        response = root / f"{bid}.txt"; tool.write_json(response, completed_response(packet))
        provenance = root / f"{bid}.provenance.json"; tool.write_json(provenance, captured_provenance(output, bid))
        tool.import_response(repo, output, bid, response, provenance, imports / f"{bid}.json")
    return imports


def test_freeze_requires_all_blocks_and_never_changes_existing_seal(tmp_path):
    output = tmp_path / "prepared"; tool.prepare(REPO, output)
    imports = import_all(REPO, output, tmp_path); destination = tmp_path / "freeze.json"
    result = tool.freeze(REPO, output, imports, destination)
    original = destination.read_bytes()
    assert tool.freeze(REPO, output, imports, destination) == result and destination.read_bytes() == original
    record = json.loads((imports / "B01.json").read_bytes()); record["raw_response_utf8"] += "tamper"
    (imports / "B01.json").write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError):tool.freeze(REPO, output, imports, destination)
    with pytest.raises(ValueError):tool.freeze(REPO, output, tmp_path / "missing", tmp_path / "other.json")


def test_explicit_failure_retains_cases_without_creating_labels(tmp_path):
    tool.prepare(REPO, tmp_path / "prepared"); output = tmp_path / "prepared"
    raw = tmp_path / "truncated.txt"; raw.write_text('{"cases":[', encoding="utf-8")
    prov = tmp_path / "prov.json"; tool.write_json(prov, captured_provenance(output, "B01"))
    with pytest.raises(ValueError):tool.import_response(REPO, output, "B01", raw, prov, tmp_path / "bad.json")
    tool.import_response(REPO, output, "B01", raw, prov, tmp_path / "failure.json", "response_truncated")
    record = json.loads((tmp_path / "failure.json").read_bytes())
    assert len(record["annotations"]["cases"]) == 4
    assert all(c["status"] == "technical_error" and c["units"] == [] for c in record["annotations"]["cases"])


@pytest.mark.parametrize("outcome", ["not_run", "abstained", "rejected", "invalid_response", "transport_error", "unresolved", "interpreted"])
def test_comparison_counts_all_cases_and_technical_states(tmp_path, outcome):
    # Toy identities are NOT any of the prepared 32 article IDs or semantic answers.
    cases = [{"case_id":f"instrument-{i}", "status":"nonconclusive", "units":[]} for i in range(32)]
    refs = {"cases":cases}; seal = {"review_kind":tool.ROLE, "independent_human_ground_truth":False,
        "reference_fingerprint":tool.fp(refs), "references":refs, "frozen_at":"2026-10-13T18:00:00Z"}
    tool.write_json(tmp_path / "seal.json", seal)
    systems = {"cases":[{"case_id":c["case_id"], "outcome":outcome, "units":[],
        "attempt_started_at":"2026-10-13T18:01:00Z", "record_id":"fixture-only", "output_fingerprint":"fixture-only"} for c in cases]}
    tool.write_json(tmp_path / "system.json", systems)
    alignment = {"reference_freeze_sha256":tool.sha(tmp_path / "seal.json"), "system_file_sha256":tool.sha(tmp_path / "system.json"), "matches":[]}
    tool.write_json(tmp_path / "alignment.json", alignment)
    report = tool.compare(tmp_path / "seal.json", tmp_path / "system.json", tmp_path / "alignment.json")
    assert report["case_outcomes"] == {outcome:32} and len(report["owner_review_queue"]) == 32
    assert report["population_metrics"] == "not_estimated"
    systems["cases"].pop(); (tmp_path / "system.json").write_text(json.dumps(systems), encoding="utf-8")
    with pytest.raises(ValueError):tool.compare(tmp_path / "seal.json", tmp_path / "system.json", tmp_path / "alignment.json")


@pytest.mark.parametrize("mode", ["agreement", "disagreement", "omission"])
def test_comparison_dimensions_are_separate_and_omissions_not_agreement(tmp_path, mode):
    cases = [{"case_id":f"toy-{i}", "status":"nonconclusive", "units":[]} for i in range(32)]
    cases[0]["units"] = [{"unit_id":"ref-toy", "dimensions":{
        d:{"status":"conclusive", "value":"toy-reference-value"} for d in tool.DIMENSIONS}}]
    refs = {"cases":cases}
    tool.write_json(tmp_path / "seal.json", {"review_kind":tool.ROLE, "independent_human_ground_truth":False,
        "reference_fingerprint":tool.fp(refs), "references":refs, "frozen_at":"2026-10-13T18:00:00Z"})
    systems = {"cases":[{"case_id":c["case_id"], "outcome":"interpreted", "units":[],
        "attempt_started_at":"2026-10-13T18:01:00Z", "record_id":"fixture-only", "output_fingerprint":"fixture-only"} for c in cases]}
    systems["cases"][0]["units"] = [{"unit_id":"sys-toy", "dimensions":{
        d:"toy-reference-value" if mode=="agreement" else "toy-disagreeing-value" for d in tool.DIMENSIONS}}]
    tool.write_json(tmp_path / "system.json", systems)
    matches = [] if mode=="omission" else [{"case_id":"toy-0", "reference_unit_id":"ref-toy", "system_unit_id":"sys-toy"}]
    tool.write_json(tmp_path / "alignment.json", {"reference_freeze_sha256":tool.sha(tmp_path / "seal.json"),
        "system_file_sha256":tool.sha(tmp_path / "system.json"), "matches":matches})
    result = tool.compare(tmp_path / "seal.json", tmp_path / "system.json", tmp_path / "alignment.json")
    assert all(counts[mode]==1 for counts in result["dimensions"].values())
    assert result["owner_review_queue"][0]["extra_system_units"] == (1 if mode=="omission" else 0)
