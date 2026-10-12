"""Synthetic tool tests; never create adjudications for actual provider cases."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path

import pytest

from investment_system.audit.news_semantic_review import (
    HUMAN_FIELDS, case_id, evaluate_adjudications, select_review_pairs, write_review_bundle,
)
from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry, synthetic_record
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_grouping import build_news_groups_as_of
from investment_system.data.storage.news_store import NewsStore
from scripts.prepare_phase4b_semantic_review import sanitized_summary


def source(tmp_path, reverse=False, future=False):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    records = [synthetic_record(str(index), text, ticker) for index, (text, ticker) in enumerate((
        ("Apple quarterly earnings results show revenue growth in the third quarter", "AAPL"),
        ("Apple quarterly earnings results show revenue details in the third quarter", "AAPL"),
        ("Microsoft quarterly earnings results show revenue growth in the third quarter", "MSFT"),
        ("Apple announces the new phone launch with release information today", "AAPL"),
        ("Apple announces the new tablet launch with release information today", "AAPL"),
        ("Apple announces quarterly earnings results and revenue growth of 12 percent", "AAPL"),
        ("Apple announces quarterly earnings results and revenue growth of 15 percent", "AAPL"),
    ))]
    if future:
        records.append(synthetic_record("future", records[0].headline, available_at=FIXTURE_TIME + timedelta(days=1)))
    store.write_records(list(reversed(records)) if reverse else records)
    return build_news_groups_as_of(store, FIXTURE_TIME, fixture_registry(),
                                  reconstruction_policy="deterministic_reconstruction_v1")


def bundle(tmp_path):
    return select_review_pairs(source(tmp_path), size=12)


def test_selection_ids_seed_and_physical_order_are_reproducible(tmp_path):
    first = select_review_pairs(source(tmp_path / "one"), size=12)
    second = select_review_pairs(source(tmp_path / "two", reverse=True), size=12)
    assert first == second
    assert case_id("left", "right") == case_id("right", "left")
    ids = [row["case_id"] for row in first["blind"]["cases"]]
    assert len(ids) == len(set(ids))
    assert ids == [row["case_id"] for row in first["technical"]["cases"]]


def test_blind_file_has_no_algorithm_scores_or_sampling_categories(tmp_path):
    result = bundle(tmp_path)
    blind = json.dumps(result["blind"])
    for forbidden in ("similarity", "algorithm_pair_evidence", "sampling_categories", "same_event_cluster", "reasons", "prediction_origin"):
        assert forbidden not in blind
    for row in result["blind"]["cases"]:
        assert all(row[field] == "" for field in HUMAN_FIELDS)
        assert row["left"]["summary"] is None


def test_pending_review_never_fabricates_metrics(tmp_path):
    result = bundle(tmp_path)
    evaluation = evaluate_adjudications(result["blind"], result["technical"], result["manifest"])
    assert evaluation["status"] == "human_adjudication_pending"
    assert evaluation["metrics"] is None and evaluation["adjudicated"] == 0
    # Synthetic attributed test data solely exercises incomplete evaluation handling.
    partial = deepcopy(result["blind"])
    partial["cases"][0].update(human_label="uncertain", human_rationale="Synthetic test only",
                              reviewer="synthetic-unit-test", reviewed_at=FIXTURE_TIME.isoformat())
    evaluation = evaluate_adjudications(partial, result["technical"], result["manifest"])
    assert evaluation["metrics"] is None and evaluation["pending"] > 0


def test_attributed_synthetic_completion_and_uncertain_exclusion(tmp_path):
    result = bundle(tmp_path)
    synthetic_labels = deepcopy(result["blind"])
    for row in synthetic_labels["cases"]:
        row.update(human_label="uncertain", human_rationale="Synthetic test of uncertainty",
                   reviewer="synthetic-unit-test", reviewed_at=FIXTURE_TIME.isoformat())
    synthetic_labels["cases"][0]["human_label"] = " uncertain "
    evaluation = evaluate_adjudications(synthetic_labels, result["technical"], result["manifest"])
    assert evaluation["status"] == "human_adjudication_completed"
    assert evaluation["metrics"]["certain_pairs"] == 0
    assert evaluation["metrics"]["pair_duplicate_detection"]["precision"] is None
    assert evaluation["abstention_frequency"] == 1


def test_mismatched_ids_changed_predictions_and_changed_content_are_rejected(tmp_path):
    result = bundle(tmp_path)
    wrong = deepcopy(result["blind"])
    wrong["cases"][0]["case_id"] = "bad"
    with pytest.raises(ValueError, match="IDs"):
        evaluate_adjudications(wrong, result["technical"], result["manifest"])
    changed = deepcopy(result["technical"])
    changed["cases"][0]["algorithm_pair_evidence"]["similarity"] = 0.5
    with pytest.raises(ValueError, match="modified"):
        evaluate_adjudications(result["blind"], changed, result["manifest"])
    wrong = deepcopy(result["blind"])
    wrong["cases"][0]["left"]["headline"] = "altered evidence"
    with pytest.raises(ValueError, match="evidence"):
        evaluate_adjudications(wrong, result["technical"], result["manifest"])


def test_incomplete_attribution_and_naive_review_time_are_rejected(tmp_path):
    result = bundle(tmp_path)
    invalid = deepcopy(result["blind"])
    invalid["cases"][0].update(human_label="uncertain", human_rationale=None,
                               reviewer="synthetic-unit-test", reviewed_at=FIXTURE_TIME.isoformat())
    with pytest.raises(ValueError, match="rationale"):
        evaluate_adjudications(invalid, result["technical"], result["manifest"])
    invalid["cases"][0].update(human_rationale="Synthetic timestamp validation", reviewed_at="2026-01-02T14:00:00")
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_adjudications(invalid, result["technical"], result["manifest"])


def test_metrics_against_handcrafted_synthetic_confusion_matrix():
    # Separate fictitious numerical fixture; never a provider adjudication.
    truths = ("exact_duplicate", "shared_event", "uncertain")
    predictions = ("exact_duplicate", "different", "shared_event")
    blind = {"review_id": "numeric-fixture", "cases": [
        {"case_id": str(index), "left": {}, "right": {}, "human_label": label,
         "human_rationale": "Synthetic numerical fixture", "reviewer": "synthetic-unit-test",
         "reviewed_at": FIXTURE_TIME.isoformat()} for index, label in enumerate(truths)
    ]}
    technical = {"review_id": "numeric-fixture", "cases": [
        {"case_id": str(index), "algorithm_pair_evidence": {"relationship": label},
         "same_duplicate_group": index == 0, "same_event_cluster": index == 0,
         "sampling_categories": []} for index, label in enumerate(predictions)
    ]}
    manifest = {"review_id": "numeric-fixture", "technical_fingerprint": fingerprint(technical),
        "blind_evidence_fingerprint": fingerprint([{k: v for k, v in row.items() if k not in HUMAN_FIELDS}
                                                  for row in blind["cases"]]),
        "dataset_role": "independent_evaluation_pending_human_labels", "limitations": ["Synthetic unit fixture"]}
    evaluation = evaluate_adjudications(blind, technical, manifest)
    assert evaluation["confusion_matrix"]["shared_event"]["different"] == 1
    assert evaluation["confusion_matrix"]["uncertain"]["shared_event"] == 1
    assert evaluation["metrics"]["pair_same_event"]["precision"] == 1
    assert evaluation["metrics"]["pair_same_event"]["recall"] == 0.5
    assert evaluation["metrics"]["pair_duplicate_detection"]["f1"] == 1
    assert evaluation["abstention_frequency"] == pytest.approx(1 / 3)


def test_cutoff_and_previous_development_pairs_are_excluded(tmp_path):
    past = select_review_pairs(source(tmp_path / "past"), size=12)
    future = select_review_pairs(source(tmp_path / "future", future=True), size=12)
    assert past == future
    excluded = select_review_pairs(source(tmp_path / "excluded"), size=12, excluded_provider_pairs=(("0", "1"),))
    assert all({row["left"]["provider_news_id"], row["right"]["provider_news_id"]} != {"0", "1"}
               for row in excluded["technical"]["cases"])


def test_invalid_strict_snapshot_is_rejected(tmp_path):
    snapshot = source(tmp_path)
    changed = snapshot.model_copy(update={"manifest": snapshot.manifest.model_copy(update={"query_mode": "historical_research"})})
    with pytest.raises(ValueError, match="strict"):
        select_review_pairs(changed)


def test_write_preserves_human_edits_and_restricted_publication_is_blocked(tmp_path):
    result = bundle(tmp_path / "news")
    root = tmp_path / "ignored-local"
    destination = root / result["manifest"]["review_id"]
    write_review_bundle(result, destination, allowed_root=root)
    path = destination / "blind.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["cases"][0]["human_rationale"] = "Synthetic draft edit"
    path.write_text(json.dumps(saved), encoding="utf-8")
    write_review_bundle(result, destination, allowed_root=root)
    assert json.loads(path.read_text())["cases"][0]["human_rationale"] == "Synthetic draft edit"
    with pytest.raises(ValueError, match="ignored review root"):
        write_review_bundle(result, tmp_path / "public", allowed_root=root)
    summary = sanitized_summary(result)
    public = json.dumps(summary)
    for row in result["blind"]["cases"]:
        assert row["left"]["headline"] not in public
    assert "cases" not in summary and "technical" not in summary and "human_label" not in summary


def test_gitignore_explicitly_covers_every_local_review_artifact():
    rules = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/data/reports/news/phase4b_semantic_review/" in rules
    assert not any(rule.startswith("!data/reports/news/phase4b_semantic_review") for rule in rules)
