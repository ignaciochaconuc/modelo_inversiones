"""Opt-in, read-only review dispositions; no contractual adapter or provider imports."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = "news-pilot-review-disposition-v1"
POLICY = "news-pilot-semantic-timing-separation-proposal-v2"
PROPOSAL_PATH = "docs/phase4c2-pilot-semantic-timing-separation-proposal-v2.md"
PROPOSAL_SHA256 = "663102a7caaf7ef6ea53b5dfec90a1b0bf22933d72a6982ebd4b0e385601d453"
INVENTORY_PATH = "data/cache/news_development_pilot/factual-six-case-balance-v1/inventory.json"
INVENTORY_SHA256 = "c016de6fb0dcaa0372e6db58cf9d54aa45b4f98ddffea36f87e246a6cc2feb18"
APPROVAL_VERSION = "news-development-pilot-owner-content-approval-evidence-v1"
APPROVAL_DECISIONS = {
    "approved_content_only", "approved_factual_proposal_v2_including_materiality_changes",
    "approved_complete_factual_content_v1", "approved_complete_factual_content_v1_after_confirmation_and_validation",
    "approved_complete_factual_content_v2_after_authorized_coverage_correction",
}
Phase = Literal["reading", "factual_annotation", "citation_check", "contract_review",
                "discrepancies", "adjudication", "administration"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def nonblank_strings(self):
        if any(isinstance(v, str) and not v.strip() for v in self.__dict__.values()):
            raise ValueError("blank_metadata_field")
        return self


class Ref(Model):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Provenance(Model):
    approver_identity: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    annotation_origin: Literal["chatgpt_assisted_exploratory_review"]
    independent_human_review: Literal[False]
    adjudication_claimed: Literal[False]
    approval_timestamp: datetime | None


class Content(Model):
    status: Literal["owner_approved_content"]
    decision: Ref
    provenance: Provenance


class Closure(Model):
    status: Literal["open", "closed_content_only_untimed", "closed_under_legacy_protocol"]
    decision: Ref | None


class Estimate(Model):
    value: float = Field(ge=0, strict=True)
    unit: Literal["minute"]
    approximate: Literal[True]
    source: Literal["owner_estimate"]
    exact_measurement: Literal[False]


class Declaration(Model):
    value: float = Field(ge=0, strict=True)
    unit: Literal["seconds"]
    source: Literal["owner_declaration"]
    measurement_method: None
    stopwatch_used: None
    is_estimate: None
    independently_verified: Literal[False]


class TimingAxis(Model):
    status: Literal["unknown", "estimate_only", "declared_duration_unvalidated",
                    "valid_measured_scope", "valid_complete_measurement", "invalid_or_expired"]
    original_form: Ref
    reading: Estimate | Declaration | None
    measurement: Ref | None
    measured_scope: tuple[Phase, ...]


class Effort(Model):
    status: Literal["excluded", "eligible_for_named_scope"]
    scope: tuple[Phase, ...]
    reason: str = Field(min_length=1)
    attestation: Ref | None


class Disposition(Model):
    schema_version: Literal["news-pilot-review-disposition-v1"]
    disposition_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    case_id: str = Field(min_length=1)
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    annotation: Ref
    annotation_version: str = Field(min_length=1)
    annotation_schema: Literal["news-pilot-factual-form-v1"]
    legacy_factual_status: Literal["unfilled", "in_progress", "completed"]
    methodology_authorization: Ref
    content: Content
    closure: Closure
    timing: TimingAxis
    effort: Effort
    supersedes: Ref | None


class Authorization(Model):
    schema_version: Literal["news-pilot-methodology-authorization-v1"]
    policy_version: Literal["news-pilot-semantic-timing-separation-proposal-v2"]
    proposal: Ref
    approved: Literal[True]
    authorized_by: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    owner_statement: str = Field(min_length=1)
    source_message_id: str | None
    authorized_at: datetime | None
    scope: Literal["development_pilot_dispositions_only"]
    case_closures_authorized_by_this_record: Literal[False]
    contractual_adapter_authorized: Literal[False]
    inference_authorized: Literal[False]


class Coverage(Model):
    canonical_ids: tuple[str, ...] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ClosureDecision(Model):
    schema_version: Literal["news-pilot-factual-closure-decision-v1"]
    policy_version: Literal["news-pilot-semantic-timing-separation-proposal-v2"]
    case_id: str
    packet_fingerprint: str
    annotation_sha256: str
    approval_sha256: str
    authorization_sha256: str
    mode: Literal["closed_content_only_untimed", "closed_under_legacy_protocol"]
    explicitly_approved: Literal[True]
    decided_by: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    decided_at: datetime | None
    factual_evidence_reviewed: Literal[True]
    uncertainty_preserved: Literal[True]
    unresolved_semantic_changes: Literal[False]
    material_coverage: dict[str, Coverage]


class EffortAttestation(Model):
    schema_version: Literal["news-pilot-effort-attestation-v1"]
    case_id: str
    measurement_sha256: str
    review_id: str
    reviewer_id: str
    scope: tuple[Phase, ...]
    clock_evidence: Ref
    quality_reviewed_by: str = Field(min_length=1)
    decision_source: str = Field(min_length=1)
    population: str = Field(min_length=1)
    familiarity: str = Field(min_length=1)
    assistance: str = Field(min_length=1)
    human_time_separated_from_ai_and_waits: Literal[True]


class Manifest(Model):
    schema_version: Literal["news-pilot-review-disposition-manifest-v1"]
    policy: Ref
    source_inventory: Ref
    records: tuple[Ref, ...]


def legacy_module():
    """Load definitions only; never run the historical CLI or change its contracts."""
    name = "pilot_disposition_legacy"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("development_pilot_review.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value: dict) -> str:
    body = {k: v for k, v in value.items() if k != "disposition_id"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def path_for(repo: Path, name: str) -> Path:
    """Reject absolute, traversal, alternate stream, URL and escaping symlink paths."""
    require(not PureWindowsPath(name).is_absolute() and not PureWindowsPath(name).drive
            and ":" not in name and "\\" not in name, "unsafe_reference_path")
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe_reference_path")
    resolved = (repo / relative).resolve()
    require(resolved.is_relative_to(repo.resolve()), "reference_outside_repository")
    return resolved


def bound_path(repo: Path, ref: Ref) -> Path:
    path = path_for(repo, ref.path)
    require(digest(path) == ref.sha256, "reference_hash_mismatch")
    return path


def read_ref(repo: Path, ref: Ref) -> dict:
    # Parse exactly the bytes whose digest was checked, not a second file read.
    payload = path_for(repo, ref.path).read_bytes()
    require(hashlib.sha256(payload).hexdigest() == ref.sha256, "reference_hash_mismatch")
    return json.loads(payload.decode("utf-8"))


def check_date(value: datetime | None, now: datetime) -> None:
    if value is not None:
        require(value.utcoffset() is not None and value <= now, "invalid_decision_timestamp")


def validate_record(repo: Path, record: Disposition, packet: dict, *, now: datetime,
                    seen: frozenset[str] = frozenset()) -> dict:
    """Validate declared provenance and integrity, never entailment or real-world clocks."""
    require(now.utcoffset() is not None, "timezone_required")
    legacy = legacy_module()
    raw = record.model_dump(mode="json")
    require(identity(raw) == record.disposition_id, "disposition_identity_mismatch")
    require(record.disposition_id not in seen, "supersession_cycle")
    require(record.case_id == packet["case_id"] and record.packet_fingerprint == packet["packet_fingerprint"], "packet_binding_mismatch")
    factual = legacy.Factual.model_validate(read_ref(repo, record.annotation))
    require(factual.case_id == record.case_id and factual.packet_fingerprint == record.packet_fingerprint
            and factual.status == record.legacy_factual_status, "annotation_binding_mismatch")
    legacy.validate_factual(factual, packet)

    auth = Authorization.model_validate(read_ref(repo, record.methodology_authorization))
    require(auth.proposal.path == PROPOSAL_PATH and auth.proposal.sha256 == PROPOSAL_SHA256, "wrong_methodology_policy")
    bound_path(repo, auth.proposal)
    check_date(auth.authorized_at, now)
    a = read_ref(repo, record.content.decision)
    require(a.get("version") == APPROVAL_VERSION and a.get("decision") in APPROVAL_DECISIONS
            and a.get("record_kind") == "documentary_owner_decision_not_protocol_completion"
            and a.get("scope") == "development_pilot_factual_content_only", "unsupported_approval")
    # The second legacy record predates an annotation_version field; its exact
    # version is explicitly named by its decision, not guessed from a filename.
    approval_version = a.get("annotation_version") or {
        "approved_factual_proposal_v2_including_materiality_changes": "factual-proposal-v2",
    }.get(a.get("decision"))
    require(a.get("case_id") == record.case_id and a.get("annotation_sha256") == record.annotation.sha256
            and a.get("packet_fingerprint") == record.packet_fingerprint
            and approval_version == record.annotation_version, "approval_binding_mismatch")
    require(a.get("full_content_approval", a.get("decision") == "approved_content_only") is True
            and a.get("approval_condition_satisfied", True) is True, "approval_not_complete")
    require(record.content.provenance.model_dump(mode="json") == {
        k: a.get(k) for k in Provenance.model_fields}, "approval_provenance_mismatch")
    require(a.get("independent_human_review") is False and a.get("adjudication_claimed") is False,
            "unsupported_independence_or_adjudication")
    check_date(record.content.provenance.approval_timestamp, now)

    original = legacy.Timing.model_validate(read_ref(repo, record.timing.original_form))
    require(original.case_id == record.case_id and original.packet_fingerprint == record.packet_fingerprint, "timing_binding_mismatch")
    # A nonempty source is never bypassed just because the caller claims it is untimed.
    legacy.validate_timing(original, now=now)
    reading = a.get("reading_duration_declaration", a.get("reading_estimate"))
    actual_reading = record.timing.reading.model_dump(mode="json") if record.timing.reading else None
    require(actual_reading == reading, "reading_provenance_mismatch")
    expected_status = "unknown" if reading is None else ("estimate_only" if reading.get("source") == "owner_estimate" else "declared_duration_unvalidated")
    measured = record.timing.status in {"valid_measured_scope", "valid_complete_measurement"}
    timing = None
    if not measured:
        require(record.timing.status == expected_status, "unsupported_timing_classification")
        require(record.timing.measurement is None and not record.timing.measured_scope, "unvalidated_measurement_claim")
        require(original.status == "unfilled", "nonempty_timing_requires_measurement_validation")
    else:
        require(record.timing.measurement is not None, "measurement_required")
        timing = legacy.Timing.model_validate(read_ref(repo, record.timing.measurement))
        require(timing.case_id == record.case_id and timing.packet_fingerprint == record.packet_fingerprint, "measurement_binding_mismatch")
        require(timing.completed_at is not None and timing.status != "unfilled", "bounded_measurement_required")
        legacy.validate_timing(timing, now=now)  # Includes exact 90-day boundary, anchored to the source.
        require(timing.active_seconds is not None and timing.pause_seconds is not None and bool(timing.intervals), "measurement_totals_required")
        scope = record.timing.measured_scope
        require(bool(scope) and len(scope) == len(set(scope)), "measurement_scope_required")
        active = {i.phase for i in timing.intervals if i.kind == "active"}
        require(active <= set(scope) and all(timing.phase_seconds[p] is not None for p in scope), "measurement_scope_mismatch")
        if record.timing.status == "valid_measured_scope":
            require(active == set(scope), "unobserved_measurement_scope")
        if record.timing.status == "valid_complete_measurement":
            require(timing.status == "completed" and set(scope) == set(legacy.PHASES), "incomplete_measurement")

    e = record.effort
    if e.status == "excluded":
        require(not e.scope and e.attestation is None, "excluded_effort_has_scope")
    else:
        require(measured and e.attestation is not None and bool(e.scope)
                and len(e.scope) == len(set(e.scope)) and set(e.scope) <= set(record.timing.measured_scope), "invalid_effort_eligibility")
        att = EffortAttestation.model_validate(read_ref(repo, e.attestation))
        require(att.case_id == record.case_id and att.measurement_sha256 == record.timing.measurement.sha256
                and att.review_id == timing.review_id and att.reviewer_id == timing.reviewer_id
                and att.scope == e.scope, "effort_attestation_mismatch")
        bound_path(repo, att.clock_evidence)

    c = record.closure
    if c.status == "open":
        require(c.decision is None, "open_closure_has_decision")
    else:
        require(c.decision is not None and c.decision.path != record.content.decision.path
                and c.decision.sha256 != record.content.decision.sha256, "separate_closure_decision_required")
        decision = ClosureDecision.model_validate(read_ref(repo, c.decision))
        require(decision.case_id == record.case_id and decision.packet_fingerprint == record.packet_fingerprint
                and decision.annotation_sha256 == record.annotation.sha256
                and decision.approval_sha256 == record.content.decision.sha256
                and decision.authorization_sha256 == record.methodology_authorization.sha256
                and decision.mode == c.status and decision.decided_by == record.content.provenance.approver_identity,
                "closure_decision_binding_mismatch")
        check_date(decision.decided_at, now)
        require(all(x.status is not None for x in factual.dimension_assessments.values()), "closure_unassessed_dimension")
        material = {f.fact_id for f in factual.facts if f.material is True} | set(factual.must_not_omit)
        require(set(decision.material_coverage) == material
                and all(set(v.canonical_ids) <= set(factual.must_not_omit) for v in decision.material_coverage.values()), "closure_material_coverage_required")
        if c.status == "closed_content_only_untimed":
            require(not measured and e.status == "excluded", "untimed_closure_claims_measurement")
        else:
            require(factual.status == "completed" and timing is not None and timing.factual_closed_at is not None,
                    "legacy_closure_requires_real_timing")
            require({"factual_annotation", "citation_check"} <= {
                i.phase for i in timing.intervals if i.kind == "active" and i.completed_at <= timing.factual_closed_at
            }, "legacy_factual_session_not_measured")

    if record.supersedes is not None:
        previous = Disposition.model_validate(read_ref(repo, record.supersedes))
        require(previous.case_id == record.case_id and previous.packet_fingerprint == record.packet_fingerprint,
                "supersession_case_mismatch")
        validate_record(repo, previous, packet, now=now, seen=seen | {record.disposition_id})
        if previous.annotation == record.annotation and previous.closure.status != "open":
            require(record.closure.status != "open", "closure_cannot_silently_reopen")
    return dict(case_id=record.case_id, content=record.content.status, closure=c.status,
                timing=record.timing.status, effort=e.status, semantic_truth="not_assessed",
                contractual_adapter="not_implemented", legacy_state_changed=False)


def verify(repo: Path, folder: Path, *, now: datetime) -> dict:
    """Check the six existing approvals against the immutable documentary inventory."""
    manifest = Manifest.model_validate(json.loads((folder / "manifest.json").read_text(encoding="utf-8")))
    require(manifest.source_inventory.path == INVENTORY_PATH and manifest.source_inventory.sha256 == INVENTORY_SHA256,
            "wrong_historical_inventory")
    inventory = read_ref(repo, manifest.source_inventory)
    packets = legacy_module().verify_packages(repo)
    require(len(manifest.records) == len(packets) == 6, "six_dispositions_required")
    expected_files = {"manifest.json"} | {Path(r.path).name for r in manifest.records}
    require({p.name for p in folder.iterdir()} == expected_files, "unexpected_disposition_files")
    rows = {r["case_id"]: r for r in inventory["cases"]}
    seen, results = set(), []
    for ref in manifest.records:
        require(path_for(repo, ref.path).parent == folder.resolve(), "disposition_outside_selected_folder")
        d = Disposition.model_validate(read_ref(repo, ref))
        require(d.case_id in packets and d.case_id not in seen, "duplicate_or_unknown_disposition")
        require(d.methodology_authorization == manifest.policy, "authorization_mismatch")
        row = rows[d.case_id]
        require(d.annotation.path == row["annotation_path"] and d.annotation.sha256 == row["annotation_sha256"]
                and d.content.decision.path == row["approval_path"] and d.content.decision.sha256 == row["approval_sha256"]
                and d.timing.original_form.sha256 == row["timing_sha256"], "historical_source_changed")
        require(d.effort.status == "excluded" and d.timing.measurement is None, "historical_attempt_timing_excluded")
        results.append(validate_record(repo, d, packets[d.case_id], now=now))
        seen.add(d.case_id)
    return dict(status="offline_dispositions_verified", cases=results, content_approved=6,
                factual_closed=sum(x["closure"] != "open" for x in results),
                eligible_measured_attempts=0, integral_pilot_completed=False, semantic_truth="not_assessed",
                provider_calls=0, predictions=0, contractual_adapter="not_implemented")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", type=Path, required=True, help="Explicitly select a disposition directory; read-only")
    args = parser.parse_args()
    try:
        result = verify(Path(__file__).resolve().parents[2], args.validate, now=datetime.now(timezone.utc))
        print(json.dumps(result))
        return 0
    except Exception:
        # Never echo arbitrary paths, provenance text, article content or Pydantic input.
        print(json.dumps(dict(status="blocked", error="pilot_disposition_validation_failed", provider_calls=0)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
