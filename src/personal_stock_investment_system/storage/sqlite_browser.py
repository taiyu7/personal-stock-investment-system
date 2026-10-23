"""Read-only introspection and pagination for the configured local SQLite database."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True)
class SQLiteTableColumn:
    name: str
    data_type: str
    not_null: bool
    default_value: str | None
    primary_key_order: int


class SQLiteBrowserRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def list_tables(self) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name <> 'schema_migrations' ORDER BY name"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def table_columns(self, table_name: str) -> tuple[SQLiteTableColumn, ...]:
        if table_name not in self.list_tables():
            raise ValueError("找不到指定資料表。")
        with self._connect() as connection:
            rows = connection.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
        return tuple(SQLiteTableColumn(row[1], row[2] or "未指定", bool(row[3]), row[4], row[5]) for row in rows)

    def row_count(self, table_name: str) -> int:
        self._require_table(table_name)
        with self._connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}").fetchone()
        return int(row[0])

    def read_page(self, table_name: str, *, limit: int, offset: int) -> tuple[tuple[object, ...], ...]:
        self._require_table(table_name)
        if limit < 1 or limit > 500 or offset < 0:
            raise ValueError("分頁參數超出允許範圍。")
        columns = self.table_columns(table_name)
        primary_keys = sorted((column for column in columns if column.primary_key_order), key=lambda column: column.primary_key_order)
        ordering = ", ".join(_quote_identifier(column.name) for column in primary_keys) or "rowid"
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM {_quote_identifier(table_name)} ORDER BY {ordering} LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return tuple(tuple(row) for row in rows)

    def _require_table(self, table_name: str) -> None:
        if table_name not in self.list_tables():
            raise ValueError("找不到指定資料表。")

    def _connect(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise FileNotFoundError(f"找不到 SQLite 資料庫：{self.database_path}")
        path = quote(self.database_path.resolve().as_posix(), safe="/:")
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        connection.execute("PRAGMA query_only = ON")
        return connection


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
