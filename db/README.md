# 資料庫 schema 與 migration 策略

本文定義目前已實作的資料庫狀態，以及未來擴充 schema 與 migration 時的原則。現階段資料庫只保存個人每日復盤資料；市場行情、財報、回測快照與交易明細都還沒有建立正式資料表。

## 現行資料庫

- 預設資料庫：SQLite。
- 預設路徑：`data/local/personal-stock-investment.db`。
- 設定入口：`.env.example` 的 `DATABASE_URL=sqlite:///data/local/personal-stock-investment.db`。
- 現行 repository：`src/personal_stock_investment_system/storage/daily_reviews.py`。

目前 Dashboard 只接受 `sqlite:///` URL。MySQL 與 PostgreSQL 是未來擴充方向，尚未實作 adapter。

## 現行 schema

`daily_reviews` 由 `DailyReviewRepository.save()` 在第一次儲存時建立。

```sql
CREATE TABLE IF NOT EXISTS daily_reviews (
    trade_date TEXT PRIMARY KEY,
    fields_json TEXT NOT NULL,
    markdown TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

欄位說明：

- `trade_date`：交易日期，文字格式，作為 primary key。
- `fields_json`：Dashboard 表單欄位的 JSON 字串，使用 UTF-8 儲存中文內容。
- `markdown`：由復盤欄位產生的 Markdown 內容。
- `updated_at`：UTC ISO 8601 更新時間。

儲存策略是 upsert；同一個 `trade_date` 再次儲存會覆寫 `fields_json`、`markdown` 與 `updated_at`。

## 資料邊界

SQLite 目前只保存使用者主動填寫的復盤內容與產生的 Markdown。

目前不保存：

- 全台股常駐行情資料。
- yfinance 快取內容。
- 結構化交易明細。
- 持倉快照資料表。
- 財報資料表。
- 回測歷史快照。
- 券商帳務或下單資料。
- API key、token 或任何 secrets。

`data/local/` 的實際資料不得提交 Git。

## Migration 策略

現階段 schema 很小，還沒有 migration framework。之後只要出現第二張表、欄位變更、索引調整或跨版本升級需求，就應先建立正式 migration 流程。

建議策略：

1. 在 `db/migrations/` 建立版本化 SQL 檔案。
2. 以遞增版本命名，例如 `0001_create_daily_reviews.sql`、`0002_add_review_tags.sql`。
3. 建立 `schema_migrations` 表，記錄已套用版本與套用時間。
4. migration 必須可重複執行或在已套用時安全略過。
5. schema 變更要搭配 repository 測試，確認新舊資料可讀寫。
6. 涉及個人資料的 migration 不輸出資料內容，只輸出結構與驗證結果。

建議的 migration metadata：

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

## 未來 schema 草案

以下是未來資料層可能需要的表，僅作設計方向，不代表已實作。

### stocks

保存股票基本資料與市場識別。

- `symbol`
- `market`
- `name`
- `currency`
- `is_active`
- `updated_at`

### daily_prices

保存可重現的日線資料，用於資料品質檢查與回測。

- `symbol`
- `trade_date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`
- `fetched_at`

建議 primary key：`(symbol, trade_date, source)`。

### daily_reviews

延續現行表，必要時可新增 tags、score 或結構化欄位。但交易紀錄自由文字是否解析，應另開 issue 設計。

### portfolio_snapshots

保存盤前／盤後持股水位或資產配置快照。

- `snapshot_date`
- `session`
- `cash_ratio`
- `stock_ratio`
- `notes`
- `created_at`

### research_notes

若未來需要把研究工具輸出保存到資料庫，應先釐清與 Obsidian 的分工。預設研究脈絡仍優先回寫 Obsidian，資料庫只保存需要結構化查詢的摘要。

## Repository 設計原則

- 每個資料表由明確 repository 或 service 管理，不讓 SQL 散落在 Streamlit UI。
- repository 接受明確資料模型，不直接接收未清理的 UI 狀態。
- 寫入操作需可測試；測試使用暫存 SQLite，不依賴本機個人資料庫。
- migration 與 repository 都不得讀取或輸出 secrets。
- 新增資料表時，同步更新本文件與相關測試。

## 下一步

資料庫近期不需要先擴充到完整股票 DB。較合理的順序是：

1. 維持現行 `daily_reviews` 穩定。
2. 完成 Dashboard smoke test 與研究工具優先版。
3. 在需要回測或資料品質驗證前，設計歷史行情快照 schema。
4. 再決定是否加入 migration framework 與多資料庫 adapter。
