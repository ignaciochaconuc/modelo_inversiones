"""Versioned offline workshop. No provider, production interpreter or credential loading.

Only simulated development inputs are accepted. This is not the 96-case runner
or a live-response importer. Response bodies live in memory, never in exports.
"""
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = "news-semantic-review-instrument-v1"
DIMENSIONS = ("events", "event_stage", "evidence", "identity", "participation", "role",
              "relationship", "ticker_link", "quantities", "dates", "negation", "impact", "material_omissions")
Dimension = Literal["events", "event_stage", "evidence", "identity", "participation", "role",
    "relationship", "ticker_link", "quantities", "dates", "negation", "impact", "material_omissions"]


def fp(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Source(Model):
    case_id: str = Field(pattern=r"^W-[0-9]{2}$")
    family_id: str = Field(pattern=r"^WF-[0-9]{2}$")
    headline: str
    summary: str
    neutral_identity: str = ""
    available_at: datetime
    decision_time: datetime
    kind: Literal["simulated_development"] = "simulated_development"

    @model_validator(mode="after")
    def pit(self):
        if (self.available_at.tzinfo is None or self.decision_time.tzinfo is None
                or self.available_at > self.decision_time):
            raise ValueError("invalid_workshop_pit")
        return self


class Citation(Model):
    field: Literal["headline", "summary", "neutral_identity"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str


class Fact(Model):
    fact_id: str = Field(pattern=r"^F[0-9]{2}$")
    dimension: Dimension
    meaning: str
    certainty: Literal["conclusive", "indeterminate"]
    material: bool
    citation: Citation


class Annotation(Model):
    case_id: str
    source_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer_id: str = Field(pattern=r"^sim-[a-z0-9-]+$")
    provenance_kind: Literal["simulated_development"] = "simulated_development"
    facts: tuple[Fact, ...]


class Representation(Model):
    """Separate from factual meaning; never edits the reference fact to fit regex."""
    fact_id: str
    mode: Literal["structured", "faithful_partial_only", "not_representable", "indeterminate"]


class ContractLayer(Model):
    allowed_outcomes: tuple[Literal["interpreted", "abstained"], ...]
    mappings: tuple[Representation, ...]
    rationale: str


def write_once(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def freeze_references(sources, first, second, contracts, adjudications, destination: Path, *, at: datetime):
    """Freeze pre-output workshop sources and two simulated annotation streams."""
    if at.tzinfo is None or len({s.case_id for s in sources}) != len(sources):
        raise ValueError("invalid_reference_inventory")
    ids = {s.case_id for s in sources}
    if any(set(rows) != ids for rows in (first, second, contracts)) or not set(adjudications) <= ids:
        raise ValueError("reference_inventory_mismatch")
    records = []
    for source in sources:
        if source.decision_time > at:
            raise ValueError("future_reference_source")
        a, b = first[source.case_id], second[source.case_id]
        for annotation in (a, b, *([adjudications[source.case_id]] if source.case_id in adjudications else [])):
            if annotation.case_id != source.case_id or annotation.source_fingerprint != fp(source.model_dump(mode="json")):
                raise ValueError("reference_source_mismatch")
            if len({f.fact_id for f in annotation.facts}) != len(annotation.facts):
                raise ValueError("duplicate_reference_fact")
            for fact in annotation.facts:
                cite = fact.citation
                text = getattr(source, cite.field)
                if (cite.end > len(text) or cite.end-cite.start != len(cite.quote)
                        or cite.end <= cite.start or text[cite.start:cite.end] != cite.quote):
                    raise ValueError("invalid_reference_citation")
        if a.reviewer_id == b.reviewer_id:
            raise ValueError("distinct_annotation_streams_required")
        disagreement = a.facts != b.facts
        if disagreement:
            final = adjudications.get(source.case_id)
            if final is None or final.reviewer_id in {a.reviewer_id, b.reviewer_id}:
                raise ValueError("explicit_reference_adjudication_required")
        else:
            if source.case_id in adjudications:
                raise ValueError("unnecessary_reference_override")
            final = a
        layer = contracts[source.case_id]
        if (not layer.allowed_outcomes or len({m.fact_id for m in layer.mappings}) != len(layer.mappings)
                or {m.fact_id for m in layer.mappings} != {f.fact_id for f in final.facts}):
            raise ValueError("contract_layer_does_not_match_facts")
        records.append(dict(source=source.model_dump(mode="json"), first=a.model_dump(mode="json"),
            second=b.model_dump(mode="json"), disagreement=disagreement, final=final.model_dump(mode="json"),
            contract=layer.model_dump(mode="json")))
    body = dict(version=VERSION, kind="simulated_development_reference_freeze", frozen_at=at.isoformat(), records=records)
    seal = dict(body=body, fingerprint=fp(body))
    write_once(destination, seal)
    return seal, hashlib.sha256(destination.read_bytes()).hexdigest()


def load_freeze(path: Path, expected_sha256: str):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reference_freeze_hash_mismatch")
    seal = json.loads(raw)
    if (set(seal) != {"body", "fingerprint"} or fp(seal["body"]) != seal["fingerprint"]
            or seal["body"].get("version") != VERSION
            or seal["body"].get("kind") != "simulated_development_reference_freeze"):
        raise ValueError("invalid_reference_freeze")
    return seal


class MockResponse(Model):
    kind: Literal["simulated_development"] = "simulated_development"
    case_id: str
    arm: Literal["v3", "v4"]
    outcome: Literal["interpreted", "abstained", "rejected", "technical_error", "not_run"]
    body: str = Field(repr=False)
    persisted_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def ttl(self):
        if self.persisted_at.tzinfo is None or self.expires_at != self.persisted_at+timedelta(hours=24):
            raise ValueError("response_ttl_must_be_24_hours")
        return self


def anonymize(seal, responses, *, now: datetime, seed: int):
    """Ephemeral blind packets only; no file writer for response bodies exists."""
    references = {r["source"]["case_id"]: r for r in seal["body"]["records"]}
    expected = {(c, a) for c in references for a in ("v3", "v4")}
    if len(responses) != len(expected) or {(r.case_id, r.arm) for r in responses} != expected:
        raise ValueError("exact_paired_response_inventory_required")
    rng, packets, private = random.Random(seed), [], {}
    for case_id in references:
        pair = [r for r in responses if r.case_id == case_id]
        rng.shuffle(pair)
        for slot, response in enumerate(pair):
            if (not datetime.fromisoformat(seal["body"]["frozen_at"]) < response.persisted_at <= now < response.expires_at):
                raise ValueError("response_not_reviewable_or_pre_freeze")
            label = "B-"+fp([case_id, slot, rng.getrandbits(128)])[:16]
            private[label] = dict(case_id=case_id, arm=response.arm, response_fingerprint=fp(response.model_dump(mode="json")),
                                  expires_at=response.expires_at.isoformat(), persisted_at=response.persisted_at.isoformat())
            source = {k: v for k, v in references[case_id]["source"].items() if k != "family_id"}
            packets.append(dict(blind_id=label, source=source, outcome=response.outcome,
                                response_text=response.body, expires_at=response.expires_at.isoformat()))
    return packets, private


class Rating(Model):
    verdict: Literal["pass", "fail", "indeterminate", "not_applicable"]
    matched: int = Field(ge=0, strict=True)
    omitted: int = Field(ge=0, strict=True)
    unsupported: int = Field(ge=0, strict=True)


class Judgment(Model):
    version: Literal["news-semantic-review-instrument-v1"] = VERSION
    blind_id: str = Field(pattern=r"^B-[a-f0-9]{16}$")
    reviewer_id: str = Field(pattern=r"^sim-[a-z0-9-]+$")
    provenance_kind: Literal["simulated_development"] = "simulated_development"
    created_at: datetime
    expires_at: datetime
    dimensions: dict[Dimension, Rating]
    abstention: Literal["not_applicable", "justified", "unjustified", "indeterminate"]
    critical: tuple[Literal["false_completion", "false_identity", "false_participation", "lost_negation",
        "fabricated_evidence", "future_information", "operational_output"], ...] = ()

    @model_validator(mode="after")
    def sanitized(self):
        if (set(self.dimensions) != set(DIMENSIONS) or self.created_at.tzinfo is None
                or self.expires_at != self.created_at+timedelta(days=90)):
            raise ValueError("incomplete_or_invalid_review_metadata")
        for score in self.dimensions.values():
            if (score.verdict in {"pass", "not_applicable"} and (score.omitted or score.unsupported)):
                raise ValueError("passing_score_cannot_hide_errors")
        return self


def validate_judgment(judgment, private, reference, *, now):
    binding = private[judgment.blind_id]
    if reference["source"]["case_id"] != binding["case_id"]:
        raise ValueError("judgment_reference_case_mismatch")
    if not (datetime.fromisoformat(binding["persisted_at"]) <= judgment.created_at < datetime.fromisoformat(binding["expires_at"])
            and judgment.created_at <= now < judgment.expires_at):
        raise ValueError("review_outside_content_or_metadata_ttl")
    facts = reference["final"]["facts"]
    for dimension, score in judgment.dimensions.items():
        n = sum(f["dimension"] == dimension and f["certainty"] == "conclusive" for f in facts)
        ambiguous = any(f["dimension"] == dimension and f["certainty"] == "indeterminate" for f in facts)
        if score.matched+score.omitted > n or (n and score.verdict == "not_applicable"):
            raise ValueError("invalid_reference_denominator")
        if score.verdict == "not_applicable" and (score.matched or ambiguous):
            raise ValueError("cannot_hide_ambiguous_reference")
        if score.verdict == "pass" and (score.matched != n or ambiguous):
            raise ValueError("pass_requires_complete_conclusive_coverage")
    return judgment


def adjudicate(first: Judgment, second: Judgment, resolution: Judgment | None):
    if first.blind_id != second.blind_id or first.reviewer_id == second.reviewer_id:
        raise ValueError("distinct_blind_reviews_required")
    def content(j):
        return j.model_dump(mode="json", exclude={"reviewer_id", "created_at", "expires_at"})
    if content(first) == content(second):
        if resolution is not None:
            raise ValueError("cannot_override_agreement")
        return first, dict(disagreement=False, first=fp(first.model_dump(mode="json")), second=fp(second.model_dump(mode="json")))
    if resolution is None or resolution.blind_id != first.blind_id or resolution.reviewer_id in {first.reviewer_id, second.reviewer_id}:
        raise ValueError("explicit_blind_adjudication_required")
    return resolution, dict(disagreement=True, first=fp(first.model_dump(mode="json")),
        second=fp(second.model_dump(mode="json")), resolution=fp(resolution.model_dump(mode="json")))


def summarize(seal, packets, private, judgments, *, now):
    """Family-weighted F_case bounds; no automatic adoption decision for a workshop."""
    if (set(judgments) != set(private) or len(packets) != len(private)
            or {p["blind_id"] for p in packets} != set(private)):
        raise ValueError("incomplete_review_inventory")
    rows, metrics = [], {arm: {d: dict(matched=0, omitted=0, unsupported=0, opportunities=0) for d in DIMENSIONS} for arm in ("v3", "v4")}
    refs = {r["source"]["case_id"]: r for r in seal["body"]["records"]}
    for packet in packets:
        label = packet["blind_id"]
        binding, j = private[label], judgments[label]
        ref = refs[binding["case_id"]]
        validate_judgment(j, private, ref, now=now)
        if j.blind_id != label:
            raise ValueError("review_label_mismatch")
        facts = ref["final"]["facts"]
        eligible = all(f["certainty"] == "conclusive" for f in facts if f["material"])
        known_zero = packet["outcome"] in {"rejected", "technical_error", "not_run"}
        if known_zero or j.critical or any(r.verdict == "fail" for r in j.dimensions.values()) or j.abstention == "unjustified":
            f_case = 0
        elif not eligible or j.abstention == "indeterminate" or any(r.verdict == "indeterminate" for r in j.dimensions.values()):
            f_case = None
        elif packet["outcome"] not in ref["contract"]["allowed_outcomes"]:
            f_case = 0
        elif packet["outcome"] == "abstained":
            f_case = 1 if j.abstention == "justified" else None
        else:
            f_case = 1
        row = dict(case_id=binding["case_id"], family_id=ref["source"]["family_id"], arm=binding["arm"],
            outcome=packet["outcome"], eligible=eligible, f_case=f_case, critical=list(j.critical), abstention=j.abstention)
        rows.append(row)
        for dimension, score in j.dimensions.items():
            tally = metrics[binding["arm"]][dimension]
            tally["opportunities"] += sum(f["dimension"] == dimension and f["certainty"] == "conclusive" for f in facts)
            for name in ("matched", "omitted", "unsupported"):
                tally[name] += getattr(score, name)
    families = {}
    for case_id in refs:
        pair = {r["arm"]: r for r in rows if r["case_id"] == case_id}
        if pair["v3"]["eligible"]:
            a, b = pair["v3"]["f_case"], pair["v4"]["f_case"]
            low = (b if b is not None else 0)-(a if a is not None else 1)
            high = (b if b is not None else 1)-(a if a is not None else 0)
            families.setdefault(pair["v3"]["family_id"], []).append((low, high))
    bounds = [sum((sum(Fraction(v[i]) for v in group)/len(group) for group in families.values()), Fraction())/len(families)
              if families else None for i in (0, 1)]
    return dict(version=VERSION, kind="simulated_development_summary", cases=rows, dimensions=metrics,
        eligible_families=len(families), delta_lower=str(bounds[0]), delta_upper=str(bounds[1]),
        adoption="not_assessed_workshop", provider_calls=0)


def capacity_plan(releases, primary_pools, adjudicators, *, review_minutes=12, adjudication_minutes=6,
                  margin=1.25, safety_minutes=60):
    """Conservative worst-case simulation: two reviews + adjudication of EVERY output.

    Worker lists contain explicit (opaque id, available_from, available_until).
    This computes feasibility of declared slots, not evidence of real availability.
    """
    if len(releases) != 192 or any(t.tzinfo is None for t in releases):
        raise ValueError("six_complete_aware_microblocks_required")
    if len(primary_pools) != 2 or not all(primary_pools) or not adjudicators:
        return dict(feasible=False, reason="unassigned_review_capacity")
    all_workers = [w for pool in primary_pools for w in pool]+list(adjudicators)
    if len({w[0] for w in all_workers}) != len(all_workers):
        raise ValueError("review_roles_must_be_distinct")
    if (review_minutes <= 0 or adjudication_minutes <= 0 or margin < 1 or safety_minutes < 0
            or any(a.tzinfo is None or b <= a for _, a, b in all_workers)):
        raise ValueError("invalid_capacity_parameters")
    queues = [{name: [start, end] for name, start, end in pool} for pool in (*primary_pools, adjudicators)]
    latest = None
    for persisted in sorted(releases):
        deadline = persisted+timedelta(hours=24)-timedelta(minutes=safety_minutes)
        finished = []
        for i, duration in ((0, review_minutes), (1, review_minutes), (2, adjudication_minutes)):
            release = persisted if i < 2 else max(finished)
            choices = [(max(start, release)+timedelta(minutes=duration*margin), name, end)
                       for name, (start, end) in queues[i].items()]
            choices = [c for c in choices if c[0] <= c[2] and c[0] < deadline]
            if not choices:
                return dict(feasible=False, reason="capacity_or_individual_ttl_exceeded")
            finish, name, _ = min(choices)
            queues[i][name][0] = finish
            finished.append(finish)
            latest = max(latest, finish) if latest else finish
    return dict(feasible=True, reason="declared_capacity_only_not_authorization", outputs=len(releases),
                review_tasks=2*len(releases), adjudication_tasks=len(releases), latest_finish=latest.isoformat() if latest else None)


def audit_reviews(path: Path, expected_sha256: str, *, now: datetime):
    """Reads ONLY closed review metadata, not packets, responses or attempts."""
    if path.stat().st_size > 1_048_576:
        raise ValueError("oversized_review_metadata")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("review_metadata_hash_mismatch")
    value = json.loads(raw)
    if set(value) != {"version", "judgments"} or value["version"] != VERSION:
        raise ValueError("invalid_review_metadata_wrapper")
    judgments = [Judgment.model_validate(v) for v in value["judgments"]]
    if len({j.blind_id for j in judgments}) != len(judgments):
        raise ValueError("duplicate_review_metadata")
    if any(not j.created_at <= now < j.expires_at for j in judgments):
        raise ValueError("review_metadata_expired_or_future")
    return dict(version=VERSION, audited=len(judgments), content_reads=0, provider_calls=0)


def run_workshop(fixtures_path: Path, destination: Path, *, at: datetime):
    """Exercise all stages with explicitly invented responses/reviewer streams."""
    raw = json.loads(fixtures_path.read_text(encoding="utf-8"))
    if raw.get("kind") != "ai_authored_simulated_development" or raw.get("excluded_from_future_24_and_96") is not True:
        raise ValueError("workshop_inputs_only")
    sources, first, second, layers, adjudications = [], {}, {}, {}, {}
    for item in raw["cases"]:
        source = Source(case_id=item["case_id"], family_id=item["family_id"], headline=item["headline"],
            summary=item["summary"], neutral_identity=item.get("neutral_identity", ""),
            available_at=at-timedelta(hours=2), decision_time=at-timedelta(hours=2))
        sources.append(source)
        facts = []
        for i, (dimension, meaning) in enumerate(item["facts"]):
            field = "neutral_identity" if dimension in {"identity", "ticker_link"} and source.neutral_identity else "summary" if dimension in {"quantities", "negation", "dates", "relationship", "impact"} else "headline"
            text = getattr(source, field)
            facts.append(Fact(fact_id=f"F{i+1:02d}", dimension=dimension, meaning=meaning,
                certainty="indeterminate" if item.get("ambiguous") else "conclusive", material=True,
                citation=Citation(field=field, start=0, end=len(text), quote=text)))
        a = Annotation(case_id=source.case_id, source_fingerprint=fp(source.model_dump(mode="json")),
                       reviewer_id="sim-factual-a", facts=tuple(facts))
        b = a.model_copy(update={"reviewer_id": "sim-factual-b"})
        if source.case_id == "W-02":
            wrong = facts[0].model_copy(update={"meaning": "Invented disagreement: closure is not established."})
            b = b.model_copy(update={"facts": (wrong, *facts[1:])})
            adjudications[source.case_id] = a.model_copy(update={"reviewer_id": "sim-factual-adjudicator"})
        first[source.case_id], second[source.case_id] = a, b
        layers[source.case_id] = ContractLayer(allowed_outcomes=tuple(item.get("allowed_outcomes", ["interpreted"])),
            mappings=tuple(Representation(fact_id=f.fact_id, mode="indeterminate" if item.get("ambiguous") else
                "faithful_partial_only" if item.get("partial") else "structured") for f in facts),
            rationale="Workshop-only representability proposal, separate from factual meanings.")
    seal, seal_sha = freeze_references(sources, first, second, layers, adjudications,
                                     destination/"workshop-references.json", at=at)
    responses = []
    for i, item in enumerate(raw["cases"]):
        for arm in ("v3", "v4"):
            persisted = at+timedelta(minutes=10, seconds=i)
            responses.append(MockResponse(case_id=item["case_id"], arm=arm, outcome=item[arm]["outcome"],
                body=item[arm]["text"], persisted_at=persisted, expires_at=persisted+timedelta(hours=24)))
    packets, private = anonymize(seal, responses, now=at+timedelta(hours=1), seed=3107)
    judgments, chains, initial = {}, {}, {}
    refs = {r["source"]["case_id"]: r for r in seal["body"]["records"]}
    items = {c["case_id"]: c for c in raw["cases"]}
    for label, binding in private.items():
        spec = items[binding["case_id"]]
        output = spec[binding["arm"]]
        facts = refs[binding["case_id"]]["final"]["facts"]
        dimensions = {}
        for dimension in DIMENSIONS:
            n = sum(f["dimension"] == dimension and f["certainty"] == "conclusive" for f in facts)
            ambiguous = any(f["dimension"] == dimension and f["certainty"] == "indeterminate" for f in facts)
            status = "indeterminate" if ambiguous or (n and output["outcome"] in {"technical_error", "not_run"}) else "pass" if n else "not_applicable"
            dimensions[dimension] = Rating(verdict=status, matched=n if status == "pass" else 0, omitted=0, unsupported=0)
        if output.get("fail"):
            dimension = output["fail"]
            n = dimensions[dimension].matched
            dimensions[dimension] = Rating(verdict="fail", matched=0,
                omitted=n if output.get("omitted") else 0, unsupported=0 if output.get("omitted") else 1)
        created = at+timedelta(hours=2)
        a = Judgment(blind_id=label, reviewer_id="sim-output-a", created_at=created,
            expires_at=created+timedelta(days=90), dimensions=dimensions,
            abstention="indeterminate" if spec.get("ambiguous") and output["outcome"] == "abstained" else output.get("abstention", "not_applicable"),
            critical=(output["critical"],) if output.get("critical") else ())
        b = a.model_copy(update={"reviewer_id": "sim-output-b"})
        resolution = None
        if binding["case_id"] == "W-05" and binding["arm"] == "v3":
            changed = dict(dimensions)
            changed["dates"] = Rating(verdict="pass", matched=1, omitted=0, unsupported=0)
            b = b.model_copy(update={"dimensions": changed})
            resolution = a.model_copy(update={"reviewer_id": "sim-output-adjudicator"})
        for j in (a, b, *([resolution] if resolution else [])):
            validate_judgment(j, private, refs[binding["case_id"]], now=created)
        final, chain = adjudicate(a, b, resolution)
        judgments[label], chains[label] = final, chain
        initial[label] = [j.model_dump(mode="json") for j in (a, b, *([resolution] if resolution else []))]
    # Drop body-bearing objects before the post-TTL summary/audit. Exports are closed metadata.
    headers = [dict(blind_id=p["blind_id"], outcome=p["outcome"]) for p in packets]
    del packets, responses
    summary = summarize(seal, headers, private, judgments, now=at+timedelta(days=2))
    metadata = dict(version=VERSION, judgments=[j.model_dump(mode="json") for j in judgments.values()])
    write_once(destination/"workshop-review-metadata.json", metadata)
    metadata_sha = hashlib.sha256((destination/"workshop-review-metadata.json").read_bytes()).hexdigest()
    audit = audit_reviews(destination/"workshop-review-metadata.json", metadata_sha, now=at+timedelta(days=2))
    write_once(destination/"workshop-adjudication-chain.json", dict(version=VERSION, bindings=private,
        initial_and_adjudications=initial, chains=chains))
    write_once(destination/"workshop-summary.json", summary)
    return dict(summary=summary, audit=audit, reference_sha256=seal_sha, review_sha256=metadata_sha,
                factual_disagreements=sum(r["disagreement"] for r in seal["body"]["records"]),
                output_disagreements=sum(c["disagreement"] for c in chains.values()))


if __name__ == "__main__":
    import argparse
    from datetime import timezone
    import tempfile
    parser = argparse.ArgumentParser(description="Self-test only; no real input/import/inference mode")
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        fixture = Path(__file__).resolve().parents[2]/"evaluation/phase4c2_semantic_review_workshop_v1/examples.json"
        with tempfile.TemporaryDirectory(prefix="nacho-semantic-workshop-") as folder:
            result = run_workshop(fixture, Path(folder), at=datetime(2026, 1, 12, 12, tzinfo=timezone.utc))
            print(json.dumps(dict(status="workshop_validated_offline", cases=len(result["summary"]["cases"]),
                delta_lower=result["summary"]["delta_lower"], delta_upper=result["summary"]["delta_upper"],
                factual_disagreements=result["factual_disagreements"], output_disagreements=result["output_disagreements"],
                provider_calls=0, production_writes=0, adoption="not_assessed_workshop")))
    except Exception:
        print(json.dumps(dict(status="blocked", error="workshop_self_test_failed", provider_calls=0)))
        raise SystemExit(2)
