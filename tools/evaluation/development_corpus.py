"""Read-only checks for the fictional 24-case development corpus. No inference path."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from investment_system.agents.news_interpretation.schemas import NewsInterpretationRequest
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_evaluation import synthetic_record
from investment_system.data.schemas.news import NewsRecord
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry

VERSION = "news-prompt-development-corpus-v1"
ROOT = "evaluation/phase4c2_development_corpus_v1"
STRATA = ("announced", "completed", "proposed", "unknown_stage", "negation",
          "temporal_conditions", "direct_participation", "indirect_relations",
          "context_and_identity", "numeric_fidelity", "dates_and_pit", "insufficient_evidence")
COMPARATORS = (
    "evaluation/phase4c2_attribution_v1/synthetic_sources.json",
    "evaluation/phase4c2_p1_prompt_v4/fixtures.json",
    "evaluation/phase4c2_semantic_review_workshop_v1/examples.json",
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.utcoffset() is None:
        raise ValueError("timezone_required")
    return value


def identifier(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256((VERSION + ":" + value).encode()).hexdigest()[:16]


def build(authoring: dict) -> dict[str, dict]:
    """Derive primary revisions, exact field evidence and filtered neutral identities.

    The explicit empty ticker prevents synthetic_record's historical real-ticker
    default. No prompt, settings, router, model output or reference is imported.
    """
    families = authoring["families"]
    if (len(families) != 12 or Counter(f["stratum"] for f in families) != Counter(STRATA)
            or len({f["key"] for f in families}) != 12):
        raise ValueError("twelve_unique_families_and_strata_required")
    clock = authoring["virtual_clock"]
    times = {k: utc(clock[k]) for k in (
        "published_at", "first_seen_at", "available_at", "ingested_at", "decision_time")}
    if not (times["published_at"] <= times["first_seen_at"] == times["available_at"]
            <= times["ingested_at"] <= times["decision_time"]):
        raise ValueError("invalid_virtual_clock")
    names = sorted({name for f in families for name in f["entities"]}
                   - set(authoring["unlisted_entities"]))
    registry = []
    for index, name in enumerate(names, 1):
        entry = EntityRegistryEntry(
            entity_id=identifier("dev-entity-", name), corporate_name=name,
            security_id=identifier("dev-security-", name), ticker=f"SYNTH-DEV24-{index:03d}",
            aliases=(), effective_from="2031-01-01", known_at="2031-03-20T09:00:00Z",
            evidence="Fictional identity and non-market security identifier authored for development; no economic relationship asserted.")
        if name == "Yrvexil Bioceramics":
            entry = EntityRegistryEntry.model_validate({**entry.model_dump(mode="json"),
                "known_at": "2031-03-21T10:05:00Z"})
            future = EntityRegistryEntry.model_validate({**entry.model_dump(mode="json"),
                "security_id": identifier("dev-security-", name+":future"),
                "ticker": "SYNTH-DEV24-FUTURE", "known_at": "2031-03-20T09:00:00Z",
                "effective_from": "2031-03-22"})
            registry.append(future)
        registry.append(entry)
    packets, private = [], []
    for family in families:
        if not family["axis"] or not family["novelty"] or family["a"] == family["b"]:
            raise ValueError("counterfactual_change_required")
        family_id = identifier("DF-", family["key"])
        for variant in ("a", "b"):
            case_id = identifier("D-", family["key"]+":"+variant)
            headline = family["headline"]
            summary = family["summary_prefix"] + family[variant]
            news = synthetic_record(case_id, headline, ticker="", summary=summary,
                published_at=times["published_at"], available_at=times["available_at"])
            news = NewsRecord.model_validate({**news.model_dump(mode="json"),
                "first_seen_at": times["first_seen_at"], "ingested_at": times["ingested_at"]})
            fact_date = times["published_at"].date()
            relevant = [e for e in registry if e.corporate_name in family["entities"]]
            # Do not hint at an unnamed actor merely by exposing its family inventory.
            eligible = tuple(e for e in relevant if e.corporate_name in headline+" "+summary
                and e.known_at <= times["decision_time"]
                and e.effective_from <= fact_date and (e.effective_to is None or fact_date < e.effective_to))
            request = NewsInterpretationRequest(news=news, decision_time=times["decision_time"],
                registry_entries=eligible)
            evidence = [dict(evidence_id=e.evidence_id, **e.model_dump(mode="json")) for e in request.evidence]
            packet = dict(case_id=case_id, primary_revision_id=news.revision_id,
                request=request.model_dump(mode="json"), request_fingerprint=request.request_id,
                evidence=evidence, evidence_fingerprint=request.evidence_fingerprint)
            packet["packet_fingerprint"] = fingerprint(packet)
            packets.append(packet)
            private.append(dict(case_id=case_id, family_id=family_id, variant=variant,
                primary_stratum=family["stratum"], secondary_tags=family["tags"],
                counterfactual_axis=family["axis"], deliberate_ambiguity=family["ambiguity"],
                originality_note=family["novelty"], relevant_registry_ids=[e.security_id for e in relevant],
                changed_field="summary", start=len(family["summary_prefix"]),
                old=family["a"], new=family["b"], packet_fingerprint=packet["packet_fingerprint"]))
    # Stable opaque order conceals adjacency; it is not a future inference schedule.
    packets.sort(key=lambda p: p["case_id"])
    private.sort(key=lambda p: p["case_id"])
    return {
        "corpus.json": dict(version=VERSION, purpose="development_only", fictional=True,
            cases=packets, corpus_fingerprint=fingerprint(packets)),
        "registry.json": dict(version="news-development-neutral-registry-v1", fictional=True,
            real_market_symbols=False, entries=[e.model_dump(mode="json") for e in registry]),
        "private-design.json": dict(version="news-development-private-design-v1", cases=private,
            not_model_input=True, semantic_reference_status="not_created"),
        "review-template.json": dict(version="news-development-unfilled-review-template-v1",
            instrument="news-semantic-review-instrument-v1", status="unfilled_not_a_reference",
            factual_forms=[dict(case_id=p["case_id"], source_fingerprint=p["packet_fingerprint"],
                reviewer_id=None, provenance_kind=None, started_at=None, completed_at=None,
                timestamp_source=None, facts=[]) for p in packets],
            separate_contract_forms=[dict(case_id=p["case_id"],
                contract_version="news-economic-validation-v3", source_factual_reference_sha256=None,
                allowed_outcomes=[], mappings=[]) for p in packets]),
    }


def prior_sources(repo: Path) -> list[dict]:
    """Only allowlisted source text fields; never retrieve historical annotations/outputs."""
    result = []
    for name in COMPARATORS:
        for i, case in enumerate(read(repo/name)["cases"]):
            result.append(dict(group=name, id=case.get("key", case.get("id", case.get("case_id", str(i)))),
                text=case["headline"]+" "+case.get("summary", "")))
    if len(result) != 80:
        raise ValueError("comparator_inventory_changed")
    return result


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).casefold())


def delexicalize(text: str) -> list[str]:
    """Conservative surface-template probe; not a semantic equivalence detector."""
    text = re.sub(r"\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*\b", "ENTITY", text)
    return ["number" if word.isdigit() else word for word in tokens(text)]


def concept_tokens(text: str) -> set[str]:
    """Transparent broad-topic normalization; all neighbors still need author review."""
    groups = {
        "ownership": ("acqui", "takeover", "purchase", "buy", "merger"),
        "restriction": ("suspend", "halt", "withdraw", "restrict", "penalty", "permit"),
        "finance": ("financ", "fund", "grant", "redemption", "payment", "escrow"),
        "operation": ("operat", "production", "plant", "furnace", "kiln", "refit"),
        "relation": ("supplier", "supply", "subsidiar", "parent", "partner", "licen"),
        "numbers": ("revenue", "receipts", "tonne", "usd", "eur", "million", "thousand"),
        "identity": ("unnamed", "unidentified", "name", "holder", "caption"),
        "timing": ("date", "day", "week", "month", "year", "pending", "condition"),
    }
    return {category for word in tokens(text) for category, roots in groups.items()
            if any(word.startswith(root) for root in roots)}


def jaccard(left: set, right: set) -> float:
    return len(left & right)/len(left | right) if left | right else 0.0


def similarity(left: str, right: str) -> dict:
    a, b = tokens(left), tokens(right)
    da, db = delexicalize(left), delexicalize(right)
    block = SequenceMatcher(None, a, b, autojunk=False).find_longest_match()
    return dict(token_jaccard=round(jaccard(set(a), set(b)), 6),
        delexicalized_bigram_jaccard=round(jaccard(set(zip(da, da[1:])), set(zip(db, db[1:]))), 6),
        longest_common_tokens=block.size,
        topic_overlap=round(jaccard(concept_tokens(left), concept_tokens(right)), 6))


def originality(repo: Path, corpus: dict) -> dict:
    prior = prior_sources(repo)
    rows = []
    for packet in corpus["cases"]:
        news = packet["request"]["news"]
        text = news["headline"]+" "+news["summary"]
        neighbors = [dict(group=p["group"], id=p["id"], **similarity(text, p["text"])) for p in prior]
        nearest = {}
        for metric in ("token_jaccard", "delexicalized_bigram_jaccard", "longest_common_tokens", "topic_overlap"):
            nearest[metric] = max(neighbors, key=lambda n: n[metric])
        exact = any(tokens(text) == tokens(p["text"]) for p in prior)
        if exact:
            raise ValueError("reused_prior_text")
        rows.append(dict(case_id=packet["case_id"], exact_normalized_match=exact, nearest=nearest,
            surface_review_flag=any(n["token_jaccard"] >= .38 or n["delexicalized_bigram_jaccard"] >= .52
                or n["longest_common_tokens"] >= 12 for n in neighbors)))
    return dict(version="news-development-originality-audit-v1", compared_source_cases=80,
        comparisons=len(rows)*80, source_files={p: sha(repo/p) for p in COMPARATORS},
        method="NFKC token, name/number-delexicalized bigrams, longest token span, broad-topic lexicon; not semantic proof",
        thresholds="surface-review triage only; not model scoring or statistical adoption thresholds",
        conceptual_review="AI author self-review in private design and documentation; independent review pending",
        entity_name_reuse=[name for f in read(repo/ROOT/"authoring.json")["families"] for name in f["entities"]
            if any(name.casefold() in p["text"].casefold() for p in prior)],
        historical_predictions_and_annotations_consulted=False, cases=rows)


def verify(repo: Path) -> dict:
    """Verify pins and exact deterministic reconstruction, including PIT and separation."""
    folder = repo/ROOT
    manifest = read(folder/"manifest.json")
    if any(sha(repo/path) != digest for path, digest in manifest["sha256"].items()):
        raise ValueError("artifact_hash_mismatch")
    built = build(read(folder/"authoring.json"))
    for name, value in built.items():
        if read(folder/name) != value:
            raise ValueError("corpus_reconstruction_mismatch")
    if read(folder/"originality-audit.json") != originality(repo, built["corpus.json"]):
        raise ValueError("originality_reconstruction_mismatch")
    return dict(status="development_corpus_verified_offline", cases=24, families=12,
        strata=12, evidence_fields=48, provider_calls=0, predictions=0, reserved_cases=0,
        independent_semantic_review="pending", corpus_fingerprint=built["corpus.json"]["corpus_fingerprint"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", required=True)
    parser.parse_args()
    try:
        print(json.dumps(verify(Path(__file__).resolve().parents[2]), sort_keys=True))
    except Exception:
        print(json.dumps(dict(status="blocked", error="development_corpus_verification_failed", provider_calls=0)))
        raise SystemExit(2)
