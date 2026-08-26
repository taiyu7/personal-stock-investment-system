# 個人股票投資系統

這是個人股票投資系統的唯一主線 Repo。系統以台股投資流程為核心，將美股、半導體與總經指標作為盤前參考，逐步整合 Dashboard、共用市場資料服務、個人交易紀錄、MCP、回測與多模型 AI 工作流。

目前可直接使用的是 Streamlit Dashboard、yfinance 按需行情、規則訊號、SQLite 每日復盤，以及第一階段研究來源分析工具。研究工具已可從 Dashboard 貼上影片 URL，經瀏覽器媒體取得、FFmpeg 音訊前處理、OpenAI 或 OpenVINO 轉錄 provider 產生逐字稿 JSON，再交給本機規則或 OpenAI 研究彙整 provider 產生固定格式 Markdown 報告。MCP、回測引擎與 AI Orchestrator 會依路線圖分階段加入。

目前開發流程以 Docker 為預設執行環境；本機 Python 只作為可選 fallback，不是日常啟動方式。

## 快速啟動

需求：Docker Desktop，並使用支援 `docker compose` 的版本。

第一次建立開發 image：

```powershell
git clone <repository-url>
cd personal-stock-investment-system
docker compose build
```

啟動 Dashboard：

```powershell
docker compose up dashboard
```

瀏覽器開啟：<http://localhost:8501>

執行完整測試：

```powershell
docker compose run --rm app pytest
```

## 目前可用架構

```text
                              使用者
                                 │
                                 ▼
                  Streamlit Dashboard
              盤前觀察 / 盤後復盤 / 研究來源分析
                                 │
                                 ▼
              personal_stock_investment_system 共用核心
    ┌───────────────┬───────────────┬────────────────┬────────────────┐
    ▼               ▼               ▼                ▼
市場資料服務       規則訊號引擎      每日復盤服務       研究來源工具
    │                               │                │
    ▼                               ▼                ▼
yfinance 按需下載              SQLite 本機資料庫   影片 / PDF / 文字 / ASR JSON
15 分鐘記憶體快取              個人紀錄與 Markdown          │
                                                            ▼
                                      media discovery -> FFmpeg -> ASR provider
                                                            │
                                                            ▼
                                      analysis provider -> Markdown / Obsidian
```

Dashboard 只負責畫面與互動。行情取得、資料正規化、市場判斷、復盤格式與 SQLite 儲存都放在共用核心，讓未來的 MCP 與回測可以重複使用，不需依賴 Streamlit。

## Dashboard 功能

- **市場儀表板**：四個觀察區塊、市場摘要、五日行情、漲跌幅與月線 K 線圖。
- **研究來源分析**：從左側 sidebar 進入，支援手動文字／逐字稿、ASR 逐字稿 JSON、PDF 路徑、公開 YouTube URL fallback，以及 Dashboard 內建的影片 URL 轉逐字稿流程；可選轉錄 provider 與研究彙整 provider，產生固定格式研究報告 Markdown，並輸出到 Obsidian inbox、自選路徑或只在介面顯示。
- **每日復盤**：填寫盤前／盤後持股水位、交易紀錄、計畫符合度與檢討內容；可依日期儲存、覆寫、載入及下載 Markdown。
- **股價概念筆記**：保存既有的價格、成交量與判讀框架。
- **開發歷程**：保留 AutoDashboard v0.1 至 v0.6 的歷史，並記錄整合後的功能演進。

研究來源分析目前的 MVP 主線是：影片 URL 先取得媒體並產生 ASR 逐字稿 JSON，接著用該 JSON 產生研究報告。公開 YouTube URL 來源類型仍保留為字幕 adapter 的 fallback 路徑；真實 YouTube CC / automatic captions adapter 尚未接上。若不想重新轉錄，也可以手動貼上逐字稿或既有 ASR JSON 路徑。

### 轉錄 provider

Dashboard 的「研究來源分析」頁分成兩段：

1. **取得逐字稿**：貼上影片 URL，選擇 `只產生 WAV`、`OpenAI` 或 `OpenVINO`。
2. **產生研究報告**：使用剛產生的 ASR JSON，選擇研究彙整 provider，輸出 Markdown 報告。

