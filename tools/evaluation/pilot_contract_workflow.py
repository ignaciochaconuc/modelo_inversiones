"""Opt-in offline operator workflow; never judges facts or starts a clock implicitly."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Literal
import uuid


def _clock():
    name = "pilot_workflow_clock"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("pilot_contract_clock.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


c = _clock()
m = c.m
WORKFLOW_ERRORS = frozenset({
    "new_separate_workspace_required", "source_review_still_active", "case_not_available",
    "draft_not_editable", "all_facts_contractual_review_required", "stale_contractual_source_binding",
    "completed_session_required", "content_approval_already_recorded",
    "explicit_closure_authorization_required", "authorized_fingerprint_mismatch",
    "contract_owner_decision_required", "contract_owner_decision_binding_mismatch",
    "separate_opening_authorization_required", "workflow_receipt_mismatch",
    "source_uncertainty_not_preserved", "incomplete_workflow_operation",
    "clock_history_mismatch",
    "retry_not_eligible", "retry_reason_not_observed", "retry_lineage_mismatch",
    "retry_predecessor_changed", "retry_cycle", "retry_time_overlap",
})


class Preparation(m.Model):
    record_version: Literal["news-pilot-contract-workflow-v1"]
    case_id: str
    review_id: str
    source_manifest: m.Ref
    form_path: str
    session_path: str
    materials: tuple[m.Ref, ...]


RetryReason = Literal["contract_mapping_not_timed", "owner_review_not_timed"]


class RetryPreparation(Preparation):
    record_version: Literal["news-pilot-contract-workflow-v2"]
    retry_lineage: m.Ref


class RetryLineage(m.Model):
    record_version: Literal["news-pilot-contract-retry-lineage-v1"]
    case_id: str
    predecessor_review_id: str
    review_id: str
    reason: RetryReason
    predecessor_workflow: m.Ref
    predecessor_manifest: m.Ref
    predecessor_form: m.Ref
    predecessor_session: m.Ref
    predecessor_inventory: tuple[m.Ref, ...]
    derived_proposal: m.Ref
    independent_evaluation: Literal[False]
    proposal_initially_approved: Literal[False]
    prior_times_transferred: Literal[False]


class Submission(m.Model):
    """Transport envelope only; judgments and outcomes use the adapter's types."""
    case_id: str
    review_id: str
    factual: m.Ref
    technical_reference: m.Ref
    mappings: tuple[m.ContractMapping, ...]
    allowed_outcomes: m.ContractForm.model_fields["allowed_outcomes"].annotation
    rationale: str


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ref(repo: Path, path: Path) -> m.Ref:
    return c._ref(path, repo, path.read_bytes())


def _folder(repo: Path, folder: Path) -> Path:
    folder = folder.resolve()
    m.d.require(folder.is_relative_to(repo.resolve()) and folder != repo.resolve(), "workspace_outside_repository")
    return folder


def _load(repo: Path, folder: Path, *, now: datetime, _ancestry: frozenset[Path] = frozenset()):
    folder = _folder(repo, folder)
    m.d.require(folder not in _ancestry, "retry_cycle")
    raw = _json(folder/"workflow.json")
    model = RetryPreparation if raw.get("record_version") == "news-pilot-contract-workflow-v2" else Preparation
    prep = model.model_validate(raw)
    m.d.require(not (folder/"retry-lineage-v1.json").exists() or isinstance(prep,RetryPreparation), "retry_lineage_mismatch")
    m.d.bound_path(repo, prep.source_manifest)
    for ref in prep.materials:
        m.d.bound_path(repo, ref)
    _audit(repo, folder)
    result = m.verify(repo, folder, now=now)
    manifest = m.Manifest.model_validate(_json(folder/"manifest.json"))
    refs = [r for r in manifest.forms if r.path == prep.form_path]
    m.d.require(len(refs) == 1, "reserved_form_not_selected")
    form = m.ContractForm.model_validate(m.d.read_ref(repo, refs[0]))
    m.d.require(form.case_id == prep.case_id and form.session.path == prep.session_path,
        "reservation_source_mismatch")
    for path in (prep.form_path, prep.session_path):
        m.d.require(m.d.path_for(repo, path).is_relative_to(folder), "reserved_file_outside_workspace")
    m.d.require(all(r["case_id"] == prep.case_id or r["status"] in {"unfilled", "completed"}
        for r in result["cases"]), "other_cases_must_remain_unfilled")
    if (folder/"opening/reservation.json").exists():
        reservation, _, _, _, _ = c._load(repo, folder, now=now, allow_completed_other_cases=True)
        m.d.require(reservation.review_id == prep.review_id, "active_session_not_reserved")
        if form.status != "unfilled":
            c._event_chain(repo, _json(folder/"clock/state.json"), reservation, form.session)
            _audit_clock(repo, folder)
    else:
        m.d.require(form.status == "unfilled", "separate_opening_authorization_required")
    if isinstance(prep, RetryPreparation):
        _validate_retry(repo, folder, prep, form, now=now, ancestry=_ancestry | {folder})
    return prep, form, manifest, result


