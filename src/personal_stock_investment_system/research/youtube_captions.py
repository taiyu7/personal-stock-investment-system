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
    converted_to_traditional: bool = False


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
        common = ["yt-dlp", "--ignore-config", "--no-playlist", "--skip-download"]
        if cookies_from_browser:
            common.extend(("--cookies-from-browser", cookies_from_browser))
        if remote_components:
            common.extend(("--remote-components", remote_components))
        try:
            metadata = runner(
                [*common, "--dump-single-json", video_url],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
            return CaptionFetchResult(error=f"字幕取得失敗：{type(error).__name__}")
        if metadata.returncode:
            return CaptionFetchResult(error=_caption_failure_reason(metadata.stderr or metadata.stdout))
        try:
            languages = _select_caption_languages(json.loads(metadata.stdout))
        except (TypeError, ValueError):
            return CaptionFetchResult(error="YouTube 字幕清單無法解析。")
        if not languages:
            return CaptionFetchResult(error="找不到可讀取的 zh-TW 或簡體中文字幕。")
        failures = []
        for language in languages:
            command = [
                *common, "--write-subs", "--write-auto-subs", "--sub-langs", language,
                "--sub-format", "vtt", "--output", str(Path(directory) / "caption.%(ext)s"), video_url,
            ]
            try:
                completed = runner(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
                failures.append(f"{language} 字幕取得失敗：{type(error).__name__}")
                continue
            for path in Path(directory).glob(f"caption.{language}.vtt"):
                segments = parse_webvtt(path.read_text(encoding="utf-8-sig"))
                if segments:
                    return _caption_result(segments, language)
            reason = _caption_failure_reason(completed.stderr or completed.stdout) if completed.returncode else "字幕沒有可讀內容。"
            failures.append(f"{language}：{reason}")
        return CaptionFetchResult(error="；".join(failures), track_found=True)


_CAPTION_LANGUAGES = ("zh-TW", "zh-Hans", "zh-CN")


def _select_caption_languages(info: object) -> tuple[str, ...]:
    if not isinstance(info, dict):
        return ()
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    if not isinstance(manual, dict) or not isinstance(automatic, dict):
        return ()
    return tuple(language for language in _CAPTION_LANGUAGES if manual.get(language) or automatic.get(language))


def _caption_result(segments: tuple[AsrTranscriptSegment, ...], language: str) -> CaptionFetchResult:
    if language == "zh-TW":
        return CaptionFetchResult(segments, language, track_found=True)
    try:
        from opencc import OpenCC

        converter = OpenCC("s2tw.json")
        converted = tuple(
            AsrTranscriptSegment(converter.convert(segment.text), segment.start_seconds, segment.end_seconds)
            for segment in segments
        )
    except (ImportError, RuntimeError) as error:
        return CaptionFetchResult(error=f"{language} 字幕已取得，但簡轉繁失敗（{type(error).__name__}）。", track_found=True)
    return CaptionFetchResult(converted, language, track_found=True, converted_to_traditional=True)


def _caption_failure_reason(output: str) -> str:
    detail = output.casefold()
    if "failed to resolve" in detail or "name resolution" in detail:
        return "字幕檢查無法連線到 YouTube（DNS 解析失敗）。"
    if "sign in" in detail or "login" in detail or "cookies" in detail:
        return "字幕檢查需要登入或有效的瀏覽器登入狀態。"
    if "403" in detail or "forbidden" in detail:
        return "YouTube 拒絕下載字幕（403）。"
    if "429" in detail or "too many requests" in detail:
        return "YouTube 暫時限制字幕請求（429）。"
    return "YouTube 字幕下載失敗；請檢查容器中的 yt-dlp 與網路連線。"


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
        chinese_tracks = [
            track for track in tracks
            if isinstance(track, dict) and track.get("languageCode") in _CAPTION_LANGUAGES
        ] if isinstance(tracks, list) else []
        if not chinese_tracks:
            return CaptionFetchResult(error="瀏覽器頁面未提供 zh-TW 或簡體中文字幕軌。")
        for track in sorted(chinese_tracks, key=lambda value: (
            _CAPTION_LANGUAGES.index(value["languageCode"]), value.get("kind") == "asr",
        )):
            if not track.get("baseUrl"):
                continue
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
                return _caption_result(segments, str(track["languageCode"]))
        return CaptionFetchResult(error="瀏覽器找到了中文字幕軌，但字幕內容無法讀取。", track_found=True)
    except Exception as error:  # noqa: BLE001 - retain yt-dlp diagnostic and fall back to ASR.
        return CaptionFetchResult(error=f"瀏覽器字幕讀取失敗（{type(error).__name__}）。")
    finally:
        driver.quit()


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
        "converted_to_traditional": result.converted_to_traditional,
        "segments": [
            {"start": segment.start_seconds, "end": segment.end_seconds, "text": segment.text}
            for segment in result.segments
        ],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return AsrTranscriptionResult(
        segments=result.segments, transcript_path=output_path,
        status_message=(
            f"已使用 YouTube 現成字幕（{result.language}→繁體中文），未執行音訊轉錄。"
            if result.converted_to_traditional else
            f"已使用 YouTube 現成字幕（{result.language}），未執行音訊轉錄。"
        ),
    )