目前轉錄 provider 狀態：

- `只產生 WAV`：只執行瀏覽器媒體取得與 FFmpeg 16 kHz mono WAV 前處理，適合除錯下載流程。
- `OpenAI`：使用 OpenAI Audio Transcriptions API。長音訊會先切成 10 分鐘 MP3 chunks，再逐段送出並合併 transcript JSON。
- `OpenVINO`：使用本機 OpenVINO Breeze-ASR-25 adapter。Windows + Intel Arc / Core Ultra Arc GPU 是目前建議路線；Docker 內不期待 Intel GPU 加速。

### 研究彙整 provider

已新增研究彙整 provider 邊界。Dashboard 目前可選：

- `本機規則 fallback`：目前可用，沿用保守 rule-based 分析器。
- `OpenAI`：已接上 OpenAI Responses API client。Docker Compose 會從 `.env` 讀取 `OPENAI_API_KEY` 與 `OPENAI_RESEARCH_ANALYSIS_MODEL`，再傳入 `app` / `dashboard` container。若未設定 API key 或 API 回傳無法解析，系統會明確標示失敗並回退本機規則 fallback。
- `Claude`：目前會明確標示尚未接上 API，並回退本機規則 fallback；後續再接真實 API adapter、secrets、usage / cost 記錄與 schema validation。

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

## 開發工作流

公開 repo 只保存可執行的程式碼、測試、README、架構文件與 roadmap；個人 AI 接手筆記、私人工作目錄與本機路徑不放進公開文件。

新的功能想法建議先整理成可驗收的 GitHub Issue，再進入實作：

```text
Idea / research note
  ↓
GitHub Issue
  ↓
Implementation in this repo
  ↓
Docker tests / CI
  ↓
Documentation update
  ↓
Issue closed
```

分工原則：

- GitHub Issues 保存「要做什麼」，包含需求、驗收條件與討論。
- GitHub Project 可用於管理 Backlog、Ready、In Progress、Verify、Done。
- 本 repo 保存「實際做了什麼」，包含程式碼、測試、README、架構文件與 roadmap。
- 本機資料、API keys、交易紀錄、影片、音訊、逐字稿與模型 cache 不提交 Git。

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
├── docs/development/                      # 開發環境、Docker 與本機依賴邊界
├── docs/research/                         # 研究工具規格與文件
├── docs/roadmap/                          # 階段路線圖
├── docs/legacy/autodashboard/             # 舊專案文件封存
└── tests/                                 # 單元測試
```

## Docker 開發環境補充

`docker-compose.yml` 會掛載 `src/`、`apps/`、`tests/` 與 `data/local/`，方便在本機修改程式後直接重跑測試或 Dashboard。Dashboard 服務另外掛載 `data/raw/` 與 `data/processed/`，供影片下載、音訊前處理與逐字稿輸出使用。`.dockerignore` 會排除 `.venv/`、`.pytest_cache/`、`.tmp/`、`.yfinance-cache/` 與本機資料，避免把虛擬環境、快取與暫存資料包進 image。

Docker 中的 image 是可重複使用的執行環境範本；container 則是由 image 建立出來的一次執行個體。本專案會使用 `personal-stock-investment-system-dev` 作為開發 image，並以 Python 基底 image 組成它。`docker compose run --rm app pytest` 會建立暫時 container 跑測試，正常結束後會移除；Docker Desktop 裡看到 `Exited (0)` 的 container 則代表它已成功結束，並沒有持續執行。

Dashboard image 會安裝 `ffmpeg`、`chromium`、`chromium-driver` 與 `media-browser` extra，讓瀏覽器介面可以直接執行「影片 URL -> WAV -> OpenAI/OpenVINO 逐字稿」流程。詳細配置與依賴邊界請見 `docs/development/runtime-configuration.md`。

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

需要在 PDF 工具環境中執行 PDF 轉 Markdown 測試時：

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

### ASR 硬體路線選擇

Breeze-ASR-25 的加速路線和電腦硬體高度相關，不能假設每台機器都能使用同一條最快路線。硬體加速實測後，本專案目前採用 **OpenVINO GPU FP32** 作為本機 ASR 加速方向，CPU 只保留為 fallback。

目前測試結論：

- **Windows + Intel Arc / Core Ultra Arc GPU**：優先使用 OpenVINO GPU FP32。60 秒投顧音檔實測約 `101.92 秒`，RTF 約 `1.70`，是目前最快且輸出正常的路線。
- **Docker ASR profile**：適合一般 CPU fallback、工具鏈驗證與可重現環境，但目前不作為 Intel GPU 加速主線。實測 Docker 內 XPU 不可用，Windows + Intel GPU passthrough 到 Docker / WSL 的成本與穩定性不適合作為預設方案。
- **PyTorch XPU**：Windows 本機可偵測 Arc，也能跑最小 tensor 測試，但 Breeze-ASR-25 whisper patch 實際 ASR 轉錄比 CPU 慢，因此不採用。
- **OpenVINO FP16**：可跑，但 15 秒 clip 沒有比 FP32 快；為降低精度變動風險，先採用 FP32。
- **沒有 Intel GPU 的電腦**：仍可使用 CPU fallback，但長音檔會很慢，不適合作為日常投顧節目轉錄主線。

其他人使用本專案時，應先依設備選擇 ASR 路線：

```text
有 Intel Arc / Core Ultra Arc GPU 的 Windows 主機
  -> OpenVINO GPU FP32

