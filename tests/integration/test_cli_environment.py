"""Credential bootstrap tests use synthetic files and no external operations."""
import importlib
import json
import logging
import runpy
from pathlib import Path

import pytest

from investment_system.core import environment
from investment_system.core.config import load_settings, load_news_settings
from investment_system.core.logging import JsonFormatter


def test_root_is_anchored_to_module_not_current_directory(tmp_path, monkeypatch, capsys, caplog):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    (tmp_path / ".env").write_text("FINNHUB_API_KEY=synthetic-root-key\n", encoding="utf-8")
    arbitrary = tmp_path / "other"
    arbitrary.mkdir()
    (arbitrary / ".env").write_text("FINNHUB_API_KEY=wrong-cwd-key\n", encoding="utf-8")
    monkeypatch.chdir(arbitrary)
    assert environment.load_repository_environment(real_operation_authorized=True)
    assert environment.os.getenv("FINNHUB_API_KEY") == "synthetic-root-key"
    assert not capsys.readouterr().out and not caplog.text


@pytest.mark.parametrize("existing", ["system-key", ""])
def test_environment_priority_including_explicit_empty_values(tmp_path, monkeypatch, existing):
    monkeypatch.setenv("OPENAI_API_KEY", existing)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=synthetic-file-key\n", encoding="utf-8")
    environment.load_repository_environment(real_operation_authorized=True)
    assert environment.os.getenv("OPENAI_API_KEY") == existing


