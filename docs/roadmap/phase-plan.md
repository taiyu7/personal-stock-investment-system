# 路線圖

## Phase 1：本機骨架

- [x] 建立根目錄
- [x] 建立 Git repo
- [x] 建立 README
- [x] 建立架構文件
- [x] 建立環境設定範本

## Phase 2：資料層最小可用版

- [x] 選定第一個市場：台股為核心，美股與總經指標為參考
- [x] 選定第一個行情來源：yfinance 按需抓取
- [x] 建立 Dashboard 與 SQLite 每日復盤儲存
- [ ] 驗證台股資料完整性，決定是否新增 TWSE、TPEx 或 FinMind provider
- [ ] 為回測標的建立可重現的歷史資料快照流程

## Phase 3：MCP 最小可用版

- [ ] 建立 MCP server 專案
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
