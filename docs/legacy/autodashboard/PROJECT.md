# Market Dashboard

## 目標

建立一個每日市場觀察 Dashboard，用來快速判斷隔日台股開盤前的國際市況、AI 指標股、總經環境與台股相關夜盤狀態。

第一版先在本機執行，之後再考慮部署到免費雲端。

## 技術

- Python
- Streamlit
- Pandas
- yfinance

## Dashboard 區塊

### 1. 前日國際市況

追蹤：

- S&P 500
- NASDAQ
- SOX 費半
- KOSPI 韓股

顯示：

- 最新價格
- 漲跌
- 漲跌幅
- 簡短結論

### 2. 美股 AI 指標股

追蹤：

- NVDA
- AMD
- AVGO
- TSM ADR

顯示：

- 最新價格
- 漲跌
- 漲跌幅
- 簡短結論

### 3. 總經市況

追蹤：

- 美元指數 DXY
- 美國 10 年期公債殖利率

顯示：

- 最新數值
- 漲跌
- 漲跌幅
- 簡短結論

### 4. 台股相關

追蹤：

- 台指夜盤
- 持股事件，第一版可先手動輸入

顯示：

- 最新價格
- 漲跌
- 漲跌幅
- 簡短結論

## MVP 功能

第一版先完成：

1. 建立 Streamlit 頁面
2. 使用 yfinance 抓取資料
3. 用表格呈現各區塊數據
4. 自動計算漲跌與漲跌幅
5. 顯示簡單結論
6. 支援本機執行

## 建議目錄結構

```text
market-dashboard/
├── app.py
├── requirements.txt
├── PROJECT.md
├── TODO.md
├── DECISIONS.md
├── config/
│   └── watchlist.py
└── services/
    └── market_data.py