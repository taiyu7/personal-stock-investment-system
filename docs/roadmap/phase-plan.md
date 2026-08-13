# 路線圖

## 近期優先任務

1. 補上真實 YouTube CC / automatic captions adapter，讓有公開字幕的影片能實際匯入逐字稿；純核心測試仍使用 fake/mock，真實網路驗收放 integration。
2. 設計 YouTube 會員影片 / 受限制影音來源的合法取得流程；待使用者提供既有登入或素材取得機制後再細化。
3. 建立影音來源匯入與轉錄 roadmap，後續支援本機影片、本機音訊、podcast 與技術分析圖面自動截圖。
4. 使用真實投顧 PDF / 簡報 PDF 驗收 PDF to Markdown 品質，確認文字、頁碼、表格與圖表附近文字是否足夠分析。
5. 驗證研究報告輸出到 Obsidian inbox / 自選路徑後的整理流程，決定是否新增長期知識頁回寫規則。
6. 建立公司盡職調查工具與財報分析工具。
7. 研究工具優先版穩定後，再做 12 個預設 ticker 的資料完整性檢查。

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

- [x] 確認沿用既有 Obsidian vault：`C:\Users\taiyu\Obsidian\個人理財資訊系統`
- [x] 建立 Obsidian 基本目錄與系統索引
- [x] 定義 Obsidian 與 GitHub Issues 的分工
- [x] 將本機 GitHub 帳號切換與 remote 維運方式記錄到 Obsidian
- [ ] 整理目前 Obsidian vault 架構，確認索引、系統設計、研究筆記、決策紀錄與 issue 拆解的分工
- [ ] 將必要的 AI context 摘要同步到既有 Obsidian vault
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

- YouTube：目前入口會解析公開 URL 並顯示 `transcript_unavailable` fallback；尚未實際抓取 YouTube CC 或 automatic captions。
- 影音來源：本機影片、本機音訊、podcast、會員影片與技術分析圖面截圖尚未實作；完整規劃見 `docs/research/media-source-ingestion-roadmap.md`。
- 會員影片：不先假設 cookie 或瀏覽器 session；待使用者提供既有登入 / 爬蟲 / 取得素材機制後，再設計 adapter 與合法邊界。
- PDF：文字型 PDF 已有 builtin fallback；進階 PDF 可用 `pdf-tools` profile 的 PyMuPDF4LLM backend，但仍需真實投顧 PDF / 簡報 PDF 品質驗收。
- 分析器：目前是保守 rule-based MVP，只根據來源文字抽取，不使用模型記憶補公司基本面；不確定內容會標記 `未判定` 或 `待查證`。
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
