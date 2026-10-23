CREATE TABLE IF NOT EXISTS research_correction_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_code TEXT NOT NULL DEFAULT '',
    raw_name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('taiwan_stock', 'foreign_stock', 'sector', 'non_stock')),
    canonical_code TEXT NOT NULL DEFAULT '',
    canonical_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(raw_code, raw_name)
);

CREATE INDEX IF NOT EXISTS idx_research_correction_rules_enabled
ON research_correction_rules(enabled, raw_code, raw_name);
