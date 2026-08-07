from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import streamlit as st

from personal_stock_investment_system.config.watchlist import MARKET_SECTIONS
from personal_stock_investment_system.market_data.provider import YFinanceProvider
from personal_stock_investment_system.market_data.service import MarketSummaryService
from personal_stock_investment_system.reviews import build_daily_review_text, build_market_note
from personal_stock_investment_system.storage.daily_reviews import DailyReview, DailyReviewRepository


FIELD_SPECS = (
    ("market_note", "前日市場資料", "area", 260),
    ("premarket_news", "重大新聞／財報／法說／政策題材", "area", 110),
    ("holding_analysis", "持股狀況分析", "area", 140),
    ("holding_level_before", "盤前持股水位", "input", 0),
    ("yesterday_groups", "昨日主流族群", "area", 90),
    ("market_status", "市場狀態（開高走低／開高走高／開平走低／開低走高／開低走低）", "area", 140),
    ("strong_groups", "今日強勢族群", "area", 100),
    ("plan_match", "是否符合盤前劇本", "input", 0),
    ("trade_records", "今日交易紀錄（股票／進出場／結果）", "area", 140),
    ("holding_level_after", "盤後持股水位", "input", 0),
    ("good_actions", "做對的事", "area", 90),
    ("mistakes", "犯的錯", "area", 90),
    ("emotion_notes", "情緒狀態與備註", "area", 120),
)


def _database_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    default = "sqlite:///data/local/personal-stock-investment.db"
    database_url = os.getenv("DATABASE_URL", default)
    if not database_url.startswith("sqlite:///"):
        raise ValueError("目前 Dashboard 只支援 SQLite。請使用 sqlite:///data/local/personal-stock-investment.db")
    return root / database_url.removeprefix("sqlite:///")


@st.cache_data(ttl=900, show_spinner=False)
def _market_note() -> str:
    report = MarketSummaryService(YFinanceProvider()).build(MARKET_SECTIONS)
    return build_market_note(report)


def _set_fields(fields: dict[str, str]) -> None:
    for key, _, _, _ in FIELD_SPECS:
        st.session_state[f"review_{key}"] = fields.get(key, "")


def render_daily_review_page() -> None:
    st.subheader("每日復盤輸出")
    st.caption("儲存盤前與盤後紀錄到本機 SQLite，並保留可下載的 Markdown。")
    selected_date = st.date_input("交易日期", value=date.today()).strftime("%Y/%m/%d")
    repository = DailyReviewRepository(_database_path())
    actions = st.columns(3)
    with actions[0]:
        load_clicked = st.button("載入當日紀錄")
    with actions[1]:
        regenerate_clicked = st.button("重新產生市場資料")
    with actions[2]:
        save_clicked = st.button("儲存當日紀錄", type="primary")
    if regenerate_clicked:
        st.cache_data.clear()
    if load_clicked:
        saved = repository.load(selected_date)
        if saved:
            _set_fields(saved.fields)
            st.success("已載入當日紀錄。")
        else:
            st.info("這一天尚未儲存紀錄。")
    market_key = "review_market_note"
    if market_key not in st.session_state or regenerate_clicked:
        st.session_state[market_key] = _market_note()

    fields: dict[str, str] = {}
    for index, (key, label, widget, height) in enumerate(FIELD_SPECS):
        if index == 1:
            st.markdown("### 盤前功課")
        if index == 5:
            st.markdown("### 盤後復盤")
        state_key = f"review_{key}"
        if key == "market_note" and state_key not in st.session_state:
            st.session_state[state_key] = st.session_state[market_key]
        fields[key] = st.text_input(label, key=state_key) if widget == "input" else st.text_area(label, key=state_key, height=height)
    markdown = build_daily_review_text(selected_date, fields)
    if save_clicked:
        repository.save(DailyReview(selected_date, fields, markdown))
        st.success("已儲存到本機 SQLite。")
    st.markdown("### Google Docs 內容")
    st.text_area("複製下面內容到 Google Docs", value=markdown, height=420)
    st.download_button("下載 Markdown", data=markdown.encode("utf-8"), file_name=f"{selected_date.replace('/', '')}_股票交易紀錄.md", mime="text/markdown")
