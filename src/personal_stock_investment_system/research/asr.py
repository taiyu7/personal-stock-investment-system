"""Local speech-to-text adapters for research media sources."""

from __future__ import annotations

import json
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from personal_stock_investment_system.research.sources import ResearchSource, ResearchSourceImportResult, SourceImportStatus

DEFAULT_BREEZE_ASR_MODEL = "breeze-asr-25"


@dataclass(frozen=True)
class AsrTranscriptSegment:
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None

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
class AsrTranscriptionResult:
    segments: tuple[AsrTranscriptSegment, ...]
    transcript_path: Path | None = None
    status: SourceImportStatus = "available"
    status_message: str = "ASR 逐字稿可用。"
    error: str = ""


class SpeechToTextClient(Protocol):
    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        """Transcribe a local audio file into timestamped text segments."""


@dataclass(frozen=True)
class BreezeAsrCliConfig:
    model: str = DEFAULT_BREEZE_ASR_MODEL
    executable: str = "whisper"
    output_dir: Path | None = None
    language: str = "Chinese"


class BreezeAsrCliTranscriber:
    """Run the Breeze-ASR-25 Whisper CLI and read the generated JSON transcript."""

    def __init__(self, config: BreezeAsrCliConfig | None = None) -> None:
        self.config = config or BreezeAsrCliConfig()

    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        resolved_audio_path = audio_path.expanduser().resolve()
        if not resolved_audio_path.exists():
            return AsrTranscriptionResult(
                segments=(),
                status="media_unavailable",
                status_message="音訊檔不存在，無法執行 ASR。",
                error=str(resolved_audio_path),
            )
        output_dir = (self.config.output_dir or resolved_audio_path.parent / "transcripts").expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.config.executable,
            str(resolved_audio_path),
            "--model",
            self.config.model,
            "--output_format",
            "json",
            "--output_dir",
            str(output_dir),
        ]
        if self.config.language:
            command.extend(["--language", self.config.language])
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            return AsrTranscriptionResult(
                segments=(),
                status="unsupported_source",
                status_message="找不到 whisper CLI，尚未安裝 Breeze-ASR-25 工具環境。",
                error=str(error),
            )
        except subprocess.CalledProcessError as error:
            return AsrTranscriptionResult(
                segments=(),
                status="transcript_unavailable",
                status_message="Breeze-ASR-25 轉錄失敗。",
                error=(error.stderr or error.stdout or str(error)).strip(),
            )

        transcript_path = output_dir / f"{resolved_audio_path.stem}.json"
        if not transcript_path.exists():
            return AsrTranscriptionResult(
                segments=(),
                status="transcript_unavailable",
                status_message="Breeze-ASR-25 未產生 JSON 逐字稿。",
                error=str(transcript_path),
            )
        normalize_whisper_json_encoding(transcript_path)
        return AsrTranscriptionResult(
            segments=_segments_from_whisper_json(transcript_path),
            transcript_path=transcript_path,
        )


@dataclass(frozen=True)
class OpenVINOAsrConfig:
    model_dir: Path
    device: str = "GPU"
    output_dir: Path | None = None
    language: str = "zh"
    task: str = "transcribe"
    chunk_length_seconds: float = 25.0


class OpenVINOTranscriptionRunner(Protocol):
    def transcribe(self, audio_path: Path) -> str | tuple[AsrTranscriptSegment, ...]:
        """Transcribe an audio file using an OpenVINO-backed ASR model."""


class OpenVINOAsrTranscriber:
    """Run an OpenVINO-exported Breeze-ASR-25 model and return ASR segments."""

    def __init__(self, config: OpenVINOAsrConfig, runner: OpenVINOTranscriptionRunner | None = None) -> None:
        self.config = config
        self._runner = runner

    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        resolved_audio_path = audio_path.expanduser().resolve()
        if not resolved_audio_path.exists():
            return AsrTranscriptionResult(
                segments=(),
                status="media_unavailable",
                status_message="音訊檔不存在，無法執行 OpenVINO ASR。",
                error=str(resolved_audio_path),
            )

        model_dir = self.config.model_dir.expanduser().resolve()
        if self._runner is None and not model_dir.exists():
            return AsrTranscriptionResult(
                segments=(),
                status="unsupported_source",
                status_message="找不到 OpenVINO ASR 模型目錄。",
                error=str(model_dir),
            )

        output_dir = (self.config.output_dir or resolved_audio_path.parent / "openvino-transcripts").expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = output_dir / f"{resolved_audio_path.stem}.json"

        try:
            runner_output = (self._runner or _OpenVINOAsrRunner(self.config)).transcribe(resolved_audio_path)
        except ImportError as error:
            return AsrTranscriptionResult(
                segments=(),
                status="unsupported_source",
                status_message="尚未安裝 OpenVINO ASR 工具環境。",
                error=str(error),
            )
        except wave.Error as error:
            return AsrTranscriptionResult(
                segments=(),
                status="unsupported_source",
                status_message="OpenVINO ASR 目前只支援 PCM WAV 音訊；請先將音訊轉成 16kHz mono WAV。",
                error=str(error),
            )
        except Exception as error:
            return AsrTranscriptionResult(
                segments=(),
                status="transcript_unavailable",
                status_message="OpenVINO ASR 轉錄失敗。",
                error=str(error),
            )

        segments = _openvino_segments_from_runner_output(runner_output)
        text = "\n".join(segment.text for segment in segments).strip()

        if not segments or not text:
            return AsrTranscriptionResult(
                segments=(),
                transcript_path=transcript_path,
                status="transcript_unavailable",
                status_message="OpenVINO ASR 未產生文字。",
            )

        payload = {
            "text": text,
            "segments": [
                {"start": segment.start_seconds, "end": segment.end_seconds, "text": segment.text}
                for segment in segments
            ],
            "backend": "openvino",
            "device": self.config.device,
            "model_dir": str(model_dir),
        }
        transcript_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return AsrTranscriptionResult(
            segments=segments,
            transcript_path=transcript_path,
            status_message=f"OpenVINO ASR 逐字稿可用。device={self.config.device}",
        )