def _inventory(repo: Path, folder: Path) -> tuple[m.Ref, ...]:
    return tuple(_ref(repo, path) for path in sorted(folder.rglob("*"))
                 if path.is_file() and "__pycache__" not in path.parts)


def _retry_source(repo: Path, source: Path, case_id: str, reason: RetryReason, *, now: datetime,
                  ancestry: frozenset[Path] = frozenset()):
    """Read-only eligibility check, including the existing reader's 90-day TTL."""
    prep, form, manifest, _ = _load(repo, source, now=now, _ancestry=ancestry)
    m.d.require(prep.case_id == case_id and form.status == "in_progress"
        and form.owner_decision is None and not (source/"content-approval.json").exists(), "retry_not_eligible")
    session = m.ContractSession.model_validate(m.d.read_ref(repo, form.session))
    m.d.require(session.status == "completed" and session.review_id == prep.review_id, "retry_not_eligible")
    tip = m.d.read_ref(repo,m.Ref.model_validate(_json(source/"clock/state.json")["last_event"]))
    m.d.require(tip["action"] == "stop" and tip["next_kind"] == "stopped", "retry_not_eligible")
    m.d.require(reason in {"contract_mapping_not_timed", "owner_review_not_timed"}, "retry_not_eligible")
    phase = reason.removesuffix("_not_timed")
    m.d.require(not any(i.kind == "active" and i.phase == phase for i in session.intervals), "retry_reason_not_observed")
    m.d.require(len(form.mappings) == len(form.factual_snapshot["facts"])
        and {entry.fact_id for entry in form.mappings} == {f["fact_id"] for f in form.factual_snapshot["facts"]}
        and bool(form.allowed_outcomes) and bool(form.rationale), "all_facts_contractual_review_required")
    return prep, form, manifest, session


def _validate_retry(repo: Path, folder: Path, prep: RetryPreparation, form, *, now: datetime,
                    ancestry: frozenset[Path]) -> None:
    m.d.require(m.d.path_for(repo,prep.retry_lineage.path).is_relative_to(folder), "retry_lineage_mismatch")
    lineage = RetryLineage.model_validate(m.d.read_ref(repo, prep.retry_lineage))
    source = m.d.path_for(repo, lineage.predecessor_workflow.path).parent
    old_prep, old_form, _, old_session = _retry_source(repo, source, lineage.case_id, lineage.reason,
        now=now, ancestry=ancestry)
    m.d.require(lineage.case_id == prep.case_id and lineage.review_id == prep.review_id
        and lineage.predecessor_review_id == old_prep.review_id and prep.review_id != old_prep.review_id
        and lineage.predecessor_workflow == _ref(repo,source/"workflow.json")
        and lineage.predecessor_manifest == prep.source_manifest == _ref(repo,source/"manifest.json")
        and lineage.predecessor_form == _ref(repo,m.d.path_for(repo,old_prep.form_path))
        and lineage.predecessor_session == old_form.session
        and form.factual == old_form.factual and form.closure_decision == old_form.closure_decision
        and form.closed_disposition == old_form.closed_disposition
        and form.technical_reference == old_form.technical_reference, "retry_lineage_mismatch")
    m.d.require(lineage.predecessor_inventory == _inventory(repo,source), "retry_predecessor_changed")
    m.d.require(m.d.path_for(repo,lineage.derived_proposal.path).is_relative_to(folder), "retry_lineage_mismatch")
    proposal = Submission.model_validate(m.d.read_ref(repo,lineage.derived_proposal))
    m.d.require(proposal.case_id == prep.case_id and proposal.review_id == prep.review_id
        and proposal.factual == old_form.factual and proposal.technical_reference == old_form.technical_reference
        and proposal.model_dump(mode="json")["mappings"] == old_form.model_dump(mode="json")["mappings"]
        and proposal.allowed_outcomes == old_form.allowed_outcomes and proposal.rationale == old_form.rationale,
        "retry_lineage_mismatch")
    session = m.ContractSession.model_validate(m.d.read_ref(repo,form.session))
    m.d.require(form.session.path != old_form.session.path, "retry_lineage_mismatch")
    if session.started_at is not None:
        m.d.require(session.started_at >= old_session.completed_at, "retry_time_overlap")


