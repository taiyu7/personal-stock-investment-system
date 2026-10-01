"""CLI for capturing timestamped screenshots from a legal local video artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from personal_stock_investment_system.research.screenshots import (
    FfmpegFrameCaptureClient,
    FrameCaptureClient,
    ScreenshotRequest,
    capture_requested_screenshots,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture one or more timestamped screenshots from a local video artifact.",
    )
    parser.add_argument("video_path", type=Path, help="Path to a legal local video artifact.")
    parser.add_argument(
        "--timestamp",
        dest="timestamps",
        type=float,
        action="append",
        required=True,
        help="Timestamp in seconds. Repeat this option to capture multiple frames.",
    )
    parser.add_argument("--reason", default="人工指定截圖", help="Reason associated with every screenshot request.")
    parser.add_argument("--quote", default="", help="Optional transcript quote associated with the screenshots.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/screenshots"))
    parser.add_argument("--filename-prefix", default="frame")
    parser.add_argument("--ffmpeg-executable", default="ffmpeg")
    return parser


def main(argv: Sequence[str] | None = None, *, client: FrameCaptureClient | None = None) -> int:
    args = build_parser().parse_args(argv)
    requests = tuple(
        ScreenshotRequest(
            timestamp_seconds=timestamp,
            reason=args.reason,
            quote=args.quote,
        )
        for timestamp in args.timestamps
    )
    results = capture_requested_screenshots(
        args.video_path,
        requests,
        args.output_dir,
        client=client or FfmpegFrameCaptureClient(executable=args.ffmpeg_executable),
        filename_prefix=args.filename_prefix,
    )
    for result in results:
        print(f"timestamp_seconds={result.request.timestamp_seconds:.3f}")
        print(f"status={result.status}")
        if result.artifact is not None:
            print(f"screenshot_path={result.artifact.path}")
        if result.status_message:
            print(f"status_message={result.status_message}")
        if result.error:
            print(f"error={result.error}")
    return 0 if all(result.is_available() for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
