"""Versioned metadata-only sidecars for newly authorized evaluations, never backfill."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from investment_system.agents.news_interpretation.diagnostic_events import (
    MetadataModel, BranchDiagnostic, Stage, Rule, capture_validation, _SPECIFIC,
)
from investment_system.data.news_entities import fingerprint

VERSION = "news-evaluation-diagnostics-v1"
POLICY = "diagnostic-metadata-retention-v1"
RETENTION_DAYS = 90
ROOT = Path("data/cache/news_evaluation_diagnostics")
Digest = str
NativeOutcome = Literal["interpreted", "abstained", "invalid_response", "timeout", "disconnect", "authentication",
    "authorization", "rate_limit", "server_error", "permanent_http_error", "invalid_provider_envelope",
    "model_identity_mismatch", "provider_refusal", "incomplete_response", "missing_api_key", "secret_echo_rejected",
    "effective_parameters_mismatch", "unexpected_provider_tool", "permanent_provider_error",
    "unexpected_pending_or_cancelled_response", "provider_error", "unexpected_client_error", "invalid_usage_telemetry",
    "usage_outside_verified_price_band", "observed_cost_exceeds_reservation", "invalid_result_provenance"]


class DiagnosticSidecar(MetadataModel):
    schema_version: Literal["news-evaluation-diagnostics-v1"] = VERSION
    retention_policy: Literal["diagnostic-metadata-retention-v1"] = POLICY
    run_id: str = Field(pattern=r"^eval-[a-f0-9]{32}$")
    case_id: str = Field(pattern=r"^S-[a-f0-9]{16}$")
    created_at: datetime
    expires_at: datetime
    attempt_started_at: datetime | None
    outcome: Literal["interpreted", "abstained", "rejected", "technical_error", "not_run"]
    native_outcome: NativeOutcome | None
    error_code: NativeOutcome | Literal["invalid_structured_evidence"] | None
    lifecycle_code: Literal["not_authorized", "preflight_failed", "upstream_halt"] | None = None
    pipeline_stage: Stage | Literal["complete", "execution"]
    rejection_code: Rule | None
    request_id: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    revision_id: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    source_evidence_fingerprint: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    request_evidence_fingerprint: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    settings_fingerprint: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    wire_fingerprint: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    cache_key: Digest = Field(pattern=r"^[a-f0-9]{64}$")
    attempt_id: str | None = Field(pattern=r"^[a-f0-9]{32}$")
    record_id: Digest | None = Field(pattern=r"^[a-f0-9]{64}$")
    validation_observed: bool
    diagnostics: tuple[BranchDiagnostic, ...] = Field(max_length=128)

    @field_validator("created_at", "expires_at", "attempt_started_at")
    @classmethod
    def utc(cls, value):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("diagnostic_timezone_required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def policy(self):
        if self.expires_at != self.created_at + timedelta(days=RETENTION_DAYS) or (self.attempt_started_at and self.attempt_started_at > self.created_at):
            raise ValueError("invalid_diagnostic_retention")
        if self.outcome == "not_run":
            if (any(v is not None for v in (self.native_outcome, self.error_code, self.attempt_started_at, self.attempt_id, self.record_id))
                    or self.validation_observed or self.diagnostics or self.lifecycle_code is None
                    or self.pipeline_stage != "execution" or self.rejection_code is not None):
                raise ValueError("not_run_cannot_claim_an_attempt")
            return self
        if self.attempt_started_at is None or self.attempt_id is None or self.record_id is None or self.lifecycle_code is not None:
            raise ValueError("attempt_metadata_required")
        if (self.native_outcome in {"interpreted", "abstained"}) != (self.outcome in {"interpreted", "abstained"}):
            raise ValueError("diagnostic_outcome_mismatch")
        if self.outcome in {"interpreted", "abstained"} and self.outcome != self.native_outcome:
            raise ValueError("diagnostic_outcome_mismatch")
        if self.outcome in {"interpreted", "abstained"} and (not self.validation_observed or self.diagnostics):
            raise ValueError("diagnostic_success_requires_observed_validation")
        if self.diagnostics:
            if self.pipeline_stage != self.diagnostics[0].stage or self.rejection_code != self.diagnostics[0].rule:
                raise ValueError("primary_diagnostic_mismatch")
        elif self.rejection_code is not None or self.pipeline_stage != "complete":
            raise ValueError("unexpected_primary_diagnostic")
        if self.native_outcome == "invalid_response" and (not self.validation_observed or not self.diagnostics or self.outcome != "rejected"):
            raise ValueError("rejection_requires_observed_diagnostic")
        stages = {"numeric_fidelity": "internal_schema", "stage_not_supported": "semantic_validation", "negation_lost": "semantic_validation"}
        for detail in self.diagnostics:
            if detail.rule in _SPECIFIC and detail.subcode not in _SPECIFIC[detail.rule]:
                raise ValueError("specific_branch_diagnostic_required")
            if detail.rule in _SPECIFIC and detail.stage != stages.get(detail.rule, "evidence_resolution"):
                raise ValueError("diagnostic_stage_mismatch")
        return self

    @property
    def sidecar_id(self):
        return fingerprint(self.model_dump(mode="json"))


class SidecarStore:
    """Independent store. Reads never open attempts, cache, output files or news."""
    def __init__(self, root: Path = ROOT, *, allowed_root: Path = ROOT):
        self.root = Path(root).resolve()
        if not self.root.is_relative_to(Path(allowed_root).resolve()):
            raise ValueError("diagnostic_storage_outside_allowed_tree")

    def _path(self, run_id: str, case_id: str):
        import re
        if not re.fullmatch(r"eval-[a-f0-9]{32}", run_id) or not re.fullmatch(r"S-[a-f0-9]{16}", case_id):
            raise ValueError("invalid_diagnostic_identifier")
        path = self.root / run_id / (case_id + ".json")
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ValueError("unsafe_diagnostic_path")
        return path

    def write(self, sidecar: DiagnosticSidecar, *, now: datetime | None = None):
        sidecar = DiagnosticSidecar.model_validate_json(sidecar.model_dump_json())
        now = now or datetime.now(timezone.utc)
        if not sidecar.created_at <= now < sidecar.expires_at:
            raise ValueError("diagnostic_not_current")
        path = self._path(sidecar.run_id, sidecar.case_id)
        value = {"sidecar_id": sidecar.sidecar_id, "metadata": sidecar.model_dump(mode="json")}
        raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError("diagnostic_sidecar_is_immutable")
            return sidecar.sidecar_id
        with path.open("xb") as stream:
            stream.write(raw)
        return sidecar.sidecar_id

    def read(self, run_id: str, case_id: str, *, now: datetime | None = None, expected_id: str | None = None):
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate_diagnostic_key")
                result[key] = value
            return result
        path = self._path(run_id, case_id)
        if path.stat().st_size > 131072:
            raise ValueError("oversized_diagnostic_sidecar")
        try:
            value = json.loads(path.read_bytes(), object_pairs_hook=unique)
            if set(value) != {"sidecar_id", "metadata"}:
                raise ValueError("invalid_diagnostic_wrapper")
            # JSON validation retains strict primitive checks, including timestamps.
            sidecar = DiagnosticSidecar.model_validate_json(json.dumps(value["metadata"]))
            if (sidecar.run_id != run_id or sidecar.case_id != case_id or sidecar.sidecar_id != value["sidecar_id"]
                    or (expected_id is not None and sidecar.sidecar_id != expected_id)):
                raise ValueError("diagnostic_identity_mismatch")
        except Exception:
            raise ValueError("invalid_diagnostic_sidecar") from None
        now = now or datetime.now(timezone.utc)
        if now < sidecar.created_at or now >= sidecar.expires_at:
            raise ValueError("diagnostic_retention_expired_or_future")
        return sidecar


def interpret_observed(service, request, *, case_id: str, source_evidence_fingerprint: str, store: SidecarStore):
    """Explicit opt-in for a NEW one-attempt v3 execution, authorized by service.

    No function accepts historical attempt IDs or an existing delivery for backfill.
    Persistence failure propagates: caller must halt; no automatic second attempt.
    """
    from investment_system.agents.news_interpretation.runtime_schemas import EconomicRuntimeSettings
    if not isinstance(service.settings, EconomicRuntimeSettings) or service.settings.max_attempts != 1:
        raise ValueError("sidecar_requires_single_attempt_economic_runtime")
    # Validate trusted IDs before service/provider invocation, even if caller bypasses CLI.
    path = store._path(service.run_id, case_id)
    if path.exists():
        raise ValueError("diagnostic_case_already_exists")
    import re
    if not re.fullmatch(r"[a-f0-9]{64}", source_evidence_fingerprint):
        raise ValueError("invalid_source_fingerprint")
    if request.news.provider != "synthetic" or source_evidence_fingerprint != fingerprint({
            "headline": request.news.headline, "summary": request.news.summary or ""}):
        raise ValueError("evaluation_source_binding_mismatch")
    started = service.clock()
    with capture_validation() as capture:
        delivery = service.interpret(request, force_new=True)
    record = delivery.record
    if record is None:
        # No inference record to bind. Caller must retain ordinary not_run metadata.
        raise ValueError("no_new_attempt_for_diagnostic_sidecar")
    now = service.clock()
    if (delivery.retrieval_mode != "new_inference" or delivery.additional_attempts != 1
            or record.started_at < started or record.expires_at <= now or record.run_id != service.run_id
            or record.request != request or record.attempt_number != 1):
        raise ValueError("historical_or_mismatched_delivery_forbidden")
    details = tuple(capture.details)
    if not details and record.rejection_diagnostics:
        # Current typed transport/provenance diagnostics; never error messages.
        details = tuple(BranchDiagnostic(stage=d.stage, rule=d.rule, field_path=tuple(d.field_path))
                        for d in record.rejection_diagnostics)
    outcome = record.outcome if record.outcome in {"interpreted", "abstained"} else (
        "rejected" if record.outcome == "invalid_response" or record.error_code == "provider_refusal" else "technical_error")
    sidecar = DiagnosticSidecar(run_id=service.run_id, case_id=case_id, created_at=now,
        expires_at=now + timedelta(days=RETENTION_DAYS), attempt_started_at=record.started_at,
        outcome=outcome, native_outcome=record.outcome, error_code=record.error_code,
        pipeline_stage=details[0].stage if details else "complete", rejection_code=details[0].rule if details else None,
        request_id=request.request_id, revision_id=request.revision_id,
        source_evidence_fingerprint=source_evidence_fingerprint, request_evidence_fingerprint=request.evidence_fingerprint,
        settings_fingerprint=fingerprint(service.settings.model_dump(mode="json")), wire_fingerprint=record.wire_fingerprint,
        cache_key=record.cache_key, attempt_id=record.attempt_id, record_id=record.record_id,
        validation_observed=capture.validated, diagnostics=details)
    # Compare only structured enums/paths, never inspect serialized exception bodies.
    if record.outcome == "invalid_response" and {d.rule for d in details} != {d.rule for d in record.rejection_diagnostics}:
        raise ValueError("diagnostic_capture_mismatch")
    identity = store.write(sidecar, now=now)
    return delivery, identity


def record_not_run(request, settings, *, run_id: str, case_id: str, source_evidence_fingerprint: str,
                   reason: Literal["not_authorized", "preflight_failed", "upstream_halt"], store: SidecarStore):
    """Fresh lifecycle metadata only; never labels a possible failed write as no call.

    For a persistence failure after a possible call, halt and preserve its ledger;
    this function must NOT be used to manufacture a not_run classification.
    """
    from investment_system.agents.news_interpretation.service import prepare_invocation
    from investment_system.agents.news_interpretation.runtime_schemas import EconomicRuntimeSettings
    if not isinstance(settings, EconomicRuntimeSettings) or settings.max_attempts != 1:
        raise ValueError("sidecar_requires_single_attempt_economic_runtime")
    if request.news.provider != "synthetic" or source_evidence_fingerprint != fingerprint({
            "headline": request.news.headline, "summary": request.news.summary or ""}):
        raise ValueError("evaluation_source_binding_mismatch")
    now = datetime.now(timezone.utc)
    _, wire, key = prepare_invocation(request, settings)  # Pure, no client transport.
    sidecar = DiagnosticSidecar(run_id=run_id, case_id=case_id, created_at=now,
        expires_at=now + timedelta(days=RETENTION_DAYS), attempt_started_at=None, outcome="not_run",
        native_outcome=None, error_code=None, lifecycle_code=reason, request_id=request.request_id,
        pipeline_stage="execution", rejection_code=None,
        revision_id=request.revision_id, source_evidence_fingerprint=source_evidence_fingerprint,
        request_evidence_fingerprint=request.evidence_fingerprint, settings_fingerprint=fingerprint(settings.model_dump(mode="json")),
        wire_fingerprint=fingerprint(wire), cache_key=key, attempt_id=None, record_id=None,
        validation_observed=False, diagnostics=())
    return store.write(sidecar, now=now)
