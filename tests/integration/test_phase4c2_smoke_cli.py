"""CLI opt-in validation only: never issue a real smoke call."""
import json
from pathlib import Path

import pytest
import yaml

from scripts import run_phase4c2_news_smoke as cli


def arguments(tmp_path):
    return ["smoke","--config",str(tmp_path/"config.yaml"),"--model","explicit-model",
            "--budget-usd","0.05","--revision-id","0"*64,"--as-of","2026-10-12T13:17:53Z"]


def test_cli_disabled_before_config_key_or_news_access(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",arguments(tmp_path))
    monkeypatch.setattr(cli.os,"getenv",lambda _: (_ for _ in ()).throw(AssertionError("must not access key")))
    assert cli.main()==2
    assert json.loads(capsys.readouterr().out)["provider_calls"]==0
    assert not list(tmp_path.iterdir())


def test_cli_missing_key_never_calls_provider(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",arguments(tmp_path)+["--confirm-real-inference"])
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    assert cli.main()==2
    assert "missing_api_key" in capsys.readouterr().out


def test_cli_template_is_deliberately_incomplete_and_secret_free(tmp_path,monkeypatch,capsys):
    text=Path("config/news_interpretation.example.yaml").read_text()
    (tmp_path/"config.yaml").write_text(text)
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-cli-secret")
    monkeypatch.setattr("sys.argv",arguments(tmp_path)+["--confirm-real-inference"])
    assert cli.main()==2
    output=capsys.readouterr().out
    assert "synthetic-cli-secret" not in output
    assert json.loads(output)["provider_calls"]==0
    data=yaml.safe_load(text)
    assert data["adapter"]["model"] is None and data["pricing"]["input_per_million"] is None


def test_cli_help_does_not_initialize_runtime(monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",["smoke","--help"])
    with pytest.raises(SystemExit) as exc:cli.main()
    assert exc.value.code==0
    assert "confirm-real-inference" in capsys.readouterr().out


def test_invalid_yaml_never_echoes_context_or_secret(tmp_path,monkeypatch,capsys):
    (tmp_path/"config.yaml").write_text('adapter: [bad\n private: synthetic-cli-secret')
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-cli-secret")
    monkeypatch.setattr("sys.argv",arguments(tmp_path)+["--confirm-real-inference"])
    assert cli.main()==2
    assert "synthetic-cli-secret" not in capsys.readouterr().out


def test_yaml_timestamps_are_accepted_without_real_execution(tmp_path,monkeypatch,capsys):
    from datetime import datetime,timezone
    raw=yaml.safe_load(Path("config/news_interpretation.example.yaml").read_text())
    raw["adapter"].update(model="explicit-model",capabilities_model="explicit-model",structured_outputs_supported=True,
        capability_max_output_tokens=2048,context_window_tokens=200000,capability_source="synthetic",capabilities_verified_at=datetime(2020,1,1,tzinfo=timezone.utc))
    raw["pricing"].update(model="explicit-model",input_per_million=1,cached_input_per_million=0.1,output_per_million=2,
        source="synthetic",valid_from=datetime(2020,1,1,tzinfo=timezone.utc),valid_until=datetime(2100,1,1,tzinfo=timezone.utc))
    raw.update(request_budget_usd=0.05,run_budget_usd=0.1,local_restricted_storage_acknowledged=True)
    (tmp_path/"config.yaml").write_text(yaml.safe_dump(raw))
    reached=[]
    def stop_before_news(*args,**kwargs):
        reached.append(True)
        raise ValueError("synthetic stop")
    monkeypatch.setattr(cli,"build_interpretation_request",stop_before_news)
    monkeypatch.setenv("OPENAI_API_KEY","synthetic-cli-secret")
    monkeypatch.setattr("sys.argv",arguments(tmp_path)+["--confirm-real-inference"])
    assert cli.main()==2 and reached
    assert json.loads(capsys.readouterr().out)["provider_calls"]==0
