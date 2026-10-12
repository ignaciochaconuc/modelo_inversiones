"""Offline reproducibility/protection tests; actual licensed evidence optional."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from investment_system.audit.news_semantic_review import HUMAN_FIELDS, evaluate_adjudications, select_review_pairs
from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry, synthetic_record
from investment_system.data.news_grouping import build_news_groups_as_of, load_grouping_parameters
from investment_system.data.storage.news_store import NewsStore
from scripts import run_phase4b2_offline as runner
from scripts import evaluate_phase4b_semantic_review as old_evaluator


def test_targeted_strata_exclude_development_and_keep_predictions_blind(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    text = "Apple announces quarterly earnings results with revenue growth of 12 percent"
    store.write_records([synthetic_record("a", text), synthetic_record("b", text),
                         synthetic_record("c", text.replace("12", "15"))])
    snap = build_news_groups_as_of(store, FIXTURE_TIME, fixture_registry(),
        load_grouping_parameters("config/news_grouping_v1_1.yaml"), reconstruction_policy="deterministic_reconstruction_v1")
    result = select_review_pairs(snap, size=3, seed=4202, targeted_semantic_strata=True,
                                 excluded_provider_pairs=(("a", "c"),))
    assert result == select_review_pairs(snap, size=3, seed=4202, targeted_semantic_strata=True,
                                        excluded_provider_pairs=(("c", "a"),))
    assert result["manifest"]["selected_pairs"] == 2
    assert result["manifest"]["category_selected_counts"]["candidate_exact"] == 1
    for row in result["blind"]["cases"]:
        assert all(not row[key] for key in HUMAN_FIELDS)
        assert "algorithm_pair_evidence" not in row and "sampling_categories" not in row
        assert {row["left"]["provider_news_id"],row["right"]["provider_news_id"]} != {"a","c"}
    assert evaluate_adjudications(result["blind"],result["technical"],result["manifest"])["metrics"] is None
    # All-uncertain synthetic test only; never generate reference labels from predictions.
    labels = deepcopy(result["blind"])
    for row in labels["cases"]:
        row.update(human_label="uncertain",human_rationale="Synthetic evaluator test",reviewer="unit-test",reviewed_at=FIXTURE_TIME.isoformat())
    done = evaluate_adjudications(labels,result["technical"],result["manifest"])
    assert "candidate_exact" in done["by_sampling_category"]
    assert done["metrics"]["certain_pairs"] == 0


def test_old_review_cannot_be_renewed_as_independent_after_role_sidecar(tmp_path, monkeypatch):
    root = tmp_path / "old"
    target = root / "old-review"
    target.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    role_file = Path("data/reports/news/phase4b2_local/prior_review_role.json")
    role_file.parent.mkdir(parents=True)
    role_file.write_text(json.dumps({"prior_review_id":"old-review","dataset_role":"development_diagnostic"}))
    monkeypatch.setattr(old_evaluator,"DEFAULT_LOCAL_ROOT",root)
    monkeypatch.setattr("sys.argv",["evaluate", "--review-dir",str(target)])
    with pytest.raises(ValueError, match="development material"):
        old_evaluator.main()
    assert not list(target.iterdir())


def test_original_protected_bytes_and_new_local_review_when_available():
    baseline = runner.LOCAL / "protected_files.json"
    if not baseline.exists():
        pytest.skip("licensed offline artifacts intentionally not distributed")
    assert runner.protected_hashes() == runner.read_json(baseline)
    summary = runner.read_json(runner.PUBLIC)
    target = runner.LOCAL / "reviews" / summary["new_review_id"]
    blind, technical, manifest = [runner.read_json(target / f"{name}.json") for name in ("blind","technical","manifest")]
    old = runner.read_json(runner.OLD_REVIEW / "blind.json")
    assert {r["case_id"] for r in blind["cases"]}.isdisjoint(r["case_id"] for r in old["cases"])
    assert len(blind["cases"]) == 40
    assert all(r["raw_capture_ids"][side] for r in technical["cases"] for side in ("left","right"))
    assert evaluate_adjudications(blind,technical,manifest)["metrics"] is None
    assert all(c["old_identity_reproduced"] for c in summary["comparisons"])
    assert "/data/reports/news/phase4b2_local/" in Path(".gitignore").read_text()


def test_immutable_output_never_replaces_existing_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    runner.immutable_json(path,{"original":1})
    before = path.read_bytes()
    runner.immutable_json(path,{"original":1})
    with pytest.raises(ValueError,match="existing evidence differs"):
        runner.immutable_json(path,{"original":2})
    assert path.read_bytes() == before


def test_synthetic_blind_supplement_hides_coverage_cues():
    supplement = runner.read_json(Path("tests/fixtures/news_semantic_evaluation_v1_1.json"))
    blind = runner.synthetic_blind(supplement)
    assert len(blind["cases"]) == 9
    assert all("cue" not in r and all(not r[k] for k in HUMAN_FIELDS) for r in blind["cases"])
