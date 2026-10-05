from investment_system.data.universe import load_universe

def test_development_universe_is_coherent_and_warns_about_bias() -> None:
    universe = load_universe()
    assert universe.benchmark == "SPY"
    assert 90 <= len(universe.tickers) <= 110
    assert len(universe.tickers) == len(set(universe.tickers))
    assert not universe.universe.point_in_time
    assert universe.universe.survivorship_bias_warning
