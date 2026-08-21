from pathlib import Path

from personal_stock_investment_system.research import (
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BreezeAsrCliTranscriber,
    OpenVINOAsrConfig,
    OpenVINOAsrTranscriber,
    build_local_audio_research_source,
)
from personal_stock_investment_system.research.asr import _segments_from_whisper_json
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
