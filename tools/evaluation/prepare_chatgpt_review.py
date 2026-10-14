"""Manual ChatGPT review instruments. Strictly offline, no API/client/credentials."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROLE = "chatgpt_assisted_exploratory_review"
VERSION = "chatgpt-attribution-review-v1"
DIMENSIONS = ("corporate_identity", "participation", "role", "relationship", "ticker_link",
              "event_state", "event_stage", "impact_support")
STATUSES = {"annotated", "nonconclusive", "abstained", "technical_error"}
EDITORIAL_VERSION = "chatgpt-attribution-review-v2"


def editorial_chain_module():
    """Load the offline extension lazily; preparation and v1 remain unchanged."""
    spec = importlib.util.spec_from_file_location("chatgpt_editorial_chain", Path(__file__).with_name("chatgpt_editorial_chain.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def fp(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_once(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ValueError("artifact_exists_with_different_content")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    write_once(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def parse(text: str) -> tuple[dict, str]:
    """Only complete JSON or one complete JSON fence; retain exact raw text."""
    mode = "plain_json"
    match = re.fullmatch(r"\s*```(?:json)?\s*\n([\s\S]*?)\n```\s*", text)
    if match:
        text = match[1]; mode = "single_json_fence_unwrapped"
    def invalid_constant(value):
        raise ValueError("nonfinite_json")
    try:
        data = json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (ValueError, TypeError, RecursionError):
        raise ValueError("invalid_response_json") from None
    if not isinstance(data, dict):
        raise ValueError("response_must_be_object")
    return data, mode


def prepare(repo: Path, output: Path) -> dict:
    root = repo / "evaluation/phase4c2_attribution_v1/prepared/reviewer"
    original = json.loads((root / "blind_synthetic_evidence.json").read_bytes())
    identity = json.loads((root / "identity_lookup.synthetic.json").read_bytes())
    if original.get("fictional") is not True or identity.get("fictional") is not True or len(original["cases"]) != 32:
        raise ValueError("only_original_32_synthetic_cases_allowed")
    if len({c["case_id"] for c in original["cases"]}) != 32:
        raise ValueError("duplicate_original_case")
    instructions_path = repo / "evaluation/phase4c2_chatgpt_review_v1/ANNOTATION_INSTRUCTIONS.md"
    instructions = instructions_path.read_text(encoding="utf-8")
    artifacts = []; blocks = []
    for offset in range(0, 32, 4):
        bid = f"B{offset // 4 + 1:02d}"
        packet = {"block_id": bid, "cases": original["cases"][offset:offset+4], "identity_evidence": identity}
        rendered = instructions + "\n## Bloque para anotar\n\n```json\n" + json.dumps(packet, ensure_ascii=False, indent=2) + "\n```\n"
        write_json(output / f"packets/{bid}.json", packet)
        write_once(output / f"packets/{bid}.md", rendered)
        provenance = {"review_kind": ROLE, "interface": "chatgpt_conversation", "block_id": bid,
            "recorded_by": None, "conversation_reference": None, "visible_model_label": None,
            "model_label_visibility": "not_recorded", "model_snapshot": None, "api_parameters": None,
            "api_tokens": None, "api_calls": 0, "paid_api_cost_usd": 0,
            "subscription_cost_usd": None, "subscription_cost_note": "not_measured",
            "started_at": None, "completed_at": None, "fresh_conversation_declared": None,
            "system_outputs_seen": None, "context_limitations": [], "response_limitations": [],
            "packet_sha256": sha(output / f"packets/{bid}.md")}
        write_json(output / f"templates/{bid}.provenance.json", provenance)
        write_json(output / f"templates/{bid}.response.json", {"block_id": bid, "limitations": [],
            "cases": [{"case_id": c["case_id"], "evidence_fingerprint": c["evidence_fingerprint"],
                       "status": "not_run", "events": [], "units": [], "uncertainties": []} for c in packet["cases"]]})
        artifacts.extend([f"packets/{bid}.json", f"packets/{bid}.md", f"templates/{bid}.provenance.json", f"templates/{bid}.response.json"])
        blocks.append({"block_id": bid, "case_ids": [c["case_id"] for c in packet["cases"]]})
    manifest = {"version": VERSION, "review_kind": ROLE, "status": "chatgpt_review_prepared_pending_execution",
        "independent_human_ground_truth": False, "api_calls": 0, "references_generated": 0,
        "blocks": blocks, "source_sha256": {p.relative_to(repo).as_posix(): sha(p) for p in
            [root / "blind_synthetic_evidence.json", root / "identity_lookup.synthetic.json", instructions_path]},
        "artifact_sha256": {name: sha(output / name) for name in artifacts}}
    write_json(output / "manifest.json", manifest)
    return manifest


def verify(repo: Path, output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_bytes())
    if manifest["review_kind"] != ROLE or len(manifest["blocks"]) != 8:
        raise ValueError("invalid_preparation_manifest")
    for name, expected in manifest["source_sha256"].items():
        if sha(repo / name) != expected:
            raise ValueError("original_source_or_instructions_changed")
    for name, expected in manifest["artifact_sha256"].items():
        if sha(output / name) != expected:
            raise ValueError("prepared_artifact_changed")
    original = json.loads((repo / "evaluation/phase4c2_attribution_v1/prepared/reviewer/blind_synthetic_evidence.json").read_bytes())["cases"]
    rebuilt = []
    for block in manifest["blocks"]:
        packet = json.loads((output / f"packets/{block['block_id']}.json").read_bytes())
        if set(packet) != {"block_id", "cases", "identity_evidence"} or len(packet["cases"]) != 4:
            raise ValueError("invalid_blind_packet")
        rebuilt.extend(packet["cases"])
    if rebuilt != original:
        raise ValueError("original_cases_or_fingerprints_changed")
    return {"status": "verified", "blocks": 8, "cases": 32, "api_calls": 0}


def packet_for(repo: Path, output: Path, block_id: str) -> dict:
    verify(repo, output)
    if block_id not in {f"B{i:02d}" for i in range(1, 9)}:
        raise ValueError("unknown_block_id")
    return json.loads((output / f"packets/{block_id}.json").read_bytes())


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("invalid_actual_timestamp") from None
    if result.tzinfo is None:
        raise ValueError("timestamp_requires_timezone")
    return result


def validate_provenance(prov: dict, output: Path, block_id: str) -> None:
    expected_fields = set(json.loads((output / f"templates/{block_id}.provenance.json").read_bytes()))
    if set(prov) != expected_fields:
        raise ValueError("unexpected_or_missing_provenance_fields")
    if (prov.get("review_kind") != ROLE or prov.get("interface") != "chatgpt_conversation"
            or prov.get("block_id") != block_id or not prov.get("recorded_by")
            or prov.get("fresh_conversation_declared") is not True or prov.get("system_outputs_seen") is not False):
        raise ValueError("manual_blind_review_provenance_required")
    for name in ("api_parameters", "api_tokens", "model_snapshot"):
        if name not in prov or prov[name] is not None:
            raise ValueError("unknown_api_details_must_remain_null")
    if prov.get("api_calls") != 0 or prov.get("paid_api_cost_usd") != 0:
        raise ValueError("api_execution_not_allowed")
    if any(not isinstance(prov[k], list) or any(not isinstance(item, str) for item in prov[k])
           for k in ("context_limitations", "response_limitations")):
        raise ValueError("invalid_provenance_limitations")
    if prov.get("model_label_visibility") not in {"visible_label", "not_exposed"}:
        raise ValueError("record_real_model_label_visibility")
    if ((prov["model_label_visibility"] == "visible_label" and not prov.get("visible_model_label"))
            or (prov["model_label_visibility"] == "not_exposed" and prov.get("visible_model_label") is not None)):
        raise ValueError("model_label_provenance_conflict")
    if prov.get("packet_sha256") != sha(output / f"packets/{block_id}.md"):
        raise ValueError("conversation_input_fingerprint_mismatch")
    if not timestamp(prov.get("started_at")) <= timestamp(prov.get("completed_at")) <= datetime.now(timezone.utc):
        raise ValueError("invalid_review_chronology")


def validate_annotations(data: dict, packet: dict) -> None:
    if set(data) != {"block_id", "limitations", "cases"} or data["block_id"] != packet["block_id"]:
        raise ValueError("response_block_structure_mismatch")
    if not isinstance(data["limitations"], list) or not isinstance(data["cases"], list):
        raise ValueError("invalid_response_arrays")
    expected = {c["case_id"]: c for c in packet["cases"]}; seen = set()
    for case in data["cases"]:
        if set(case) != {"case_id", "evidence_fingerprint", "status", "events", "units", "uncertainties"}:
            raise ValueError("case_structure_mismatch")
        cid = case["case_id"]
        if cid not in expected or cid in seen or case["evidence_fingerprint"] != expected[cid]["evidence_fingerprint"]:
            raise ValueError("case_identity_or_revision_mismatch")
        seen.add(cid)
        if case["status"] not in STATUSES or any(not isinstance(case[k], list) for k in ("events", "units", "uncertainties")):
            raise ValueError("pending_or_invalid_annotation")
        event_ids = [e["event_id"] for e in case["events"]]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("duplicate_event_id")
        fields = {e["evidence_id"]: e["text"] for e in expected[cid]["evidence"]}; unit_ids = set()
        for unit in case["units"]:
            if (set(unit) != {"unit_id", "event_id", "name", "dimensions"} or not unit["name"]
                    or unit["unit_id"] in unit_ids or (unit["event_id"] is not None and unit["event_id"] not in event_ids)
                    or set(unit["dimensions"]) != set(DIMENSIONS)):
                raise ValueError("unit_identity_or_dimensions_invalid")
            unit_ids.add(unit["unit_id"])
            for dim in unit["dimensions"].values():
                if set(dim) != {"status", "value", "rationale", "evidence"} or dim["status"] not in {"conclusive", "uncertain", "insufficient", "not_applicable"} or not isinstance(dim["evidence"], list):
                    raise ValueError("invalid_dimension_structure")
                if dim["status"] == "conclusive" and (dim["value"] is None or not dim["rationale"] or not dim["evidence"]):
                    raise ValueError("conclusive_reference_without_support")
                for ev in dim["evidence"]:
                    if set(ev) == {"identity_entry_index"}:
                        index = ev["identity_entry_index"]
                        if type(index) is not int or not 0 <= index < len(packet["identity_evidence"]["entries"]):
                            raise ValueError("unknown_neutral_identity_evidence")
                    elif (set(ev) != {"evidence_id", "quote"} or ev.get("evidence_id") not in fields
                            or not isinstance(ev.get("quote"), str) or not ev["quote"] or ev["quote"] not in fields[ev["evidence_id"]]):
                        raise ValueError("quote_not_in_declared_case_field")
        if case["status"] == "annotated" and not case["units"]:
            raise ValueError("empty_annotation_must_be_nonconclusive")
    if seen != set(expected):
        raise ValueError("all_four_cases_required")


def import_response(repo: Path, output: Path, bid: str, response: Path, provenance: Path, destination: Path, failure: str | None = None) -> dict:
    packet = packet_for(repo, output, bid); prov = json.loads(provenance.read_bytes())
    validate_provenance(prov, output, bid)
    raw = response.read_bytes(); raw_text = raw.decode("utf-8")
    if failure is None:
        data, transform = parse(raw_text); validate_annotations(data, packet)
    else:
        if failure not in {"response_truncated", "no_response", "invalid_json", "usage_limit", "unusable_response"}:
            raise ValueError("unknown_operator_failure_code")
        transform = "operator_recorded_block_failure_not_annotation"
        data = {"block_id": bid, "limitations": [failure], "cases": [
            {"case_id": c["case_id"], "evidence_fingerprint": c["evidence_fingerprint"], "status": "technical_error",
             "events": [], "units": [], "uncertainties": [failure]} for c in packet["cases"]]}
    record = {"version": VERSION, "review_kind": ROLE, "independent_human_ground_truth": False,
        "block_id": bid, "packet_sha256": sha(output / f"packets/{bid}.md"), "provenance": prov,
        "raw_response_utf8": raw_text, "raw_response_sha256": hashlib.sha256(raw).hexdigest(),
        "transformation": transform, "annotations": data}
    record["record_id"] = fp(record)
    write_json(destination, record)
    return {"status": "response_imported", "block_id": bid, "record_id": record["record_id"]}


def verify_import_record(repo: Path, output: Path, record: dict, bid: str) -> dict:
    """Validate either original v1 or explicit editorial v2 without rewriting it."""
    content = {k: v for k, v in record.items() if k != "record_id"}
    if (record.get("record_id") != fp(content) or record["review_kind"] != ROLE
            or record["independent_human_ground_truth"] is not False or record["block_id"] != bid):
        raise ValueError("import_record_integrity_failed")
    packet = packet_for(repo, output, bid); validate_provenance(record["provenance"], output, bid)
    if record["packet_sha256"] != sha(output / f"packets/{bid}.md"):
        raise ValueError("imported_packet_fingerprint_mismatch")
    if record["version"] == EDITORIAL_VERSION:
        return editorial_chain_module().verify_record(record, packet, parse, validate_annotations, timestamp, fp)
    if record["version"] == VERSION:
        if hashlib.sha256(record["raw_response_utf8"].encode()).hexdigest() != record["raw_response_sha256"]:
            raise ValueError("original_response_hash_failed")
        if record["transformation"] != "operator_recorded_block_failure_not_annotation":
            parsed, mode = parse(record["raw_response_utf8"])
            if mode != record["transformation"] or parsed != record["annotations"]:
                raise ValueError("response_transformation_mismatch")
        elif any(c["status"] != "technical_error" or c["units"] for c in record["annotations"]["cases"]):
            raise ValueError("operator_failure_cannot_create_reference_labels")
        validate_annotations(record["annotations"], packet)
        return record["annotations"]
    raise ValueError("unsupported_import_record_version")


def import_editorial_response(repo: Path, output: Path, bid: str, original: Path, corrected: Path,
                             manifest: Path, authorization: Path, provenance: Path, destination: Path) -> dict:
    """Opt-in v2; stores evaluator original and post-evaluation annotation apart."""
    packet = packet_for(repo, output, bid); prov = json.loads(provenance.read_bytes())
    validate_provenance(prov, output, bid)
    module = editorial_chain_module()
    original_raw = original.read_bytes(); corrected_raw = corrected.read_bytes()
    manifest_raw = manifest.read_bytes(); auth_raw = authorization.read_bytes()
    manifest_data, _ = parse(manifest_raw.decode("utf-8")); auth_data, _ = parse(auth_raw.decode("utf-8"))
    if auth_data["manifest_sha256"] != module.digest(manifest_raw):
        raise ValueError("authorization_manifest_hash_mismatch")
    annotations, original_validation = module.verify_chain(original_raw, corrected_raw, manifest_data, auth_data,
        packet, parse, validate_annotations, timestamp, fp)
    record = {"version": EDITORIAL_VERSION, "review_kind": ROLE, "independent_human_ground_truth": False,
        "block_id": bid, "packet_sha256": sha(output / f"packets/{bid}.md"), "provenance": prov,
        "source_kind": "editorially_corrected_annotation", "new_chatgpt_generation": False,
        "original_provider_response": module.text_artifact(original_raw),
        "editorially_corrected_annotation": module.text_artifact(corrected_raw),
        "editorial_correction_manifest": module.text_artifact(manifest_raw),
        "correction_authorization": module.text_artifact(auth_raw),
        "transformation": module.TRANSFORMATION, "original_provider_response_validation": original_validation,
        "annotations": annotations}
    record["record_id"] = fp(record)
    verify_import_record(repo, output, record, bid)
    write_json(destination, record)
    return {"status": "editorial_response_imported", "block_id": bid, "record_id": record["record_id"]}


def freeze(repo: Path, output: Path, imports: Path, destination: Path) -> dict:
    verify(repo, output); records = []; all_cases = []
    if {p.name for p in imports.glob("*.json")} != {f"B{i:02d}.json" for i in range(1, 9)}:
        raise ValueError("exactly_eight_imported_blocks_required")
    for i in range(1, 9):
        bid = f"B{i:02d}"; record = json.loads((imports / f"{bid}.json").read_bytes())
        verify_import_record(repo, output, record, bid)
        records.append(record); all_cases.extend(record["annotations"]["cases"])
    payload = {"review_kind": ROLE, "independent_human_ground_truth": False, "records": records, "cases": all_cases}
    if destination.exists():
        existing = json.loads(destination.read_bytes())
        if existing["references"] != payload or existing["reference_fingerprint"] != fp(payload):
            raise ValueError("frozen_references_cannot_be_overwritten")
    else:
        version = EDITORIAL_VERSION if any(r["version"] == EDITORIAL_VERSION for r in records) else VERSION
        write_json(destination, {"version": version, "review_kind": ROLE, "independent_human_ground_truth": False,
            "frozen_at": datetime.now(timezone.utc).isoformat(), "reference_fingerprint": fp(payload), "references": payload})
    return {"status": "references_frozen", "cases": len(all_cases), "freeze_sha256": sha(destination)}


def compare(seal_path: Path, system_path: Path, alignment_path: Path) -> dict:
    seal = json.loads(seal_path.read_bytes()); refs = seal["references"]
    if seal["review_kind"] != ROLE or seal["independent_human_ground_truth"] is not False or fp(refs) != seal["reference_fingerprint"]:
        raise ValueError("chatgpt_reference_freeze_invalid")
    system = json.loads(system_path.read_bytes()); alignment = json.loads(alignment_path.read_bytes())
    if alignment.get("reference_freeze_sha256") != sha(seal_path) or alignment.get("system_file_sha256") != sha(system_path):
        raise ValueError("alignment_fingerprints_do_not_match")
    rc = {c["case_id"]: c for c in refs["cases"]}; sc = {c["case_id"]: c for c in system["cases"]}
    if len(rc) != 32 or len(refs["cases"]) != 32 or len(sc) != 32 or len(system["cases"]) != 32 or set(rc) != set(sc):
        raise ValueError("all_original_32_cases_required")
    maps = {}; used = set()
    for row in alignment["matches"]:
        key = (row["case_id"], row["reference_unit_id"]); target = (row["case_id"], row["system_unit_id"])
        if key in maps or target in used or key[0] not in rc or not any(u["unit_id"] == key[1] for u in rc[key[0]]["units"]) or not any(u["unit_id"] == target[1] for u in sc[key[0]]["units"]):
            raise ValueError("invalid_or_ambiguous_manual_alignment")
        maps[key] = target[1]; used.add(target)
    dimensions = {d: Counter() for d in DIMENSIONS}; outcomes = Counter(); review = []
    for cid, rcase in rc.items():
        s = sc[cid]; outcome = s["outcome"]
        if outcome not in {"interpreted", "abstained", "rejected", "invalid_response", "transport_error", "unresolved", "not_run"}:
            raise ValueError("unknown_system_outcome")
        if outcome != "not_run" and (timestamp(s.get("attempt_started_at")) < timestamp(seal["frozen_at"]) or not s.get("record_id") or not s.get("output_fingerprint")):
            raise ValueError("system_attempt_must_follow_reference_freeze")
        outcomes[outcome] += 1; su = {u["unit_id"]: u for u in s["units"]}
        if len(su) != len(s["units"]):raise ValueError("duplicate_system_unit")
        for ru in rcase["units"]:
            match = su.get(maps.get((cid, ru["unit_id"])))
            for d in DIMENSIONS:
                rd = ru["dimensions"][d]; count = dimensions[d]; count["reference_units"] += 1
                if rd["status"] != "conclusive":count["nonconclusive"] += 1
                elif outcome != "interpreted":count[outcome] += 1
                elif match is None or d not in match["dimensions"]:count["omission"] += 1
                else:count["agreement" if rd["value"] == match["dimensions"][d] else "disagreement"] += 1
        review.append({"case_id": cid, "reference_status": rcase["status"], "system_outcome": outcome,
            "extra_system_units": sum((cid, uid) not in used for uid in su), "owner_review_required": True})
    return {"review_kind": ROLE, "independent_human_ground_truth": False, "case_outcomes": dict(outcomes),
        "reference_case_statuses": dict(Counter(c["status"] for c in rc.values())),
        "dimensions": {d: dict(c) for d, c in dimensions.items()}, "owner_review_queue": review,
        "population_metrics": "not_estimated"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify", "import-response", "import-editorial", "verify-import", "record-failure", "freeze", "compare"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2]); parser.add_argument("--output", type=Path)
    for name in ("response", "provenance", "destination", "imports", "reference-freeze", "system-file", "alignment", "original", "corrected", "correction-manifest", "authorization", "record"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--block"); parser.add_argument("--reason")
    args = parser.parse_args(); output = args.output or args.repo / "evaluation/phase4c2_chatgpt_review_v1/prepared"
    try:
        if args.command == "prepare":
            m = prepare(args.repo, output); result = {"status": m["status"], "blocks": 8, "cases": 32, "api_calls": 0}
        elif args.command == "verify":result = verify(args.repo, output)
        elif args.command == "import-editorial":
            if not all((args.block, args.original, args.corrected, args.correction_manifest, args.authorization, args.provenance, args.destination)):
                parser.error("--block --original --corrected --correction-manifest --authorization --provenance --destination required")
            result = import_editorial_response(args.repo, output, args.block, args.original, args.corrected,
                args.correction_manifest, args.authorization, args.provenance, args.destination)
        elif args.command == "verify-import":
            if args.block is None or args.record is None:parser.error("--block --record required")
            record = json.loads(args.record.read_bytes()); verify_import_record(args.repo, output, record, args.block)
            result = {"status": "import_verified", "block_id": args.block, "version": record["version"], "record_id": record["record_id"]}
        elif args.command in {"import-response", "record-failure"}:
            if not all((args.block, args.response, args.provenance, args.destination)):parser.error("--block --response --provenance --destination required")
            if args.command == "record-failure" and args.reason is None:parser.error("--reason required")
            result = import_response(args.repo, output, args.block, args.response, args.provenance, args.destination,
                                     args.reason if args.command == "record-failure" else None)
        elif args.command == "freeze":
            if args.imports is None or args.destination is None:parser.error("--imports --destination required")
            result = freeze(args.repo, output, args.imports, args.destination)
        else:
            if not all((args.reference_freeze, args.system_file, args.alignment, args.destination)):parser.error("--reference-freeze --system-file --alignment --destination required")
            report = compare(args.reference_freeze, args.system_file, args.alignment); write_json(args.destination, report)
            result = {"status": "chatgpt_comparison_written", "review_kind": ROLE}
    except (ValueError, KeyError, TypeError, IndexError, OSError, UnicodeError):
        # Static, sanitized diagnostic: never response text, paths, or exception repr.
        parser.exit(2, "offline_review_validation_failed; inspect inputs locally, no content logged\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
