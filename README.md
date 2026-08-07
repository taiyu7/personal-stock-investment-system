# 個人股票投資系統

這個 repo 是你的本機「個人股票投資系統」主線。它以台股投資工作流為核心，並保留美股、半導體與總經指標作為盤前參考。

## 目標架構

```text
                    使用者
                      │
                      ▼
              AI Orchestrator
               /      |      \
              /       |       \
             ▼        ▼        ▼
         ChatGPT    Claude    Gemini
             │        │        │
             └────────┼────────┘
                      │
                      ▼
                     MCP
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
        股票 DB     市場資料      回測
```

## 目前功能

- `apps/dashboard/`：Streamlit 盤前與盤後工作台。
- `src/personal_stock_investment_system/`：可供 Dashboard、未來 MCP 與回測共用的核心邏輯。
- SQLite：保存每日復盤與原始交易／持倉文字，不保存全台股行情。
- yfinance：依觀察清單或回測標的按需下載歷史行情。

## 啟動 Dashboard

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m streamlit run apps\dashboard\app.py
```

首次儲存每日復盤時，系統會在 `data/local/` 建立 SQLite 資料庫。此檔案只留在本機，不會提交 Git。

## 暫不實作的內容

- 實際串接券商 API
- 自動下單
- 真實資金交易
- 完整資料庫 schema
- 完整回測引擎

## 建議下一步

1. 驗證 yfinance 對所需台股與指標的資料完整性。
2. 新增台股專用資料來源，例如 TWSE、TPEx 或 FinMind。
3. 建立第一個 MCP server，先只提供唯讀查詢工具。
4. 建立股票基本資料與日線資料的最小資料表。
5. 建立第一個簡單回測策略，例如均線或突破策略。
