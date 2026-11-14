"""Isolated prospective workload clock; never interprets news or certifies human work."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, StrictBool, model_validator

VERSION = "news-prospective-timing-pilot-v1"
STORAGE = Path("data/cache/news_prospective_timing_pilot")
PHASES = {
    "factual": ("factual_reading", "factual_annotation", "citation_check", "factual_owner_review"),
    "contractual": ("contract_reading", "contract_mapping", "contract_check", "contract_owner_review"),
    "administration": ("batch_administration",),
}
PAUSES = {"ai_wait", "break", "interruption", "other"}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def literal_flags(cls, value):
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                args = get_args(field.annotation)
                if args and type(args[0]) is bool and name in value:
                    require(value[name] is args[0], "explicit_boolean_required")
        return value


class Ref(Model):
    path: str
    sha256: str


class Candidate(Model):
    case_id: str
    family_id: str
    packet_fingerprint: str
    request_fingerprint: str


class Slot(Model):
    session_id: str
    case_id: str
    stage: Literal["factual", "contractual"]


class Plan(Model):
    version: Literal["news-prospective-timing-pilot-v1"]
    kind: Literal["prepared_real_calibration", "synthetic_fixture"]
    purpose: Literal["development_workload_only"]
    records_directory: str
    instrument: Ref
    protocol: Ref
    source_manifest: Ref
    corpus: Ref
    private_design: Ref
    historical_selection: Ref
    technical_reference: Ref
    candidates: tuple[Candidate, ...]
    sessions: tuple[Slot, ...]
    administration_id: str


class Authorization(Model):
    version: Literal["news-prospective-timing-authorization-v1"]
    plan_fingerprint: str
    session_id: str
    explicitly_authorized: StrictBool
    authorized_by: str
    decision_source: str
    authorized_at: datetime | None
    source_message_id: str | None
    reviewer_id: str
    reviewer_name: str
    assistance: Literal["manual_human", "manual_chatgpt_owner"]
    visible_model_label: str | None
    familiarity_confirmed: StrictBool
    first_reading: StrictBool
    unseen_counterfactual: StrictBool
    familiarity_basis: str
    factual_tip: str | None
    factual_source: Ref | None
    factual_content_ready: StrictBool
    independent_human_review: Literal[False]
    adjudication_claimed: Literal[False]
    inference_authorized: Literal[False]


class Event(Model):
    version: Literal["news-prospective-timing-event-v1"]
    kind: Literal["prepared_real_calibration", "synthetic_fixture"]
    plan_fingerprint: str
    session_id: str
    sequence: int
    previous: str | None
    action: Literal["start", "phase", "pause", "resume", "stop"]
    at: datetime
    next_kind: Literal["active", "pause", "stopped"]
    phase: str | None
    pause_reason: str | None
    authorization: Ref


class Attestation(Model):
    version: Literal["news-prospective-timing-eligibility-v1"]
    plan_fingerprint: str
    session_id: str
    session_tip: str
    explicitly_attested: StrictBool
    eligible_for_named_scope: StrictBool
    scope: tuple[str, ...]
    task_complete: StrictBool
    recording_complete: StrictBool
    no_unlogged_multitasking: StrictBool
    decided_by: str
    decision_source: str
    decided_at: datetime | None
    independent_human_review: Literal[False]


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(plan: Plan) -> str:
    return hashlib.sha256(encoded(plan.model_dump(mode="json"))).hexdigest()


def bound(repo: Path, ref: Ref) -> Path:
    path = (repo / ref.path).resolve()
    require(path.is_relative_to(repo.resolve()) and path.is_file(), "invalid_reference_path")
    require(digest(path) == ref.sha256, "reference_hash_mismatch")
    return path


def read_ref(repo: Path, ref: Ref) -> dict:
    return json.loads(bound(repo, ref).read_text(encoding="utf-8"))


def ref_for(repo: Path, path: Path) -> Ref:
    path = path.resolve()
    require(path.is_relative_to(repo.resolve()), "reference_outside_repository")
    return Ref(path=path.relative_to(repo.resolve()).as_posix(), sha256=digest(path))


def load_plan(repo: Path, path: Path) -> Plan:
    plan = Plan.model_validate_json(path.read_text(encoding="utf-8"))
    for ref in (plan.instrument, plan.protocol, plan.source_manifest, plan.corpus,
                plan.private_design, plan.historical_selection, plan.technical_reference):
        bound(repo, ref)
    require(plan.instrument.path == "tools/evaluation/prospective_timing_pilot.py", "wrong_instrument")
    manifest = read_ref(repo, plan.source_manifest)
    require(manifest["reserved_cases_created"] == 0 and manifest["reserved_freeze_created"] is False
            and manifest["reference_status"] == "not_created", "development_only_required")
    for ref in (plan.corpus, plan.private_design, plan.historical_selection):
        require(manifest["sha256"].get(ref.path) == ref.sha256, "source_manifest_mismatch")
    technical = read_ref(repo, plan.technical_reference)
    require(technical.get("contract_version") == "news-economic-validation-v3"
            and set(technical.get("files", {})) == {
                f"src/investment_system/agents/news_interpretation/{name}.py"
                for name in ("economic_attribution", "grounding", "replay", "schemas")}, "technical_version_mismatch")
    for name, sha in technical["files"].items():
        bound(repo, Ref(path=name, sha256=sha))
    corpus = read_ref(repo, plan.corpus)
    require(corpus["purpose"] == "development_only" and corpus["fictional"] is True, "development_only_required")
    rows = {x["case_id"]: x for x in corpus["cases"]}
    private = {x["case_id"]: x for x in read_ref(repo, plan.private_design)["cases"]}
    excluded = set(read_ref(repo, plan.historical_selection)["selected_case_ids"])
    require(len(plan.candidates) == len({x.case_id for x in plan.candidates}) == 3
            and len({x.family_id for x in plan.candidates}) == 3, "three_distinct_families_required")
    allowed = {"case_id", "primary_revision_id", "request", "request_fingerprint", "evidence", "evidence_fingerprint", "packet_fingerprint"}
    for candidate in plan.candidates:
        row = rows.get(candidate.case_id)
        require(candidate.case_id not in excluded and row is not None and set(row) == allowed,
                "ineligible_source_inventory")
        require(set(row["request"]) <= {"schema_version", "prompt_version", "taxonomy_version", "decision_time",
                    "mode", "allow_historical_proxy", "allow_retrospective_registry", "news", "context_news",
                    "registry_entries", "snapshot", "target"}, "unexpected_request_fields")
        require(row["packet_fingerprint"] == candidate.packet_fingerprint
                and row["request_fingerprint"] == candidate.request_fingerprint
                and private[candidate.case_id]["family_id"] == candidate.family_id, "candidate_binding_mismatch")
    expected = {(x.case_id, stage) for x in plan.candidates for stage in ("factual", "contractual")}
    require(len(plan.sessions) == 6 and {(s.case_id, s.stage) for s in plan.sessions} == expected,
            "six_reservations_required")
    ids = [s.session_id for s in plan.sessions] + [plan.administration_id]
    require(len(set(ids)) == 7 and all(x.startswith("pt-") and len(x) > 10
            and all(c.isalnum() or c == "-" for c in x) for x in ids), "new_namespaced_ids_required")
    return plan


def stage_for(plan: Plan, session_id: str) -> str:
    if session_id == plan.administration_id:
        return "administration"
    matches = [s for s in plan.sessions if s.session_id == session_id]
    require(len(matches) == 1, "unknown_session")
    return matches[0].stage


def storage(repo: Path, folder: Path) -> Path:
    folder = folder.resolve()
    base = (repo / STORAGE).resolve()
    require(base == repo.resolve()/STORAGE and folder.is_relative_to(base) and folder != base,
            "isolated_storage_required")
    return folder


def aware(at: datetime, now: datetime) -> None:
    require(at.utcoffset() is not None and at <= now, "invalid_real_timestamp")


def authorization(repo: Path, plan: Plan, session_id: str, ref: Ref, *, now: datetime) -> Authorization:
    auth = Authorization.model_validate(read_ref(repo, ref))
    require(auth.explicitly_authorized is True and auth.plan_fingerprint == fingerprint(plan)
            and auth.session_id == session_id and auth.familiarity_confirmed is True, "explicit_authorization_required")
    require(auth.authorized_by == "Project owner, current conversation participant"
            and all(x.strip() for x in (auth.reviewer_id, auth.reviewer_name, auth.decision_source, auth.familiarity_basis)),
            "actual_provenance_required")
    if auth.authorized_at is not None:
        aware(auth.authorized_at, now)
    require(auth.assistance != "manual_human" or auth.visible_model_label is None, "invalid_model_provenance")
    if stage_for(plan, session_id) == "factual":
        require(auth.first_reading and auth.unseen_counterfactual and auth.factual_source is None
                and auth.factual_tip is None and not auth.factual_content_ready, "first_reading_not_confirmed")
    return auth


def read_session(repo: Path, plan: Plan, folder: Path, session_id: str, *, now: datetime) -> dict:
    stage = stage_for(plan, session_id)
    directory = folder / session_id
    if not directory.exists():
        return dict(state="unfilled", tip=None, phase_seconds={}, active_seconds=None, pause_seconds=None)
    files = sorted(directory.glob("*.event.json"))
    require(bool(files), "incomplete_persistence")
    latest = Event.model_validate_json(files[-1].read_text(encoding="utf-8"))
    if latest.action == "stop":
        require(now < latest.at + timedelta(days=90), "timing_metadata_expired")
    previous = None
    last = None
    totals = {p: 0.0 for p in PHASES[stage]}
    pauses = 0.0
    auth = None
    for index, path in enumerate(files):
        event = Event.model_validate_json(path.read_text(encoding="utf-8"))
        require(path.name == f"{index:04d}.event.json" and event.sequence == index
                and event.previous == previous and event.session_id == session_id
                and event.plan_fingerprint == fingerprint(plan) and event.kind == plan.kind, "event_chain_mismatch")
        aware(event.at, now)
        current_auth = authorization(repo, plan, session_id, event.authorization, now=now)
        require(auth is None or current_auth == auth, "authorization_changed")
        auth = current_auth
        if last is None:
            require(event.action == "start" and event.next_kind == "active", "missing_start")
        else:
            require(last.next_kind != "stopped" and event.at > last.at, "invalid_transition_time")
            seconds = (event.at-last.at).total_seconds()
            if last.next_kind == "active":
                totals[last.phase] += seconds
            else:
                pauses += seconds
            require((event.action == "phase" and last.next_kind == "active" and event.next_kind == "active")
                    or (event.action == "pause" and last.next_kind == "active" and event.next_kind == "pause")
                    or (event.action == "resume" and last.next_kind == "pause" and event.next_kind == "active")
                    or (event.action == "stop" and event.next_kind == "stopped"), "invalid_transition")
        require((event.next_kind == "active" and event.phase in PHASES[stage] and event.pause_reason is None)
                or (event.next_kind == "pause" and event.phase is None and event.pause_reason in PAUSES)
                or (event.next_kind == "stopped" and event.phase is None and event.pause_reason is None), "invalid_phase")
        previous, last = digest(path), event
    allowed = {p.name for p in files} | {"eligibility.json"}
    require({p.name for p in directory.iterdir()} <= allowed, "unexpected_session_file")
    return dict(state=last.next_kind, tip=previous, phase_seconds=totals,
                active_seconds=sum(totals.values()), pause_seconds=pauses,
                authorization=auth, last=last, complete_phases=all(x > 0 for x in totals.values()))


def validate_eligibility(repo: Path, plan: Plan, session_id: str, value: Attestation, session: dict, *, now: datetime) -> None:
    require(session["state"] == "stopped" and value.plan_fingerprint == fingerprint(plan)
            and value.session_id == session_id and value.session_tip == session["tip"]
            and value.explicitly_attested and value.decided_by == session["authorization"].reviewer_name
            and bool(value.decision_source.strip()), "invalid_eligibility_attestation")
    if value.decided_at is not None:
        aware(value.decided_at, now)
        require(value.decided_at >= session["last"].at, "attestation_before_stop")
    if value.eligible_for_named_scope:
        require(session["complete_phases"] and value.task_complete and value.recording_complete
                and value.no_unlogged_multitasking and set(value.scope) == set(PHASES[stage_for(plan, session_id)])
                and len(value.scope) == len(set(value.scope)), "scope_not_eligible")
    else:
        require(not value.scope, "excluded_scope_must_be_empty")


def verify(repo: Path, plan: Plan, folder: Path, *, now: datetime) -> dict:
    return _verify(repo, plan, folder, now=now)


def _verify(repo: Path, plan: Plan, folder: Path, *, now: datetime, owns_lock: bool = False) -> dict:
    aware(now, now)
    folder = storage(repo, folder)
    require(folder == storage(repo, repo/plan.records_directory), "plan_storage_binding_mismatch")
    ids = [s.session_id for s in plan.sessions] + [plan.administration_id]
    if folder.exists():
        require({p.name for p in folder.iterdir()} <= set(ids) | ({".lock"} if owns_lock else set()), "unexpected_batch_file_or_lock")
    sessions = {sid: read_session(repo, plan, folder, sid, now=now) for sid in ids}
    active = [v for v in sessions.values() if v["state"] in {"active", "pause"}]
    require(len(active) <= 1, "overlapping_sessions")
    for slot in plan.sessions:
        current = sessions[slot.session_id]
        if slot.stage == "contractual" and current["state"] != "unfilled":
            parent_id = next(s.session_id for s in plan.sessions if s.case_id == slot.case_id and s.stage == "factual")
            parent = sessions[parent_id]
            auth = current["authorization"]
            require(parent["state"] == "stopped" and parent["complete_phases"] and auth.factual_tip == parent["tip"]
                    and auth.factual_content_ready and auth.factual_source is not None and not auth.first_reading
                    and current["last"].authorization is not None, "factual_gate_missing")
            artifact = read_ref(repo, auth.factual_source)
            require(artifact.get("case_id") == slot.case_id, "factual_source_case_mismatch")
            # The artifact is a binding, not a certificate of semantic correctness.
            first = Event.model_validate_json((folder/slot.session_id/"0000.event.json").read_text(encoding="utf-8"))
            require(first.at > parent["last"].at, "contract_before_factual_stop")
    eligible = 0
    timeline = []
    for sid, session in sessions.items():
        if session["state"] != "unfilled":
            first = Event.model_validate_json((folder/sid/"0000.event.json").read_text(encoding="utf-8"))
            timeline.append((first.at, session["last"].at, session["state"]))
        path = folder/sid/"eligibility.json"
        if path.exists():
            value = Attestation.model_validate_json(path.read_text(encoding="utf-8"))
            validate_eligibility(repo, plan, sid, value, session, now=now)
            eligible += int(value.eligible_for_named_scope)
    timeline.sort()
    for left, right in zip(timeline, timeline[1:]):
        require(left[2] == "stopped" and left[1] < right[0], "overlapping_sessions")
    return dict(status="offline_timing_verified", plan_fingerprint=fingerprint(plan),
                case_sessions={s.session_id: sessions[s.session_id]["state"] for s in plan.sessions},
                administration_state=sessions[plan.administration_id]["state"], eligible_records=eligible,
                structural_validation_only=True, integral_pilot_completed=False, semantic_truth="not_assessed",
                factual_timing_rehabilitated=False, provider_calls=0, inferences=0)


def material(repo: Path, plan: Plan, folder: Path, session_id: str, *, now: datetime) -> dict:
    """Explicit local disclosure only after a real authorized reading start."""
    verify(repo, plan, folder, now=now)
    session = read_session(repo, plan, folder, session_id, now=now)
    stage = stage_for(plan, session_id)
    require(stage != "administration" and session["state"] == "active"
            and session["last"].phase == PHASES[stage][0], "authorized_reading_required")
    if stage == "contractual":
        return dict(factual=read_ref(repo, session["authorization"].factual_source),
                    technical_reference=read_ref(repo, plan.technical_reference))
    slot = next(s for s in plan.sessions if s.session_id == session_id)
    row = next(x for x in read_ref(repo, plan.corpus)["cases"] if x["case_id"] == slot.case_id)
    request = row["request"]
    # Allowlist projection: no private family/stratum, author intent, predictions or scoring.
    return dict(case_id=slot.case_id, primary_revision_id=row["primary_revision_id"],
                headline=request["news"]["headline"], summary=request["news"]["summary"],
                decision_time=request["decision_time"], eligible_registry=request["registry_entries"],
                evidence=[{k:x[k] for k in ("evidence_id","news_id","revision_id","field","text","available_at")}
                          for x in row["evidence"]])


@contextmanager
def locked(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    lock = folder/".lock"
    with lock.open("xb"):
        pass
    try:
        yield
    finally:
        lock.unlink()


def record(repo: Path, plan: Plan, folder: Path, session_id: str, action: str, *, now: datetime,
           auth_path: Path | None = None, phase: str | None = None, reason: str | None = None,
           confirm_start: bool = False) -> dict:
    folder = storage(repo, folder)
    verify(repo, plan, folder, now=now)
    stage = stage_for(plan, session_id)
    session = read_session(repo, plan, folder, session_id, now=now)
    require(not (folder/session_id/"eligibility.json").exists(), "attested_session_immutable")
    if action == "start":
        require(confirm_start and auth_path is not None and session["state"] == "unfilled", "explicit_real_start_required")
        auth_ref = ref_for(repo, auth_path)
        authorization(repo, plan, session_id, auth_ref, now=now)
        require(phase == PHASES[stage][0], "start_in_reading_phase")
        require(all(read_session(repo, plan, folder, sid, now=now)["state"] in {"unfilled", "stopped"}
                    for sid in [s.session_id for s in plan.sessions]+[plan.administration_id]), "other_session_active")
        next_kind = "active"
    else:
        require(session["state"] in {"active", "pause"} and now > session["last"].at, "session_not_active")
        auth_ref = session["last"].authorization
        require((action in {"phase", "pause"} and session["state"] == "active")
                or (action == "resume" and session["state"] == "pause") or action == "stop", "invalid_transition")
        next_kind = "pause" if action == "pause" else "stopped" if action == "stop" else "active"
    require((next_kind == "active" and phase in PHASES[stage] and reason is None)
            or (next_kind == "pause" and phase is None and reason in PAUSES)
            or (next_kind == "stopped" and phase is None and reason is None), "invalid_phase")
    sequence = 0 if session["state"] == "unfilled" else session["last"].sequence+1
    event = Event(version="news-prospective-timing-event-v1", kind=plan.kind,
        plan_fingerprint=fingerprint(plan),session_id=session_id,sequence=sequence,previous=session["tip"],
        action=action,at=now,next_kind=next_kind,phase=phase,pause_reason=reason,authorization=auth_ref)
    # Validate the factual dependency before any write, including a new start.
    if stage == "contractual" and action == "start":
        slot = next(s for s in plan.sessions if s.session_id == session_id)
        parent_id = next(s.session_id for s in plan.sessions if s.case_id == slot.case_id and s.stage == "factual")
        parent = read_session(repo, plan, folder, parent_id, now=now)
        auth = authorization(repo, plan, session_id, auth_ref, now=now)
        require(parent["state"] == "stopped" and parent["complete_phases"] and auth.factual_tip == parent["tip"]
                and auth.factual_content_ready and auth.factual_source is not None and not auth.first_reading
                and now > parent["last"].at, "factual_gate_missing")
        require(read_ref(repo,auth.factual_source).get("case_id") == slot.case_id, "factual_source_case_mismatch")
    with locked(folder):
        _verify(repo,plan,folder,now=now,owns_lock=True)
        current = read_session(repo,plan,folder,session_id,now=now)
        require(current["tip"] == session["tip"], "concurrent_update")
        if action == "start":
            require(all(read_session(repo,plan,folder,sid,now=now)["state"] in {"unfilled","stopped"}
                        for sid in [s.session_id for s in plan.sessions]+[plan.administration_id]), "other_session_active")
        # A competing writer cannot reuse the sequence. No overwrite or automatic retry.
        directory = folder/session_id
        directory.mkdir(exist_ok=True)
        with (directory/f"{sequence:04d}.event.json").open("xb") as stream:
            stream.write(encoded(event.model_dump(mode="json")))
    return verify(repo, plan, folder, now=now)


def attest(repo: Path, plan: Plan, folder: Path, decision: Path, *, now: datetime) -> dict:
    folder = storage(repo,folder)
    verify(repo,plan,folder,now=now)
    value = Attestation.model_validate_json(decision.read_text(encoding="utf-8"))
    session = read_session(repo,plan,folder,value.session_id,now=now)
    validate_eligibility(repo,plan,value.session_id,value,session,now=now)
    with locked(folder):
        _verify(repo,plan,folder,now=now,owns_lock=True)
        with (folder/value.session_id/"eligibility.json").open("xb") as stream:
            stream.write(encoded(value.model_dump(mode="json")))
    return verify(repo,plan,folder,now=now)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--records",type=Path,required=True)
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("validate")
    p=sub.add_parser("material");p.add_argument("--session",required=True)
    p=sub.add_parser("clock");p.add_argument("action",choices=["start","phase","pause","resume","stop"])
    p.add_argument("--session",required=True);p.add_argument("--authorization",type=Path)
    p.add_argument("--phase");p.add_argument("--reason",choices=sorted(PAUSES));p.add_argument("--confirm-start",action="store_true")
    p=sub.add_parser("attest");p.add_argument("--decision",type=Path,required=True)
    args=parser.parse_args()
    try:
        repo=Path(__file__).resolve().parents[2]
        plan=load_plan(repo,args.plan)
        require(plan.kind == "prepared_real_calibration", "synthetic_plan_not_for_real_cli")
        now=datetime.now(timezone.utc)
        if args.command=="validate":result=verify(repo,plan,args.records,now=now)
        elif args.command=="material":result=material(repo,plan,args.records,args.session,now=now)
        elif args.command=="attest":result=attest(repo,plan,args.records,args.decision,now=now)
        else:result=record(repo,plan,args.records,args.session,args.action,now=now,auth_path=args.authorization,
                           phase=args.phase,reason=args.reason,confirm_start=args.confirm_start)
        print(json.dumps(result));return 0
    except Exception:
        print(json.dumps(dict(status="blocked",error="prospective_timing_validation_failed",provider_calls=0,inferences=0)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
