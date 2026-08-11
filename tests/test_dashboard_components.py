import pandas as pd

from apps.dashboard.components.market_cards import get_recent_trading_rows


def test_recent_rows_calculates_change_from_previous_close():
    dates = pd.date_range("2026-08-01", periods=6, freq="D")
    history = pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104, 105],
            "High": [102, 103, 104, 105, 106, 108],
            "Low": [99, 100, 101, 102, 103, 104],
            "Close": [101, 102, 103, 104, 105, 107],
        },
        index=dates,
    )

    rows = get_recent_trading_rows(history)

    assert len(rows) == 5
    assert rows.iloc[-1]["相對前日漲跌"] == 2
    assert rows.iloc[-1]["相對前日漲跌幅"] == 2 / 105 * 100


def test_recent_rows_returns_empty_when_required_price_columns_are_missing():
    history = pd.DataFrame({"Close": [100.0, 101.0]})

    rows = get_recent_trading_rows(history)

    assert rows.empty
