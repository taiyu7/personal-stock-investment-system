from pathlib import Path
import subprocess

import pytest

from personal_stock_investment_system.research import (
    FfmpegFrameCaptureClient,
    ScreenshotCaptureResult,
    ScreenshotRequest,
    SourceReference,
    capture_requested_screenshots,
)
from personal_stock_investment_system.research.screenshots_cli import main as screenshot_cli_main


def test_screenshot_request_rejects_invalid_input():
    with pytest.raises(ValueError):
        ScreenshotRequest(timestamp_seconds=-0.1, reason="圖面")
    with pytest.raises(ValueError):
        ScreenshotRequest(timestamp_seconds=1, reason="  ")


def test_ffmpeg_frame_capture_builds_shell_free_command(tmp_path):
    commands: list[list[str]] = []
    video_path = tmp_path / "local-video.mp4"
    video_path.write_bytes(b"fake local video")
    reference = SourceReference(
        source_id="video-1",
        locator_type="timestamp",
        locator="00:01:23",
        quote="這根 K 突破壓力。",
    )
    request = ScreenshotRequest(
        timestamp_seconds=83.25,
        reason="確認 K 線突破與成交量",
        quote=reference.quote,
        reference=reference,
    )

    def runner(command):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    output_path = tmp_path / "screenshots" / "frame.jpg"
    result = FfmpegFrameCaptureClient(executable="ffmpeg-test", runner=runner).capture(
        video_path,
        request,
        output_path,
    )

    assert result.is_available()
    assert result.artifact is not None
    assert result.artifact.path == output_path.resolve()
    assert result.artifact.timestamp_seconds == 83.25
    assert result.artifact.reason == "確認 K 線突破與成交量"
    assert result.artifact.reference == reference
    assert result.artifact.markdown_reference() == f"![技術分析截圖]({output_path.resolve().as_posix()})"
    assert commands == [
        [
            "ffmpeg-test",
            "-y",
            "-ss",
            "83.250",
            "-i",
            str(video_path.resolve()),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path.resolve()),
        ]
    ]


def test_missing_video_returns_capture_unavailable_without_calling_runner(tmp_path):
    called = False

    def runner(command):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = FfmpegFrameCaptureClient(runner=runner).capture(
        tmp_path / "missing.mp4",
        ScreenshotRequest(timestamp_seconds=10, reason="查看支撐"),
        tmp_path / "frame.jpg",
    )

    assert result.status == "capture_unavailable"
    assert result.artifact is None
    assert "不存在" in result.status_message
    assert not called


def test_batch_capture_keeps_partial_results(tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake")

    class FakeCaptureClient:
        def capture(self, video_path: Path, request: ScreenshotRequest, output_path: Path):
            if request.timestamp_seconds == 20:
                raise RuntimeError("bad frame")
            return ScreenshotCaptureResult(
                status="available",
                request=request,
            )

    results = capture_requested_screenshots(
        video_path,
        (
            ScreenshotRequest(timestamp_seconds=10, reason="第一張"),
            ScreenshotRequest(timestamp_seconds=20, reason="第二張"),
        ),
        tmp_path / "screenshots",
        client=FakeCaptureClient(),
        filename_prefix="research",
    )

    assert [result.status for result in results] == ["available", "capture_unavailable"]
    assert results[1].error == "bad frame"


def test_screenshot_cli_reports_paths_and_statuses(tmp_path, capsys):
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake")

    class FakeCaptureClient:
        def capture(self, video_path: Path, request: ScreenshotRequest, output_path: Path):
            from personal_stock_investment_system.research import ScreenshotArtifact

            return ScreenshotCaptureResult(
                status="available",
                request=request,
                artifact=ScreenshotArtifact(
                    path=output_path.resolve(),
                    timestamp_seconds=request.timestamp_seconds,
                    reason=request.reason,
                    quote=request.quote,
                ),
                status_message="fake capture ready",
            )

    exit_code = screenshot_cli_main(
        [
            str(video_path),
            "--timestamp",
            "10.5",
            "--timestamp",
            "20",
            "--reason",
            "確認圖面",
            "--output-dir",
            str(tmp_path / "screenshots"),
        ],
        client=FakeCaptureClient(),
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert output.count("status=available") == 2
    assert "timestamp_seconds=10.500" in output
    assert "screenshot_path=" in output


def test_screenshot_cli_returns_nonzero_for_missing_video(tmp_path, capsys):
    exit_code = screenshot_cli_main(
        [str(tmp_path / "missing.mp4"), "--timestamp", "1"],
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "status=capture_unavailable" in output
