# 路線圖

## 近期優先任務

1. #57 多檔 AI 推理 / NotebookLM-like 聚合：多份逐字稿或研究報告一起推理，輸出固定格式，例如高頻提及股票、多位分析師看好 / 看壞名單。
2. #58 台股上市櫃公司代號 / 公司名驗證：每天用固定清單修正逐字稿與研究報告中的股票提及。
3. #59 專有詞彙 / glossary：加入台股、半導體與投顧常用詞，例如 CoWoS，提升 ASR 與 AI 彙整品質。
4. 補上真實 YouTube CC / automatic captions adapter，讓有公開字幕的影片可不經 ASR 直接匯入逐字稿。
5. 設計 YouTube 會員影片 / 受限制影音來源的合法取得流程，特別是 Docker Dashboard 與 Windows Chrome profile 的邊界。
6. 使用真實投顧 PDF / 簡報 PDF 驗收 PDF to Markdown 品質，確認文字、頁碼、表格與圖表附近文字是否足夠分析。
7. 驗證研究報告輸出到 Obsidian inbox / 自選路徑後的整理流程，決定是否新增長期知識頁回寫規則。
8. 建立公司盡職調查工具與財報分析工具。
9. 研究工具優先版穩定後，再做 12 個預設 ticker 的資料完整性檢查。

## Phase 1：本機骨架

- [x] 建立根目錄
- [x] 建立 Git repo
- [x] 建立 README
- [x] 建立架構文件
- [x] 建立環境設定範本
- [x] 推送主 Repo 到 GitHub
- [x] 建立 GitHub Issue template
- [x] 建立 GitHub Project 作為任務看板

## Phase 1.5：知識庫與開發環境隔離

- [x] 確認沿用個人 Obsidian vault，實際路徑由本機設定或使用者輸出設定管理，不寫入公開文件。
- [x] 建立 Obsidian 基本目錄與系統索引
- [x] 定義 Obsidian 與 GitHub Issues 的分工
- [x] 將 GitHub remote 維運與開發環境注意事項記錄到內部知識庫
- [ ] 整理目前 Obsidian vault 架構，確認索引、系統設計、研究筆記、決策紀錄與 issue 拆解的分工
- [ ] 將必要的專案交接摘要同步到內部知識庫
- [x] 建立 Dockerfile、docker-compose.yml 與 .dockerignore
- [x] 確認 `docker compose run --rm app pytest` 可通過
- [x] 確認 `docker compose up dashboard` 可啟動 Streamlit Dashboard
- [x] 在 GitHub Actions 補上 Docker build 與 compose pytest 驗證
- [x] 更新 README 的 Docker 開發流程

## Phase 1.6：自動化測試補強

Docker 開發環境完成後，先補強自動化測試，再開始搭建後續工具。

- [x] 補強共用核心單元測試，涵蓋 provider、service、rules、repository 的錯誤與缺資料分支
- [x] 補 Dashboard smoke test，確認 Streamlit 服務可啟動並回應
- [x] 補 Docker-based CI 驗證，讓 GitHub Actions 同時檢查本機 Python 流程與 Docker 流程
- [x] 整理測試命令與驗收標準到 README

## Phase 1.7：研究工具優先

自動化測試穩定後，優先搭建直接支援投資研究的工具。這裡的「工具」優先指盡職調查、財報分析與影片分析，不是 MCP 或回測底層。

