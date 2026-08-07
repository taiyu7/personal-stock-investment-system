# Decisions

## 2026-06-11

### 專案方向

先建立本機版市場 Dashboard，不先處理付費雲端部署。

原因：

- 本機最快能完成 MVP
- 不需要先處理帳號、部署、排程問題
- 可以先確認資料來源與畫面是否符合需求

### 技術選型

使用：

- Python
- Streamlit
- Pandas
- yfinance

原因：

- Streamlit 適合快速做資料 Dashboard
- Python 抓金融資料與資料整理方便
- yfinance 適合第一版快速驗證

### 資料來源策略

第一版先使用 yfinance。

注意：

- yfinance 不是正式交易所 API
- 適合個人研究與 MVP
- 若未來要更穩定，需改接交易所、券商或付費資料源

### 部署策略

第一版：

- 本機執行

未來：

- 若需要雲端，優先考慮免費的 Streamlit Community Cloud
- 若資料排程與自動化需求變強，再考慮 VPS 或雲端主機

### Dashboard 判斷方式

第一版先使用規則式判斷，不使用 AI 自動分析。

原因：

- 規則清楚
- 可回測
- 比較不會產生幻覺
- 適合交易前檢查表