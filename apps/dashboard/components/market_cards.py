from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from personal_stock_investment_system.market_data.service import QuoteSnapshot


def format_number(value: float | None, digits: int = 2) -> str:
    return "N/A" if value is None or pd.isna(value) else f"{value:,.{digits}f}"


def _recent_rows(history: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close"]
    if history.empty or any(column not in history for column in required):
        return pd.DataFrame()
    rows = history.copy()
    rows["月線"] = rows["Close"].rolling(window=20, min_periods=1).mean()
    rows = rows.dropna(subset=required).tail(days).copy()
    if rows.empty:
        return pd.DataFrame()
    rows["日期"] = rows.index.strftime("%Y-%m-%d") if isinstance(rows.index, pd.DatetimeIndex) else rows.index.astype(str)
    for source, target in (("Open", "開盤價"), ("High", "最高價"), ("Low", "最低價"), ("Close", "收盤價")):
        rows[target] = rows[source].astype(float)
    rows["漲跌"] = rows["收盤價"] - rows["開盤價"]
    rows["漲跌幅"] = rows["漲跌"] / rows["開盤價"] * 100
    return rows


def _render_candlestick(rows: pd.DataFrame) -> None:
    base = alt.Chart(rows).encode(x=alt.X("日期:N", sort=None, axis=alt.Axis(title=None, labelAngle=0)), color=alt.condition("datum['收盤價'] >= datum['開盤價']", alt.value("#ef4444"), alt.value("#22c55e")))
    wick = base.mark_rule().encode(y=alt.Y("最低價:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=None)), y2="最高價:Q")
    body = base.mark_bar(size=28).encode(y="開盤價:Q", y2="收盤價:Q")
    average = alt.Chart(rows).mark_line(color="#2563eb", point=True, strokeWidth=2).encode(x=alt.X("日期:N", sort=None), y=alt.Y("月線:Q", scale=alt.Scale(zero=False), axis=alt.Axis(title=None)))
    st.altair_chart((wick + body + average).properties(height=180), use_container_width=True)


def render_snapshot_card(snapshot: QuoteSnapshot) -> None:
    delta = None if snapshot.change is None or snapshot.change_percent is None else f"{snapshot.change:+,.2f} ({snapshot.change_percent:+.2f}%)"
    st.metric(f"{snapshot.name} ({snapshot.ticker})", format_number(snapshot.price), delta=delta, delta_color="inverse")
    if snapshot.error:
        st.caption(f"資料狀態：{snapshot.error}")
        return
    if snapshot.fetched_at:
        st.caption(f"來源：{snapshot.source}，更新：{snapshot.fetched_at}")
    rows = _recent_rows(snapshot.history)
    if not rows.empty:
        st.dataframe(rows[["日期", "收盤價", "月線", "漲跌", "漲跌幅"]], hide_index=True, use_container_width=True, height=210)
        _render_candlestick(rows)
