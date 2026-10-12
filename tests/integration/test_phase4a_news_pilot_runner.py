from scripts.run_phase4a_news_pilot import load_finnhub_api_key


def test_runner_loads_finnhub_key_from_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    (tmp_path / ".env").write_text("FINNHUB_API_KEY=dotenv-test-value\n", encoding="utf-8")

    assert load_finnhub_api_key(tmp_path / ".env") == "dotenv-test-value"


def test_system_environment_takes_precedence_over_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FINNHUB_API_KEY", "system-test-value")
    (tmp_path / ".env").write_text("FINNHUB_API_KEY=dotenv-test-value\n", encoding="utf-8")

    assert load_finnhub_api_key(tmp_path / ".env") == "system-test-value"
