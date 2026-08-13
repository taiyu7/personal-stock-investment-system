# 路線圖

## 近期優先任務

1. 整理目前 Obsidian vault 架構，確認索引、系統設計、研究筆記、決策紀錄與 issue 拆解的分工。
2. 依 GitHub Issues #12 至 #17 搭建第一階段研究來源分析工具。
3. 後續再搭建公司盡職調查工具與財報分析工具。
4. 研究工具優先版完成後，再做 12 個預設 ticker 的資料完整性檢查。

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

- [ ] 建立公司盡職調查工具，支援產業、商業模式、競爭力、風險與估值問題拆解
- [ ] 建立財報分析工具，支援三大財報、關鍵比率、趨勢與異常項目檢查
- [ ] 建立第一階段研究來源分析工具，支援公開影片與 PDF 轉 Markdown，將選股邏輯整理成可追溯、可測試的規則
  - [x] #12 研究來源資料模型與固定 Markdown 報告模型。
  - [x] #13 PDF 轉 Markdown MVP：builtin fallback、PyMuPDF4LLM optional backend、`pdf-tools` Docker profile。
  - [ ] 真實投顧 PDF / 簡報 PDF 品質驗收。
  - [x] #14 公開 YouTube 影片匯入與逐字稿 fallback。
  - [x] #15 股票觀點分析與固定研究報告輸出。
  - [x] #16 研究報告輸出目的地設定。
  - [ ] #17 第一階段研究來源分析工具入口。
- [ ] 建立盤前分析、盤後復盤與交易紀律檢查模板
- [ ] 確認研究工具輸出可回寫或整理到 Obsidian 長期知識頁

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