def _audit(repo: Path, folder: Path) -> None:
    approval_receipts = 0
    for archive in (folder/"workflow-history").glob("*"):
        m.d.require(archive.is_dir() and (archive/"receipt.json").exists()
            and (archive/"applied.json").exists(), "incomplete_workflow_operation")
    for receipt_path in (folder/"workflow-history").glob("*/receipt.json"):
        receipt = _json(receipt_path)
        applied_path = receipt_path.with_name("applied.json")
        m.d.require(applied_path.exists(), "incomplete_workflow_operation")
        m.d.require(_json(applied_path) == dict(receipt_sha256=m.d.digest(receipt_path), applied=True),
            "workflow_receipt_mismatch")
        for row in receipt["before"]:
            m.d.bound_path(repo, m.Ref.model_validate(row["backup"]))
        for row in receipt["after"]:
            snapshot = m.Ref.model_validate(row["snapshot"])
            m.d.bound_path(repo, snapshot)
            if row["path"] == (folder/"content-approval.json").relative_to(repo).as_posix():
                m.d.require(receipt["action"] == "content_approved_not_closed" and receipt["source"] is not None,
                    "workflow_receipt_mismatch")
                approval_receipts += 1
                m.d.require(m.d.digest(folder/"content-approval.json") == snapshot.sha256, "workflow_receipt_mismatch")
        if receipt["source"]:
            m.d.bound_path(repo, m.Ref.model_validate(receipt["source"]))
    m.d.require(not list((folder/"workflow-history").glob("*/*.pending")), "incomplete_workflow_operation")
    m.d.require(approval_receipts == int((folder/"content-approval.json").exists()), "workflow_receipt_mismatch")


def _audit_clock(repo: Path, folder: Path) -> None:
    """Audit actual clock history only after the adapter has enforced session TTL."""
    ref = m.Ref.model_validate(_json(folder/"clock/state.json")["last_event"])
    successor, seen = None, set()
    while ref is not None:
        event = m.d.read_ref(repo, ref)
        seen.add(ref.path)
        path = m.d.path_for(repo, ref.path)
        m.d.require(path.parent == folder/"clock", "clock_history_mismatch")
        archive = folder/"clock/history"/path.name.removesuffix(".event.json")
        before = event["session_sha256_before"]
        m.d.require(m.d.digest(archive/"session.json") == before
            and _json(archive/"form.json")["session"]["sha256"] == before, "clock_history_mismatch")
        old_manifest = m.Manifest.model_validate(_json(archive/"manifest.json"))
        m.d.require(any(r.sha256 == m.d.digest(archive/"form.json") for r in old_manifest.forms), "clock_history_mismatch")
        m.d.require(successor is None or successor["session_sha256_before"] == event["session_sha256_after"],
            "clock_history_mismatch")
        successor = event
        ref = m.Ref.model_validate(event["previous_event"]) if event["previous_event"] else None
    actual = {p.relative_to(repo).as_posix() for p in (folder/"clock").glob("*.event.json")}
    m.d.require(seen == actual and not list((folder/"clock").glob("*.pending")), "clock_history_mismatch")


def prepare(repo: Path, source: Path, folder: Path, case_id: str, *, now: datetime) -> dict:
    """Prepare a new independent workspace, not an opening or semantic annotation."""
    return _prepare(repo, source, folder, case_id, now=now)


def prepare_retry(repo: Path, source: Path, folder: Path, case_id: str, *, reason: RetryReason, now: datetime) -> dict:
    """Explicit new attempt only; never resets or writes the completed predecessor clock."""
    return _prepare(repo, source, folder, case_id, retry_reason=reason, now=now)


