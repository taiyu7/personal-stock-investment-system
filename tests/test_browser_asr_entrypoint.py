from pathlib import Path

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BrowserSessionAsrInput,
    DiscoveredMediaRequest,
    MediaArtifact,
    run_existing_media_asr_pipeline,
    run_browser_session_asr_pipeline,
)
from personal_stock_investment_system.research.browser_asr import _format_cli_result
from personal_stock_investment_system.research.youtube_captions import CaptionFetchResult


class FakeDiscovery:
    def discover(self, page_url: str) -> tuple[DiscoveredMediaRequest, ...]:
        assert page_url == "https://example.test/member-video"
        return (DiscoveredMediaRequest("https://cdn.example.test/index.m3u8"),)


class FakeDownloader:
    def download(self, media_request: DiscoveredMediaRequest, output_dir: Path) -> MediaArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = output_dir / "downloaded.mp4"
        artifact_path.write_bytes(b"fake media")
        return MediaArtifact(path=artifact_path, source_url=media_request.url, artifact_type="stream")


class FakePreprocessor:
    def to_asr_wav(self, artifact: MediaArtifact, output_path: Path) -> MediaArtifact:
        assert artifact.path.name == "downloaded.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake wav")
        return MediaArtifact(
            path=output_path,
            source_url=artifact.source_url,
            artifact_type="audio_wav",
            mime_type="audio/wav",
            sample_rate_hz=16000,
            channels=1,
        )


class FakeSpeechToText:
    def __init__(self) -> None:
        self.audio_path: Path | None = None

    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        self.audio_path = audio_path
        return AsrTranscriptionResult(
            segments=(AsrTranscriptSegment("投顧提到 2330 與 AI 需求", 1.0, 3.0),),
            transcript_path=audio_path.parent / "sample.json",
        )


def test_existing_youtube_captions_skip_media_and_asr(tmp_path):
    def unavailable_discovery(*args, **kwargs):
        raise AssertionError("不應下載影片")

    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title="測試影片", asr_provider="openai",
            transcript_output_dir=tmp_path,
        ),
        discovery=unavailable_discovery,
        speech_to_text=FakeSpeechToText(),
        caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(
            (AsrTranscriptSegment("台積電 2330", 1.0, 2.0),), "zh-TW"
        ),
    )
    assert result.is_available()
    assert result.media_result.artifact is None
    assert result.transcription is not None
    assert result.transcription.transcript_path is not None
    assert result.transcription.transcript_path.is_file()
    assert "現成字幕" in result.transcription.status_message


def test_unavailable_youtube_captions_fall_back_to_asr_with_reason(tmp_path):
    class YoutubeDiscovery:
        def discover(self, page_url):
            return (DiscoveredMediaRequest("https://cdn.example.test/index.m3u8"),)

    speech_to_text = FakeSpeechToText()
    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_stem="video-without-readable-captions", asr_provider="openai",
            raw_output_dir=tmp_path / "raw", wav_output_dir=tmp_path / "wav",
        ),
        discovery=YoutubeDiscovery(), downloader=FakeDownloader(), preprocessor=FakePreprocessor(),
        speech_to_text=speech_to_text,
        caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(error="字幕檢查 DNS 失敗"),
        browser_caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(error="瀏覽器也無法讀取"),
    )
    assert result.is_available()
    assert "字幕檢查 DNS 失敗" in result.caption_diagnostic
    assert speech_to_text.audio_path is not None


def test_browser_caption_fallback_skips_asr(tmp_path):
    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://www.youtube.com/watch?v=OH9SPy88MLk",
            asr_provider="openai", transcript_output_dir=tmp_path,
        ),
        caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(error="yt-dlp failed"),
        browser_caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(
            (AsrTranscriptSegment("瀏覽器字幕", 12.0, 14.0),), "zh-TW"
        ),
    )
    assert result.is_available()
    assert result.media_result.artifact is None
    assert result.caption_diagnostic == ""


def test_unreadable_existing_caption_track_does_not_start_asr(tmp_path):
    def unavailable_discovery(*args, **kwargs):
        raise AssertionError("字幕軌已存在時不應下載影片")

    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://www.youtube.com/watch?v=OH9SPy88MLk",
            asr_provider="openai", transcript_output_dir=tmp_path,
        ),
        discovery=unavailable_discovery,
        caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(error="YouTube 429"),
        browser_caption_fetcher=lambda *args, **kwargs: CaptionFetchResult(
            error="瀏覽器找到字幕軌但回傳空內容", track_found=True,
        ),
    )
    assert not result.is_available()
    assert result.status == "transcript_unavailable"
    assert "未啟動音訊轉錄" in result.media_result.status_message
    assert "429" in result.caption_diagnostic


