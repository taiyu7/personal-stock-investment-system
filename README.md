# 個人股票投資系統

這是個人股票投資系統的唯一主線 Repo。系統以台股投資流程為核心，將美股、半導體與總經指標作為盤前參考，逐步整合 Dashboard、共用市場資料服務、個人交易紀錄、MCP、回測與多模型 AI 工作流。

目前可直接使用的是 Streamlit Dashboard、yfinance 按需行情、規則訊號、SQLite 每日復盤，以及第一階段研究來源分析工具入口。研究工具可處理手動文字、文字型 PDF 前處理與公開 YouTube URL fallback 狀態，並已建立通用來源匯入 status/result 邊界；真實 YouTube CC 字幕讀取尚未接上 adapter。MCP、回測引擎與 AI Orchestrator 會依路線圖分階段加入。

目前開發流程以 Docker 為預設執行環境；本機 Python 只作為可選 fallback，不是日常啟動方式。

## 目前可用架構

```text
                              使用者
                                 │
                                 ▼
                  Streamlit Dashboard v0.9.0
              盤前觀察 / 盤後復盤 / 研究來源分析
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
- **研究來源分析**：從左側 sidebar 進入，支援手動文字／逐字稿、PDF 路徑與公開 YouTube URL，產生固定格式研究報告 Markdown，並可依設定輸出到 Obsidian inbox、自選路徑或只在介面顯示。
- **每日復盤**：填寫盤前／盤後持股水位、交易紀錄、計畫符合度與檢討內容；可依日期儲存、覆寫、載入及下載 Markdown。
- **進銘的股價概念**：保存既有的價格、成交量與判讀框架。
- **開發歷程**：保留 AutoDashboard v0.1 至 v0.6 的歷史，並記錄整合後的功能演進。

研究來源分析目前是第一階段 MVP：YouTube URL 會解析 video id 並顯示逐字稿 fallback 狀態，但尚未實際抓取 YouTube CC 或 automatic captions。若要分析影片內容，目前需要手動貼上逐字稿或摘要；後續會補真實字幕 adapter。

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

## 從想法到實作(workflow)

新的想法先進 Obsidian，再依成熟度進入 GitHub Issues、Project 與主 Repo 實作。

```text
突然想到
  ↓
Obsidian 00-inbox
  ↓
整理分類
  ↓
Obsidian 正式知識頁 / 04-issues 問題拆解
  ↓
GitHub Issue
  ↓
GitHub Project 排程
  ↓
AI Context 標記目前焦點
  ↓
主 Repo 實作
  ↓
測試與驗證
  ↓
Issue 關閉
  ↓
AI Context 更新交接
  ↓
Obsidian 補上長期知識或決策
```

分工原則：

- Obsidian 保存「為什麼與怎麼想」，例如長期知識、研究框架、設計理由與決策紀錄。
- GitHub Issues 保存「要做什麼」，例如可執行、可驗收、可排程的任務。
- GitHub Project 管理任務狀態，例如 Backlog、Ready、In Progress、Verify、Done。
- 主 Repo 保存「實際做了什麼」，例如程式碼、測試、README、架構文件與 roadmap。
- AI Context 保存「現在做到哪裡」，用於 AI 接手、規範與交接摘要。

## 專案目錄

```text
personal-stock-investment-system/
├── apps/dashboard/                         # Streamlit 使用介面
├── src/personal_stock_investment_system/  # 共用 Python 核心套件
│   ├── config/                            # 觀察清單設定
│   ├── market_data/                       # Provider、行情模型與摘要服務
│   ├── research/                          # 研究來源模型、通用匯入狀態、PDF/YouTube adapter、分析、輸出與入口
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
├── docs/research/                         # 研究工具規格與文件
├── docs/roadmap/                          # 階段路線圖
├── docs/legacy/autodashboard/             # 舊專案文件封存
└── tests/                                 # 單元測試
```

## 在 Windows 啟動 Docker

需求：Docker Desktop，並使用支援 `docker compose` 的版本。

第一次建立開發 image：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
docker compose build
```

啟動 Dashboard：

```powershell
docker compose up dashboard
```

瀏覽器開啟：<http://localhost:8501>

執行測試：

```powershell
docker compose run --rm app pytest
```

`docker-compose.yml` 會掛載 `src/`、`apps/`、`tests/` 與 `data/local/`，方便在本機修改程式後直接重跑測試或 Dashboard。`.dockerignore` 會排除 `.venv/`、`.pytest_cache/`、`.tmp/`、`.yfinance-cache/` 與本機資料，避免把虛擬環境、快取與暫存資料包進 image。

