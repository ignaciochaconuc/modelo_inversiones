"""Four-lane cost correction and smoke preflight; all transports stay offline."""
from datetime import datetime, timedelta
import json
from pathlib import Path

import httpx
import pytest
import yaml

from investment_system.agents.news_interpretation.runtime_schemas import InterpretationRuntimeSettings
from investment_system.agents.news_interpretation.service import reservation_bound
from investment_system.llm.openai_client import OpenAIClient
from investment_system.llm.openai_settings import LLMProviderError
from scripts import run_phase4c2_news_smoke as cli
from test_news_interpretation_runtime import NOW, MODEL, settings, response, request, service


def v2_settings(**updates):
    data = settings().model_dump(mode="json")
    data["settings_version"] = "news-inference-settings-v2"
    data["adapter"].update(transport_version="openai-responses-settings-v2",
        reasoning_effort="none", supported_parameters=["reasoning_effort"],
        service_tier="default", prompt_cache_mode="implicit", prompt_cache_ttl="30m",
        capability_max_output_tokens=128000, capability_max_input_tokens=922000)
    data["pricing"].update(pricing_version="news-token-prices-v2", input_per_million=0.20,
        cached_input_per_million=0.02, cache_write_per_million=0.25,
        output_per_million=1.20, short_context_max_input_tokens=272000)
    data.update(max_attempts=1, retry_invalid_response=False)
    data.update(updates)
    return InterpretationRuntimeSettings.model_validate(data)


def test_v1_roundtrip_unchanged_and_versions_cannot_mix():
    legacy = settings().model_dump(mode="json")
    assert "pricing_version" not in legacy["pricing"]
    assert "transport_version" not in legacy["adapter"]
    assert InterpretationRuntimeSettings.model_validate(legacy).model_dump(mode="json") == legacy
    modern = v2_settings().model_dump(mode="json")
    modern["settings_version"] = "news-inference-settings-v1"
    with pytest.raises(ValueError):
        InterpretationRuntimeSettings.model_validate(modern)


@pytest.mark.parametrize("writes", [0, 30, 80])
def test_disjoint_cache_write_charge_roundtrip_cache_and_core_contract(tmp_path, writes):
    resp = response()
    resp.raw["cache_write_tokens"] = writes
    svc, client = service(tmp_path, [resp], config=v2_settings())
    delivered = svc.interpret(request())
    expected = ((80-writes)*0.20 + 20*0.02 + writes*0.25 + 50*1.20)/1_000_000
    assert delivered.additional_provider_cost_usd == pytest.approx(expected)
    record = delivered.record
    assert record.schema_version == "news-inference-attempt-v2"
    assert record.cache_write_tokens == writes
    assert "cache_write_tokens" not in record.provider_response.model_dump()
    assert "cache_write_tokens" not in record.interpretation.result.provenance.model_dump()
    assert svc.reconstruct(delivered.record_id).record == record
    assert svc.interpret(request()).additional_provider_cost_usd == 0
    assert client.calls == 1
    dumped = record.model_dump(mode="json")
    dumped["cache_write_tokens"] = writes + 1
    with pytest.raises(ValueError):
        type(record).model_validate(dumped)


@pytest.mark.parametrize("written", [None, True, -1, "30"])
def test_missing_or_malformed_writes_are_unknown_never_zero(tmp_path, written):
    resp = response()
    if written is not None:
        resp.raw["cache_write_tokens"] = written
    svc, client = service(tmp_path, [resp], config=v2_settings())
    delivered = svc.interpret(request())
    assert delivered.additional_provider_cost_usd is None
    assert delivered.record.cache_write_tokens is None
    assert delivered.record.accounted_usd == delivered.record.maximum_reserved_usd
    assert svc.tracker.unknown_cost_count() == 1 and client.calls == 1


def test_overlapping_reads_writes_rejected_and_not_retried(tmp_path):
    resp = response()
    resp.raw["cache_write_tokens"] = 81
    svc, client = service(tmp_path, [resp], config=v2_settings())
    delivered = svc.interpret(request())
    assert delivered.error_code == "invalid_usage_telemetry"
    assert delivered.additional_provider_cost_usd is None and client.calls == 1


