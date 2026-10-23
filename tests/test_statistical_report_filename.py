from datetime import date

from personal_stock_investment_system.research.sources import ResearchReport, ResearchSource
from personal_stock_investment_system.research.statistical_report import generate_statistical_report
from personal_stock_investment_system.research.stock_validation import TaiwanStockDirectory


def test_statistical_filename_uses_entered_video_titles_in_order():
    reports = tuple(
        ResearchReport(ResearchSource("youtube_public", title, "逐字稿"))
        for title in ("一綺聊股", "股市情報局", "理財達人秀")
    )
    result = generate_statistical_report(
        reports, TaiwanStockDirectory((), "2026-10-23T00:00:00+00:00"), report_date=date(2026, 10, 23)
    )
    assert result.filename == "20261023-多來源統計分析報告(一綺聊股、股市情報局、理財達人秀).md"
