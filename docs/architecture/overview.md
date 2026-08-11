# 系統架構

本文說明目前已實作的系統邊界，以及未來 MCP、回測與 AI workflow 的目標位置。若本文與程式碼不一致，以主 Repo 的程式碼、測試與 Git 紀錄為準。

## 現行架構

```text
使用者
  │
  ▼
Streamlit Dashboard v0.7.0
  │
  ├─ 市場儀表板
  ├─ 每日復盤
  ├─ 股價概念
  └─ 開發歷程
  │
  ▼
personal_stock_investment_system 共用核心
  │
  ├─ config/watchlist.py
  ├─ market_data/provider.py
  ├─ market_data/service.py
  ├─ signals/rules.py
  ├─ reviews.py
  └─ storage/daily_reviews.py
      │
      └─ SQLite: data/local/personal-stock-investment.db
```

現行產品定位是本機優先的投資研究與復盤工作台。Dashboard 負責畫面與互動；可重用的行情、訊號、復盤文字與資料儲存邏輯都放在 `src/personal_stock_investment_system/`。

## 分層責任

### Dashboard

`apps/dashboard/` 是每天使用的盤前與盤後工作台。

- 顯示四個市場觀察區塊、整體市場摘要、五日行情與月線圖。
- 提供每日復盤表單，支援儲存、覆寫、載入與 Markdown 下載。
- 使用 Streamlit 15 分鐘記憶體快取減少重複抓取行情。
- 不直接承擔可重用商業邏輯；共用邏輯應放回核心套件。

### 共用核心

`src/personal_stock_investment_system/` 是未來 Dashboard、MCP 與回測共同使用的核心。

- `config/watchlist.py`：預設觀察清單與市場區塊。
- `market_data/provider.py`：行情來源 boundary；目前有 `YFinanceProvider`。
- `market_data/service.py`：把 watchlist 與 provider 組成市場報告。
- `signals/rules.py`：偏多／中性／偏空透明規則，macro 區塊反向計分。
- `reviews.py`：每日復盤 Markdown 與市場摘要文字。
- `storage/daily_reviews.py`：SQLite 每日復盤 repository。

新增功能時，若邏輯未來可能被 Dashboard 以外的入口使用，應優先放在共用核心。

### 市場資料

現階段行情來源是 yfinance 按需下載，不建立全台股常駐資料庫。

- 觀察清單只在 Dashboard 或服務需要時抓取。
- yfinance 回傳的 MultiIndex 欄位會在 provider 層正規化。
- provider 下載失敗時，錯誤保存在 snapshot，不讓整個 Dashboard 中止。
- 未來若加入 TWSE、TPEx 或 FinMind，應實作新的 provider，不把來源判斷散落在 UI。

### 資料庫

目前 SQLite 只保存個人每日復盤資料。

- 預設路徑：`data/local/personal-stock-investment.db`。
- `daily_reviews.trade_date` 是 primary key。
- 儲存內容包含原始表單欄位 JSON、產生的 Markdown 與更新時間。
- 自由文字交易紀錄目前不解析成結構化交易資料。

詳細 schema 與 migration 策略請見 `db/README.md`。

### 測試與 CI

目前測試涵蓋 provider、market summary service、signal rules、daily review repository 與部分 Dashboard helper。

CI 在 push 到 `main` 或建立 PR 時執行：

- Ubuntu + Python 3.11.15 安裝專案並跑 `pytest`。
- `docker compose build`。
- `docker compose run --rm app pytest`。

Docker 與 CI 使用固定 Python 版本、GitHub Actions SHA、Docker digest 與 `requirements.lock`，避免同一份提交在不同時間解析到不同依賴。

## 目標架構

```text
使用者
  │
  ├─ Dashboard
  ├─ Obsidian
  └─ AI Orchestrator
       │
       ├─ 市場分析 Agent
       ├─ 復盤教練 Agent
       └─ 回測分析 Agent
            │
            ▼
          MCP
            │
            ▼
        共用核心服務
            │
            ├─ 股票 DB
            ├─ 市場資料 Provider
            └─ 回測引擎
```

目標架構仍是規劃，不代表已實作。導入順序會採漸進方式：先讓資料與測試穩定，再建立唯讀 MCP；確認有價值後，才加入 AI workflow 與多 Agent 編排。

## 未來分層

### MCP

MCP 是 AI 與本機股票系統之間的標準工具介面。第一版維持唯讀，不碰下單。

預計工具：

- `search_stock`
- `get_daily_prices`
- `get_market_summary`
- `get_daily_review`

MCP 不直接依賴 Streamlit，也不應直接呼叫 yfinance；它應透過共用核心服務與 repository 取得資料。

### 回測

回測層負責策略介面、歷史資料快照、績效統計與報告輸出。

回測不應依賴 Dashboard 狀態，也不應用即時網路資料作為唯一輸入。未來應建立可重現的歷史資料快照流程。

### AI Orchestrator 與 AI Clients

AI Orchestrator 負責任務分派、流程編排與結果整合，不直接保存市場或交易資料。

AI clients 只保存各模型平台的使用約定、提示詞模板與安全邊界。OpenAI、Anthropic、Google 或其他模型供應商是可替換 runtime；市場分析、復盤教練與回測分析才是具體角色。

### Obsidian

Obsidian 保存長期知識、研究框架、決策理由與學習紀錄。GitHub Issues 保存可執行任務；主 Repo 保存程式事實；AI Context 保存跨 Session 交接狀態。

## 開發原則

- 先唯讀，再寫入。
- 先資料可信，再策略複雜。
- 先本機可重現，再自動化。
- 先記錄決策理由，再考慮交易執行。
- Dashboard 只負責 UI；可共用邏輯放在核心套件。
- 真實網路資料不穩定，測試優先使用 fake 或 mock provider。
- 不保存 secrets、API key、本機 SQLite 內容或個人交易資料到 Git。
- 現階段不實作券商 API、自動下單或實盤交易。
