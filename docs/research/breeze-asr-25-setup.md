# Breeze-ASR-25 安裝與整合流程

## 目標

將 Breeze-ASR-25 作為完整影片研究報告 pipeline 的本機 ASR backend。第一版整合方式是：

```text
本機音訊檔
  -> whisper CLI + breeze-asr-25
  -> JSON timestamp transcript
  -> personal_stock_investment_system.research.asr
  -> ResearchSourceImportResult
```

Breeze-ASR-25 官方 README 說明此模型基於 Whisper-large-v2 微調，針對台灣華語與中英混用情境優化，並強化時間戳對齊，適合自動字幕生成。

## 安全邊界

- 不提交影片、音訊、逐字稿、截圖、模型權重或 Hugging Face cache 到 Git。
- 不讀取或保存 cookie、session、token。
- 不繞過付費牆、帳號權限、平台限制或 DRM。
- `tools/external/`、`data/raw/`、`data/processed/` 都是本機資料區，不進 Git。

## 推薦流程：Docker asr-tools profile

以下命令都在主 Repo 執行：

```powershell
cd <repo-root>
```

### 1. 建立外部工具目錄

```powershell
New-Item -ItemType Directory -Force tools\external
```

### 2. 下載 Breeze-ASR-25 官方 repository

```powershell
git clone --recurse-submodules https://github.com/mtkresearch/Breeze-ASR-25 tools\external\Breeze-ASR-25
```

若已經 clone 過，更新 submodule：

```powershell
cd tools\external\Breeze-ASR-25
git submodule update --init --recursive
cd ..\..
```

### 3. 建立 ASR Docker image

這一步會安裝 PyTorch、Transformers、Datasets、Accelerate 與 ffmpeg，耗時與磁碟用量都會比一般 app image 大。

```powershell
docker compose --profile asr-tools build asr-tools
```

### 4. 確認 ASR dependencies 可 import

```powershell
docker compose --profile asr-tools run --rm asr-tools
```

看到以下訊息代表 profile 基本可用：

```text
asr dependencies ready
```

### 5. 確認 whisper CLI 可用

`asr-tools` image 會從 Breeze-ASR-25 使用的 whisper patch repository 安裝 `openai-whisper`，因此 image 建好後應可直接使用 `whisper` CLI。

```powershell
docker compose --profile asr-tools run --rm asr-tools whisper --help
```

### 6. 放入測試音訊

將音訊放到：

```text
data/raw/asr-samples/
```

例如：

```text
data/raw/asr-samples/sample.wav
```

不要提交這些檔案。

### 7. 執行 Breeze-ASR-25 轉錄

```powershell
docker compose --profile asr-tools run --rm asr-tools sh -lc "whisper data/raw/asr-samples/sample.wav --model breeze-asr-25 --output_format json --output_dir data/processed/asr-transcripts --language Chinese"
```

預期輸出：

```text
data/processed/asr-transcripts/sample.json
```

第一次執行可能會下載模型權重，時間會比較久。

### 8. 用系統 adapter 讀取逐字稿

`BreezeAsrCliTranscriber` 會呼叫 `whisper` 並讀取 Whisper JSON。若只想先驗證系統橋接，可用 fake/mock ASR 測試，不需要真實模型。

核心測試：

```powershell
docker compose run --rm app pytest tests/test_asr_research.py
```

完整測試：

```powershell
docker compose run --rm app pytest
```

## 本機 Python 替代流程

若不使用 Docker，可以在你自己的 Python 環境安裝：

```powershell
python -m pip install --upgrade pip
python -m pip install --upgrade transformers datasets[audio] accelerate torch
```

接著安裝 Breeze-ASR-25 使用的 whisper patch：

```powershell
python -m pip install git+https://github.com/Splend1d/whisper-patch-breeze.git@f94c6ba670a35ee8d720d4221e102f4685c288d6
```

執行：

```powershell
whisper data\raw\asr-samples\sample.wav --model breeze-asr-25 --output_format json --output_dir data\processed\asr-transcripts --language Chinese
```

## 整合位置

- ASR adapter：`src/personal_stock_investment_system/research/asr.py`
- Docker profile：`docker-compose.yml` 的 `asr-tools`
- 外部工具目錄：`tools/external/`
- 輸入音訊：`data/raw/`
- 輸出逐字稿：`data/processed/`
- ASR / Whisper 模型 cache：`data/local/asr-cache/`

後續 #29 會負責建立 YouTube 影片 / 音訊 artifact，#37 會把 Breeze-ASR-25 adapter 接成完整流程，#38 會把逐字稿交給 LLM analyzer。