def test_no_authorization_never_touches_file_or_dotenv(monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("dotenv must not be called")
    monkeypatch.setattr(environment, "load_dotenv", forbidden)
    with pytest.raises(environment.EnvironmentBootstrapError, match="authorization_required"):
        environment.load_repository_environment(real_operation_authorized=False)


def test_missing_file_keeps_system_credentials(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "system-key")
    assert not environment.load_repository_environment(real_operation_authorized=True)
    assert environment.os.getenv("TIINGO_API_KEY") == "system-key"


def test_options_and_no_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", "synthetic-private-key")
    monkeypatch.delenv("CLI_BOOTSTRAP_TEST_MARKER", raising=False)
    (tmp_path / ".env").write_text("CLI_BOOTSTRAP_TEST_MARKER=${TIINGO_API_KEY}\n", encoding="utf-8")
    actual = environment.load_dotenv
    seen = []
    def capture(**kwargs):
        seen.append(kwargs)
        return actual(**kwargs)
    monkeypatch.setattr(environment, "load_dotenv", capture)
    environment.load_repository_environment(real_operation_authorized=True)
    assert seen[0]["dotenv_path"] == tmp_path / ".env"
    assert seen[0]["override"] is False and seen[0]["interpolate"] is False
    assert environment.os.getenv("CLI_BOOTSTRAP_TEST_MARKER") == "${TIINGO_API_KEY}"


def test_imports_and_yaml_configuration_never_load_dotenv(monkeypatch):
    import dotenv
    def forbidden(*args, **kwargs):
        pytest.fail("import/configuration must not load dotenv")
    monkeypatch.setattr(dotenv, "load_dotenv", forbidden)
    monkeypatch.setattr(environment, "load_dotenv", forbidden)
    namespace = runpy.run_path(environment.__file__)
    assert namespace["REPOSITORY_ROOT"] == Path(environment.__file__).resolve().parents[3]
    for name in ("run_phase4a_news_pilot", "run_phase4c2_news_smoke", "ingest_market_data",
                 "build_full_universe", "run_real_data_pilot", "diagnose_provider_symbol"):
        importlib.reload(importlib.import_module("scripts." + name))
    assert load_settings("config").prediction_horizon_days == 10
    assert load_news_settings("config").provider.name == "finnhub"


def test_loader_error_has_no_secret_or_exception_context(monkeypatch, capsys, caplog):
    def failure(**kwargs):
        raise ValueError("synthetic-private-key")
    monkeypatch.setattr(environment, "load_dotenv", failure)
    with pytest.raises(environment.EnvironmentBootstrapError) as captured:
        environment.load_repository_environment(real_operation_authorized=True)
    error = captured.value
    assert error.__context__ is None and error.__cause__ is None
    assert "synthetic-private-key" not in str(error)
    assert not capsys.readouterr().out and "synthetic-private-key" not in caplog.text


def test_dotenv_symlink_is_rejected_before_loading(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == tmp_path / ".env" or original(path))
    def forbidden(**kwargs):
        pytest.fail("must not read a redirected dotenv")
    monkeypatch.setattr(environment, "load_dotenv", forbidden)
    with pytest.raises(environment.EnvironmentBootstrapError, match="load_failed"):
        environment.load_repository_environment(real_operation_authorized=True)


def test_cli_errors_logs_and_provider_reports_are_secret_safe(monkeypatch, capsys):
    from investment_system.data.full_universe import _safe_error
    monkeypatch.setenv("TIINGO_API_KEY", "synthetic-private-key")
    @environment.safe_cli_errors
    def failed_cli():
        raise RuntimeError("request failed: synthetic-private-key")
    assert failed_cli() == 2
    assert "synthetic-private-key" not in capsys.readouterr().out
    assert "synthetic-private-key" not in _safe_error(RuntimeError("synthetic-private-key"))
    record = logging.LogRecord("offline", logging.ERROR, "", 1,
        "key=%s", ("synthetic-private-key",), None)
    output = JsonFormatter().format(record)
    assert "synthetic-private-key" not in output and "[REDACTED]" in output


@pytest.mark.parametrize("name, args", [
    ("run_phase4a_news_pilot", []),
    ("ingest_market_data", ["--ticker", "AAPL", "--start", "2020-01-01"]),
    ("build_full_universe", []),
    ("run_real_data_pilot", []),
    ("diagnose_provider_symbol", ["AAPL"]),
    ("run_phase4c2_news_smoke", ["--config", "absent.yaml", "--model", "test",
        "--budget-usd", "0.05", "--revision-id", "0"*64, "--as-of", "2026-10-12T13:17:53Z"]),
])
def test_all_external_cli_require_confirmation_before_bootstrap(name, args, monkeypatch, capsys):
    cli = importlib.import_module("scripts." + name)
    monkeypatch.setenv("TIINGO_API_KEY", "synthetic-private-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "synthetic-private-key")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-private-key")
    def forbidden(*a, **k):
        pytest.fail("must not read dotenv or initialize a provider without confirmation")
    monkeypatch.setattr(environment, "load_dotenv", forbidden)
    for provider in ("FinnhubNewsProvider", "TiingoEODDataSource", "OpenAIClient"):
        if hasattr(cli, provider):
            monkeypatch.setattr(cli, provider, forbidden)
    monkeypatch.setattr("sys.argv", [name, *args])
    assert cli.main() == 2
    assert "synthetic-private-key" not in capsys.readouterr().out


@pytest.mark.parametrize("name, args", [
    ("ingest_market_data", ["--ticker", "AAPL", "--start", "2020-01-01", "--dry-run"]),
    ("build_full_universe", ["--skip-download"]),
    ("run_real_data_pilot", ["--skip-download"]),
])
def test_offline_modes_skip_bootstrap_even_with_confirmation(name, args, monkeypatch):
    cli = importlib.import_module("scripts." + name)
    reached = []
    def forbidden(**kwargs):
        pytest.fail("offline mode must not bootstrap credentials")
    def stop_after_guard():
        reached.append(True)
        raise ValueError("offline stop before constructing workflows")
    monkeypatch.setattr(cli, "load_repository_environment", forbidden)
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "load_settings", stop_after_guard)
    monkeypatch.setattr("sys.argv", [name, *args, "--confirm-real-requests"])
    assert cli.main() == 2 and reached


def test_authorized_smoke_loads_only_synthetic_key_without_provider(tmp_path, monkeypatch, capsys):
    from scripts import run_phase4c2_news_smoke as cli
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=synthetic-private-key\n", encoding="utf-8")
    def forbidden(*args, **kwargs):
        pytest.fail("provider must not be constructed")
    monkeypatch.setattr(cli, "OpenAIClient", forbidden)
    monkeypatch.setattr("sys.argv", ["smoke", "--config", str(tmp_path / "missing.yaml"),
        "--model", "test", "--budget-usd", "0.05", "--revision-id", "0"*64,
        "--as-of", "2026-10-12T13:17:53Z", "--confirm-real-inference"])
    assert cli.main() == 2
    assert environment.os.getenv("OPENAI_API_KEY") == "synthetic-private-key"
    result = capsys.readouterr().out
    assert "synthetic-private-key" not in result
    assert json.loads(result)["provider_calls"] == 0
