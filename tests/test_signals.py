from types import SimpleNamespace

from personal_stock_investment_system.signals.rules import BEARISH, BULLISH, NEUTRAL, build_market_summary, build_section_signal


def test_macro_score_is_inverted():
    signal = build_section_signal("macro", [SimpleNamespace(change_percent=1.0)])
    assert signal.label == BEARISH


def test_regular_section_keeps_price_direction():
    signal = build_section_signal("taiwan_market", [SimpleNamespace(change_percent=1.0)])
    assert signal.label == BULLISH


def test_section_signal_is_neutral_when_every_snapshot_lacks_change_data():
    signal = build_section_signal("taiwan_market", [SimpleNamespace(change_percent=None)])

    assert signal.label == NEUTRAL
    assert signal.valid_count == 0


def test_market_summary_is_neutral_when_no_section_has_valid_data():
    section = build_section_signal("taiwan_market", [SimpleNamespace(change_percent=None)])

    summary = build_market_summary([section])

    assert summary.label == NEUTRAL
    assert summary.score == 0
