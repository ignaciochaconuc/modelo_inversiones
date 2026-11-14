"""Read-only preparatory declarations; deliberately incompatible with clock authorization."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Literal

from pydantic import Field, ValidationError, model_validator


def execution_module():
    """Reuse pinned v1 definitions without modifying its code or loading credentials."""
    name = "preparation_pinned_prospective_clock_v1"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("prospective_timing_pilot.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


clock = execution_module()
VERSION = "news-prospective-timing-preparation-v1"
Pending = Literal["reviewer_id", "familiarity_statement", "declaration_source", "familiarity_confirmed",
                  "first_reading", "unseen_counterfactual", "execution_authorization"]


class Preparation(clock.Model):
    version: Literal["news-prospective-timing-preparation-v1"]
    status: Literal["preparation_only"]
    scope: Literal["preparation_and_preflight_only"]
    start_authorized: Literal[False]
    eligibility_granted: Literal[False]
    plan_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    case_id: str
    session_id: str
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    responsible_reference: Literal["Project owner, current conversation participant"]
    reviewer_id: str | None
    familiarity_statement: str | None = Field(repr=False)
    familiarity_status: Literal["unknown", "owner_declares_seen", "owner_declares_unseen"]
    first_reading: Literal["unknown", "declared_yes", "declared_no"]
    variant_exposure: Literal["unknown", "owner_declares_seen", "owner_declares_unseen"]
    assistance: Literal["manual_chatgpt_owner"]
    declaration_source: str | None = Field(repr=False)
    declared_at: datetime | None
    source_message_id: str | None
    independent_human_review: Literal[False]
    adjudication_claimed: Literal[False]
    pending_fields: tuple[Pending, ...]

    @model_validator(mode="after")
    def explicit_pending_information(self):
        expected = {"execution_authorization"}  # Preparation never records execution consent.
        if self.reviewer_id is None:
            expected.add("reviewer_id")
        else:
            clock.require(bool(self.reviewer_id.strip()), "empty_reviewer_reference")
        for field in ("familiarity_statement", "declaration_source"):
            value = getattr(self, field)
            if value is None:
                expected.add(field)
            else:
                clock.require(bool(value.strip()), "empty_declaration")
        if self.familiarity_status == "unknown":
            expected.add("familiarity_confirmed")
        if self.first_reading == "unknown":
            expected.add("first_reading")
        if self.variant_exposure == "unknown":
            expected.add("unseen_counterfactual")
        clock.require(len(self.pending_fields) == len(set(self.pending_fields))
                      and set(self.pending_fields) == expected, "pending_information_mismatch")
        return self


def reject_as_execution_authorization(preparation: Preparation) -> None:
    """Explicit separation boundary, not a converter or an alternative clock entry point."""
    raise ValueError("preparation_is_not_execution_authorization")


def validate_preparation(repo: Path, plan, preparation: Preparation, *, now: datetime) -> dict:
    clock.aware(now, now)
    clock.require(preparation.plan_fingerprint == clock.fingerprint(plan), "stale_preparation_plan")
    slots = [s for s in plan.sessions if s.session_id == preparation.session_id]
    clock.require(len(slots) == 1 and slots[0].stage == "factual"
                  and slots[0].case_id == preparation.case_id, "preparation_session_mismatch")
    candidate = next(c for c in plan.candidates if c.case_id == preparation.case_id)
    clock.require(candidate.packet_fingerprint == preparation.packet_fingerprint, "preparation_packet_mismatch")
    if preparation.declared_at is not None:
        clock.aware(preparation.declared_at, now)
    # Check the actual unmodified executable parser too: a path change cannot help.
    try:
        clock.Authorization.model_validate(preparation.model_dump(mode="json"))
    except ValidationError:
        pass
    else:
        raise ValueError("preparation_unexpectedly_satisfies_execution_schema")
    preflight = clock.verify(repo, plan, repo/plan.records_directory, now=now)
    return dict(version=VERSION, preparation_valid=True, case_id=preparation.case_id,
                session_id=preparation.session_id, packet_fingerprint=preparation.packet_fingerprint,
                plan_fingerprint=preparation.plan_fingerprint, status=preparation.status,
                start_authorized=False, eligibility_granted=False,
                executable_authorization_compatible=False,
                familiarity_status=preparation.familiarity_status, first_reading=preparation.first_reading,
                variant_exposure=preparation.variant_exposure, assistance=preparation.assistance,
                pending_fields=list(preparation.pending_fields), preflight=preflight,
                integral_pilot_completed=False, semantic_truth="not_assessed",
                factual_timing_rehabilitated=False, provider_calls=0, inferences=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("command", choices=["validate"])
    args = parser.parse_args()
    try:
        repo = Path(__file__).resolve().parents[2]
        plan = clock.load_plan(repo, args.plan)
        record = Preparation.model_validate_json(args.record.read_text(encoding="utf-8"))
        result = validate_preparation(repo, plan, record, now=datetime.now(timezone.utc))
        print(json.dumps(result))
        return 0
    except Exception:
        print(json.dumps(dict(status="blocked", error="prospective_preparation_validation_failed", provider_calls=0, inferences=0)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
