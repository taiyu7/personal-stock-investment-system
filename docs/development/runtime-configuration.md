# Runtime 配置與依賴邊界

本文記錄目前系統哪些依賴裝在 Docker container，哪些依賴留在 Windows 本機，以及什麼情況下需要安裝或重建。若本文與程式碼不一致，以 `docker-compose.yml`、`pyproject.toml`、`Dockerfile` 與實際測試結果為準。

## 原則

- 日常開發、測試與 Dashboard 啟動以 Docker Compose 為預設路徑。
- 本機 Python 只作為快速檢查或特殊硬體 runtime 的 fallback。
- `.env`、Chrome profile、OpenVINO 模型、下載音訊、逐字稿、SQLite 與 cache 都是本機資料，不提交 Git。
- 只有改到依賴、Docker build args、系統套件或 image 內容時才需要 rebuild；只改 `src/`、`apps/`、`tests/` 通常重啟或重新整理即可。

## Docker services

### `app`

用途：

- 跑單元測試。
- 驗證共用核心、Dashboard helper、研究工具與 provider 邊界。

安裝內容：

- Python runtime dependencies：`altair`、`openai`、`pandas`、`streamlit`、`yfinance`。
- `requirements.lock` 中的測試依賴，包含 `pytest`。
- 專案本身以 editable mode 安裝。

掛載：

- `./src:/app/src`
- `./apps:/app/apps`
- `./tests:/app/tests`
- `./data/local:/app/data/local`

不負責：

- 不安裝 Chromium / ChromeDriver / ffmpeg。
- 不負責 UI 內瀏覽器轉錄。
- 不跑 OpenVINO GPU 本機加速。

常用命令：

```powershell
docker compose run --rm -T app pytest
```

### `dashboard`

用途：

- 啟動 Streamlit Dashboard。
- 在 UI 內執行影片 URL 轉逐字稿與研究報告流程。

安裝內容：

- `app` 的一般 Python runtime dependencies。
- `media-browser` extra：`selenium`、`webdriver-manager`、`yt-dlp`。
- apt packages：`ffmpeg`、`chromium`、`chromium-driver`。

為什麼 #60 要安裝這些：

- Dashboard 需要 Selenium 開 Chromium，才能進影片頁面並嗅探 media request。
- 取得 media request 後，需要 `yt-dlp` 下載影片或音訊。
- 下載後需要 `ffmpeg` 轉成 16 kHz mono WAV，才能交給 ASR provider。
- Docker container 沒有桌面顯示器，所以 Dashboard 預設使用 headless Chromium。

掛載：

- `./src:/app/src`
- `./apps:/app/apps`
- `./data/local:/app/data/local`
- `./data/raw:/app/data/raw`
- `./data/processed:/app/data/processed`

重要預設：

- Docker/Linux Chrome binary：`/usr/bin/chromium`
- Docker/Linux ChromeDriver：`/usr/bin/chromedriver`
- Docker/Linux `Headless browser`：預設勾選
- OpenAI transcript JSON：`data/processed/asr-transcripts/openai/`
- OpenVINO transcript JSON：`data/processed/asr-transcripts/openvino/`

常用命令：

```powershell
docker compose build dashboard
docker compose up dashboard
docker compose restart dashboard
```

### `pdf-tools`

用途：

- 進階 PDF 轉 Markdown。
- 驗證 `pymupdf4llm` backend。

安裝內容：

- `pdf` extra：`pymupdf4llm`。

為什麼獨立：

- PyMuPDF4LLM 只在需要處理進階 PDF 時才用，避免拖重日常 app / dashboard image。

常用命令：

```powershell
docker compose --profile pdf-tools build pdf-tools
docker compose --profile pdf-tools run --rm pdf-tools
```

### `asr-tools`

用途：

- Breeze-ASR-25 / Whisper CPU 工具鏈驗證。
- 一般 ASR dependency smoke test。

安裝內容：

- apt packages：`ffmpeg`、`git`。
- `asr` extra：`accelerate`、`datasets[audio]`、`torch`、`transformers`、Breeze-ASR-25 whisper patch。

為什麼獨立：

- ASR 工具與模型 cache 很重，不應拖慢日常測試與 Dashboard。
- Docker 內目前不作為 Intel GPU 加速主線。

掛載：

- `./data/local/asr-cache:/root/.cache`
- `./tools/external:/app/tools/external`

常用命令：

```powershell
docker compose --profile asr-tools build asr-tools
docker compose --profile asr-tools run --rm asr-tools
```

## Windows 本機依賴

