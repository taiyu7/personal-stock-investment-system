import sqlite3
from datetime import datetime, timedelta, timezone

from personal_stock_investment_system.research import TaiwanListedCompany, TaiwanStockDirectory
from personal_stock_investment_system.storage import ReferenceDataSyncRun, TaiwanStockRepository, run_sqlite_migrations


def _directory(*companies: TaiwanListedCompany) -> TaiwanStockDirectory:
    return TaiwanStockDirectory(companies=companies, collected_at="2026-08-27T12:00:00+00:00")


def test_migrations_create_and_track_current_schema(tmp_path):
    database_path = tmp_path / "investment.db"

    first = run_sqlite_migrations(database_path)
    second = run_sqlite_migrations(database_path)

    assert first == ("0001_create_daily_reviews", "0002_create_taiwan_stock_reference")
    assert second == ()
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert "daily_reviews" in tables
    assert "taiwan_listed_companies" in tables
    assert "reference_data_sync_runs" in tables
    assert "schema_migrations" in tables


def test_migrations_preserve_existing_pre_migration_daily_reviews(tmp_path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE daily_reviews (
                trade_date TEXT PRIMARY KEY,
                fields_json TEXT NOT NULL,
                markdown TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO daily_reviews VALUES ('2026/08/07', '{}', '# existing', '2026-08-07T00:00:00+00:00')"
        )

    run_sqlite_migrations(database_path)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT trade_date, markdown FROM daily_reviews WHERE trade_date = '2026/08/07'"
        ).fetchone()
    assert row == ("2026/08/07", "# existing")


def test_repository_persists_latest_directory_and_deactivates_removed_companies(tmp_path):
    repository = TaiwanStockRepository(tmp_path / "investment.db")
    first = _directory(
        TaiwanListedCompany("2330", "台積電", "listed", source_url="listed.csv"),
        TaiwanListedCompany("6139", "亞翔", "otc", source_url="otc.csv"),
    )
    second = _directory(
        TaiwanListedCompany("2330", "台積電", "listed", industry="24", source_url="listed.csv"),
        TaiwanListedCompany("8103", "瀚荃", "otc", source_url="otc.csv"),
    )

    repository.replace_directory(first, started_at="2026-08-27T11:00:00+00:00")
    sync_run = repository.replace_directory(second, started_at="2026-08-28T11:00:00+00:00")
    loaded = repository.load_directory()

    assert loaded is not None
    assert [(item.code, item.name) for item in loaded.companies] == [("2330", "台積電"), ("8103", "瀚荃")]
    assert loaded.companies[0].industry == "24"
    assert sync_run.status == "success"
    assert sync_run.record_count == 2
    with sqlite3.connect(repository.database_path) as connection:
        inactive = connection.execute(
            "SELECT is_active FROM taiwan_listed_companies WHERE stock_code = '6139'"
        ).fetchone()
    assert inactive == (0,)


def test_repository_records_failed_sync_without_erasing_last_success(tmp_path):
    repository = TaiwanStockRepository(tmp_path / "investment.db")
    repository.replace_directory(
        _directory(
            TaiwanListedCompany("2330", "台積電", "listed"),
            TaiwanListedCompany("6139", "亞翔", "otc"),
        )
    )

    failed = repository.record_failed_sync(
        started_at="2026-08-29T11:00:00+00:00",
        error="network unavailable",
    )
    loaded = repository.load_directory()

    assert failed.status == "failed"
    assert repository.latest_sync() == failed
    assert loaded is not None
    assert len(loaded.companies) == 2


def test_sync_run_reports_when_local_reference_data_is_stale():
    run = ReferenceDataSyncRun(
        dataset="taiwan_listed_companies",
        started_at="2026-09-29T00:00:00+00:00",
        completed_at="2026-09-29T00:01:00+00:00",
        status="success",
        record_count=1988,
    )

    assert run.is_stale(
        max_age=timedelta(days=1),
        now=datetime(2026, 10, 1, tzinfo=timezone.utc),
    ) is True