def test_browser_session_asr_pipeline_can_stop_after_asr_ready_wav(tmp_path):
    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        discovery=FakeDiscovery(),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
    )

    assert result.status == "available"
    assert result.media_result.artifact is not None
    assert result.media_result.artifact.path == (tmp_path / "wav" / "episode-1-16k-mono.wav").resolve()
    assert result.transcription is None
    assert result.source_import_result is None


def test_browser_session_asr_pipeline_can_build_research_source_after_transcription(tmp_path):
    speech_to_text = FakeSpeechToText()

    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            title="會員影片測試",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        discovery=FakeDiscovery(),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        speech_to_text=speech_to_text,
    )

    assert result.status == "available"
    assert result.source_import_result is not None
    assert result.source_import_result.source.source_type == "local_audio"
    assert result.source_import_result.source.title == "會員影片測試"
    assert result.source_import_result.source.source_url == "https://example.test/member-video"
    assert "[00:01] 投顧提到 2330 與 AI 需求" in result.source_import_result.source.raw_text
    assert speech_to_text.audio_path == (tmp_path / "wav" / "episode-1-16k-mono.wav").resolve()


def test_browser_session_asr_pipeline_reports_media_and_transcription_progress(tmp_path):
    events = []

    run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        discovery=FakeDiscovery(),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        speech_to_text=FakeSpeechToText(),
        on_progress=lambda stage, status, message: events.append((stage, status, message)),
    )

    assert [(stage, status) for stage, status, _ in events] == [
        ("media", "running"),
        ("media", "success"),
        ("transcription", "running"),
        ("transcription", "success"),
    ]


def test_existing_media_can_continue_to_asr_without_downloading_again(tmp_path):
    class ReusePreprocessor:
        def to_asr_wav(self, artifact: MediaArtifact, output_path: Path) -> MediaArtifact:
            assert artifact.path.name == "downloaded.mkv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake wav")
            return MediaArtifact(path=output_path, source_url=artifact.source_url, artifact_type="audio_wav")

    existing_media = tmp_path / "raw" / "downloaded.mkv"
    existing_media.parent.mkdir(parents=True)
    existing_media.write_bytes(b"fake media")
    speech_to_text = FakeSpeechToText()

    result = run_existing_media_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            title="會員影片測試",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        existing_media,
        preprocessor=ReusePreprocessor(),
        speech_to_text=speech_to_text,
    )

    assert result.status == "available"
    assert result.media_result.artifact is not None
    assert result.media_result.artifact.path == (tmp_path / "wav" / "episode-1-16k-mono.wav").resolve()
    assert speech_to_text.audio_path == (tmp_path / "wav" / "episode-1-16k-mono.wav").resolve()


def test_existing_media_reports_a_clear_error_when_path_is_missing(tmp_path):
    result = run_existing_media_asr_pipeline(
        BrowserSessionAsrInput(page_url="https://example.test/member-video"),
        tmp_path / "missing.mkv",
    )

    assert result.status == "media_unavailable"
    assert "不存在" in result.media_result.status_message


def test_browser_session_asr_cli_result_includes_transcription_error(tmp_path):
    class FailingSpeechToText:
        def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
            return AsrTranscriptionResult(
                segments=(),
                transcript_path=audio_path.parent / "sample.json",
                status="transcript_unavailable",
                status_message="OpenAI ASR 轉錄失敗。",
                error="input_too_large",
            )

    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        discovery=FakeDiscovery(),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        speech_to_text=FailingSpeechToText(),
    )

    output = _format_cli_result(result)

    assert "asr_status=transcript_unavailable" in output
    assert "asr_error=input_too_large" in output


def test_browser_session_asr_cli_result_includes_transcription_warnings(tmp_path):
    class WarningSpeechToText:
        def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
            return AsrTranscriptionResult(
                segments=(AsrTranscriptSegment("投顧提到 2330", 1.0, 3.0),),
                transcript_path=audio_path.parent / "sample.json",
                warnings=("chunk 0 output_tokens=2048 reached warning threshold 2048; transcript may be truncated",),
            )

    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url="https://example.test/member-video",
            output_stem="episode-1",
            raw_output_dir=tmp_path / "raw",
            wav_output_dir=tmp_path / "wav",
        ),
        discovery=FakeDiscovery(),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        speech_to_text=WarningSpeechToText(),
    )

    output = _format_cli_result(result)

    assert "asr_warning=chunk 0 output_tokens=2048" in output
