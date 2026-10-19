"""Offline corpus quality/integrity tests, not predictions or semantic references."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import re

import pytest

from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest
from investment_system.data.news_hashing import normalized_content_hash

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("development_corpus", REPO/"tools/evaluation/development_corpus.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
AUTHORING = m.read(REPO/m.ROOT/"authoring.json")


def artifacts():
    return m.build(deepcopy(AUTHORING))


def indexed(built):
    packets = {p["case_id"]: p for p in built["corpus.json"]["cases"]}
    return {(p["primary_stratum"], p["variant"]): packets[p["case_id"]]
            for p in built["private-design.json"]["cases"]}


def test_whole_inventory_and_exact_reconstruction():
    built = artifacts()
    assert m.verify(REPO)["cases"] == 24
    assert m.verify(REPO)["provider_calls"] == 0
    assert m.build(deepcopy(AUTHORING)) == built
    assert len({p["case_id"] for p in built["corpus.json"]["cases"]}) == 24
    rows = built["private-design.json"]["cases"]
    assert len({p["family_id"] for p in rows}) == 12
    assert {p["primary_stratum"] for p in rows} == set(m.STRATA)
    assert all(sum(r["family_id"] == p["family_id"] for r in rows) == 2 for p in rows)


def test_primary_evidence_and_content_hashes():
    for p in artifacts()["corpus.json"]["cases"]:
        request = NewsInterpretationRequest.model_validate(p["request"])
        assert p["primary_revision_id"] == request.revision_id
        assert p["request_fingerprint"] == request.request_id
        assert p["evidence_fingerprint"] == request.evidence_fingerprint
        assert {e["field"] for e in p["evidence"]} == {"headline", "summary"}
        assert p["evidence"] == [dict(evidence_id=e.evidence_id, **e.model_dump(mode="json")) for e in request.evidence]
        assert all(e["revision_id"] == request.revision_id for e in p["evidence"])
        assert not request.context_news and request.target is None and request.snapshot is None
        assert request.news.direct_tickers == ()
        content = {key: getattr(request.news, key) for key in (
            "headline", "summary", "content_ref", "source_name", "source_url", "language",
            "direct_tickers", "provider_entities", "published_at", "event_date")}
        assert normalized_content_hash(content) == request.news.content_hash


def test_no_private_metadata_or_labels_in_model_request():
    for p in artifacts()["corpus.json"]["cases"]:
        raw = json.dumps(p["request"])
        for key in ("family_id", "stratum", "secondary_tags", "variant", "expected", "scoring", "counterfactual_axis", "originality_note"):
            assert f'"{key}"' not in raw
        assert re.fullmatch(r"D-[0-9a-f]{16}", p["case_id"])
        assert "v3" not in raw and "draft2" not in raw


def test_fictional_identity_namespace_and_neutrality():
    entries = artifacts()["registry.json"]["entries"]
    assert entries and len({e["security_id"] for e in entries}) == len(entries)
    assert all(e["ticker"].startswith("SYNTH-DEV24-") and len(e["ticker"]) > 10 for e in entries)
    assert all(not e["aliases"] for e in entries)
    assert all(not set(e) & {"participation", "role", "impact", "relationship"} for e in entries)


def test_exact_single_replacement_and_not_a_name_or_figure_swap():
    built = artifacts()
    pairs = indexed(built)
    for f in AUTHORING["families"]:
        a, b = [pairs[(f["stratum"], v)]["request"]["news"] for v in ("a", "b")]
        assert a["headline"] == b["headline"]
        start = len(f["summary_prefix"])
        assert a["summary"][:start] == b["summary"][:start]
        assert a["summary"][start:] == f["a"] and b["summary"][start:] == f["b"]
        assert a["summary"][:start]+f["b"] == b["summary"]
        assert re.sub(r"\d+", "NUMBER", f["a"]) != re.sub(r"\d+", "NUMBER", f["b"])
        assert f["axis"] and f["novelty"]


def test_deliberate_scope_conditions_and_numeric_basis_are_preserved():
    pairs = indexed(artifacts())
    def summary(s, v):
        return pairs[(s, v)]["request"]["news"]["summary"]
    assert "suspends lot releases" in summary("negation", "a")
    assert "does not suspend lot releases" in summary("negation", "b")
    assert "does not disclose the inspector's name" in summary("negation", "a")
    assert "No cash has yet been paid" in summary("temporal_conditions", "b")
    assert "certificate is still outstanding" in summary("temporal_conditions", "a")
    assert "certificate has arrived" in summary("temporal_conditions", "b")
    assert "three months combined, not an individual month" in summary("numeric_fidelity", "a")
    assert "each individual month, not the three months combined" in summary("numeric_fidelity", "b")


def test_future_registry_and_unnamed_actor_do_not_leak():
    built = artifacts()
    pairs = indexed(built)
    for v in ("a", "b"):
        assert pairs[("dates_and_pit", v)]["request"]["registry_entries"] == []
    assert pairs[("insufficient_evidence", "a")]["request"]["registry_entries"] == []
    assert len(pairs[("insufficient_evidence", "b")]["request"]["registry_entries"]) == 1
    future = [e for e in built["registry.json"]["entries"] if e["corporate_name"] == "Yrvexil Bioceramics"]
    assert len(future) == 2
    assert any(e["effective_from"] == "2031-03-22" for e in future)
    assert any(e["known_at"] == "2031-03-21T10:05:00Z" for e in future)


def test_cutoff_boundary_is_inclusive_and_temporal_clocks_not_collapsed():
    a = deepcopy(AUTHORING)
    a["virtual_clock"]["decision_time"] = "2031-03-21T10:05:00Z"
    pairs = indexed(m.build(a))
    assert len(pairs[("dates_and_pit", "a")]["request"]["registry_entries"]) == 1
    for p in artifacts()["corpus.json"]["cases"]:
        r = NewsInterpretationRequest.model_validate(p["request"])
        assert r.news.published_at < r.news.available_at < r.news.ingested_at <= r.decision_time
        assert r.news.event_date is None
        raw = r.model_dump(mode="json")
        raw["decision_time"] = (r.news.available_at-timedelta(seconds=1)).isoformat()
        with pytest.raises(ValueError):
            NewsInterpretationRequest.model_validate(raw)


@pytest.mark.parametrize("mutation", ["duplicate_family", "missing_stratum", "identical_variants", "naive_time", "early_cutoff"])
def test_invalid_authoring_rejected(mutation):
    a = deepcopy(AUTHORING)
    if mutation == "duplicate_family":
        a["families"][1]["key"] = a["families"][0]["key"]
    elif mutation == "missing_stratum":
        a["families"][1]["stratum"] = "announced"
    elif mutation == "identical_variants":
        a["families"][0]["b"] = a["families"][0]["a"]
    elif mutation == "naive_time":
        a["virtual_clock"]["decision_time"] = "2031-03-21T10:04:00"
    else:
        a["virtual_clock"]["decision_time"] = "2031-03-21T10:01:00Z"
    with pytest.raises(ValueError):
        m.build(a)


def test_prior_sources_are_text_only_not_annotations_or_predictions():
    sources = m.prior_sources(REPO)
    assert len(sources) == 80
    assert all(set(s) == {"group", "id", "text"} for s in sources)
    assert {s["group"] for s in sources} == set(m.COMPARATORS)
    assert all("data/cache" not in p for p in m.COMPARATORS)


def test_similarity_detects_identical_and_delexicalized_templates():
    text = "Zoqvir shipped 400 crates after the inspection was finished."
    assert m.similarity(text, text)["token_jaccard"] == 1
    rewritten = "Hqeluv shipped 900 crates after the inspection was finished."
    assert m.similarity(text, rewritten)["delexicalized_bigram_jaccard"] == 1
    assert m.concept_tokens("A permit was withdrawn.") == m.concept_tokens("A restriction suspended operations.") - {"operation"}


def test_originality_recomputes_and_does_not_claim_independence():
    built = artifacts()
    audit = m.originality(REPO, built["corpus.json"])
    assert audit == m.read(REPO/m.ROOT/"originality-audit.json")
    assert audit["comparisons"] == 1920
    assert all(not c["surface_review_flag"] and not c["exact_normalized_match"] for c in audit["cases"])
    assert "independent review pending" in audit["conceptual_review"]


def test_verifier_blocks_tampering_without_overwriting(tmp_path):
    folder = tmp_path/m.ROOT
    folder.mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({"sha256": {m.ROOT+"/authoring.json": "0"*64}}))
    (folder/"authoring.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact_hash_mismatch"):
        m.verify(tmp_path)
    assert (folder/"authoring.json").read_text() == "{}"
