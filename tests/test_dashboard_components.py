import pandas as pd

from apps.dashboard.components.layout import SIDEBAR_PAGES
from apps.dashboard.components.market_cards import get_recent_trading_rows
from apps.dashboard.views.research_source_analysis import ANALYSIS_PROVIDER_OPTIONS, INPUT_KIND_OPTIONS


def test_recent_rows_calculates_change_from_previous_close():
    dates = pd.date_range("2026-08-01", periods=6, freq="D")
    history = pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104, 105],
            "High": [102, 103, 104, 105, 106, 108],
            "Low": [99, 100, 101, 102, 103, 104],
            "Close": [101, 102, 103, 104, 105, 107],
        },
        index=dates,
    )

    rows = get_recent_trading_rows(history)

    assert len(rows) == 5
    assert rows.iloc[-1]["相對前日漲跌"] == 2
    assert rows.iloc[-1]["相對前日漲跌幅"] == 2 / 105 * 100


def test_recent_rows_returns_empty_when_required_price_columns_are_missing():
    history = pd.DataFrame({"Close": [100.0, 101.0]})

    rows = get_recent_trading_rows(history)

    assert rows.empty


def test_research_source_analysis_is_available_from_sidebar_navigation():
    assert "研究來源分析" in SIDEBAR_PAGES
    assert SIDEBAR_PAGES.index("研究來源分析") == 1


def test_research_source_analysis_supports_transcript_json_and_provider_choice():
    assert INPUT_KIND_OPTIONS["ASR 逐字稿 JSON"] == "asr_transcript_json"
    assert ANALYSIS_PROVIDER_OPTIONS["本機規則 fallback"] == "rule_based_fallback"
    assert ANALYSIS_PROVIDER_OPTIONS["OpenAI（尚未接 API）"] == "openai"
    assert ANALYSIS_PROVIDER_OPTIONS["Claude（尚未接 API）"] == "anthropic_claude"
