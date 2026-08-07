from datetime import datetime, timezone

import pandas as pd

from personal_stock_investment_system.config.watchlist import MarketSection, WatchSymbol
from personal_stock_investment_system.market_data.provider import HistoryResult, YFinanceProvider
from personal_stock_investment_system.market_data.service import MarketSummaryService


def test_yfinance_provider_flattens_multiindex(monkeypatch):
    columns = pd.MultiIndex.from_tuples([("Open", "2330.TW"), ("Close", "2330.TW")])
    downloaded = pd.DataFrame([[100.0, 101.0]], columns=columns)
    monkeypatch.setattr("personal_stock_investment_system.market_data.provider.yf.download", lambda **_: downloaded)
    result = YFinanceProvider().fetch_history("2330.TW")
    assert list(result.history.columns) == ["Open", "Close"]
    assert result.source == "yfinance"


class FakeProvider:
    def fetch_history(self, symbol: str, period: str = "6mo", interval: str = "1d") -> HistoryResult:
        close = [100.0, 101.0] if symbol == "GOOD" else [100.0, 99.0]
        history = pd.DataFrame({"Close": close})
        return HistoryResult(symbol, history, "fake", datetime.now(timezone.utc))


def test_market_summary_service_builds_section_signal():
    section = MarketSection("taiwan_market", "台灣市場", "test", (WatchSymbol("GOOD", "Good"), WatchSymbol("BAD", "Bad")))
    report = MarketSummaryService(FakeProvider()).build((section,))
    assert report.sections[0].signal.valid_count == 2
    assert report.summary.label == "中性"
