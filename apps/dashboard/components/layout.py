from __future__ import annotations

import streamlit as st

SIDEBAR_PAGES = ("市場交易儀表板", "研究來源分析", "每日復盤輸出", "進銘的股價概念", "開發歷程")


def render_global_styles() -> None:
    st.markdown(
        """
        <style>
        .app-version { color: #64748b; font-size: 0.84rem; font-weight: 500; line-height: 1.6; padding-top: 0.7rem; text-align: right; }
        .app-version strong { color: #0f172a; font-size: 0.92rem; font-weight: 700; }
        section[data-testid="stSidebar"] { background: #f8fafc; border-right: 1px solid #cbd5e1; }
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { background: #f8fafc; }
        section[data-testid="stSidebar"] div.stButton > button { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; color: #0f172a; font-size: 1rem; font-weight: 700; justify-content: flex-start; padding: 0.65rem 0.8rem; text-align: left; width: 100%; }
        section[data-testid="stSidebar"] div.stButton > button:hover { background: #dbeafe; border-color: #38bdf8; color: #075985; }
        section[data-testid="stSidebar"] div.stButton > button:focus { box-shadow: none; }
        section[data-testid="stSidebar"] div.stButton > button:focus-visible { box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.35); }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"],
        section[data-testid="stSidebar"] div.stButton > button[data-testid="stBaseButton-primary"] { background: #0f172a; border-color: #0f172a; color: #ffffff; }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover,
        section[data-testid="stSidebar"] div.stButton > button[data-testid="stBaseButton-primary"]:hover { background: #1e293b; border-color: #1e293b; color: #ffffff; }
        .feature-log { margin-top: 1.5rem; max-width: 920px; }
        .feature-entry { border-left: 2px solid #94a3b8; margin-left: 0.55rem; padding: 0 0 1.4rem 1.5rem; position: relative; }
        .feature-entry:last-child { padding-bottom: 0; }
        .feature-node { background: #0f172a; border: 3px solid #38bdf8; border-radius: 999px; height: 0.9rem; left: -0.52rem; position: absolute; top: 0.15rem; width: 0.9rem; }
        .feature-version { color: #0369a1; font-size: 0.85rem; font-weight: 700; letter-spacing: 0; margin-bottom: 0.2rem; }
        .feature-title { color: #0f172a; font-size: 1.1rem; font-weight: 700; margin-bottom: 0.35rem; }
        .feature-items { color: #334155; line-height: 1.75; margin: 0; padding-left: 1.1rem; }
        .market-summary { border-left: 5px solid #94a3b8; border-radius: 8px; margin: 1rem 0 1.5rem; padding: 1rem 1.15rem; }
        .summary-偏多 { background: #fef2f2; border-left-color: #ef4444; }
        .summary-中性 { background: #f8fafc; border-left-color: #64748b; }
        .summary-偏空 { background: #f0fdf4; border-left-color: #22c55e; }
        .summary-label { color: #64748b; font-size: 0.85rem; font-weight: 700; margin-bottom: 0.15rem; }
        .summary-title { color: #0f172a; font-size: 1.65rem; font-weight: 800; line-height: 1.25; }
        .summary-reason { color: #334155; line-height: 1.7; margin-top: 0.35rem; }
        .summary-signals { display: grid; gap: 0.45rem; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-top: 0.9rem; }
        .summary-signals div { align-items: center; background: rgba(255, 255, 255, 0.7); border: 1px solid #e2e8f0; border-radius: 6px; color: #475569; display: flex; justify-content: space-between; padding: 0.55rem 0.7rem; }
        .summary-signals strong { color: #0f172a; }
        .signal-pill { border-radius: 999px; font-size: 0.9rem; font-weight: 800; margin-top: 0.55rem; padding: 0.38rem 0.75rem; text-align: center; width: fit-content; }
        .signal-偏多 { background: #fee2e2; color: #b91c1c; }.signal-中性 { background: #e2e8f0; color: #334155; }.signal-偏空 { background: #dcfce7; color: #15803d; }
        .concept-board { border: 1px solid #e2e8f0; border-radius: 8px; margin-top: 1.25rem; padding: 1.2rem; }
        .concept-row { align-items: stretch; display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-bottom: 0.85rem; }
        .concept-node { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; color: #334155; min-height: 92px; padding: 0.85rem; }
        .concept-node strong { color: #0f172a; display: block; font-size: 1rem; margin-bottom: 0.3rem; }
        .concept-node span { display: block; font-size: 0.9rem; line-height: 1.55; }
        .concept-core { background: #ecfeff; border-color: #06b6d4; }
        .concept-price { background: #fef2f2; border-color: #ef4444; text-align: center; }
        .concept-price strong { font-size: 1.35rem; }
        .concept-arrow { color: #64748b; font-size: 1.15rem; font-weight: 800; margin: 0.25rem 0 0.75rem; text-align: center; }
        .trade-concept-table { border-collapse: collapse; margin: .75rem 0 1.25rem; table-layout: fixed; width: 100%; }
        .trade-concept-table th,.trade-concept-table td { border: 1px solid #cbd5e1; color: #334155; line-height: 1.65; padding: .7rem .8rem; vertical-align: top; white-space: normal; word-break: break-word; }
        .trade-concept-table th { background: #f8fafc; color: #0f172a; }.trade-concept-table th:first-child,.trade-concept-table td:first-child { font-weight: 700; width: 18%; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(app_version: str, last_updated: str) -> None:
    title_column, version_column = st.columns([0.82, 0.18], vertical_alignment="top")
    with title_column:
        st.title("市場交易儀表板")
        st.caption("這是一個股票資料儀表板，用來協助交易員了解近期的市場經濟訊號與台灣市場資料。")
    with version_column:
        st.markdown(
            f'<div class="app-version"><strong>{app_version}</strong><br>程式上次更新：{last_updated}</div>',
            unsafe_allow_html=True,
        )


def render_sidebar(current_page: str) -> str:
    selected_page = current_page
    with st.sidebar:
        for index, page in enumerate(SIDEBAR_PAGES):
            if st.button(
                page,
                key=f"sidebar_page_{index}",
                type="primary" if page == current_page else "secondary",
                width="stretch",
            ):
                selected_page = page
    return selected_page
