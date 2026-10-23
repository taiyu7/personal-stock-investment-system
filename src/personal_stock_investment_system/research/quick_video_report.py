"""One-click OpenAI video research report orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlparse

from personal_stock_investment_system.research.analysis_provider import (
    ResearchAnalysisClient,
    ResearchAnalysisSettings,
)
from personal_stock_investment_system.research.browser_asr import (
    BrowserSessionAsrInput,
    BrowserSessionAsrResult,
    run_browser_session_asr_pipeline,
)
from personal_stock_investment_system.research.entrypoint import (
    PhaseOneResearchInput,
    PhaseOneResearchResult,
    run_phase_one_research_source_analysis,
)
from personal_stock_investment_system.research.media import safe_filename
from personal_stock_investment_system.research.output import ResearchReportOutputSettings
from personal_stock_investment_system.research.stock_validation import TaiwanStockDirectory

QuickReportStepStatus = Literal["pending", "running", "success", "failed"]
QuickReportProgressCallback = Callable[["QuickReportProgressEvent"], None]
BrowserAsrRunner = Callable[..., BrowserSessionAsrResult]


@dataclass(frozen=True)
class QuickVideoReportInput:
    video_url: str
    published_date: date
    title: str


@dataclass(frozen=True)
class QuickReportProgressEvent:
    step_id: str
    label: str
    status: QuickReportStepStatus
    message: str = ""


@dataclass(frozen=True)
class QuickVideoReportResult:
    request: QuickVideoReportInput
    filename: str
    events: tuple[QuickReportProgressEvent, ...]
    browser_asr_result: BrowserSessionAsrResult | None = None
    research_result: PhaseOneResearchResult | None = None
    error: str = ""

    @property
    def markdown(self) -> str:
        return self.research_result.markdown if self.research_result is not None else ""

    @property
    def is_available(self) -> bool:
        return bool(self.research_result and self.research_result.analysis_result.is_available() and not self.error)


def build_quick_video_report_filename(request: QuickVideoReportInput) -> str:
    return f"{request.published_date:%Y%m%d}-{safe_filename(request.title)}-摘要報告.md"


def run_quick_video_research_report(
    request: QuickVideoReportInput,
    browser_asr_input: BrowserSessionAsrInput,
    *,
    stock_directory: TaiwanStockDirectory | None,
    asr_runner: BrowserAsrRunner = run_browser_session_asr_pipeline,
    analysis_client: ResearchAnalysisClient | None = None,
    progress_callback: QuickReportProgressCallback | None = None,
) -> QuickVideoReportResult:
    """Run the fixed OpenAI pipeline without writing a report to local files."""

    events: list[QuickReportProgressEvent] = []

    def emit(step_id: str, label: str, status: QuickReportStepStatus, message: str = "") -> None:
        event = QuickReportProgressEvent(step_id=step_id, label=label, status=status, message=message)
        events.append(event)
        if progress_callback is not None:
            progress_callback(event)

    filename = build_quick_video_report_filename(request)
    emit("validate", "驗證輸入與公司清單", "running")
    validation_error = _quick_report_validation_error(request, stock_directory)
    if validation_error:
        emit("validate", "驗證輸入與公司清單", "failed", validation_error)
        return QuickVideoReportResult(request=request, filename=filename, events=tuple(events), error=validation_error)
    emit("validate", "驗證輸入與公司清單", "success", "已載入本機公司清單，將強制執行股票身分查核。")

    def on_asr_progress(stage: str, status: str, message: str) -> None:
        if stage == "media":
            emit("media", "取得影片媒體並轉換 ASR 音訊", _progress_status(status), message)
        elif stage == "transcription":
            emit("transcription", "OpenAI 產生逐字稿", _progress_status(status), message)

    browser_result = asr_runner(browser_asr_input, on_progress=on_asr_progress)
    if not browser_result.media_result.is_available():
        error = browser_result.media_result.error or browser_result.media_result.status_message
        _ensure_failed(events, emit, "media", "取得影片媒體並轉換 ASR 音訊", error)
        return QuickVideoReportResult(
            request=request,
            filename=filename,
            events=tuple(events),
            browser_asr_result=browser_result,
            error=error,
        )
    transcription = browser_result.transcription
    if transcription is None or transcription.status != "available" or transcription.transcript_path is None:
        error = (transcription.error if transcription is not None else "") or (
            transcription.status_message if transcription is not None else "未產生逐字稿。"
        )
        _ensure_failed(events, emit, "transcription", "OpenAI 產生逐字稿", error)
        return QuickVideoReportResult(
            request=request,
            filename=filename,
            events=tuple(events),
            browser_asr_result=browser_result,
            error=error,
        )

    def on_research_progress(stage: str, status: str, message: str) -> None:
        if stage == "analysis":
            emit("analysis", "OpenAI 研究彙整", _progress_status(status), message)
        elif stage == "stock_validation":
            emit("render", "查核股票身分並產生 Markdown", _progress_status(status), message)

    research_result = run_phase_one_research_source_analysis(
        source_input=_phase_one_input(request, transcription.transcript_path),
        output_settings=ResearchReportOutputSettings.no_local_files(),
        analysis_settings=ResearchAnalysisSettings(provider="openai", report_style="structured_report"),
        analysis_client=analysis_client,
        stock_directory=stock_directory,
        report_date=request.published_date,
        progress_callback=on_research_progress,
        stop_on_analysis_failure=True,
    )
    if not research_result.analysis_result.is_available():
        error = research_result.analysis_result.error or research_result.analysis_result.status_message
        _ensure_failed(events, emit, "analysis", "OpenAI 研究彙整", error)
        return QuickVideoReportResult(
            request=request,
            filename=filename,
            events=tuple(events),
            browser_asr_result=browser_result,
            research_result=research_result,
            error=error,
        )

    emit("complete", "摘要報告完成", "success", "已完成公司清單查核，可預覽或下載 Markdown。")
    return QuickVideoReportResult(
        request=request,
        filename=filename,
        events=tuple(events),
        browser_asr_result=browser_result,
        research_result=research_result,
    )


def _phase_one_input(request: QuickVideoReportInput, transcript_path: Path) -> PhaseOneResearchInput:
    return PhaseOneResearchInput(
        input_kind="asr_transcript_json",
        title=request.title,
        transcript_json_path=Path(transcript_path),
        source_url=request.video_url,
        published_date=request.published_date.isoformat(),
    )


def _quick_report_validation_error(request: QuickVideoReportInput, stock_directory: TaiwanStockDirectory | None) -> str:
    if not request.video_url.strip():
        return "請輸入影片連結。"
    parsed = urlparse(request.video_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "影片連結必須是有效的 HTTP(S) URL。"
    if not request.title.strip():
        return "請輸入影片名稱。"
    if stock_directory is None or not stock_directory.companies:
        return "本機沒有可用公司清單。請先在進階模式同步官方上市／上櫃公司清單，再重新產生報告。"
    return ""


def _progress_status(status: str) -> QuickReportStepStatus:
    if status == "success":
        return "success"
    if status == "failed":
        return "failed"
    return "running"


def _ensure_failed(
    events: list[QuickReportProgressEvent],
    emit: Callable[[str, str, QuickReportStepStatus, str], None],
    step_id: str,
    label: str,
    message: str,
) -> None:
    if not events or events[-1].step_id != step_id or events[-1].status != "failed":
        emit(step_id, label, "failed", message)
