# 第一階段研究來源分析工具規格

## 目標

建立第一階段研究工具，將公開影片與 PDF 轉成可分析的 Markdown/text，再整理成固定格式的股票研究報告。

第一階段優先解決兩個痛點：

- 使用者沒有足夠時間看完整影片，需要快速掌握影片中提到的股票、觀點、依據與技術分析。
- 使用者收到的文字資料多為 PDF，需要先轉成 Markdown，才能進入同一套研究分析流程。

本階段重點是「研究來源轉 Markdown」與「投資觀點結構化」，不是會員影片自動下載、NotebookLM 替代品、回測系統或 MCP。

## 使用情境

### 公開影片分析

使用者貼上一段公開 YouTube 影片連結。系統取得影片資訊與可用文字內容，整理出：

- 哪個人對哪一檔股票有什麼評價，是偏多、偏空或中性。
- 評價依據是什麼。
- 哪些股票彼此或與哪些公司、產業、族群有關聯。
- 提到的公司是做什麼的。
- 是否有技術分析；若有，對應的圖面、型態、價量訊號或均線位置是什麼。

### PDF 前處理與分析

使用者提供 PDF。系統先將 PDF 轉成 Markdown，再進入同一套分析流程。

PDF 可能來自：

- 研究報告
- 投顧講義
- 影片逐字稿匯出
- 簡報
- 財報或公司說明資料

## 第一階段輸入

### 共用來源欄位

所有來源先轉成共同資料結構。

```text
source_id
source_type
title
source_url
publisher
speaker
speakers
published_date
collected_at
language
raw_text
markdown_text
source_locator
notes
```

欄位說明：

- `source_id`：本機產生的來源 ID。
- `source_type`：`youtube_public`、`pdf`、`manual_text`。
- `title`：影片或 PDF 標題。
- `source_url`：YouTube URL 或原始來源 URL；本機 PDF 可留空。
- `publisher`：頻道、機構或發布者。
- `speaker`：單一講者或主持人；未知時可留空。
- `speakers`：多位講者、來賓或研究員；例如電視節目可列主持人與多位來賓。
- `published_date`：發布日期；未知時可留空。
- `collected_at`：系統匯入日期。
- `language`：例如 `zh-TW`。
- `raw_text`：原始抽取文字。
- `markdown_text`：整理後 Markdown。
- `source_locator`：可追溯位置，例如影片時間戳或 PDF 頁碼。
- `notes`：使用者補充說明。

### YouTube 公開影片輸入

第一階段支援：

```text
youtube_url
optional_title
optional_speaker
optional_notes
```

系統應嘗試取得：

- 影片標題
- 頻道名稱
- 發布日期
- 影片長度
- 可用逐字稿或字幕文字

若無法取得逐字稿，第一階段允許降級為：

- 使用者手動貼上逐字稿。
- 使用者提供其他文字摘要。
- 標記為 `transcript_unavailable`，不強行分析。

### PDF 輸入

第一階段支援：

```text
pdf_path
optional_title
optional_source_url
optional_publisher
optional_speaker
optional_notes
```

PDF 轉 Markdown 時應盡量保留：

- 頁碼
- 標題層級
- 段落
- 表格
- 圖表附近文字

第一階段不要求完美還原版面，但必須保留足夠定位資訊，讓後續報告可以引用「第幾頁」。

## 第一階段輸出

輸出一份 Markdown 研究報告。

```markdown
# 研究來源分析報告

## 來源資訊

- 類型：
- 標題：
- 來源：
- 發布者：
- 講者：
- 日期：
- 匯入時間：

## 一句話摘要

## 人物對股票的評價

| 人物 | 股票 | 公司 | 方向 | 評價 | 依據 | 原文位置 | 信心 |
|---|---|---|---|---|---|---|---|

## 股票與族群關聯

| 股票 | 公司 | 相關族群 | 關聯公司/供應鏈 | 關聯理由 | 原文位置 |
|---|---|---|---|---|---|

## 提到的公司是做什麼的

| 股票 | 公司 | 主要業務 | 產品/服務 | 客戶/市場 | 待查證 | 原文位置 |
|---|---|---|---|---|---|---|

## 技術分析

| 股票 | 技術訊號 | 對應圖面 | 判斷依據 | 原文位置 | 待補資料 |
|---|---|---|---|---|---|

## 可驗證假設

| 假設 | 需要資料 | 可否回測 | 初步規則 | 信心 |
|---|---|---|---|---|

## 風險與反例

## 待查問題

## 後續行動
```

## 輸出目的地

第一階段產生的是標準 Markdown 報告，但輸出目的地不應寫死。

預設輸出兩份：

- Obsidian inbox：可設定為使用者自己的 Obsidian inbox 或其他知識庫資料夾，作為待整理研究來源。
- 自選路徑：預設為使用者桌面，後續可在 UI 或設定中改成其他資料夾。

使用者可以調整輸出策略：

- 同時輸出到 Obsidian inbox 與自選路徑。
- 只輸出到 Obsidian inbox。
- 只輸出到自選路徑。
- 都不要輸出成檔案，只在介面顯示或提供一次性下載。

