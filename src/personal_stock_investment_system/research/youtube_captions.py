"""Retrieve existing YouTube captions before falling back to speech recognition."""

from __future__ import annotations

import html
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from personal_stock_investment_system.research.asr import AsrTranscriptSegment, AsrTranscriptionResult
from personal_stock_investment_system.research.youtube import parse_youtube_video_id


@dataclass(frozen=True)
class CaptionFetchResult:
    segments: tuple[AsrTranscriptSegment, ...] = ()
    language: str = ""
    error: str = ""
    track_found: bool = False


CaptionRunner = Callable[..., subprocess.CompletedProcess[str]]


def fetch_youtube_captions(
    video_url: str,
    *,
    cookies_from_browser: str = "",
    remote_components: str = "",
    work_dir: Path = Path("data/local"),
    runner: CaptionRunner = subprocess.run,
) -> CaptionFetchResult:
    """Fetch creator captions or automatic captions without downloading video media."""
    try:
        parse_youtube_video_id(video_url)
    except ValueError:
        return CaptionFetchResult(error="不是 YouTube 影片網址。")
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="psis-captions-", dir=work_dir) as directory:
        command = [
            "yt-dlp", "--ignore-config", "--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs",
            "--sub-langs", "zh-TW,zh-Hant,zh-Hans,zh,en", "--sub-format", "vtt",
            "--output", str(Path(directory) / "caption.%(ext)s"),
        ]
        if cookies_from_browser:
            command.extend(("--cookies-from-browser", cookies_from_browser))
        if remote_components:
            command.extend(("--remote-components", remote_components))
        command.append(video_url)
        try:
            completed = runner(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
            return CaptionFetchResult(error=f"字幕取得失敗：{type(error).__name__}")
        if completed.returncode:
            return CaptionFetchResult(error=_caption_failure_reason(completed.stderr or completed.stdout))
        candidates = sorted(Path(directory).glob("caption.*.vtt"), key=_caption_priority)
        for path in candidates:
            segments = parse_webvtt(path.read_text(encoding="utf-8-sig"))
            if segments:
                return CaptionFetchResult(segments, path.name.removeprefix("caption.").removesuffix(".vtt"), track_found=True)
        return CaptionFetchResult(error="找不到可讀取的中文或英文 YouTube 字幕，將使用音訊轉錄。")


def _caption_failure_reason(output: str) -> str:
    detail = output.casefold()
    if "failed to resolve" in detail or "name resolution" in detail:
        return "字幕檢查無法連線到 YouTube（DNS 解析失敗），將使用音訊轉錄。"
    if "sign in" in detail or "login" in detail or "cookies" in detail:
        return "字幕檢查需要登入或有效的瀏覽器登入狀態，將使用音訊轉錄。"
    if "403" in detail or "forbidden" in detail:
        return "YouTube 拒絕下載字幕（403），將使用音訊轉錄。"
    if "429" in detail or "too many requests" in detail:
        return "YouTube 暫時限制字幕請求（429），將使用音訊轉錄。"
    return "YouTube 字幕下載失敗；請檢查容器中的 yt-dlp 與網路連線。將使用音訊轉錄。"


def _caption_priority(path: Path) -> int:
    language = path.name.removeprefix("caption.").removesuffix(".vtt")
    return {"zh-TW": 0, "zh-Hant": 1, "zh-Hans": 2, "zh": 3, "en": 4}.get(language, 5)


def fetch_youtube_captions_in_browser(video_url: str, config, *, driver_factory=None) -> CaptionFetchResult:
    """Use the same browser profile as media discovery when yt-dlp cannot read captions."""
    from personal_stock_investment_system.research.media import create_selenium_chrome_driver

    try:
        parse_youtube_video_id(video_url)
        driver = (driver_factory or create_selenium_chrome_driver)(config)
    except Exception as error:  # noqa: BLE001 - browser captions are a best-effort fallback.
        return CaptionFetchResult(error=f"瀏覽器字幕檢查無法啟動（{type(error).__name__}）。")
    try:
        driver.set_page_load_timeout(30)
        driver.get(video_url)
        tracks = driver.execute_script(
            """
            const response = window.ytInitialPlayerResponse ||
              document.querySelector('ytd-player')?.player_?.getPlayerResponse?.();
            return response?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
            """
        )
        if not isinstance(tracks, list) or not tracks:
            return CaptionFetchResult(error="瀏覽器頁面未提供可讀取的字幕軌。")
        tracks = sorted(
            (track for track in tracks if isinstance(track, dict) and track.get("baseUrl")),
            key=lambda track: (track.get("kind") == "asr", _language_priority(str(track.get("languageCode", "")))),
        )
        for track in tracks:
            content = driver.execute_async_script(
                """
                const base = arguments[0], done = arguments[arguments.length - 1];
                const url = new URL(base); url.searchParams.set('fmt', 'vtt');
                fetch(url.toString(), {credentials: 'include'})
                  .then(response => response.ok ? response.text() : '')
                  .then(done).catch(() => done(''));
                """,
                track["baseUrl"],
            )
            segments = parse_webvtt(content) if isinstance(content, str) else ()
            if segments:
                return CaptionFetchResult(segments, str(track.get("languageCode", "")), track_found=True)
        return CaptionFetchResult(error="瀏覽器找到了字幕軌，但字幕內容無法讀取。", track_found=True)
    except Exception as error:  # noqa: BLE001 - retain yt-dlp diagnostic and fall back to ASR.
        return CaptionFetchResult(error=f"瀏覽器字幕讀取失敗（{type(error).__name__}）。")
    finally:
        driver.quit()


def _language_priority(language: str) -> int:
    return {"zh-TW": 0, "zh-Hant": 1, "zh-Hans": 2, "zh": 3, "en": 4}.get(language, 5)


_TIMING = re.compile(r"^(\d{2}:)?\d{2}:\d{2}\.\d{3}\s+-->\s+(\d{2}:)?\d{2}:\d{2}\.\d{3}")
_TAG = re.compile(r"<[^>]+>")


def parse_webvtt(content: str) -> tuple[AsrTranscriptSegment, ...]:
    """Keep timestamped caption cues and remove YouTube rolling-caption duplicates."""
    segments: list[AsrTranscriptSegment] = []
    for block in re.split(r"\r?\n\s*\r?\n", content):
        lines = block.splitlines()
        timing_index = next((i for i, line in enumerate(lines) if _TIMING.match(line.strip())), None)
        if timing_index is None:
            continue
        start, end = lines[timing_index].split("-->", 1)
        text = html.unescape(_TAG.sub("", " ".join(lines[timing_index + 1:]))).strip()
        text = " ".join(text.split())
        if not text or (segments and segments[-1].text == text):
            continue
        segments.append(AsrTranscriptSegment(text, _seconds(start), _seconds(end.strip().split()[0])))
    return tuple(segments)


def _seconds(value: str) -> float:
    parts = value.strip().split(":")
    return sum(float(part) * 60 ** index for index, part in enumerate(reversed(parts)))


def save_caption_transcript(result: CaptionFetchResult, output_path: Path) -> AsrTranscriptionResult:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "youtube_captions", "language": result.language,
        "segments": [
            {"start": segment.start_seconds, "end": segment.end_seconds, "text": segment.text}
            for segment in result.segments
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return AsrTranscriptionResult(
        segments=result.segments, transcript_path=output_path,
        status_message=f"已使用 YouTube 現成字幕（{result.language}），未執行音訊轉錄。",
    )
