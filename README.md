# 個人股票投資系統

這是個人股票投資系統的唯一主線 Repo。系統以台股投資流程為核心，將美股、半導體與總經指標作為盤前參考，逐步整合 Dashboard、共用市場資料服務、個人交易紀錄、MCP、回測與多模型 AI 工作流。

目前可直接使用的是 Streamlit Dashboard、yfinance 按需行情、規則訊號與 SQLite 每日復盤。MCP、回測引擎與 AI Orchestrator 會依路線圖分階段加入。

## 目前可用架構

```text
                              使用者
                                 │
                                 ▼
                  Streamlit Dashboard v0.7.0
                    盤前觀察 / 盤後復盤工作台
                                 │
                                 ▼
              personal_stock_investment_system 共用核心
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
   市場資料服務與模型         規則訊號引擎          每日復盤服務
          │                                             │
          ▼                                             ▼
 yfinance 按需下載                               SQLite 本機資料庫
 15 分鐘記憶體快取                               個人紀錄與 Markdown
```

Dashboard 只負責畫面與互動。行情取得、資料正規化、市場判斷、復盤格式與 SQLite 儲存都放在共用核心，讓未來的 MCP 與回測可以重複使用，不需依賴 Streamlit。

## 遠期目標架構

```text
                              使用者
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
           Dashboard          Obsidian       AI Orchestrator
         操作與結果檢視      知識與進步紀錄    任務分派 / 流程編排
                                                    │
                         ┌──────────────────────────┼──────────────────────────┐
                         ▼                          ▼                          ▼
                   市場分析 Agent              復盤教練 Agent              回測分析 Agent
                 盤前與盤後市場研究          決策品質與紀律檢查          策略驗證與結果解讀
                         └──────────────────────────┼──────────────────────────┘
                                                    │
                  每個 Agent = Model + Instructions / Persona + Skill + Guardrails
                         Model 可選 OpenAI / Anthropic / Google 或其他供應商
                                                    │
                                                    ▼
                                                   MCP
                                      標準化工具、權限與資料存取介面
                                                    │
                                                    ▼
                                               共用核心服務
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                           股票 DB                市場資料               回測引擎
                          個人累積資料          多來源 Provider        指定標的與期間
```

這個設計將 AI 平台與 Agent 角色分開：OpenAI、Anthropic、Google 是可替換的模型供應商；市場分析、復盤教練與回測分析則是具體工作角色。每個 Agent 以 instructions 定義目標、人格與限制，以 Skill 保存可重複的工作方法，並透過 MCP 使用共用核心服務。

AI Orchestrator 負責任務分派、流程編排與結果整合，不直接保存市場或交易資料。Obsidian 保存個人的學習、決策理由與進步軌跡；Git Repo、AI Context 與 SQLite 仍各自維持程式事實、跨 Session 交接與個人復盤資料的責任邊界。

遠期導入順序仍採漸進方式：先完成資料品質與唯讀 MCP，再建立一個可驗證的盤前／盤後研究 Agent；確認穩定且確實有價值後，才拆分多 Agent 並加入 Orchestrator。所有 Agent 預設只提供研究與決策輔助，不得自動下單。

## Dashboard 功能

- **市場儀表板**：四個觀察區塊、市場摘要、五日行情、漲跌幅與月線 K 線圖。
- **每日復盤**：填寫盤前／盤後持股水位、交易紀錄、計畫符合度與檢討內容；可依日期儲存、覆寫、載入及下載 Markdown。
- **進銘的股價概念**：保存既有的價格、成交量與判讀框架。
- **開發歷程**：保留 AutoDashboard v0.1 至 v0.6 的歷史，並記錄整合後的 v0.7。

預設觀察清單分為：

- 全球指數
- AI／半導體
- 美債與美元
- 台灣市場

## 資料原則

