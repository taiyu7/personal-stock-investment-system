"""Minimal versioned SQLite migration runner."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def default_migrations_path() -> Path:
    return Path(__file__).resolve().parents[3] / "db" / "migrations"


def run_sqlite_migrations(
    database_path: Path | str,
    *,
    migrations_path: Path | str | None = None,
) -> tuple[str, ...]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    migration_directory = Path(migrations_path) if migrations_path is not None else default_migrations_path()
    migration_files = sorted(migration_directory.glob("*.sql"))
    if not migration_files:
        raise FileNotFoundError(f"No SQLite migrations found in {migration_directory}")

    applied: list[str] = []
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        existing = {
            row[0]
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration_file in migration_files:
            version = migration_file.stem
            if version in existing:
                continue
            connection.executescript(migration_file.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            applied.append(version)
    return tuple(applied)
