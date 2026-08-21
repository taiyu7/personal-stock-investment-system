from __future__ import annotations

import streamlit as st

from components.layout import render_global_styles, render_page_header, render_sidebar
from views.changelog import render_changelog_page
from views.daily_review import render_daily_review_page
from views.dashboard import render_dashboard_page
from views.research_source_analysis import render_research_source_analysis_page
from views.trade_concept import render_stock_concept_page


APP_VERSION = "v0.10.0"
APP_LAST_UPDATED = "2026-08-22"
DEFAULT_PAGE = "市場交易儀表板"

st.set_page_config(page_title="個人股票投資系統", layout="wide")


def main() -> None:
    render_global_styles()
    current_page = st.session_state.get("current_page", DEFAULT_PAGE)
    current_page = render_sidebar(current_page)
    st.session_state.current_page = current_page
    if current_page == "市場交易儀表板":
        render_page_header(APP_VERSION, APP_LAST_UPDATED)
        render_dashboard_page()
    elif current_page == "研究來源分析":
        render_research_source_analysis_page()
    elif current_page == "每日復盤輸出":
        render_daily_review_page()
    elif current_page == "進銘的股價概念":
        render_stock_concept_page()
    else:
        render_changelog_page()


if __name__ == "__main__":
    main()
