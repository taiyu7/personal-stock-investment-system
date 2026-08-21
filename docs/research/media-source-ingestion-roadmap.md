# 影音來源匯入與轉錄 Roadmap

## 目標

建立可長期擴充的影音來源匯入能力，讓投資研究工具可以處理公開 YouTube、受限制或會員影片、本機影片、本機音訊與 podcast 音頻，並把可用文字、時間戳與圖面線索整理進同一套 `ResearchSource -> ResearchReport -> Markdown output` 流程。

這條主線不只補 YouTube CC，而是把「影音素材取得、轉錄、圖面截取、來源定位與合法邊界」拆成可測試、可替換的 adapter。

## 優先順序

1. **真實公開 YouTube 字幕 adapter**
   - 讀取公開影片的人工 CC 與 automatic captions。
   - 支援語言優先序：`zh-TW`、`zh-Hant`、`zh`、`en`。
   - 清楚區分：有字幕、字幕停用、影片不可用、需要登入、網路失敗、語言不存在。
   - 純核心測試使用 fake/mock；真實 YouTube 驗收放 integration，不混入一般單元測試。

2. **YouTube 會員影片 / 受限制影片**
   - 參考舊 Selenium crawler：`C:\Github\Python Selenium Crawler\seleniumScreenShot-fullPageAndYoutubeAndm3u8.py`。
   - 不再把流程設計成反覆手動更新 cookie 或長期保存 m3u8。
   - 使用專用 Chrome profile 或既有瀏覽器 session，進頁面後即時嗅探 m3u8 / media request。
   - 嗅探到短效 m3u8 後立刻交給 yt-dlp / ffmpeg 下載，不把短效 URL 當長期資料保存。
   - 輸出影片 / 音訊 artifact 到 `data/raw/`，再交給 FFmpeg 轉 16kHz mono WAV。
   - 以 #47 追蹤 Browser Session 媒體取得流程。

3. **本機影片 / 音訊匯入**
   - 支援使用者提供本機影片檔或音訊檔路徑。
   - 從影片抽取音訊後進行語音轉文字。
   - 保留來源定位：檔案路徑、檔名、時間戳。
   - 測試使用 mock 或小型 fixture，不把大型媒體檔提交到 Git。

4. **Podcast 音頻匯入**
   - 先支援本機 podcast 音訊檔。
   - 後續再評估 podcast RSS feed、episode URL 或下載流程。
   - 轉錄後沿用相同研究報告分析與輸出流程。

5. **技術分析圖面自動截圖**
   - 當逐字稿提到「這張圖」、「這裡」、「這根 K」、「突破」、「支撐」、「壓力」等圖面語境時，不應要求使用者手工截圖。
   - 需要建立影片時間戳到截圖的流程，保留截圖檔案、時間戳與文字引用的關聯。
   - 後續研究報告應能引用「文字逐字稿 + 對應圖面截圖」。
   - 第一版可先支援本機影片或可合法取得的影片檔；公開 YouTube / 會員影片截圖需依素材取得 adapter 的合法邊界處理。

## Adapter 邊界

未來影音來源應拆成幾個獨立 adapter：

- `transcript adapter`：取得字幕或轉錄文字。
- `media file adapter`：讀取本機影片 / 音訊檔 metadata。
- `audio extraction adapter`：從影片抽音訊。
- `speech-to-text adapter`：將音訊轉成逐字稿。
- `frame capture adapter`：依時間戳擷取影片畫面。
- `restricted source adapter`：受限制來源的合法取得流程；待使用者提供既有機制後設計。
- `browser session provider`：管理專用 Chrome profile 或既有瀏覽器 session，避免每次手動匯出 cookie。
- `media discovery adapter`：打開頁面、觸發播放、從 browser performance log 即時取得 m3u8 / media request。
- `download adapter`：用 yt-dlp / ffmpeg 下載剛嗅探到的媒體 artifact。

核心分析流程不應直接依賴任何單一平台或登入方式。所有 adapter 都應回傳明確狀態，而不是讓流程假裝成功。

