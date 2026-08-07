from __future__ import annotations

import streamlit as st


def render_global_styles() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div.stButton > button { border: 0; border-radius: 6px; color: #334155; font-weight: 600; justify-content: flex-start; text-align: left; }
        section[data-testid="stSidebar"] div.stButton > button:hover { background: #e0f2fe; color: #0369a1; }
        .market-summary { border-left: 5px solid #94a3b8; border-radius: 8px; margin: 1rem 0 1.5rem; padding: 1rem 1.15rem; }
        .summary-偏多 { background: #fef2f2; border-left-color: #ef4444; }
        .summary-中性 { background: #f8fafc; border-left-color: #64748b; }
        .summary-偏空 { background: #f0fdf4; border-left-color: #22c55e; }
        .summary-title { color: #0f172a; font-size: 1.65rem; font-weight: 800; }
        .summary-reason { color: #334155; line-height: 1.7; margin-top: 0.35rem; }
        .signal-pill { border-radius: 999px; font-weight: 800; margin-top: 0.55rem; padding: 0.38rem 0.75rem; text-align: center; width: fit-content; }
        .signal-偏多 { background: #fee2e2; color: #b91c1c; }.signal-中性 { background: #e2e8f0; color: #334155; }.signal-偏空 { background: #dcfce7; color: #15803d; }
        .trade-concept-table { border-collapse: collapse; margin: .75rem 0 1.25rem; table-layout: fixed; width: 100%; }
        .trade-concept-table th,.trade-concept-table td { border: 1px solid #cbd5e1; color: #334155; line-height: 1.65; padding: .7rem .8rem; vertical-align: top; word-break: break-word; }
        .trade-concept-table th { background: #f8fafc; color: #0f172a; }.trade-concept-table th:first-child,.trade-concept-table td:first-child { font-weight: 700; width: 18%; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(current_page: str) -> str:
    selected_page = current_page
    with st.sidebar:
        for page in ("市場交易儀表板", "每日復盤輸出", "交易觀念"):
            if st.button(page, use_container_width=True):
                selected_page = page
    return selected_page
