from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from personal_stock_investment_system.storage.database import sqlite_database_path
from personal_stock_investment_system.storage.sqlite_browser import SQLiteBrowserRepository


def render_sqlite_database_page() -> None:
    st.title("SQLite 資料庫")
    st.caption("唯讀瀏覽目前設定的本機 SQLite 資料庫；本頁不會修改資料或資料表結構。")
    repository = SQLiteBrowserRepository(sqlite_database_path())
    try:
        tables = repository.list_tables()
    except FileNotFoundError:
        st.info("目前尚未建立本機 SQLite 資料庫。完成一次資料同步或儲存後，這裡就會列出資料表。")
        return
    except Exception as error:  # noqa: BLE001 - database errors become a local page state.
        st.error(f"無法讀取 SQLite 資料庫：{error}")
        return

    st.caption(f"資料庫位置：{repository.database_path.resolve()}")
    st.metric("可瀏覽資料表", len(tables))
    if not tables:
        st.info("目前資料庫沒有可瀏覽的使用者資料表。")
        return

    selected_table = st.selectbox(
        "選擇資料表", tables, key="sqlite_browser_table", on_change=_reset_sqlite_browser_page
    )
    try:
        columns = repository.table_columns(selected_table)
        total_rows = repository.row_count(selected_table)
    except Exception as error:  # noqa: BLE001 - keep other dashboard pages available.
        st.error(f"無法讀取資料表結構：{error}")
        return

    st.markdown("#### 欄位資訊")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "欄位": column.name,
                    "型別": column.data_type,
                    "不可為空": "是" if column.not_null else "否",
                    "主鍵順序": column.primary_key_order or "—",
                    "預設值": column.default_value if column.default_value is not None else "—",
                }
                for column in columns
            ]
        ),
        hide_index=True,
    )

    st.markdown("#### 資料列")
    st.caption(f"資料表共有 {total_rows:,} 筆；每頁最多載入 100 筆。")
    page_size = st.selectbox(
        "每頁筆數", (25, 50, 100), index=1, key="sqlite_browser_page_size", on_change=_reset_sqlite_browser_page
    )
    page_count = max(1, math.ceil(total_rows / page_size))
    page_number = st.number_input(
        "頁次", min_value=1, max_value=page_count, value=1, step=1, key="sqlite_browser_page_number"
    )
    if not total_rows:
        st.info("這個資料表目前沒有資料列。")
        return
    try:
        rows = repository.read_page(selected_table, limit=page_size, offset=(page_number - 1) * page_size)
        st.dataframe(pd.DataFrame(rows, columns=[column.name for column in columns]), hide_index=True)
    except Exception as error:  # noqa: BLE001 - rowid/table-specific errors are non-fatal.
        st.error(f"無法讀取資料列：{error}")


def _reset_sqlite_browser_page() -> None:
    st.session_state["sqlite_browser_page_number"] = 1
