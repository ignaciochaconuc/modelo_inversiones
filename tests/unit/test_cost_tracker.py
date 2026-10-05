from datetime import datetime, timezone
import pytest
from investment_system.llm.cost_tracker import CostTracker, LLMCallRecord
from investment_system.llm.pricing import PricingRegistry, TokenPrice

def make_record() -> LLMCallRecord:
    return LLMCallRecord(timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc), provider="test", model="m", agent="news", task="classify", ticker="AAPL", analysis_id="a1", trade_id="t1", input_tokens=100, cached_input_tokens=20, output_tokens=50, total_tokens=150, estimated_cost_usd=0.25, latency_ms=10, success=True)

def test_cost_aggregations() -> None:
    tracker = CostTracker(); tracker.add(make_record())
    assert tracker.by_agent("news") == tracker.by_ticker("AAPL") == 0.25
    assert tracker.daily(datetime(2025, 1, 2).date()) == 0.25
    assert tracker.monthly(2025, 1) == 0.25
    assert tracker.by_analysis("a1") == tracker.by_trade("t1") == 0.25

def test_configurable_pricing() -> None:
    registry = PricingRegistry({("test", "m"): TokenPrice(1, 0.5, 2)})
    assert registry.estimate("test", "m", 100, 20, 50) == pytest.approx((80 + 10 + 100) / 1_000_000)
