"""Shared market summary service for the dashboard and future MCP tools."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from personal_stock_investment_system.config.watchlist import MarketSection, WatchSymbol
from personal_stock_investment_system.market_data.provider import HistoryResult, MarketDataProvider
from personal_stock_investment_system.signals.rules import MarketSummary, SectionSignal, build_market_summary, build_section_signal


@dataclass(frozen=True)
class QuoteSnapshot:
    ticker: str
    name: str
    price: float | None
    change: float | None
    change_percent: float | None
    history: pd.DataFrame
    source: str | None
    fetched_at: str | None
    error: str | None = None


@dataclass(frozen=True)
class SectionReport:
    section: MarketSection
    snapshots: list[QuoteSnapshot]
    signal: SectionSignal


@dataclass(frozen=True)
class MarketReport:
    sections: list[SectionReport]
    summary: MarketSummary


class MarketSummaryService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def build(self, watchlist: tuple[MarketSection, ...], period: str = "6mo", interval: str = "1d") -> MarketReport:
        sections = [self.build_section(section, period, interval) for section in watchlist]
        return MarketReport(sections, build_market_summary([section.signal for section in sections]))

    def build_section(self, section: MarketSection, period: str = "6mo", interval: str = "1d") -> SectionReport:
        snapshots = [self.build_snapshot(symbol, period, interval) for symbol in section.symbols]
        return SectionReport(section, snapshots, build_section_signal(section.key, snapshots))

    def build_snapshot(self, symbol: WatchSymbol, period: str, interval: str) -> QuoteSnapshot:
        try:
            result = self.provider.fetch_history(symbol.ticker, period, interval)
        except Exception as exc:
            return QuoteSnapshot(symbol.ticker, symbol.name, None, None, None, pd.DataFrame(), None, None, str(exc))
        return self._snapshot_from_history(symbol, result)

    @staticmethod
    def _snapshot_from_history(symbol: WatchSymbol, result: HistoryResult) -> QuoteSnapshot:
        history = result.history
        fetched_at = result.fetched_at.astimezone().strftime("%Y-%m-%d %H:%M")
        if history.empty or "Close" not in history:
            return QuoteSnapshot(symbol.ticker, symbol.name, None, None, None, history, result.source, fetched_at, "沒有取得資料")
        close = history["Close"].dropna()
        if close.empty:
            return QuoteSnapshot(symbol.ticker, symbol.name, None, None, None, history, result.source, fetched_at, "沒有收盤價資料")
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) > 1 else latest
        change = latest - previous
        return QuoteSnapshot(symbol.ticker, symbol.name, latest, change, (change / previous * 100) if previous else 0.0, history, result.source, fetched_at)
