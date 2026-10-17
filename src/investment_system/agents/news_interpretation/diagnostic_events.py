"""Opt-in, content-free branch observation. No persisted replay schema changes."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


Stage = Literal["transport", "telemetry", "json", "model_schema", "evidence_resolution", "internal_schema",
    "semantic_validation", "provenance", "identity", "economic_attribution", "consumer_contract"]
Rule = Literal["invalid_json", "duplicate_json_keys", "structural_contract_violation", "unknown_evidence_id",
    "wrong_revision", "quote_not_found_in_declared_field", "ambiguous_quote", "date_iso_literal_required",
    "date_evidence_pair_required", "span_mismatch", "numeric_fidelity", "entity_name_not_grounded",
    "entity_registry_mismatch", "state_not_supported", "stage_not_supported", "negation_lost",
    "contradictory_amounts", "prohibited_output", "semantic_contract_violation", "invalid_result_provenance",
    "provider_transport_failure", "invalid_usage_telemetry", "cost_reservation_exceeded",
    "identity_not_supported", "identity_ambiguous", "product_identity_forbidden", "attribution_evidence_required",
    "attribution_not_explicit", "attribution_state_conflict", "contextual_participation_forbidden",
    "impact_not_supported", "invalid_consumer_projection"]
Subcode = Literal["not_available", "completion_literal_missing", "announced_literal_missing", "proposed_literal_missing",
    "number_lexeme_unparseable", "number_value_nonfinite_or_transformed", "number_absent_from_context",
    "unit_absent_from_context", "scale_absent_from_context", "period_absent_from_context",
    "negation_token_present_flag_false", "evidence_id_not_in_request", "evidence_revision_not_primary",
    "exact_quote_absent", "exact_quote_ambiguous"]
_SPECIFIC = {
    "stage_not_supported": {"completion_literal_missing", "announced_literal_missing", "proposed_literal_missing"},
    "numeric_fidelity": {"number_lexeme_unparseable", "number_value_nonfinite_or_transformed", "number_absent_from_context",
        "unit_absent_from_context", "scale_absent_from_context", "period_absent_from_context"},
    "negation_lost": {"negation_token_present_flag_false"}, "unknown_evidence_id": {"evidence_id_not_in_request"},
    "wrong_revision": {"evidence_revision_not_primary"}, "quote_not_found_in_declared_field": {"exact_quote_absent"},
    "ambiguous_quote": {"exact_quote_ambiguous"},
}
# Closed vocabulary, never arbitrary model keys or exception paths.
SAFE_FIELDS = frozenset("events economics entities numbers evidence state_evidence date_evidence event_date event_key event_type "
    "other_type description state stage negated value value_text unit scale period metric context name role entity_id ticker "
    "evidence_id start end quote unknown_fields favorable unfavorable text category rationale horizon materiality stance "
    "uncertainty evidence_limitations status abstention_reasons evidence_sufficiency schema_version mention_kind "
    "registry_entity_id identity_evidence attribution participation_role relation_type related_entity relation_state "
    "relationship_evidence potential_impact channel identity security_id canonical_name confirmed_exposure "
    "operational unknown_field".split())


class MetadataModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def closed_fields(cls, value):
        if isinstance(value, dict) and not set(value) <= set(cls.model_fields):
            raise ValueError("unexpected_diagnostic_fields")
        if isinstance(value, dict):
            value = dict(value)
            for name in ("field_path", "diagnostics"):
                if name in value and type(value[name]) is list:
                    value[name] = tuple(value[name])
            for name in ("created_at", "expires_at", "attempt_started_at"):
                if name in value and type(value[name]) is str:
                    try:
                        value[name] = datetime.fromisoformat(value[name])
                    except ValueError:
                        raise ValueError("invalid_diagnostic_timestamp") from None
        return value


class BranchDiagnostic(MetadataModel):
    stage: Stage
    rule: Rule
    subcode: Subcode = "not_available"
    field_path: tuple[str | int, ...] = ()

    @field_validator("field_path")
    @classmethod
    def safe_path(cls, value):
        if len(value) > 16 or any((type(p) is int and not 0 <= p < 100000)
                or (type(p) is str and p not in SAFE_FIELDS) or type(p) not in {str, int} for p in value):
            raise ValueError("unsafe_diagnostic_path")
        return value

    @model_validator(mode="after")
    def paired_code(self):
        if self.subcode != "not_available" and self.subcode not in _SPECIFIC.get(self.rule, set()):
            raise ValueError("diagnostic_code_pair_mismatch")
        return self


def safe_path(path) -> tuple:
    return tuple(p if (type(p) is int and 0 <= p < 100000) or (type(p) is str and p in SAFE_FIELDS)
                 else "unknown_field" for p in path[:16])


class BranchViolation(ValueError):
    """Original fixed message plus typed branch metadata, not parsed error text."""
    def __init__(self, message: str, detail: BranchDiagnostic):
        super().__init__(message)
        self.detail = detail


_CURRENT = ContextVar("news_diagnostic_capture", default=None)


class ValidationCapture:
    def __init__(self):
        self.active = False
        self.sealed = False
        self.validated = False
        self.details = []

    def add(self, detail: BranchDiagnostic):
        if self.active and detail not in self.details:
            self.details.append(detail)


@contextmanager
def capture_validation():
    """No I/O. Scope belongs to one future attempt, not replay/backfill."""
    value = ValidationCapture()
    token = _CURRENT.set(value)
    try:
        yield value
    finally:
        _CURRENT.reset(token)


def emit(detail: BranchDiagnostic):
    capture = _CURRENT.get()
    if capture is not None:
        capture.add(detail)


def violation(message: str, stage: Stage, rule: Rule, subcode: Subcode, path=()) -> ValueError:
    detail = BranchDiagnostic(stage=stage, rule=rule, subcode=subcode, field_path=safe_path(path))
    if path:
        emit(detail)
    return BranchViolation(message, detail)


def observe_pydantic(error):
    """Only typed exceptions created at the failing branch; no message parsing."""
    for item in error.errors(include_input=False, include_url=False):
        branch = (item.get("ctx") or {}).get("error")
        if isinstance(branch, BranchViolation):
            emit(branch.detail.model_copy(update={"field_path": safe_path(item["loc"])}))


def observed_validation(function):
    """Observe first validation only; nested/repeated replay stays side-effect-free."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        capture = _CURRENT.get()
        if capture is None or capture.active or capture.sealed:
            return function(*args, **kwargs)
        capture.active = True
        try:
            result = function(*args, **kwargs)
            for diagnostic in result[1].diagnostics:
                if not any(d.stage == diagnostic.stage and d.rule == diagnostic.rule for d in capture.details):
                    capture.add(BranchDiagnostic(stage=diagnostic.stage, rule=diagnostic.rule,
                        field_path=safe_path(diagnostic.field_path)))
            capture.validated = True
            return result
        finally:
            capture.active = False
            capture.sealed = True
    return wrapped
