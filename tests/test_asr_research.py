from pathlib import Path

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BreezeAsrCliTranscriber,
    OpenAIAsrConfig,
    OpenAIAsrTranscriber,
    OpenVINOAsrConfig,
    OpenVINOAsrTranscriber,
    build_local_audio_research_source,
)
from personal_stock_investment_system.research.asr import _segments_from_whisper_json
from personal_stock_investment_system.research.asr import _openai_segments_from_chunk_payloads
from personal_stock_investment_system.research.asr import normalize_whisper_json_encoding


class FakeSpeechToTextClient:
    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        return AsrTranscriptionResult(
            segments=(
                AsrTranscriptSegment("研究員提到 2330 台積電受惠 AI 伺服器。", 1.2, 5.6),
                AsrTranscriptSegment("但估值風險需要留意。", 8.0, 10.0),
            ),
            transcript_path=audio_path.parent / "transcripts" / f"{audio_path.stem}.json",
        )


class FakeOpenVINORunner:
    def __init__(self, text: str = "投信買超 AI 伺服器族群。") -> None:
        self.text = text
        self.audio_path: Path | None = None

    def transcribe(self, audio_path: Path) -> str:
        self.audio_path = audio_path
        return self.text


class FakeSegmentOpenVINORunner:
    def transcribe(self, audio_path: Path) -> tuple[AsrTranscriptSegment, ...]:
        return (
            AsrTranscriptSegment("第一段內容。", 0.0, 25.0),
            AsrTranscriptSegment("第二段內容。", 25.0, 50.0),
        )


class FakeOpenAITranscriptionResponse:
    def __init__(self, usage: dict[str, object] | None = None) -> None:
        self.usage = usage or {"type": "tokens", "total_tokens": 123}

    def model_dump(self):
        return {
            "text": "研究員提到 2330 台積電與 2303 聯電。",
            "segments": [
                {"start": 0.0, "end": 3.5, "text": "研究員提到 2330 台積電。"},
                {"start": 3.5, "end": 6.0, "text": "也提到 2303 聯電。"},
            ],
            "usage": self.usage,
        }


class FakeOpenAITranscriptions:
    def __init__(self, usage: dict[str, object] | None = None) -> None:
        self.kwargs = {}
        self.usage = usage

    def create(self, **kwargs: object) -> FakeOpenAITranscriptionResponse:
        self.kwargs = kwargs
        return FakeOpenAITranscriptionResponse(self.usage)


class FakeOpenAIAudio:
    def __init__(self, usage: dict[str, object] | None = None) -> None:
        self.transcriptions = FakeOpenAITranscriptions(usage)


class FakeOpenAIClient:
    def __init__(self, usage: dict[str, object] | None = None) -> None:
        self.audio = FakeOpenAIAudio(usage)


