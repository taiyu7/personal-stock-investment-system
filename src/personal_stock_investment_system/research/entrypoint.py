"""Phase-one research source analysis entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.markdown import render_research_report
from personal_stock_investment_system.research.output import ResearchReportOutputSettings, WrittenResearchReport, write_research_report_outputs
from personal_stock_investment_system.research.pdf import build_pdf_research_source
from personal_stock_investment_system.research.sources import ResearchReport, ResearchSource
from personal_stock_investment_system.research.youtube import (
    YouTubePublicClient,
    YouTubeTranscriptSegment,
    YouTubeVideoMetadata,
    build_youtube_research_source,
)

ResearchInputKind = Literal["manual_text", "pdf", "youtube_public"]


@dataclass(frozen=True)
class PhaseOneResearchInput:
    input_kind: ResearchInputKind
    title: str = ""
    manual_text: str = ""
    youtube_url: str = ""
    pdf_path: Path | str | None = None
    source_url: str = ""
    publisher: str = ""
    speaker: str = ""
    speakers: tuple[str, ...] = ()
    published_date: str = ""
    notes: str = ""


@dataclass(frozen=True)
class PhaseOneResearchResult:
    source: ResearchSource
    report: ResearchReport
    markdown: str
    written_outputs: tuple[WrittenResearchReport, ...] = ()
    statuses: tuple[str, ...] = ()


class TranscriptUnavailableYouTubeClient:
    def __init__(self, title: str = "", channel: str = "", published_date: str = "") -> None:
        self._metadata = YouTubeVideoMetadata(title=title, channel=channel, published_date=published_date)

    def fetch_metadata(self, video_id: str, youtube_url: str) -> YouTubeVideoMetadata:
        if self._metadata.title:
            return self._metadata
        return YouTubeVideoMetadata(title=f"YouTube 影片 {video_id}", channel=self._metadata.channel, published_date=self._metadata.published_date)

    def fetch_transcript(self, video_id: str) -> tuple[YouTubeTranscriptSegment, ...]:
        raise RuntimeError("transcript_unavailable")


def run_phase_one_research_source_analysis(
    source_input: PhaseOneResearchInput,
    *,
    output_settings: ResearchReportOutputSettings | None = None,
    youtube_client: YouTubePublicClient | None = None,
    report_date: date | None = None,
) -> PhaseOneResearchResult:
    statuses: list[str] = []
    source = _build_source(source_input, youtube_client=youtube_client, statuses=statuses)
    report = analyze_research_source(source)
    markdown = render_research_report(report)
    written_outputs = write_research_report_outputs(
        report,
        settings=output_settings or ResearchReportOutputSettings.no_local_files(),
        markdown=markdown,
        report_date=report_date,
    )
    if written_outputs:
        statuses.append(f"已輸出 {len(written_outputs)} 份 Markdown。")
    else:
        statuses.append("未輸出本機檔案，可在介面顯示或提供一次性下載。")
    return PhaseOneResearchResult(source=source, report=report, markdown=markdown, written_outputs=written_outputs, statuses=tuple(statuses))


def _build_source(
    source_input: PhaseOneResearchInput,
    *,
    youtube_client: YouTubePublicClient | None,
    statuses: list[str],
) -> ResearchSource:
    if source_input.input_kind == "manual_text":
        if not source_input.manual_text.strip():
            statuses.append("手動文字為空，分析結果會標記為未判定。")
        return ResearchSource(
            source_type="manual_text",
            title=source_input.title or "手動研究文字",
            source_url=source_input.source_url,
            publisher=source_input.publisher,
            speaker=source_input.speaker,
            speakers=source_input.speakers,
            published_date=source_input.published_date,
            raw_text=source_input.manual_text.strip(),
            markdown_text=source_input.manual_text.strip(),
            notes=source_input.notes,
        )
    if source_input.input_kind == "pdf":
        if source_input.pdf_path is None:
            raise ValueError("PDF input requires pdf_path.")
        source = build_pdf_research_source(
            source_input.pdf_path,
            title=source_input.title or None,
            source_url=source_input.source_url,
            publisher=source_input.publisher,
            speaker=source_input.speaker,
            speakers=source_input.speakers,
            published_date=source_input.published_date,
            notes=source_input.notes,
        )
        if not source.raw_text.strip():
            statuses.append("PDF 未抽取到文字，後續分析會標記為未判定或待查證。")
        else:
            statuses.append("PDF to Markdown 前處理完成。")
        return source
    if source_input.input_kind == "youtube_public":
        if not source_input.youtube_url.strip():
            raise ValueError("YouTube input requires youtube_url.")
        client = youtube_client or TranscriptUnavailableYouTubeClient(
            title=source_input.title,
            channel=source_input.publisher,
            published_date=source_input.published_date,
        )
        result = build_youtube_research_source(
            source_input.youtube_url,
            client=client,
            manual_text=source_input.manual_text,
            optional_title=source_input.title,
            optional_speaker=source_input.speaker,
            optional_notes=source_input.notes,
        )
        statuses.append(f"YouTube 逐字稿狀態：{result.transcript_status}")
        if result.transcript_status == "transcript_unavailable":
            statuses.append("未取得公開逐字稿，請手動貼上逐字稿或摘要後再分析。")
        return result.source
    raise ValueError(f"Unsupported input kind: {source_input.input_kind}")
