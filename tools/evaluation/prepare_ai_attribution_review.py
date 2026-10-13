"""Prepare/seal exploratory AI references offline. No credentials or transport."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

VERSION = "ai-assisted-attribution-evaluation-v1"
ROLE = "ai_assisted_exploratory_evaluation"
DIMENSIONS = ("corporate_identity", "participation", "role", "relationship",
              "ticker_link", "event_state", "event_stage", "impact_support")
OPTIONS = {
    "claude-sonnet-4-6": {"provider": "anthropic", "family": "claude", "input": 3.0, "output": 15.0,
        "source": "https://platform.claude.com/docs/en/about-claude/pricing"},
    "gemini-2.5-flash": {"provider": "google", "family": "gemini", "input": 0.30, "output": 2.50,
        "source": "https://ai.google.dev/gemini-api/docs/pricing"},
}


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def immutable(path: Path, value: object) -> None:
    if path.exists():
        if json.loads(path.read_bytes()) != value:
            raise ValueError("existing artifact differs; use a new version")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(repo: Path, output: Path) -> dict:
    source = repo / "evaluation/phase4c2_attribution_v1/prepared/reviewer"
    evidence = json.loads((source / "blind_synthetic_evidence.json").read_bytes())
    identity = json.loads((source / "identity_lookup.synthetic.json").read_bytes())
    if evidence.get("fictional") is not True or len(evidence["cases"]) != 32 or identity.get("fictional") is not True:
        raise ValueError("only the frozen 32 fictional cases are eligible")
    instructions_path = repo / "evaluation/phase4c2_attribution_ai_v1/ANNOTATION_INSTRUCTIONS.md"
    instructions = instructions_path.read_text(encoding="utf-8")
    packets = [{"instructions": instructions, "case": case, "identity_evidence": identity}
               for case in evidence["cases"]]
    immutable(output / "evaluator/annotation_inputs.json", packets)
    # Conservative application estimate, not provider tokenization or invoice bound.
    bounds = [len(json.dumps(p, ensure_ascii=False).encode()) + 512 for p in packets]
    estimates = {model: {"nominal_usd": round(32 * (2500 * option["input"] + 3000 * option["output"]) / 1e6, 6),
        "byte_bound_scenario_usd": round((sum(bounds) * option["input"] + 32 * 4096 * option["output"]) / 1e6, 6),
        **option} for model, option in OPTIONS.items()}
    plan = {"version": VERSION, "evaluation_kind": ROLE, "status": "ai_evaluation_prepared_pending_authorization",
        "paid_calls_authorized": False, "evaluator_selected": None, "recommended_candidate": "claude-sonnet-4-6",
        "model_options": estimates, "price_checked_at": "2026-10-13T20:04:48Z",
        "price_reverify_before_execution": True, "max_attempts_per_case": 1, "max_output_tokens_planned": 4096,
        "tools": [], "retries": False, "explicit_cache": False, "parameters_actual": None,
        "evaluator_budget_proposed_usd": 3.50, "nacho_budget_separate_proposed_usd": 1.60,
        "bounds_max": max(bounds), "actual_cost_usd": None, "inference_attempts": 0,
        "finnhub_external_review_allowed": False, "reference_count": 0,
        "input_fingerprints": {p["case"]["case_id"]: fingerprint(p) for p in packets},
        "preserved_inputs_sha256": {str(p.relative_to(repo).as_posix()): sha(p) for p in
            [source / "blind_synthetic_evidence.json", source / "identity_lookup.synthetic.json",
             repo / "docs/phase4c1-evaluation.md", repo / "evaluation/phase4c2_attribution_v1/prepared/manifest.json"]},
        "instructions_sha256": sha(instructions_path)}
    immutable(output / "plan.json", plan)
    template = {"version": VERSION, "reference_kind": ROLE, "independent_human_ground_truth": False,
        "run_provenance": {"provider": None, "model": None, "model_version": None, "parameters": None,
            "authorization_id": None, "started_at": None, "completed_at": None, "actual_cost_usd": None,
            "cost_quality": "unknown", "tokens": None, "tools": [], "system_outputs_seen": None,
            "instructions_sha256": plan["instructions_sha256"], "plan_sha256": sha(output / "plan.json")},
        "cases": [{"case_id": p["case"]["case_id"], "evidence_fingerprint": p["case"]["evidence_fingerprint"],
            "input_fingerprint": fingerprint(p), "status": "not_run", "events": [], "units": [],
            "uncertainties": [], "response_sha256": None, "case_provenance": None} for p in packets]}
    immutable(output / "references/ai_references.template.json", template)
    immutable(output / "owner/focused_review.template.json", {"evaluation_kind": ROLE,
        "review_kind": "owner_unblinded_not_independent", "reviewer_id": None, "reviewed_at": None,
        "observed_system_predictions": None, "reference_freeze_sha256": None,
        "selection_rule": "all disagreements, omissions, inconclusive cases, technical failures and critical attribution dimensions",
        "cases": []})
    immutable(output / "system/system_outputs.template.json", {"evaluation_kind": ROLE,
        "execution_status": "not_executed", "paid_calls_authorized": False,
        "reference_freeze_sha256": None, "model": None,
        "cases": [{"case_id": p["case"]["case_id"], "outcome": "not_run", "attempt_started_at": None,
            "generated_at": None, "record_id": None, "output_fingerprint": None, "units": []} for p in packets]})
    immutable(output / "operator/alignment.template.json", {"reference_freeze_sha256": None,
        "system_file_sha256": None, "matches": []})
    return plan


def verify(output: Path, repo: Path) -> dict:
    plan = json.loads((output / "plan.json").read_bytes())
    for name, expected in plan["preserved_inputs_sha256"].items():
        if sha(repo / name) != expected:
            raise ValueError("frozen input differs")
    instructions = repo / "evaluation/phase4c2_attribution_ai_v1/ANNOTATION_INSTRUCTIONS.md"
    if sha(instructions) != plan["instructions_sha256"]:
        raise ValueError("annotation instructions differ")
    packets = json.loads((output / "evaluator/annotation_inputs.json").read_bytes())
    if {p["case"]["case_id"]: fingerprint(p) for p in packets} != plan["input_fingerprints"]:
        raise ValueError("annotation packet differs")
    if any(set(p) != {"instructions", "case", "identity_evidence"} for p in packets):
        raise ValueError("unexpected evaluator input")
    return {"status": "verified", "cases": len(packets), "network_calls": 0}


def freeze(output: Path, submitted: Path, destination: Path, repo: Path) -> dict:
    verify(output, repo)
    plan = json.loads((output / "plan.json").read_bytes())
    data = json.loads(submitted.read_bytes())
    prov = data["run_provenance"]
    if (data.get("reference_kind") != ROLE or data.get("independent_human_ground_truth") is not False
            or prov.get("system_outputs_seen") is not False or prov.get("tools") != []):
        raise ValueError("AI provenance/blindness required; never human ground truth")
    for key in ("provider", "model", "model_version", "parameters", "authorization_id", "started_at", "completed_at"):
        if prov.get(key) is None:
            raise ValueError("incomplete evaluator provenance")
    if prov["model"] not in OPTIONS or prov["provider"] != OPTIONS[prov["model"]]["provider"]:
        raise ValueError("evaluator selection requires a versioned plan")
    if prov["plan_sha256"] != sha(output / "plan.json") or prov["instructions_sha256"] != plan["instructions_sha256"]:
        raise ValueError("evaluator plan/instructions binding mismatch")
    start = datetime.fromisoformat(prov["started_at"]); end = datetime.fromisoformat(prov["completed_at"])
    if start.tzinfo is None or end.tzinfo is None or not start <= end <= datetime.now(timezone.utc):
        raise ValueError("invalid actual evaluation chronology")
    seen = set()
    packets = json.loads((output / "evaluator/annotation_inputs.json").read_bytes())
    evidence_fps = {p["case"]["case_id"]: p["case"]["evidence_fingerprint"] for p in packets}
    source_fields = {p["case"]["case_id"]: {s["evidence_id"]: s["text"] for s in p["case"]["evidence"]} for p in packets}
    identity_count = len(packets[0]["identity_evidence"]["entries"])
    for case in data["cases"]:
        cid = case["case_id"]
        if cid in seen or case.get("input_fingerprint") != plan["input_fingerprints"].get(cid):
            raise ValueError("case identity/binding mismatch")
        if case.get("evidence_fingerprint") != evidence_fps.get(cid):
            raise ValueError("case evidence fingerprint differs")
        seen.add(cid)
        if case["status"] not in {"annotated", "nonconclusive", "abstained", "technical_error"}:
            raise ValueError("pending cases cannot be frozen as completed references")
        if case.get("case_provenance") is None:
            raise ValueError("per-case timestamp/usage/cost/error provenance required")
        cp = case["case_provenance"]
        required = {"started_at", "completed_at", "provider", "model", "parameters", "usage", "cost_usd", "cost_quality", "error_code"}
        if not required.issubset(cp):
            raise ValueError("incomplete per-case provenance fields")
        cs = datetime.fromisoformat(cp["started_at"]); ce = datetime.fromisoformat(cp["completed_at"])
        if cs.tzinfo is None or ce.tzinfo is None or not start <= cs <= ce <= end:
            raise ValueError("invalid case chronology")
        if cp["provider"] != prov["provider"] or cp["model"] != prov["model"] or cp["parameters"] != prov["parameters"]:
            raise ValueError("case evaluator route/parameters differ")
        if cp["cost_quality"] not in {"unknown", "usage_based_estimate"} or (cp["cost_quality"] == "unknown" and cp["cost_usd"] is not None):
            raise ValueError("invalid case cost provenance")
        if cp["cost_quality"] == "usage_based_estimate" and (cp["usage"] is None or cp["cost_usd"] is None or cp["cost_usd"] < 0):
            raise ValueError("known cost requires reported usage and nonnegative estimate")
        if case["status"] != "technical_error" and not case.get("response_sha256"):
            raise ValueError("original evaluator output fingerprint required")
        if case["status"] == "annotated" and not case["units"]:
            raise ValueError("empty annotation must be explicitly nonconclusive")
        unit_ids = set()
        for unit in case["units"]:
            if unit["unit_id"] in unit_ids or set(unit["dimensions"]) != set(DIMENSIONS):
                raise ValueError("duplicate/incomplete annotation unit")
            unit_ids.add(unit["unit_id"])
            for dim in unit["dimensions"].values():
                if dim["status"] not in {"conclusive", "uncertain", "insufficient", "not_applicable"}:
                    raise ValueError("invalid reference conclusion status")
                if dim["status"] == "conclusive" and (dim.get("value") is None or not dim.get("evidence") or not dim.get("rationale")):
                    raise ValueError("conclusive dimension lacks annotation support")
                for ev in dim.get("evidence", []):
                    if "identity_entry_index" in ev:
                        if not isinstance(ev["identity_entry_index"], int) or not 0 <= ev["identity_entry_index"] < identity_count:
                            raise ValueError("neutral identity evidence index invalid")
                    elif (ev.get("evidence_id") not in source_fields[cid] or not ev.get("quote")
                          or ev["quote"] not in source_fields[cid][ev["evidence_id"]]):
                        raise ValueError("reference quote not present in declared synthetic field")
    if seen != set(plan["input_fingerprints"]):
        raise ValueError("all 32 cases including failed/nonconclusive must be retained")
    if destination.exists():
        existing = json.loads(destination.read_bytes())
        if existing["reference_content_fingerprint"] != fingerprint(data) or existing["references"] != data:
            raise ValueError("frozen references differ; never overwrite")
        return {"status": "references_frozen", "cases": len(seen), "freeze_sha256": sha(destination)}
    seal = {"version": VERSION, "reference_kind": ROLE,
        "independent_human_ground_truth": False, "submitted_file_sha256": sha(submitted),
        "reference_content_fingerprint": fingerprint(data), "frozen_at": datetime.now(timezone.utc).isoformat(),
        "references": data, "nacho_stage": "pending_separate_authorization_after_freeze"}
    immutable(destination, seal)
    return {"status": "references_frozen", "cases": len(seen), "freeze_sha256": sha(destination)}


def compare(reference_freeze: Path, system_file: Path, alignment_file: Path) -> dict:
    """Agreement with frozen AI references only; never human-ground-truth metrics."""
    from collections import Counter
    seal = json.loads(reference_freeze.read_bytes())
    refs = seal["references"]
    if seal["reference_kind"] != ROLE or fingerprint(refs) != seal["reference_content_fingerprint"]:
        raise ValueError("AI reference seal differs")
    system = json.loads(system_file.read_bytes()); alignment = json.loads(alignment_file.read_bytes())
    if alignment.get("reference_freeze_sha256") != sha(reference_freeze) or alignment.get("system_file_sha256") != sha(system_file):
        raise ValueError("alignment not bound to frozen files")
    ref_cases = {r["case_id"]: r for r in refs["cases"]}
    sys_cases = {r["case_id"]: r for r in system["cases"]}
    if len(sys_cases) != len(system["cases"]) or set(sys_cases) != set(ref_cases):
        raise ValueError("all 32 cases, failures and not-run cases required")
    frozen_at = datetime.fromisoformat(seal["frozen_at"])
    for case in sys_cases.values():
        if case["outcome"] != "not_run":
            if not case.get("attempt_started_at"):
                raise ValueError("actual attempt start required")
            timestamp = datetime.fromisoformat(case["attempt_started_at"])
            if timestamp.tzinfo is None or timestamp < frozen_at or not case.get("record_id") or not case.get("output_fingerprint"):
                raise ValueError("system generation must follow reference freeze and be traceable")
    matches = {}; used_system = set()
    for row in alignment["matches"]:
        key = (row["case_id"], row["reference_unit_id"]); target = (row["case_id"], row["system_unit_id"])
        if key in matches or target in used_system:
            raise ValueError("ambiguous alignment; no first-match choice")
        if not any(u["unit_id"] == key[1] for u in ref_cases[key[0]]["units"]) or not any(u["unit_id"] == target[1] for u in sys_cases[target[0]]["units"]):
            raise ValueError("alignment unit does not exist")
        matches[key] = target[1]; used_system.add(target)
    counts = {d: Counter() for d in DIMENSIONS}; outcomes = Counter(); queue = []
    for cid, ref_case in ref_cases.items():
        sys_case = sys_cases[cid]; outcome = sys_case["outcome"]
        if outcome not in {"not_run", "interpreted", "abstained", "rejected", "invalid_response", "transport_error", "unresolved"}:
            raise ValueError("unknown system outcome")
        outcomes[outcome] += 1
        units = {u["unit_id"]: u for u in sys_case["units"]}
        if len(units) != len(sys_case["units"]):
            raise ValueError("duplicate system unit")
        for ru in ref_case["units"]:
            su = units.get(matches.get((cid, ru["unit_id"])))
            for dim in DIMENSIONS:
                rd = ru["dimensions"][dim]; dc = counts[dim]; dc["reference_units"] += 1
                if rd["status"] != "conclusive":
                    dc["nonconclusive_reference"] += 1
                elif outcome != "interpreted":
                    dc[outcome] += 1
                elif su is None or dim not in su["dimensions"]:
                    dc["omission"] += 1
                else:
                    dc["compared"] += 1
                    dc["agreement" if rd["value"] == su["dimensions"][dim] else "disagreement"] += 1
        extras = sum((cid, uid) not in used_system for uid in units)
        queue.append({"case_id": cid, "system_outcome": outcome, "reference_status": ref_case["status"],
                      "extra_system_units": extras, "owner_review_required": True})
    return {"evaluation_kind": ROLE, "independent_human_ground_truth": False,
        "case_outcomes": dict(outcomes), "dimensions": {d: dict(c) for d, c in counts.items()},
        "owner_review_queue": queue, "population_metrics": "not_estimated"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify", "freeze-references", "compare"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--submitted", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--reference-freeze", type=Path)
    parser.add_argument("--system-file", type=Path)
    parser.add_argument("--alignment", type=Path)
    args = parser.parse_args()
    output = args.output or args.repo / "evaluation/phase4c2_attribution_ai_v1/prepared"
    if args.command == "prepare":
        plan = prepare(args.repo, output)
        result = {k: plan[k] for k in ("status", "reference_count", "inference_attempts", "model_options")}
    elif args.command == "verify":
        result = verify(output, args.repo)
    elif args.command == "freeze-references":
        if args.submitted is None or args.destination is None:
            parser.error("--submitted and --destination required")
        result = freeze(output, args.submitted, args.destination, args.repo)
    else:
        if args.reference_freeze is None or args.system_file is None or args.alignment is None or args.destination is None:
            parser.error("--reference-freeze, --system-file, --alignment and --destination required")
        report = compare(args.reference_freeze, args.system_file, args.alignment)
        immutable(args.destination, report)
        result = {"status": "ai_comparison_counts_written", "evaluation_kind": ROLE}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
