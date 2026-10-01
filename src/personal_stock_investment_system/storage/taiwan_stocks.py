"""SQLite repository for Taiwan listed/OTC company reference data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from personal_stock_investment_system.research.stock_validation import (
    TaiwanListedCompany,
    TaiwanStockDirectory,
)
from personal_stock_investment_system.storage.migrations import run_sqlite_migrations

TAIWAN_STOCK_DIRECTORY_DATASET = "taiwan_listed_companies"


@dataclass(frozen=True)
class ReferenceDataSyncRun:
    dataset: str
    started_at: str
    completed_at: str
    status: str
    record_count: int = 0
    error: str = ""

    def is_stale(
        self,
        *,
        max_age: timedelta = timedelta(days=1),
        now: datetime | None = None,
    ) -> bool:
        completed = datetime.fromisoformat(self.completed_at)
        current = now or datetime.now(timezone.utc)
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current - completed > max_age


class TaiwanStockRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def replace_directory(self, directory: TaiwanStockDirectory, *, started_at: str | None = None) -> ReferenceDataSyncRun:
        run_sqlite_migrations(self.database_path)
        started = started_at or _now()
        completed = _now()
        try:
            with self._connect() as connection:
                connection.execute("UPDATE taiwan_listed_companies SET is_active = 0")
                connection.executemany(
                    """
                    INSERT INTO taiwan_listed_companies (
                        stock_code,
                        company_name,
                        company_full_name,
                        market,
                        industry,
                        source_url,
                        source_updated_at,
                        synced_at,
                        is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(stock_code) DO UPDATE SET
                        company_name = excluded.company_name,
                        company_full_name = excluded.company_full_name,
                        market = excluded.market,
                        industry = excluded.industry,
                        source_url = excluded.source_url,
                        source_updated_at = excluded.source_updated_at,
                        synced_at = excluded.synced_at,
                        is_active = 1
                    """,
                    (
                        (
                            company.code,
                            company.name,
                            company.full_name,
                            company.market,
                            company.industry,
                            company.source_url,
                            company.source_updated_at,
                            completed,
                        )
                        for company in directory.companies
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO reference_data_sync_runs (
                        dataset, started_at, completed_at, status, record_count, error
                    ) VALUES (?, ?, ?, 'success', ?, '')
                    """,
                    (TAIWAN_STOCK_DIRECTORY_DATASET, started, completed, len(directory.companies)),
                )
        except Exception as error:
            self.record_failed_sync(started_at=started, error=str(error))
            raise
        return ReferenceDataSyncRun(
            dataset=TAIWAN_STOCK_DIRECTORY_DATASET,
            started_at=started,
            completed_at=completed,
            status="success",
            record_count=len(directory.companies),
        )

    def record_failed_sync(self, *, started_at: str, error: str) -> ReferenceDataSyncRun:
        run_sqlite_migrations(self.database_path)
        completed = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reference_data_sync_runs (
                    dataset, started_at, completed_at, status, record_count, error
                ) VALUES (?, ?, ?, 'failed', 0, ?)
                """,
                (TAIWAN_STOCK_DIRECTORY_DATASET, started_at, completed, error),
            )
        return ReferenceDataSyncRun(
            dataset=TAIWAN_STOCK_DIRECTORY_DATASET,
            started_at=started_at,
            completed_at=completed,
            status="failed",
            error=error,
        )

    def load_directory(self) -> TaiwanStockDirectory | None:
        if not self.database_path.exists():
            return None
        run_sqlite_migrations(self.database_path)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    stock_code,
                    company_name,
                    company_full_name,
                    market,
                    industry,
                    source_url,
                    source_updated_at
                FROM taiwan_listed_companies
                WHERE is_active = 1
                ORDER BY stock_code
                """
            ).fetchall()
        if not rows:
            return None
        latest_sync = self.latest_sync(status="success")
        collected_at = latest_sync.completed_at if latest_sync is not None else ""
        return TaiwanStockDirectory(
            companies=tuple(
                TaiwanListedCompany(
                    code=row[0],
                    name=row[1],
                    full_name=row[2],
                    market=row[3],
                    industry=row[4],
                    source_url=row[5],
                    source_updated_at=row[6],
                )
                for row in rows
            ),
            collected_at=collected_at,
        )

    def latest_sync(self, *, status: str | None = None) -> ReferenceDataSyncRun | None:
        if not self.database_path.exists():
            return None
        run_sqlite_migrations(self.database_path)
        query = (
            "SELECT dataset, started_at, completed_at, status, record_count, error "
            "FROM reference_data_sync_runs WHERE dataset = ?"
        )
        params: tuple[str, ...] = (TAIWAN_STOCK_DIRECTORY_DATASET,)
        if status is not None:
            query += " AND status = ?"
            params += (status,)
        query += " ORDER BY id DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        return ReferenceDataSyncRun(
            dataset=row[0],
            started_at=row[1],
            completed_at=row[2],
            status=row[3],
            record_count=row[4],
            error=row[5],
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
