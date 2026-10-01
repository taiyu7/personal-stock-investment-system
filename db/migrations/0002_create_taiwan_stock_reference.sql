CREATE TABLE IF NOT EXISTS taiwan_listed_companies (
    stock_code TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    company_full_name TEXT NOT NULL DEFAULT '',
    market TEXT NOT NULL CHECK (market IN ('listed', 'otc')),
    industry TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL,
    source_updated_at TEXT NOT NULL DEFAULT '',
    synced_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_taiwan_listed_companies_name
ON taiwan_listed_companies(company_name);

CREATE INDEX IF NOT EXISTS idx_taiwan_listed_companies_active
ON taiwan_listed_companies(is_active, market);

CREATE TABLE IF NOT EXISTS reference_data_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    record_count INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_reference_data_sync_runs_dataset
ON reference_data_sync_runs(dataset, completed_at DESC);