沒有 Intel GPU，或 OpenVINO 偵測不到 GPU
  -> CPU fallback

Docker 環境
  -> app/tests/CPU fallback，不期待 Intel GPU 加速
```

OpenVINO 本機環境、模型與 cache 都放在 `data/local/`，不提交 Git。實作 adapter 時應加入 backend 偵測：能看到 OpenVINO `GPU` 時使用 OpenVINO GPU FP32；否則退回 Breeze-ASR-25 CPU CLI adapter。詳細實測紀錄請見 `docs/research/asr-hardware-acceleration-phase-a.md`。

OpenVINO ASR adapter 的核心入口是：

```python
from pathlib import Path

from personal_stock_investment_system.research import (
    OpenVINOAsrConfig,
    OpenVINOAsrTranscriber,
    build_local_audio_research_source,
)

transcriber = OpenVINOAsrTranscriber(
    OpenVINOAsrConfig(
        model_dir=Path("data/local/openvino/breeze-asr-25-fp32"),
        device="GPU",
        output_dir=Path("data/processed/asr-transcripts/openvino"),
    )
)
result = build_local_audio_research_source(
    "data/raw/asr-samples/sample2-60s-16k-mono.wav",
    client=transcriber,
    title="投顧節目片段",
)
```

目前 OpenVINO adapter 預期輸入為 PCM WAV；若來源是 MP3 或影片，請先用 FFmpeg 轉成 16kHz mono WAV。OpenVINO runner 會以 `chunk_length_seconds=25.0` 將長音檔分段轉錄，再合併成 timestamped `AsrTranscriptSegment`，避免 Whisper 類模型直接 `generate()` 長音檔時只輸出前段內容。後續影片 / 連結流程會在素材取得後，先下載或抽取音訊，再交給 OpenVINO ASR adapter。

## 本機 Python fallback

日常開發與完整驗證優先使用 Docker。本機 Python 只用於快速語法檢查、Windows 專用瀏覽器 / OpenVINO 驗證，或使用者明確建立好虛擬環境後的局部除錯。

已知本機狀態：

- 不要預設直接跑 `pytest`；本機 `pytest` 不一定在 PATH。
- 不要預設用 `python -m pytest` 當主要測試路徑；本機環境不一定有 pytest module。
- 標準測試路徑是 `docker compose run --rm app pytest`。
- 可用本機 Python 做語法快檢，例如 `python -m compileall <paths>`。
- 若使用者自行建立 `.venv` 或其他本機 runtime，請勿提交 `.venv/`、模型 cache、音訊、影片、逐字稿或任何本機資料。

需要安裝本機 fallback 環境時，可在專案根目錄執行：

```powershell
cd personal-stock-investment-system
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
```

本機啟動 Dashboard 的命令如下；一般仍建議優先使用 Docker 啟動：

```powershell
python -m streamlit run apps\dashboard\app.py
```

## 環境設定

`.env.example` 提供以下設定入口：

- `DATABASE_URL`：預設 SQLite，保留其他資料庫擴充能力。
- `MARKET_DATA_PROVIDER`、`MARKET_DATA_API_KEY`：未來新增行情來源。
- `MCP_SERVER_HOST`、`MCP_SERVER_PORT`：未來 MCP server。
- `OPENAI_API_KEY`：OpenAI API project key；到 <https://platform.openai.com/api-keys> 建立後填入本機 `.env`。
- `OPENAI_RESEARCH_ANALYSIS_MODEL`：研究彙整使用的 OpenAI 模型，預設 `gpt-4.1-mini`。
- `OPENAI_AUDIO_TRANSCRIPTION_MODEL`：OpenAI 音訊轉錄使用的模型，預設 `gpt-4o-mini-transcribe`。
- `ANTHROPIC_API_KEY`、`GOOGLE_API_KEY`：未來 AI clients。
- `ENABLE_LIVE_TRADING=false`：預設禁止實盤交易。

第一次設定可直接複製範本：

```powershell
Copy-Item .env.example .env
```

填好 `.env` 後重新啟動 Docker Compose，`app` 與 `dashboard` container 會取得對應環境變數。請勿將 `.env`、API 金鑰或本機資料庫提交到 Git。

### OpenAI API 除錯

若 Dashboard 顯示「OpenAI 彙整失敗，已改用本機規則 fallback 產生報告」，先確認 Docker container 有讀到 `.env`，且不要把 API key 本體印出來：

```powershell
$debugScript = @'
import os
from personal_stock_investment_system.research import (
    ResearchSource,
    ResearchAnalysisSettings,
    analyze_research_source_with_provider,
)

