"""Development regressions, never reference labels for the new blind set."""
from datetime import timedelta
import json
from pathlib import Path

import pytest

from investment_system.data.news_editorial_normalization import normalize_editorial_headline
from investment_system.data.news_evaluation import FIXTURE_TIME, synthetic_record
from investment_system.data.news_grouping import classify_pair, classify_pair_v1, load_grouping_parameters, tokens
from investment_system.data.schemas.news_enrichment import NewsGroupingParameters, NewsClusterSnapshot


PARAMETERS = load_grouping_parameters("config/news_grouping_v1_1.yaml")
A = "Apple cuts iPhone 18 Pro component orders amid soft demand"
B = "Apple cuts iPhone18 Pro component orders amid sluggish demand- Nikkei"
OLD_REVIEW = Path("data/reports/news/phase4b_semantic_review/8b446f52bcfcaac6f40541e7e9298db5371f60e68e584775fc4e6b492afe4ca0")


def pair(a=A, b=B, *, common=("apple",), summary_a=None, summary_b=None, parameters=PARAMETERS):
    return classify_pair(synthetic_record("left", a, summary=summary_a),
                         synthetic_record("right", b, summary=summary_b), common, FIXTURE_TIME, parameters)


def test_development_headline_false_negative_old_and_new():
    assert pair(parameters=NewsGroupingParameters()).relationship == "different"
    result = pair()
    assert result.relationship == "editorial_duplicate"
    assert result.headline_similarity == 1
    assert result.similarity < PARAMETERS.editorial_threshold
    assert "global_cosine_reported_not_editorial_gate" in result.reasons


def test_real_original_false_negative_and_diagnosis_when_evidence_available():
    if not (OLD_REVIEW / "source_snapshot.json").exists():
        pytest.skip("licensed real evidence intentionally not distributed")
    snapshot = NewsClusterSnapshot.model_validate_json((OLD_REVIEW / "source_snapshot.json").read_text())
    a = next(r for r in snapshot.inputs if r.provider_news_id == "142765169")
    b = next(r for r in snapshot.inputs if r.provider_news_id == "142749411")
    stored = next(p for p in snapshot.pair_evidence if {p.left_revision_id,p.right_revision_id} == {a.revision_id,b.revision_id})
    original = classify_pair(a, b, stored.common_entities, stored.available_at, snapshot.manifest.parameters)
    assert original == stored
    assert original.similarity == pytest.approx(0.550364706926844)
    assert original.headline_similarity == pytest.approx(0.5789473684210527)
    result = classify_pair(a, b, stored.common_entities, stored.available_at, PARAMETERS)
    assert result.relationship == "editorial_duplicate"
    assert result.left_revision_id == a.revision_id and result.right_revision_id == b.revision_id


@pytest.mark.parametrize("a,b", [
    (A.replace("18", "17"), B),
    (A + " by 20 percent", B + " by 30 percent"),
    (A.replace("cuts", "increases"), B),
    (A.replace("cuts", "approved"), B.replace("cuts", "rejected")),
    (A.replace("cuts", "announced"), B.replace("cuts", "completed")),
    (A.replace("cuts", "rumor"), B.replace("cuts", "confirmed")),
    (A.replace("cuts", "guidance raised"), B.replace("cuts", "guidance lowered")),
    (A.replace("Apple", "Microsoft"), B),
    (A.replace("cuts", "does not cut"), B),
    (A.replace("iPhone", "iPad"), B),
    (A, B.replace("sluggish demand", "sluggish sales")),
    (A, B.replace("Nikkei", "a new product")),
])
def test_adversarial_factual_changes_never_merge(a, b):
    assert pair(a, b).relationship == "different"


@pytest.mark.parametrize("summary_a,summary_b", [
    ("Orders were approved", "Orders were rejected"),
    ("Deal announced", "Deal completed"),
    ("Shipment target 20", "Shipment target 25"),
    ("Shipment target 20", "No shipment target"),
    ("Guidance raised", "Guidance lowered"),
    ("Unconfirmed rumor", "Confirmed information"),
])
def test_relevant_updates_in_summary_abstain(summary_a, summary_b):
    assert pair(summary_a=summary_a, summary_b=summary_b).relationship == "different"


def test_normalization_is_scoped_preserves_identifiers_and_negation():
    assert tokens(normalize_editorial_headline(B)) == tokens(A)
    value = normalize_editorial_headline("Apple does not cut iPhone17 orders on sluggish demand- Nikkei")
    assert "not" in tokens(value) and "17" in tokens(value) and "18" not in tokens(value)
    assert "sluggish sales" in normalize_editorial_headline("sluggish sales")
    assert "nikkei reports" in normalize_editorial_headline("Nikkei reports soft demand")
    assert "nikkei raised" in normalize_editorial_headline("Apple guidance - Nikkei raised estimates")
    assert "pixel18" in normalize_editorial_headline("Pixel18")
    assert normalize_editorial_headline(value) == value


def test_common_entity_and_time_required_not_merely_ticker_date():
    assert pair(common=()).relationship == "different"
    assert pair(A, "Apple investor newsletter covering unrelated legal proceedings in court today").relationship == "different"
    a, b = synthetic_record("a", A), synthetic_record("b", B, published_at=FIXTURE_TIME + timedelta(hours=49))
    assert classify_pair(a,b,("apple",),FIXTURE_TIME,PARAMETERS).relationship == "different"


def test_versions_thresholds_contracts_and_legacy_are_explicit():
    old = NewsGroupingParameters()
    assert PARAMETERS.model_dump(exclude={"algorithm_version", "text_version"}) == old.model_dump(exclude={"algorithm_version", "text_version"})
    a,b = synthetic_record("a",A),synthetic_record("b",B)
    assert classify_pair(a,b,("apple",),FIXTURE_TIME,old) == classify_pair_v1(a,b,("apple",),FIXTURE_TIME,old)
    with pytest.raises(ValueError, match="version"):
        pair(parameters=old.model_copy(update={"algorithm_version":"news-groups-v1.1"}))
    assert pair(A,A).relationship == "exact_duplicate"
    assert pair().relationship != "exact_duplicate"


def test_new_supplement_is_unlabelled_separate_and_not_a_regression_oracle():
    data = json.loads(Path("tests/fixtures/news_semantic_evaluation_v1_1.json").read_text())
    old = json.loads(Path("tests/fixtures/news_pairs_v1.json").read_text())
    prior = {r[side] for r in old["cases"] for side in ("left", "right")}
    assert len(data["cases"]) == 9
    assert all(not row["human_label"] for row in data["cases"])
    assert all(row[side] not in prior for row in data["cases"] for side in ("left", "right"))