- yfinance 是目前的 MVP 行情來源，只在需要時下載觀察清單或指定回測標的。
- 行情使用 Streamlit 15 分鐘記憶體快取，不提交 `.yfinance-cache`。
- SQLite 只保存個人累積資料，包括每日復盤、產生的 Markdown、交易原始文字及盤前／盤後持股水位。
- 系統目前不解析自由文字交易紀錄，也不建立全台股常駐行情資料庫。
- 本機資料庫預設位於 `data/local/personal-stock-investment.db`，不會提交 Git。
- 未來可透過 `DATABASE_URL` 擴充至 MySQL 或 PostgreSQL。

## 專案目錄

```text
personal-stock-investment-system/
├── apps/dashboard/                         # Streamlit 使用介面
├── src/personal_stock_investment_system/  # 共用 Python 核心套件
│   ├── config/                            # 觀察清單設定
│   ├── market_data/                       # Provider、行情模型與摘要服務
│   ├── signals/                           # 偏多／中性／偏空規則引擎
│   └── storage/                           # SQLite 每日復盤 Repository
├── data/                                  # 本機資料；內容不提交 Git
├── market_data/                           # 未來資料來源與匯入文件
├── db/                                    # 未來 schema 與 migration
├── mcp/                                   # 未來 MCP server 與工具
├── backtesting/                           # 未來策略、回測與報告
├── orchestrator/                          # 未來 AI 工作流編排
├── clients/                               # ChatGPT／Claude／Gemini 約定
├── config/                                # 非敏感設定文件
├── docs/architecture/                     # 架構文件
├── docs/roadmap/                          # 階段路線圖
├── docs/legacy/autodashboard/             # 舊專案文件封存
└── tests/                                 # 單元測試
```

## 在 Windows 啟動

需求：Python 3.11 以上。

第一次建立環境並安裝套件：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

之後每次在 VS Code Terminal 啟動 Dashboard：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
.\.venv\Scripts\Activate.ps1
python -m streamlit run apps\dashboard\app.py
```

瀏覽器開啟：<http://localhost:8501>

若 PowerShell 阻擋虛擬環境啟用，可只對目前 Terminal 執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 環境設定

`.env.example` 提供以下設定入口：

- `DATABASE_URL`：預設 SQLite，保留其他資料庫擴充能力。
- `MARKET_DATA_PROVIDER`、`MARKET_DATA_API_KEY`：未來新增行情來源。
- `MCP_SERVER_HOST`、`MCP_SERVER_PORT`：未來 MCP server。
- `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`：未來 AI clients。
- `ENABLE_LIVE_TRADING=false`：預設禁止實盤交易。

請勿將 `.env`、API 金鑰或本機資料庫提交到 Git。

## 測試

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
.\.venv\Scripts\Activate.ps1
python -m pytest
```

目前測試涵蓋：

- yfinance OHLCV 正規化與多層欄位處理
- 市場摘要與總經反向計分
- 五日行情以前一交易日收盤價計算漲跌
- 每日復盤的儲存、覆寫、讀回與 Markdown 格式

## 開發路線

1. **Phase 1：本機骨架**：Repo、文件、環境範本與 Git，已完成。
2. **Phase 2：資料層 MVP**：Dashboard、yfinance、共用服務與 SQLite，核心功能已完成；下一步驗證台股資料完整性與歷史快照流程。
3. **Phase 3：MCP MVP**：建立唯讀 server，提供市場行情、市場摘要與每日復盤查詢。
4. **Phase 4：回測 MVP**：建立策略介面、示範策略、績效統計與報告。
5. **Phase 5：AI 工作流**：建立盤前、盤後與交易紀律模板，再加入多模型編排與比較。

完整階段清單請見 `docs/roadmap/phase-plan.md`，分層設計請見 `docs/architecture/overview.md`。

## 安全邊界

目前不實作券商 API、自動下單、實盤交易或完整全市場資料倉。所有交易結論都應由使用者自行確認；系統現階段定位為研究、記錄與決策輔助工具。

## AutoDashboard 遷移說明

舊 AutoDashboard 的功能已整合至本 Repo。原始 README、PROJECT、TODO、DECISIONS、requirements 與來源提交資訊保存在 `docs/legacy/autodashboard/`，只供歷史追溯；後續程式與文件維護皆以本 Repo 為準。