Docker 中的 image 是可重複使用的執行環境範本；container 則是由 image 建立出來的一次執行個體。本專案會使用 `personal-stock-investment-system-dev` 作為開發 image，並以 Python 基底 image 組成它。`docker compose run --rm app pytest` 會建立暫時 container 跑測試，正常結束後會移除；Docker Desktop 裡看到 `Exited (0)` 的 container 則代表它已成功結束，並沒有持續執行。

### PDF 工具 Docker profile

進階 PDF 轉 Markdown 使用獨立的 `pdf-tools` profile，不會拖重日常 Dashboard 與核心測試 image。

第一次建立 PDF 工具 image：

```powershell
docker compose --profile pdf-tools build pdf-tools
```

確認 PyMuPDF4LLM backend 可用：

```powershell
docker compose --profile pdf-tools run --rm pdf-tools
```

需要在 PDF 工具環境中執行 #13 測試時：

```powershell
docker compose --profile pdf-tools run --rm pdf-tools pytest tests/test_pdf_research.py
```

一般開發與 CI 仍使用 `docker compose run --rm app pytest`。

### ASR 工具 Docker profile

Breeze-ASR-25 使用獨立的 `asr-tools` profile，不會拖重日常 Dashboard 與核心測試 image。第一次建立 ASR 工具 image：

```powershell
docker compose --profile asr-tools build asr-tools
```

確認 ASR dependencies 可用：

```powershell
docker compose --profile asr-tools run --rm asr-tools
```

本機音訊測試可先把檔案放到 `data/raw/asr-samples/`，再輸出逐字稿到 `data/processed/asr-transcripts/`：

```powershell
docker compose --profile asr-tools run --rm asr-tools whisper data/raw/asr-samples/sample.mp3 --model breeze-asr-25 --output_format json --output_dir data/processed/asr-transcripts --language Chinese
```

Breeze-ASR-25 會下載大型模型快取；本專案將 ASR cache 掛載到 `data/local/asr-cache/`，不會提交 Git。若 Whisper 產出的 JSON 顯示為 `\uXXXX` escape，研究工具的 ASR adapter 會在讀取後重新寫成可讀 UTF-8 JSON。

## 本機 Python fallback

日常開發優先使用 Docker。只有在需要快速檢查或 Docker 不方便啟動時，才使用本機 Python。

