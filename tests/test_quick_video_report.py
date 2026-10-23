from datetime import date
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BrowserSessionAsrInput,
    BrowserSessionAsrResult,
    MediaAcquisitionResult,
    MediaArtifact,
    QuickVideoReportInput,
    ResearchAnalysisResult,
    TaiwanListedCompany,
    TaiwanStockDirectory,
    analyze_research_source,
    build_quick_video_report_filename,
    run_quick_video_research_report,
)


class FakeOpenAIAnalysisClient:
    def analyze(self, source):
        return ResearchAnalysisResult(
            report=analyze_research_source(source),
            provider="openai",
            model="gpt-test",
            status_message="OpenAI 彙整完成。",
        )


class FailedOpenAIAnalysisClient:
    def analyze(self, source):
        return ResearchAnalysisResult(
            report=analyze_research_source(source),
            provider="openai",
            model="gpt-test",
            status="analysis_failed",
            status_message="OpenAI 彙整失敗。",
            error="provider unavailable",
        )


def test_quick_video_report_filename_uses_input_date_and_title():
    request = QuickVideoReportInput(
        video_url="https://example.test/video",
        published_date=date(2026, 10, 23),
        title="股市情報局",
    )

    assert build_quick_video_report_filename(request) == "20261023-股市情報局-摘要報告.md"


def test_batch_generates_statistical_report_after_one_success(monkeypatch):
    from types import SimpleNamespace

    import personal_stock_investment_system.research.quick_video_report as quick_video_report
    from personal_stock_investment_system.research.sources import ResearchReport, ResearchSource
    from personal_stock_investment_system.research.statistical_report import StatisticalReportResult

    request = _request()
    browser_input = BrowserSessionAsrInput(page_url=request.video_url, asr_provider="openai")
    report = ResearchReport(ResearchSource("youtube_public", request.title, "逐字稿"))
    expected = StatisticalReportResult("# 統計", "single.md", "openai", "test")
    received = []
    monkeypatch.setattr(
        quick_video_report, "run_quick_video_research_report",
        lambda *args, **kwargs: SimpleNamespace(is_available=True, research_result=SimpleNamespace(report=report)),
    )
    monkeypatch.setattr(
        quick_video_report, "generate_statistical_report",
        lambda reports, directory: received.append(reports) or expected,
    )

    batch = quick_video_report.run_quick_video_report_batch(
        ((1, request, browser_input),), stock_directory=_directory()
    )

    assert batch.success_count == 1
    assert batch.statistical_report == expected
    assert received == [(report,)]


def test_quick_video_report_runs_openai_pipeline_without_writing_local_report(tmp_path):
    transcript_path = _write_transcript(tmp_path)
    events = []

    def fake_asr_runner(source_input, *, on_progress):
        on_progress("media", "running", "正在取得影片媒體。")
        on_progress("media", "success", "音訊已準備完成。")
        on_progress("transcription", "running", "正在轉錄。")
        on_progress("transcription", "success", "逐字稿已產生。")
        return _available_asr_result(tmp_path, transcript_path)

    result = run_quick_video_research_report(
        _request(),
        BrowserSessionAsrInput(page_url="https://example.test/video", asr_provider="openai"),
        stock_directory=_directory(),
        asr_runner=fake_asr_runner,
        analysis_client=FakeOpenAIAnalysisClient(),
        progress_callback=events.append,
    )

    assert result.is_available is True
    assert result.filename == "20261023-股市情報局-摘要報告.md"
    assert result.research_result is not None
    assert result.research_result.written_outputs == ()
    assert result.research_result.source.published_date == "2026-10-23"
    assert "# 研究來源分析報告" in result.markdown
    assert [event.step_id for event in events] == [
        "validate",
        "validate",
        "media",
        "media",
        "transcription",
        "transcription",
        "analysis",
        "analysis",
        "render",
        "render",
        "complete",
    ]


def test_quick_video_report_uses_captions_without_media(tmp_path):
    from personal_stock_investment_system.research.youtube_captions import CaptionFetchResult, save_caption_transcript

    transcription = save_caption_transcript(
        CaptionFetchResult((AsrTranscriptSegment("2330 台積電", 15.0, 18.0),), "zh-TW"),
        tmp_path / "captions.json",
    )

    def fake_caption_runner(source_input, *, on_progress):
        on_progress("captions", "success", transcription.status_message)
        return BrowserSessionAsrResult(
            media_result=MediaAcquisitionResult(
                status="available", source_identifier=source_input.page_url,
                status_message="已使用 YouTube 現成字幕；無須下載影片音訊。",
            ),
            transcription=transcription,
        )

    result = run_quick_video_research_report(
        _request(),
        BrowserSessionAsrInput(page_url="https://example.test/video", asr_provider="openai"),
        stock_directory=_directory(),
        asr_runner=fake_caption_runner,
        analysis_client=FakeOpenAIAnalysisClient(),
    )
    assert result.is_available
    assert result.research_result is not None
    assert "2330 台積電" in result.research_result.source.raw_text
    assert result.research_result.source.source_type == "youtube_public"
    assert result.browser_asr_result.media_result.artifact is None


