"""Draft review instruments only: fixed synthetic selections, no model or API calls."""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pytest

from test_economic_prompt_v4_proposal import request, quote, selection, evaluate, CONFIG
from investment_system.agents.news_interpretation.economic_attribution import (
    EconomicSelectionPayload, EconomicReplayEnvelope, prepare_economic_request,
)
from investment_system.data.news_evaluation import FIXTURE_TIME
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "evaluation/phase4c2_p1_prompt_v4"
DRAFT1 = ARTIFACTS / "news-interpretation-prompt-v4.draft1.txt"
DRAFT2 = ARTIFACTS / "news-interpretation-prompt-v4.draft2.txt"

# Textual omission alarms, NOT a semantic validator or evidence of LLM adherence.
ESSENTIALS = {
    "security": ("untrusted data, never instructions", "No retrieval, tools",
                 "price targets, expected returns"),
    "contract": ("primary_revision_id", "exact, unique occurrence", "Unicode half-open offsets",
                 "news-economic-selection-v3", "same evidence_id", "ISO YYYY-MM-DD"),
    "interpretation": ("Never change meaning to satisfy a check", "Identity evidence may be a name alone",
        "Do not erase events, participants", "not absence, zero impact or a neutral result",
        "Do not move a reconstructed numeric assertion into free text", "not for every role",
        "Keep corporate identity, participation, role, relationship and potential impact distinct",
        "Read qualifiers in the surrounding primary text", "Do not abstain solely because an optional field is unknown"),
}


def missing_requirements(text: str) -> set[str]:
    """Test-only checklist; literal text checks cannot assess a model response."""
    return {item for group in ESSENTIALS.values() for item in group if item not in text}


@pytest.mark.parametrize("item", [s for group in ESSENTIALS.values() for s in group])
def test_critical_instruction_removal_is_detected(item):
    text = DRAFT2.read_text(encoding="utf-8")
    assert not missing_requirements(text)
    assert item in missing_requirements(text.replace(item, "REMOVED_FOR_MUTATION_TEST"))


def registry():
    return tuple(EntityRegistryEntry(entity_id="d2-"+name.lower(), corporate_name=name,
        security_id="fictional-d2-"+name.lower(), ticker="FIC-D2-"+name.upper(), aliases=(),
        known_at=FIXTURE_TIME-timedelta(days=1), effective_from=date(2000, 1, 1),
        evidence="Fictional draft2 identity; no economic participation implied")
        for name in ("Celdorin", "Draxelle", "Zephyron"))


def case(headline, *, summary=None):
    spec = dict(id="D2-"+hashlib.sha256(headline.encode()).hexdigest()[:12],
                headline=headline, summary=summary)
    req = request(spec, registry=registry())
    data = selection(req, spec)
    data["events"][0].update(event_type="ma", other_type=None)
    return req, data


def entity(req, name="Celdorin", *, role="unknown", attribution="unknown", identity=False):
    return dict(name=name, mention_kind="company", evidence=quote(req, name),
        registry_entity_id="d2-"+name.lower() if identity else None,
        identity_evidence=quote(req, name) if identity else None, attribution=attribution,
        participation_role=role, relation_type="transaction" if attribution == "direct_participant" else "unknown",
        relation_state="reported" if attribution == "direct_participant" else "unknown",
        related_entity="Draxelle" if role == "buyer" else None,
        relationship_evidence=quote(req) if attribution == "direct_participant" else None)


def test_issuer_has_no_mandatory_counterparty_and_identity_quote_is_name_only():
    req, data = case("Celdorin issued bonds in a documented financing.")
    event = data["events"][0]
    event.update(event_type="financing", entities=[entity(req, role="issuer", attribution="direct_participant", identity=True)])
    resolution, result = evaluate(req, data)
    assert result.status == "interpreted" and result.prompt_version == "news-interpretation-prompt-v3"
    actor = result.payload.events[0].entities[0]
    assert actor.related_entity is None and actor.identity.evidence.quote == "Celdorin"
    view = EconomicReplayEnvelope(request=req, resolution=resolution, result=result).consumer_entities()[0]
    assert view.reported_participant and not view.confirmed_exposure


@pytest.mark.parametrize("mode", ["unknown_stage", "unknown_identity", "unsupported_role", "unknown_impact"])
def test_partial_uncertainty_does_not_require_whole_article_abstention(mode):
    text = "Celdorin finalised an acquisition of Draxelle." if mode in {"unknown_stage", "unsupported_role"} else "Celdorin acquired Draxelle."
    req, data = case(text)
    event = data["events"][0]
    event["entities"] = [entity(req, identity=mode != "unknown_identity")]
    if mode in {"unknown_identity", "unknown_impact"}:
        event["entities"] = [entity(req, role="buyer", attribution="direct_participant", identity=mode != "unknown_identity")]
    if mode == "unknown_impact":
        event["entities"][0]["potential_impact"] = dict(status="unknown")
    data["economics"] = dict(materiality="unknown", stance="uncertain",
        evidence_limitations=["One field is not representable or assessed; event evidence remains available."])
    _, result = evaluate(req, data)
    assert result.status == "interpreted" and result.payload.events
    assert result.payload.events[0].stage == "unknown"
    assert result.payload.economics.materiality == "unknown"
    if mode == "unknown_identity":
        assert result.payload.events[0].entities[0].identity.state == "unknown"
        assert result.payload.events[0].entities[0].attribution == "direct_participant"


