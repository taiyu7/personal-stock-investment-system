# Tests

這裡放自動化測試。目前涵蓋行情資料正規化、資料缺漏與 provider 錯誤處理、訊號判斷、每日復盤儲存、研究來源 Markdown 報告模型、文字型 PDF 轉 Markdown、PyMuPDF4LLM optional backend、本機 ASR adapter fake/mock 測試、Dashboard 資料表的防呆邏輯，以及 Streamlit Dashboard 啟動 smoke test。

預設用 Docker 執行：

```powershell
docker compose run --rm app pytest
```

若使用本機 Python fallback：

```powershell
pytest
```

一般測試不依賴 Breeze-ASR-25 真實模型、大型音訊檔或外部 LLM API；真實 ASR 驗收應與核心測試分開執行。
