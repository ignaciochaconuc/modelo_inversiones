"""Offline preparation/validation instruments, never an interpreter or adjudicator."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
from itertools import permutations
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = "evaluation/phase4c2_development_pilot_v1"
SOURCE = "evaluation/phase4c2_development_corpus_v1"
SOURCE_MANIFEST_SHA256 = "a661f3c9f2b3e12d152c78b56b98e7a6f7673a6ed675d1d84fa9849dfec59b3c"
VERSION = "news-development-pilot-packets-v1"
SEED = "development-pilot-order-20261019-v1"
DIMENSIONS = ("events", "event_stage", "evidence", "identity", "participation", "role",
    "relationship", "ticker_link", "quantities", "dates", "negation", "impact", "material_omissions")
Dimension = Literal["events", "event_stage", "evidence", "identity", "participation", "role",
    "relationship", "ticker_link", "quantities", "dates", "negation", "impact", "material_omissions"]
PHASES = ("reading", "factual_annotation", "citation_check", "contract_review", "discrepancies", "adjudication", "administration")
Phase = Literal["reading", "factual_annotation", "citation_check", "contract_review", "discrepancies", "adjudication", "administration"]
State = Literal["unfilled", "in_progress", "completed"]
Digest = str


def fp(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, allow_inf_nan=False)


class Citation(Model):
    evidence_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    field: Literal["headline", "summary"]
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    quote: str = Field(min_length=1, repr=False)


class Fact(Model):
    fact_id: str = Field(pattern=r"^F[0-9]{3}$")
    dimension: Dimension
    meaning: str = Field(min_length=1, repr=False)
    certainty: Literal["conclusive", "uncertain", "indeterminate"]
    material: bool | None = Field(strict=True)
    citations: tuple[Citation, ...] = Field(min_length=1)


class Assessment(Model):
    status: Literal["recorded", "insufficient", "indeterminate", "not_applicable"] | None
    fact_ids: tuple[str, ...]
    note: str | None = Field(repr=False)


class Factual(Model):
    schema_version: Literal["news-pilot-factual-form-v1"]
    case_id: str
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: State
    facts: tuple[Fact, ...]
    dimension_assessments: dict[Dimension, Assessment]
    must_not_omit: tuple[str, ...]


class Mapping(Model):
    fact_id: str
    mode: Literal["structured", "faithful_partial_only", "not_representable", "indeterminate"]
    rationale: str = Field(min_length=1, repr=False)


class Contract(Model):
    schema_version: Literal["news-pilot-contract-form-v1"]
    case_id: str
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    contract_version: Literal["news-economic-validation-v3"]
    status: State
    factual_record_sha256: str | None = Field(pattern=r"^[a-f0-9]{64}$")
    mappings: tuple[Mapping, ...]
    allowed_outcomes: tuple[Literal["interpreted", "abstained", "indeterminate"], ...]
    rationale: str | None = Field(repr=False)


class Interval(Model):
    kind: Literal["active", "pause"]
    phase: Phase | None
    pause_reason: Literal["break", "interruption", "queue", "other"] | None
    started_at: datetime
    completed_at: datetime


class Timing(Model):
    schema_version: Literal["news-pilot-timing-provenance-v1"]
    case_id: str
    packet_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: State
    review_id: str | None
    reviewer_id: str | None
    reviewer_name: str | None
    review_kind: Literal["human_owner", "human_reviewer", "ai_assisted"] | None
    independence: Literal["not_claimed", "not_independent", "reviewer_declared_independent"] | None
    independence_basis: str | None = Field(repr=False)
    execution_mode: Literal["manual_no_api"] | None
    model_label: str | None
    model_snapshot: None
    api_parameters: None
    api_tokens: None
    timestamp_source: Literal["owner_declared", "manual_clock", "platform_export", "mixed"] | None
    timestamp_basis: str | None = Field(repr=False)
    started_at: datetime | None
    completed_at: datetime | None
    factual_closed_at: datetime | None
    active_seconds: float | None = Field(ge=0)
    pause_seconds: float | None = Field(ge=0)
    phase_seconds: dict[Phase, float | None]
    intervals: tuple[Interval, ...]
    discrepancy_status: Literal["no_disagreement", "disagreement", "unresolved", "not_applicable"] | None
    adjudication_status: Literal["not_performed", "performed", "deferred"] | None
    adjudicates_review_ids: tuple[str, ...]


def load_sources(repo: Path) -> tuple[dict, dict, dict, dict]:
    manifest_path = repo/SOURCE/"manifest.json"
    if sha(manifest_path) != SOURCE_MANIFEST_SHA256:
        raise ValueError("source_manifest_pin_mismatch")
    for name, digest in read(manifest_path)["sha256"].items():
        if sha(repo/name) != digest:
            raise ValueError("source_dependency_mismatch")
    plan = read(repo/SOURCE/"pilot-plan.json")
    ids = plan["selected_case_ids"]
    if len(ids) != 6 or len(set(ids)) != 6:
        raise ValueError("six_unique_planned_cases_required")
    corpus = {p["case_id"]: p for p in read(repo/SOURCE/"corpus.json")["cases"]}
    private = {p["case_id"]: p for p in read(repo/SOURCE/"private-design.json")["cases"]}
    if not set(ids) <= set(corpus) & set(private):
        raise ValueError("planned_case_missing")
    instrument = read(repo/"evaluation/phase4c2_semantic_review_workshop_v1/instrument.json")
    return plan, corpus, private, instrument


def blind_order(ids: list[str], private: dict) -> list[str]:
    """Deterministic hash priority and first valid permutation; two intervening cases."""
    ranked = sorted(ids, key=lambda i: fp([SEED, i]))
    for order in permutations(ranked):
        if all(private[a]["family_id"] != private[b]["family_id"]
               for i, a in enumerate(order) for j, b in enumerate(order) if 0 < j-i < 3):
            return list(order)
    raise ValueError("separated_order_unavailable")


def templates(packet: dict) -> dict:
    binding = dict(case_id=packet["case_id"], packet_fingerprint=packet["packet_fingerprint"], status="unfilled")
    factual = dict(schema_version="news-pilot-factual-form-v1", **binding, facts=[], must_not_omit=[],
        dimension_assessments={d: dict(status=None, fact_ids=[], note=None) for d in DIMENSIONS})
    contract = dict(schema_version="news-pilot-contract-form-v1", **binding,
        contract_version="news-economic-validation-v3", factual_record_sha256=None, mappings=[],
        allowed_outcomes=[], rationale=None)
    timing = dict(schema_version="news-pilot-timing-provenance-v1", **binding,
        **{k: None for k in ("review_id", "reviewer_id", "reviewer_name", "review_kind", "independence",
            "independence_basis", "execution_mode", "model_label", "model_snapshot", "api_parameters", "api_tokens",
            "timestamp_source", "timestamp_basis", "started_at", "completed_at", "factual_closed_at", "active_seconds",
            "pause_seconds", "discrepancy_status", "adjudication_status")},
        phase_seconds={p: None for p in PHASES}, intervals=[], adjudicates_review_ids=[])
    return dict(factual=factual, contract=contract, timing=timing)


def prepare(repo: Path) -> dict[str, dict | str]:
    """Return artifacts in memory only; caller must explicitly persist new files."""
    plan, corpus, private, instrument = load_sources(repo)
    order = blind_order(plan["selected_case_ids"], private)
    output = {"review-order.json": dict(version=VERSION, case_ids=order)}
    instructions = dict(instrument=instrument["version"],
        task="Anote los hechos del texto, sin decidir cómo encajarlos en un contrato técnico.",
        principles=["Distinga hechos explícitos, inferencias, incertidumbre y ausencia de información.",
            "No convierta identidad o ticker en prueba de participación, exposición o retorno.",
            "Registre las condiciones materiales y el alcance de las negaciones sin recortarlos.",
            "Use citas literales del campo indicado y offsets Unicode half-open [start,end); no bytes ni UTF-16.",
            "Mantenga indeterminaciones; no fuerce consenso ni complete datos ausentes.",
            "Cierre la anotación factual antes de abrir el formulario contractual separado."],
        dimensions=instrument["dimensions"])
    for case_id in order:
        source = corpus[case_id]
        news = source["request"]["news"]
        packet = dict(version=VERSION, case_id=case_id, fictional=True,
            source_packet_fingerprint=source["packet_fingerprint"], primary_revision_id=source["primary_revision_id"],
            headline=news["headline"], summary=news["summary"], evidence=source["evidence"],
            virtual_clock={**{key: news[key] for key in ("published_at", "first_seen_at", "available_at", "ingested_at")},
                "decision_time": source["request"]["decision_time"]},
            eligible_registry=source["request"]["registry_entries"], factual_instructions=instructions)
        packet["packet_fingerprint"] = fp(packet)
        output[f"packets/{case_id}.json"] = packet
        output[f"packets/{case_id}.md"] = render(packet)
        for kind, form in templates(packet).items():
            output[f"forms/{kind}/{case_id}.json"] = form
    for kind, cls in (("factual", Factual), ("contract", Contract), ("timing", Timing)):
        output[f"schemas/{kind}.schema.json"] = cls.model_json_schema()
    return output


def render(packet: dict) -> str:
    """Human-readable packet generated from the same exact source fields."""
    lines = [f"# {packet['case_id']}", "", "Texto íntegramente ficticio. Revisión factual manual; sin respuestas esperadas.",
        "", "## Headline", "", packet["headline"], "", "## Summary", "", packet["summary"], "", "## Evidencias"]
    for e in packet["evidence"]:
        lines += ["", f"- Campo: {e['field']}; evidence_id: {e['evidence_id']}",
            f"- Revisión: {e['revision_id']}; available_at: {e['available_at']}"]
    lines += ["", "Los textos de cada evidencia son exactamente los campos completos anteriores.",
        "", "## Reloj virtual y cutoff", "", "```json", json.dumps(packet["virtual_clock"], indent=2), "```",
        "", "## Registry elegible ficticio", "", "```json", json.dumps(packet["eligible_registry"], indent=2, ensure_ascii=False), "```",
        "", "## Instrucciones factuales", "", packet["factual_instructions"]["task"]]
    lines += ["", *["- "+p for p in packet["factual_instructions"]["principles"]]]
    lines += ["", *["- "+d["id"]+": "+d["instruction"] for d in packet["factual_instructions"]["dimensions"]],
        "", f"Packet fingerprint: {packet['packet_fingerprint']}", ""]
    return "\n".join(lines)


def aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value


def validate_factual(form: Factual, packet: dict) -> None:
    if set(form.dimension_assessments) != set(DIMENSIONS):
        raise ValueError("complete_dimension_inventory_required")
    facts = {f.fact_id: f for f in form.facts}
    if len(facts) != len(form.facts):
        raise ValueError("duplicate_fact_id")
    evidence = {e["evidence_id"]: e for e in packet["evidence"]}
    for fact in form.facts:
        if not fact.meaning.strip():
            raise ValueError("empty_fact_meaning")
        for citation in fact.citations:
            e = evidence.get(citation.evidence_id)
            if e is None or e["field"] != citation.field or e["revision_id"] != packet["primary_revision_id"]:
                raise ValueError("wrong_evidence_binding")
            if not (0 <= citation.start < citation.end <= len(e["text"])) or e["text"][citation.start:citation.end] != citation.quote:
                raise ValueError("exact_unicode_citation_mismatch")
    for dimension, assessment in form.dimension_assessments.items():
        if len(set(assessment.fact_ids)) != len(assessment.fact_ids) or any(
                fid not in facts or facts[fid].dimension != dimension for fid in assessment.fact_ids):
            raise ValueError("wrong_fact_binding")
        if assessment.status == "recorded" and not assessment.fact_ids:
            raise ValueError("recorded_dimension_needs_fact")
        if assessment.status is None and (assessment.fact_ids or assessment.note is not None):
            raise ValueError("unassessed_dimension_contains_judgment")
        if assessment.status == "not_applicable" and assessment.fact_ids:
            raise ValueError("not_applicable_contains_fact")
        if assessment.status in {"insufficient", "indeterminate", "not_applicable"} and not (assessment.note or "").strip():
            raise ValueError("uncertainty_or_exclusion_needs_note")
    referenced = {fid for a in form.dimension_assessments.values() for fid in a.fact_ids}
    if referenced != set(facts) or len(set(form.must_not_omit)) != len(form.must_not_omit) or not set(form.must_not_omit) <= set(facts):
        raise ValueError("unlinked_fact_or_material_obligation")
    if form.status == "completed" and any(a.status is None for a in form.dimension_assessments.values()):
        raise ValueError("unassessed_completed_factual")
    if form.status == "unfilled" and (form.facts or form.must_not_omit or any(a.status is not None for a in form.dimension_assessments.values())):
        raise ValueError("unfilled_factual_has_annotations")


def validate_contract(form: Contract, factual: Factual, factual_sha: str) -> None:
    if form.factual_record_sha256 is not None and form.factual_record_sha256 != factual_sha:
        raise ValueError("factual_record_hash_mismatch")
    ids = [m.fact_id for m in form.mappings]
    if len(set(ids)) != len(ids) or not set(ids) <= {f.fact_id for f in factual.facts}:
        raise ValueError("contract_fact_inventory_mismatch")
    if len(set(form.allowed_outcomes)) != len(form.allowed_outcomes) or any(not m.rationale.strip() for m in form.mappings):
        raise ValueError("invalid_contract_annotations")
    has_annotations = bool(form.mappings or form.allowed_outcomes or form.rationale is not None or form.factual_record_sha256 is not None)
    if has_annotations and factual.status != "completed":
        raise ValueError("factual_must_close_before_contract")
    if form.status == "completed" and (factual.status != "completed" or form.factual_record_sha256 != factual_sha
            or set(ids) != {f.fact_id for f in factual.facts} or not form.allowed_outcomes or not (form.rationale or "").strip()):
        raise ValueError("incomplete_contract_review")
    if form.status == "unfilled" and has_annotations:
        raise ValueError("unfilled_contract_has_annotations")


def validate_timing(form: Timing, *, now: datetime) -> None:
    if set(form.phase_seconds) != set(PHASES):
        raise ValueError("complete_phase_inventory_required")
    for date in (form.started_at, form.completed_at, form.factual_closed_at):
        if date is not None:
            aware(date)
            if date > now:
                raise ValueError("future_review_timestamp")
    if any(v is not None and v < 0 for v in form.phase_seconds.values()):
        raise ValueError("negative_phase_seconds")
    if form.status == "unfilled":
        expected = templates(dict(case_id=form.case_id, packet_fingerprint=form.packet_fingerprint))["timing"]
        if form.model_dump(mode="json") != expected:
            raise ValueError("unfilled_timing_has_measurements")
        return
    required = (form.review_id, form.reviewer_id, form.reviewer_name, form.review_kind, form.independence,
                form.execution_mode, form.timestamp_source, form.timestamp_basis, form.started_at)
    if not all(required) or any(isinstance(v, str) and not v.strip() for v in required):
        raise ValueError("missing_declared_provenance")
    if form.review_kind == "human_owner" and form.independence == "reviewer_declared_independent":
        raise ValueError("owner_not_independent")
    if form.independence == "reviewer_declared_independent" and not (form.independence_basis or "").strip():
        raise ValueError("independence_basis_required")
    if form.review_kind != "ai_assisted" and form.model_label is not None:
        raise ValueError("human_has_model_provenance")
    totals = {p: 0.0 for p in PHASES}
    pause = 0.0
    last = form.started_at
    for interval in form.intervals:
        start, end = aware(interval.started_at), aware(interval.completed_at)
        if start != last or end <= start or end > now or (form.completed_at is not None and end > form.completed_at):
            raise ValueError("overlap_gap_or_invalid_interval")
        seconds = (end-start).total_seconds()
        if interval.kind == "active":
            if interval.phase is None or interval.pause_reason is not None:
                raise ValueError("invalid_active_interval")
            totals[interval.phase] += seconds
        else:
            if interval.phase is not None or interval.pause_reason is None:
                raise ValueError("invalid_pause_interval")
            pause += seconds
        last = end
    if form.completed_at is not None:
        if form.completed_at <= form.started_at or last != form.completed_at:
            raise ValueError("incomplete_timeline")
        if now >= form.completed_at+timedelta(days=90):
            raise ValueError("timing_metadata_expired")
    for actual, reported in [(sum(totals.values()), form.active_seconds), (pause, form.pause_seconds),
                             *[(totals[p], form.phase_seconds[p]) for p in PHASES]]:
        if reported is not None and abs(actual-reported) > 1e-6:
            raise ValueError("reported_duration_mismatch")
    if form.adjudication_status == "performed":
        ids = form.adjudicates_review_ids
        if (form.discrepancy_status not in {"disagreement", "unresolved"} or totals["adjudication"] <= 0
                or len(ids) < 2 or len(set(ids)) != len(ids) or form.review_id in ids):
            raise ValueError("adjudication_provenance_required")
    elif totals["adjudication"] or form.adjudicates_review_ids:
        raise ValueError("undeclared_adjudication")
    if form.factual_closed_at is not None:
        if not form.started_at <= form.factual_closed_at <= last:
            raise ValueError("invalid_factual_closure")
        if any(i.phase in {"factual_annotation", "citation_check"} and i.completed_at > form.factual_closed_at for i in form.intervals):
            raise ValueError("factual_edits_after_closure")
    if any(i.phase == "contract_review" and (form.factual_closed_at is None or i.started_at < form.factual_closed_at) for i in form.intervals):
        raise ValueError("contract_review_before_factual_closure")
    if form.status == "completed" and (form.completed_at is None or form.active_seconds is None or form.pause_seconds is None
            or any(v is None for v in form.phase_seconds.values()) or form.discrepancy_status is None
            or form.adjudication_status is None or not form.intervals):
        raise ValueError("incomplete_completed_timing")


def validate_forms(forms: Path, packets: dict[str, dict], *, require_completed: bool, now: datetime) -> dict:
    aware(now)
    if len(packets) != 6:
        raise ValueError("exact_six_case_form_inventory_required")
    expected = {f"{kind}/{cid}.json" for kind in ("factual", "contract", "timing") for cid in packets}
    actual = {p.relative_to(forms).as_posix() for p in forms.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("exact_six_case_form_inventory_required")
    complete = 0
    review_ids = set()
    for cid, packet in packets.items():
        f = Factual.model_validate(read(forms/"factual"/(cid+".json")))
        c = Contract.model_validate(read(forms/"contract"/(cid+".json")))
        t = Timing.model_validate(read(forms/"timing"/(cid+".json")))
        for form in (f, c, t):
            if form.case_id != cid or form.packet_fingerprint != packet["packet_fingerprint"]:
                raise ValueError("form_packet_binding_mismatch")
        validate_factual(f, packet)
        validate_contract(c, f, sha(forms/"factual"/(cid+".json")))
        validate_timing(t, now=now)
        if t.review_id is not None:
            if t.review_id in review_ids:
                raise ValueError("duplicate_review_id")
            review_ids.add(t.review_id)
        if f.status != "unfilled" and t.status == "unfilled":
            raise ValueError("annotation_without_provenance")
        if c.status != "unfilled" and (t.factual_closed_at is None or not any(i.phase == "contract_review" for i in t.intervals)):
            raise ValueError("contract_without_separate_timing")
        done = all(form.status == "completed" for form in (f, c, t))
        if require_completed and not done:
            raise ValueError("review_not_completed")
        complete += done
    return dict(cases=6, completed_cases=complete, semantic_truth="not_assessed", judgments_created=0)


def verify_packages(repo: Path) -> dict[str, dict]:
    folder = repo/ROOT
    manifest = read(folder/"manifest.json")
    if manifest["version"] != VERSION:
        raise ValueError("wrong_manifest_version")
    generated = prepare(repo)
    required = {f"{ROOT}/{name}" for name in generated}
    if not required <= set(manifest["sha256"]):
        raise ValueError("incomplete_manifest_inventory")
    for name, digest in manifest["sha256"].items():
        if sha(repo/name) != digest:
            raise ValueError("package_hash_mismatch")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != "manifest.json"}
    if actual != set(generated):
        raise ValueError("unexpected_package_file")
    for name, value in generated.items():
        stored = (folder/name).read_text(encoding="utf-8") if isinstance(value, str) else read(folder/name)
        if stored != value:
            raise ValueError("package_reconstruction_mismatch")
    return {v["case_id"]: v for k, v in generated.items() if k.startswith("packets/") and k.endswith(".json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-packages", action="store_true")
    parser.add_argument("--forms", type=Path, help="Read-only validation of a separate operator working copy")
    parser.add_argument("--allow-incomplete", action="store_true", help="Structure check, not acceptance as completed review")
    args = parser.parse_args()
    if not args.verify_packages and args.forms is None:
        parser.error("choose --verify-packages or --forms")
    try:
        repo = Path(__file__).resolve().parents[2]
        packets = verify_packages(repo)
        summary = validate_forms(args.forms or repo/ROOT/"forms", packets,
            require_completed=bool(args.forms) and not args.allow_incomplete, now=datetime.now(timezone.utc))
        print(json.dumps(dict(status="offline_validation_passed", **summary, provider_calls=0, predictions=0)))
    except Exception:
        print(json.dumps(dict(status="blocked", error="pilot_material_or_form_validation_failed", provider_calls=0)))
        raise SystemExit(2)
