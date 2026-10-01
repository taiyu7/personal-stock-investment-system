"""Complete video research report aggregation and Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from personal_stock_investment_system.research.analysis_provider import ResearchAnalysisResult
from personal_stock_investment_system.research.asr import AsrTranscriptSegment, AsrTranscriptionResult
from personal_stock_investment_system.research.markdown import render_research_report
from personal_stock_investment_system.research.media import MediaArtifact
from personal_stock_investment_system.research.output import (
    ResearchReportOutputSettings,
    WrittenResearchReport,
    write_research_report_outputs,
)
from personal_stock_investment_system.research.screenshots import ScreenshotCaptureResult
from personal_stock_investment_system.research.sources import ResearchReport, SourceReference
from personal_stock_investment_system.research.vlm import VlmChartAnalysisResult

VideoReportStatus = Literal["available", "partial"]


@dataclass(frozen=True)
class VideoResearchReportInput:
    analysis_result: ResearchAnalysisResult
    media_artifact: MediaArtifact | None = None
    transcription_result: AsrTranscriptionResult | None = None
    screenshot_results: tuple[ScreenshotCaptureResult, ...] = ()
    vlm_results: tuple[VlmChartAnalysisResult, ...] = ()
    asr_backend: str = "未判定"
    asr_model: str = ""


@dataclass(frozen=True)
class VideoResearchReportResult:
    report: ResearchReport
    markdown: str
    status: VideoReportStatus
    missing_items: tuple[str, ...] = ()
    written_outputs: tuple[WrittenResearchReport, ...] = ()


def run_video_research_report_pipeline(
    pipeline_input: VideoResearchReportInput,
    *,
    output_settings: ResearchReportOutputSettings | None = None,
    report_date: date | None = None,
) -> VideoResearchReportResult:
    """Aggregate completed adapter results; never invokes media, model, or screenshot providers."""

    markdown = render_video_research_report(pipeline_input)
    missing_items = _missing_items(pipeline_input)
    written = write_research_report_outputs(
        pipeline_input.analysis_result.report,
        settings=output_settings or ResearchReportOutputSettings.no_local_files(),
        markdown=markdown,
        report_date=report_date,
    )
    return VideoResearchReportResult(
        report=pipeline_input.analysis_result.report,
        markdown=markdown,
        status="partial" if missing_items else "available",
        missing_items=missing_items,
        written_outputs=written,
    )


def render_video_research_report(pipeline_input: VideoResearchReportInput) -> str:
    report = pipeline_input.analysis_result.report
    markdown = render_research_report(report).replace("# 研究來源分析報告", "# 完整影片研究報告", 1)
    markdown = _insert_before(
        markdown,
        "## 一句話摘要",
        _pipeline_metadata_lines(pipeline_input) + [""] + _timeline_lines(report),
    )
    markdown = _insert_before(
        markdown,
        "## 查核標記",
        _screenshot_lines(pipeline_input.screenshot_results, pipeline_input.vlm_results),
    )
    return markdown.rstrip() + "\n\n" + "\n".join(_transcript_lines(pipeline_input.transcription_result)) + "\n"


def _pipeline_metadata_lines(pipeline_input: VideoResearchReportInput) -> list[str]:
    media = pipeline_input.media_artifact
    transcription = pipeline_input.transcription_result
    analysis = pipeline_input.analysis_result
    return [
        "## Pipeline 資訊",
        "",
        f"- 媒體 artifact：{_display(str(media.path) if media else '')}",
        f"- 媒體類型：{_display(media.artifact_type if media else '')}",
        f"- 媒體來源：{_display(media.source_url if media else analysis.report.source.source_url)}",
        f"- ASR backend：{_display(pipeline_input.asr_backend)}",
        f"- ASR model：{_display(pipeline_input.asr_model)}",
        f"- ASR 狀態：{_display(transcription.status if transcription else '待補')}",
        f"- 逐字稿 artifact：{_display(str(transcription.transcript_path) if transcription and transcription.transcript_path else '')}",
        f"- LLM analyzer：{_display(analysis.provider)}",
        f"- LLM model：{_display(analysis.model)}",
        f"- LLM 狀態：{_display(analysis.status)}",
        "- 安全邊界：本報告整理來源內容，不提供自動下單、即時投資建議或獲利保證。",
    ]


def _timeline_lines(report: ResearchReport) -> list[str]:
    references = _report_references(report)
    lines = [
        "## 重要時間軸與結論引用",
        "",
        "| 時間／位置 | 類型 | 結論 | 原文引用 | 信心 |",
        "|---|---|---|---|---|",
    ]
    if not references:
        return lines + ["| 待補 | 待補 | 尚無可追溯結論 | 待補 | 未判定 |"]
    lines.extend(
        _table_row([reference.display_locator(), category, claim, reference.quote or "待補", reference.confidence])
        for category, claim, reference in references
    )
    return lines


def _report_references(report: ResearchReport) -> list[tuple[str, str, SourceReference]]:
    references: list[tuple[str, str, SourceReference]] = []
    for item in report.stock_opinions:
        _append_reference(references, "股票觀點", f"{item.stock} {item.company}：{item.opinion}", item.reference)
    for item in report.stock_relations:
        _append_reference(references, "族群／公司關聯", f"{item.stock} {item.company}：{item.rationale}", item.reference)
    for item in report.company_profiles:
        _append_reference(references, "公司資料", f"{item.stock} {item.company}：{item.main_business}", item.reference)
    for item in report.technical_notes:
        _append_reference(references, "技術分析", f"{item.stock}：{item.signal}；{item.rationale}", item.reference)
    for item in report.verification_issues:
        _append_reference(references, "查核", f"{item.target}：{item.claim}", item.reference)
    return references


def _append_reference(
    values: list[tuple[str, str, SourceReference]],
    category: str,
    claim: str,
    reference: SourceReference | None,
) -> None:
    if reference is not None:
        values.append((category, claim, reference))


def _screenshot_lines(
    screenshot_results: tuple[ScreenshotCaptureResult, ...],
    vlm_results: tuple[VlmChartAnalysisResult, ...],
) -> list[str]:
    lines = ["## 技術分析截圖與圖面理解", ""]
    if not screenshot_results:
        return lines + ["- 待補：尚未提供時間戳截圖結果。", ""]
    for index, capture in enumerate(screenshot_results, start=1):
        timestamp = _timestamp(capture.request.timestamp_seconds)
        lines.extend([f"### 截圖 {index} · {timestamp}", ""])
        if not capture.is_available() or capture.artifact is None:
            lines.extend(
                [
                    f"- 截圖狀態：待補（{_display(capture.status_message or capture.status)}）",
                    f"- 截圖理由：{_display(capture.request.reason)}",
                    f"- 原文引用：{_display(capture.request.quote)}",
                    f"- 錯誤：{_display(capture.error)}",
                    "",
                ]
            )
            continue
        artifact = capture.artifact
        lines.extend(
            [
                artifact.markdown_reference(f"{timestamp} 技術分析截圖"),
                "",
                f"- 截圖路徑：{artifact.path}",
                f"- 截圖理由：{_display(artifact.reason)}",
                f"- 原文引用：{_display(artifact.quote or (artifact.reference.quote if artifact.reference else ''))}",
                f"- 來源位置：{_display(artifact.reference.display_locator() if artifact.reference else timestamp)}",
            ]
        )
        vlm = _matching_vlm(artifact.path, artifact.timestamp_seconds, vlm_results)
        lines.extend(_vlm_lines(vlm))
        lines.append("")
    return lines


def _matching_vlm(
    screenshot_path: Path,
    timestamp_seconds: float,
    vlm_results: tuple[VlmChartAnalysisResult, ...],
) -> VlmChartAnalysisResult | None:
    path_key = str(screenshot_path)
    for result in vlm_results:
        if str(result.screenshot_path) == path_key:
            return result
    for result in vlm_results:
        if abs(result.timestamp_seconds - timestamp_seconds) < 0.001:
            return result
    return None


def _vlm_lines(result: VlmChartAnalysisResult | None) -> list[str]:
    if result is None:
        return ["- VLM 圖面分析：待補"]
    lines = [
        f"- VLM 狀態：{result.status}",
        f"- VLM provider／model：{_display(result.provider)}／{_display(result.model)}",
        f"- Prompt／schema version：{result.prompt_version}／{result.schema_version}",
        f"- 圖面類型／可讀性：{_display(result.chart_type)}／{result.readability}",
        f"- VLM 訊息：{_display(result.status_message)}",
    ]
    if result.error:
        lines.append(f"- VLM 錯誤：{result.error}")
    lines.extend(
        [
            "",
            "| 圖面類別 | 可見內容 | 證據 | 信心 | 待查證 | 查證原因 |",
            "|---|---|---|---|---|---|",
        ]
    )
    if result.observations:
        lines.extend(
            _table_row(
                [
                    item.category,
                    item.description,
                    item.evidence,
                    item.confidence,
                    "是" if item.needs_verification else "否",
                    item.verification_reason,
                ]
            )
            for item in result.observations
        )
    else:
        lines.append("| 待補 | 無可用圖面 observation | 待補 | 未判定 | 是 | 模型未產生可驗證結果 |")
    if result.stock_candidates:
        lines.extend(
            [
                "",
                "| 圖面股票代號候選 | 公司名稱候選 | 信心 | 驗證狀態 |",
                "|---|---|---|---|",
            ]
        )
        lines.extend(
            _table_row([item.raw_code, item.raw_company_name, item.confidence, "待 #58 deterministic 驗證"])
            for item in result.stock_candidates
        )
    return lines


def _transcript_lines(transcription: AsrTranscriptionResult | None) -> list[str]:
    lines = ["## 逐字稿引用", ""]
    if transcription is None:
        return lines + ["- 待補：尚未提供 ASR 結果。"]
    if not transcription.segments:
        return lines + [f"- 待補：{_display(transcription.status_message)}"]
    lines.extend(["| 時間 | 逐字稿 |", "|---|---|"])
    lines.extend(_transcript_row(item) for item in transcription.segments)
    if transcription.warnings:
        lines.extend(["", "### ASR 警告", "", *[f"- {warning}" for warning in transcription.warnings]])
    return lines


def _transcript_row(segment: AsrTranscriptSegment) -> str:
    return _table_row([segment.display_timestamp(), segment.text])


def _missing_items(pipeline_input: VideoResearchReportInput) -> tuple[str, ...]:
    missing: list[str] = []
    if pipeline_input.media_artifact is None:
        missing.append("media_artifact")
    transcription = pipeline_input.transcription_result
    if transcription is None or transcription.status != "available" or not transcription.segments:
        missing.append("transcript")
    if not pipeline_input.analysis_result.is_available():
        missing.append("llm_analysis")
    if pipeline_input.analysis_result.report.technical_notes and not pipeline_input.screenshot_results:
        missing.append("screenshots")
    if any(not item.is_available() for item in pipeline_input.screenshot_results):
        missing.append("screenshots")
    available_screenshots = [item for item in pipeline_input.screenshot_results if item.is_available()]
    if available_screenshots and any(
        _matching_vlm(item.artifact.path, item.artifact.timestamp_seconds, pipeline_input.vlm_results) is None
        for item in available_screenshots
        if item.artifact is not None
    ):
        missing.append("vlm_analysis")
    if any(item.status in {"input_unavailable", "unsupported_provider", "analysis_failed"} for item in pipeline_input.vlm_results):
        missing.append("vlm_analysis")
    if any(item.status == "needs_verification" for item in pipeline_input.vlm_results):
        missing.append("vlm_verification")
    return tuple(dict.fromkeys(missing))


def _insert_before(markdown: str, heading: str, block: list[str]) -> str:
    marker = f"\n{heading}\n"
    insertion = "\n" + "\n".join(block).rstrip() + "\n\n" + heading + "\n"
    if marker not in markdown:
        return markdown.rstrip() + "\n\n" + "\n".join(block).rstrip() + "\n"
    return markdown.replace(marker, insertion, 1)


def _timestamp(value: float) -> str:
    total_seconds = max(0, int(value))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _table_row(values: list[str]) -> str:
    return "| " + " | ".join(_escape_table_cell(_display(value)) for value in values) + " |"


def _display(value: str) -> str:
    return value.strip() if value and value.strip() else "未判定"


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