def _prepare(repo: Path, source: Path, folder: Path, case_id: str, *, now: datetime,
             retry_reason: RetryReason | None = None) -> dict:
    source, folder = _folder(repo, source), _folder(repo, folder)
    m.d.require(not folder.exists() and not folder.is_relative_to(source)
        and not source.is_relative_to(folder), "new_separate_workspace_required")
    result = m.verify(repo, source, now=now)
    predecessor = None
    if retry_reason is None:
        m.d.require(all(r["status"] in {"unfilled", "completed"} for r in result["cases"]), "source_review_still_active")
    else:
        predecessor = _retry_source(repo, source, case_id, retry_reason, now=now)
    manifest = m.Manifest.model_validate(_json(source/"manifest.json"))
    forms = [(ref, m.ContractForm.model_validate(m.d.read_ref(repo, ref))) for ref in manifest.forms]
    selected = [(ref, form) for ref, form in forms if form.case_id == case_id]
    expected_status = "in_progress" if predecessor else "unfilled"
    m.d.require(len(selected) == 1 and selected[0][1].status == expected_status, "case_not_available")
    old_ref, form = selected[0]
    review_id = "contract-"+case_id+"-"+uuid.uuid4().hex
    m.d.require(all(r["review_id"] != review_id for r in result["cases"]), "reserved_review_id_already_used")
    packet = m.d.legacy_module().verify_packages(repo)[case_id]
    session = m.d.read_ref(repo, form.session)
    factual = m.d.read_ref(repo, form.factual)
    reference = m.d.read_ref(repo, form.technical_reference)
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    if predecessor:
        session = m.blank_session(disposition)
    inventory = _inventory(repo,source) if predecessor else None
    # Resolve all inputs before the first write. Completed source cases are never copied or edited.
    sources = {name: m.d.bound_path(repo, m.Ref(path=name, sha256=sha)).read_bytes()
               for name, sha in reference["files"].items()}
    session_path = folder/"sessions"/(case_id+".json")
    form_path = folder/"forms"/(case_id+".json")
    _write(session_path, c._bytes(session))
    raw = form.model_dump(mode="json")
    raw["session"] = _ref(repo, session_path).model_dump()
    if predecessor:
        raw = m.blank_form(form.closed_disposition, disposition, factual, form.technical_reference,
                           _ref(repo, session_path))
    _write(form_path, c._bytes(raw))
    data = manifest.model_dump(mode="json")
    data["forms"] = [_ref(repo, form_path).model_dump() if r == old_ref else r.model_dump() for r in manifest.forms]
    _write(folder/"manifest.json", c._bytes(data))
    materials = {"NEWS-PACKET.json": c._bytes(packet), "FACTUAL-APPROVED.json": c._bytes(factual),
                 "TECHNICAL-REFERENCE.json": c._bytes(reference)}
    materials.update({"reference-source/"+name: payload for name, payload in sources.items()})
    # This is an incomplete operator template, not a valid or issued authorization.
    opening = dict(schema_version="news-pilot-contract-opening-authorization-v1", case_id=case_id,
        review_id=review_id, disposition_id=disposition.disposition_id, factual_sha256=form.factual.sha256,
        closure_sha256=form.closure_decision.sha256, explicitly_authorized=None,
        authorized_by=disposition.content.provenance.approver_identity,
        decision_source=None, authorized_at=None, source_message_id=None,
        inference_authorized=False)
    annotation = dict(case_id=case_id, review_id=review_id, factual=form.factual.model_dump(),
        technical_reference=form.technical_reference.model_dump(),
        mappings=[dict(fact_id=f["fact_id"], mode=None, rationale=None, limits_acknowledged=None)
                  for f in factual["facts"]], allowed_outcomes=[], rationale=None)
    materials["SUBMISSION-SCHEMA.json"] = c._bytes(Submission.model_json_schema())
    instructions = (
        "# Revision contractual manual asistida\n\nTexto ficticio; no ejecutar un modelo/API. "
        "Revisar cada fact_id, todas las dimensiones, evidencias e incertidumbres. "
        "No reducir a must_not_omit. Separar hechos aprobados de representabilidad tecnica; "
        "no inventar tickers, etapas, fechas o impacto. Entregar todos los mappings juntos "
        "usando ANNOTATION-TEMPLATE.json y SUBMISSION-SCHEMA.json. No aprobar ni cerrar. "
        "Indeterminate del instrumento no es un estado ejecutable del payload v3.\n\n")
    sections = [("Noticia original", packet), ("Factual completo aprobado", factual),
                ("Referencia tecnica", reference), ("Plantilla de entrega", annotation)]
    if predecessor:
        derived = Submission(case_id=case_id, review_id=review_id, factual=form.factual,
            technical_reference=form.technical_reference, mappings=form.mappings,
            allowed_outcomes=form.allowed_outcomes, rationale=form.rationale)
        materials["DERIVED-PROPOSAL-v1.json"] = c._bytes(derived.model_dump(mode="json"))
        sections.append(("Propuesta derivada del intento anterior: no aprobada ni independiente", derived.model_dump(mode="json")))
        instructions += ("Este es un reintento por " + retry_reason + ". La propuesta se copio del intento anterior; "
                         "no es una evaluacion nueva independiente ni una aprobacion. Medir una comprobacion humana "
                         "real de todos los mappings y la revision del propietario; no transferir tiempos.\n\n")
    text = instructions+"\n".join("## "+title+"\n\n```json\n"+json.dumps(value, ensure_ascii=False, indent=2)+"\n```\n"
                                     for title, value in sections)
    for name, payload in sources.items():
        text += "\n## Contrato y reglas: "+name+"\n\n```python\n"+payload.decode("utf-8")+"\n```\n"
    materials["CHATGPT-PACKET.md"] = text.encode("utf-8")
    for name, payload in materials.items():
        _write(folder/"materials"/name, payload)
    _write(folder/"OPENING-TEMPLATE.json", c._bytes(opening))
    _write(folder/"ANNOTATION-TEMPLATE.json", c._bytes(annotation))
    metadata = dict(record_version="news-pilot-contract-workflow-v1", case_id=case_id,
        review_id=review_id, source_manifest=_ref(repo, source/"manifest.json"),
        form_path=form_path.relative_to(repo).as_posix(), session_path=session_path.relative_to(repo).as_posix(),
        materials=tuple(_ref(repo, folder/"materials"/name) for name in materials))
    if predecessor:
        _write(folder/"DERIVED-PROPOSAL-v1.json", c._bytes(derived.model_dump(mode="json")))
        approval = dict(schema_version="news-pilot-contract-owner-decision-v1", case_id=case_id,
            review_id=review_id, review_fingerprint=None, factual_sha256=form.factual.sha256,
            explicitly_approved=None, decided_by=disposition.content.provenance.approver_identity,
            decision_source=None, decided_at=None, independent_human_review=False, adjudication_claimed=False)
        _write(folder/"CONTENT-APPROVAL-TEMPLATE.json", c._bytes(approval))
        old_prep, old_form, _, _ = predecessor
        lineage = RetryLineage(record_version="news-pilot-contract-retry-lineage-v1", case_id=case_id,
            predecessor_review_id=old_prep.review_id, review_id=review_id, reason=retry_reason,
            predecessor_workflow=_ref(repo,source/"workflow.json"),
            predecessor_manifest=_ref(repo,source/"manifest.json"),
            predecessor_form=_ref(repo,m.d.path_for(repo,old_prep.form_path)), predecessor_session=old_form.session,
            predecessor_inventory=inventory, derived_proposal=_ref(repo,folder/"DERIVED-PROPOSAL-v1.json"),
            independent_evaluation=False, proposal_initially_approved=False, prior_times_transferred=False)
        lineage_path = folder/"retry-lineage-v1.json"
        _write(lineage_path,c._bytes(lineage.model_dump(mode="json")))
        metadata.update(record_version="news-pilot-contract-workflow-v2", retry_lineage=_ref(repo,lineage_path))
        prep = RetryPreparation(**metadata)
    else:
        prep = Preparation(**metadata)
    _write(folder/"workflow.json", c._bytes(prep.model_dump(mode="json")))
    return validate(repo, folder, now=now)


