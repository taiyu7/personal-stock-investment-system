from __future__ import annotations

import streamlit as st

from components.market_cards import render_snapshot_card
from personal_stock_investment_system.config.watchlist import DEFAULT_INTERVAL, DEFAULT_PERIOD, MARKET_SECTIONS
from personal_stock_investment_system.market_data.provider import YFinanceProvider
from personal_stock_investment_system.market_data.service import MarketReport, MarketSummaryService


PERIOD_OPTIONS = ["1mo", "3mo", "6mo", "1y", "2y"]
INTERVAL_OPTIONS = ["1d", "1wk", "1mo"]


@st.cache_data(ttl=900, show_spinner=False)
def load_market_report(period: str, interval: str) -> MarketReport:
    return MarketSummaryService(YFinanceProvider()).build(MARKET_SECTIONS, period, interval)


def render_dashboard_page() -> None:
    st.title("市場交易儀表板")
    st.caption("以台股為核心，搭配國際市場、AI 半導體與總經資料作為盤前參考。")
    period_column, interval_column, refresh_column = st.columns([0.24, 0.24, 0.52], vertical_alignment="bottom")
    with period_column:
        period = st.selectbox("歷史資料範圍", PERIOD_OPTIONS, index=PERIOD_OPTIONS.index(DEFAULT_PERIOD))
    with interval_column:
        interval = st.selectbox("資料間隔", INTERVAL_OPTIONS, index=INTERVAL_OPTIONS.index(DEFAULT_INTERVAL))
    with refresh_column:
        if st.button("重新整理資料"):
            st.cache_data.clear()
            st.rerun()

    report = load_market_report(period, interval)
    summary = report.summary
    st.markdown(f'<div class="market-summary summary-{summary.label}"><div>市場總結</div><div class="summary-title">{summary.label}</div><div class="summary-reason">{summary.reason}</div></div>', unsafe_allow_html=True)
    for section in report.sections:
        st.divider()
        title_column, signal_column = st.columns([0.8, 0.2], vertical_alignment="top")
        with title_column:
            st.subheader(section.section.title)
            st.caption(section.section.description)
        with signal_column:
            st.markdown(f'<div class="signal-pill signal-{section.signal.label}">{section.signal.label}</div>', unsafe_allow_html=True)
        st.caption(section.signal.reason)
        columns = st.columns(min(len(section.snapshots), 4))
        for index, snapshot in enumerate(section.snapshots):
            with columns[index % len(columns)]:
                render_snapshot_card(snapshot)
