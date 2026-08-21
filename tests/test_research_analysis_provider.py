from pathlib import Path

from personal_stock_investment_system.research import (
    PhaseOneResearchInput,
    ResearchAnalysisSettings,
    ResearchReportOutputSettings,
    ResearchSource,
    analyze_research_source_with_provider,
    build_transcript_json_research_source,
    load_asr_transcription_result,
    run_phase_one_research_source_analysis,
)


def test_rule_based_analysis_provider_returns_structured_report():
    source = ResearchSource(
        source_type="manual_text",
        title="逐字稿",
        raw_text="[00:00:10] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
    )

    result = analyze_research_source_with_provider(source)

    assert result.status == "available"
    assert result.provider == "rule_based_fallback"
    assert result.report.summary != "未判定"
    assert result.report.stock_opinions[0].stock == "2330"


def test_unimplemented_llm_provider_is_explicit_and_uses_rule_based_fallback():
    source = ResearchSource(
        source_type="manual_text",
        title="逐字稿",
        raw_text="[00:00:10] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
    )

    result = analyze_research_source_with_provider(
        source,
        settings=ResearchAnalysisSettings(provider="anthropic_claude", model="claude-placeholder"),
    )

    assert result.status == "unsupported_provider"
    assert result.provider == "anthropic_claude"
    assert result.error == "provider_not_implemented"
    assert result.report.stock_opinions[0].stock == "2330"


def test_transcript_json_can_be_loaded_as_research_source(tmp_path):
    transcript_path = _write_transcript_json(tmp_path)

    transcription = load_asr_transcription_result(transcript_path)
    import_result = build_transcript_json_research_source(
        transcript_path,
        title="測試影片逐字稿",
        source_url="https://www.youtube.com/watch?v=oQnFGL10tVY",
    )

    assert transcription.status == "available"
    assert transcription.segments[0].display_timestamp() == "00:00"
    assert import_result.status == "available"
    assert import_result.source.source_type == "local_audio"
    assert import_result.source.source_url == "https://www.youtube.com/watch?v=oQnFGL10tVY"
    assert "[00:00] 研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。" in import_result.source.raw_text


def test_transcript_json_loader_accepts_windows_repo_absolute_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    transcript_path = Path("data/processed/asr-transcripts/openvino/sample.json")
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(_transcript_json_text(), encoding="utf-8")

    windows_path = (
        "C:\\Users\\taiyu\\personal-stock-investment-system\\"
        "data\\processed\\asr-transcripts\\openvino\\sample.json"
    )

    transcription = load_asr_transcription_result(windows_path)

    assert transcription.status == "available"
    assert transcription.transcript_path == transcript_path.resolve()


def test_entrypoint_accepts_asr_transcript_json_with_analysis_provider(tmp_path):
    transcript_path = _write_transcript_json(tmp_path)

    result = run_phase_one_research_source_analysis(
        PhaseOneResearchInput(
            input_kind="asr_transcript_json",
            title="測試影片逐字稿",
            transcript_json_path=transcript_path,
            source_url="https://www.youtube.com/watch?v=oQnFGL10tVY",
        ),
        output_settings=ResearchReportOutputSettings.no_local_files(),
        analysis_settings=ResearchAnalysisSettings(provider="openai", model="gpt-placeholder"),
    )

    assert result.import_result.status == "available"
    assert result.analysis_result.status == "unsupported_provider"
    assert "openai 彙整 provider 尚未接上 API" in "\n".join(result.statuses)
    assert "| 研究員 A | 2330 | 台積電 | 偏多 |" in result.markdown


def _write_transcript_json(tmp_path: Path) -> Path:
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(_transcript_json_text(), encoding="utf-8")
    return transcript_path


def _transcript_json_text() -> str:
    return """{
  "text": "研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。",
  "segments": [
    {
      "start": 0.0,
      "end": 25.0,
      "text": "研究員 A 認為 2330 台積電受惠 AI 伺服器需求，方向偏多。"
    }
  ],
  "backend": "openvino"
}"""
