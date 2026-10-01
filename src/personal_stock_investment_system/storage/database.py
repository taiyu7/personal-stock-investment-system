"""Shared local database configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATABASE_URL = "sqlite:///data/local/personal-stock-investment.db"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def sqlite_database_path(database_url: str | None = None) -> Path:
    resolved_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not resolved_url.startswith("sqlite:///"):
        raise ValueError(
            "目前只支援 SQLite。請使用 sqlite:///data/local/personal-stock-investment.db"
        )
    configured_path = Path(resolved_url.removeprefix("sqlite:///"))
    if configured_path.is_absolute():
        return configured_path
    return project_root() / configured_path
