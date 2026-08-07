from __future__ import annotations

import streamlit as st

from components.layout import render_global_styles, render_sidebar
from views.daily_review import render_daily_review_page
from views.dashboard import render_dashboard_page
from views.trade_concept import render_trade_concept_page


st.set_page_config(page_title="個人股票投資系統", layout="wide")


def main() -> None:
    render_global_styles()
    current_page = st.session_state.get("current_page", "市場交易儀表板")
    current_page = render_sidebar(current_page)
    st.session_state.current_page = current_page
    if current_page == "市場交易儀表板":
        render_dashboard_page()
    elif current_page == "每日復盤輸出":
        render_daily_review_page()
    else:
        render_trade_concept_page()


if __name__ == "__main__":
    main()
