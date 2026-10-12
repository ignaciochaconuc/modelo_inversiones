"""Evaluate fully attributed human adjudications, or report that review is pending."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_system.audit.news_semantic_review import DEFAULT_LOCAL_ROOT, evaluate_adjudications


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    args = parser.parse_args()
    target = args.review_dir.resolve()
    if not target.is_relative_to(DEFAULT_LOCAL_ROOT.resolve()):
        raise ValueError("review directory must remain in the ignored local evidence tree")
    role_file = Path("data/reports/news/phase4b2_local/prior_review_role.json")
    if role_file.exists():
        role = json.loads(role_file.read_text(encoding="utf-8"))
        if role.get("prior_review_id") == target.name and role.get("dataset_role") == "development_diagnostic":
            raise ValueError("this review is now AI-assisted development material, not independent evaluation; original results are preserved")
    inputs = {name: json.loads((target / f"{name}.json").read_text(encoding="utf-8"))
              for name in ("blind", "technical", "manifest")}
    result = evaluate_adjudications(inputs["blind"], inputs["technical"], inputs["manifest"])
    # Evaluation errors can contain case identifiers/rationales. Keep outputs local.
    output = target / "evaluation.json"
    temporary = output.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(result, sort_keys=True, indent=2), encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"status": result["status"], "adjudicated": result["adjudicated"],
                      "pending": result["pending"], "evaluation": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
