from personal_stock_investment_system.research import (
    ResearchReport,
    ResearchSource,
    SourceReference,
    StockOpinion,
    TechnicalAnalysisNote,
    TaiwanStockDirectory,
    TaiwanStockMentionVerifier,
    VerificationIssue,
    sync_taiwan_stock_directory,
    verify_research_report_stock_mentions,
)
from personal_stock_investment_system.storage import TaiwanStockRepository


def _directory() -> TaiwanStockDirectory:
    return TaiwanStockDirectory.from_openapi_payloads(
        [
            {"公司代號": "2330", "公司簡稱": "台積電", "公司名稱": "台灣積體電路製造股份有限公司"},
            {"公司代號": "8039", "公司簡稱": "台虹", "公司名稱": "台虹科技股份有限公司"},
        ],
        [
            {"公司代號": "3362", "公司簡稱": "先進光", "公司名稱": "先進光電科技股份有限公司"},
            {"公司代號": "6139", "公司簡稱": "亞翔", "公司名稱": "亞翔工程股份有限公司"},
            {"公司代號": "8103", "公司簡稱": "瀚荃", "公司名稱": "瀚荃股份有限公司"},
        ],
        collected_at="2026-08-27T12:00:00+00:00",
    )


def test_verifier_accepts_exact_official_code_and_name_pair():
    result = TaiwanStockMentionVerifier(_directory()).verify("2330", "台積電")

    assert result.status == "已查證"
    assert result.canonical_code == "2330"
    assert result.canonical_name == "台積電"
    assert result.market == "listed"
    assert result.confidence == "高"


def test_verifier_completes_company_name_only_mention():
    result = TaiwanStockMentionVerifier(_directory()).verify("", "台積電")

    assert result.status == "已查證"
    assert result.canonical_code == "2330"
    assert result.canonical_name == "台積電"
    assert result.confidence == "高"


def test_verifier_reports_wrong_code_when_company_name_has_one_official_match():
    result = TaiwanStockMentionVerifier(_directory()).verify("8139", "台虹")

    assert result.status == "疑似錯誤"
    assert result.canonical_code == "8039"
    assert result.canonical_name == "台虹"
    assert "不是 8139" in result.evidence


def test_verifier_reports_name_conflict_when_code_exists():
    verifier = TaiwanStockMentionVerifier(_directory())

    asia_result = verifier.verify("6139", "亞香")
    connector_result = verifier.verify("8103", "漢權")

    assert asia_result.status == "衝突"
    assert asia_result.canonical_name == "亞翔"
    assert connector_result.status == "衝突"
    assert connector_result.canonical_name == "瀚荃"


def test_verifier_reports_wrong_code_for_advanced_optics_regression():
    result = TaiwanStockMentionVerifier(_directory()).verify("3166", "先進光")

    assert result.status == "疑似錯誤"
    assert result.canonical_code == "3362"


def test_report_verification_replaces_untrusted_identity_issues_and_keeps_other_claims():
    source = ResearchSource(source_id="src_verify", source_type="manual_text", title="測試", raw_text="")
    reference = SourceReference(source_id=source.source_id, locator_type="timestamp", locator="00:01:00")
    report = ResearchReport(
        source=source,
        stock_opinions=(
            StockOpinion(speaker="A", stock="2330", company="台積電", reference=reference),
            StockOpinion(speaker="A", stock="8139", company="台虹", reference=reference),
        ),
        technical_notes=(
            TechnicalAnalysisNote(stock="2330", signal="突破", reference=reference),
            TechnicalAnalysisNote(stock="8139", signal="長紅", reference=reference),
        ),
        verification_issues=(
            VerificationIssue(item_type="股票代碼", target="台虹", status="已查證"),
            VerificationIssue(item_type="供應鏈", target="台積電", status="待查證"),
        ),
    )

    verified = verify_research_report_stock_mentions(report, _directory())

    assert [item.status for item in verified.verification_issues] == ["待查證", "已查證", "疑似錯誤"]
    assert verified.verification_issues[0].item_type == "供應鏈"
    wrong_code_issue = verified.verification_issues[-1]
    assert wrong_code_issue.target == "8139 台虹"
    assert "候選：8039 台虹" in wrong_code_issue.evidence
    assert wrong_code_issue.external_sources


def test_report_verification_does_not_silently_rewrite_conflicting_mentions():
    source = ResearchSource(source_id="src_conflict", source_type="manual_text", title="測試", raw_text="")
    report = ResearchReport(
        source=source,
        stock_opinions=(StockOpinion(speaker="A", stock="6139", company="亞香"),),
    )

    verified = verify_research_report_stock_mentions(report, _directory())

    assert verified.stock_opinions[0].company == "亞香"
    assert verified.verification_issues[0].status == "衝突"
    assert "候選：6139 亞翔" in verified.verification_issues[0].evidence


def test_report_verification_completes_mentions_with_only_code_or_company_name():
    source = ResearchSource(source_id="src_partial", source_type="manual_text", title="測試", raw_text="")
    report = ResearchReport(
        source=source,
        stock_opinions=(
            StockOpinion(speaker="A", stock="2330", company=""),
            StockOpinion(speaker="A", stock="", company="先進光"),
        ),
    )

    verified = verify_research_report_stock_mentions(report, _directory())

    assert verified.stock_opinions[0].stock == "2330"
    assert verified.stock_opinions[0].company == "台積電"
    assert verified.stock_opinions[1].stock == "3362"
    assert verified.stock_opinions[1].company == "先進光"
    assert [issue.status for issue in verified.verification_issues] == ["已查證", "已查證"]


def test_sync_persists_official_directory_before_it_is_used(tmp_path):
    class FakeClient:
        def fetch_directory(self):
            return _directory()

    repository = TaiwanStockRepository(tmp_path / "investment.db")

    result = sync_taiwan_stock_directory(client=FakeClient(), repository=repository)

    assert result.status == "success"
    assert result.record_count == 5
    assert repository.load_directory() == result.directory


def test_sync_failure_uses_last_successful_local_directory(tmp_path):
    class FailingClient:
        def fetch_directory(self):
            raise RuntimeError("official source unavailable")

    repository = TaiwanStockRepository(tmp_path / "investment.db")
    repository.replace_directory(_directory())

    result = sync_taiwan_stock_directory(client=FailingClient(), repository=repository)

    assert result.status == "failed"
    assert result.directory is not None
    assert len(result.directory.companies) == 5
    assert "沿用本機最後成功版本" in result.status_message
    assert repository.latest_sync().status == "failed"
