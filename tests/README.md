# Tests

這裡放自動化測試。目前涵蓋行情資料正規化、資料缺漏與 provider 錯誤處理、訊號判斷、每日復盤儲存、Dashboard 資料表的防呆邏輯，以及 Streamlit Dashboard 啟動 smoke test。

預設用 Docker 執行：

```powershell
docker compose run --rm app pytest
```

若使用本機 Python fallback：

```powershell
pytest
```
