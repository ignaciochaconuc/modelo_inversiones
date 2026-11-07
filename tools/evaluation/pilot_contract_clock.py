"""Prospective operator clock for one authorized contractual case; never runs an LLM."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import os
import sys
import uuid
from typing import Literal

from pydantic import ValidationError

def _adapter():
    name = "contract_clock_adapter"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("pilot_contract_review.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


m = _adapter()

# Only fixed rule identifiers may cross the CLI boundary. Never print exception
# messages from parsers, filesystem operations or caller-supplied values.
SAFE_ERROR_CODES = frozenset({
    "clock_not_running", "clock_already_started", "clock_already_stopped",
    "clock_did_not_advance", "invalid_phase_transition", "invalid_pause_transition",
    "invalid_resume_transition", "unknown_clock_action", "operator_provenance_required",
    "clock_state_binding_mismatch", "clock_event_cycle", "clock_event_binding_mismatch",
    "clock_event_order_mismatch", "clock_chain_missing_start", "session_changed_outside_clock",
    "workspace_outside_repository", "reserved_form_not_selected", "reservation_source_mismatch",
    "reserved_file_outside_workspace", "reserved_authorization_mismatch",
    "reserved_review_id_already_used", "other_cases_must_remain_unfilled",
    "active_session_not_reserved", "unfilled_session_has_clock_state",
    "reference_hash_mismatch", "session_duration_mismatch", "incomplete_session_timeline",
    "incomplete_completed_session", "contract_session_metadata_expired",
    "owner_review_not_timed", "contract_mapping_not_timed",
})


def error_code(exc: Exception) -> str:
    """Expose an allowlisted condition, never arbitrary exception content."""
    if type(exc) is ValueError and len(exc.args) == 1 and isinstance(exc.args[0], str):
        if exc.args[0] in SAFE_ERROR_CODES:
            return exc.args[0]
    if isinstance(exc, ValidationError):
        return "schema_validation_failed"
    if isinstance(exc, OSError):
        return "clock_io_failed"
    return "unclassified_clock_failure"


class Reservation(m.Model):
    record_version: Literal["news-pilot-contract-opening-reservation-v1"]
    case_id: str
    review_id: str
    opening_authorization: m.Ref
    form_path: str
    session_path: str


def _load(repo: Path, folder: Path, *, now: datetime, allow_completed_other_cases: bool = False):
    m.d.require(folder.resolve().is_relative_to(repo.resolve()), "workspace_outside_repository")
    result = m.verify(repo, folder, now=now)
    reservation = Reservation.model_validate(json.loads((folder/"opening/reservation.json").read_text(encoding="utf-8")))
    auth = m.OpeningAuthorization.model_validate(m.d.read_ref(repo, reservation.opening_authorization))
    manifest = m.Manifest.model_validate(json.loads((folder/"manifest.json").read_text(encoding="utf-8")))
    matches = [(r, m.ContractForm.model_validate(m.d.read_ref(repo, r))) for r in manifest.forms
               if r.path == reservation.form_path]
    m.d.require(len(matches) == 1, "reserved_form_not_selected")
    ref, form = matches[0]
    m.d.require(form.case_id == reservation.case_id and form.session.path == reservation.session_path, "reservation_source_mismatch")
    for name in (reservation.form_path, reservation.session_path, reservation.opening_authorization.path):
        m.d.require(m.d.path_for(repo, name).is_relative_to(folder.resolve()), "reserved_file_outside_workspace")
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    m.d.require(auth.case_id == reservation.case_id and auth.review_id == reservation.review_id
        and auth.disposition_id == disposition.disposition_id and auth.factual_sha256 == form.factual.sha256
        and auth.closure_sha256 == form.closure_decision.sha256
        and auth.authorized_by == disposition.content.provenance.approver_identity, "reserved_authorization_mismatch")
    m.d.check_date(auth.authorized_at, now)
    m.d.require(all(r["case_id"] == reservation.case_id or r["review_id"] != reservation.review_id for r in result["cases"]),
        "reserved_review_id_already_used")
    other_states = {"unfilled", "completed"} if allow_completed_other_cases else {"unfilled"}
    m.d.require(all(r["case_id"] == reservation.case_id or r["status"] in other_states for r in result["cases"]),
        "other_cases_must_remain_unfilled")
    session = m.ContractSession.model_validate(m.d.read_ref(repo, form.session))
    if session.status != "unfilled":
        m.d.require(session.review_id == reservation.review_id
            and session.opening_authorization == reservation.opening_authorization, "active_session_not_reserved")
    return reservation, form, session, disposition, manifest


def _event_chain(repo: Path, state: dict, reservation: Reservation, session_ref) -> dict:
    m.d.require(state.get("review_id") == reservation.review_id and state.get("case_id") == reservation.case_id,
        "clock_state_binding_mismatch")
    last_ref = m.Ref.model_validate(state["last_event"])
    current, seen, newest = last_ref, set(), None
    later = None
    while current is not None:
        m.d.require(current.sha256 not in seen, "clock_event_cycle")
        event = m.d.read_ref(repo, current)
        m.d.require(event.get("event_version") == "news-pilot-contract-clock-event-v1"
            and event.get("review_id") == reservation.review_id and event.get("case_id") == reservation.case_id,
            "clock_event_binding_mismatch")
        at = datetime.fromisoformat(event["at"])
        m.d.require(at.utcoffset() is not None and (later is None or at < later), "clock_event_order_mismatch")
        later = at
        newest = newest or event
        seen.add(current.sha256)
        previous = event.get("previous_event")
        if previous is None:
            m.d.require(event["action"] == "start", "clock_chain_missing_start")
        current = m.Ref.model_validate(previous) if previous else None
    m.d.require(newest["session_sha256_after"] == session_ref.sha256, "session_changed_outside_clock")
    return newest


def status(repo: Path, folder: Path, *, now: datetime, allow_completed_other_cases: bool = False) -> dict:
    reservation, form, session, _, _ = _load(repo, folder, now=now,
        allow_completed_other_cases=allow_completed_other_cases)
    state_path = folder/"clock/state.json"
    if session.status == "unfilled":
        m.d.require(not state_path.exists(), "unfilled_session_has_clock_state")
        state = "authorized_waiting_for_real_start"
    else:
        event = _event_chain(repo, json.loads(state_path.read_text(encoding="utf-8")), reservation, form.session)
        state = event["next_kind"]
    return dict(case_id=reservation.case_id, review_id=reservation.review_id, authorization_valid=True,
        clock=state, session_status=session.status, mappings_recorded=len(form.mappings),
        provider_calls=0, inferences=0)


def _bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2)+"\n").encode("utf-8")


def _ref(path: Path, repo: Path, payload: bytes):
    import hashlib
    return m.Ref(path=path.resolve().relative_to(repo.resolve()).as_posix(), sha256=hashlib.sha256(payload).hexdigest())


def record(repo: Path, folder: Path, action: str, *, now: datetime, phase: str | None = None,
           reason: str | None = None, reviewer_id: str | None = None, reviewer_name: str | None = None,
           context: str | None = None, model_label: str | None = None,
           allow_completed_other_cases: bool = False) -> dict:
    """Called only by explicit operator action; tests inject synthetic clocks in temp dirs."""
    reservation, form, session, disposition, manifest = _load(repo, folder, now=now,
        allow_completed_other_cases=allow_completed_other_cases)
    raw = session.model_dump(mode="json")
    state_path = folder/"clock/state.json"
    previous = None
    if action == "start":
        m.d.require(session.status == "unfilled" and not state_path.exists(), "clock_already_started")
        m.d.require(phase in m.PHASES and all(x and x.strip() for x in (reviewer_id, reviewer_name, context)),
            "operator_provenance_required")
        raw.update(status="in_progress", opening_authorization=reservation.opening_authorization.model_dump(),
            review_id=reservation.review_id, reviewer_id=reviewer_id, reviewer_name=reviewer_name,
            execution_mode="manual_chatgpt_owner", independence_context=context, visible_model_label=model_label,
            timestamp_source="manual_clock", timestamp_basis="UTC system clock captured prospectively by explicit local operator commands; not platform-verified.",
            started_at=now.isoformat())
        next_kind, next_phase, next_reason = "active", phase, None
    else:
        m.d.require(session.status == "in_progress", "clock_not_running")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        event = _event_chain(repo, state, reservation, form.session)
        previous = state["last_event"]
        last = datetime.fromisoformat(event["at"])
        m.d.require(now.utcoffset() is not None and now > last, "clock_did_not_advance")
        kind = event["next_kind"]
        m.d.require(kind in {"active", "pause"}, "clock_already_stopped")
        if action == "phase":
            m.d.require(kind == "active" and phase in m.PHASES and phase != event["next_phase"], "invalid_phase_transition")
            next_kind, next_phase, next_reason = "active", phase, None
        elif action == "pause":
            m.d.require(kind == "active" and reason in {"break", "interruption", "ai_wait", "other"}, "invalid_pause_transition")
            next_kind, next_phase, next_reason = "pause", None, reason
        elif action == "resume":
            m.d.require(kind == "pause" and phase in m.PHASES, "invalid_resume_transition")
            next_kind, next_phase, next_reason = "active", phase, None
        else:
            m.d.require(action == "stop", "unknown_clock_action")
            next_kind, next_phase, next_reason = "stopped", None, None
        raw["intervals"].append(dict(kind=kind, phase=event["next_phase"], pause_reason=event["next_pause_reason"],
            started_at=last.isoformat(), completed_at=now.isoformat()))
        totals, pause = {p:0.0 for p in m.PHASES}, 0.0
        observed = set()
        for interval in raw["intervals"]:
            seconds = (datetime.fromisoformat(interval["completed_at"])-datetime.fromisoformat(interval["started_at"])).total_seconds()
            if interval["kind"] == "active":
                totals[interval["phase"]] += seconds
                observed.add(interval["phase"])
            else:
                pause += seconds
        raw.update(active_seconds=sum(totals.values()), pause_seconds=pause,
            phase_seconds={p:totals[p] if p in observed or action == "stop" else None for p in m.PHASES})
        if action == "stop":
            raw.update(status="completed", completed_at=now.isoformat())
    updated = m.ContractSession.model_validate(raw)
    m.validate_session(repo, updated, disposition, now=now)
    session_path = m.d.path_for(repo, reservation.session_path)
    form_path = m.d.path_for(repo, reservation.form_path)
    session_bytes = _bytes(updated.model_dump(mode="json"))
    new_session_ref = _ref(session_path, repo, session_bytes)
    new_form = form.model_copy(update={"session":new_session_ref, "status":"in_progress"})
    form_bytes = _bytes(new_form.model_dump(mode="json"))
    new_form_ref = _ref(form_path, repo, form_bytes)
    manifest_data = manifest.model_dump(mode="json")
    manifest_data["forms"] = [new_form_ref.model_dump() if r.path == reservation.form_path else r.model_dump() for r in manifest.forms]
    event = dict(event_version="news-pilot-contract-clock-event-v1", case_id=reservation.case_id,
        review_id=reservation.review_id, action=action, at=now.isoformat(), timestamp_source="local_operator_clock",
        next_kind=next_kind, next_phase=next_phase, next_pause_reason=next_reason, previous_event=previous,
        session_sha256_before=form.session.sha256, session_sha256_after=new_session_ref.sha256)
    clock = folder/"clock"
    clock.mkdir(exist_ok=True)
    token = uuid.uuid4().hex
    event_path = clock/(token+".event.json")
    event_bytes = _bytes(event)
    event_ref = _ref(event_path, repo, event_bytes)
    state = dict(case_id=reservation.case_id, review_id=reservation.review_id, last_event=event_ref.model_dump())
    # Retain prior mutable working records. These are timing metadata, not provider content.
    archive = clock/"history"/token
    archive.mkdir(parents=True)
    for path, name in ((session_path,"session.json"), (form_path,"form.json"), (folder/"manifest.json","manifest.json")):
        (archive/name).write_bytes(path.read_bytes())
    with event_path.open("xb") as out:
        out.write(event_bytes)
    for path, payload in [(session_path, session_bytes), (form_path, form_bytes), (state_path,_bytes(state)),
                          (folder/"manifest.json",_bytes(manifest_data))]:
        temporary = clock/(token+"-"+path.name+".pending")
        with temporary.open("xb") as out:
            out.write(payload)
        os.replace(temporary, path)
    m.verify(repo, folder, now=now)
    return status(repo, folder, now=now, allow_completed_other_cases=allow_completed_other_cases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("action", choices=["status","start","phase","pause","resume","stop"])
    parser.add_argument("--phase", choices=m.PHASES)
    parser.add_argument("--reason", choices=["break","interruption","ai_wait","other"])
    parser.add_argument("--reviewer-id")
    parser.add_argument("--reviewer-name")
    parser.add_argument("--context")
    parser.add_argument("--model-label")
    args = parser.parse_args()
    try:
        repo = Path(__file__).resolve().parents[2]
        now = datetime.now(timezone.utc)  # Never persisted by status, never supplied as a retrospective CLI argument.
        if args.action == "status":
            result = status(repo,args.workspace,now=now)
        else:
            result = record(repo,args.workspace,args.action,now=now,phase=args.phase,reason=args.reason,
                reviewer_id=args.reviewer_id,reviewer_name=args.reviewer_name,context=args.context,model_label=args.model_label)
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status="blocked",error="contract_clock_validation_failed",
            error_code=error_code(exc),provider_calls=0)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
