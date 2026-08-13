from datetime import date

from personal_stock_investment_system.research import (
    PhaseOneResearchInput,
    ResearchReportOutputSettings,
    run_phase_one_research_source_analysis,
)
from tests.test_pdf_research import _minimal_text_pdf


def test_manual_text_entrypoint_produces_research_report_without_local_output():
    result = run_phase_one_research_source_analysis(
        PhaseOneResearchInput(
            input_kind="manual_text",
            title="固定逐字稿",
            manual_text="[00:01:23] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
            speakers=("研究員 A",),
        ),
        output_settings=ResearchReportOutputSettings.no_local_files(),
        report_date=date(2026, 8, 13),
    )

    assert result.source.source_type == "manual_text"
    assert "## 人物對股票的評價" in result.markdown
    assert "| 研究員 A | 2330 | 台積電 | 偏多 |" in result.markdown
    assert result.written_outputs == ()
    assert "未輸出本機檔案" in result.statuses[-1]


def test_pdf_entrypoint_completes_pdf_to_markdown_preprocessing(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_minimal_text_pdf("2330 TSMC AI server demand", "valuation risk"))

    result = run_phase_one_research_source_analysis(
        PhaseOneResearchInput(input_kind="pdf", title="測試 PDF", pdf_path=pdf_path),
        output_settings=ResearchReportOutputSettings.no_local_files(),
        report_date=date(2026, 8, 13),
    )

    assert result.source.source_type == "pdf"
    assert "PDF to Markdown 前處理完成。" in result.statuses
    assert "## 第 1 頁" in result.source.markdown_text
    assert "2330 TSMC AI server demand" in result.source.raw_text


def test_youtube_entrypoint_shows_transcript_unavailable_fallback():
    result = run_phase_one_research_source_analysis(
        PhaseOneResearchInput(
            input_kind="youtube_public",
            title="無逐字稿公開影片",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        output_settings=ResearchReportOutputSettings.no_local_files(),
        report_date=date(2026, 8, 13),
    )

    assert result.source.source_type == "youtube_public"
    assert result.source.raw_text == ""
    assert "YouTube 逐字稿狀態：transcript_unavailable" in result.statuses
    assert "未取得公開逐字稿" in "\n".join(result.statuses)
    assert "## 一句話摘要\n\n未判定" in result.markdown


def test_entrypoint_can_write_to_selected_temp_destinations(tmp_path):
    settings = ResearchReportOutputSettings(
        obsidian_inbox_path=tmp_path / "obsidian" / "00-inbox",
        custom_output_path=tmp_path / "desktop",
    )

    result = run_phase_one_research_source_analysis(
        PhaseOneResearchInput(
            input_kind="manual_text",
            title="AI 伺服器 / 台股: 觀察?",
            manual_text="[00:01:23] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
            speakers=("研究員 A",),
        ),
        output_settings=settings,
        report_date=date(2026, 8, 13),
    )

    assert [item.kind for item in result.written_outputs] == ["obsidian_inbox", "custom_path"]
    assert result.written_outputs[0].path.exists()
    assert result.written_outputs[1].path.exists()
    assert result.written_outputs[0].path.name == "2026-08-13_manual_text_AI伺服器台股觀察.md"
