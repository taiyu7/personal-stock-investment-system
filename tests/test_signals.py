from types import SimpleNamespace

from personal_stock_investment_system.signals.rules import BEARISH, BULLISH, build_section_signal


def test_macro_score_is_inverted():
    signal = build_section_signal("macro", [SimpleNamespace(change_percent=1.0)])
    assert signal.label == BEARISH


def test_regular_section_keeps_price_direction():
    signal = build_section_signal("taiwan_market", [SimpleNamespace(change_percent=1.0)])
    assert signal.label == BULLISH
