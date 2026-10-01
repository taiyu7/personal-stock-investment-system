CREATE TABLE IF NOT EXISTS daily_reviews (
    trade_date TEXT PRIMARY KEY,
    fields_json TEXT NOT NULL,
    markdown TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
