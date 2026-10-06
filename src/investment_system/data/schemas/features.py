from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

IDENTIFIER_COLUMNS = ("ticker", "decision_date", "decision_time", "sector", "industry", "market_cap")
FEATURE_COLUMNS = (
    "split_adjusted_open split_adjusted_high split_adjusted_low split_adjusted_close split_adjusted_volume return_1d return_2d return_5d return_10d return_20d return_60d "
    "gap_open intraday_return overnight_return momentum_5d momentum_10d momentum_20d momentum_60d momentum_120d "
    "relative_momentum_spy_5d relative_momentum_spy_20d relative_momentum_spy_60d volatility_5d volatility_10d "
    "volatility_20d volatility_60d downside_volatility atr_14 beta_20d beta_60d max_drawdown_20d max_drawdown_60d "
    "rsi_14 atr_pct macd macd_signal macd_histogram macd_pct macd_signal_pct macd_histogram_pct distance_ma10 distance_ma20 distance_ma50 distance_ma200 "
    "volume_ratio_5d volume_ratio_20d volume_change_1d avg_dollar_volume_20d avg_dollar_volume_60d distance_52w_high "
    "distance_52w_low percentile_price_252d percentile_volume_252d percentile_volatility_252d spy_return_1d spy_return_5d "
    "spy_return_20d excess_return_5d excess_return_20d correlation_spy_20d correlation_spy_60d sector_return_5d "
    "sector_return_20d relative_sector_return_20d news_score news_impact news_novelty news_confidence news_count_24h "
    "news_count_7d positive_news_count negative_news_count high_impact_news_count news_event_regulation news_event_product "
    "news_event_legal news_event_management news_event_ma analyst_score analyst_confidence consensus_buy_ratio consensus_hold_ratio "
    "consensus_sell_ratio target_price_upside target_price_change_30d eps_revision_7d eps_revision_30d revenue_revision_30d "
    "analyst_dispersion consensus_change days_to_earnings expected_eps_growth expected_revenue_growth eps_revision_pre_earnings "
    "revenue_revision_pre_earnings historical_eps_surprise_mean historical_revenue_surprise_mean eps_surprise_probability "
    "revenue_surprise_probability expectation_level guidance_risk event_risk earnings_confidence eps_surprise revenue_surprise "
    "guidance_surprise margin_surprise management_sentiment post_earnings_score earnings_pre_event earnings_post_event "
    "revenue_growth_yoy eps_growth_yoy fcf_growth_yoy gross_margin operating_margin net_margin roe roic debt_to_equity "
    "net_debt_to_ebitda pe_ratio forward_pe price_to_sales ev_to_ebitda gross_margin_change_yoy operating_margin_change_yoy "
    "debt_change_yoy growth_score profitability_score balance_sheet_score valuation_score fundamental_momentum fundamental_score "
    "fed_funds_rate treasury_2y treasury_10y yield_curve_10y2y inflation_yoy unemployment_rate vix dxy_change oil_change "
    "macro_growth_score macro_inflation_score macro_rates_score macro_liquidity_score macro_risk_score days_to_major_event "
    "major_event_impact major_event_uncertainty event_confidence event_fed event_cpi event_fda event_court event_product event_investor_day"
).split()
CATEGORICAL_FEATURE_COLUMNS = ("market_regime", "growth_regime", "inflation_regime", "rates_regime")
TARGET_COLUMNS = ("target_return_5d", "target_return_10d", "target_return_20d", "target_positive_10d", "target_rank_10d")
BOOLEAN_COLUMNS = {
    "news_event_regulation", "news_event_product", "news_event_legal", "news_event_management", "news_event_ma",
    "earnings_pre_event", "earnings_post_event", "event_fed", "event_cpi", "event_fda", "event_court", "event_product", "event_investor_day",
}

QUANTITATIVE_FEATURE_COLUMNS = tuple(
    "split_adjusted_open split_adjusted_high split_adjusted_low split_adjusted_close split_adjusted_volume "
    "return_1d return_2d return_5d return_10d return_20d return_60d momentum_5d momentum_10d momentum_20d momentum_60d momentum_120d "
    "volatility_5d volatility_10d volatility_20d volatility_60d downside_volatility gap_open intraday_return overnight_return "
    "rsi_14 atr_14 atr_pct macd macd_signal macd_histogram macd_pct macd_signal_pct macd_histogram_pct "
    "distance_ma10 distance_ma20 distance_ma50 distance_ma200 volume_ratio_5d volume_ratio_20d volume_change_1d "
    "avg_dollar_volume_20d avg_dollar_volume_60d max_drawdown_20d max_drawdown_60d distance_52w_high distance_52w_low "
    "percentile_price_252d percentile_volume_252d percentile_volatility_252d spy_return_1d spy_return_5d spy_return_20d "
    "excess_return_5d excess_return_20d relative_momentum_spy_5d relative_momentum_spy_20d relative_momentum_spy_60d "
    "correlation_spy_20d correlation_spy_60d beta_20d beta_60d sector_return_5d sector_return_20d relative_sector_return_20d".split()
)

class _FeatureRowBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1)
    decision_date: date
    decision_time: datetime
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = Field(default=None, ge=0)
    history_count: int = Field(default=0, ge=0)
    has_20d_history: bool = False
    has_60d_history: bool = False
    has_120d_history: bool = False
    has_252d_history: bool = False
    model_eligible: bool = False
    feature_corporate_action_contaminated: bool = False
    corporate_action_reason: str | None = None
    corporate_action_event_id: str | None = None

    @field_validator("decision_time")
    @classmethod
    def decision_time_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decision_time must be timezone-aware")
        return value

    def model_features(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in (*FEATURE_COLUMNS, *CATEGORICAL_FEATURE_COLUMNS)}

_fields: dict[str, tuple[Any, Any]] = {}
for _name in FEATURE_COLUMNS:
    _fields[_name] = ((bool | None) if _name in BOOLEAN_COLUMNS else (float | None), None)
for _name in CATEGORICAL_FEATURE_COLUMNS:
    _fields[_name] = (str | None, None)
for _name in TARGET_COLUMNS:
    _fields[_name] = ((int | None) if _name == "target_positive_10d" else (float | None), None)

FeatureRow = create_model("FeatureRow", __base__=_FeatureRowBase, **_fields)
