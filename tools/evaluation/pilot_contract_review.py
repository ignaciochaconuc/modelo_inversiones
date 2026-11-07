"""Read-only, opt-in contractual review adapter; preparation is not review opening."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Literal, get_args, get_origin

from pydantic import Field, JsonValue, StrictFloat, model_validator


def _load_dispositions():
    name = "contract_review_dispositions"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("pilot_review_disposition.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


d = _load_dispositions()  # Definitions only: no data, credentials, providers or CLI.
Ref = d.Ref
VERSION = "news-pilot-contract-form-v2"
CURRENT_DISPOSITION_MANIFEST = "data/cache/news_development_pilot/review-dispositions-v1/manifest.json"
PHASES = ("material_reading", "contract_mapping", "evidence_check", "owner_review", "administration")
Phase = Literal["material_reading", "contract_mapping", "evidence_check", "owner_review", "administration"]
State = Literal["unfilled", "in_progress", "completed"]
Limit = Literal["uncertain_fact", "indeterminate_fact", "insufficient_dimension", "indeterminate_dimension"]
REFERENCE_FILES = frozenset({
    "src/investment_system/agents/news_interpretation/economic_attribution.py",
    "src/investment_system/agents/news_interpretation/schemas.py",
    "src/investment_system/agents/news_interpretation/grounding.py",
    "src/investment_system/agents/news_interpretation/replay.py",
})


class Model(d.Model):
    @model_validator(mode="before")
    @classmethod
    def literal_booleans_are_not_numbers(cls, value):
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                args = get_args(field.annotation)
                if get_origin(field.annotation) is Literal and args and type(args[0]) is bool and name in value:
                    d.require(value[name] is args[0], "explicit_boolean_required")
        return value


class TechnicalReference(Model):
    schema_version: Literal["news-pilot-contract-technical-reference-v1"]
    contract_version: Literal["news-economic-validation-v3"]
    files: dict[str, str]


class ContractMapping(Model):
    fact_id: str = Field(pattern=r"^F[0-9]{3}$")
    mode: Literal["structured", "faithful_partial_only", "not_representable", "indeterminate"]
    rationale: str = Field(min_length=1, repr=False)
    limits_acknowledged: tuple[Limit, ...]


class ContractForm(Model):
    schema_version: Literal["news-pilot-contract-form-v2"]
    case_id: str
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: State
    closed_disposition: Ref
    closure_decision: Ref
    factual: Ref
    factual_snapshot: dict[str, JsonValue] = Field(repr=False)
    technical_reference: Ref
    contract_version: Literal["news-economic-validation-v3"]
    session: Ref
    mappings: tuple[ContractMapping, ...]
    allowed_outcomes: tuple[Literal["interpreted", "abstained", "indeterminate"], ...]
    rationale: str | None = Field(repr=False)
    owner_decision: Ref | None


class ContractInterval(Model):
    kind: Literal["active", "pause"]
    phase: Phase | None
    pause_reason: Literal["break", "interruption", "ai_wait", "other"] | None
    started_at: datetime
    completed_at: datetime


class ContractSession(Model):
    schema_version: Literal["news-pilot-contract-session-v1"]
    case_id: str
    packet_fingerprint: str
    disposition_id: str
    factual_sha256: str
    status: State
    opening_authorization: Ref | None
    review_id: str | None
    reviewer_id: str | None
    reviewer_name: str | None
    execution_mode: Literal["manual_chatgpt_owner", "manual_human"] | None
    independence_context: str | None
    independent_human_review: Literal[False]
    adjudication_claimed: Literal[False]
    visible_model_label: str | None
    model_snapshot: None
    api_parameters: None
    api_tokens: None
    timestamp_source: Literal["owner_declared", "manual_clock", "platform_export", "mixed"] | None
    timestamp_basis: str | None
    started_at: datetime | None
    completed_at: datetime | None
    active_seconds: float | None = Field(ge=0, strict=True)
    pause_seconds: float | None = Field(ge=0, strict=True)
    phase_seconds: dict[Phase, StrictFloat | None]
    intervals: tuple[ContractInterval, ...]
    factual_timing_reused: Literal[False]


class OpeningAuthorization(Model):
    schema_version: Literal["news-pilot-contract-opening-authorization-v1"]
    case_id: str
    review_id: str
    disposition_id: str
    factual_sha256: str
    closure_sha256: str
    explicitly_authorized: Literal[True]
    authorized_by: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    authorized_at: datetime | None
    source_message_id: str | None
    inference_authorized: Literal[False]


class OwnerDecision(Model):
    schema_version: Literal["news-pilot-contract-owner-decision-v1"]
    case_id: str
    review_id: str
    review_fingerprint: str
    factual_sha256: str
    explicitly_approved: Literal[True]
    decided_by: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    decided_at: datetime | None
    independent_human_review: Literal[False]
    adjudication_claimed: Literal[False]


class Manifest(Model):
    schema_version: Literal["news-pilot-contract-adapter-manifest-v1"]
    disposition_manifest: Ref
    technical_reference: Ref
    forms: tuple[Ref, ...]


def blank_session(disposition) -> dict:
    """Binding metadata only: no person, start time, authorization or intervals."""
    return dict(schema_version="news-pilot-contract-session-v1", case_id=disposition.case_id,
        packet_fingerprint=disposition.packet_fingerprint, disposition_id=disposition.disposition_id,
        factual_sha256=disposition.annotation.sha256, status="unfilled",
        **{k: None for k in ("opening_authorization", "review_id", "reviewer_id", "reviewer_name", "execution_mode",
            "independence_context", "visible_model_label", "model_snapshot", "api_parameters", "api_tokens",
            "timestamp_source", "timestamp_basis", "started_at", "completed_at", "active_seconds", "pause_seconds")},
        independent_human_review=False, adjudication_claimed=False, factual_timing_reused=False,
        phase_seconds={p: None for p in PHASES}, intervals=[])


def blank_form(disposition_ref: Ref, disposition, snapshot: dict, reference: Ref, session: Ref) -> dict:
    return dict(schema_version=VERSION, case_id=disposition.case_id, packet_fingerprint=disposition.packet_fingerprint,
        status="unfilled", closed_disposition=disposition_ref.model_dump(), closure_decision=disposition.closure.decision.model_dump(),
        factual=disposition.annotation.model_dump(), factual_snapshot=snapshot, technical_reference=reference.model_dump(),
        contract_version="news-economic-validation-v3", session=session.model_dump(), mappings=[], allowed_outcomes=[],
        rationale=None, owner_decision=None)


def review_fingerprint(form: ContractForm) -> str:
    """A decision binds the finalized form and session without a circular self-reference."""
    return d.identity({k: v for k, v in form.model_dump(mode="json").items() if k != "owner_decision"})


def validate_reference(repo: Path, ref: Ref) -> None:
    reference = TechnicalReference.model_validate(d.read_ref(repo, ref))
    d.require(set(reference.files) == REFERENCE_FILES, "incomplete_technical_reference")
    for name, sha in reference.files.items():
        d.bound_path(repo, Ref(path=name, sha256=sha))


def source_limits(fact, assessment) -> set[str]:
    limits = set()
    if fact.certainty in {"uncertain", "indeterminate"}:
        limits.add(fact.certainty + "_fact")
    if assessment.status in {"insufficient", "indeterminate"}:
        limits.add(assessment.status + "_dimension")
    return limits


def validate_session(repo: Path, session: ContractSession, disposition, *, now: datetime) -> None:
    d.require(now.utcoffset() is not None, "timezone_required")
    d.require(session.case_id == disposition.case_id and session.packet_fingerprint == disposition.packet_fingerprint
        and session.disposition_id == disposition.disposition_id and session.factual_sha256 == disposition.annotation.sha256,
        "session_source_binding_mismatch")
    if session.status == "unfilled":
        d.require(session.model_dump(mode="json") == blank_session(disposition), "unfilled_session_has_activity")
        return
    d.require(session.opening_authorization is not None, "separate_opening_authorization_required")
    auth = OpeningAuthorization.model_validate(d.read_ref(repo, session.opening_authorization))
    d.require(auth.case_id == session.case_id and auth.review_id == session.review_id
        and auth.disposition_id == disposition.disposition_id and auth.factual_sha256 == disposition.annotation.sha256
        and auth.closure_sha256 == disposition.closure.decision.sha256
        and auth.authorized_by == disposition.content.provenance.approver_identity, "opening_authorization_binding_mismatch")
    d.check_date(auth.authorized_at, now)
    required = (session.review_id, session.reviewer_id, session.reviewer_name, session.execution_mode,
        session.independence_context, session.timestamp_source, session.timestamp_basis, session.started_at)
    d.require(all(required), "new_session_provenance_required")
    d.check_date(session.started_at, now)
    d.check_date(session.completed_at, now)
    if auth.authorized_at is not None:
        d.require(auth.authorized_at <= session.started_at, "session_before_opening_authorization")
    closure = d.ClosureDecision.model_validate(d.read_ref(repo, disposition.closure.decision))
    if closure.decided_at is not None:
        d.require(closure.decided_at <= session.started_at, "session_before_factual_closure")
    original = d.legacy_module().Timing.model_validate(d.read_ref(repo, disposition.timing.original_form))
    d.require(session.review_id != original.review_id, "factual_review_id_reused")
    d.require(session.execution_mode != "manual_human" or session.visible_model_label is None, "human_session_has_model_label")
    d.require(set(session.phase_seconds) == set(PHASES), "session_phase_inventory_mismatch")
    d.require(all(v is None or (type(v) in {int, float} and v >= 0 and v < float("inf"))
        for v in session.phase_seconds.values()), "invalid_phase_duration")
    totals = {p: 0.0 for p in PHASES}
    pause, last = 0.0, session.started_at
    for interval in session.intervals:
        d.check_date(interval.started_at, now)
        d.check_date(interval.completed_at, now)
        d.require(interval.started_at == last and interval.completed_at > interval.started_at
            and (session.completed_at is None or interval.completed_at <= session.completed_at), "invalid_session_timeline")
        seconds = (interval.completed_at - interval.started_at).total_seconds()
        if interval.kind == "active":
            d.require(interval.phase is not None and interval.pause_reason is None, "invalid_active_interval")
            totals[interval.phase] += seconds
        else:
            d.require(interval.phase is None and interval.pause_reason is not None, "invalid_pause_interval")
            pause += seconds
        last = interval.completed_at
    if session.completed_at is not None:
        d.require(session.completed_at > session.started_at and last == session.completed_at, "incomplete_session_timeline")
        d.require(now < session.completed_at + timedelta(days=90), "contract_session_metadata_expired")
    pairs = [(sum(totals.values()), session.active_seconds), (pause, session.pause_seconds)]
    pairs.extend((totals[p], session.phase_seconds[p]) for p in PHASES)
    d.require(all(reported is None or abs(actual-reported) <= 1e-6 for actual, reported in pairs), "session_duration_mismatch")
    if session.status == "completed":
        d.require(session.completed_at is not None and session.active_seconds is not None and session.pause_seconds is not None
            and all(v is not None for v in session.phase_seconds.values()) and bool(session.intervals), "incomplete_completed_session")


def validate_form(repo: Path, form: ContractForm, selected_ref: Ref, disposition, packet: dict, *, now: datetime) -> dict:
    """No factual projection: bindings and every read-only factual field must match."""
    d.require(disposition.closure.status == "closed_content_only_untimed" and disposition.closure.decision is not None,
        "closed_untimed_disposition_required")
    d.validate_record(repo, disposition, packet, now=now)
    d.require(form.closed_disposition == selected_ref and form.closure_decision == disposition.closure.decision
        and form.factual == disposition.annotation and form.case_id == disposition.case_id
        and form.packet_fingerprint == disposition.packet_fingerprint, "stale_contractual_source_binding")
    raw_factual = d.read_ref(repo, form.factual)
    # Python equality conflates True/1 and 0/0.0; preserve JSON values and types.
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    d.require(canonical(form.factual_snapshot) == canonical(raw_factual), "factual_snapshot_changed")
    factual = d.legacy_module().Factual.model_validate(raw_factual)
    validate_reference(repo, form.technical_reference)
    session = ContractSession.model_validate(d.read_ref(repo, form.session))
    validate_session(repo, session, disposition, now=now)
    facts = {f.fact_id: f for f in factual.facts}
    ids = [entry.fact_id for entry in form.mappings]
    d.require(len(ids) == len(set(ids)) and set(ids) <= set(facts), "contractual_fact_inventory_mismatch")
    for entry in form.mappings:
        fact = facts[entry.fact_id]
        d.require(len(entry.limits_acknowledged) == len(set(entry.limits_acknowledged))
            and set(entry.limits_acknowledged) == source_limits(fact, factual.dimension_assessments[fact.dimension]),
            "source_uncertainty_not_preserved")
    d.require(len(form.allowed_outcomes) == len(set(form.allowed_outcomes)), "duplicate_allowed_outcome")
    if form.status == "unfilled":
        d.require(not form.mappings and not form.allowed_outcomes and form.rationale is None and form.owner_decision is None
            and session.status == "unfilled", "unfilled_contract_has_activity")
    else:
        d.require(session.status != "unfilled", "contract_requires_new_session")
    if form.status == "completed":
        d.require(set(ids) == set(facts) and bool(form.allowed_outcomes) and bool((form.rationale or "").strip()),
            "all_facts_contractual_review_required")
        d.require(session.status == "completed" and form.owner_decision is not None, "contract_owner_decision_required")
        d.require(any(i.phase == "owner_review" and i.kind == "active" for i in session.intervals), "owner_review_not_timed")
        d.require(any(i.phase == "contract_mapping" and i.kind == "active" for i in session.intervals), "contract_mapping_not_timed")
        decision = OwnerDecision.model_validate(d.read_ref(repo, form.owner_decision))
        d.require(decision.case_id == form.case_id and decision.review_id == session.review_id
            and decision.review_fingerprint == review_fingerprint(form) and decision.factual_sha256 == form.factual.sha256
            and decision.decided_by == disposition.content.provenance.approver_identity, "contract_owner_decision_binding_mismatch")
        d.check_date(decision.decided_at, now)
        if decision.decided_at is not None:
            d.require(decision.decided_at >= session.completed_at, "contract_decision_before_session_end")
    else:
        d.require(form.owner_decision is None, "unfinished_contract_claims_approval")
    return dict(case_id=form.case_id, status=form.status, review_id=session.review_id,
        facts_retained=len(facts), mappings_recorded=len(ids), semantic_truth="not_assessed",
        historical_factual_status=factual.status, historical_factual_timing_eligible=False)


def verify(repo: Path, folder: Path, *, now: datetime, require_completed: bool = False) -> dict:
    manifest = Manifest.model_validate(json.loads((folder / "manifest.json").read_text(encoding="utf-8")))
    d.require(manifest.disposition_manifest.path == CURRENT_DISPOSITION_MANIFEST, "current_disposition_selection_required")
    source_path = d.bound_path(repo, manifest.disposition_manifest)
    prerequisite = d.verify(repo, source_path.parent, now=now)
    d.require(prerequisite["factual_closed"] == 6, "six_factual_closures_required")
    source = d.Manifest.model_validate(d.read_ref(repo, manifest.disposition_manifest))
    selected = {}
    for ref in source.records:
        disposition = d.Disposition.model_validate(d.read_ref(repo, ref))
        selected[disposition.case_id] = (ref, disposition)
    validate_reference(repo, manifest.technical_reference)
    packets = d.legacy_module().verify_packages(repo)
    d.require(len(manifest.forms) == len(selected) == 6, "six_contract_forms_required")
    results, seen, reviews = [], set(), set()
    for ref in manifest.forms:
        form = ContractForm.model_validate(d.read_ref(repo, ref))
        d.require(form.case_id in selected and form.case_id not in seen, "duplicate_or_unknown_contract_case")
        d.require(form.technical_reference == manifest.technical_reference, "technical_reference_mismatch")
        selected_ref, disposition = selected[form.case_id]
        result = validate_form(repo, form, selected_ref, disposition, packets[form.case_id], now=now)
        if result["review_id"] is not None:
            d.require(result["review_id"] not in reviews, "duplicate_contract_review_id")
            reviews.add(result["review_id"])
        d.require(not require_completed or result["status"] == "completed", "contract_review_not_completed")
        seen.add(form.case_id)
        results.append(result)
    return dict(status="offline_contract_adapter_verified", instrument=VERSION, cases=results,
        prepared_not_started=sum(r["status"] == "unfilled" for r in results),
        started=sum(r["status"] != "unfilled" for r in results), completed=sum(r["status"] == "completed" for r in results),
        integral_pilot_completed=False, factual_timing_rehabilitated=False, effort_eligibility_assessed=False,
        semantic_truth="not_assessed", provider_calls=0, inferences=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path, required=True)
    parser.add_argument("--require-completed", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(Path(__file__).resolve().parents[2], args.validate, now=datetime.now(timezone.utc),
                        require_completed=args.require_completed)
        print(json.dumps(result))
        return 0
    except Exception:
        print(json.dumps(dict(status="blocked", error="pilot_contract_adapter_validation_failed", provider_calls=0)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