def _publish(repo: Path, folder: Path, *, action: str, writes: dict[Path, bytes],
             source: m.Ref | None = None, authorization: dict | None = None) -> None:
    """Keep before/after records and an immutable receipt; no automatic recovery/retries."""
    token = uuid.uuid4().hex
    archive = folder/"workflow-history"/token
    m.d.require(all(p.resolve().is_relative_to(folder.resolve()) for p in writes), "reserved_file_outside_workspace")
    before, after = [], []
    for index, (path, payload) in enumerate(writes.items()):
        if path.exists():
            backup = archive/"before"/(str(index)+".json")
            _write(backup, path.read_bytes())
            before.append(dict(path=path.relative_to(repo).as_posix(), backup=_ref(repo, backup).model_dump()))
        staged = archive/"after"/(str(index)+".json")
        _write(staged, payload)
        after.append(dict(path=path.relative_to(repo).as_posix(), snapshot=_ref(repo, staged).model_dump()))
    receipt = dict(record_version="news-pilot-contract-operation-v1", action=action,
        source=source.model_dump() if source else None, authorization=authorization,
        before=before, after=after, status="prepared_for_application")
    _write(archive/"receipt.json", c._bytes(receipt))
    for path, payload in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = archive/(uuid.uuid4().hex+".pending")
        _write(temp, payload)
        os.replace(temp, path)
    _write(archive/"applied.json", c._bytes(dict(receipt_sha256=m.d.digest(archive/"receipt.json"), applied=True)))


