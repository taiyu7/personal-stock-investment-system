from datetime import date
from types import SimpleNamespace

import pytest

from personal_stock_investment_system.research.sources import ResearchReport, ResearchSource, SourceReference, StockOpinion
from personal_stock_investment_system.research.statistical_report import build_stock_consensus, generate_statistical_report
from personal_stock_investment_system.research.stock_validation import TaiwanListedCompany, TaiwanStockDirectory


def test_statistical_filename_uses_entered_video_titles_in_order():
    reports = tuple(
        ResearchReport(ResearchSource("youtube_public", title, "逐字稿"))
        for title in ("一綺聊股", "股市情報局", "理財達人秀")
    )
    result = generate_statistical_report(
        reports, TaiwanStockDirectory((), "2026-10-23T00:00:00+00:00"), report_date=date(2026, 10, 23)
    )
    assert result.filename == "20261023-多來源統計分析報告(一綺聊股、股市情報局、理財達人秀).md"


def test_single_report_counts_distinct_speakers_within_one_program():
    source = ResearchSource("youtube_public", "股市情報局", "逐字稿", publisher="股市情報局")
    report = ResearchReport(
        source,
        stock_opinions=(
            StockOpinion("主持人", "2330", "台積電", "偏多", reference=SourceReference(source.source_id, "timestamp", "01:00")),
            StockOpinion("來賓甲", "2330", "台積電", "偏多", reference=SourceReference(source.source_id, "timestamp", "02:00")),
        ),
    )
    directory = TaiwanStockDirectory((TaiwanListedCompany("2330", "台積電", "listed"),), "2026-10-23T00:00:00+00:00")
    consensus = build_stock_consensus((report,), directory)

    assert (consensus[0].speaker_count, consensus[0].program_count, consensus[0].mention_count) == (2, 1, 2)

    class FakeClient:
        responses = SimpleNamespace(create=lambda **kwargs: SimpleNamespace(output_text='{"stocks": []}'))

    result = generate_statistical_report((report,), directory, client=FakeClient(), report_date=date(2026, 10, 23))
    assert "- 納入報告：1 份" in result.markdown
    assert "- 不同講者數：2" in result.markdown
    assert "- 不同節目數：1" in result.markdown
    assert "- 可追溯提及次數：2" in result.markdown
    assert result.filename == "20261023-多來源統計分析報告(股市情報局).md"


def test_statistical_report_still_rejects_zero_reports():
    with pytest.raises(ValueError, match="至少選取一份"):
        generate_statistical_report((), TaiwanStockDirectory((), "2026-10-23T00:00:00+00:00"))
