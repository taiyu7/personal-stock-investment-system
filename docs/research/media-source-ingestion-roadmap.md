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
   - 這類來源需要等使用者提供既有登入或素材取得機制後再設計。
   - 不先假設 cookie、瀏覽器 session、token 或特定下載方式。
   - 若使用瀏覽器登入狀態或既有爬蟲機制，必須明確記錄合法取得邊界、資料保存邊界與失敗狀態。
   - 不繞過付費牆、帳號權限、DRM 或平台限制；工具只分析使用者有權存取且合法取得的素材。

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

核心分析流程不應直接依賴任何單一平台或登入方式。所有 adapter 都應回傳明確狀態，而不是讓流程假裝成功。

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
