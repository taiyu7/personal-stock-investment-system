"""Default market sections used by the dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchSymbol:
    ticker: str
    name: str


@dataclass(frozen=True)
class MarketSection:
    key: str
    title: str
    description: str
    symbols: tuple[WatchSymbol, ...]


DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"

MARKET_SECTIONS = (
    MarketSection("global_indices", "全球主要指數", "用美國主要股市指數觀察市場方向，以利判斷對台股的影響。", (WatchSymbol("^GSPC", "S&P 500"), WatchSymbol("^IXIC", "NASDAQ Composite"), WatchSymbol("^SOX", "PHLX Semiconductor Index"), WatchSymbol("^KS11", "KOSPI Composite"))),
    MarketSection("ai_semiconductors", "AI 半導體", "追蹤美國核心 AI 與半導體相關股票。", (WatchSymbol("NVDA", "NVIDIA"), WatchSymbol("AMD", "AMD"), WatchSymbol("AVGO", "Broadcom"), WatchSymbol("TSM", "TSMC ADR"))),
    MarketSection("macro", "美債／美元狀況", "觀察美元與美債殖利率對股市資金面的影響。", (WatchSymbol("DX-Y.NYB", "US Dollar Index"), WatchSymbol("^TNX", "US 10Y Treasury Yield"))),
    MarketSection("taiwan_market", "台灣市場", "追蹤台灣股市與重要半導體參考標的。", (WatchSymbol("^TWII", "TAIEX"), WatchSymbol("2330.TW", "TSMC Taiwan"))),
)