需求：Python 3.11 以上。

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
```

本機執行測試：

```powershell
pytest
```

本機啟動 Dashboard：

```powershell
python -m streamlit run apps\dashboard\app.py
```

本專案目前沒有要求建立 `.venv`。若使用者自行建立虛擬環境，請勿提交 `.venv/`。

## 環境設定

`.env.example` 提供以下設定入口：

- `DATABASE_URL`：預設 SQLite，保留其他資料庫擴充能力。
- `MARKET_DATA_PROVIDER`、`MARKET_DATA_API_KEY`：未來新增行情來源。
- `MCP_SERVER_HOST`、`MCP_SERVER_PORT`：未來 MCP server。
- `OPENAI_API_KEY`、`ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`：未來 AI clients。
- `ENABLE_LIVE_TRADING=false`：預設禁止實盤交易。

請勿將 `.env`、API 金鑰或本機資料庫提交到 Git。

## 測試

預設使用 Docker 執行完整測試：

```powershell
cd C:\Users\taiyu\personal-stock-investment-system
docker compose run --rm app pytest
```

若使用本機 Python fallback：

```powershell
pytest
```

目前測試涵蓋：

- yfinance OHLCV 正規化與多層欄位處理
- provider 失敗、空資料與缺少收盤價時的安全處理
- 市場摘要、總經反向計分與資料不足時的中性判斷
- 五日行情以前一交易日收盤價計算漲跌，以及 OHLC 欄位缺漏處理
- 每日復盤的儲存、覆寫、讀回、尚未建立資料庫與 Markdown 格式
- 研究來源資料模型與固定格式 Markdown 報告輸出
- 研究來源通用 import status/result 邊界
- 文字型 PDF 轉 Markdown，並保留頁碼定位；可選用 PyMuPDF4LLM backend 處理進階 PDF
- 公開 YouTube URL 解析、逐字稿 fallback 狀態與 fake/mock 字幕 adapter 測試
- 本機音訊 ASR adapter 的 fake/mock 轉錄、Whisper JSON 解析與 UTF-8 正規化
- 固定文字逐字稿轉成股票研究報告，包含人物觀點、族群關聯、公司業務、技術分析、假設、風險與待查問題
- 研究報告輸出目的地設定，可輸出到 Obsidian inbox、自選路徑，或不寫入本機檔案
- 第一階段研究來源分析入口，支援手動文字、PDF 前處理、YouTube fallback 狀態與暫存輸出目的地測試
- Dashboard 資料表的防呆邏輯
- Streamlit Dashboard 啟動 smoke test

### 可重現依賴

`requirements.lock` 由 Python 3.11 的 `pip-tools==7.5.2` 產生，鎖定所有直接與遞迴依賴的精確版本與 SHA-256 hash。Docker 與 GitHub Actions 都以此檔案安裝依賴；`setuptools` 也固定在 `pyproject.toml`，避免同一份程式在不同時間解析到不同套件或建置工具版本。

修改 `pyproject.toml` 依賴後，請重新產生 lock file：

```powershell
docker run --rm -v "${PWD}:/workspace" -w /workspace python:3.11-slim sh -c "python -m pip install pip-tools==7.5.2 && pip-compile --extra dev --generate-hashes --output-file requirements.lock pyproject.toml"
```

目前已有 GitHub Actions CI：push 到 `main` 或建立 pull request 時，會執行以下兩項驗證。CI runner 固定為 Ubuntu 24.04，Python、GitHub Actions 與 Docker base image 也固定到明確版本或不可變 digest：

- Ubuntu + Python 3.11.15 依 `requirements.lock` 安裝專案並執行 `pytest`。
- `docker compose build`，接著在容器中執行 `docker compose run --rm app pytest`。

Docker 開發環境可用於本機 build、測試與啟動 Dashboard，CI 會同步驗證本機開發時使用的 Docker 測試流程。Dashboard smoke test 已納入自動化測試。

### 固定參照的意義

GitHub Actions 的 `actions/checkout` 與 `actions/setup-python` 會以 commit SHA 參照特定、不可變的 action 原始碼；相較於 `@v4` 或 `@v5` 這類可能被更新的標籤，CI 每次都會執行相同版本的 action。

Dockerfile 的 Python base image 以 digest 參照特定 image 內容；`python:3.11-slim` 是可移動的標籤，未來可能指到新版 image，而 `@sha256:...` 則固定指向目前已驗證的那一份內容。升級 action、base image 或依賴時，應主動更新對應參照並重新執行測試。

## 開發路線

1. **Phase 1：本機骨架**：Repo、文件、環境範本與 Git，已完成。
2. **Phase 1.5：知識庫與開發環境隔離**：沿用既有 Obsidian vault，Docker 開發環境已可 build、測試與啟動 Dashboard。
3. **Phase 1.6：自動化測試補強**：核心單元測試、Docker-based CI 與 Dashboard smoke test 已完成。
4. **Phase 1.7：研究工具優先**：#12 至 #17 已完成第一階段研究來源分析工具 MVP，包含資料模型、PDF 轉 Markdown、YouTube fallback、股票觀點分析、輸出目的地設定與 Streamlit sidebar 入口。#24 已完成研究來源 adapter 邊界小重構，建立通用 import status/result。尚未完成真實 YouTube CC 字幕 adapter、真實 PDF 品質驗收與 Obsidian 長期知識整理流程。
5. **Phase 2：資料層 MVP**：Dashboard、yfinance、共用服務與 SQLite，核心功能已完成；下一步是在研究工具 MVP 後驗證 12 個預設 ticker 的資料完整性，決定是否新增 TWSE、TPEx 或 FinMind provider。
6. **Phase 3：MCP MVP**：建立唯讀 server，提供市場行情、市場摘要與每日復盤查詢。
7. **Phase 4：回測 MVP**：建立策略介面、示範策略、績效統計與報告。
8. **Phase 5：AI 工作流**：建立盤前、盤後與交易紀律模板，再加入多模型編排與比較。

完整階段清單請見 `docs/roadmap/phase-plan.md`，分層設計請見 `docs/architecture/overview.md`，資料庫 schema 與 migration 策略請見 `db/README.md`。第一階段研究來源分析工具規格請見 `docs/research/phase-1-research-source-spec.md`。

目前已完成研究來源分析工具的 GitHub Issues：#12 至 #17，以及 #24 adapter 邊界小重構。下一批研究工具工作會優先補真實 YouTube 字幕 adapter，接著處理 YouTube 會員影片 / 受限制來源合法取得流程，再展開本機影片、本機音訊、podcast 與技術分析圖面自動截圖。完整規劃請見 `docs/research/media-source-ingestion-roadmap.md`。

## 安全邊界

目前不實作券商 API、自動下單、實盤交易或完整全市場資料倉。所有交易結論都應由使用者自行確認；系統現階段定位為研究、記錄與決策輔助工具。