2026-08-14 更新：#24 已完成第一步 adapter 邊界小重構。核心模型已新增通用來源匯入狀態與 `ResearchSourceImportResult`，YouTube fallback 與 phase-one entrypoint 已改用此結果結構，同時維持 #12 至 #17 既有行為。

2026-08-16 更新：已開 #47，目標是把舊 Selenium crawler 的瀏覽器 session / m3u8 嗅探能力拆成正式 media acquisition flow。設計重點是不保存短效 m3u8，而是每次下載當下進頁面嗅探最新 media URL，立刻下載並輸出 artifact，後續接 #45 OpenVINO ASR adapter。

## 狀態分類

影音匯入流程至少應能回傳：

- `available`：可取得文字或媒體素材。
- `manual_fallback`：使用者提供手動逐字稿、摘要或本機素材。
- `transcript_unavailable`：未取得字幕或轉錄文字。
- `login_required`：來源需要登入或會員權限。
- `unsupported_source`：來源類型尚未支援。
- `media_unavailable`：影片或音訊不可用。
- `caption_language_unavailable`：有字幕但沒有指定語言。
- `capture_unavailable`：無法擷取對應圖面。

## 測試策略

- 純單元測試：使用 fake/mock adapter，不依賴真實 YouTube、podcast、瀏覽器登入或大型媒體檔。
- integration 測試：可選擇少量公開影片 / 公開 podcast / 小型本機媒體 fixture，並與一般 CI 分離。
- 受限制或會員來源：不進 CI；只做本機人工驗收，且必須由使用者確認合法存取方式。

## 近期建議 GitHub Issues

- 真實公開 YouTube CC / automatic captions adapter。
- 本機影片 / 音訊檔匯入與轉錄入口。
- 技術分析圖面時間戳截圖 MVP。
- Podcast 音頻來源匯入。
- 會員影片 / 受限制影音來源合法取得流程設計。
- Browser Session 媒體取得流程：即時嗅探 m3u8 並交給 ASR pipeline（#47）。

## #47 Browser Session Media Acquisition Adapter

2026-08-16 實作第一版 adapter 邊界，目標是把舊 Selenium crawler 裡「瀏覽器 performance log 嗅探 m3u8」的能力，收斂成可測、可替換的 research media pipeline：

```text
browser session / Chrome performance log
  -> extract m3u8 or media request
  -> yt-dlp download adapter
  -> FFmpeg 16 kHz mono WAV adapter
  -> #45 OpenVINO ASR adapter
```

已新增程式：

- `src/personal_stock_investment_system/research/media.py`
  - `DiscoveredMediaRequest`
  - `MediaArtifact`
  - `MediaAcquisitionResult`
  - `ChromePerformanceLogMediaDiscovery`
  - `SeleniumBrowserMediaDiscovery`
  - `SeleniumBrowserSessionConfig`
  - `YtDlpMediaDownloader`
  - `FfmpegAudioPreprocessor`
  - `BrowserSessionMediaAcquirer`
- `tests/test_media_acquisition.py`
  - 測試 Chrome performance log m3u8 擷取。
  - 測試 stream manifest 選取。
  - 測試 browser session media acquisition orchestration。
  - 測試 yt-dlp / ffmpeg shell-free command construction。

目前這一版已提供 `SeleniumBrowserMediaDiscovery` 作為真正開啟既有 Chrome profile 的 discovery client；Selenium runtime 採延遲 import，因此一般單元測試不需要安裝瀏覽器工具。下一步是把這個 discovery client 接成 CLI / entrypoint，讓 URL 可以一路產生 WAV path，再交給 #45 OpenVINO ASR adapter。

驗證結果：

```powershell
python -m compileall src\personal_stock_investment_system\research tests\test_media_acquisition.py
docker compose run --rm app pytest tests/test_media_acquisition.py tests/test_asr_research.py
```

Docker 測試結果：`16 passed`。

## #49 Browser Session 到 OpenVINO ASR 一鍵入口

2026-08-16 已開 #49：`https://github.com/taiyu7/personal-stock-investment-system/issues/49`