print("OPENAI_API_KEY set:", bool(os.getenv("OPENAI_API_KEY")))
print("OPENAI_RESEARCH_ANALYSIS_MODEL:", os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL"))

source = ResearchSource(
    source_type="manual_text",
    title="OpenAI debug",
    raw_text="[00:00:10] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
)

result = analyze_research_source_with_provider(
    source,
    settings=ResearchAnalysisSettings(provider="openai"),
)

print("status:", result.status)
print("provider:", result.provider)
print("model:", result.model)
print("status_message:", result.status_message)
print("error:", result.error)
'@

$debugScript | docker compose run --rm -T app python -
```

判讀方式：

- `OPENAI_API_KEY set: False`：Docker 沒讀到 `.env`，確認 `.env` 是否在專案根目錄，然後重啟 Docker Compose。
- `OPENAI_API_KEY set: True` 但 `error` 顯示 `insufficient_quota` / `429`：API key 已進 container，但 OpenAI 帳號額度不足或 billing / usage limit 需要處理。
- `status: available`：OpenAI 彙整成功。

處理 `.env` 或 billing 後，通常不需要 rebuild Docker，只要重啟 Dashboard：

```powershell
docker compose down
docker compose up dashboard
```

## 測試

預設使用 Docker 執行完整測試：

```powershell
cd personal-stock-investment-system
docker compose run --rm app pytest
```

若只需要快速確認語法，可以用本機 Python 做 compile check：

```powershell
python -m compileall src apps tests
```

這不是完整測試替代品；正式驗證仍以 Docker pytest 或 CI 結果為準。

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
- Browser session media acquisition、yt-dlp / FFmpeg command boundary、browser ASR entrypoint 與 Dashboard 轉錄 provider wiring
- OpenAI 音訊轉錄 provider、長音訊 10 分鐘切段、逐字稿 JSON 合併與錯誤輸出
- 固定文字逐字稿轉成股票研究報告，包含人物觀點、族群關聯、公司業務、技術分析、假設、風險與待查問題
- OpenAI 研究彙整 provider、缺 key / API 失敗 / JSON 解析失敗時的本機規則 fallback
- 研究報告輸出目的地設定，可輸出到 Obsidian inbox、自選路徑，或不寫入本機檔案
- 第一階段研究來源分析入口，支援手動文字、ASR JSON、PDF 前處理、YouTube fallback 狀態、轉錄 provider 選擇與暫存輸出目的地測試
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

## 安全邊界

目前不實作券商 API、自動下單、實盤交易或完整全市場資料倉。所有交易結論都應由使用者自行確認；系統現階段定位為研究、記錄與決策輔助工具。

## Browser Session Media Acquisition

`research.media` adapter 用來銜接需要瀏覽器 session 才能取得媒體請求的研究來源。核心流程是：

```text
Chrome performance log / browser session
  -> m3u8 or media request discovery
  -> yt-dlp download
  -> FFmpeg 16 kHz mono WAV
  -> ASR provider: none / OpenVINO / OpenAI
  -> transcript JSON
  -> analysis provider: rule-based / OpenAI / Claude fallback
  -> Markdown report
```

目前已提供可測的邊界與預設下載/轉檔 adapter：

- `ChromePerformanceLogMediaDiscovery`
- `SeleniumBrowserMediaDiscovery`
- `YtDlpMediaDownloader`
- `FfmpegAudioPreprocessor`
- `BrowserSessionMediaAcquirer`

實際使用時，建議依設備與來源選擇路線：有 Intel Arc / Core Ultra Arc GPU 的 Windows 本機可接 OpenVINO GPU FP32；沒有 Intel GPU 或在 Docker 內執行時，應視為 CPU fallback 或只跑下載/前處理測試。瀏覽器 session 部分可使用既有 Chrome profile 取得當下有效的 media request，不保存短效 m3u8 當作長期資料。

`psis-browser-asr` 入口會把 browser session media acquisition 串成可以操作的命令。只想先產生 ASR-ready WAV 時，可以不傳 OpenVINO model：

```powershell
psis-browser-asr "https://example.com/member-video" `
  --chrome-user-data-dir "<chrome-user-data-dir>" `
  --chrome-profile-directory "Default" `
  --output-stem sample-video
```

若要接 OpenVINO ASR，補上模型目錄：

```powershell
psis-browser-asr "https://example.com/member-video" `
  --chrome-user-data-dir "<chrome-user-data-dir>" `
  --chrome-profile-directory "Default" `
  --output-stem sample-video `
  --openvino-model-dir data\local\openvino\breeze-asr-25-fp32 `
  --openvino-device GPU
```

填好 `.env` 的 `OPENAI_API_KEY` 後，可以改用 OpenAI 音訊轉錄 provider：

```powershell
psis-browser-asr "https://example.com/member-video" `
  --chrome-user-data-dir "<chrome-user-data-dir>" `
  --chrome-profile-directory "Default" `
  --output-stem sample-video `
  --asr-provider openai
```

OpenAI 轉錄預設會輸出到 `data/processed/asr-transcripts/openai/`。若不指定 `--asr-provider`，舊行為維持相容：有傳 `--openvino-model-dir` 時走 OpenVINO，否則只產生 ASR-ready WAV。

OpenAI Audio API 有上傳大小與長音訊限制；即使先壓成小於 25 MB，長音訊仍可能因 `input_too_large` 失敗。因此 `OpenAIAsrTranscriber` 會先用 FFmpeg 將音訊切成 10 分鐘 MP3 chunks，再逐段送 OpenAI ASR，最後合併成同一份 transcript JSON。若 OpenAI ASR 失敗，CLI 會輸出 `asr_error=...` 方便判斷是 quota、key、模型權限或輸入過大。

輸出重點：

- `wav_path`：FFmpeg 轉好的 16kHz mono WAV。
- `selected_media_url`：當次 browser session 嗅探到並用於下載的 media URL。
- `transcript_path`：有接 OpenVINO 或 OpenAI ASR 時產生的 transcript JSON。

YouTube 會員影片若 yt-dlp 需要讀取登入狀態與解析 YouTube player challenge，可使用：

```powershell
psis-browser-asr "https://www.youtube.com/watch?v=..." `
  --chrome-user-data-dir "data\local\psis-browser-asr-debug-profile" `
  --chrome-binary-path "<chrome-binary-path>" `
  --chromedriver-path "data\local\chromedriver\chromedriver-win64\chromedriver.exe" `
  --output-stem youtube-member-test `
  --settle-seconds 3 `
  --playback-wait-seconds 20 `
  --yt-dlp-download-page-url `
  --yt-dlp-cookies-from-browser "chrome:<chrome-profile-for-cookies>" `
  --yt-dlp-remote-components ejs:github
```

這條路線會先用瀏覽器確認頁面與媒體請求，再讓 yt-dlp 用原始 page URL、Chrome profile cookie 與 remote component 解析 YouTube 下載格式，最後交給 FFmpeg 轉 WAV。

## 遠期目標架構

```text
                              使用者
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
           Dashboard          Knowledge Base    AI Orchestrator
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

這個設計將 AI 平台與 Agent 角色分開：OpenAI、Anthropic、Google 是可替換的模型供應商；市場分析、復盤教練與回測分析則是具體工作角色。每個 Agent 以 instructions 定義目標、角色與限制，以 Skill 保存可重複的工作方法，並透過 MCP 使用共用核心服務。

AI Orchestrator 負責任務分派、流程編排與結果整合，不直接保存市場或交易資料。知識庫保存學習、決策理由與進步軌跡；Git repo、AI context 與 SQLite 則各自維持程式事實、跨 session 交接與個人復盤資料的責任邊界。

遠期導入順序仍採漸進方式：先完成資料品質與唯讀 MCP，再建立一個可驗證的盤前／盤後研究 Agent；確認穩定且確實有價值後，才拆分多 Agent 並加入 Orchestrator。所有 Agent 預設只提供研究與決策輔助，不得自動下單。

## 開發路線

1. **Phase 1：本機骨架**：Repo、文件、環境範本與 Git，已完成。
2. **Phase 1.5：知識庫與開發環境隔離**：知識庫與 Docker 開發環境已可用。
3. **Phase 1.6：自動化測試補強**：核心單元測試、Docker-based CI 與 Dashboard smoke test 已完成。
4. **Phase 1.7：研究工具優先**：第一階段研究來源分析工具已完成 MVP；OpenVINO ASR、browser media acquisition、OpenAI 音訊轉錄、研究彙整 provider 與 Dashboard 端影片 URL 轉研究報告流程已接上。尚未完成真實 YouTube CC 字幕 adapter、真實 PDF 品質驗收、知識庫長期整理流程、多檔 AI 推理、股票代號驗證與專有詞彙增強。
5. **Phase 2：資料層 MVP**：Dashboard、yfinance、共用服務與 SQLite 核心功能已完成；下一步是在研究工具 MVP 後驗證預設 ticker 的資料完整性，決定是否新增 TWSE、TPEx 或 FinMind provider。
6. **Phase 3：MCP MVP**：建立唯讀 server，提供市場行情、市場摘要與每日復盤查詢。
7. **Phase 4：回測 MVP**：建立策略介面、示範策略、績效統計與報告。
8. **Phase 5：AI 工作流**：建立盤前、盤後與交易紀律模板，再加入多模型編排與比較。

完整階段清單請見 `docs/roadmap/phase-plan.md`，分層設計請見 `docs/architecture/overview.md`，資料庫 schema 與 migration 策略請見 `db/README.md`。第一階段研究來源分析工具規格請見 `docs/research/phase-1-research-source-spec.md`。

目前已完成研究來源分析工具的 GitHub Issues：#12 至 #17、#24、#45、#47、#49、#50、#51、#55、#60。下一批研究工具工作會優先處理多檔 AI 推理、股票代號 / 公司名驗證、專有詞彙增強、真實 YouTube 字幕 adapter，以及 YouTube 會員影片 / 受限制來源合法取得流程。完整規劃請見 `docs/research/media-source-ingestion-roadmap.md`。
