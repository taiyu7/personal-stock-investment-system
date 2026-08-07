# 個人股票投資系統

這個 repo 是你的本機「個人股票投資系統」主線。它以台股投資工作流為核心，並保留美股、半導體與總經指標作為盤前參考。

## 目前架構

```text
                         使用者
                            │
                            ▼
          Streamlit Dashboard（盤前與盤後工作台）
                            │
                            ▼
    共用核心：市場資料 / 訊號規則 / 復盤格式 / 個人紀錄
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
    yfinance 按需行情     SQLite 本機紀錄    未來 MCP / 回測
    - 台股觀察標的        - 每日復盤        - 唯讀工具
    - 美股與總經參考      - 交易原始文字    - 指定標的回測
    - 15 分鐘快取         - 持股水位文字
```

Dashboard 只負責畫面與互動；市場資料、規則、復盤格式與 SQLite 儲存都在共用核心中。未來加入 MCP、ChatGPT、Claude、Gemini 或回測時，會直接使用同一套核心服務，不直接依賴 Dashboard。

## 長期擴充方向

```text
                ChatGPT / Claude / Gemini
                            │
                            ▼
                     AI Orchestrator
                            │
                            ▼
                           MCP
                            │
                            ▼
                    共用核心服務
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
       市場資料 provider   SQLite / 未來 DB   回測引擎
```

## 目前功能

- `apps/dashboard/`：Streamlit 盤前與盤後工作台。
- Dashboard 保留市場摘要、五日行情與月線、每日復盤、交易觀念及開發歷程頁。
- `src/personal_stock_investment_system/`：可供 Dashboard、未來 MCP 與回測共用的核心邏輯。
- SQLite：保存每日復盤與原始交易／持倉文字，不保存全台股行情。
- yfinance：依觀察清單或回測標的按需下載歷史行情。

舊 AutoDashboard 的原始 README、PROJECT、TODO、DECISIONS 與 requirements 已封存在 `docs/legacy/autodashboard/`。該目錄只供追溯舊設計；目前架構仍以本 README、`docs/architecture/` 與現有程式碼為準。

## 在 VS Code Terminal 啟動 Dashboard

第一次在這台電腦啟動時，建立環境並安裝套件：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

之後每次啟動只需要：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
.\.venv\Scripts\Activate.ps1
python -m streamlit run apps\dashboard\app.py
```

啟動後在瀏覽器開啟 `http://localhost:8501`。首次儲存每日復盤時，系統會在 `data/local/` 建立 SQLite 資料庫；此檔案只留在本機，不會提交 Git。

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
4. 建立第一個 MCP server，提供市場摘要與每日復盤的唯讀查詢。
5. 建立第一個指定標的的簡單回測策略，例如均線或突破策略。
