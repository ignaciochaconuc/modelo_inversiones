"""Record explicit owner-authorized B04 import scope without altering old artifacts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-owner-authorized-import", action="store_true")
    args = parser.parse_args()
    if not args.confirm_owner_authorized_import:
        parser.error("explicit owner authorization confirmation required")
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("review", Path(__file__).with_name("prepare_chatgpt_review.py"))
    review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
    chain = review.editorial_chain_module()
    base = repo / "data/cache/news_attribution_review/chatgpt-v1"
    legacy_raw = (base / "corrections/B04-editorial-v1.json").read_bytes()
    legacy, _ = review.parse(legacy_raw.decode("utf-8"))
    original = (base / "responses/B04.txt").read_bytes()
    corrected = (base / "responses/B04-corrected-v1.txt").read_bytes()
    change = {k: legacy[k] for k in ("json_pointer", "case_id", "unit_id", "evidence_id", "before", "after",
        "byte_offset_zero_based", "byte_before_hex", "byte_after_hex", "performed_by", "reason", "transformed_at")}
    change["operation"] = "replace_initial_ascii_case_in_quote"
    manifest = {"version": chain.MANIFEST_VERSION, "policy": chain.POLICY, "block_id": "B04",
        "packet_sha256": legacy["packet_sha256"], "original_sha256": chain.digest(original),
        "corrected_sha256": chain.digest(corrected), "changes": [change],
        "legacy_artifact_manifest": chain.text_artifact(legacy_raw)}
    manifest_path = base / "corrections/B04-editorial-change-list-v1.json"
    review.write_json(manifest_path, manifest)
    auth = {"version": chain.AUTHORIZATION_VERSION, "approved": True,
        "authorized_action": "import_editorially_corrected_annotation", "authorized_by": "Nacho",
        "recorded_by": "Codex recording the owner's explicit instruction", "recorded_at": None,
        "owner_authorized_at": None,
        "authorization_basis": "Owner explicitly requested the one-letter B04 correction and subsequently authorized a versioned import preserving the original, corrected copy and legacy manifest. CLI confirmation records that instruction; no digital signature or exact owner message timestamp is inferred.",
        "block_id": "B04", "policy": chain.POLICY, "original_sha256": chain.digest(original),
        "corrected_sha256": chain.digest(corrected), "manifest_sha256": review.sha(manifest_path),
        "allowed_changes_fingerprint": review.fp(manifest["changes"]), "legacy_manifest_sha256": chain.digest(legacy_raw)}
    auth_path = base / "corrections/B04-editorial-import-authorization-v1.json"
    if auth_path.exists():
        existing = json.loads(auth_path.read_bytes()); auth["recorded_at"] = existing["recorded_at"]
        if auth != existing:raise ValueError("existing_authorization_differs")
    else:
        auth["recorded_at"] = datetime.now(timezone.utc).isoformat()
    packet = review.packet_for(repo, repo / "evaluation/phase4c2_chatgpt_review_v1/prepared", "B04")
    chain.verify_chain(original, corrected, manifest, auth, packet, review.parse, review.validate_annotations, review.timestamp, review.fp)
    review.write_json(auth_path, auth)
    print(json.dumps({"status": "explicit_editorial_authorization_recorded", "manifest_sha256": review.sha(manifest_path),
                      "authorization_sha256": review.sha(auth_path), "changes": len(manifest["changes"])}))


if __name__ == "__main__":
    main()
