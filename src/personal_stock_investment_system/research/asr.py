"""Local speech-to-text adapters for research media sources."""

from __future__ import annotations

import json
import subprocess
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