### OpenVINO GPU runtime

用途：

- 在 Windows + Intel Arc / Core Ultra Arc GPU 上跑 Breeze-ASR-25 OpenVINO FP32。

位置：

- Python venv：`data/local/openvino-venv`
- OpenVINO model：`data/local/openvino/breeze-asr-25-fp32`

原因：

- #43 Phase A 實測後，Windows 本機 OpenVINO GPU FP32 是目前速度與輸出都較可接受的本機 ASR 路線。
- Docker 內不期待 Intel GPU passthrough；不要把 Docker XPU 當預設加速方案。

使用方式：

```powershell
$env:PYTHONPATH = "src"
& .\data\local\openvino-venv\Scripts\python.exe -m personal_stock_investment_system.research.browser_asr_cli ...
```

### Windows Chrome / ChromeDriver

用途：

- 本機 CLI 需要使用 Windows Chrome profile 或登入狀態時使用。

常見位置：

- Chrome：`C:\Program Files\Google\Chrome\Application\chrome.exe`
- ChromeDriver：`data\local\chromedriver\chromedriver-win64\chromedriver.exe`
- 專用 debug profile：`data\local\psis-browser-asr-debug-profile`
- yt-dlp cookies profile：`chrome:C:\Users\taiyu\AppData\Local\psis-browser-asr-profile\Default`

原因：

- 某些會員影片或需要登入的來源，Docker 內乾淨 Chromium 沒有 Windows Chrome 的登入狀態。
- 使用本機 CLI 時可以直接指定 Windows Chrome 與 profile。

### `.env`

用途：

- 提供 OpenAI API key 與模型設定。

目前使用：

- `OPENAI_API_KEY`
- `OPENAI_RESEARCH_ANALYSIS_MODEL`
- `OPENAI_AUDIO_TRANSCRIPTION_MODEL`

注意：

- `.env` 必須放在 repo 根目錄。
- 不提交 `.env`。
- 修改 `.env` 後通常只要重啟 Dashboard，不需要 rebuild image。

## 什麼時候要安裝或 rebuild

需要 `docker compose build dashboard`：

- 修改 `dashboard` 的 apt packages。
- 修改 `dashboard` 的 `INSTALL_EXTRAS`。
- 新增 UI 轉錄所需的 Python 套件、系統套件或 command-line 工具。

需要 `docker compose build app dashboard`：

- 修改一般 runtime dependencies。
- 更新 `requirements.lock`。
- 新增 `openai` 這類 app / dashboard 都會 import 的套件。

需要 `docker compose --profile asr-tools build asr-tools`：

- 修改 Breeze-ASR-25 / Whisper / Torch / Transformers 相關依賴。
- 需要重建 ASR CPU 工具環境。

需要 Windows 本機安裝：

- 需要使用 Intel GPU OpenVINO。
- 需要使用 Windows Chrome 登入狀態或本機 profile。
- 需要在 Docker 外跑 `data/local/openvino-venv`。

不需要 rebuild：

- 只改 `src/`、`apps/`、`tests/`。
- 只更新 `.env`。
- 只修改 README / docs。
- 只更換 Dashboard 表單值或輸入網址。

## #60 當時做了什麼

#60 目標是讓使用者可以在 Dashboard 直接貼影片 URL，選轉錄 provider，產生逐字稿，再接研究彙整報告。

因此做了三類配置變更：

1. Dashboard UI 增加轉錄表單與 provider 選項。
2. Dashboard container 增加瀏覽器與媒體工具依賴：`ffmpeg`、`chromium`、`chromium-driver`、`media-browser` extra。
3. Dashboard 在 Docker/Linux 預設使用 headless Chromium；Windows 直接跑時保留 Windows Chrome path 預設。

這些變更讓公開影片可以在瀏覽器 UI 內跑完 MVP 流程；需要 Windows 登入狀態的會員影片仍可能要走本機 CLI 或後續新增 profile 掛載策略。

## 快速判斷

- 想跑測試：用 `app`。
- 想開 Dashboard：用 `dashboard`。
- 想從 Dashboard 貼影片 URL 轉逐字稿：用 `dashboard`，且 image 要含 #60 依賴。
- 想用 OpenAI 轉錄或 OpenAI 彙整：確認 `.env` 有 `OPENAI_API_KEY`。
- 想用 OpenVINO GPU：用 Windows 本機 `data/local/openvino-venv`。
- 想處理進階 PDF：用 `pdf-tools` profile。
- 想驗證 Breeze-ASR-25 CPU 工具鏈：用 `asr-tools` profile。
