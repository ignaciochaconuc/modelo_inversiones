"""Hand-authored contract probes, NOT model generations or v4 runtime results."""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investment_system.agents.news_interpretation.diagnostic_events import capture_validation
from investment_system.agents.news_interpretation.economic_attribution import (
    EconomicSelectionPayload, EconomicReplayEnvelope, evaluate_economic_response, prepare_economic_request,
)
from investment_system.agents.news_interpretation.runtime_schemas import EconomicRuntimeSettings
from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest, ModelConfiguration
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_evaluation import FIXTURE_TIME, synthetic_record
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry
from investment_system.llm.schemas import LLMResponse

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "evaluation/phase4c2_p1_prompt_v4"
CASES = json.loads((ROOT/"fixtures.json").read_text(encoding="utf-8"))["cases"]
NOW = FIXTURE_TIME + timedelta(seconds=12)
CONFIG = ModelConfiguration(provider="openai", model="offline-p1-contract-model")


def request(case: dict, *, registry=()) -> NewsInterpretationRequest:
    news = synthetic_record(case["id"], case["headline"], "", summary=case.get("summary"), published_at=None)
    context = ()
    if case.get("mode") == "context_id":
        context = (synthetic_record("P1-other-revision", "Tersaline announced a platform release.", "", published_at=None),)
    return NewsInterpretationRequest(news=news, decision_time=FIXTURE_TIME,
                                     registry_entries=registry, context_news=context)


def quote(req, text=None, *, field="headline"):
    source = next(e for e in req.evidence if e.revision_id == req.revision_id and e.field == field)
    return dict(evidence_id=source.evidence_id, quote=text or source.text)


def selection(req, case: dict) -> dict:
    state = quote(req, case.get("quote"))
    if case.get("mode") == "unknown_id":
        state["evidence_id"] = "f"*64
    elif case.get("mode") == "context_id":
        source = next(e for e in req.evidence if e.revision_id != req.revision_id)
        state = dict(evidence_id=source.evidence_id, quote=source.text)
    event = dict(event_key="P1-event", event_type="other", other_type="contract probe",
        description="Fictional contract probe, not an operative assessment", state=case.get("state", "confirmed"),
        stage=case.get("stage", "unknown"), negated=case.get("negated", False),
        state_evidence=state, evidence=[quote(req)], entities=[])
    if case.get("number"):
        values = dict(case["number"])
        text = values.pop("quote", None)
        event["numbers"] = [dict(metric="reported amount", context=quote(req, text), **values)]
    if case.get("event_date"):
        event.update(event_date=case["event_date"], date_evidence=quote(req))
    return dict(schema_version="news-economic-selection-v3", status="interpreted", events=[event])


def evaluate(req, data):
    response = LLMResponse(provider="openai", model=CONFIG.model, content=json.dumps(data),
                           generated_at=NOW, input_tokens=0, cached_input_tokens=0, output_tokens=0)
    return evaluate_economic_response(req, response, CONFIG, validated_at=NOW)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_current_validator_contract_probe(case):
    req = request(case)
    data = selection(req, case)
    # All probes are structurally valid: failures are the unchanged downstream rules.
    EconomicSelectionPayload.model_validate(data)
    with capture_validation() as capture:
        _, result = evaluate(req, data)
    assert result.prompt_version == "news-interpretation-prompt-v3"  # never mislabel as v4
    if case.get("rule"):
        assert result.status == "invalid_response"
        assert [d.rule for d in result.diagnostics] == [case["rule"]]
        if case.get("subcode"):
            assert [d.subcode for d in capture.details] == [case["subcode"]]
    else:
        assert result.status == "interpreted"
    if case.get("semantic_warning"):
        # Passing a lexical guard is deliberately NOT a semantic reference label.
        assert result.status == "interpreted"
        warnings = {
            "lexical_acceptance_does_not_establish_completion": "actual completion",
            "completion_refers_to_other_action": "completion of a review",
            "qualifier_clipping_must_be_forbidden": "Never clip out 'not'",
            "ambiguous_decimal_comma_must_not_be_exploited": "Do not exploit comma removal",
            "future_event_is_not_confirmed_by_guard_acceptance": "a future",
        }
        assert warnings[case["semantic_warning"]] in (ROOT/"news-interpretation-prompt-v4.draft1.txt").read_text(encoding="utf-8")


def registry():
    return tuple(EntityRegistryEntry(entity_id="p1-"+name.lower(), corporate_name=name,
        ticker="FIC-P1-"+name.upper(), security_id="fictional-p1-"+name.lower(), aliases=(),
        effective_from=date(2000, 1, 1), known_at=FIXTURE_TIME-timedelta(days=1),
        evidence="New fictional P1 identity only, not relationship evidence") for name in ("Velquora", "Tersaline"))


def entity(req, *, name="Velquora", identity=True, attribution="direct_participant"):
    return dict(name=name, mention_kind="company", evidence=quote(req),
        registry_entity_id="p1-"+name.lower() if identity else None,
        identity_evidence=quote(req, name) if identity else None, attribution=attribution,
        participation_role="buyer" if attribution == "direct_participant" else "unknown",
        relation_type="transaction" if attribution == "direct_participant" else "unknown",
        related_entity="Tersaline" if attribution == "direct_participant" else None,
        relation_state="reported" if attribution == "direct_participant" else "unknown",
        relationship_evidence=quote(req) if attribution == "direct_participant" else None)


