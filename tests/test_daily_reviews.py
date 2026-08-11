from personal_stock_investment_system.reviews import build_daily_review_text
from personal_stock_investment_system.storage.daily_reviews import DailyReview, DailyReviewRepository


def test_daily_review_can_be_saved_and_overwritten(tmp_path):
    repository = DailyReviewRepository(tmp_path / "reviews.db")
    first = DailyReview("2026/08/07", {"market_note": "第一版"}, "# first")
    repository.save(first)
    repository.save(DailyReview("2026/08/07", {"market_note": "第二版"}, "# second"))
    loaded = repository.load("2026/08/07")
    assert loaded is not None
    assert loaded.fields["market_note"] == "第二版"
    assert loaded.markdown == "# second"


def test_daily_review_markdown_keeps_existing_sections():
    markdown = build_daily_review_text("2026/08/07", {"market_note": "市場資料", "trade_records": "2330 買進"})
    assert "## 盤前功課" in markdown
    assert "## 盤後復盤" in markdown
    assert "2330 買進" in markdown


def test_daily_review_load_returns_none_before_database_exists(tmp_path):
    repository = DailyReviewRepository(tmp_path / "reviews.db")

    assert repository.load("2026/08/07") is None
