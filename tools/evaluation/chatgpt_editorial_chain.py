"""Explicit, owner-authorized editorial chain verification; no normalizations."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re

VERSION = "chatgpt-attribution-review-v2"
MANIFEST_VERSION = "chatgpt-editorial-change-list-v1"
AUTHORIZATION_VERSION = "chatgpt-editorial-authorization-v1"
POLICY = "quote-initial-ascii-case-v1"
TRANSFORMATION = "explicit_authorized_quote_case_corrections_v1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def text_artifact(raw: bytes) -> dict:
    return {"utf8": raw.decode("utf-8"), "sha256": digest(raw)}


def artifact_bytes(value: dict) -> bytes:
    if set(value) != {"utf8", "sha256"} or not isinstance(value["utf8"], str):
        raise ValueError("editorial_artifact_structure_invalid")
    raw = value["utf8"].encode("utf-8")
    if digest(raw) != value["sha256"]:
        raise ValueError("editorial_artifact_hash_mismatch")
    return raw


def verify_chain(original: bytes, corrected: bytes, manifest: dict, authorization: dict,
                 packet: dict, parser, validator, timestamp, fingerprint) -> tuple[dict, dict]:
    """Reconstruct declared ASCII quote-case substitutions and preserve all else.

    Hashes bind the owner's explicit authorization to immutable artifacts; they
    are not digital signatures proving the identity of a human or platform.
    """
    manifest_fields = {"version", "policy", "block_id", "packet_sha256", "original_sha256",
                       "corrected_sha256", "changes", "legacy_artifact_manifest"}
    auth_fields = {"version", "approved", "authorized_action", "authorized_by", "recorded_by",
                   "recorded_at", "owner_authorized_at", "authorization_basis", "block_id",
                   "policy", "original_sha256", "corrected_sha256", "manifest_sha256",
                   "allowed_changes_fingerprint", "legacy_manifest_sha256"}
    if set(manifest) != manifest_fields or manifest["version"] != MANIFEST_VERSION or manifest["policy"] != POLICY:
        raise ValueError("unsupported_editorial_manifest")
    if (set(authorization) != auth_fields or authorization["version"] != AUTHORIZATION_VERSION
            or authorization["approved"] is not True
            or authorization["authorized_action"] != "import_editorially_corrected_annotation"
            or authorization["policy"] != POLICY
            or any(not isinstance(authorization[k], str) or not authorization[k].strip()
                   for k in ("authorized_by", "recorded_by", "authorization_basis"))):
        raise ValueError("explicit_owner_authorization_required")
    if (manifest["block_id"] != packet["block_id"] or authorization["block_id"] != packet["block_id"]
            or manifest["original_sha256"] != digest(original) or authorization["original_sha256"] != digest(original)
            or manifest["corrected_sha256"] != digest(corrected) or authorization["corrected_sha256"] != digest(corrected)):
        raise ValueError("editorial_response_hash_or_block_mismatch")
    now = datetime.now(timezone.utc)
    if timestamp(authorization["recorded_at"]) > now:
        raise ValueError("authorization_recorded_in_future")
    if authorization["owner_authorized_at"] is not None and timestamp(authorization["owner_authorized_at"]) > timestamp(authorization["recorded_at"]):
        raise ValueError("invalid_authorization_chronology")
    changes = manifest["changes"]
    if not isinstance(changes, list) or not changes or fingerprint(changes) != authorization["allowed_changes_fingerprint"]:
        raise ValueError("undeclared_or_unauthorized_change_list")
    original_data, original_mode = parser(original.decode("utf-8"))
    corrected_data, corrected_mode = parser(corrected.decode("utf-8"))
    if original_mode != corrected_mode or len(original) != len(corrected):
        raise ValueError("editorial_format_or_length_change_forbidden")
    expected = deepcopy(original_data); reconstructed = bytearray(original)
    used_paths = set(); used_offsets = set()
    change_fields = {"operation", "json_pointer", "case_id", "unit_id", "evidence_id", "before", "after",
                     "byte_offset_zero_based", "byte_before_hex", "byte_after_hex", "performed_by", "reason", "transformed_at"}
    pattern = r"/cases/(0|[1-9]\d*)/units/(0|[1-9]\d*)/dimensions/([a-z_]+)/evidence/(0|[1-9]\d*)/quote"
    sources = {c["case_id"]: {e["evidence_id"]: e["text"] for e in c["evidence"]} for c in packet["cases"]}
    for change in changes:
        if set(change) != change_fields or change["operation"] != "replace_initial_ascii_case_in_quote":
            raise ValueError("unsupported_editorial_operation")
        before, after = change["before"], change["after"]
        if (not isinstance(before, str) or not isinstance(after, str) or not before or not after
                or before[1:] != after[1:] or before[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                or before[0].swapcase() != after[0]):
            raise ValueError("non_editorial_quote_change_forbidden")
        match = re.fullmatch(pattern, change["json_pointer"])
        if not match or change["json_pointer"] in used_paths:
            raise ValueError("editorial_target_not_a_unique_quote_field")
        ci, ui, dim, ei = match.groups()
        try:
            case = original_data["cases"][int(ci)]; unit = case["units"][int(ui)]
            evidence = unit["dimensions"][dim]["evidence"][int(ei)]
        except (KeyError, IndexError, TypeError):
            raise ValueError("editorial_pointer_does_not_exist") from None
        if (case["case_id"] != change["case_id"] or unit["unit_id"] != change["unit_id"]
                or evidence != {"evidence_id": change["evidence_id"], "quote": before}
                or case["case_id"] not in sources or change["evidence_id"] not in sources[case["case_id"]]
                or after not in sources[case["case_id"]][change["evidence_id"]]):
            raise ValueError("editorial_quote_identity_or_exact_grounding_invalid")
        offset = change["byte_offset_zero_based"]
        if (type(offset) is not int or offset in used_offsets or original.count(before.encode("utf-8")) != 1
                or original.find(before.encode("utf-8")) != offset
                or change["byte_before_hex"] != before[0].encode().hex()
                or change["byte_after_hex"] != after[0].encode().hex()):
            raise ValueError("editorial_byte_location_or_patch_invalid")
        if (any(not isinstance(change[k], str) or not change[k].strip() for k in ("performed_by", "reason"))
                or timestamp(change["transformed_at"]) > now):
            raise ValueError("editorial_responsibility_or_timestamp_invalid")
        reconstructed[offset] = ord(after[0])
        expected["cases"][int(ci)]["units"][int(ui)]["dimensions"][dim]["evidence"][int(ei)]["quote"] = after
        used_paths.add(change["json_pointer"]); used_offsets.add(offset)
    if bytes(reconstructed) != corrected or corrected_data != expected:
        raise ValueError("undeclared_bytes_or_semantic_annotation_changes")
    legacy = manifest["legacy_artifact_manifest"]
    if legacy is not None:
        legacy_raw = artifact_bytes(legacy); old, _ = parser(legacy_raw.decode("utf-8"))
        if legacy["sha256"] != authorization["legacy_manifest_sha256"] or len(changes) != 1:
            raise ValueError("legacy_manifest_authorization_mismatch")
        change = changes[0]
        links = {"block_id": manifest["block_id"], "original_sha256": digest(original), "corrected_sha256": digest(corrected),
                 "before": change["before"], "after": change["after"], "json_pointer": change["json_pointer"],
                 "case_id": change["case_id"], "unit_id": change["unit_id"], "evidence_id": change["evidence_id"],
                 "byte_offset_zero_based": change["byte_offset_zero_based"], "byte_before_hex": change["byte_before_hex"],
                 "byte_after_hex": change["byte_after_hex"], "performed_by": change["performed_by"],
                 "reason": change["reason"], "transformed_at": change["transformed_at"], "authorized_by": authorization["authorized_by"]}
        if (old.get("transformation_version") != "b04-editorial-artifact-v1" or old.get("new_chatgpt_generation") is not False
                or old.get("bytes_changed") != 1 or any(old.get(k) != v for k, v in links.items())
                or old.get("packet_sha256") != manifest["packet_sha256"]):
            raise ValueError("legacy_manifest_does_not_describe_exact_chain")
    elif authorization["legacy_manifest_sha256"] is not None:
        raise ValueError("required_legacy_manifest_missing")
    validator(corrected_data, packet)  # Exactly the unchanged original validator.
    try:
        validator(original_data, packet)
        original_validation = {"status": "passed", "code": None}
    except ValueError as error:
        original_validation = {"status": "rejected", "code": str(error)}
    return corrected_data, original_validation


def verify_record(record: dict, packet: dict, parser, validator, timestamp, fingerprint) -> dict:
    """Self-contained chain verification, also used during mixed-version freeze."""
    fields = {"version", "review_kind", "independent_human_ground_truth", "block_id", "packet_sha256", "provenance",
              "source_kind", "new_chatgpt_generation", "original_provider_response", "editorially_corrected_annotation",
              "editorial_correction_manifest", "correction_authorization", "transformation",
              "original_provider_response_validation", "annotations", "record_id"}
    if (set(record) != fields or record["version"] != VERSION or record.get("source_kind") != "editorially_corrected_annotation"
            or record.get("new_chatgpt_generation") is not False or record.get("transformation") != TRANSFORMATION):
        raise ValueError("editorial_import_kind_invalid")
    original = artifact_bytes(record["original_provider_response"])
    corrected = artifact_bytes(record["editorially_corrected_annotation"])
    manifest_raw = artifact_bytes(record["editorial_correction_manifest"])
    auth_raw = artifact_bytes(record["correction_authorization"])
    manifest, _ = parser(manifest_raw.decode("utf-8")); auth, _ = parser(auth_raw.decode("utf-8"))
    if auth["manifest_sha256"] != digest(manifest_raw) or manifest["packet_sha256"] != record["packet_sha256"]:
        raise ValueError("authorization_manifest_or_packet_hash_mismatch")
    data, original_validation = verify_chain(original, corrected, manifest, auth, packet, parser, validator, timestamp, fingerprint)
    if data != record["annotations"] or original_validation != record["original_provider_response_validation"]:
        raise ValueError("editorial_annotations_or_original_diagnostic_mismatch")
    for change in manifest["changes"]:
        if timestamp(change["transformed_at"]) < timestamp(record["provenance"]["completed_at"]):
            raise ValueError("editorial_correction_precedes_evaluator_completion")
    return data