def test_reservation_uses_most_expensive_input_lane_and_price_band(tmp_path):
    cfg = v2_settings()
    svc, _ = service(tmp_path, config=cfg)
    _, wire, _ = svc.invocation(request())
    bound, cost = reservation_bound(wire, cfg)
    assert cost == (bound*0.25 + 1024*1.20)/1_000_000
    bad = cfg.model_dump(mode="json")
    bad["pricing"]["short_context_max_input_tokens"] = bound - 1
    svc2, client = service(tmp_path / "band", config=InterpretationRuntimeSettings.model_validate(bad))
    assert svc2.interpret(request()).error_code == "estimated_input_exceeds_verified_price_band"
    assert client.calls == 0
    with pytest.raises(ValueError, match="price_band"):
        cfg.pricing.estimate_usage(272001, 0, 0, 0)


def test_budget_insufficient_before_any_attempt(tmp_path):
    cfg = v2_settings(request_budget_usd=0.000001, run_budget_usd=0.000001)
    svc, client = service(tmp_path, config=cfg)
    assert svc.interpret(request()).error_code == "request_or_run_budget_insufficient"
    assert client.calls == 0


def test_single_attempt_even_on_transient_error(tmp_path):
    svc, client = service(tmp_path, [LLMProviderError("timeout", retryable=True)], config=v2_settings())
    delivered = svc.interpret(request())
    assert client.calls == 1 and delivered.additional_attempts == 1
    assert delivered.additional_provider_cost_usd is None


def test_responses_wire_and_write_usage_with_mock_transport(tmp_path, monkeypatch):
    cfg = v2_settings()
    svc, _ = service(tmp_path, config=cfg)
    llm, _, _ = svc.invocation(request())
    seen = []
    def handler(http):
        payload = json.loads(http.content)
        seen.append(payload)
        assert payload["reasoning"] == {"effort":"none"}
        assert "reasoning_effort" not in payload
        assert payload["service_tier"] == "default"
        assert payload["text"]["format"]["strict"] is True
        assert payload["tools"] == [] and payload["store"] is False
        return httpx.Response(200, json={"model":MODEL,"created_at":NOW.timestamp(),"status":"completed",
            "output":[],"usage":{"input_tokens":100,"output_tokens":50,
            "input_tokens_details":{"cached_tokens":20,"cache_write_tokens":30}}})
    monkeypatch.setenv("OPENAI_API_KEY", "offline-secret-value")
    client = OpenAIClient(cfg.adapter, enabled=True, transport=httpx.MockTransport(handler))
    parsed = client.complete(llm, MODEL)
    assert parsed.raw["cache_write_tokens"] == 30 and len(seen) == 1
    assert "offline-secret-value" not in parsed.model_dump_json()


def test_offline_cli_preflight_never_initializes_live_runtime(tmp_path, monkeypatch, capsys):
    cfg = v2_settings(request_budget_usd=0.05, run_budget_usd=0.05)
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")), encoding="utf-8")
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(cli, "datetime", FrozenDateTime)
    monkeypatch.setattr(cli, "build_interpretation_request", lambda *a, **k: request())
    monkeypatch.setattr(cli, "load_entity_registry", lambda: ())
    monkeypatch.setattr(cli, "NewsStore", lambda *a: None)
    def forbidden(*args, **kwargs):
        pytest.fail("offline preflight must not initialize runtime or call a provider")
    monkeypatch.setattr(cli, "LocalInterpretationStore", forbidden)
    monkeypatch.setattr(OpenAIClient, "complete", forbidden)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["smoke", "--config", str(path), "--model", MODEL,
        "--budget-usd", "0.05", "--revision-id", "0"*64, "--as-of", NOW.isoformat(), "--validate-only"])
    assert cli.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "validated_offline"
    assert result["provider_calls"] == result["persistence_writes"] == 0
    assert not result["api_key_present"]
    assert result["maximum_reserved_usd"] < 0.05
    assert result["max_attempts"] == 1


def test_local_profile_is_explicit_secret_free_and_officially_sourced():
    raw = yaml.safe_load(Path("config/news_interpretation.local.yaml").read_text(encoding="utf-8"))
    cfg = InterpretationRuntimeSettings.model_validate(raw)
    assert cfg.adapter.model == "gpt-5.6-luna"
    assert cfg.adapter.max_output_tokens == 2048
    assert cfg.adapter.context_window_tokens == 1050000
    assert cfg.adapter.effective_parameters["reasoning"] == {"effort":"none"}
    assert cfg.pricing.cache_write_per_million == 0.25
    assert cfg.request_budget_usd == cfg.run_budget_usd == 0.05
    assert cfg.max_attempts == 1 and not cfg.retry_invalid_response
    assert cfg.pricing.valid_from.utcoffset() == timedelta(0)
    assert cfg.pricing.valid_from < cfg.pricing.valid_until
    assert "developers.openai.com" in cfg.pricing.source
    assert "api_key" not in json.dumps(raw, default=str).lower()