Obsidian 是個人知識整理入口，不是唯一輸出管道。需要分享給別人時，應使用自選路徑或下載檔案產生獨立 Markdown；後續可再擴充 PDF、HTML 或雲端同步輸出。

建議檔名格式：

```text
YYYY-MM-DD_來源類型_標題摘要.md
```

例如：

```text
2026-08-13_youtube_public_AI伺服器與台股供應鏈.md
```

## 分析規則

### 人物對股票的評價

系統應嘗試抽取：

- 人物名稱
- 股票名稱或代號
- 偏多、偏空或中性方向
- 明確評價
- 評價依據
- 原文位置
- 信心等級

方向定義：

- `偏多`：講者認為公司、股價、題材或技術面有正向機會。
- `偏空`：講者認為有下跌、風險、衰退、估值過高或題材退潮。
- `中性`：僅描述事實、等待確認，或多空條件尚未成立。
- `未判定`：文字不足以判斷。

### 股票與族群關聯

系統應整理台股常見的族群性，例如：

- AI 伺服器
- 半導體
- IC 設計
- PCB
- 散熱
- 軍工
- 電動車
- 生技
- 金融
- 航運

若族群由講者明確提及，標記為「原文提及」。

若族群由系統根據公司業務推論，標記為「系統推論」，並降低信心。

### 公司業務說明

公司業務可來自：

- 來源文字明確描述
- 系統既有公司資料庫
- 後續查證資料

第一階段若沒有公司資料庫，允許先輸出：

```text
待查證：來源未說明公司主要業務。
```

不要用模型記憶直接產生看似確定的公司介紹；若是模型推論，必須標示不確定性。

### 技術分析

系統應抓出與圖面或技術型態有關的描述，例如：

- 突破
- 回測
- 均線
- 季線
- 月線
- 成交量放大
- 爆量
- 帶量長紅
- 跳空
- 箱型整理
- 頭部
- 底部
- 壓力
- 支撐

第一階段不需要自動截圖或讀取影片畫面。

若講者提到「這張圖」、「這裡」、「這根 K」但文字不足以辨識圖面，輸出：

```text
需要人工補圖：原文提到圖面，但逐字稿未包含畫面資訊。
```

## 非目標

第一階段不做：

- 會員影片自動下載。
- 繞過付費牆、帳號權限、DRM 或平台限制。
- 自動下單。
- 回測。
- MCP server。
- NotebookLM 替代品。
- 多影片知識庫問答。
- 自動驗證所有公司基本資料。
- 自動產生投資建議或買賣清單。

## 法律與資料邊界

工具只分析使用者有權存取的內容。

公開 YouTube 影片仍受平台條款與著作權限制。第一階段只保存研究摘要、引用位置與使用者自己的分析，不保存或散布完整受保護內容。

會員影片、付費內容或受限制內容在後續階段若要支援，必須另行確認合法取得方式。cookie 或登入 session 只能視為取得素材的 adapter，不應成為核心分析流程的一部分。

## 建議模組

```text
src/personal_stock_investment_system/research/
  __init__.py
  sources.py
  pdf.py
  youtube.py
  analysis.py
  markdown.py
  output.py
  entrypoint.py
```

責任分工：

- `sources.py`：共用資料模型。
- `pdf.py`：PDF 轉 Markdown。
- `youtube.py`：公開 YouTube metadata 與可用文字來源匯入。
- `analysis.py`：將 Markdown/text 轉成研究報告資料結構。
- `markdown.py`：將研究報告資料結構輸出成 Markdown。
- `output.py`：研究報告輸出目的地設定與 Markdown 檔案寫入。
- `entrypoint.py`：第一階段研究來源分析工具的共用入口，供 Streamlit 或未來 CLI 重複使用。

## 目前實作狀態

截至 2026-08-13，主 Repo 已完成第一階段研究來源分析工具的 MVP 骨架：

- #12：`src/personal_stock_investment_system/research/sources.py` 定義 `ResearchSource`、`ResearchReport`、`SourceReference`、`StockOpinion`、`StockRelation`、`CompanyProfileNote`、`TechnicalAnalysisNote`、`VerifiableHypothesis`。
- #12：`markdown.py` 可將 `ResearchReport` 轉成固定格式 Markdown，並支援多位 `speakers` 顯示為「講者／來賓」。
- #12：`docs/research/sample-research-report.md` 提供人工驗收範例。
- #13：`pdf.py` 提供 `pdf_to_markdown()`、`extract_text_pages()`、`build_pdf_research_source()`。
- #13：PDF backend 支援 `builtin` 與 `pymupdf4llm`。`builtin` 是最小本地 fallback；`pymupdf4llm` 是 optional backend。
- #13：`docker-compose.yml` 已新增 `pdf-tools` profile，可建立含 PyMuPDF4LLM 的獨立 Docker image，不拖重日常 `app` / `dashboard` image。
- #14：`youtube.py` 可解析公開 YouTube URL 的 video id，並提供 metadata/transcript adapter 介面、手動文字 fallback 與 `transcript_unavailable` 狀態。
- #15：`analysis.py` 可用保守 rule-based 流程，從固定逐字稿/text 產生 `ResearchReport`，包含人物觀點、族群關聯、公司業務、技術分析、可驗證假設、風險與待查問題。
- #16：`output.py` 定義輸出目的地設定，支援 Obsidian inbox、自選路徑、兩者都輸出、只輸出其一，或不輸出本機檔案。
- #17：`entrypoint.py` 與 Streamlit sidebar「研究來源分析」頁面提供第一階段操作入口，支援手動文字、PDF 路徑與公開 YouTube URL。

