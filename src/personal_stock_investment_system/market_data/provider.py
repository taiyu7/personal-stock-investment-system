"""Provider boundary for retrieving historical market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class HistoryResult:
    ticker: str
    history: pd.DataFrame
    source: str
    fetched_at: datetime


class MarketDataProvider(Protocol):
    def fetch_history(self, symbol: str, period: str = "6mo", interval: str = "1d") -> HistoryResult:
        """Return normalized OHLCV history and source metadata."""


class YFinanceProvider:
    source_name = "yfinance"

    def fetch_history(self, symbol: str, period: str = "6mo", interval: str = "1d") -> HistoryResult:
        data = yf.download(tickers=symbol, period=period, interval=interval, progress=False, auto_adjust=False, threads=False)
        return HistoryResult(symbol, self._normalize_history(data), self.source_name, datetime.now(timezone.utc))

    @staticmethod
    def _normalize_history(data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return pd.DataFrame()
        normalized = data.copy()
        if isinstance(normalized.columns, pd.MultiIndex):
            normalized.columns = normalized.columns.get_level_values(0)
        return normalized.dropna(how="all")