def test_build_local_audio_research_source_from_asr_segments(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")

    result = build_local_audio_research_source(
        audio_path,
        client=FakeSpeechToTextClient(),
        title="測試音訊",
        speaker="研究員 A",
    )

    assert result.status == "available"
    assert result.source.source_type == "local_audio"
    assert result.source.title == "測試音訊"
    assert result.source.speaker == "研究員 A"
    assert "[00:01] 研究員提到 2330 台積電受惠 AI 伺服器。" in result.source.raw_text
    assert "逐字稿檔案" in result.source.markdown_text
    assert result.source.source_locator.startswith("audio:")


def test_breeze_asr_cli_transcriber_reports_missing_audio(tmp_path):
    transcriber = BreezeAsrCliTranscriber()

    result = transcriber.transcribe(tmp_path / "missing.wav")

    assert result.status == "media_unavailable"
    assert result.segments == ()
    assert "不存在" in result.status_message


def test_openvino_asr_transcriber_writes_single_segment_transcript(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    output_dir = tmp_path / "transcripts"
    runner = FakeOpenVINORunner()
    transcriber = OpenVINOAsrTranscriber(
        OpenVINOAsrConfig(
            model_dir=tmp_path / "missing-model-ok-with-fake-runner",
            device="GPU",
            output_dir=output_dir,
        ),
        runner=runner,
    )

    result = transcriber.transcribe(audio_path)

    assert result.status == "available"
    assert result.segments == (AsrTranscriptSegment("投信買超 AI 伺服器族群。"),)
    assert result.transcript_path == output_dir / "sample.json"
    assert result.transcript_path.read_text(encoding="utf-8")
    assert runner.audio_path == audio_path.resolve()


def test_openvino_asr_transcriber_writes_timestamped_segments(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    output_dir = tmp_path / "transcripts"
    transcriber = OpenVINOAsrTranscriber(
        OpenVINOAsrConfig(
            model_dir=tmp_path / "missing-model-ok-with-fake-runner",
            device="GPU",
            output_dir=output_dir,
        ),
        runner=FakeSegmentOpenVINORunner(),
    )

    result = transcriber.transcribe(audio_path)

    assert result.status == "available"
    assert result.segments == (
        AsrTranscriptSegment("第一段內容。", 0.0, 25.0),
        AsrTranscriptSegment("第二段內容。", 25.0, 50.0),
    )
    transcript_text = result.transcript_path.read_text(encoding="utf-8")
    assert '"start": 25.0' in transcript_text
    assert '"text": "第一段內容。\\n第二段內容。"' in transcript_text


def test_openvino_asr_transcriber_reports_missing_audio(tmp_path):
    transcriber = OpenVINOAsrTranscriber(
        OpenVINOAsrConfig(model_dir=tmp_path / "model"),
        runner=FakeOpenVINORunner(),
    )

    result = transcriber.transcribe(tmp_path / "missing.wav")

    assert result.status == "media_unavailable"
    assert result.segments == ()
    assert "不存在" in result.status_message


def test_openvino_asr_transcriber_reports_missing_model_without_runner(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    transcriber = OpenVINOAsrTranscriber(OpenVINOAsrConfig(model_dir=tmp_path / "missing-model"))

    result = transcriber.transcribe(audio_path)

    assert result.status == "unsupported_source"
    assert result.segments == ()
    assert "模型目錄" in result.status_message


def test_openai_asr_transcriber_writes_transcript_json_from_fake_response(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    output_dir = tmp_path / "openai-transcripts"
    fake_client = FakeOpenAIClient()
    transcriber = OpenAIAsrTranscriber(
        OpenAIAsrConfig(
            model="gpt-test-transcribe",
            output_dir=output_dir,
            language="zh",
        ),
        api_key="test-key",
        client=fake_client,
    )

    result = transcriber.transcribe(audio_path)

    assert result.status == "available"
    assert result.segments == (
        AsrTranscriptSegment("研究員提到 2330 台積電。", 0.0, 3.5),
        AsrTranscriptSegment("也提到 2303 聯電。", 3.5, 6.0),
    )
    assert result.transcript_path == output_dir / "sample.json"
    transcript_text = result.transcript_path.read_text(encoding="utf-8")
    assert '"backend": "openai"' in transcript_text
    assert '"model": "gpt-test-transcribe"' in transcript_text
    assert '"chunk_length_seconds": 180.0' in transcript_text
    assert '"total_tokens": 123' in transcript_text
    assert fake_client.audio.transcriptions.kwargs["model"] == "gpt-test-transcribe"
    assert fake_client.audio.transcriptions.kwargs["language"] == "zh"
    assert fake_client.audio.transcriptions.kwargs["response_format"] == "json"


def test_openai_asr_transcriber_reads_env_quality_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", "gpt-env-transcribe")
    monkeypatch.setenv("OPENAI_AUDIO_TRANSCRIPTION_PROMPT", "台股詞彙：台積電、CPO、瀚荃。")
    monkeypatch.setenv("OPENAI_AUDIO_CHUNK_LENGTH_SECONDS", "120")
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    output_dir = tmp_path / "openai-transcripts"
    fake_client = FakeOpenAIClient()

    transcriber = OpenAIAsrTranscriber(
        OpenAIAsrConfig(output_dir=output_dir),
        api_key="test-key",
        client=fake_client,
    )
    result = transcriber.transcribe(audio_path)

    assert result.status == "available"
    assert transcriber.config.model == "gpt-env-transcribe"
    assert transcriber.config.prompt == "台股詞彙：台積電、CPO、瀚荃。"
    assert transcriber.config.chunk_length_seconds == 120.0
    assert fake_client.audio.transcriptions.kwargs["prompt"] == "台股詞彙：台積電、CPO、瀚荃。"


def test_openai_asr_transcriber_warns_when_output_tokens_hit_threshold(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    output_dir = tmp_path / "openai-transcripts"
    fake_client = FakeOpenAIClient({"type": "tokens", "total_tokens": 2500, "output_tokens": 2048})
    transcriber = OpenAIAsrTranscriber(
        OpenAIAsrConfig(
            model="gpt-test-transcribe",
            output_dir=output_dir,
            output_token_warning_threshold=2048,
        ),
        api_key="test-key",
        client=fake_client,
    )

    result = transcriber.transcribe(audio_path)

    assert result.warnings == (
        "chunk 0 output_tokens=2048 reached warning threshold 2048; transcript may be truncated",
    )
    assert "警示=1" in result.status_message
    transcript_text = result.transcript_path.read_text(encoding="utf-8")
    assert '"warnings": [' in transcript_text
    assert "output_tokens=2048" in transcript_text


def test_openai_asr_transcriber_reports_missing_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")

    result = OpenAIAsrTranscriber(OpenAIAsrConfig(model="gpt-test-transcribe")).transcribe(audio_path)

    assert result.status == "unsupported_source"
    assert result.error == "missing_openai_api_key"
    assert "OPENAI_API_KEY" in result.status_message


def test_openai_chunk_payloads_are_combined_with_offsets():
    segments = _openai_segments_from_chunk_payloads(
        [
            {"text": "第一段", "segments": [{"start": 1.0, "end": 2.0, "text": "第一段"}]},
            {"text": "第二段"},
        ],
        chunk_length_seconds=600.0,
    )

    assert segments == (
        AsrTranscriptSegment("第一段", 1.0, 2.0),
        AsrTranscriptSegment("第二段", 600.0, None),
    )


def test_build_local_audio_research_source_from_openvino_segments(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake wav")
    transcriber = OpenVINOAsrTranscriber(
        OpenVINOAsrConfig(
            model_dir=tmp_path / "fake-model",
            output_dir=tmp_path / "transcripts",
        ),
        runner=FakeOpenVINORunner("外資回補被動元件。"),
    )

    result = build_local_audio_research_source(audio_path, client=transcriber, title="投顧片段")

    assert result.status == "available"
    assert "[timestamp:unknown] 外資回補被動元件。" in result.source.raw_text
    assert "OpenVINO ASR 逐字稿可用" in result.status_message
    assert "asr_status=available" in result.source.notes


def test_segments_from_whisper_json_reads_timestamped_segments(tmp_path):
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(
        """
        {
          "segments": [
            {"start": 1.2, "end": 3.4, "text": " 第一段 "},
            {"start": 5, "end": 6, "text": ""},
            {"start": 7, "end": 8.5, "text": "第二段"}
          ]
        }
        """,
        encoding="utf-8",
    )

    segments = _segments_from_whisper_json(transcript_path)

    assert segments == (
        AsrTranscriptSegment("第一段", 1.2, 3.4),
        AsrTranscriptSegment("第二段", 7.0, 8.5),
    )


def test_normalize_whisper_json_encoding_writes_readable_utf8(tmp_path):
    transcript_path = tmp_path / "sample.json"
    transcript_path.write_text(
        '{"text": "\\u6211\\u611b\\u53f0\\u7063", "segments": [{"text": "\\u7b2c\\u4e00\\u6bb5"}]}',
        encoding="utf-8",
    )

    normalize_whisper_json_encoding(transcript_path)

    normalized = transcript_path.read_text(encoding="utf-8")
    assert "我愛台灣" in normalized
    assert "第一段" in normalized
    assert "\\u6211" not in normalized