def build_local_audio_research_source(
    audio_path: Path | str,
    *,
    client: SpeechToTextClient,
    title: str = "",
    source_url: str = "",
    publisher: str = "",
    speaker: str = "",
    speakers: tuple[str, ...] = (),
    published_date: str = "",
    notes: str = "",
) -> ResearchSourceImportResult:
    resolved_audio_path = Path(audio_path).expanduser().resolve()
    transcription = client.transcribe(resolved_audio_path)
    raw_text = _raw_text(transcription.segments)
    source = ResearchSource(
        source_type="local_audio",
        title=title or resolved_audio_path.stem,
        source_url=source_url,
        publisher=publisher,
        speaker=speaker,
        speakers=speakers,
        published_date=published_date,
        raw_text=raw_text,
        markdown_text=_markdown_text(resolved_audio_path, transcription),
        source_locator=f"audio:{resolved_audio_path}",
        notes=_notes(notes, transcription),
    )
    return ResearchSourceImportResult(
        source=source,
        status=transcription.status,
        source_identifier=str(resolved_audio_path),
        status_message=transcription.status_message,
        error=transcription.error,
    )


def _segments_from_whisper_json(transcript_path: Path) -> tuple[AsrTranscriptSegment, ...]:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    return tuple(
        AsrTranscriptSegment(
            text=str(segment.get("text", "")).strip(),
            start_seconds=_float_or_none(segment.get("start")),
            end_seconds=_float_or_none(segment.get("end")),
        )
        for segment in segments
        if str(segment.get("text", "")).strip()
    )


def normalize_whisper_json_encoding(transcript_path: Path) -> None:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    transcript_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _OpenVINOAsrRunner:
    def __init__(self, config: OpenVINOAsrConfig) -> None:
        self.config = config

    def transcribe(self, audio_path: Path) -> tuple[AsrTranscriptSegment, ...]:
        from optimum.intel.openvino import OVModelForSpeechSeq2Seq
        from transformers import AutoProcessor

        samples, sample_rate = _read_pcm_wav(audio_path)
        processor = AutoProcessor.from_pretrained(self.config.model_dir)
        model = OVModelForSpeechSeq2Seq.from_pretrained(self.config.model_dir, device=self.config.device)
        segments: list[AsrTranscriptSegment] = []
        for start_frame, end_frame in _sample_windows(len(samples), sample_rate, self.config.chunk_length_seconds):
            chunk = samples[start_frame:end_frame]
            if not len(chunk):
                continue
            inputs = processor(chunk, sampling_rate=sample_rate, return_tensors="pt")
            generated_ids = model.generate(
                **inputs,
                language=self.config.language,
                task=self.config.task,
            )
            text = str(processor.batch_decode(generated_ids, skip_special_tokens=True)[0]).strip()
            if text:
                segments.append(
                    AsrTranscriptSegment(
                        text=text,
                        start_seconds=start_frame / sample_rate,
                        end_seconds=end_frame / sample_rate,
                    )
                )
        return tuple(segments)


def _openvino_segments_from_runner_output(
    runner_output: str | tuple[AsrTranscriptSegment, ...],
) -> tuple[AsrTranscriptSegment, ...]:
    if isinstance(runner_output, str):
        text = runner_output.strip()
        return (AsrTranscriptSegment(text=text),) if text else ()
    return tuple(segment for segment in runner_output if segment.text.strip())


def _sample_windows(sample_count: int, sample_rate: int, chunk_length_seconds: float):
    if sample_count <= 0:
        return
    chunk_size = int(max(1.0, chunk_length_seconds) * sample_rate)
    for start in range(0, sample_count, chunk_size):
        yield start, min(sample_count, start + chunk_size)


def _read_pcm_wav(audio_path: Path):
    import numpy as np

    with wave.open(str(audio_path), "rb") as audio:
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
        sample_rate = audio.getframerate()
        frames = audio.readframes(audio.getnframes())

    if sample_width == 1:
        samples = np.frombuffer(frames, dtype=np.uint8).astype("float32")
        samples = (samples - 128.0) / 128.0
    elif sample_width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype("float32") / 2147483648.0
    else:
        raise wave.Error(f"unsupported PCM sample width: {sample_width}")

    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples, sample_rate


def _raw_text(segments: tuple[AsrTranscriptSegment, ...]) -> str:
    return "\n".join(f"[{segment.display_timestamp()}] {segment.text}" for segment in segments)


def _markdown_text(audio_path: Path, transcription: AsrTranscriptionResult) -> str:
    lines = [
        f"# {audio_path.stem}",
        "",
        f"- 音訊路徑：{audio_path}",
        f"- ASR 狀態：{transcription.status}",
        f"- 逐字稿檔案：{transcription.transcript_path or '未產生'}",
        "",
        "## 文字內容",
        "",
    ]
    if transcription.segments:
        lines.extend(f"- [{segment.display_timestamp()}] {segment.text}" for segment in transcription.segments)
    else:
        lines.append(transcription.status_message)
    return "\n".join(lines).strip() + "\n"


def _notes(notes: str, transcription: AsrTranscriptionResult) -> str:
    parts = [notes.strip()] if notes.strip() else []
    parts.append(f"asr_status={transcription.status}")
    if transcription.error:
        parts.append(f"asr_error={transcription.error}")
    return "\n".join(parts)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