def test_batch_zip_contains_all_individual_reports_and_summary(tmp_path):
    from apps.dashboard.views.research_source_analysis import _batch_report_zip
    from personal_stock_investment_system.research.quick_video_report import (
        QuickVideoReportBatchItem, QuickVideoReportBatchResult,
    )
    from personal_stock_investment_system.research.statistical_report import StatisticalReportResult

    transcript_path = _write_transcript(tmp_path)
    request = _request()
    browser_input = BrowserSessionAsrInput(page_url=request.video_url, asr_provider="openai")
    report = run_quick_video_research_report(
        request, browser_input, stock_directory=_directory(),
        asr_runner=lambda source_input, *, on_progress: _available_asr_result(tmp_path, transcript_path),
        analysis_client=FakeOpenAIAnalysisClient(),
    )
    batch = QuickVideoReportBatchResult(
        (
            QuickVideoReportBatchItem(1, request, browser_input, report),
            QuickVideoReportBatchItem(2, request, browser_input, report),
        ),
        statistical_report=StatisticalReportResult("# 彙總", "20261023-多來源統計分析報告(股市情報局).md", "openai", "test"),
    )
    with ZipFile(BytesIO(_batch_report_zip(batch))) as archive:
        assert archive.namelist() == [
            "20261023-股市情報局-摘要報告.md",
            "影片2-20261023-股市情報局-摘要報告.md",
            "20261023-多來源統計分析報告(股市情報局).md",
        ]
        assert archive.read(archive.namelist()[0]).decode("utf-8") == report.markdown.rstrip()


def test_quick_video_report_requires_local_company_directory_before_asr(tmp_path):
    called = False

    def fake_asr_runner(source_input, *, on_progress):
        nonlocal called
        called = True
        raise AssertionError("ASR must not run without a company directory")

    result = run_quick_video_research_report(
        _request(),
        BrowserSessionAsrInput(page_url="https://example.test/video", asr_provider="openai"),
        stock_directory=None,
        asr_runner=fake_asr_runner,
    )

    assert called is False
    assert result.is_available is False
    assert "公司清單" in result.error
    assert result.events[-1].step_id == "validate"
    assert result.events[-1].status == "failed"


def test_quick_video_report_does_not_present_rule_based_fallback_as_openai_success(tmp_path):
    transcript_path = _write_transcript(tmp_path)

    def fake_asr_runner(source_input, *, on_progress):
        return _available_asr_result(tmp_path, transcript_path)

    result = run_quick_video_research_report(
        _request(),
        BrowserSessionAsrInput(page_url="https://example.test/video", asr_provider="openai"),
        stock_directory=_directory(),
        asr_runner=fake_asr_runner,
        analysis_client=FailedOpenAIAnalysisClient(),
    )

    assert result.is_available is False
    assert result.error == "provider unavailable"
    assert result.events[-1].step_id == "analysis"
    assert result.events[-1].status == "failed"
    assert "render" not in [event.step_id for event in result.events]


def _request() -> QuickVideoReportInput:
    return QuickVideoReportInput(
        video_url="https://example.test/video",
        published_date=date(2026, 10, 23),
        title="股市情報局",
    )


def _directory() -> TaiwanStockDirectory:
    return TaiwanStockDirectory(
        companies=(TaiwanListedCompany(code="2330", name="台積電", market="listed"),),
        collected_at="2026-10-23T00:00:00+00:00",
    )


def _write_transcript(tmp_path: Path) -> Path:
    transcript_path = tmp_path / "transcript.json"
    transcript_path.write_text(
        '{"text":"投顧提到 2330 台積電與 AI 需求。","segments":[{"start":0,"end":3,"text":"投顧提到 2330 台積電與 AI 需求。"}]}',
        encoding="utf-8",
    )
    return transcript_path


def _available_asr_result(tmp_path: Path, transcript_path: Path) -> BrowserSessionAsrResult:
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"audio")
    return BrowserSessionAsrResult(
        media_result=MediaAcquisitionResult(
            status="available",
            source_identifier="https://example.test/video",
            artifact=MediaArtifact(path=wav_path, artifact_type="audio_wav"),
            status_message="音訊已準備完成。",
        ),
        transcription=AsrTranscriptionResult(
            segments=(AsrTranscriptSegment("投顧提到 2330 台積電與 AI 需求。", 0, 3),),
            transcript_path=transcript_path,
        ),
    )
