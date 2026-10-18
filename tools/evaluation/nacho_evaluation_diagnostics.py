"""Opt-in evaluation orchestration; audit only sanitized metadata, never responses."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from investment_system.agents.news_interpretation.diagnostic_events import MetadataModel
from investment_system.agents.news_interpretation.diagnostic_sidecar import (
    VERSION, POLICY, RETENTION_DAYS, ROOT, SidecarStore, interpret_observed, record_not_run,
)
from investment_system.agents.news_interpretation.service import prepare_invocation
from investment_system.data.news_entities import fingerprint

POLICY_CONFIG = dict(enabled=True, schema_version=VERSION, retention_policy=POLICY,
                     retention_days=RETENTION_DAYS, content_retention_hours=24)


class ManifestCase(MetadataModel):
    case_id: str = Field(pattern=r"^S-[a-f0-9]{16}$")
    source_evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    wire_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    cache_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    sidecar_id: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["persisted", "diagnostic_failure"]

    @model_validator(mode="after")
    def binding(self):
        if (self.status == "persisted") != (self.sidecar_id is not None):
            raise ValueError("invalid_manifest_binding")
        return self


class DiagnosticManifest(MetadataModel):
    schema_version: Literal["news-evaluation-diagnostic-manifest-v1"] = "news-evaluation-diagnostic-manifest-v1"
    sidecar_version: Literal["news-evaluation-diagnostics-v1"] = VERSION
    retention_policy: Literal["diagnostic-metadata-retention-v1"] = POLICY
    retention_days: Literal[90] = RETENTION_DAYS
    content_retention_hours: Literal[24] = 24
    run_id: str = Field(pattern=r"^eval-[a-f0-9]{32}$")
    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    diagnostics_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    settings_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    expires_at: datetime
    cases: tuple[ManifestCase, ...] = Field(min_length=32, max_length=32)

    @field_validator("cases", mode="before")
    @classmethod
    def json_array(cls, value):
        return tuple(value) if type(value) is list else value

    @model_validator(mode="after")
    def integrity(self):
        if (self.created_at.tzinfo is None or self.expires_at.tzinfo is None
                or self.expires_at != self.created_at + timedelta(days=RETENTION_DAYS)
                or len({c.case_id for c in self.cases}) != 32):
            raise ValueError("invalid_diagnostic_manifest")
        return self


class _ObservedService:
    """Keep an already persisted delivery if the independent sidecar write fails."""
    def __init__(self, service):
        self.service, self.delivery = service, None

    def __getattr__(self, name):
        return getattr(self.service, name)

    def interpret(self, *args, **kwargs):
        self.delivery = self.service.interpret(*args, **kwargs)
        return self.delivery


def execute(requests, service, root, plan, *, export_delivery, write_json, before_call, store, authorize):
    """Sequential fresh run. No reference payload or historical record API."""
    authorize()
    if (not service.execution_authorized or len(requests) != 32
            or fingerprint(service.settings.model_dump(mode="json")) != plan["settings_fingerprint"]
            or fingerprint({k: v for k, v in plan.items() if k != "plan_fingerprint"}) != plan["plan_fingerprint"]):
        raise ValueError("diagnostic_plan_or_service_mismatch")
    # All bindings are checked before the first call or write.
    expected = []
    for binding, request in requests:
        _, wire, key = prepare_invocation(request, service.settings)
        expected.append({**binding, "wire_fingerprint": fingerprint(wire), "cache_key": key})
    if ([{k: c[k] for k in b} for b, c in zip(expected, plan["cases"])] != expected
            or len(plan["cases"]) != 32 or len({b["case_id"] for b in expected}) != 32):
        raise ValueError("diagnostic_case_plan_mismatch")
    store = store or SidecarStore()
    for binding in expected:
        if store._path(service.run_id, binding["case_id"]).exists():
            raise ValueError("diagnostic_run_already_exists")
    created = service.clock()
    rows, entries, halted = [], [], False
    for binding, request in requests:
        observed, sidecar_id, invocation_started = _ObservedService(service), None, False
        row = {**binding, "outcome": "not_run", "attempt_started_at": None, "record_id": None,
               "output_fingerprint": None, "units": [], "error_code": "previous_accounting_or_execution_halt"}
        try:
            if halted:
                sidecar_id = record_not_run(request, service.settings, run_id=service.run_id,
                    case_id=binding["case_id"], source_evidence_fingerprint=binding["evidence_fingerprint"],
                    reason="upstream_halt", store=store, now=service.clock())
            else:
                authorize()
                if before_call is not None:
                    before_call()
                invocation_started = True
                delivery, sidecar_id = interpret_observed(observed, request, case_id=binding["case_id"],
                    source_evidence_fingerprint=binding["evidence_fingerprint"], store=store)
                row = export_delivery(binding, delivery)
                halted = bool(delivery.record.observed_usage_cost_usd is None or delivery.record.error_code in {
                    "observed_cost_exceeds_reservation", "invalid_usage_telemetry", "usage_outside_verified_price_band"})
        except Exception:
            # Never inspect exception text. A delivered record remains semantically unchanged.
            if observed.delivery is not None and observed.delivery.record is not None:
                row = export_delivery(binding, observed.delivery)
            elif not halted:
                if not invocation_started or (observed.delivery is not None and observed.delivery.additional_attempts == 0):
                    row["error_code"] = "pre_call_check_failed"
                    try:
                        sidecar_id = record_not_run(request, service.settings, run_id=service.run_id,
                            case_id=binding["case_id"], source_evidence_fingerprint=binding["evidence_fingerprint"],
                            reason="preflight_failed", store=store, now=service.clock())
                    except Exception:
                        pass
                else:
                    row.update(outcome="transport_error", error_code="runner_failure_review_required",
                               attempt_may_have_occurred=True)
            row["diagnostic_observation_failed"] = True
            if sidecar_id is None:
                row["diagnostic_persistence_failed"] = True
            halted = True
        rows.append(row)
        bound = next(b for b in expected if b["case_id"] == binding["case_id"])
        entry = ManifestCase(case_id=binding["case_id"], source_evidence_fingerprint=binding["evidence_fingerprint"],
            **{k: bound[k] for k in ("request_id", "revision_id", "request_evidence_fingerprint", "wire_fingerprint", "cache_key")},
            sidecar_id=sidecar_id, status="persisted" if sidecar_id else "diagnostic_failure")
        entries.append(entry)
        # Durable incremental binding survives a later full-export/manifest write failure.
        write_json(root / "diagnostic-bindings" / (binding["case_id"] + ".json"), entry.model_dump(mode="json"))
        write_json(root / "cases" / (binding["case_id"] + ".json"), row)
    manifest = DiagnosticManifest(run_id=service.run_id, plan_fingerprint=plan["plan_fingerprint"],
        diagnostics_fingerprint=fingerprint(plan["evaluation_diagnostics"]), settings_fingerprint=plan["settings_fingerprint"],
        created_at=created, expires_at=created+timedelta(days=RETENTION_DAYS), cases=tuple(entries))
    write_json(root / "diagnostic-manifest.json", manifest.model_dump(mode="json"))
    export = dict(version=plan["version"], plan_fingerprint=plan["plan_fingerprint"],
        reference_freeze_sha256=plan["freeze_sha256"], dataset_role="synthetic_exploratory_system_outputs",
        operational=False, cases=rows, accounted_usd=service.budget.accounted(),
        unknown_cost_attempts=service.tracker.unknown_cost_count(),
        diagnostic_manifest_sha256=hashlib.sha256((root / "diagnostic-manifest.json").read_bytes()).hexdigest(),
        diagnostics_complete=all(e.sidecar_id is not None for e in entries))
    write_json(root / "nacho-outputs.json", export)
    return export


def audit(path: Path, expected_sha256: str, *, store=None, now=None):
    """Pinned metadata-only audit, usable after the response's 24-hour TTL."""
    if path.stat().st_size > 131072:
        raise ValueError("diagnostic_manifest_hash_or_size_invalid")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256 or len(raw) > 131072:
        raise ValueError("diagnostic_manifest_hash_or_size_invalid")
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate_manifest_field")
            value[key] = item
        return value
    json.loads(raw, object_pairs_hook=unique)
    manifest = DiagnosticManifest.model_validate_json(raw)
    now = now or datetime.now(timezone.utc)
    if not manifest.created_at <= now < manifest.expires_at:
        raise ValueError("diagnostic_manifest_retention_expired_or_future")
    store = store or SidecarStore()
    counts = {}
    for entry in manifest.cases:
        if entry.status != "persisted":
            raise ValueError("diagnostic_manifest_incomplete")
        sidecar = store.read(manifest.run_id, entry.case_id, expected_id=entry.sidecar_id, now=now)
        fields = ("request_id", "revision_id", "source_evidence_fingerprint", "request_evidence_fingerprint", "wire_fingerprint", "cache_key")
        if (any(getattr(sidecar, k) != getattr(entry, k) for k in fields)
                or sidecar.settings_fingerprint != manifest.settings_fingerprint):
            raise ValueError("diagnostic_manifest_binding_mismatch")
        counts[sidecar.outcome] = counts.get(sidecar.outcome, 0) + 1
    return dict(status="diagnostic_manifest_verified_offline", cases=32, outcomes=counts,
                manifest_sha256=expected_sha256, provider_calls=0, content_reads=0)
