from datetime import date

from personal_stock_investment_system.research import (
    ResearchReport,
    ResearchReportOutputSettings,
    ResearchSource,
    build_research_report_filename,
    resolve_research_report_output_destinations,
    write_research_report_outputs,
)


def test_default_output_settings_resolve_obsidian_and_desktop_destinations(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    monkeypatch.setattr("personal_stock_investment_system.research.output.Path.home", lambda: fake_home)

    destinations = resolve_research_report_output_destinations()

    assert [destination.kind for destination in destinations] == ["obsidian_inbox", "custom_path"]
    assert str(destinations[0].directory).endswith(r"個人理財資訊系統\00-inbox")
    assert destinations[1].directory == fake_home / "Desktop"


def test_output_settings_support_all_destination_combinations(tmp_path):
    obsidian_dir = tmp_path / "obsidian" / "00-inbox"
    custom_dir = tmp_path / "desktop"

    both = resolve_research_report_output_destinations(
        ResearchReportOutputSettings(obsidian_inbox_path=obsidian_dir, custom_output_path=custom_dir)
    )
    obsidian_only = resolve_research_report_output_destinations(
        ResearchReportOutputSettings(
            write_to_custom_path=False,
            obsidian_inbox_path=obsidian_dir,
            custom_output_path=custom_dir,
        )
    )
    custom_only = resolve_research_report_output_destinations(
        ResearchReportOutputSettings(
            write_to_obsidian_inbox=False,
            obsidian_inbox_path=obsidian_dir,
            custom_output_path=custom_dir,
        )
    )
    none = resolve_research_report_output_destinations(ResearchReportOutputSettings.no_local_files())

    assert [destination.kind for destination in both] == ["obsidian_inbox", "custom_path"]
    assert [destination.kind for destination in obsidian_only] == ["obsidian_inbox"]
    assert [destination.kind for destination in custom_only] == ["custom_path"]
    assert none == ()


def test_write_outputs_uses_temp_destinations_and_windows_safe_filename(tmp_path):
    report = ResearchReport(
        source=ResearchSource(
            source_id="src_output",
            source_type="youtube_public",
            title="AI 伺服器 / 台股: 供應鏈? 觀察",
            raw_text="sample",
        )
    )
    settings = ResearchReportOutputSettings(
        obsidian_inbox_path=tmp_path / "obsidian" / "00-inbox",
        custom_output_path=tmp_path / "desktop",
    )

    written = write_research_report_outputs(
        report,
        settings=settings,
        markdown="# 測試報告\n",
        report_date=date(2026, 8, 13),
    )

    assert len(written) == 2
    assert written[0].path.name == "2026-08-13_youtube_public_AI伺服器台股供應鏈觀察.md"
    assert written[1].path.name == "2026-08-13_youtube_public_AI伺服器台股供應鏈觀察.md"
    assert written[0].path.read_text(encoding="utf-8") == "# 測試報告\n"
    assert written[1].path.read_text(encoding="utf-8") == "# 測試報告\n"
    assert "<" not in written[0].path.name
    assert "/" not in written[0].path.name
    assert "?" not in written[0].path.name


def test_no_local_file_setting_writes_nothing(tmp_path):
    report = ResearchReport(
        source=ResearchSource(
            source_id="src_no_output",
            source_type="manual_text",
            title="只顯示不輸出",
            raw_text="sample",
        )
    )

    written = write_research_report_outputs(
        report,
        settings=ResearchReportOutputSettings.no_local_files(),
        markdown="# 只顯示\n",
        report_date=date(2026, 8, 13),
    )

    assert written == ()
    assert list(tmp_path.rglob("*.md")) == []


def test_report_filename_can_be_built_from_date_type_and_title():
    report = ResearchReport(
        source=ResearchSource(
            source_id="src_filename",
            source_type="pdf",
            title='財報分析: Q2 / "風險"?',
            raw_text="sample",
        )
    )

    assert build_research_report_filename(report, date(2026, 8, 13)) == "2026-08-13_pdf_財報分析Q2風險.md"
