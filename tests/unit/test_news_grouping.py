from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from investment_system.data.news_entities import eligible_registry_entries, resolve_entities
from investment_system.data.news_evaluation import FIXTURE_TIME, evaluate_entity_examples, evaluate_labelled_pairs, fixture_registry, synthetic_record
from investment_system.data.news_grouping import canonical_url, classify_pair, complete_link_groups, load_grouping_parameters
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry, NewsEntityRegistry, NewsGroupingParameters


def test_labelled_development_duplicate_precision_and_adversarial_abstention():
    report = evaluate_labelled_pairs(NewsGroupingParameters())
    assert report["metrics"]["development"]["duplicates"]["fp"] == 0
    assert report["metrics"]["development"]["duplicates"]["tp"] >= 1
    assert report["metrics"]["frozen_evaluation"]["duplicates"]["fp"] == 0


def test_independent_entity_scenario_labels():
    report = evaluate_entity_examples()
    assert not report["errors"]
    assert report["abstentions"] == 3 and report["security_ambiguities"] == 1


def test_url_alone_cannot_merge_different_revisions():
    a = synthetic_record("a", "Apple filed lawsuit in federal court over software licensing agreement today", url="https://example.test/article")
    b = synthetic_record("b", "Apple settled lawsuit in federal court over software licensing agreement today", url="https://example.test/article")
    pair = classify_pair(a, b, ("apple",), FIXTURE_TIME, NewsGroupingParameters())
    assert pair.relationship == "different"
    assert "matching_url_support_only" in pair.reasons
    assert canonical_url("https://example.test/a?utm_source=x&id=3#top") == "https://example.test/a?id=3"


@pytest.mark.parametrize("parameters", [NewsGroupingParameters(), load_grouping_parameters("config/news_grouping_v1_1.yaml")])
def test_complete_link_does_not_infer_transitive_event(parameters):
    a = synthetic_record("a", "Apple announces quarterly earnings results and revenue for third quarter today")
    b = synthetic_record("b", a.headline)
    c = synthetic_record("c", a.headline)
    ids = ["a", "b", "c"]
    pair = classify_pair(a, b, ("apple",), FIXTURE_TIME, parameters)
    pairs = {("a", "b"): pair, ("b", "c"): pair, ("a", "c"): pair.model_copy(update={"relationship": "different"})}
    assert complete_link_groups(ids, pairs, {"exact_duplicate"}) == [("a", "b"), ("c",)]


def test_high_similarity_different_product_and_spelled_quarter_are_not_events():
    for left, right in (
        ("Apple announces the new phone launch with release information today", "Apple announces the new tablet launch with release information today"),
        ("Apple announces third quarter earnings results with revenue information today", "Apple announces fourth quarter earnings results with revenue information today"),
    ):
        a, b = synthetic_record("a", left), synthetic_record("b", right)
        pair = classify_pair(a, b, ("apple",), FIXTURE_TIME, NewsGroupingParameters())
        assert pair.similarity > 0.70 and pair.relationship == "different"


def test_roundup_update_is_not_editorial_duplicate_or_single_event():
    left = synthetic_record("a", "Dow Jones Futures: Yields Move Higher; Samsung, Micron, Taiwan Semi, Sandisk In Focus", summary="Apple earnings analyst coverage report for today")
    right = synthetic_record("b", "Dow Jones Futures Fall As Yields Move Higher; Samsung, Micron, Taiwan Semi, Sandisk In Focus", summary=left.summary)
    pair = classify_pair(left, right, ("apple",), FIXTURE_TIME, NewsGroupingParameters())
    assert pair.similarity > 0.8 and pair.relationship == "different"


def test_entity_names_do_not_imply_share_class_and_support_multiple_entities():
    base = fixture_registry().entries[0]
    registry = NewsEntityRegistry(version="test", universe_description="synthetic", entries=(
        base,
        base.model_copy(update={"entity_id": "alphabet", "corporate_name": "Alphabet", "security_id": "alphabet-a", "ticker": "GOOGL", "aliases": ("Google",)}),
        base.model_copy(update={"entity_id": "alphabet", "corporate_name": "Alphabet", "security_id": "alphabet-c", "ticker": "GOOG", "aliases": ("Google",)}),
    ))
    record = synthetic_record("multi", "Apple and Google announce a joint research project", "")
    links = resolve_entities(record, registry.entries, FIXTURE_TIME, FIXTURE_TIME, registry.version, "resolver")
    assert {link.entity_id for link in links} == {"apple", "alphabet"}
    assert any(link.status == "ambiguous_security" and link.security_id is None for link in links)


def test_bare_letters_and_substrings_do_not_resolve_tickers():
    base = fixture_registry().entries[0]
    entries = tuple(base.model_copy(update={"ticker": ticker, "entity_id": ticker, "corporate_name": name, "aliases": ()}) for ticker, name in (("T", "AT&T"), ("V", "Visa"), ("C", "Citigroup")))
    for text in ("T V C are mathematical symbols", "Visual tools alphabetic testing"):
        links = resolve_entities(synthetic_record("letters", text, ""), entries, FIXTURE_TIME, FIXTURE_TIME, "test", "resolver")
        assert all(link.status == "unresolved" for link in links)
    links = resolve_entities(synthetic_record("explicit", "$T and NYSE:V cooperate", ""), entries, FIXTURE_TIME, FIXTURE_TIME, "test", "resolver")
    assert {link.ticker for link in links} == {"T", "V"}


def test_known_at_and_effective_date_are_separate_and_half_open():
    original = fixture_registry().entries[0]
    new = original.model_copy(update={"ticker": "NEW", "effective_from": date(2026, 1, 2), "known_at": FIXTURE_TIME + timedelta(days=1)})
    old = original.model_copy(update={"ticker": "OLD", "effective_to": date(2026, 1, 2)})
    registry = NewsEntityRegistry(version="test", universe_description="synthetic", entries=(old, new))
    eligible = eligible_registry_entries(registry, FIXTURE_TIME, False)
    assert eligible == (old,)
    links = resolve_entities(synthetic_record("dated", "Corporate update", "NEW"), eligible, FIXTURE_TIME, FIXTURE_TIME, "test", "resolver")
    assert links[0].status == "unresolved"
    links = resolve_entities(synthetic_record("dated", "Corporate update", "NEW"), registry.entries, FIXTURE_TIME, FIXTURE_TIME, "test", "resolver")
    assert links[0].ticker == "NEW" and links[0].temporal_status == "retrospective_registry"