@pytest.mark.parametrize("mode,rule", [
    ("supported", None), ("unresolved_direct", None), ("context", None),
    ("identity_only", "attribution_evidence_required"),
    ("unsupported_frame", "attribution_not_explicit"),
    ("product_to_manufacturer", "product_identity_forbidden"),
    ("context_impact", "contextual_participation_forbidden"),
    ("nonoverlap", "attribution_not_explicit"),
])
def test_identity_participation_and_context_are_separate(mode, rule):
    headline = "Velquora acquired Tersaline."
    if mode in {"context", "context_impact"}:
        headline = "An industry report mentions Velquora near an acquisition headline."
    if mode == "unsupported_frame":
        headline = "Velquora announced the acquisition of Tersaline."
    if mode == "product_to_manufacturer":
        headline = "Velquora Desk is a platform mentioned in an acquisition report."
    case = dict(id="P1-entity-"+mode, headline=headline, summary="Velquora acquired Tersaline.")
    req = request(case, registry=registry())
    data = selection(req, case)
    data["events"][0].update(event_type="ma", other_type=None)
    item = entity(req, identity=mode != "unresolved_direct",
                  attribution="contextual_mention" if mode in {"context", "context_impact"} else "direct_participant")
    if mode == "identity_only":
        item["relationship_evidence"] = None
    if mode == "product_to_manufacturer":
        item.update(name="Velquora Desk", mention_kind="platform", identity_evidence=quote(req, "Velquora Desk"))
    if mode == "context_impact":
        item["potential_impact"] = dict(status="potential", channel="commercial", evidence=quote(req), rationale="Unsupported implication")
    if mode == "nonoverlap":
        item["relationship_evidence"] = quote(req, field="summary")
    data["events"][0]["entities"] = [item]
    resolution, result = evaluate(req, data)
    if rule:
        assert result.status == "invalid_response" and result.diagnostics[0].rule == rule
    else:
        assert result.status == "interpreted"
        view = EconomicReplayEnvelope(request=req, resolution=resolution, result=result).consumer_entities()[0]
        assert not view.confirmed_exposure and not view.operational
        if mode in {"unresolved_direct", "context"}:
            assert view.economic_ticker is None
        if mode == "context":
            assert not view.reported_participant


def test_draft_artifact_is_pinned_separate_and_not_activated():
    manifest = json.loads((ROOT/"proposal.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase4c2_p1_prompt_v4_proposed_pending_review"
    assert manifest["production_activation"] is False
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
    for name, digest in manifest["production_source_sha256"].items():
        assert hashlib.sha256((REPO/name).read_bytes()).hexdigest() == digest
    req = request(CASES[0])
    old = prepare_economic_request(req, CONFIG)
    header, _, body = old.prompt.partition("{")
    assert header.startswith("news-interpretation-prompt-v3\n")
    envelope = json.loads("{"+body)
    assert envelope["prompt_version"] == "news-interpretation-prompt-v3"
    assert old.response_schema == EconomicSelectionPayload.model_json_schema()
    # Schema-only draft specimen, never a LLMRequest or a routable runtime configuration.
    envelope["prompt_version"] = "news-interpretation-prompt-v4"
    draft = (ROOT/"news-interpretation-prompt-v4.draft1.txt").read_text(encoding="utf-8") + json.dumps(envelope)
    assert draft.startswith("news-interpretation-prompt-v4\n")
    assert envelope["output_schema"] == old.response_schema
    assert "Only eligible exact corporate names/aliases support entity_id/ticker assignments." not in draft
    assert prepare_economic_request(req, CONFIG) == old


def test_future_prompt_cannot_be_mislabeled_as_supported_runtime():
    import yaml
    raw = yaml.safe_load((REPO/"config/news_interpretation.evaluation.yaml").read_text(encoding="utf-8"))
    raw["prompt_version"] = "news-interpretation-prompt-v4"
    with pytest.raises(ValidationError):
        EconomicRuntimeSettings.model_validate(raw)


def test_fixture_integrity_disjointness_and_deterministic_replay():
    assert len(CASES) == 40 and len({c["id"] for c in CASES}) == 40
    original = REPO/"evaluation/phase4c2_attribution_v1/prepared/reviewer/blind_synthetic_evidence.json"
    if original.exists():
        originals = json.loads(original.read_text(encoding="utf-8"))["cases"]
        original_text = {e["text"] for c in originals for e in c["evidence"]}
        assert all(c["headline"] not in original_text and c.get("summary", "") not in original_text for c in CASES)
        assert not {c["id"] for c in CASES} & {c["case_id"] for c in originals}
    req = request(CASES[0])
    data = selection(req, CASES[0])
    a = evaluate(req, deepcopy(data))
    b = evaluate(req, deepcopy(data))
    assert a == b
    assert req.news.published_at is None and req.inputs_available_at <= req.decision_time
    future = req.news.model_copy(update={"available_at": FIXTURE_TIME+timedelta(seconds=1)})
    with pytest.raises(ValidationError):
        NewsInterpretationRequest(news=future, decision_time=FIXTURE_TIME)


def test_abstention_is_not_a_neutral_fabricated_event():
    req = request(dict(id="P1-abstention", headline="Velquora has not ruled out a possible acquisition."))
    data = dict(schema_version="news-economic-selection-v3", status="abstained",
                abstention_reasons=["insufficient_evidence"])
    _, result = evaluate(req, data)
    assert result.status == "abstained" and not result.payload.events
    data["economics"] = dict(stance="neutral")
    assert evaluate(req, data)[1].status == "invalid_response"
