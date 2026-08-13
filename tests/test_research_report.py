from datetime import date

from personal_stock_investment_system.research import (
    CompanyProfileNote,
    ResearchReport,
    ResearchSource,
    SourceReference,
    StockOpinion,
    StockRelation,
    TechnicalAnalysisNote,
    VerifiableHypothesis,
    build_research_report_filename,
    render_research_report,
)


def test_research_report_renders_fixed_markdown_sections():
    source = ResearchSource(
        source_id="src_sample",
        source_type="manual_text",
        title="財經節目 AI 伺服器與台股供應鏈逐字稿",
        publisher="財經電視台",
        speaker="主持人 C",
        speakers=("主持人 C", "研究員 A", "分析師 B"),
        published_date="2026-08-13",
        collected_at="2026-08-13T09:00:00+00:00",
        raw_text="研究員 A 認為 2330 台積電受惠 AI 伺服器需求。分析師 B 提醒估值風險。",
    )
    reference = SourceReference(
        source_id=source.source_id,
        locator_type="timestamp",
        locator="00:01:23",
        quote="台積電受惠 AI 伺服器需求",
        confidence="高",
    )
    report = ResearchReport(
        source=source,
        summary="節目中研究員 A 偏多看待 AI 伺服器供應鏈，分析師 B 提醒估值風險。",
        stock_opinions=(
            StockOpinion(
                speaker="研究員 A",
                stock="2330",
                company="台積電",
                direction="偏多",
                opinion="AI 需求帶動先進製程",
                rationale="原文提到 AI 伺服器需求",
                reference=reference,
                confidence="高",
            ),
            StockOpinion(
                speaker="分析師 B",
                stock="2330",
                company="台積電",
                direction="中性",
                opinion="題材正向但估值需留意",
                rationale="原文提醒估值風險",
                reference=reference,
                confidence="中",
            ),
        ),
        stock_relations=(
            StockRelation(
                stock="2330",
                company="台積電",
                related_groups=("AI 伺服器", "半導體"),
                related_companies=("供應鏈待補",),
                rationale="原文提及 AI 伺服器需求",
                reference=reference,
            ),
        ),
        company_profiles=(
            CompanyProfileNote(
                stock="2330",
                company="台積電",
                main_business="待查證：來源未說明公司主要業務。",
                reference=reference,
            ),
        ),
        technical_notes=(
            TechnicalAnalysisNote(
                stock="2330",
                signal="未判定",
                chart_context="需要人工補圖：原文提到圖面，但逐字稿未包含畫面資訊。",
                rationale="逐字稿缺少圖面資訊",
                missing_data="K 線截圖",
                reference=reference,
            ),
        ),
        hypotheses=(
            VerifiableHypothesis(
                hypothesis="AI 伺服器需求增加時，先進製程供應鏈相對強勢。",
                required_data="AI 伺服器營收、股價相對強弱",
                backtestable="可",
                initial_rule="營收年增且股價站上月線",
                confidence="中",
            ),
        ),
        risks_and_counterexamples=("估值過高可能抵銷題材利多。",),
        open_questions=("AI 伺服器需求是否已反映在報價？",),
        next_actions=("查證公司主要業務與營收占比。",),
    )

    markdown = render_research_report(report)

    assert markdown.startswith("# 研究來源分析報告")
    assert "- 講者／來賓：主持人 C、研究員 A、分析師 B" in markdown
    assert "## 人物對股票的評價" in markdown
    assert "| 研究員 A | 2330 | 台積電 | 偏多 | AI 需求帶動先進製程 |" in markdown
    assert "| 分析師 B | 2330 | 台積電 | 中性 | 題材正向但估值需留意 |" in markdown
    assert "| 2330 | 台積電 | AI 伺服器、半導體 | 供應鏈待補 |" in markdown
    assert "需要人工補圖" in markdown
    assert "估值過高可能抵銷題材利多" in markdown


def test_research_report_marks_unknown_values_instead_of_guessing():
    source = ResearchSource(source_id="src_unknown", source_type="manual_text", title="", raw_text="")
    report = ResearchReport(source=source)

    markdown = render_research_report(report)

    assert "- 標題：未判定" in markdown
    assert "- 講者／來賓：未判定" in markdown
    assert "## 一句話摘要\n\n未判定" in markdown
    assert "## 待查問題\n\n- 未判定" in markdown


def test_research_report_filename_is_stable_and_windows_safe():
    source = ResearchSource(
        source_id="src_sample",
        source_type="youtube_public",
        title="AI 伺服器 / 台股: 供應鏈? 觀察",
        raw_text="sample",
    )
    report = ResearchReport(source=source)

    assert build_research_report_filename(report, date(2026, 8, 13)) == "2026-08-13_youtube_public_AI伺服器台股供應鏈觀察.md"