def _update_form(repo: Path, folder: Path, prep, form, manifest, *, action: str, source=None, authorization=None):
    path = m.d.path_for(repo, prep.form_path)
    payload = c._bytes(form.model_dump(mode="json"))
    new_ref = c._ref(path, repo, payload)
    data = manifest.model_dump(mode="json")
    data["forms"] = [new_ref.model_dump() if r.path == prep.form_path else r.model_dump() for r in manifest.forms]
    _publish(repo, folder, action=action, writes={path:payload, folder/"manifest.json":c._bytes(data)},
             source=source, authorization=authorization)


def open_review(repo: Path, folder: Path, authorization: Path, *, now: datetime) -> dict:
    prep, form, _, _ = _load(repo, folder, now=now)
    m.d.require(form.status == "unfilled" and not (folder/"opening").exists(), "clock_already_started")
    source = _ref(repo, authorization)
    auth = m.OpeningAuthorization.model_validate(m.d.read_ref(repo, source))
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    m.d.require(auth.case_id == form.case_id and auth.review_id == prep.review_id
        and auth.disposition_id == disposition.disposition_id and auth.factual_sha256 == form.factual.sha256
        and auth.closure_sha256 == form.closure_decision.sha256
        and auth.authorized_by == disposition.content.provenance.approver_identity, "reserved_authorization_mismatch")
    m.d.check_date(auth.authorized_at, now)
    auth_path = folder/"opening/authorization.json"
    reservation = c.Reservation(record_version="news-pilot-contract-opening-reservation-v1",case_id=form.case_id,
        review_id=prep.review_id, opening_authorization=c._ref(auth_path, repo, c._bytes(auth.model_dump(mode="json"))),
        form_path=prep.form_path, session_path=prep.session_path)
    _publish(repo, folder, action="opening_authorized_not_started", source=source,
        writes={auth_path:c._bytes(auth.model_dump(mode="json")),
                folder/"opening/reservation.json":c._bytes(reservation.model_dump(mode="json"))})
    return validate(repo, folder, now=now)


def clock(repo: Path, folder: Path, action: str, *, now: datetime, **kwargs) -> dict:
    _load(repo, folder, now=now)
    if action == "status":
        return c.status(repo, folder, now=now, allow_completed_other_cases=True)
    return c.record(repo, folder, action, now=now, allow_completed_other_cases=True, **kwargs)


def apply_mappings(repo: Path, folder: Path, annotation: Path, *, now: datetime) -> dict:
    prep, form, manifest, _ = _load(repo, folder, now=now)
    m.d.require(form.status == "in_progress" and not (folder/"content-approval.json").exists(), "draft_not_editable")
    source = _ref(repo, annotation)
    proposal = Submission.model_validate(m.d.read_ref(repo, source))
    m.d.require(proposal.case_id == prep.case_id and proposal.review_id == prep.review_id
        and proposal.factual == form.factual and proposal.technical_reference == form.technical_reference,
        "stale_contractual_source_binding")
    m.d.require(len(proposal.mappings) == len(form.factual_snapshot["facts"])
        and {r.fact_id for r in proposal.mappings} == {f["fact_id"] for f in form.factual_snapshot["facts"]}
        and bool(proposal.allowed_outcomes), "all_facts_contractual_review_required")
    raw = form.model_dump(mode="json")
    raw.update(mappings=[v.model_dump(mode="json") for v in proposal.mappings],
        allowed_outcomes=list(proposal.allowed_outcomes), rationale=proposal.rationale)
    updated = m.ContractForm.model_validate(raw)
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    packet = m.d.legacy_module().verify_packages(repo)[prep.case_id]
    m.validate_form(repo, updated, form.closed_disposition, disposition, packet, now=now)
    _update_form(repo, folder, prep, updated, manifest, action="draft_mappings_imported_not_approved", source=source)
    return validate(repo, folder, now=now)