已驗證：

- `docker compose run --rm app pytest`：40 passed。
- `docker compose --profile pdf-tools build pdf-tools`：成功。
- `docker compose --profile pdf-tools run --rm pdf-tools`：顯示 `pymupdf4llm ready`。
- `docker compose --profile pdf-tools run --rm pdf-tools pytest tests/test_pdf_research.py`：5 passed。

尚未完成：

- 使用真實投顧 PDF / 簡報 PDF 進行品質驗收。
- OCR / 掃描 PDF 品質驗收。
- 真實 YouTube CC / automatic captions adapter。現行 `TranscriptUnavailableYouTubeClient` 是安全 fallback，不會實際讀取 YouTube 字幕；即使影片有 CC，入口也會顯示 `transcript_unavailable`，除非未來接上真實 adapter 或使用者手動貼逐字稿。
- YouTube 字幕語言選擇、人工 CC 與自動字幕狀態辨識。
- PDF 文字品質與版面品質的真實樣本驗收。
- 將研究工具輸出回寫或整理到 Obsidian 長期知識頁的流程。
- CLI 入口；目前可操作入口是 Streamlit sidebar 頁面。

## 建議資料模型

```text
ResearchSource
ResearchReport
StockOpinion
StockRelation
CompanyProfileNote
TechnicalAnalysisNote
VerifiableHypothesis
SourceReference
```

### SourceReference

```text
source_id
locator_type
locator
quote
confidence
```

`locator_type` 可為：

- `timestamp`
- `page`
- `section`
- `unknown`

## 驗收標準

第一階段完成時，應能做到：

- 給定一段固定測試逐字稿，產生固定格式 Markdown 報告。
- 給定一個文字型 PDF，轉成包含頁碼的 Markdown。
- 預設可同時輸出到 Obsidian inbox 與使用者自選路徑。
- 可設定為不輸出本機檔案，只在介面顯示或提供一次性下載。
- 分析報告包含人物觀點、股票族群、公司業務、技術分析、可驗證假設。
- 每個抽取結果盡量帶有來源位置。
- 無法判斷的內容會標示 `未判定` 或 `待查證`，不假裝確定。
- 測試不依賴真實 YouTube 網路結果。
- 真實 YouTube 整合測試若要加入，必須與純核心測試分開。

## 開發順序

1. 建立 `ResearchSource` 與 `ResearchReport` 資料模型。
2. 建立 Markdown 輸出模板。
3. 使用固定文字樣本撰寫分析輸出測試。
4. 實作 PDF 轉 Markdown 的最小版本。
5. 實作手動文字輸入到研究報告的純核心流程。
6. 加入公開 YouTube metadata 匯入與 fallback 狀態。
7. 實作輸出目的地設定，預設輸出到 Obsidian inbox 與桌面自選路徑。
8. 加入 Streamlit sidebar 操作入口。
9. 補真實 YouTube CC / automatic captions adapter，並把網路整合測試與純核心測試分開。
10. 使用真實投顧 PDF / 簡報 PDF 驗收 PDF 轉 Markdown 品質。
11. 再評估音訊轉錄與會員影片取得素材流程。

## 後續階段

### 第二階段：影音來源匯入與轉錄

當公開影片沒有逐字稿時，支援更多合法取得的影音素材，轉錄成文字後進入同一套流程。這條主線包含：

- 真實公開 YouTube CC / automatic captions adapter。
- YouTube 會員影片 / 受限制影音來源的合法取得流程；待使用者提供既有登入或素材取得機制後再細化。
- 本機影片 / 音訊檔匯入與語音轉文字。
- Podcast 音頻匯入。
- 技術分析圖面自動截圖：當逐字稿提到「這張圖」、「這裡」、「這根 K」等圖面時，依時間戳擷取影片畫面，不要求使用者手工截圖。

詳細規劃請見 `docs/research/media-source-ingestion-roadmap.md`。

### 第三階段：批次分析

支援一天約 10 份來源的批次分析，產生：

- 單篇研究報告
- 當日彙整報告
- 重複出現股票
- 重複出現族群
- 多位講者觀點比較

### 第四階段：Obsidian 與 NotebookLM 分工

本系統負責把來源整理成乾淨、固定格式、可追溯的 Markdown。

Obsidian 保存長期知識、公司研究與策略假設。

NotebookLM 可作為多份報告的二次閱讀與問答工具，不作為第一階段必要依賴。
