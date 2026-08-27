"""Local speech-to-text adapters for research media sources."""

from __future__ import annotations

import json
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from personal_stock_investment_system.research.sources import ResearchSource, ResearchSourceImportResult, SourceImportStatus

DEFAULT_BREEZE_ASR_MODEL = "breeze-asr-25"
DEFAULT_OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS = 180.0
DEFAULT_OPENAI_OUTPUT_TOKEN_WARNING_THRESHOLD = 2048


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
    warnings: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class OpenAIAsrConfig:
    model: str = DEFAULT_OPENAI_TRANSCRIPTION_MODEL
    output_dir: Path | None = None
    language: str = "zh"
    prompt: str = ""
    response_format: str = "json"
    chunk_length_seconds: float = DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS
    chunk_bitrate: str = "32k"
    ffmpeg_executable: str = "ffmpeg"
    output_token_warning_threshold: int = DEFAULT_OPENAI_OUTPUT_TOKEN_WARNING_THRESHOLD


class OpenAIAudioTranscriptionsClient(Protocol):
    class Audio(Protocol):
        class Transcriptions(Protocol):
            def create(self, **kwargs: object) -> object:
                """Create an OpenAI audio transcription."""

        transcriptions: Transcriptions

    audio: Audio


class OpenAIAsrTranscriber:
    """Transcribe an audio file with OpenAI Audio Transcriptions API."""

    def __init__(
        self,
        config: OpenAIAsrConfig | None = None,
        *,
        api_key: str | None = None,
        client: OpenAIAudioTranscriptionsClient | None = None,
    ) -> None:
        env_model = os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", "")
        env_prompt = os.getenv("OPENAI_AUDIO_TRANSCRIPTION_PROMPT", "")
        env_chunk_seconds = _float_env(
            "OPENAI_AUDIO_CHUNK_LENGTH_SECONDS",
            DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS,
        )
        env_warning_threshold = _int_env(
            "OPENAI_AUDIO_OUTPUT_TOKEN_WARNING_THRESHOLD",
            DEFAULT_OPENAI_OUTPUT_TOKEN_WARNING_THRESHOLD,
        )
        resolved_config = config or OpenAIAsrConfig(
            model=env_model or DEFAULT_OPENAI_TRANSCRIPTION_MODEL,
            prompt=env_prompt,
            chunk_length_seconds=env_chunk_seconds,
            output_token_warning_threshold=env_warning_threshold,
        )
        self.config = OpenAIAsrConfig(
            model=_openai_model_value(resolved_config.model, env_model),
            output_dir=resolved_config.output_dir,
            language=resolved_config.language,
            prompt=resolved_config.prompt or env_prompt,
            response_format=resolved_config.response_format,
            chunk_length_seconds=_float_env_value(
                "OPENAI_AUDIO_CHUNK_LENGTH_SECONDS",
                resolved_config.chunk_length_seconds,
            ),
            chunk_bitrate=resolved_config.chunk_bitrate,
            ffmpeg_executable=resolved_config.ffmpeg_executable,
            output_token_warning_threshold=_int_env_value(
                "OPENAI_AUDIO_OUTPUT_TOKEN_WARNING_THRESHOLD",
                resolved_config.output_token_warning_threshold,
            ),
        )
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self._client = client

    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        resolved_audio_path = audio_path.expanduser().resolve()
        if not resolved_audio_path.exists():
            return AsrTranscriptionResult(
                segments=(),
                status="media_unavailable",
                status_message="音訊檔不存在，無法執行 OpenAI ASR。",
                error=str(resolved_audio_path),
            )
        if not self.api_key and self._client is None:
            return AsrTranscriptionResult(
                segments=(),
                status="unsupported_source",
                status_message="缺少 OPENAI_API_KEY，無法執行 OpenAI ASR。",
                error="missing_openai_api_key",
            )

        output_dir = (self.config.output_dir or resolved_audio_path.parent / "openai-transcripts").expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = output_dir / f"{resolved_audio_path.stem}.json"

        try:
            chunk_paths = self._audio_chunks(resolved_audio_path, output_dir)
            chunk_payloads = [
                _openai_transcription_payload(self._transcriptions_create(chunk_path))
                for chunk_path in chunk_paths
            ]
        except Exception as error:  # noqa: BLE001 - provider boundary returns explicit ASR status.
            return AsrTranscriptionResult(
                segments=(),
                transcript_path=transcript_path,
                status="transcript_unavailable",
                status_message="OpenAI ASR 轉錄失敗。",
                error=str(error),
            )

        segments = _openai_segments_from_chunk_payloads(chunk_payloads, self.config.chunk_length_seconds)
        text = "\n".join(segment.text for segment in segments).strip()

        if not text:
            return AsrTranscriptionResult(
                segments=(),
                transcript_path=transcript_path,
                status="transcript_unavailable",
                status_message="OpenAI ASR 未產生文字。",
            )

        transcript_payload: dict[str, object] = {
            "text": text,
            "segments": [
                {"start": segment.start_seconds, "end": segment.end_seconds, "text": segment.text}
                for segment in segments
            ],
            "backend": "openai",
            "model": self.config.model,
            "language": self.config.language,
            "chunk_length_seconds": self.config.chunk_length_seconds,
        }
        usage = [payload.get("usage") for payload in chunk_payloads if payload.get("usage") is not None]
        if usage:
            transcript_payload["usage"] = usage
        warnings = _openai_usage_warnings(chunk_payloads, self.config.output_token_warning_threshold)
        if warnings:
            transcript_payload["warnings"] = list(warnings)
        if len(chunk_payloads) > 1:
            transcript_payload["chunks"] = len(chunk_payloads)
        transcript_path.write_text(json.dumps(transcript_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        status_message = f"OpenAI ASR 逐字稿可用。model={self.config.model}"
        if warnings:
            status_message += f"；警示={len(warnings)}"
        return AsrTranscriptionResult(
            segments=segments,
            transcript_path=transcript_path,
            status_message=status_message,
            warnings=warnings,
        )

    def _transcriptions_create(self, audio_path: Path) -> object:
        with audio_path.open("rb") as audio_file:
            kwargs: dict[str, object] = {
                "file": audio_file,
                "model": self.config.model,
                "response_format": self.config.response_format,
            }
            if self.config.language:
                kwargs["language"] = self.config.language
            if self.config.prompt:
                kwargs["prompt"] = self.config.prompt
            return self._audio_client().audio.transcriptions.create(**kwargs)

    def _audio_chunks(self, audio_path: Path, output_dir: Path) -> tuple[Path, ...]:
        if self._client is not None:
            return (audio_path,)
        chunk_seconds = int(max(1.0, self.config.chunk_length_seconds))
        chunks_dir = output_dir / "chunks" / audio_path.stem
        chunks_dir.mkdir(parents=True, exist_ok=True)
        for old_chunk in chunks_dir.glob("*.mp3"):
            old_chunk.unlink()
        command = [
            self.config.ffmpeg_executable,
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            self.config.chunk_bitrate,
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-reset_timestamps",
            "1",
            str(chunks_dir / "%05d.mp3"),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("找不到 ffmpeg，無法將長音訊切段後送 OpenAI ASR。") from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            raise RuntimeError(f"OpenAI ASR 前處理切段失敗：{detail}") from error
        chunk_paths = tuple(sorted(chunks_dir.glob("*.mp3")))
        if not chunk_paths:
            raise RuntimeError("OpenAI ASR 前處理未產生音訊切段。")
        return chunk_paths

    def _audio_client(self) -> OpenAIAudioTranscriptionsClient:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("openai Python SDK is not installed.") from error
        return OpenAI(api_key=self.api_key)


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


def load_asr_transcription_result(transcript_path: Path | str) -> AsrTranscriptionResult:
    resolved_transcript_path = _resolve_local_transcript_path(transcript_path)
    if not resolved_transcript_path.exists():
        return AsrTranscriptionResult(
            segments=(),
            transcript_path=resolved_transcript_path,
            status="transcript_unavailable",
            status_message="逐字稿 JSON 檔不存在。",
            error=str(resolved_transcript_path),
        )
    try:
        segments = _segments_from_whisper_json(resolved_transcript_path)
    except Exception as error:
        return AsrTranscriptionResult(
            segments=(),
            transcript_path=resolved_transcript_path,
            status="transcript_unavailable",
            status_message="逐字稿 JSON 無法解析。",
            error=str(error),
        )
    if not segments:
        return AsrTranscriptionResult(
            segments=(),
            transcript_path=resolved_transcript_path,
            status="transcript_unavailable",
            status_message="逐字稿 JSON 未包含可用文字段落。",
        )
    return AsrTranscriptionResult(
        segments=segments,
        transcript_path=resolved_transcript_path,
        status_message="已讀取 ASR 逐字稿 JSON。",
    )


def build_transcript_json_research_source(
    transcript_path: Path | str,
    *,
    title: str = "",
    source_url: str = "",
    publisher: str = "",
    speaker: str = "",
    speakers: tuple[str, ...] = (),
    published_date: str = "",
    notes: str = "",
) -> ResearchSourceImportResult:
    resolved_transcript_path = _resolve_local_transcript_path(transcript_path)
    transcription = load_asr_transcription_result(resolved_transcript_path)
    raw_text = _raw_text(transcription.segments)
    source = ResearchSource(
        source_type="local_audio",
        title=title or resolved_transcript_path.stem,
        source_url=source_url,
        publisher=publisher,
        speaker=speaker,
        speakers=speakers,
        published_date=published_date,
        raw_text=raw_text,
        markdown_text=_transcript_json_markdown_text(resolved_transcript_path, transcription),
        source_locator=f"transcript:{resolved_transcript_path}",
        notes=_notes(notes, transcription),
    )
    return ResearchSourceImportResult(
        source=source,
        status=transcription.status,
        source_identifier=str(resolved_transcript_path),
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


def _resolve_local_transcript_path(path: Path | str) -> Path:
    raw_path = str(path).strip()
    resolved_path = Path(raw_path).expanduser()
    if resolved_path.exists():
        return resolved_path.resolve()

    normalized = raw_path.replace("\\", "/")
    marker = "personal-stock-investment-system/"
    if marker in normalized:
        relative_tail = normalized.split(marker, 1)[1]
        candidate = Path(relative_tail).expanduser()
        if candidate.exists():
            return candidate.resolve()

    return resolved_path.resolve()


def normalize_whisper_json_encoding(transcript_path: Path) -> None:
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    transcript_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _openai_transcription_payload(response: object) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    payload: dict[str, Any] = {}
    for key in ("text", "segments", "duration", "language", "usage"):
        value = getattr(response, key, None)
        if value is not None:
            payload[key] = value
    return payload


def _openai_segments_from_payload(payload: dict[str, Any]) -> tuple[AsrTranscriptSegment, ...]:
    return tuple(
        AsrTranscriptSegment(
            text=_string(segment.get("text"), ""),
            start_seconds=_float_or_none(segment.get("start")),
            end_seconds=_float_or_none(segment.get("end")),
        )
        for segment in _list(payload.get("segments"))
        if isinstance(segment, dict) and _string(segment.get("text"), "")
    )


def _openai_segments_from_chunk_payloads(
    payloads: list[dict[str, Any]],
    chunk_length_seconds: float,
) -> tuple[AsrTranscriptSegment, ...]:
    segments: list[AsrTranscriptSegment] = []
    for index, payload in enumerate(payloads):
        offset = index * max(1.0, chunk_length_seconds)
        chunk_segments = _openai_segments_from_payload(payload)
        if chunk_segments:
            segments.extend(_offset_segments(chunk_segments, offset))
            continue
        text = _string(payload.get("text"), "")
        if text:
            segments.append(AsrTranscriptSegment(text=text, start_seconds=offset))
    return tuple(segments)


def _offset_segments(
    segments: tuple[AsrTranscriptSegment, ...],
    offset_seconds: float,
) -> tuple[AsrTranscriptSegment, ...]:
    return tuple(
        AsrTranscriptSegment(
            text=segment.text,
            start_seconds=_add_offset(segment.start_seconds, offset_seconds),
            end_seconds=_add_offset(segment.end_seconds, offset_seconds),
        )
        for segment in segments
    )


def _add_offset(value: float | None, offset_seconds: float) -> float | None:
    return None if value is None else value + offset_seconds


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


def _transcript_json_markdown_text(transcript_path: Path, transcription: AsrTranscriptionResult) -> str:
    lines = [
        f"# {transcript_path.stem}",
        "",
        f"- 逐字稿檔案：{transcript_path}",
        f"- ASR 狀態：{transcription.status}",
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
    for warning in transcription.warnings:
        parts.append(f"asr_warning={warning}")
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


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "未判定") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _float_env_value(name: str, fallback: float) -> float:
    if os.getenv(name, "").strip():
        return _float_env(name, fallback)
    return fallback


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _int_env_value(name: str, fallback: int) -> int:
    if os.getenv(name, "").strip():
        return _int_env(name, fallback)
    return fallback


def _openai_model_value(config_model: str, env_model: str) -> str:
    if config_model and config_model != DEFAULT_OPENAI_TRANSCRIPTION_MODEL:
        return config_model
    return env_model or config_model or DEFAULT_OPENAI_TRANSCRIPTION_MODEL


def _openai_usage_warnings(
    chunk_payloads: list[dict[str, Any]],
    threshold: int,
) -> tuple[str, ...]:
    if threshold <= 0:
        return ()
    warnings: list[str] = []
    for index, payload in enumerate(chunk_payloads):
        output_tokens = _usage_output_tokens(payload.get("usage"))
        if output_tokens is not None and output_tokens >= threshold:
            warnings.append(
                f"chunk {index} output_tokens={output_tokens} reached warning threshold {threshold}; transcript may be truncated"
            )
    return tuple(warnings)


def _usage_output_tokens(usage: object) -> int | None:
    if isinstance(usage, dict):
        value = usage.get("output_tokens")
        if value is None and isinstance(usage.get("output_tokens_details"), dict):
            value = usage["output_tokens_details"].get("total_tokens")
        return _int_or_none(value)
    value = getattr(usage, "output_tokens", None)
    return _int_or_none(value)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