第一版入口已新增：

- `src/personal_stock_investment_system/research/browser_asr.py`
  - `BrowserSessionAsrInput`
  - `BrowserSessionAsrResult`
  - `run_browser_session_asr_pipeline()`
- `src/personal_stock_investment_system/research/browser_asr_cli.py`
- console script：`psis-browser-asr`
- `tests/test_browser_asr_entrypoint.py`

命令用途：

```text
URL
  -> SeleniumBrowserMediaDiscovery
  -> BrowserSessionMediaAcquirer
  -> yt-dlp download
  -> FFmpeg 16 kHz mono WAV
  -> optional OpenVINO ASR
  -> optional ResearchSourceImportResult
```

入口支援兩種模式：

- 不傳 `--openvino-model-dir`：只產生 ASR-ready WAV。
- 傳 `--openvino-model-dir`：產生 WAV 後接 OpenVINO ASR，並建立 local audio research source import result。

驗證結果：

```powershell
python -m compileall src\personal_stock_investment_system\research tests\test_browser_asr_entrypoint.py
docker compose run --rm app pytest tests/test_browser_asr_entrypoint.py tests/test_media_acquisition.py tests/test_asr_research.py
docker compose run --rm app python -m personal_stock_investment_system.research.browser_asr_cli --help
```

Docker 測試結果：`18 passed`。

2026-08-16 本機驗證補充：

- Chrome 151 需要對應 ChromeDriver 151；舊 Selenium crawler 的 ChromeDriver 139 不適用。
- Windows 本機 Selenium 需要 `--no-sandbox`、停用 GPU/Vulkan automation 路徑與 `--remote-debugging-pipe`，否則會遇到 Chrome/tab crash。
- YouTube UI 音效 request 需排除，例如 `/s/search/audio/*.mp3`；真正媒體 request 通常是 `googlevideo.com/videoplayback`。
- YouTube 會員影片裸 `videoplayback` URL 可能 403；實測成功路線是讓 yt-dlp 使用 page URL、Chrome profile cookie 與 `--remote-components ejs:github`。
- 成功產出：`data/processed/asr-audio/browser-test-cli-cookie-16k-mono.wav`，格式為 PCM signed 16-bit little-endian、16 kHz、mono，長度約 44:03。
- Docker 相關單元測試：`19 passed`。
- OpenVINO adapter 長音檔補充：直接把 3 分 20 秒 WAV 丟進 OpenVINO `generate()` 只會得到前段短稿；已改為預設 25 秒分段轉錄，`sample-video-16k-mono.wav` 實測產生 8 個 timestamped segments，文字覆蓋 0.0 到 199.808 秒。
- Docker 相關單元測試更新：`20 passed`。

## #51 研究彙整 Provider 與 Dashboard MVP

2026-08-22 已開始 #51：`https://github.com/taiyu7/personal-stock-investment-system/issues/51`

第一版 MVP 先把 #49 的輸出接進 Dashboard，而不是直接接付費 API：

```text
#49 transcript JSON
  -> ResearchSource(local_audio)
  -> analysis provider boundary
  -> Markdown research report
  -> Dashboard display / download / output destinations
```

目前 provider 狀態：

- `rule_based_fallback`：已可用，沿用既有本機規則分析。
- `openai`：已在 provider 邊界與 Dashboard 選項中保留，但尚未接真實 API；目前會明確標示未支援並回退本機規則。
- `anthropic_claude`：已在 provider 邊界與 Dashboard 選項中保留，但尚未接真實 API；目前會明確標示未支援並回退本機規則。

已新增能力：

- `ResearchAnalysisSettings`
- `ResearchAnalysisResult`
- `ResearchAnalysisClient`
- `analyze_research_source_with_provider()`
- `load_asr_transcription_result()`
- `build_transcript_json_research_source()`
- Dashboard「研究來源分析」新增 `ASR 逐字稿 JSON` 來源類型與彙整 provider 選擇。

下一步才接真實 OpenAI / Claude API adapter，並補 secrets、usage / cost metadata、schema validation 與重試策略。
