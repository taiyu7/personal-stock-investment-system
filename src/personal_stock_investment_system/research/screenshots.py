"""Timestamp-based screenshot capture for local video research artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from personal_stock_investment_system.research.media import CommandRunner, MediaAcquisitionError, run_checked_command
from personal_stock_investment_system.research.sources import SourceImportStatus, SourceReference


@dataclass(frozen=True)
class ScreenshotRequest:
    timestamp_seconds: float
    reason: str
    quote: str = ""
    reference: SourceReference | None = None

    def __post_init__(self) -> None:
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds must be greater than or equal to zero.")
        if not self.reason.strip():
            raise ValueError("reason is required for a screenshot request.")


@dataclass(frozen=True)
class ScreenshotArtifact:
    path: Path
    timestamp_seconds: float
    reason: str
    quote: str = ""
    reference: SourceReference | None = None

    def markdown_reference(self, alt_text: str = "技術分析截圖") -> str:
        escaped_alt = alt_text.replace("[", "\\[").replace("]", "\\]")
        return f"![{escaped_alt}]({self.path.as_posix()})"


@dataclass(frozen=True)
class ScreenshotCaptureResult:
    status: SourceImportStatus
    request: ScreenshotRequest
    artifact: ScreenshotArtifact | None = None
    status_message: str = ""
    error: str = ""

    def is_available(self) -> bool:
        return self.status == "available" and self.artifact is not None


class FrameCaptureClient(Protocol):
    def capture(
        self,
        video_path: Path,
        request: ScreenshotRequest,
        output_path: Path,
    ) -> ScreenshotCaptureResult:
        """Capture one frame from a legal local video artifact."""


@dataclass(frozen=True)
class FfmpegFrameCaptureClient:
    executable: str = "ffmpeg"
    quality: int = 2
    runner: CommandRunner | None = None

    def capture(
        self,
        video_path: Path,
        request: ScreenshotRequest,
        output_path: Path,
    ) -> ScreenshotCaptureResult:
        resolved_video = video_path.expanduser().resolve()
        resolved_output = output_path.expanduser().resolve()
        if not resolved_video.is_file():
            return _unavailable(request, "本機影片 artifact 不存在或不是檔案。", str(resolved_video))

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "-y",
            "-ss",
            format_timestamp_seconds(request.timestamp_seconds),
            "-i",
            str(resolved_video),
            "-frames:v",
            "1",
            "-q:v",
            str(self.quality),
            str(resolved_output),
        ]
        try:
            run_checked_command(command, self.runner, "ffmpeg", "capture_unavailable")
        except MediaAcquisitionError as error:
            return _unavailable(request, error.status_message, error.error)

        return ScreenshotCaptureResult(
            status="available",
            request=request,
            artifact=ScreenshotArtifact(
                path=resolved_output,
                timestamp_seconds=request.timestamp_seconds,
                reason=request.reason,
                quote=request.quote,
                reference=request.reference,
            ),
            status_message="已從本機影片 artifact 擷取指定時間戳畫面。",
        )


def capture_requested_screenshots(
    video_path: Path,
    requests: Sequence[ScreenshotRequest],
    output_dir: Path,
    *,
    client: FrameCaptureClient | None = None,
    filename_prefix: str = "frame",
) -> tuple[ScreenshotCaptureResult, ...]:
    """Capture every request independently so one bad timestamp does not abort the batch."""

    resolved_output_dir = output_dir.expanduser().resolve()
    resolved_client = client or FfmpegFrameCaptureClient()
    results: list[ScreenshotCaptureResult] = []
    for index, request in enumerate(requests, start=1):
        milliseconds = round(request.timestamp_seconds * 1000)
        output_path = resolved_output_dir / f"{filename_prefix}-{index:03d}-{milliseconds:010d}ms.jpg"
        try:
            result = resolved_client.capture(video_path, request, output_path)
        except Exception as error:  # noqa: BLE001 - adapter boundary returns an explicit partial failure.
            result = _unavailable(request, "截圖 adapter 執行失敗。", str(error))
        results.append(result)
    return tuple(results)


def format_timestamp_seconds(value: float) -> str:
    """Return a locale-independent ffmpeg timestamp with millisecond precision."""

    return f"{value:.3f}"


def _unavailable(request: ScreenshotRequest, message: str, error: str = "") -> ScreenshotCaptureResult:
    return ScreenshotCaptureResult(
        status="capture_unavailable",
        request=request,
        status_message=message,
        error=error,
    )