- [ ] 補真實 YouTube CC / automatic captions adapter，支援公開字幕匯入、語言選擇與清楚錯誤狀態
- [x] #24 重構研究來源 adapter 邊界，建立通用 import status/result，供後續 YouTube、本機影音、podcast 與截圖 adapter 共用
- [x] #45 OpenVINO ASR adapter，支援 OpenVINO Breeze-ASR-25 FP32 逐字稿輸出。
- [x] #47 Browser Session 媒體取得 adapter，支援 Selenium performance log discovery、yt-dlp download 與 FFmpeg WAV 前處理。
- [x] #49 Browser Session 到 ASR-ready WAV / OpenVINO ASR 一鍵 CLI 入口。
- [x] #50 OpenAI 音訊轉錄 provider，與 OpenVINO 並列，並支援長音訊 10 分鐘切段。
- [x] #51 研究彙整 provider 邊界與 Dashboard ASR JSON 匯入。
- [x] #55 OpenAI 研究彙整 API provider，失敗時回退本機規則。
- [x] #60 Dashboard UI 接上轉錄 provider，支援影片 URL -> 逐字稿 JSON -> 研究報告。
- [ ] 設計 YouTube 會員影片 / 受限制影音來源的合法取得流程；待使用者提供既有登入或素材取得機制後再細化
- [ ] 建立本機影片 / 音訊檔匯入與語音轉文字流程
- [ ] 建立 podcast 音頻匯入流程，先支援本機音訊，再評估 RSS / episode URL
- [ ] 技術分析圖面自動截圖：依時間戳擷取影片畫面，讓報告能引用圖面，不要求手工截圖
- [ ] 使用真實投顧 PDF / 簡報 PDF 進行品質驗收
- [ ] 建立公司盡職調查工具，支援產業、商業模式、競爭力、風險與估值問題拆解
- [ ] 建立財報分析工具，支援三大財報、關鍵比率、趨勢與異常項目檢查
- [ ] 建立第一階段研究來源分析工具，支援公開影片與 PDF 轉 Markdown，將選股邏輯整理成可追溯、可測試的規則
  - [x] #12 研究來源資料模型與固定 Markdown 報告模型。
  - [x] #13 PDF 轉 Markdown MVP：builtin fallback、PyMuPDF4LLM optional backend、`pdf-tools` Docker profile。
  - [ ] 真實投顧 PDF / 簡報 PDF 品質驗收。
  - [x] #14 公開 YouTube 影片匯入與逐字稿 fallback。
  - [x] #15 股票觀點分析與固定研究報告輸出。
  - [x] #16 研究報告輸出目的地設定。
  - [x] #17 第一階段研究來源分析工具入口。
- [ ] 建立盤前分析、盤後復盤與交易紀律檢查模板
- [ ] 確認研究工具輸出可回寫或整理到 Obsidian 長期知識頁

### Phase 1.7 目前限制

- YouTube：Dashboard 已可透過 browser media acquisition + ASR provider 處理公開影片；但尚未實際抓取 YouTube CC 或 automatic captions。
- Adapter 邊界：已建立通用 import status/result，可表達 `available`、`manual_fallback`、`transcript_unavailable`、`login_required`、`unsupported_source`、`media_unavailable`、`caption_language_unavailable` 與 `capture_unavailable`。
- 影音來源：公開影片 URL -> 逐字稿 -> 報告的 MVP 已可運行；本機影片、本機音訊、podcast、會員影片穩定 UI 流程與技術分析圖面截圖尚未完成；完整規劃見 `docs/research/media-source-ingestion-roadmap.md`。
- 會員影片：本機 CLI 可使用 Windows Chrome profile / cookie 與 yt-dlp remote components；Docker Dashboard 目前使用乾淨 headless Chromium，若來源需要登入，仍需後續設計 profile 掛載或合法素材提供流程。
- PDF：文字型 PDF 已有 builtin fallback；進階 PDF 可用 `pdf-tools` profile 的 PyMuPDF4LLM backend，但仍需真實投顧 PDF / 簡報 PDF 品質驗收。
- 分析器：本機 rule-based 與 OpenAI provider 已可用；Claude provider 尚未接真實 API。不確定內容仍應標記 `未判定` 或 `待查證`。
- 輸出：可輸出到 Obsidian inbox、自選路徑或不輸出本機檔案；長期知識頁整理規則尚未完成。

## Phase 2：資料層最小可用版

- [x] 選定第一個市場：台股為核心，美股與總經指標為參考
- [x] 選定第一個行情來源：yfinance 按需抓取
- [x] 建立 Dashboard 與 SQLite 每日復盤儲存
- [ ] 在 Docker、自動化測試與研究工具優先版完成後，驗證台股資料完整性，決定是否新增 TWSE、TPEx 或 FinMind provider
- [ ] 為回測標的建立可重現的歷史資料快照流程

## Phase 3：MCP 最小可用版

- [ ] 建立 MCP server 專案骨架與唯讀工具邊界
- [ ] 提供 `search_stock`
- [ ] 提供 `get_daily_prices`
- [ ] 提供 `get_market_summary`
- [ ] 提供 `get_daily_review`
- [ ] 撰寫本機啟動文件

## Phase 4：回測最小可用版

- [ ] 建立策略介面
- [ ] 建立第一個示範策略
- [ ] 建立績效統計
- [ ] 產生回測報告

## Phase 5：AI 工作流

- [ ] 建立盤前分析模板
- [ ] 建立盤後復盤模板
- [ ] 建立交易紀律檢查模板
- [ ] 建立多模型比較流程
