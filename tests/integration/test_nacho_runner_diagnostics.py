"""Fresh fictional 32-case runs only; no reference answers or historical bodies."""
from copy import deepcopy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml

from test_economic_entity_attribution import settings, payload, quote
from test_news_quote_grounding import NOW, response
from investment_system.agents.news_interpretation.persistence import LocalInterpretationStore
from investment_system.agents.news_interpretation.service import NewsInterpretationService
from investment_system.agents.news_interpretation.diagnostic_sidecar import SidecarStore
from investment_system.data.news_entities import fingerprint
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.router import LLMRouter

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("test_p0_runner", REPO / "tools/evaluation/nacho_attribution_runner.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
RUN = "eval-" + "a" * 32


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    evidence = dict(fictional=True, cases=[])
    for i in range(32):
        fields = dict(headline=f"Birch acquired Pine for 1 USD, fixture {i}.", summary="Fictional source only.")
        if i == 11:
            fields["headline"] = "Birch has not acquired Pine."
        case = f"S-{i:016x}"
        evidence["cases"].append(dict(case_id=case, evidence_fingerprint=fingerprint(fields),
            evidence=[dict(evidence_id=case+":"+k, field=k, text=v) for k, v in fields.items()]))
    identity = dict(fictional=True, virtual_decision_time=(NOW-timedelta(seconds=1)).isoformat(), entries=[])
    metadata = dict(freeze_sha256=r.FREEZE_SHA256, reference_fingerprint="0"*64,
                    frozen_at=(NOW-timedelta(minutes=1)).isoformat())
    monkeypatch.setattr(r, "verified_sources", lambda _: (deepcopy(evidence), identity, metadata))
    source = tmp_path / r.SOURCE_ROOT
    source.mkdir(parents=True)
    for name, obj in [("blind_synthetic_evidence.json", evidence), ("identity_lookup.synthetic.json", identity)]:
        (source/name).write_text(json.dumps(obj), encoding="utf-8")
    config = tmp_path / "runtime.yaml"
    raw_settings = settings().model_dump(mode="json")
    raw_settings.update(run_budget_usd=1.60, request_budget_usd=0.05, max_attempts=1,
                        retry_invalid_response=False, retry_delay_seconds=0)
    config.write_text(yaml.safe_dump(raw_settings), encoding="utf-8")
    overlay = tmp_path / "p0.yaml"
    overlay.write_text(yaml.safe_dump(dict(runtime_profile=config.name,
        evaluation_diagnostics=r.diagnostics_module().POLICY_CONFIG)), encoding="utf-8")
    legacy = r.preflight(tmp_path, config, 1.60, now=NOW)
    p0 = r.preflight(tmp_path, overlay, 1.60, now=NOW, diagnostic_sidecars=True)
    return tmp_path, config, overlay, legacy, p0


def auth(plan):
    return dict(version="nacho-evaluation-authorization-v2", approved=True, authorized_by="fixture-owner",
        authorized_at=(NOW-timedelta(seconds=5)).isoformat(), expires_at=(NOW+timedelta(hours=1)).isoformat(),
        run_id=RUN, plan_fingerprint=plan["plan_fingerprint"], freeze_sha256=r.FREEZE_SHA256,
        max_provider_calls=32, budget_usd=1.60, diagnostics_fingerprint=fingerprint(plan["evaluation_diagnostics"]))


def responses(pairs):
    result, expected = [], []
    stages = ["completed", "announced", "proposed"]
    codes = ["completion_literal_missing", "announced_literal_missing", "proposed_literal_missing"]
    numeric = [dict(value=1, value_text="one"), dict(value=2, value_text="1"),
        dict(value=2, value_text="2"), dict(value=1, value_text="1", unit="missing"),
        dict(value=1, value_text="1", scale="million"), dict(value=1, value_text="1", period="missing")]
    nums = ["number_lexeme_unparseable", "number_value_nonfinite_or_transformed", "number_absent_from_context",
        "unit_absent_from_context", "scale_absent_from_context", "period_absent_from_context"]
    for i, (_, request) in enumerate(pairs):
        data = payload(request, entities=[])
        code = None
        if i < 3:
            data["events"][0]["stage"] = stages[i]
            code = codes[i]
        elif i < 9:
            data["events"][0]["numbers"] = [dict(metric="amount", unit=None, context=quote(request), **{
                k: v for k, v in numeric[i-3].items() if k != "unit"}) |
                ({"unit": numeric[i-3]["unit"]} if "unit" in numeric[i-3] else {})]
            code = nums[i-3]
        elif i == 9:
            data["events"][0]["state_evidence"]["evidence_id"] = "f"*64
            code = "evidence_id_not_in_request"
        elif i == 10:
            data = "invalid-json"
            code = "not_available"
        elif i == 11:
            code = "negation_token_present_flag_false"
        elif i % 2:
            data = dict(schema_version="news-economic-selection-v3", status="abstained",
                        abstention_reasons=["insufficient_evidence"])
        result.append(data)
        expected.append(code)
    return result, expected


class FakeClient(BaseLLMClient):
    provider = "openai"

    def __init__(self, data, unknown_at=None):
        self.data, self.calls, self.unknown_at = data, 0, unknown_at

    def complete(self, request, model):
        value = response(self.data[self.calls])
        self.calls += 1
        value.raw.update(usage_reported=True, cache_write_tokens=0)
        if self.calls == self.unknown_at:
            value.raw.pop("cache_write_tokens")
        return value


def service_at(path, cfg, data, *, unknown_at=None, authorized=True):
    fake = FakeClient(data, unknown_at)
    router = LLMRouter({"openai": fake}, {"news_interpretation": {"provider": "openai", "model": cfg.adapter.model}})
    storage = LocalInterpretationStore(path/"runtime", allowed_root=path)
    service = NewsInterpretationService(router, cfg, storage, RUN, execution_authorized=authorized,
                                         simulated=True, clock=lambda: NOW)
    return fake, service


def test_full_32_run_same_semantics_budgets_and_specific_subcodes(prepared, monkeypatch):
    base, _, _, legacy, p0 = prepared
    a, cfg, pairs = legacy
    b, cfg2, pairs2 = p0
    assert cfg == cfg2 and a["cases"] == b["cases"]
    for key in ("maximum_reserved_usd", "input_token_upper_bound_total", "output_token_cap_total", "run_budget_usd"):
        assert a[key] == b[key]
    assert a["plan_fingerprint"] != b["plan_fingerprint"]
    data, codes = responses(pairs)
    fake1, service1 = service_at(base/"legacy", cfg, data)
    fake2, service2 = service_at(base/"observed", cfg, data)
    old = r.execute_cases(pairs, service1, base/"legacy", a)
    store = SidecarStore(base/"sidecars", allowed_root=base)
    new = r.execute_cases(pairs2, service2, base/"observed", b, p0_authorization=auth(b), sidecar_store=store)
    assert fake1.calls == fake2.calls == 32
    assert old["accounted_usd"] == new["accounted_usd"]
    assert new["diagnostics_complete"]
    for before, after, code in zip(old["cases"], new["cases"], codes):
        # Attempt IDs are independently randomized; compare semantic payloads.
        assert before["outcome"] == after["outcome"]
        assert before.get("events") == after.get("events")
        assert before.get("units") == after.get("units")
        assert before.get("diagnostics") == after.get("diagnostics")
        sidecar = store.read(RUN, after["case_id"], now=NOW)
        assert sidecar.record_id == after["record_id"]
        assert [d.subcode for d in sidecar.diagnostics] == ([code] if code else [])
        record = service2.storage.read(after["record_id"], now=NOW)
        assert record.expires_at-record.persisted_at == timedelta(hours=24)
    def forbidden(*args, **kwargs):
        raise AssertionError("expired_content_must_not_be_read")
    monkeypatch.setattr(LocalInterpretationStore, "read", forbidden)
    path = base/"observed/diagnostic-manifest.json"
    report = r.diagnostics_module().audit(path, new["diagnostic_manifest_sha256"], store=store, now=NOW+timedelta(days=2))
    assert report["cases"] == 32 and report["content_reads"] == 0
    with pytest.raises(ValueError):
        r.diagnostics_module().audit(path, new["diagnostic_manifest_sha256"], store=store, now=NOW+timedelta(days=90))


@pytest.mark.parametrize("change", [{"version": "nacho-evaluation-authorization-v1"},
    {"diagnostics_fingerprint": "0"*64}, {"approved": False}, {"run_id": "old-run"}])
def test_new_specific_authorization_required(prepared, change):
    _, _, _, _, (plan, _, _) = prepared
    declaration = auth(plan) | change
    with pytest.raises(ValueError):
        r.validate_authorization(declaration, plan, RUN, NOW)


def test_missing_authorization_blocks_before_attempt_and_writes(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"unauthorized", cfg, responses(pairs)[0])
    with pytest.raises(ValueError):
        r.execute_cases(pairs, service, base/"outputs", plan)
    assert fake.calls == 0 and not (base/"outputs").exists()


def test_service_authorization_is_not_bypassed(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"denied", cfg, responses(pairs)[0], authorized=False)
    with pytest.raises(ValueError):
        r.execute_cases(pairs, service, base/"outputs", plan, p0_authorization=auth(plan))
    assert fake.calls == 0 and not (base/"outputs").exists()


def test_pre_call_failure_records_no_call_without_false_attempt(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"precall", cfg, responses(pairs)[0])
    store = SidecarStore(base/"sidecars", allowed_root=base)
    def forbidden():
        raise ValueError("SECRET_NOT_LOGGED")
    result = r.execute_cases(pairs, service, base/"precall", plan, p0_authorization=auth(plan),
                             sidecar_store=store, before_call=forbidden)
    assert fake.calls == 0 and result["diagnostics_complete"]
    assert all(c["outcome"] == "not_run" and c["record_id"] is None for c in result["cases"])
    assert "SECRET_NOT_LOGGED" not in json.dumps(result)
    item = store.read(RUN, pairs[0][0]["case_id"], now=NOW)
    assert item.lifecycle_code == "preflight_failed" and item.attempt_id is None


def test_requests_cannot_be_swapped_after_plan(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"swapped", cfg, responses(pairs)[0])
    changed = list(pairs)
    changed[0] = (pairs[0][0], pairs[1][1])
    with pytest.raises(ValueError, match="case_plan"):
        r.execute_cases(changed, service, base/"outputs", plan, p0_authorization=auth(plan))
    assert fake.calls == 0


def test_sidecar_failure_preserves_attempt_and_halts_without_retry(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"failure", cfg, responses(pairs)[0])
    class FailingStore(SidecarStore):
        def write(self, *args, **kwargs):
            raise OSError("SECRET_MUST_NOT_APPEAR")
    store = FailingStore(base/"sidecars", allowed_root=base)
    result = r.execute_cases(pairs, service, base/"failure", plan, p0_authorization=auth(plan), sidecar_store=store)
    assert fake.calls == 1 and not result["diagnostics_complete"]
    assert result["cases"][0]["outcome"] == "invalid_response"
    assert result["cases"][0]["record_id"] is not None
    assert len(list((base/"failure/runtime/attempts").glob("*.json"))) == 1
    assert all(c["outcome"] == "not_run" for c in result["cases"][1:])
    assert service.budget.accounted() > 0
    assert "SECRET_MUST_NOT_APPEAR" not in json.dumps(result)
    with pytest.raises(ValueError, match="incomplete"):
        r.diagnostics_module().audit(base/"failure/diagnostic-manifest.json", result["diagnostic_manifest_sha256"],
                                     store=store, now=NOW)


def test_unknown_cost_halts_and_registers_remaining_not_run(prepared):
    base, _, _, _, (plan, cfg, pairs) = prepared
    fake, service = service_at(base/"unknown", cfg, responses(pairs)[0], unknown_at=2)
    store = SidecarStore(base/"sidecars", allowed_root=base)
    result = r.execute_cases(pairs, service, base/"unknown", plan, p0_authorization=auth(plan), sidecar_store=store)
    assert fake.calls == 2 and result["diagnostics_complete"]
    assert result["unknown_cost_attempts"] == 1
    for row in result["cases"][2:]:
        item = store.read(RUN, row["case_id"], now=NOW)
        assert item.outcome == "not_run" and item.record_id is None and item.attempt_id is None
        assert item.lifecycle_code == "upstream_halt"
    report = r.diagnostics_module().audit(base/"unknown/diagnostic-manifest.json",
        result["diagnostic_manifest_sha256"], store=store, now=NOW+timedelta(days=2))
    assert report["outcomes"]["not_run"] == 30


def test_overlay_requires_both_opt_ins_and_preserves_expiry(prepared):
    base, config, overlay, _, _ = prepared
    with pytest.raises(ValueError, match="explicit_cli"):
        r.preflight(base, overlay, 1.60, now=NOW)
    with pytest.raises(ValueError, match="explicit_diagnostic_profile"):
        r.preflight(base, config, 1.60, now=NOW, diagnostic_sidecars=True)
    with pytest.raises(ValueError, match="expired"):
        r.preflight(base, overlay, 1.60, now=NOW+timedelta(days=1000), diagnostic_sidecars=True)


@pytest.mark.parametrize("mutation", ["manifest_hash", "swapped", "sidecar_tamper", "extra_text"])
def test_metadata_audit_rejects_tampering(prepared, mutation):
    base, _, _, _, (plan, cfg, pairs) = prepared
    # All abstain, limiting fixture complexity without opening historical outputs.
    data = [dict(schema_version="news-economic-selection-v3", status="abstained",
                 abstention_reasons=["insufficient_evidence"])]*32
    _, service = service_at(base/"audit", cfg, data)
    store = SidecarStore(base/"sidecars", allowed_root=base)
    output = r.execute_cases(pairs, service, base/"audit", plan, p0_authorization=auth(plan), sidecar_store=store)
    manifest = base/"audit/diagnostic-manifest.json"
    content = json.loads(manifest.read_bytes())
    expected = output["diagnostic_manifest_sha256"]
    if mutation == "manifest_hash":
        expected = "0"*64
    elif mutation == "swapped":
        content["cases"][0]["sidecar_id"] = content["cases"][1]["sidecar_id"]
    elif mutation == "extra_text":
        content["SECRET_FIELD"] = "SECRET_BODY"
    else:
        path = store._path(RUN, pairs[0][0]["case_id"])
        raw = json.loads(path.read_bytes())
        raw["metadata"]["request_id"] = "0"*64
        raw["sidecar_id"] = fingerprint(raw["metadata"])
        path.write_text(json.dumps(raw), encoding="utf-8")
    if mutation in {"swapped", "extra_text"}:
        manifest.write_text(json.dumps(content), encoding="utf-8")
        expected = r.sha(manifest)
    with pytest.raises(ValueError):
        r.diagnostics_module().audit(manifest, expected, store=store, now=NOW)


def test_cli_offline_and_unapproved_no_credentials(prepared, monkeypatch, capsys):
    from scripts import run_phase4c2_attribution_evaluation as cli
    base, _, overlay, _, bundle = prepared
    monkeypatch.setattr(cli, "preflight", lambda *args, **kwargs: bundle)
    def forbidden(*args, **kwargs):
        raise AssertionError("no_credentials")
    monkeypatch.setattr(cli, "load_repository_environment", forbidden)
    argv = ["runner", "--config", str(overlay), "--diagnostic-sidecars"]
    for tail, status in [(["--validate-only"], 0), (["--confirm-real-inference"], 2)]:
        monkeypatch.setattr(sys, "argv", argv+tail)
        assert cli.main() == status
        assert json.loads(capsys.readouterr().out)["provider_calls"] == 0
