"""Prepare one owner-authorized editorial artifact; never import or normalize."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

OLD_QUOTE = "an industry table includes a company named Marlow"
NEW_QUOTE = "An industry table includes a company named Marlow"
CASE_ID = "S-40501aee7851586a"
UNIT_ID = "U4"
ORIGINAL_SHA256 = "3cf681fcdb7581acdd14cdb8cf82e54d585bec6c4027a109879043b9553c1097"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build_candidate(raw: bytes, parse, validate, packet: dict) -> tuple[bytes, dict]:
    """One ASCII byte only; preserve CRLF, formatting and every other JSON value."""
    if digest(raw) != ORIGINAL_SHA256:
        raise ValueError("original_response_hash_differs")
    original, mode = parse(raw.decode("utf-8"))
    ci = next(i for i, c in enumerate(original["cases"]) if c["case_id"] == CASE_ID)
    ui = next(i for i, u in enumerate(original["cases"][ci]["units"]) if u["unit_id"] == UNIT_ID)
    evidence = original["cases"][ci]["units"][ui]["dimensions"]["corporate_identity"]["evidence"][0]
    if evidence != {"evidence_id": CASE_ID + ":summary", "quote": OLD_QUOTE}:
        raise ValueError("target_quote_or_evidence_identity_differs")
    source = next(c for c in packet["cases"] if c["case_id"] == CASE_ID)
    field = next(e["text"] for e in source["evidence"] if e["evidence_id"] == evidence["evidence_id"])
    if NEW_QUOTE not in field:
        raise ValueError("replacement_not_in_original_source")
    needle = OLD_QUOTE.encode()
    if raw.count(needle) != 1:
        raise ValueError("literal_location_not_unique")
    offset = raw.index(needle)
    candidate = raw[:offset] + b"A" + raw[offset+1:]
    if len(candidate) != len(raw) or [i for i, (a, b) in enumerate(zip(raw, candidate)) if a != b] != [offset]:
        raise ValueError("correction_must_change_exactly_one_byte")
    expected = deepcopy(original)
    expected["cases"][ci]["units"][ui]["dimensions"]["corporate_identity"]["evidence"][0]["quote"] = NEW_QUOTE
    corrected, corrected_mode = parse(candidate.decode("utf-8"))
    if corrected != expected or corrected_mode != mode:
        raise ValueError("non_target_annotation_or_format_changed")
    validate(corrected, packet)  # Entire block, no exceptions or weakened rules.
    trace = {
        "transformation_version": "b04-editorial-artifact-v1",
        "artifact_kind": "post_evaluation_editorial_correction_not_original_evaluator_output",
        "new_chatgpt_generation": False,
        "authorized_by": "Nacho",
        "performed_by": "Codex acting on the owner's explicit instruction",
        "reason": "Literal evidence quote differs from source only in its initial uppercase letter.",
        "block_id": "B04", "case_id": CASE_ID, "unit_id": UNIT_ID,
        "field": "corporate_identity.evidence[0].quote",
        "json_pointer": f"/cases/{ci}/units/{ui}/dimensions/corporate_identity/evidence/0/quote",
        "evidence_id": evidence["evidence_id"],
        "before": OLD_QUOTE, "after": NEW_QUOTE,
        "byte_offset_zero_based": offset, "byte_before_hex": "61", "byte_after_hex": "41",
        "bytes_changed": 1, "original_sha256": digest(raw), "corrected_sha256": digest(candidate),
        "byte_length_unchanged": True, "all_other_bytes_unchanged": True,
        "all_other_annotation_values_unchanged": True, "full_annotation_validation": "passed",
        "import_status": "pending_versioned_editorial_correction_protocol",
        "current_importer_used": False,
        "limitations": [
            "This artifact is not a new evaluator response or an independent adjudication.",
            "Successful literal/structural validation does not certify semantic entailment.",
            "Current import/freeze does not explicitly reconstruct editorial derivations; no primary import is performed."
        ]
    }
    return candidate, trace


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("manual_review", Path(__file__).with_name("prepare_chatgpt_review.py"))
    review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
    base = repo / "data/cache/news_attribution_review/chatgpt-v1"
    source = base / "responses/B04.txt"
    destination = base / "responses/B04-corrected-v1.txt"
    audit = base / "corrections/B04-editorial-v1.json"
    packet_root = repo / "evaluation/phase4c2_chatgpt_review_v1/prepared"
    raw = source.read_bytes()
    candidate, trace = build_candidate(raw, review.parse, review.validate_annotations,
                                       review.packet_for(repo, packet_root, "B04"))
    trace.update(original_path=source.relative_to(repo).as_posix(),
                 corrected_path=destination.relative_to(repo).as_posix(),
                 packet_sha256=review.sha(packet_root / "packets/B04.md"))
    if destination.exists() and destination.read_bytes() != candidate:
        raise ValueError("existing_corrected_artifact_differs")
    if audit.exists():
        existing = json.loads(audit.read_bytes())
        if {k: v for k, v in existing.items() if k != "transformed_at"} != trace:
            raise ValueError("existing_transformation_trace_differs")
        trace = existing
    else:
        trace["transformed_at"] = datetime.now(timezone.utc).isoformat()
    if not destination.exists():
        # Artifact generation preserves source bytes; no text/newline reserialization.
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(candidate)
    review.write_json(audit, trace)
    if source.read_bytes() != raw:
        raise ValueError("original_response_changed")
    print(json.dumps({"status": "corrected_artifact_validated_not_imported", "bytes_changed": 1,
                      "original_sha256": trace["original_sha256"], "corrected_sha256": trace["corrected_sha256"]}))


if __name__ == "__main__":
    main()
