# 市場儀表板

這是一個使用 Python 與 Streamlit 製作的市場資料儀表板，用來快速查看全球股市、AI 半導體、總體經濟訊號與台灣市場的即時概況。

程式會透過 yfinance 下載市場資料，再使用 pandas 整理資料，最後由 Streamlit 產生可互動的網頁儀表板。畫面中會顯示每個標的的最新價格、漲跌幅、最近三個交易日的收盤價與相對前一交易日的漲跌幅，以及這三個交易日的 K 線趨勢圖。

## 功能

- 查看全球主要指數，例如 S&P 500、NASDAQ Composite、PHLX Semiconductor Index、KOSPI Composite。
- 查看 AI 與半導體相關股票，例如 NVIDIA、AMD、Broadcom、TSMC ADR。
- 查看總體經濟指標，例如 US Dollar Index、US 10Y Treasury Yield。
- 查看台灣市場資料，例如 TAIEX、TSMC Taiwan。
- 使用側邊欄調整歷史資料範圍與資料間隔。
- 每個標的只在畫面上呈現最近三個交易日的收盤價、相對前一交易日的漲跌幅與短期 K 線趨勢。
- 漲跌顏色採用台股習慣：紅色代表上漲，綠色代表下跌。
- 使用「重新整理資料」按鈕清除快取並重新抓取最新資料。

## 使用技術

- Python：主要開發語言。
- Streamlit：建立互動式網頁儀表板。
- Altair：繪製最近三個交易日的 K 線圖。
- pandas：整理與處理市場資料。
- yfinance：從 Yahoo Finance 取得股價與市場資料。

## 專案結構

```text
AutoDashboard/
├── app.py
├── requirements.txt
├── config/
│   └── watchlist.py
└── services/
    └── market_data.py
```

- `app.py`：Streamlit 應用程式入口，負責畫面呈現與互動控制。
- `config/watchlist.py`：設定儀表板要追蹤的市場分類、標的名稱與 ticker。
- `services/market_data.py`：負責透過 yfinance 抓取資料，並整理成儀表板需要的格式。
- `requirements.txt`：列出此專案需要安裝的 Python 套件。

## 安裝方式

請先確認電腦已安裝 Python。建議使用 Python 3.10 或更新版本。

進入專案資料夾：

```powershell
cd C:\Users\taiyu\OneDrive\桌面\stock\AutoDashboard
```

安裝需要的套件：

```powershell
python -m pip install -r requirements.txt
```

## 啟動方式

Streamlit 專案不能用 `python app.py` 啟動，必須使用 Streamlit 的啟動指令。

建議使用：

```powershell
python -m streamlit run app.py
```

如果你的環境可以直接使用 `streamlit` 指令，也可以執行：

```powershell
streamlit run app.py
```

啟動成功後，終端機會顯示類似下面的網址：

```text
Local URL: http://localhost:8501
```

在瀏覽器打開 `http://localhost:8501`，就可以看到市場儀表板。

## 常見問題

### 為什麼不能執行 `python app.py`？

因為 Streamlit 需要建立自己的網頁執行環境。直接用 `python app.py` 執行時，程式會缺少 Streamlit 的 runtime，因此可能看到 `missing ScriptRunContext` 或 `Session state does not function when running a script without streamlit run` 這類警告。

正確方式是：

```powershell
python -m streamlit run app.py
```

### 資料沒有更新怎麼辦？

畫面側邊欄有「重新整理資料」按鈕，按下後會清除 Streamlit 快取並重新抓取資料。

此專案也使用 `@st.cache_data(ttl=900)` 快取資料，代表同一組查詢條件在 900 秒內會優先使用快取，減少重複下載資料。

### 為什麼有些標的顯示沒有資料？

市場資料來自 yfinance。如果 Yahoo Finance 暫時無法提供資料、ticker 不支援指定週期，或網路連線不穩，畫面可能會顯示資料狀態訊息。這通常不是 Streamlit 本身的問題。

重點分工：
[app.py (line 1)]：只保留 Streamlit 設定、版本資訊、頁面路由。
[components/layout.py (line 1)]：頁首、右上角版本資訊、側邊欄、全域 CSS。
[components/market_cards.py (line 1)]：數字格式化、近期交易表、K 線圖、股票卡片。
[views/dashboard.py (line 1)]：市場交易儀表板頁面。
[views/changelog.py (line 1)]：開發歷程頁面。