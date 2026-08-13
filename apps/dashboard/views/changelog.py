from __future__ import annotations

import streamlit as st


FEATURE_LOG = [
    {
        "version": "v0.9.0",
        "title": "第一階段研究來源分析工具",
        "items": [
            "新增左側 sidebar 的研究來源分析入口，支援手動文字、PDF 路徑與公開 YouTube URL fallback。",
            "建立研究來源資料模型、固定 Markdown 報告、rule-based 股票觀點分析與輸出目的地設定。",
            "目前 YouTube 只提供 URL 解析與 transcript_unavailable fallback，尚未接真實 CC 字幕 adapter。",
        ],
    },
    {
        "version": "v0.8.0",
        "title": "可重現開發環境與文件治理",
        "items": [
            "固定 GitHub Actions runner、Python、action SHA、Docker base image digest 與 Python lock file，降低 CI 結果漂移。",
            "補完整系統架構文件與資料庫 schema / migration 策略，明確區分現行功能與未來目標。",
            "建立 Docker 優先驗證習慣：一般程式、UI、測試或文件變更不重建 image，只有依賴或 Docker 設定變更才 rebuild。",
            "新增本機 .env 作為執行設定入口，並移除主 repo .venv，後續預設以 Docker 驗證。",
            "調整近期優先順序：先整理目前 Obsidian vault 架構，再補 Dashboard smoke test 與研究工具。",
        ],
    },
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
