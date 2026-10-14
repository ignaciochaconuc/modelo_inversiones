"""Evaluation instruments only. Never import references into model inputs."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import yaml

from investment_system.agents.news_interpretation.runtime_schemas import EconomicRuntimeSettings
from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest
from investment_system.agents.news_interpretation.service import prepare_invocation, reservation_bound
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_evaluation import synthetic_record
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry

VERSION = "nacho-attribution-evaluation-runner-v1"
FREEZE_SHA256 = "1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39"
FREEZE_PATH = "data/cache/news_attribution_review/chatgpt-v1/references-frozen.json"
SOURCE_ROOT = "evaluation/phase4c2_attribution_v1/prepared/reviewer"
OUTPUT_ROOT = "data/cache/news_attribution_evaluation/nacho-v1"


def review_module():
    spec = importlib.util.spec_from_file_location("chatgpt_review", Path(__file__).with_name("prepare_chatgpt_review.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone_required")
    return result.astimezone(timezone.utc)


def verified_sources(repo: Path) -> tuple[dict, dict, dict]:
    """Control plane only: discard annotations before constructing requests."""
    path = repo / FREEZE_PATH
    if sha(path) != FREEZE_SHA256:
        raise ValueError("reference_freeze_sha256_mismatch")
    seal = json.loads(path.read_bytes())
    review = review_module()
    prepared = repo / "evaluation/phase4c2_chatgpt_review_v1/prepared"
    review.verify(repo, prepared)
    if (seal["review_kind"] != review.ROLE or seal["independent_human_ground_truth"] is not False
            or seal["reference_fingerprint"] != review.fp(seal["references"])):
        raise ValueError("reference_freeze_integrity_failed")
    records = seal["references"]["records"]
    if [r["block_id"] for r in records] != [f"B{i:02d}" for i in range(1, 9)]:
        raise ValueError("exactly_eight_reference_blocks_required")
    cases = []
    for record in records:
        cases.extend(review.verify_import_record(repo, prepared, record, record["block_id"])["cases"])
    if cases != seal["references"]["cases"]:
        raise ValueError("reference_reconstruction_failed")
    evidence = json.loads((repo / SOURCE_ROOT / "blind_synthetic_evidence.json").read_bytes())
    identity = json.loads((repo / SOURCE_ROOT / "identity_lookup.synthetic.json").read_bytes())
    original = evidence["cases"]
    if (evidence.get("fictional") is not True or identity.get("fictional") is not True
            or len(original) != 32 or len({c["case_id"] for c in original}) != 32
            or len(cases) != 32 or len({c["case_id"] for c in cases}) != 32
            or {c["case_id"]: c["evidence_fingerprint"] for c in original}
            != {c["case_id"]: c["evidence_fingerprint"] for c in cases}):
        raise ValueError("original_synthetic_cases_required")
    # Return no events, units, labels, rationales or ChatGPT response text.
    metadata = {"freeze_sha256": FREEZE_SHA256, "reference_fingerprint": seal["reference_fingerprint"],
                "frozen_at": seal["frozen_at"]}
    return evidence, identity, metadata


def build_requests(evidence: dict, identity: dict) -> list[tuple[dict, NewsInterpretationRequest]]:
    """Pure synthetic adapter; no registry inference, publication dates or gold."""
    cutoff = utc(identity["virtual_decision_time"])
    entries = []
    for row in identity["entries"]:
        known = utc(row["known_at"])
        effective = datetime.fromisoformat(row["effective_from"]).date()
        if known > cutoff or effective > cutoff.date():
            continue
        if not row["ticker"].startswith("FIC-") or not row["security_id"].startswith("fictional-"):
            raise ValueError("nonfictional_security_forbidden")
        # One corporate entity may have multiple securities; preserve ambiguity.
        entry = EntityRegistryEntry(entity_id="synthetic-" + fingerprint(row["corporate_name"])[:16],
            corporate_name=row["corporate_name"], security_id=row["security_id"], ticker=row["ticker"],
            aliases=(), effective_from=effective, known_at=known,
            evidence="Neutral fictional identity entry; " + fingerprint(row))
        entries.append(entry)
    requests = []
    for case in evidence["cases"]:
        if set(case) != {"case_id", "evidence_fingerprint", "evidence"}:
            raise ValueError("annotation_fields_forbidden_in_input")
        fields = {}
        for item in case["evidence"]:
            if (set(item) != {"evidence_id", "field", "text"} or item["field"] not in {"headline", "summary"}
                    or item["field"] in fields or item["evidence_id"] != case["case_id"] + ":" + item["field"]):
                raise ValueError("invalid_original_evidence_field")
            fields[item["field"]] = item["text"]
        if set(fields) != {"headline", "summary"} or fingerprint(fields) != case["evidence_fingerprint"]:
            raise ValueError("synthetic_text_fingerprint_mismatch")
        # Mandatory observation/ingestion fields represent the provided fixture
        # clock, NOT historical article publication or actual generation time.
        news = synthetic_record(case["case_id"], fields["headline"], "", summary=fields["summary"],
                                available_at=cutoff, published_at=None)
        request = NewsInterpretationRequest(news=news, decision_time=cutoff, registry_entries=tuple(entries))
        binding = {"case_id": case["case_id"], "evidence_fingerprint": case["evidence_fingerprint"],
                   "request_id": request.request_id, "revision_id": request.revision_id,
                   "request_evidence_fingerprint": request.evidence_fingerprint,
                   "evidence_id_map": {case["case_id"] + ":" + e.field: e.evidence_id for e in request.evidence}}
        requests.append((binding, request))
    return requests


def preflight(repo: Path, config: Path, budget: float, *, now: datetime | None = None) -> tuple[dict, EconomicRuntimeSettings, list]:
    """No credentials, provider transport, storage, ledger or output writes."""
    now = now or datetime.now(timezone.utc)
    evidence, identity, metadata = verified_sources(repo)
    settings = EconomicRuntimeSettings.model_validate(yaml.safe_load(config.read_text(encoding="utf-8")))
    if (not Decimal(str(budget)).is_finite() or budget <= 0 or budget > settings.run_budget_usd
            or settings.max_attempts != 1 or settings.retry_invalid_response or settings.retry_delay_seconds != 0):
        raise ValueError("evaluation_budget_or_attempt_policy_invalid")
    settings = EconomicRuntimeSettings.model_validate({**settings.model_dump(mode="json"), "run_budget_usd": budget,
                                                       "request_budget_usd": min(settings.request_budget_usd, budget)})
    if not (settings.pricing.valid_from <= now < settings.pricing.valid_until
            and settings.adapter.capabilities_verified_at <= now and utc(metadata["frozen_at"]) < now):
        raise ValueError("expired_or_future_evaluation_attestation")
    requests = build_requests(evidence, identity)
    bounds = []
    for binding, request in requests:
        if request.inputs_available_at > now:
            raise ValueError("future_synthetic_inputs")
        _, wire, key = prepare_invocation(request, settings)
        tokens, maximum = reservation_bound(wire, settings)
        if maximum > settings.request_budget_usd:
            raise ValueError("per_request_budget_insufficient")
        bounds.append({**binding, "wire_fingerprint": fingerprint(wire), "cache_key": key,
                       "input_token_upper_bound": tokens, "maximum_reserved_usd": maximum})
    total = sum((Decimal(str(b["maximum_reserved_usd"])) for b in bounds), Decimal(0))
    if total > Decimal(str(budget)):
        raise ValueError("total_conservative_budget_insufficient")
    code_root = Path(__file__).resolve().parents[2]
    code_hashes = {p.relative_to(code_root).as_posix(): sha(p) for p in (code_root / "src").rglob("*.py")}
    plan = {"version": VERSION, **metadata, "production_code_fingerprint": fingerprint(code_hashes),
            "runner_code_sha256": sha(Path(__file__).resolve()),
            "cli_code_sha256": sha(code_root / "scripts/run_phase4c2_attribution_evaluation.py"),
            "temporal_mapping_policy": "provided-virtual-fixture-clock-v1",
            "source_evidence_sha256": sha(repo / SOURCE_ROOT / "blind_synthetic_evidence.json"),
            "source_identity_sha256": sha(repo / SOURCE_ROOT / "identity_lookup.synthetic.json"),
            "config_sha256": sha(config), "settings_fingerprint": fingerprint(settings.model_dump(mode="json")),
            "model": settings.adapter.model, "model_output_version": settings.model_output_version,
            "prompt_version": settings.prompt_version, "case_count": len(bounds), "max_attempts_per_case": 1,
            "request_budget_usd": settings.request_budget_usd, "run_budget_usd": budget,
            "maximum_reserved_usd": float(total), "input_token_upper_bound_total": sum(b["input_token_upper_bound"] for b in bounds),
            "output_token_cap_total": len(bounds) * settings.adapter.max_output_tokens, "cases": bounds}
    plan["plan_fingerprint"] = fingerprint(plan)
    return plan, settings, requests


def validate_authorization(auth: dict, plan: dict, run_id: str, now: datetime) -> None:
    fields = {"version", "approved", "authorized_by", "authorized_at", "expires_at", "plan_fingerprint",
              "freeze_sha256", "run_id", "max_provider_calls", "budget_usd"}
    if (set(auth) != fields or auth["version"] != "nacho-evaluation-authorization-v1" or auth["approved"] is not True
            or not isinstance(auth["authorized_by"], str) or not auth["authorized_by"].strip()
            or auth["plan_fingerprint"] != plan["plan_fingerprint"] or auth["freeze_sha256"] != FREEZE_SHA256
            or auth["run_id"] != run_id or type(auth["max_provider_calls"]) is not int or auth["max_provider_calls"] != 32
            or type(auth["budget_usd"]) not in {int, float} or auth["budget_usd"] != plan["run_budget_usd"]
            or not utc(plan["frozen_at"]) < utc(auth["authorized_at"]) <= now < utc(auth["expires_at"])
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run_id)):
        raise ValueError("explicit_plan_bound_authorization_required")


def export_delivery(binding: dict, delivery) -> dict:
    """Literal native v3 values; no semantic recoding using gold annotations."""
    record = delivery.record
    row = {**binding, "outcome": "not_run", "attempt_started_at": None, "record_id": None,
           "output_fingerprint": None, "units": [], "error_code": delivery.error_code,
           "additional_attempts": delivery.additional_attempts, "retrieval_mode": delivery.retrieval_mode}
    if record is None:
        return row
    outcome = record.outcome if record.outcome in {"interpreted", "abstained", "invalid_response"} else (
        "rejected" if record.error_code in {"provider_refusal", "model_identity_mismatch", "effective_parameters_mismatch",
        "secret_echo_rejected", "invalid_usage_telemetry", "usage_outside_verified_price_band", "observed_cost_exceeds_reservation"}
        else "transport_error")
    row.update(outcome=outcome, native_outcome=record.outcome, attempt_started_at=record.started_at.isoformat(), record_id=record.record_id,
        output_fingerprint=fingerprint(record.model_dump(mode="json")), received_at=record.received_at.isoformat(),
        persisted_at=record.persisted_at.isoformat(), expires_at=record.expires_at.isoformat(),
        usage=record.cost_record.model_dump(mode="json"), cache_write_tokens=record.cache_write_tokens,
        observed_usage_cost_usd=record.observed_usage_cost_usd, accounted_usd=record.accounted_usd,
        maximum_reserved_usd=record.maximum_reserved_usd,
        diagnostics=[d.model_dump(mode="json") for d in record.rejection_diagnostics])
    if record.interpretation is None:
        return row
    payload = record.interpretation.result.payload
    if payload is None:
        return row
    row["abstention_reasons"] = list(payload.abstention_reasons)
    row["economics"] = payload.economics.model_dump(mode="json")
    row["events"] = [e.model_dump(mode="json") for e in payload.events]
    if record.outcome != "interpreted":
        return row
    for ei, event in enumerate(payload.events):
        for ui, entity in enumerate(event.entities):
            row["units"].append({"unit_id": f"E{ei+1}-U{ui+1}", "event_id": event.event_key, "name": entity.name,
                "dimensions": {"corporate_identity": entity.identity.model_dump(mode="json"),
                    "participation": entity.attribution, "role": entity.participation_role,
                    "relationship": {"type": entity.relation_type, "related_entity": entity.related_entity, "state": entity.relation_state},
                    "ticker_link": entity.identity.ticker, "event_state": event.state,
                    "event_stage": event.stage, "impact_support": entity.potential_impact.model_dump(mode="json")},
                "confirmed_exposure": False, "operational": False})
    return row


def execute_cases(requests: list, service, root: Path, plan: dict, *, before_call=None) -> dict:
    """Authorized service only; no reference payload parameter exists here."""
    review = review_module()
    rows = []
    halted = False
    for binding, request in requests:
        if halted:
            row = {**binding, "outcome": "not_run", "attempt_started_at": None, "record_id": None,
                   "output_fingerprint": None, "units": [], "error_code": "previous_accounting_or_execution_halt"}
        else:
            # Fresh isolated run, exactly one configured attempt; no old smoke/cache.
            try:
                if before_call is not None:
                    before_call()
                delivery = service.interpret(request, force_new=True)
                row = export_delivery(binding, delivery)
                halted = bool(delivery.record is None or (delivery.record and
                    (delivery.record.observed_usage_cost_usd is None or delivery.record.error_code in {
                        "observed_cost_exceeds_reservation", "invalid_usage_telemetry", "usage_outside_verified_price_band"})))
            except Exception:
                # Durable ledger/attempts are left untouched. Do not fabricate a
                # replayable output if persistence or authorization failed.
                row = {**binding, "outcome": "not_run", "attempt_started_at": None, "record_id": None,
                       "output_fingerprint": None, "units": [], "error_code": "runner_failure_review_required",
                       "attempt_may_have_occurred": True}
                halted = True
        rows.append(row)
        review.write_json(root / "cases" / (binding["case_id"] + ".json"), row)
    export = {"version": VERSION, "plan_fingerprint": plan["plan_fingerprint"], "reference_freeze_sha256": FREEZE_SHA256,
              "dataset_role": "synthetic_exploratory_system_outputs", "operational": False, "cases": rows,
              "accounted_usd": service.budget.accounted(), "unknown_cost_attempts": service.tracker.unknown_cost_count()}
    review.write_json(root / "nacho-outputs.json", export)
    return export
