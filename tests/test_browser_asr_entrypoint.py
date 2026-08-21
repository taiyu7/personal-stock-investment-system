from pathlib import Path

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BrowserSessionAsrInput,
    DiscoveredMediaRequest,
    MediaArtifact,
    run_browser_session_asr_pipeline,
)
from personal_stock_investment_system.research.browser_asr import _format_cli_result


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