def approval_plan(repo: Path, folder: Path, *, now: datetime) -> dict:
    """Read-only fingerprint and unsigned template; never issue an owner decision."""
    prep, form, _, _ = _load(repo, folder, now=now)
    session = m.ContractSession.model_validate(m.d.read_ref(repo, form.session))
    m.d.require(form.status == "in_progress" and session.status == "completed", "completed_session_required")
    m.d.require(len(form.mappings) == len(form.factual_snapshot["facts"])
        and bool(form.allowed_outcomes) and bool(form.rationale), "all_facts_contractual_review_required")
    for phase in ("contract_mapping", "owner_review"):
        m.d.require(any(i.kind == "active" and i.phase == phase for i in session.intervals), phase+"_not_timed")
    fp = m.review_fingerprint(form.model_copy(update={"status":"completed"}))
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    return dict(case_id=prep.case_id, review_id=prep.review_id, review_fingerprint=fp,
        fingerprint_target_status="completed", target_status_applied=False,
        allowed_outcomes=list(form.allowed_outcomes), session_sha256=form.session.sha256,
        current_form=_ref(repo,m.d.path_for(repo,prep.form_path)).model_dump(),
        mappings=[entry.model_dump(mode="json") for entry in form.mappings], rationale=form.rationale,
        dimension_assessments=form.factual_snapshot["dimension_assessments"],
        decision_template=dict(schema_version="news-pilot-contract-owner-decision-v1", case_id=prep.case_id,
            review_id=prep.review_id, review_fingerprint=fp, factual_sha256=form.factual.sha256,
            explicitly_approved=None, decided_by=disposition.content.provenance.approver_identity,
            decision_source=None, decided_at=None,
            independent_human_review=False, adjudication_claimed=False), provider_calls=0)


def approve_content(repo: Path, folder: Path, decision: Path, *, now: datetime) -> dict:
    plan = approval_plan(repo, folder, now=now)
    prep, form, _, _ = _load(repo, folder, now=now)
    path = folder/"content-approval.json"
    m.d.require(not path.exists(), "content_approval_already_recorded")
    source = _ref(repo, decision)
    owner = m.OwnerDecision.model_validate(m.d.read_ref(repo, source))
    m.d.require(owner.review_fingerprint == plan["review_fingerprint"], "contract_owner_decision_binding_mismatch")
    # Validate the actual external decision with the unmodified completed-form validator.
    candidate = form.model_copy(update={"status":"completed", "owner_decision":source})
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    packet = m.d.legacy_module().verify_packages(repo)[prep.case_id]
    m.validate_form(repo, candidate, form.closed_disposition, disposition, packet, now=now)
    _publish(repo, folder, action="content_approved_not_closed", source=source,
             writes={path:c._bytes(owner.model_dump(mode="json"))})
    return validate(repo, folder, now=now)


def finalize(repo: Path, folder: Path, *, fingerprint: str, authorized_by: str, closure_source: str,
             authorize_final_closure: bool, now: datetime) -> dict:
    plan = approval_plan(repo, folder, now=now)
    prep, form, manifest, _ = _load(repo, folder, now=now)
    disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
    m.d.require(authorize_final_closure is True and bool(closure_source.strip())
        and authorized_by == disposition.content.provenance.approver_identity, "explicit_closure_authorization_required")
    m.d.require(fingerprint == plan["review_fingerprint"], "authorized_fingerprint_mismatch")
    path = folder/"content-approval.json"
    m.d.require(path.exists(), "contract_owner_decision_required")
    candidate = form.model_copy(update={"status":"completed", "owner_decision":_ref(repo,path)})
    packet = m.d.legacy_module().verify_packages(repo)[prep.case_id]
    m.validate_form(repo, candidate, form.closed_disposition, disposition, packet, now=now)
    m.d.require(m.review_fingerprint(candidate) == fingerprint, "authorized_fingerprint_mismatch")
    authorization = dict(explicitly_authorized=True, authorized_by=authorized_by,
        decision_source=closure_source, review_fingerprint=fingerprint,
        authorized_at=None, source_message_id=None)
    _update_form(repo, folder, prep, candidate, manifest, action="final_closure_authorized_and_applied",
                 source=_ref(repo,path), authorization=authorization)
    return validate(repo, folder, now=now)


