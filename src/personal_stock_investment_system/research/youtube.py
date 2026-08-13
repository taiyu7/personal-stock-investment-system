"""Public YouTube source import with transcript fallback support."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import parse_qs, urlparse

from personal_stock_investment_system.research.sources import ResearchSource

TranscriptStatus = Literal["available", "manual_fallback", "transcript_unavailable"]


@dataclass(frozen=True)
class YouTubeVideoMetadata:
    title: str = ""
    channel: str = ""
    published_date: str = ""
    duration: str = ""
    language: str = "zh-TW"


@dataclass(frozen=True)
class YouTubeTranscriptSegment:
    text: str
    start_seconds: float | None = None
    duration_seconds: float | None = None

    def display_timestamp(self) -> str:
        if self.start_seconds is None:
            return "timestamp:unknown"
        total_seconds = max(0, int(self.start_seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


@dataclass(frozen=True)
class YouTubeImportResult:
    source: ResearchSource
    video_id: str
    transcript_status: TranscriptStatus
    transcript_error: str = ""


class YouTubePublicClient(Protocol):
    def fetch_metadata(self, video_id: str, youtube_url: str) -> YouTubeVideoMetadata:
        """Fetch public video metadata without cookies or login state."""

    def fetch_transcript(self, video_id: str) -> tuple[YouTubeTranscriptSegment, ...]:
        """Fetch public transcript or captions when available."""


def parse_youtube_video_id(youtube_url: str) -> str:
    parsed = urlparse(youtube_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if _is_host(host, "youtu.be") and path_parts:
        return _validate_video_id(path_parts[0])

    if _is_host(host, "youtube.com") or _is_host(host, "youtube-nocookie.com"):
        if parsed.path == "/watch":
            video_ids = parse_qs(parsed.query).get("v", [])
            if video_ids:
                return _validate_video_id(video_ids[0])
        if path_parts and path_parts[0] in {"embed", "shorts", "live"} and len(path_parts) >= 2:
            return _validate_video_id(path_parts[1])

    raise ValueError(f"Unsupported YouTube URL or missing video id: {youtube_url}")


def build_youtube_research_source(
    youtube_url: str,
    *,
    client: YouTubePublicClient,
    manual_text: str = "",
    optional_title: str = "",
    optional_speaker: str = "",
    optional_notes: str = "",
) -> YouTubeImportResult:
    video_id = parse_youtube_video_id(youtube_url)
    metadata = client.fetch_metadata(video_id, youtube_url)
    transcript_segments, transcript_error = _fetch_transcript(client, video_id)
    transcript_status = _transcript_status(transcript_segments, manual_text)
    raw_text = _raw_text(transcript_segments, manual_text)
    markdown_text = _markdown_text(metadata, transcript_segments, manual_text, transcript_status)
    notes = _notes(optional_notes, transcript_status, transcript_error)
    source_locator = f"youtube:{video_id}"
    if transcript_segments:
        source_locator = f"{source_locator};timestamps:{transcript_segments[0].display_timestamp()}-"

    source = ResearchSource(
        source_type="youtube_public",
        title=optional_title or metadata.title or video_id,
        source_url=youtube_url,
        publisher=metadata.channel,
        speaker=optional_speaker,
        published_date=metadata.published_date,
        language=metadata.language,
        raw_text=raw_text,
        markdown_text=markdown_text,
        source_locator=source_locator,
        notes=notes,
    )
    return YouTubeImportResult(
        source=source,
        video_id=video_id,
        transcript_status=transcript_status,
        transcript_error=transcript_error,
    )


def _validate_video_id(video_id: str) -> str:
    cleaned = video_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", cleaned):
        raise ValueError(f"Invalid YouTube video id: {video_id}")
    return cleaned


def _is_host(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _fetch_transcript(
    client: YouTubePublicClient, video_id: str
) -> tuple[tuple[YouTubeTranscriptSegment, ...], str]:
    try:
        return client.fetch_transcript(video_id), ""
    except Exception as error:  # noqa: BLE001 - adapter errors become explicit fallback state.
        return (), str(error)


def _transcript_status(
    transcript_segments: tuple[YouTubeTranscriptSegment, ...],
    manual_text: str,
) -> TranscriptStatus:
    if transcript_segments:
        return "available"
    if manual_text.strip():
        return "manual_fallback"
    return "transcript_unavailable"


def _raw_text(transcript_segments: tuple[YouTubeTranscriptSegment, ...], manual_text: str) -> str:
    if transcript_segments:
        return "\n".join(f"[{segment.display_timestamp()}] {segment.text}" for segment in transcript_segments)
    return manual_text.strip()


def _markdown_text(
    metadata: YouTubeVideoMetadata,
    transcript_segments: tuple[YouTubeTranscriptSegment, ...],
    manual_text: str,
    transcript_status: TranscriptStatus,
) -> str:
    lines = [
        f"# {metadata.title or '未命名 YouTube 影片'}",
        "",
        f"- 頻道：{metadata.channel or '未判定'}",
        f"- 發布日期：{metadata.published_date or '未判定'}",
        f"- 影片長度：{metadata.duration or '未判定'}",
        f"- 逐字稿狀態：{transcript_status}",
        "",
        "## 文字內容",
        "",
    ]
    if transcript_segments:
        lines.extend(f"- [{segment.display_timestamp()}] {segment.text}" for segment in transcript_segments)
    elif manual_text.strip():
        lines.append(manual_text.strip())
    else:
        lines.append("transcript_unavailable：未取得公開逐字稿，且尚未提供手動文字。")
    return "\n".join(lines).strip() + "\n"


def _notes(optional_notes: str, transcript_status: TranscriptStatus, transcript_error: str) -> str:
    parts = [optional_notes.strip()] if optional_notes.strip() else []
    parts.append(f"transcript_status={transcript_status}")
    if transcript_error:
        parts.append(f"transcript_error={transcript_error}")
    return "\n".join(parts)
