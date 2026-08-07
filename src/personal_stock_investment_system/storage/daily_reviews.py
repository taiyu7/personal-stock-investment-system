"""SQLite persistence for daily review form data."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class DailyReview:
    trade_date: str
    fields: dict[str, str]
    markdown: str
    updated_at: str | None = None


class DailyReviewRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def save(self, review: DailyReview) -> DailyReview:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_reviews (
                    trade_date TEXT PRIMARY KEY,
                    fields_json TEXT NOT NULL,
                    markdown TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO daily_reviews (trade_date, fields_json, markdown, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(trade_date) DO UPDATE SET
                    fields_json = excluded.fields_json,
                    markdown = excluded.markdown,
                    updated_at = excluded.updated_at
                """,
                (review.trade_date, json.dumps(review.fields, ensure_ascii=False), review.markdown, updated_at),
            )
        return DailyReview(review.trade_date, review.fields, review.markdown, updated_at)

    def load(self, trade_date: str) -> DailyReview | None:
        if not self.database_path.exists():
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT trade_date, fields_json, markdown, updated_at FROM daily_reviews WHERE trade_date = ?", (trade_date,)
            ).fetchone()
        if row is None:
            return None
        return DailyReview(row[0], json.loads(row[1]), row[2], row[3])

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