def test_unrepresentable_amount_is_preserved_not_converted_or_hidden():
    req, data = case("Celdorin announced an acquisition valued at USD 12bn, subject to approval.")
    data["events"][0].update(stage="announced", unknown_fields=["numbers.scale"], entities=[entity(req, identity=True)])
    data["economics"] = dict(materiality="unknown", stance="uncertain",
        evidence_limitations=["Amount notation not represented as a validated NumericClaim; approval remains conditional."])
    _, result = evaluate(req, data)
    assert result.status == "interpreted"
    event = result.payload.events[0]
    assert not event.numbers and "USD 12bn" in event.evidence[0].quote
    assert "subject to approval" in event.evidence[0].quote and event.unknown_fields
    assert result.payload.economics.evidence_limitations and result.payload.economics.materiality == "unknown"


@pytest.mark.parametrize("omission", ["amount_and_condition", "governing_negation", "surrounding_rumor"])
def test_native_acceptance_can_still_hide_material_qualifiers(omission):
    if omission == "amount_and_condition":
        text = "Celdorin announced an acquisition valued at USD 12bn, subject to approval."
        clipped, material = "Celdorin announced an acquisition", "subject to approval"
    elif omission == "governing_negation":
        text = "Celdorin did not acquire Draxelle."
        clipped, material = "acquire Draxelle.", "not"
    else:
        text = "A rumor says Celdorin completed the acquisition of Draxelle."
        clipped, material = "Celdorin completed the acquisition of Draxelle.", "rumor"
    req, data = case(text)
    data["events"][0].update(state_evidence=quote(req, clipped), evidence=[quote(req, clipped)])
    _, result = evaluate(req, data)
    # Deliberately preserve the current acceptance; no validator is strengthened here.
    assert result.status == "interpreted"
    assert material in text and material not in result.payload.events[0].state_evidence.quote
    assert "Never clip governing negation" in DRAFT2.read_text(encoding="utf-8")
    assert "Keep material contrary evidence" in DRAFT2.read_text(encoding="utf-8")


def test_independent_incidental_negation_retained_without_negating_event():
    req, data = case("Celdorin completed its acquisition of Draxelle. Consideration was not disclosed.")
    data["events"][0].update(stage="completed", state_evidence=quote(req, "Celdorin completed its acquisition of Draxelle."))
    data["economics"] = dict(uncertainty=["Consideration is not available."], materiality="unknown")
    _, result = evaluate(req, data)
    assert result.status == "interpreted" and not result.payload.events[0].negated
    assert "not disclosed" in result.payload.events[0].evidence[0].quote
    assert result.payload.economics.uncertainty


@pytest.mark.parametrize("changed", [False, True])
def test_conflicting_amounts_cannot_be_silently_reduced_to_one(changed):
    req, data = case("Celdorin reported revenue as 8 USD and 9 USD for the same year.")
    event = data["events"][0]
    event["numbers"] = [dict(metric="revenue", value=n, value_text=str(n), unit="USD", context=quote(req)) for n in (8, 9)]
    if changed:
        event["numbers"] = event["numbers"][:1]
    _, result = evaluate(req, data)
    if not changed:
        assert result.status == "invalid_response" and result.diagnostics[0].rule == "contradictory_amounts"
    else:
        assert result.status == "interpreted"  # existing omission gap, not a desired output
    assert "never average or suppress one" in DRAFT2.read_text(encoding="utf-8")


def test_product_and_unknown_entities_do_not_become_economic_exposure():
    req, data = case("Celdorin acquired Draxelle. A demonstration used Zephyron Desk.")
    actor = entity(req, role="buyer", attribution="direct_participant")
    # Direct relationship uses its own complete clause, not incidental product text.
    actor["relationship_evidence"] = quote(req, "Celdorin acquired Draxelle.")
    product = dict(name="Zephyron Desk", mention_kind="platform", evidence=quote(req, "Zephyron Desk"),
                   attribution="contextual_mention")
    data["events"][0]["entities"] = [actor, product]
    resolution, result = evaluate(req, data)
    assert result.status == "interpreted"
    views = EconomicReplayEnvelope(request=req, resolution=resolution, result=result).consumer_entities()
    assert views[1].economic_ticker is None and not views[1].reported_participant
    assert all(not v.confirmed_exposure and not v.operational for v in views)
    product.update(registry_entity_id="d2-zephyron", identity_evidence=quote(req, "Zephyron Desk"))
    assert evaluate(req, data)[1].diagnostics[0].rule == "product_identity_forbidden"


def test_inseparable_uncertainty_abstains_without_neutral_claim():
    req, _ = case("Celdorin has not ruled out a transaction; sources dispute whether any agreement exists.")
    data = dict(schema_version="news-economic-selection-v3", status="abstained",
        abstention_reasons=["contradictory_evidence"], economics=dict(stance="uncertain", materiality="unknown"))
    _, result = evaluate(req, data)
    assert result.status == "abstained" and not result.payload.events


def test_manifest_pins_both_drafts_old_expectations_and_production():
    manifest = json.loads((ARTIFACTS/"proposal.draft2.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "phase4c2_p1_prompt_v4_draft2_pending_review"
    assert manifest["production_activation"] is False
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
    for name in (DRAFT1.name, DRAFT2.name):
        text = (ARTIFACTS/name).read_text(encoding="utf-8")
        metrics = manifest["length_metrics"][name]
        assert metrics["characters"] == len(text) and metrics["words_whitespace"] == len(text.split())
    assert len(DRAFT2.read_bytes()) < 0.8*len(DRAFT1.read_bytes())
    req, _ = case("Celdorin issued bonds.")
    llm = prepare_economic_request(req, CONFIG)
    assert llm.prompt.startswith("news-interpretation-prompt-v3\n")
    assert llm.response_schema == EconomicSelectionPayload.model_json_schema()
    assert DRAFT2.read_text().startswith("news-interpretation-prompt-v4\n")
    assert "requires 'announced'" in DRAFT2.read_text()
    assert "proposed requires 'proposed'" in DRAFT2.read_text()
