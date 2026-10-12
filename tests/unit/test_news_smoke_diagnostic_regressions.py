"""New synthetic regressions; no real-response fixtures or acceptance changes."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest
from pydantic import ValidationError

from investment_system.agents.news_interpretation.schemas import (
    EvidenceSpan, InterpretationPayload, ModelConfiguration, NewsInterpretationRequest,
)
from investment_system.agents.news_interpretation.replay import replay_response, validate_payload_evidence
from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry, synthetic_record
from investment_system.llm.schemas import LLMResponse


def request(headline="Birch announced financing.", summary=None, registry=()):
    return NewsInterpretationRequest(news=synthetic_record("new-diagnostic-case", headline,
        ticker="", summary=summary), decision_time=FIXTURE_TIME, registry_entries=registry)


def span(req, quote=None, field="headline", occurrence=0):
    source = next(e for e in req.evidence if e.field == field)
    quote = quote or source.text
    start = source.text.index(quote, occurrence)
    return dict(evidence_id=source.evidence_id, start=start, end=start+len(quote), quote=quote)


def payload(req):
    cite = span(req)
    return dict(status="interpreted", events=[dict(event_key="1", event_type="financing",
        description="Financing announcement", state="confirmed", stage="announced",
        state_evidence=cite, evidence=[cite], entities=[])])


def replay(req, candidate):
    config = ModelConfiguration(provider="offline", model="synthetic-diagnostic")
    response = LLMResponse(provider=config.provider, model=config.model, content=json.dumps(candidate),
        generated_at=FIXTURE_TIME+timedelta(seconds=1), input_tokens=10,
        cached_input_tokens=0, output_tokens=10, latency_ms=1)
    return replay_response(req, response, config, validated_at=FIXTURE_TIME+timedelta(seconds=2))


def test_exact_quotes_with_inclusive_end_rejected_without_mutating_input():
    req = request()
    candidate = payload(req)
    original = deepcopy(candidate)
    candidate["events"][0]["state_evidence"] = {**span(req), "end":len(req.news.headline)-1}
    invalid = deepcopy(candidate)
    with pytest.raises(ValidationError):
        InterpretationPayload.model_validate(candidate)
    assert replay(req, candidate).status == "invalid_response"
    assert candidate == invalid
    assert replay(req, original).status == "interpreted"


def test_length_consistent_but_displaced_quote_fails_only_grounding_stage():
    req = request("Birch announced financing. A separate sentence follows.")
    candidate = payload(req)
    cite = span(req, "Birch announced financing.")
    wrong = {**cite, "start":cite["start"]+1, "end":cite["end"]+1}
    candidate["events"][0].update(state_evidence=wrong, evidence=[wrong])
    typed = InterpretationPayload.model_validate(candidate)
    with pytest.raises(ValueError, match="invented quotation, offsets"):
        validate_payload_evidence(typed, req)
    assert replay(req, candidate).status == "invalid_response"


def test_field_specific_offsets_not_concatenated_headline_summary_offsets():
    req = request(summary="A brief summary. Birch announced a new financing agreement.")
    candidate = payload(req)
    exact = span(req, "Birch announced a new financing agreement.", field="summary")
    delta = len(req.news.headline)
    wrong = {**exact, "start":exact["start"]+delta, "end":exact["end"]+delta}
    candidate["events"][0].update(state_evidence=wrong, evidence=[wrong])
    assert replay(req, candidate).status == "invalid_response"
    candidate["events"][0].update(state_evidence=exact, evidence=[exact])
    assert replay(req, candidate).status == "interpreted"


def test_unicode_offsets_are_codepoints_not_utf8_or_utf16():
    req = request("Birch 🚀 announced financing.")
    exact = span(req)
    assert EvidenceSpan.model_validate(exact).end == len(req.news.headline)
    for wrong_end in (len(req.news.headline.encode("utf-8")), len(req.news.headline.encode("utf-16-le"))//2):
        with pytest.raises(ValidationError):
            EvidenceSpan.model_validate({**exact, "end":wrong_end})
    assert replay(req, payload(req)).status == "interpreted"


def test_repeated_quotes_have_multiple_valid_offsets_no_unique_auto_repair():
    sentence = "Birch announced financing."
    req = request(sentence+" Then: "+sentence)
    assert req.news.headline.count(sentence) == 2
    first, second = span(req, sentence), span(req, sentence, occurrence=1)
    assert first["start"] != second["start"]
    for cite in (first, second):
        candidate = payload(req)
        candidate["events"][0].update(state_evidence=cite, evidence=[cite])
        assert replay(req, candidate).status == "interpreted"


def test_unambiguous_human_date_still_rejected_by_current_iso_literal_policy():
    req = request("Birch announced financing on Jan. 02, 2026.")
    candidate = payload(req)
    candidate["events"][0].update(event_date="2026-01-02", date_evidence=span(req, "Jan. 02, 2026"))
    with pytest.raises(ValidationError, match="ISO source form"):
        InterpretationPayload.model_validate(candidate)
    assert replay(req, candidate).status == "invalid_response"


def test_unknown_date_and_literal_iso_date_controls():
    for req in (request("Birch announced financing on Jan. 02, 2026."),
                request("Birch announced financing on 2026-01-02.")):
        candidate = payload(req)
        assert replay(req, candidate).status == "interpreted"
        if "2026-01-02" in req.news.headline:
            candidate["events"][0].update(event_date="2026-01-02", date_evidence=span(req, "2026-01-02"))
            assert replay(req, candidate).status == "interpreted"


def test_product_name_cannot_inherit_parent_security_identity():
    entry = fixture_registry().entries[0].model_copy(update=dict(entity_id="oak-data",
        corporate_name="OakData", aliases=(), ticker="OAK", security_id="OAK-synthetic"))
    req = request("Birch announced financing for software using OakData Cloud.", registry=(entry,))
    candidate = payload(req)
    entity = dict(name="OakData Cloud", role="subject", ticker="OAK", evidence=span(req, "OakData Cloud"))
    candidate["events"][0]["entities"] = [entity]
    typed = InterpretationPayload.model_validate(candidate)
    with pytest.raises(ValueError, match="identity not backed by eligible registry"):
        validate_payload_evidence(typed, req)
    assert replay(req, candidate).status == "invalid_response"
    # Separate synthetic control, not an automatic correction of the real response.
    candidate["events"][0]["entities"] = [{**entity, "ticker":None}]
    assert replay(req, candidate).status == "interpreted"


def test_abstention_remains_available_without_fabricated_evidence():
    candidate = dict(status="abstained", abstention_reasons=["insufficient_evidence"])
    assert replay(request(), candidate).status == "abstained"
