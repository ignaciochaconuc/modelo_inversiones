"""Code-level diagnostic witnesses, not a replay/evaluation of historical cases.

All text below is newly authored fiction. No cache, expired record, model, prompt
or frozen reference is loaded; production validators are exercised unchanged.
"""
from datetime import datetime, timezone

import pytest

from investment_system.agents.news_interpretation.schemas import (
    EvidenceSpan, ExtractedNewsEvent, InterpretationPayload, NewsInterpretationRequest, NumericClaim,
)
from investment_system.agents.news_interpretation.replay import validate_payload_evidence
from investment_system.agents.news_interpretation.grounding import resolve_quote_fields, QuoteResolutionError
from investment_system.data.news_evaluation import synthetic_record


def example(text, stage, negated=False):
    now = datetime.now(timezone.utc)
    news = synthetic_record('new-offline-diagnostic-only', text, '', available_at=now, published_at=None)
    request = NewsInterpretationRequest(news=news, decision_time=now)
    span = EvidenceSpan(evidence_id=request.evidence[0].evidence_id, start=0, end=len(text), quote=text)
    event = ExtractedNewsEvent(event_key='new-diagnostic', event_type='ma', description='Fictional test statement',
        state='confirmed', stage=stage, negated=negated, state_evidence=span, evidence=(span,))
    return request, InterpretationPayload(status='interpreted', events=(event,)), span


@pytest.mark.parametrize('text,stage,message', [
    ('Juniper has acquired Moss.', 'completed', 'completion not supported by state evidence'),
    ('Juniper announces a purchase of Moss.', 'announced', 'event stage not explicitly supported'),
    ('Juniper plans a purchase of Moss.', 'proposed', 'event stage not explicitly supported'),
])
def test_stage_guard_is_lexical_not_a_semantic_or_morphological_parser(text, stage, message):
    request,payload,_=example(text,stage)
    with pytest.raises(ValueError,match=message):validate_payload_evidence(payload,request)


@pytest.mark.parametrize('text,stage', [
    ('Juniper completed a purchase of Moss.', 'completed'),
    ('Juniper announced a purchase of Moss.', 'announced'),
    ('Juniper proposed a purchase of Moss.', 'proposed'),
    ('Juniper has acquired Moss.', 'unknown'),
])
def test_explicit_lexical_stage_or_unknown_remain_allowed(text,stage):
    request,payload,_=example(text,stage)
    validate_payload_evidence(payload,request)


def test_negation_guard_cannot_locate_negation_scope():
    request,payload,_=example('Juniper completed a purchase of Moss. No price was disclosed.','completed')
    with pytest.raises(ValueError,match='negation was lost'):validate_payload_evidence(payload,request)


def test_actual_negation_must_not_be_lost():
    request,payload,_=example('Juniper has not completed the purchase of Moss.','completed')
    with pytest.raises(ValueError,match='negation was lost'):validate_payload_evidence(payload,request)
    request,payload,_=example('Juniper has not completed the purchase of Moss.','completed',True)
    validate_payload_evidence(payload,request)


@pytest.mark.parametrize('value,value_text,updates,message', [
    (1,'one',{},'unparseable source number'),
    (2,'1',{},'invented or transformed numerical value'),
    (2,'2',{},'source number absent from cited context'),
    (1,'1',{'unit':'EUR'},'invented unit'),
    (1,'1',{'scale':'million'},'invented numerical scale'),
    (1,'1',{'period':'Q1'},'invented reporting period'),
])
def test_numeric_code_conflates_distinct_failures(value,value_text,updates,message):
    _,_,span=example('Juniper disclosed 1 USD.','unknown')
    with pytest.raises(ValueError,match=message):
        NumericClaim.model_validate(dict(metric='fixture',value=value,value_text=value_text,
            unit=None,context=span.model_dump(),**{k:v for k,v in updates.items() if k!='unit'})
            | ({'unit':updates['unit']} if 'unit' in updates else {}))


def test_known_evidence_and_unknown_id_fail_at_different_boundary():
    request,_,_=example('Juniper disclosed 1 USD.','unknown')
    valid={'evidence_id':request.evidence[0].evidence_id,'quote':request.news.headline}
    resolved,_=resolve_quote_fields({'evidence':valid},request)
    assert resolved['evidence']['start']==0
    # Literal quote is correct, but an absent ID is never repaired or aliased.
    invalid={**valid,'evidence_id':'0'*64}
    with pytest.raises(QuoteResolutionError) as error:resolve_quote_fields({'evidence':invalid},request)
    assert error.value.diagnostic.rule=='unknown_evidence_id'
