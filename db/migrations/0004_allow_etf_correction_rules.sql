BEGIN IMMEDIATE;

CREATE TABLE research_correction_rules_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_code TEXT NOT NULL DEFAULT '',
    raw_name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (
        entity_type IN ('taiwan_stock', 'foreign_stock', 'etf', 'sector', 'non_stock')
    ),
    canonical_code TEXT NOT NULL DEFAULT '',
    canonical_name TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(raw_code, raw_name)
);

INSERT INTO research_correction_rules_v2 (
    id, raw_code, raw_name, entity_type, canonical_code, canonical_name,
    enabled, created_at, updated_at
)
SELECT
    id, raw_code, raw_name, entity_type, canonical_code, canonical_name,
    enabled, created_at, updated_at
FROM research_correction_rules;

DROP TABLE research_correction_rules;
ALTER TABLE research_correction_rules_v2 RENAME TO research_correction_rules;

CREATE INDEX idx_research_correction_rules_enabled
ON research_correction_rules(enabled, raw_code, raw_name);

COMMIT;
