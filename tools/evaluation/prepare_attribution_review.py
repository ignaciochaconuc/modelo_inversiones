"""Offline evaluation instruments only: never route, infer, or export Finnhub text."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

VERSION = "attribution-blind-review-preparation-v1"
CUTOFF = "2026-10-12T13:17:53+00:00"
SEED = "attribution-independent-review-20261013-v1"
SMOKE_REVISION = "cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12"
PATTERNS = {
    "acquisition": r"\bacquir|\bmerger|\bbuyout",
    "contract": r"\bcontract|\bsupply agreement",
    "alliance": r"\bpartner|\balliance|\bcollaborat",
    "product": r"\bproduct|\blaunch|\bdevice",
    "platform": r"\bplatform|\bsoftware|\bcloud",
    "subsidiary": r"\bsubsidiary|\bparent company|\bunit of",
    "competition": r"\bcompet|\brival",
    "regulation": r"\bregulat|\bantitrust|\bFTC\b|\bfine[ds]?\b",
    "incidental": r"\bamong|\bincluding|\broundup|\bstocks to",
}
DIMENSIONS = ("corporate_identity", "participation", "role", "relationship",
              "ticker_link", "impact_support", "event_state", "event_stage")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()


def text_digest(headline: str, summary: str | None) -> str:
    return digest({"headline": headline, "summary": summary or ""})


def immutable_json(path: Path, value: object) -> None:
    """Identical reruns are allowed; never replace evidence or annotations."""
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("prepared artifact differs; create a new evaluation version")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prior_exclusions(repo: Path) -> tuple[set[str], dict[str, str]]:
    """Exclude reviewed 4B articles, not just pairs; do not import predictions."""
    ids = {SMOKE_REVISION}
    files = {}

    def visit(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"revision_id", "news_id", "provider_news_id", "left_revision_id", "right_revision_id"} and isinstance(value, str):
                    ids.add(value)
                elif key == "provider_ids" and isinstance(value, list):
                    ids.update(value)
                else:
                    visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)

    for folder in ("phase4b_semantic_review", "phase4b2_local"):
        for path in sorted((repo / "data/reports/news" / folder).rglob("*.json")):
            if path.name == "source_snapshot.json" or "snapshots" in path.parts:
                continue  # Whole source universe is not an inspected/adjudicated case.
            raw = path.read_bytes()
            files[path.relative_to(repo).as_posix()] = hashlib.sha256(raw).hexdigest()
            visit(json.loads(raw))
    path = repo / "data/reports/news/phase4b_pilot.json"
    raw = path.read_bytes()
    files[path.relative_to(repo).as_posix()] = hashlib.sha256(raw).hexdigest()
    visit(json.loads(raw).get("real_pair_review", {}))
    return ids, files


def select_real_metadata(repo: Path) -> dict:
    """Read already authorized local sources; return no text, URL or source names."""
    from investment_system.data.storage.news_store import NewsStore
    records = NewsStore(repo / "data/raw", repo / "data/processed").read_records()
    ids, exclusion_files = prior_exclusions(repo)
    excluded_records = [r for r in records if r.revision_id in ids or r.news_id in ids or r.provider_news_id in ids]
    excluded_logical = {r.news_id for r in excluded_records}
    excluded_text = {text_digest(r.headline, r.summary) for r in excluded_records}
    cutoff = datetime.fromisoformat(CUTOFF)
    # Strict latest eligible revision, one article and one exact text per selection.
    latest = {}
    for r in sorted(records, key=lambda r: (r.available_at, r.revision_id)):
        if r.available_at <= cutoff:
            latest[r.news_id] = r
    eligible = [r for r in latest.values() if r.news_id not in excluded_logical
                and text_digest(r.headline, r.summary) not in excluded_text]
    pools = {kind: [r for r in eligible if re.search(pattern, r.headline + " " + (r.summary or ""), re.I)]
             for kind, pattern in PATTERNS.items()}
    selected = []; used = set()
    for kind in sorted(PATTERNS, key=lambda k: (len(pools[k]), k)):
        candidates = sorted(pools[kind], key=lambda r: digest([SEED, kind, r.revision_id]))
        count = 0
        for r in candidates:
            evidence_hash = text_digest(r.headline, r.summary)
            if evidence_hash in used or count == 3:
                continue
            used.add(evidence_hash); count += 1
            selected.append({"case_id": "R-" + digest([SEED, r.revision_id])[:16],
                "revision_id": r.revision_id, "news_id": r.news_id,
                "raw_payload_hash": r.raw_payload_hash, "content_hash": r.content_hash,
                "evidence_fingerprint": evidence_hash, "available_at": r.available_at.isoformat(),
                "decision_time": CUTOFF, "sampling_stratum": kind,
                "dataset_role": "real_candidate_metadata_only",
                "content_rights_status": "not_authorized_for_external_review"})
    return {"version": VERSION, "cutoff": CUTOFF, "seed": SEED,
        "selection_method": "lexical enrichment, rare pools first, hash ranking; cues are NOT reference labels",
        "source_records": len(records), "eligible_after_exclusions": len(eligible),
        "excluded_logical_articles": len(excluded_logical),
        "excluded_text_fingerprints": sorted(excluded_text),
        "exclusion_files": exclusion_files, "pool_counts": {k: len(v) for k, v in pools.items()},
        "selected_counts": dict(Counter(r["sampling_stratum"] for r in selected)),
        "content_exported": False, "cases": sorted(selected, key=lambda r: r["case_id"])}


def prepare(repo: Path, output: Path, *, include_real_metadata: bool = True) -> dict:
    sources = json.loads((repo / "evaluation/phase4c2_attribution_v1/synthetic_sources.json").read_text(encoding="utf-8"))
    blind = []; selection = []
    fixture_files = sorted((repo / "tests").rglob("*.json")) + sorted((repo / "tests").rglob("*.py"))
    fixtures_text = "\n".join(p.read_text(encoding="utf-8") for p in fixture_files)
    for row in sources["cases"]:
        if row["headline"] in fixtures_text or SMOKE_REVISION in json.dumps(row):
            raise ValueError("development/evaluation overlap")
        fp = text_digest(row["headline"], row["summary"])
        case_id = "S-" + digest([SEED, fp])[:16]
        blind.append({"case_id": case_id, "evidence_fingerprint": fp,
            "evidence": [{"evidence_id": case_id + ":headline", "field": "headline", "text": row["headline"]},
                         {"evidence_id": case_id + ":summary", "field": "summary", "text": row["summary"]}]})
        selection.append({"case_id": case_id, "source_key": row["key"], "sampling_stratum": row["stratum"],
                          "evidence_fingerprint": fp, "dataset_role": "ai_authored_synthetic_external_review_pending"})
    blind.sort(key=lambda row: row["case_id"])
    real = select_real_metadata(repo) if include_real_metadata else {"cases": []}
    identifiers = sorted([r["case_id"] for r in blind] + [r["case_id"] for r in real["cases"]])
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate case ID")
    lookup = json.loads((repo / "evaluation/phase4c2_attribution_v1/synthetic_identity_lookup.json").read_bytes())
    artifacts = {"reviewer/blind_synthetic_evidence.json": {"version": VERSION, "fictional": True, "cases": blind},
                 "reviewer/identity_lookup.synthetic.json": lookup,
                 "operator/synthetic_selection.json": {"version": VERSION, "cases": selection},
                 "operator/real_candidate_metadata.json": real}
    for reviewer in ("a", "b"):
        artifacts[f"references/human_{reviewer}.template.json"] = {
            "version": VERSION, "reviewer_id": None, "reviewed_at": None,
            "assistance": None, "independence_attestation": None,
            "has_seen_system_outputs": None, "evidence_bundle_fingerprint": digest(blind),
            "cases": [{"case_id": r["case_id"], "evidence_fingerprint": r["evidence_fingerprint"],
                       "review_status": "pending", "events": [], "units": [],
                       "evidence_sufficiency": None, "rationale": None} for r in blind]}
    artifacts["references/ai_assisted.template.json"] = {"version": VERSION,
        "reference_kind": "ai_assisted_never_independent_human", "reviews": []}
    artifacts["system/system_outputs.template.json"] = {"version": VERSION,
        "execution_status": "not_executed", "run_authorized": False,
        "model": None, "settings_fingerprint": None, "model_output_version": "news-economic-selection-v3",
        "prompt_version": "news-interpretation-prompt-v3", "attribution_version": "news-economic-attribution-v1",
        "cases": [{"case_id": cid, "outcome": "not_run", "attempts": 0,
                   "record_id": None, "output_fingerprint": None, "units": [],
                   "rejection_diagnostics": [], "abstention_reason": None, "cost_usd": None} for cid in identifiers]}
    artifacts["operator/alignment.template.json"] = {"version": VERSION, "aligned_after_reference_freeze": False,
        "reference_file_fingerprint": None, "system_file_fingerprint": None, "units": []}
    for filename, value in artifacts.items():
        immutable_json(output / filename, value)
    manifest = {"version": VERSION, "status": "prepared_pending_content_rights_review",
        "seed": SEED, "base_protocol": "docs/phase4c1-evaluation.md",
        "base_protocol_sha256": hashlib.sha256((repo / "docs/phase4c1-evaluation.md").read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256((repo / "evaluation/phase4c2_attribution_v1/synthetic_sources.json").read_bytes()).hexdigest(),
        "synthetic_cases": len(blind), "synthetic_coverage": dict(Counter(r["sampling_stratum"] for r in selection)),
        "real_candidate_cases": len(real["cases"]), "network_requests": 0, "inference_attempts": 0,
        "human_references": 0, "ai_assisted_references": 0, "system_predictions": 0,
        "production_tree_sha256": tree_digest(repo / "src"),
        "config_tree_sha256": tree_digest(repo / "config"),
        "artifact_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in artifacts}}
    immutable_json(output / "manifest.json", manifest)
    return manifest


def tree_digest(root: Path) -> str:
    rows = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    return digest(rows)


def verify(output: Path, repo: Path | None = None) -> dict:
    manifest = json.loads((output / "manifest.json").read_bytes())
    for name, expected in manifest["artifact_sha256"].items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected:
            raise ValueError("prepared artifact fingerprint mismatch")
    if repo is not None:
        if (tree_digest(repo / "src") != manifest["production_tree_sha256"]
                or tree_digest(repo / "config") != manifest["config_tree_sha256"]
                or hashlib.sha256((repo / manifest["base_protocol"]).read_bytes()).hexdigest() != manifest["base_protocol_sha256"]):
            raise ValueError("frozen production/config/protocol differs")
        if manifest["real_candidate_cases"]:
            frozen = json.loads((output / "operator/real_candidate_metadata.json").read_bytes())
            if select_real_metadata(repo) != frozen:
                raise ValueError("real selection/lineage/exclusions differ")
    return {"status": "verified", "artifacts": len(manifest["artifact_sha256"]),
            "synthetic_cases": manifest["synthetic_cases"], "real_candidate_cases": manifest["real_candidate_cases"]}


def compare(alignment: dict) -> dict:
    """Fail closed: compare only independently concluded, traceable frozen units.

    Units are aligned manually after references freeze. No live model invocation,
    semantic auto-adjudication, population precision/recall or return measurement.
    """
    if not alignment.get("aligned_after_reference_freeze") or not alignment.get("reference_file_fingerprint") or not alignment.get("system_file_fingerprint"):
        raise ValueError("reference/system freeze and alignment are required")
    counts = {d: Counter() for d in DIMENSIONS}
    outcomes = Counter(); seen = set()
    for row in alignment["units"]:
        key = (row["case_id"], row["unit_id"], row["dimension"])
        if key in seen or row["dimension"] not in counts:
            raise ValueError("duplicate or unknown comparison unit")
        seen.add(key); dim = counts[row["dimension"]]
        outcomes[row["system_outcome"]] += 1
        dim["total_units"] += 1
        if row["reference_status"] != "conclusive":
            dim["inconclusive_reference"] += 1
            continue
        if (row.get("assistance") != "none" or not row.get("independence_attestation")
                or not row.get("reviewer_id") or not row.get("provenance_verified")
                or not row.get("reference_evidence") or row.get("has_seen_system_outputs") is not False):
            raise ValueError("conclusive independent human provenance required")
        reviewed_at = datetime.fromisoformat(row["reviewed_at"])
        if reviewed_at.tzinfo is None:
            raise ValueError("timezone-aware review time required")
        if row["system_outcome"] == "not_run":
            dim["system_not_run"] += 1
        elif row["system_outcome"] in {"rejected", "invalid_response", "transport_error", "abstained", "unresolved"}:
            dim[row["system_outcome"]] += 1
        elif row["system_outcome"] == "interpreted":
            if row.get("reference_value") is None or row.get("system_value") is None:
                raise ValueError("missing conclusive comparison values")
            dim["conclusive_compared"] += 1
            dim["agreement" if row["reference_value"] == row["system_value"] else "disagreement"] += 1
        else:
            raise ValueError("unknown system outcome")
    return {"status": "comparison_counts_only", "dimensions": {k: dict(v) for k, v in counts.items()},
            "unit_outcomes": dict(outcomes), "population_metrics": "not_estimated"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "verify", "compare"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--alignment", type=Path)
    args = parser.parse_args()
    output = args.output or args.repo / "evaluation/phase4c2_attribution_v1/prepared"
    if args.command == "prepare":
        manifest = prepare(args.repo.resolve(), output)
        result = {k: manifest[k] for k in ("status", "synthetic_cases", "real_candidate_cases", "network_requests", "inference_attempts")}
    elif args.command == "verify":
        result = verify(output, args.repo)
    else:
        if args.alignment is None:
            parser.error("--alignment required")
        result = compare(json.loads(args.alignment.read_bytes()))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
