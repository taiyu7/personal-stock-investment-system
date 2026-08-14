from dataclasses import dataclass

from personal_stock_investment_system.research import (
    ResearchSourceImportResult,
    YouTubeTranscriptSegment,
    YouTubeVideoMetadata,
    build_youtube_research_source,
    parse_youtube_video_id,
)


def test_parse_youtube_video_id_from_public_url_shapes():
    assert parse_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://youtu.be/dQw4w9WgXcQ?si=sample") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert parse_youtube_video_id("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_invalid_youtube_url_has_clear_error():
    try:
        parse_youtube_video_id("https://notyoutube.com/watch?v=dQw4w9WgXcQ")
    except ValueError as error:
        assert "Unsupported YouTube URL" in str(error)
    else:
        raise AssertionError("Expected ValueError")


def test_youtube_research_source_uses_public_metadata_and_transcript():
    client = FakeYouTubeClient(
        metadata=YouTubeVideoMetadata(
            title="AI 伺服器與台股供應鏈",
            channel="公開財經頻道",
            published_date="2026-08-13",
            duration="PT12M34S",
        ),
        transcript=(
            YouTubeTranscriptSegment("研究員 A 看好 2330 台積電。", start_seconds=83.2),
            YouTubeTranscriptSegment("分析師 B 提醒估值風險。", start_seconds=125),
        ),
    )

    result = build_youtube_research_source("https://www.youtube.com/watch?v=dQw4w9WgXcQ", client=client)

    assert result.video_id == "dQw4w9WgXcQ"
    assert result.transcript_status == "available"
    assert isinstance(result.import_result, ResearchSourceImportResult)
    assert result.import_result.status == "available"
    assert result.import_result.is_available()
    assert result.import_result.source_identifier == "youtube:dQw4w9WgXcQ;timestamps:01:23-"
    assert result.source.source_type == "youtube_public"
    assert result.source.title == "AI 伺服器與台股供應鏈"
    assert result.source.publisher == "公開財經頻道"
    assert result.source.published_date == "2026-08-13"
    assert result.source.source_locator == "youtube:dQw4w9WgXcQ;timestamps:01:23-"
    assert "[01:23] 研究員 A 看好 2330 台積電。" in result.source.raw_text
    assert "- 逐字稿狀態：available" in result.source.markdown_text


def test_youtube_research_source_supports_manual_text_fallback():
    client = FakeYouTubeClient(
        metadata=YouTubeVideoMetadata(title="無字幕影片", channel="公開頻道"),
        transcript_error=RuntimeError("captions disabled"),
    )

    result = build_youtube_research_source(
        "https://youtu.be/dQw4w9WgXcQ",
        client=client,
        manual_text="使用者手動貼上的影片重點。",
        optional_speaker="分析師 A",
        optional_notes="公開影片，手動補文字。",
    )

    assert result.transcript_status == "manual_fallback"
    assert result.import_result.status == "manual_fallback"
    assert result.import_result.is_available()
    assert result.transcript_error == "captions disabled"
    assert result.source.speaker == "分析師 A"
    assert result.source.raw_text == "使用者手動貼上的影片重點。"
    assert "transcript_status=manual_fallback" in result.source.notes
    assert "transcript_error=captions disabled" in result.source.notes


def test_youtube_research_source_marks_transcript_unavailable_without_forcing_analysis():
    client = FakeYouTubeClient(
        metadata=YouTubeVideoMetadata(title="公開但無逐字稿影片"),
        transcript=(),
    )

    result = build_youtube_research_source("https://www.youtube.com/watch?v=dQw4w9WgXcQ", client=client)

    assert result.transcript_status == "transcript_unavailable"
    assert result.import_result.status == "transcript_unavailable"
    assert not result.import_result.is_available()
    assert result.import_result.status_message == "未取得公開逐字稿，且尚未提供手動文字。"
    assert result.source.raw_text == ""
    assert "transcript_unavailable：未取得公開逐字稿" in result.source.markdown_text
    assert result.source.notes == "transcript_status=transcript_unavailable"


@dataclass(frozen=True)
class FakeYouTubeClient:
    metadata: YouTubeVideoMetadata
    transcript: tuple[YouTubeTranscriptSegment, ...] = ()
    transcript_error: Exception | None = None

    def fetch_metadata(self, video_id: str, youtube_url: str) -> YouTubeVideoMetadata:
        return self.metadata

    def fetch_transcript(self, video_id: str) -> tuple[YouTubeTranscriptSegment, ...]:
        if self.transcript_error:
            raise self.transcript_error
        return self.transcript
