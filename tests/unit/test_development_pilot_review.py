"""Simulated structural tests only; never annotate the six real pilot packets."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("development_pilot_review", REPO/"tools/evaluation/development_pilot_review.py")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
NOW = datetime(2026, 1, 11, tzinfo=timezone.utc)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def sample_packet(index=1):
    # New fictional fixture unrelated to any development story or reserved case.
    text = "Ørquev café 𝛼; sample only."
    evidence = dict(evidence_id=m.fp(["simulated", index]), revision_id="a"*64,
                    field="headline", text=text)
    p = dict(case_id=f"P-SIM-{index}", primary_revision_id="a"*64, evidence=[evidence])
    p["packet_fingerprint"] = m.fp(p)
    return p


def completed_fixture(packet):
    forms = m.templates(packet)
    f, c, t = [forms[k] for k in ("factual", "contract", "timing")]
    f["status"] = "completed"
    text = packet["evidence"][0]["text"]
    f["facts"] = [dict(fact_id="F001", dimension="events", meaning="Simulated test-only assertion; not a pilot annotation.",
        certainty="indeterminate", material=None,
        citations=[dict(evidence_id=packet["evidence"][0]["evidence_id"], field="headline", start=0, end=len(text), quote=text)])]
    for dimension in m.DIMENSIONS:
        f["dimension_assessments"][dimension] = dict(status="indeterminate", fact_ids=[], note="Simulated unresolved dimension.")
    f["dimension_assessments"]["events"]["fact_ids"] = ["F001"]
    c.update(status="completed", mappings=[dict(fact_id="F001", mode="indeterminate", rationale="Simulated contractual uncertainty.")],
             allowed_outcomes=["indeterminate"], rationale="Simulation only, not a semantic decision.")
    start = datetime(2026, 1, 10, 10, tzinfo=timezone.utc)
    phases = ["reading", "factual_annotation", "citation_check", None, "contract_review"]
    intervals = [dict(kind="pause" if phase is None else "active", phase=phase,
        pause_reason="break" if phase is None else None,
        started_at=(start+timedelta(minutes=i)).isoformat(),
        completed_at=(start+timedelta(minutes=i+1)).isoformat()) for i, phase in enumerate(phases)]
    t.update(status="completed", review_id="sim-review-"+packet["case_id"], reviewer_id="sim-owner",
        reviewer_name="SIMULATED FIXTURE, NOT A REAL REVIEWER", review_kind="human_owner",
        independence="not_claimed", execution_mode="manual_no_api", timestamp_source="owner_declared",
        timestamp_basis="Synthetic fixture timestamps, not observations of a reviewer.",
        started_at=start.isoformat(), completed_at=(start+timedelta(minutes=5)).isoformat(),
        factual_closed_at=(start+timedelta(minutes=3)).isoformat(), active_seconds=240, pause_seconds=60,
        phase_seconds={p: 60 if p in phases else 0 for p in m.PHASES}, intervals=intervals,
        discrepancy_status="unresolved", adjudication_status="deferred")
    return forms


def test_exact_six_packages_and_reproducible_nonadjacent_order():
    packets = m.verify_packages(REPO)
    plan, corpus, private, _ = m.load_sources(REPO)
    order = m.blind_order(plan["selected_case_ids"], private)
    assert len(packets) == 6 and set(packets) == set(plan["selected_case_ids"])
    assert order == m.blind_order(list(reversed(plan["selected_case_ids"])), private)
    for i, cid in enumerate(order):
        for j, other in enumerate(order):
            if i < j and private[cid]["family_id"] == private[other]["family_id"]:
                assert j-i >= 3
        p = packets[cid]
        news = corpus[cid]["request"]["news"]
        assert p["headline"] == news["headline"] and p["summary"] == news["summary"]
        assert p["evidence"] == corpus[cid]["evidence"]
        assert p["eligible_registry"] == corpus[cid]["request"]["registry_entries"]
        assert p["virtual_clock"]["decision_time"] == corpus[cid]["request"]["decision_time"]


def test_blind_packets_contain_no_private_or_prompt_metadata():
    def visit(value):
        if isinstance(value, dict):
            assert not set(value) & {"family_id", "stratum", "primary_stratum", "variant", "expected", "scoring", "axis", "counterfactual_axis", "originality_note", "prompt_version"}
            for v in value.values():
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)
    for packet in m.verify_packages(REPO).values():
        visit(packet)
        assert "draft2" not in json.dumps(packet)


def test_unfilled_prepared_forms_have_no_measurements_or_semantics():
    packets = m.verify_packages(REPO)
    result = m.validate_forms(REPO/m.ROOT/"forms", packets, require_completed=False, now=NOW)
    assert result["completed_cases"] == 0 and result["semantic_truth"] == "not_assessed"
    with pytest.raises(ValueError, match="review_not_completed"):
        m.validate_forms(REPO/m.ROOT/"forms", packets, require_completed=True, now=NOW)
    for p in packets.values():
        forms = m.templates(p)
        assert not forms["factual"]["facts"] and not forms["contract"]["mappings"]
        assert all(a["status"] is None for a in forms["factual"]["dimension_assessments"].values())
        assert forms["timing"]["reviewer_name"] is None and forms["timing"]["started_at"] is None


def test_full_simulated_six_case_form_flow(tmp_path):
    packets = {p["case_id"]: p for p in [sample_packet(i) for i in range(1, 7)]}
    for cid, packet in packets.items():
        forms = completed_fixture(packet)
        write(tmp_path/"factual"/(cid+".json"), forms["factual"])
        forms["contract"]["factual_record_sha256"] = m.sha(tmp_path/"factual"/(cid+".json"))
        for kind in ("contract", "timing"):
            write(tmp_path/kind/(cid+".json"), forms[kind])
    result = m.validate_forms(tmp_path, packets, require_completed=True, now=NOW)
    assert result == dict(cases=6, completed_cases=6, semantic_truth="not_assessed", judgments_created=0)
    target = tmp_path/"factual"/(next(iter(packets))+".json")
    before = target.read_bytes()
    # A schema-valid but fabricated meaning passes structure, explicitly not truth.
    changed = json.loads(before)
    changed["facts"][0]["meaning"] = "Fabricated meaning deliberately not entailed by the quote."
    write(target, changed)
    with pytest.raises(ValueError, match="factual_record_hash_mismatch"):
        m.validate_forms(tmp_path, packets, require_completed=True, now=NOW)
    m.validate_factual(m.Factual.model_validate(changed), packets[next(iter(packets))])


@pytest.mark.parametrize("mutation", ["missing_id", "wrong_field", "other_revision", "utf16_offset", "case_change", "end_out_of_range", "negative_offset", "float_offset"])
def test_exact_unicode_citations_reject_invalid_bindings(mutation):
    packet = sample_packet()
    f = completed_fixture(packet)["factual"]
    citation = f["facts"][0]["citations"][0]
    if mutation == "missing_id": citation["evidence_id"] = "b"*64
    elif mutation == "wrong_field": citation["field"] = "summary"
    elif mutation == "other_revision": packet["evidence"][0]["revision_id"] = "b"*64
    elif mutation == "utf16_offset": citation["end"] += 1
    elif mutation == "case_change": citation["quote"] = citation["quote"].lower()
    elif mutation == "end_out_of_range": citation["end"] = 1000
    elif mutation == "negative_offset": citation["start"] = -1
    else: citation["start"] = 0.5
    with pytest.raises(ValueError):
        m.validate_factual(m.Factual.model_validate(f), packet)


def test_uncertainty_materiality_and_representability_remain_separate():
    p = sample_packet()
    forms = completed_fixture(p)
    f = m.Factual.model_validate(forms["factual"])
    m.validate_factual(f, p)
    assert f.facts[0].certainty == "indeterminate" and f.facts[0].material is None
    forms["contract"]["factual_record_sha256"] = "c"*64
    m.validate_contract(m.Contract.model_validate(forms["contract"]), f, "c"*64)
    assert forms["contract"]["mappings"][0]["mode"] == "indeterminate"
    bad = f.model_dump(mode="json")
    bad["dimension_assessments"]["events"] = dict(status="not_applicable", fact_ids=["F001"], note="Test")
    with pytest.raises(ValueError):
        m.validate_factual(m.Factual.model_validate(bad), p)
    forms["contract"]["facts"] = []
    with pytest.raises(ValueError): m.Contract.model_validate(forms["contract"])


@pytest.mark.parametrize("mutation", ["missing_dimension", "duplicate_fact", "orphan_fact", "unfilled_annotations", "missing_certainty", "extra_prediction"])
def test_complete_closed_factual_schema(mutation):
    p = sample_packet()
    f = completed_fixture(p)["factual"]
    if mutation == "missing_dimension": del f["dimension_assessments"]["dates"]
    elif mutation == "duplicate_fact": f["facts"].append(deepcopy(f["facts"][0]))
    elif mutation == "orphan_fact": f["dimension_assessments"]["events"]["fact_ids"] = []
    elif mutation == "unfilled_annotations": f["status"] = "unfilled"
    elif mutation == "missing_certainty": del f["facts"][0]["certainty"]
    else: f["prediction"] = "Not allowed"
    with pytest.raises(ValueError): m.validate_factual(m.Factual.model_validate(f), p)


@pytest.mark.parametrize("mutation", ["naive", "future", "overlap", "gap", "negative_duration", "nan", "total_mismatch", "missing_name", "owner_independent", "api_tokens", "premature_contract", "expired", "fake_adjudication", "unknown_phase"])
def test_timing_and_provenance_adversarial(mutation):
    t = completed_fixture(sample_packet())["timing"]
    if mutation == "naive": t["started_at"] = "2026-01-10T10:00:00"
    elif mutation == "future": t["completed_at"] = "2035-01-01T00:00:00Z"
    elif mutation == "overlap": t["intervals"][1]["started_at"] = t["intervals"][0]["started_at"]
    elif mutation == "gap": t["intervals"][1]["started_at"] = "2026-01-10T10:01:10Z"
    elif mutation == "negative_duration": t["phase_seconds"]["reading"] = -1
    elif mutation == "nan": t["phase_seconds"]["reading"] = float("nan")
    elif mutation == "total_mismatch": t["pause_seconds"] = 0
    elif mutation == "missing_name": t["reviewer_name"] = " "
    elif mutation == "owner_independent": t["independence"] = "reviewer_declared_independent"
    elif mutation == "api_tokens": t["api_tokens"] = 12
    elif mutation == "premature_contract": t["factual_closed_at"] = "2026-01-10T10:04:10Z"
    elif mutation == "expired": pass
    elif mutation == "fake_adjudication": t["adjudication_status"] = "performed"
    else: t["phase_seconds"]["unsupported_phase"] = 0
    with pytest.raises(ValueError):
        m.validate_timing(m.Timing.model_validate(t), now=NOW+timedelta(days=100) if mutation == "expired" else NOW)


def test_factual_must_close_before_contract_and_hash_is_required():
    forms = completed_fixture(sample_packet())
    f = m.Factual.model_validate(forms["factual"])
    with pytest.raises(ValueError, match="incomplete_contract_review"):
        m.validate_contract(m.Contract.model_validate(forms["contract"]), f, "c"*64)
    forms["factual"]["status"] = "in_progress"
    with pytest.raises(ValueError, match="factual_must_close"):
        m.validate_contract(m.Contract.model_validate(forms["contract"]), m.Factual.model_validate(forms["factual"]), "c"*64)


def test_unknown_case_or_incomplete_inventory_blocked(tmp_path):
    with pytest.raises(ValueError, match="exact_six_case_form_inventory_required"):
        m.validate_forms(tmp_path, {"P-SIM-1": sample_packet()}, require_completed=False, now=NOW)


def test_original_manifest_or_package_tampering_blocked(tmp_path):
    source = tmp_path/m.SOURCE
    source.mkdir(parents=True)
    write(source/"manifest.json", {})
    with pytest.raises(ValueError, match="source_manifest_pin_mismatch"):
        m.load_sources(tmp_path)
    folder = tmp_path/m.ROOT
    folder.mkdir(parents=True)
    write(folder/"manifest.json", {"version": "wrong", "sha256": {}})
    with pytest.raises(ValueError, match="wrong_manifest_version"):
        m.verify_packages(tmp_path)


@pytest.mark.parametrize("mutation", ["case_id", "packet_fingerprint"])
def test_forms_cannot_be_reassigned_to_another_packet(tmp_path, mutation):
    packets = {p["case_id"]: p for p in [sample_packet(i) for i in range(1, 7)]}
    for cid, packet in packets.items():
        for kind, form in m.templates(packet).items():
            if cid == "P-SIM-1" and kind == "factual":
                form[mutation] = "wrong-case" if mutation == "case_id" else "b"*64
            write(tmp_path/kind/(cid+".json"), form)
    with pytest.raises(ValueError, match="form_packet_binding_mismatch"):
        m.validate_forms(tmp_path, packets, require_completed=False, now=NOW)


def test_duplicate_review_identity_is_not_silently_reused(tmp_path):
    packets = {p["case_id"]: p for p in [sample_packet(i) for i in range(1, 7)]}
    for cid, packet in packets.items():
        forms = completed_fixture(packet)
        write(tmp_path/"factual"/(cid+".json"), forms["factual"])
        forms["contract"]["factual_record_sha256"] = m.sha(tmp_path/"factual"/(cid+".json"))
        forms["timing"]["review_id"] = "sim-duplicate-review"
        for kind in ("contract", "timing"):
            write(tmp_path/kind/(cid+".json"), forms[kind])
    with pytest.raises(ValueError, match="duplicate_review_id"):
        m.validate_forms(tmp_path, packets, require_completed=True, now=NOW)
