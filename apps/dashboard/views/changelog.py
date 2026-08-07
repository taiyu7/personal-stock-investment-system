from __future__ import annotations

import streamlit as st


FEATURE_LOG = [
    {
        "version": "v0.7.0",
        "title": "整合至個人股票投資系統",
        "items": [
            "將 Dashboard 遷入 personal-stock-investment-system 主線。",
            "拆分可供 Dashboard、未來 MCP 與回測共用的市場資料與訊號服務。",
            "每日復盤新增本機 SQLite 儲存與載入功能。",
        ],
    },
    {
        "version": "v0.6.0",
        "title": "每日復盤輸出",
        "items": ["新增每日復盤輸出頁。", "依照既有 Word 紀錄拆成盤前功課與盤後復盤欄位。", "自動帶入市場資料摘要，並產生可貼到 Google Docs 的內容。"],
    },
    {
        "version": "v0.5.0",
        "title": "股價概念頁",
        "items": ["新增進銘的股價概念頁。", "股價概念頁改為文字與量價位關係表格。", "將全域頁首限制在市場交易儀表板頁面顯示。"],
    },
    {
        "version": "v0.4.0",
        "title": "近期資料與月線",
        "items": ["將近期交易資料由 3 筆改為 5 筆。", "在 K 線圖加入月線作為趨勢參考。", "暫緩台指期夜盤資料串接，避免目前版本引入爬蟲複雜度。"],
    },
    {
        "version": "v0.3.0",
        "title": "市場總結與區塊判斷",
        "items": ["新增市場總結區塊，彙整各市場區塊方向。", "為每個市場區塊加入偏多 / 中性 / 偏空判斷。", "將判斷規則拆到服務層，方便後續調整權重。"],
    },
    {
        "version": "v0.2.0",
        "title": "版面導覽與功能紀錄",
        "items": ["將歷史資料範圍與資料間隔移到主標題下方。", "新增右上角版本號與程式上次更新日期。", "將側邊欄改為頁面切換，並新增開發歷程頁。"],
    },
    {
        "version": "v0.1.0",
        "title": "市場交易儀表板初版",
        "items": ["建立市場指數、AI 半導體、總體經濟與台灣市場區塊。", "加入近期交易資料表與 K 線圖。", "使用 yfinance 擷取並快取市場資料。"],
    },
]


def render_changelog_page() -> None:
    st.subheader("開發歷程")
    st.caption("用版本節點追蹤儀表板陸續加入的功能。")
    entries = []
    for entry in FEATURE_LOG:
        items = "".join(f"<li>{item}</li>" for item in entry["items"])
        entries.append('<div class="feature-entry"><div class="feature-node"></div>' f'<div class="feature-version">{entry["version"]}</div>' f'<div class="feature-title">{entry["title"]}</div>' f'<ul class="feature-items">{items}</ul></div>')
    st.markdown(f'<div class="feature-log">{"".join(entries)}</div>', unsafe_allow_html=True)
