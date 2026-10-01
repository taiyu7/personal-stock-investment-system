from datetime import date
from pathlib import Path

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    ChartObservation,
    MediaArtifact,
    ResearchAnalysisResult,
    ResearchReport,
    ResearchReportOutputSettings,
    ResearchSource,
    ScreenshotArtifact,
    ScreenshotCaptureResult,
    ScreenshotRequest,
    SourceReference,
    StockIdentityCandidate,
    StockOpinion,
    TechnicalAnalysisNote,
    VideoResearchReportInput,
    VlmChartAnalysisResult,
    render_video_research_report,
    run_video_research_report_pipeline,
)


def _pipeline_input(tmp_path: Path) -> VideoResearchReportInput:
    source = ResearchSource(
        source_id="video-1",
        source_type="local_video",
        title="技術分析範例",
        raw_text="台積電突破壓力，成交量放大。",
        source_url="https://example.test/video/1",
        publisher="研究頻道",
        speaker="分析師 A",
    )
    reference = SourceReference(
        source_id=source.source_id,
        locator_type="timestamp",
        locator="00:01:23",
        quote="台積電突破壓力，成交量放大。",
        confidence="中",
    )
    report = ResearchReport(
        source=source,
        summary="影片認為台積電正在測試壓力區，但仍需查證圖面。",
        stock_opinions=(
            StockOpinion(
                speaker="分析師 A",
                stock="2330",
                company="台積電",
                direction="偏多",
                opinion="測試壓力區",
                rationale="逐字稿提到突破與量能",
                reference=reference,
                confidence="中",
            ),
        ),
        technical_notes=(
            TechnicalAnalysisNote(
                stock="2330",
                signal="突破壓力",
                chart_context="需搭配截圖確認",
                rationale="講者指向 K 線與成交量",
                reference=reference,
            ),
        ),
        risks_and_counterexamples=("突破可能失敗。",),
        open_questions=("壓力價位是否辨識正確？",),
        next_actions=("人工核對截圖。",),
    )
    screenshot_path = tmp_path / "screenshots" / "frame-001.jpg"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_bytes(b"fake image")
    request = ScreenshotRequest(
        timestamp_seconds=83,
        reason="確認突破與量能",
        quote=reference.quote,
        reference=reference,
    )
    artifact = ScreenshotArtifact(
        path=screenshot_path,
        timestamp_seconds=83,
        reason=request.reason,
        quote=request.quote,
        reference=reference,
    )
    return VideoResearchReportInput(
        media_artifact=MediaArtifact(
            path=tmp_path / "video.mp4",
            source_url=source.source_url,
            artifact_type="video",
            mime_type="video/mp4",
        ),
        transcription_result=AsrTranscriptionResult(
            segments=(AsrTranscriptSegment(reference.quote, start_seconds=83, end_seconds=88),),
            transcript_path=tmp_path / "transcript.json",
        ),
        analysis_result=ResearchAnalysisResult(
            report=report,
            provider="openai",
            model="fake-analysis-model",
            status="available",
            status_message="fake analysis ready",
        ),
        screenshot_results=(ScreenshotCaptureResult(status="available", request=request, artifact=artifact),),
        vlm_results=(
            VlmChartAnalysisResult(
                screenshot_path=screenshot_path,
                timestamp_seconds=83,
                source_reference=reference,
                provider="fake",
                model="fake-vlm-v1",
                prompt_version="technical_chart_v1",
                schema_version="1.0",
                status="needs_verification",
                is_technical_chart=True,
                chart_type="K 線圖",
                readability="中",
                observations=(
                    ChartObservation(
                        category="support_resistance",
                        description="畫面可見水平壓力線。",
                        evidence="水平線靠近近期高點",
                        confidence="中",
                        needs_verification=True,
                        verification_reason="價位文字不清楚",
                    ),
                ),
                stock_candidates=(StockIdentityCandidate(raw_code="2330", raw_company_name="台積電", confidence="中"),),
                status_message="fake VLM result",
            ),
        ),
        asr_backend="fake-asr",
        asr_model="fake-asr-v1",
    )


def test_complete_video_report_renders_adapter_metadata_citations_and_screenshot(tmp_path):
    pipeline_input = _pipeline_input(tmp_path)

    markdown = render_video_research_report(pipeline_input)

    assert markdown.startswith("# 完整影片研究報告")
    assert "## Pipeline 資訊" in markdown
    assert "- ASR backend：fake-asr" in markdown
    assert "- LLM analyzer：openai" in markdown
    assert "## 重要時間軸與結論引用" in markdown
    assert "| 00:01:23 | 股票觀點 | 2330 台積電：測試壓力區 | 台積電突破壓力，成交量放大。 | 中 |" in markdown
    assert "## 技術分析截圖與圖面理解" in markdown
    assert f"![00:01:23 技術分析截圖]({pipeline_input.screenshot_results[0].artifact.path.as_posix()})" in markdown
    assert "fake-vlm-v1" in markdown
    assert "畫面可見水平壓力線" in markdown
    assert "待 #58 deterministic 驗證" in markdown
    assert "## 逐字稿引用" in markdown
    assert "| 01:23 | 台積電突破壓力，成交量放大。 |" in markdown
    assert "自動下單" in markdown


def test_pipeline_marks_verification_and_missing_artifacts_as_partial(tmp_path):
    complete = _pipeline_input(tmp_path)
    unavailable_request = ScreenshotRequest(timestamp_seconds=120, reason="確認圖面")
    pipeline_input = VideoResearchReportInput(
        analysis_result=complete.analysis_result,
        transcription_result=AsrTranscriptionResult(
            segments=(),
            status="transcript_unavailable",
            status_message="逐字稿不可用。",
        ),
        screenshot_results=(
            ScreenshotCaptureResult(
                status="capture_unavailable",
                request=unavailable_request,
                status_message="無法擷取畫面。",
                error="fake capture error",
            ),
        ),
        asr_backend="fake-asr",
    )

    result = run_video_research_report_pipeline(
        pipeline_input,
        output_settings=ResearchReportOutputSettings.no_local_files(),
    )

    assert result.status == "partial"
    assert result.missing_items == ("media_artifact", "transcript", "screenshots")
    assert "截圖狀態：待補（無法擷取畫面。）" in result.markdown
    assert "待補：逐字稿不可用。" in result.markdown
    assert result.written_outputs == ()


def test_pipeline_reuses_existing_output_destinations(tmp_path):
    pipeline_input = _pipeline_input(tmp_path)
    settings = ResearchReportOutputSettings(
        obsidian_inbox_path=tmp_path / "obsidian" / "00-inbox",
        custom_output_path=tmp_path / "custom",
    )

    result = run_video_research_report_pipeline(
        pipeline_input,
        output_settings=settings,
        report_date=date(2026, 10, 1),
    )

    assert result.status == "partial"
    assert result.missing_items == ("vlm_verification",)
    assert len(result.written_outputs) == 2
    assert all(item.path.name == "2026-10-01_local_video_技術分析範例.md" for item in result.written_outputs)
    assert all(item.path.read_text(encoding="utf-8") == result.markdown for item in result.written_outputs)
