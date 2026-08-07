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


def render_data_controls() -> tuple[str, str]:
    period_column, interval_column, refresh_column = st.columns([0.24, 0.24, 0.52], vertical_alignment="bottom")
    with period_column:
        period = st.selectbox(
            "歷史資料範圍",
            PERIOD_OPTIONS,
            index=PERIOD_OPTIONS.index(DEFAULT_PERIOD),
            format_func={"1mo": "1 個月", "3mo": "3 個月", "6mo": "6 個月", "1y": "1 年", "2y": "2 年"}.get,
        )
    with interval_column:
        interval = st.selectbox(
            "資料間隔",
            INTERVAL_OPTIONS,
            index=INTERVAL_OPTIONS.index(DEFAULT_INTERVAL),
            format_func={"1d": "每日", "1wk": "每週", "1mo": "每月"}.get,
        )
    with refresh_column:
        if st.button("重新整理資料"):
            st.cache_data.clear()
            st.rerun()
    return period, interval


def render_market_summary(report: MarketReport) -> None:
    summary = report.summary
    signal_items = "".join(
        f"<div><span>{section.section.title}</span><strong>{section.signal.label}</strong></div>"
        for section in report.sections
    )
    st.markdown(
        f'<div class="market-summary summary-{summary.label}">'
        '<div class="summary-label">市場總結</div>'
        f'<div class="summary-title">{summary.label}</div>'
        f'<div class="summary-reason">{summary.reason}</div>'
        f'<div class="summary-signals">{signal_items}</div></div>',
        unsafe_allow_html=True,
    )


def render_dashboard_page() -> None:
    period, interval = render_data_controls()
    report = load_market_report(period, interval)
    render_market_summary(report)
    st.divider()
    for section in report.sections:
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
        st.divider()