def validate(repo: Path, folder: Path, *, now: datetime) -> dict:
    prep, form, _, result = _load(repo, folder, now=now)
    if (folder/"content-approval.json").exists() and form.status != "completed":
        candidate = form.model_copy(update={"status":"completed", "owner_decision":_ref(repo,folder/"content-approval.json")})
        disposition = m.d.Disposition.model_validate(m.d.read_ref(repo, form.closed_disposition))
        m.validate_form(repo,candidate,form.closed_disposition,disposition,
            m.d.legacy_module().verify_packages(repo)[prep.case_id],now=now)
    return dict(status="offline_workflow_verified", case_id=prep.case_id, review_id=prep.review_id,
        form_status=form.status, content_approval_recorded=(folder/"content-approval.json").exists(),
        adapter=result, provider_calls=0, inferences=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--source",required=True,type=Path); p.add_argument("--case",required=True)
    p = sub.add_parser("prepare-retry")
    p.add_argument("--source",required=True,type=Path); p.add_argument("--case",required=True)
    p.add_argument("--reason",required=True,choices=["contract_mapping_not_timed","owner_review_not_timed"])
    p = sub.add_parser("open"); p.add_argument("--authorization",required=True,type=Path)
    p = sub.add_parser("clock")
    p.add_argument("event",choices=["status","start","phase","pause","resume","stop"])
    p.add_argument("--phase",choices=m.PHASES); p.add_argument("--reason",choices=["ai_wait","break","interruption","other"])
    for name in ("reviewer-id","reviewer-name","context","model-label"):
        p.add_argument("--"+name)
    p = sub.add_parser("apply"); p.add_argument("--annotation",required=True,type=Path)
    sub.add_parser("approval-plan")
    p = sub.add_parser("approve-content"); p.add_argument("--decision",required=True,type=Path)
    p = sub.add_parser("finalize")
    p.add_argument("--fingerprint",required=True); p.add_argument("--authorized-by",required=True)
    p.add_argument("--closure-source",required=True); p.add_argument("--authorize-final-closure",action="store_true")
    sub.add_parser("validate")
    args = parser.parse_args()
    try:
        repo=Path(__file__).resolve().parents[2]; now=datetime.now(timezone.utc); folder=_folder(repo,args.workspace)
        if args.action == "prepare":
            result=prepare(repo,args.source,folder,args.case,now=now)
        elif args.action == "prepare-retry":
            result=prepare_retry(repo,args.source,folder,args.case,reason=args.reason,now=now)
        elif args.action == "open":
            result=open_review(repo,folder,args.authorization.resolve(),now=now)
        elif args.action == "clock":
            result=clock(repo,folder,args.event,now=now,**{k:getattr(args,k) for k in
                ("phase","reason","reviewer_id","reviewer_name","context","model_label")})
        elif args.action == "apply":
            result=apply_mappings(repo,folder,args.annotation.resolve(),now=now)
        elif args.action == "approval-plan":
            result=approval_plan(repo,folder,now=now)
        elif args.action == "approve-content":
            result=approve_content(repo,folder,args.decision.resolve(),now=now)
        elif args.action == "finalize":
            result=finalize(repo,folder,fingerprint=args.fingerprint,authorized_by=args.authorized_by,
                closure_source=args.closure_source,authorize_final_closure=args.authorize_final_closure,now=now)
        else:
            result=validate(repo,folder,now=now)
        print(json.dumps(result,ensure_ascii=False)); return 0
    except Exception as exc:
        code = exc.args[0] if type(exc) is ValueError and len(exc.args) == 1 and isinstance(exc.args[0], str) else None
        print(json.dumps(dict(status="blocked",error="contract_workflow_validation_failed",
            error_code=code if code in WORKFLOW_ERRORS else c.error_code(exc),provider_calls=0))); return 2


if __name__ == "__main__":
    raise SystemExit(main())
