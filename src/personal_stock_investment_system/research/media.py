"""Media acquisition adapters for browser-session research sources."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Protocol, Sequence
from urllib.parse import urlparse

from personal_stock_investment_system.research.sources import SourceImportStatus

MediaArtifactType = Literal["stream", "audio", "audio_wav", "video", "unknown"]


@dataclass(frozen=True)
class DiscoveredMediaRequest:
    url: str
    source: str = "browser_performance_log"
    content_type: str = ""
    method: str = ""

    def is_stream_manifest(self) -> bool:
        return is_stream_manifest_url(self.url) or "mpegurl" in self.content_type.lower()


@dataclass(frozen=True)
class MediaArtifact:
    path: Path
    source_url: str = ""
    artifact_type: MediaArtifactType = "unknown"
    mime_type: str = ""
    sample_rate_hz: int | None = None
    channels: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class MediaAcquisitionResult:
    status: SourceImportStatus
    source_identifier: str
    artifact: MediaArtifact | None = None
    selected_request: DiscoveredMediaRequest | None = None
    discovered_requests: tuple[DiscoveredMediaRequest, ...] = ()
    status_message: str = ""
    error: str = ""

    def is_available(self) -> bool:
        return self.status == "available" and self.artifact is not None


class MediaAcquisitionError(RuntimeError):
    def __init__(self, status: SourceImportStatus, status_message: str, error: str = "") -> None:
        super().__init__(status_message)
        self.status = status
        self.status_message = status_message
        self.error = error


class BrowserMediaDiscoveryClient(Protocol):
    def discover(self, page_url: str) -> tuple[DiscoveredMediaRequest, ...]:
        """Return media requests observed while a browser session opens the page."""


class BrowserPerformanceLogDriver(Protocol):
    def get(self, url: str) -> None:
        """Open a page URL."""

    def get_log(self, log_type: str) -> list[object]:
        """Return browser logs for the requested log type."""

    def execute_script(self, script: str) -> object:
        """Execute JavaScript in the current page."""

    def set_page_load_timeout(self, seconds: int) -> None:
        """Set page load timeout."""

    def quit(self) -> None:
        """Close the browser session."""


class MediaDownloadClient(Protocol):
    def download(self, media_request: DiscoveredMediaRequest, output_dir: Path) -> MediaArtifact:
        """Download a discovered media request into output_dir."""


class AudioPreprocessor(Protocol):
    def to_asr_wav(self, artifact: MediaArtifact, output_path: Path) -> MediaArtifact:
        """Convert a media artifact into the 16 kHz mono PCM WAV expected by ASR."""


@dataclass(frozen=True)
class BrowserSessionMediaAcquirer:
    discovery: BrowserMediaDiscoveryClient
    downloader: MediaDownloadClient
    preprocessor: AudioPreprocessor
    raw_output_dir: Path
    wav_output_dir: Path

    def acquire_for_asr(self, page_url: str, *, output_stem: str = "") -> MediaAcquisitionResult:
        discovered_requests = self.discovery.discover(page_url)
        selected_request = select_stream_manifest(discovered_requests)
        if selected_request is None:
            return MediaAcquisitionResult(
                status="media_unavailable",
                source_identifier=page_url,
                discovered_requests=discovered_requests,
                status_message="No m3u8 or stream manifest was observed from the browser session.",
            )

        try:
            raw_artifact = self.downloader.download(selected_request, self.raw_output_dir)
            wav_stem = output_stem or raw_artifact.path.stem or safe_filename(urlparse(page_url).path) or "browser-media"
            wav_path = self.wav_output_dir / f"{safe_filename(wav_stem)}-16k-mono.wav"
            wav_artifact = self.preprocessor.to_asr_wav(raw_artifact, wav_path)
        except MediaAcquisitionError as error:
            return MediaAcquisitionResult(
                status=error.status,
                source_identifier=page_url,
                selected_request=selected_request,
                discovered_requests=discovered_requests,
                status_message=error.status_message,
                error=error.error,
            )

        return MediaAcquisitionResult(
            status="available",
            source_identifier=page_url,
            artifact=wav_artifact,
            selected_request=selected_request,
            discovered_requests=discovered_requests,
            status_message="Media was downloaded and converted to 16 kHz mono WAV for ASR.",
        )


@dataclass(frozen=True)
class ChromePerformanceLogMediaDiscovery:
    log_entries: tuple[object, ...]

    def discover(self, page_url: str) -> tuple[DiscoveredMediaRequest, ...]:
        del page_url
        return extract_media_requests_from_chrome_performance_logs(self.log_entries)


@dataclass(frozen=True)
class SeleniumBrowserSessionConfig:
    chrome_user_data_dir: Path | None = None
    chrome_profile_directory: str = ""
    chrome_binary_path: Path | None = None
    headless: bool = False
    page_load_timeout_seconds: int = 60
    settle_seconds: float = 3.0
    playback_wait_seconds: float = 10.0
    try_start_playback: bool = True
    quit_driver: bool = True


@dataclass(frozen=True)
class SeleniumBrowserMediaDiscovery:
    config: SeleniumBrowserSessionConfig = SeleniumBrowserSessionConfig()
    driver_factory: Callable[[SeleniumBrowserSessionConfig], BrowserPerformanceLogDriver] | None = None
    sleeper: Callable[[float], None] = time.sleep

    def discover(self, page_url: str) -> tuple[DiscoveredMediaRequest, ...]:
        driver = (self.driver_factory or create_selenium_chrome_driver)(self.config)
        try:
            driver.set_page_load_timeout(self.config.page_load_timeout_seconds)
            driver.get(page_url)
            self.sleeper(self.config.settle_seconds)
            if self.config.try_start_playback:
                try_start_browser_media_playback(driver)
                self.sleeper(self.config.playback_wait_seconds)
            return extract_media_requests_from_chrome_performance_logs(driver.get_log("performance"))
        finally:
            if self.config.quit_driver:
                driver.quit()


@dataclass(frozen=True)
class YtDlpMediaDownloader:
    executable: str = "yt-dlp"
    output_template: str = "%(title).200B.%(ext)s"
    extra_args: tuple[str, ...] = ()
    runner: CommandRunner | None = None

    def download(self, media_request: DiscoveredMediaRequest, output_dir: Path) -> MediaArtifact:
        resolved_output_dir = output_dir.expanduser().resolve()
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-o",
            str(resolved_output_dir / self.output_template),
            *self.extra_args,
            media_request.url,
        ]
        completed = run_checked_command(command, self.runner, "yt-dlp", "media_unavailable")
        output_path = last_stdout_path(completed.stdout, resolved_output_dir)
        return MediaArtifact(
            path=output_path,
            source_url=media_request.url,
            artifact_type="stream",
            mime_type=media_request.content_type,
            notes="downloaded_by=yt-dlp",
        )


@dataclass(frozen=True)
class FfmpegAudioPreprocessor:
    executable: str = "ffmpeg"
    sample_rate_hz: int = 16000
    channels: int = 1
    runner: CommandRunner | None = None

    def to_asr_wav(self, artifact: MediaArtifact, output_path: Path) -> MediaArtifact:
        resolved_output_path = output_path.expanduser().resolve()
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "-y",
            "-i",
            str(artifact.path.expanduser().resolve()),
            "-vn",
            "-ac",
            str(self.channels),
            "-ar",
            str(self.sample_rate_hz),
            "-c:a",
            "pcm_s16le",
            str(resolved_output_path),
        ]
        run_checked_command(command, self.runner, "ffmpeg", "capture_unavailable")
        return MediaArtifact(
            path=resolved_output_path,
            source_url=artifact.source_url,
            artifact_type="audio_wav",
            mime_type="audio/wav",
            sample_rate_hz=self.sample_rate_hz,
            channels=self.channels,
            notes="asr_ready=true",
        )


class CommandRunner(Protocol):
    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run a shell-free command and return the completed process."""


def extract_media_requests_from_chrome_performance_logs(entries: Iterable[object]) -> tuple[DiscoveredMediaRequest, ...]:
    requests: list[DiscoveredMediaRequest] = []
    seen: set[str] = set()
    for entry in entries:
        message = decode_chrome_performance_log_entry(entry)
        if not message:
            continue
        method = str(message.get("method", ""))
        params = message.get("params", {})
        if not isinstance(params, dict):
            continue

        url, content_type = _extract_url_and_content_type(params)
        if not url or not _looks_like_media_request(url, content_type):
            continue
        if url in seen:
            continue
        seen.add(url)
        requests.append(
            DiscoveredMediaRequest(
                url=url,
                content_type=content_type,
                method=method,
            )
        )
    return tuple(requests)


def decode_chrome_performance_log_entry(entry: object) -> dict[str, object]:
    if isinstance(entry, str):
        payload: object = _loads_json(entry)
    elif isinstance(entry, dict):
        payload = entry
    else:
        return {}

    if not isinstance(payload, dict):
        return {}
    raw_message = payload.get("message", payload)
    if isinstance(raw_message, str):
        raw_message = _loads_json(raw_message)
    if not isinstance(raw_message, dict):
        return {}
    message = raw_message.get("message", raw_message)
    return message if isinstance(message, dict) else {}


def select_stream_manifest(requests: Iterable[DiscoveredMediaRequest]) -> DiscoveredMediaRequest | None:
    for media_request in requests:
        if media_request.is_stream_manifest():
            return media_request
    return None


def create_selenium_chrome_driver(config: SeleniumBrowserSessionConfig) -> BrowserPerformanceLogDriver:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as error:
        raise MediaAcquisitionError(
            "unsupported_source",
            "selenium is required for browser-session media discovery.",
            str(error),
        ) from error

    options = Options()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    if config.headless:
        options.add_argument("--headless=new")
    if config.chrome_user_data_dir is not None:
        options.add_argument(f"--user-data-dir={config.chrome_user_data_dir.expanduser().resolve()}")
    if config.chrome_profile_directory:
        options.add_argument(f"--profile-directory={config.chrome_profile_directory}")
    if config.chrome_binary_path is not None:
        options.binary_location = str(config.chrome_binary_path.expanduser().resolve())
    return webdriver.Chrome(options=options)


def try_start_browser_media_playback(driver: BrowserPerformanceLogDriver) -> None:
    driver.execute_script(
        """
        for (const element of document.querySelectorAll('video,audio')) {
          try {
            element.muted = true;
            const promise = element.play();
            if (promise && typeof promise.catch === 'function') {
              promise.catch(() => {});
            }
          } catch (error) {}
        }
        """
    )


def is_stream_manifest_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".m3u8") or ".m3u8" in parsed.query.lower()


def safe_filename(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized[:120] or "media"


def run_checked_command(
    command: Sequence[str],
    runner: CommandRunner | None,
    executable_name: str,
    failure_status: SourceImportStatus,
) -> subprocess.CompletedProcess[str]:
    try:
        if runner is None:
            return subprocess.run(list(command), check=True, capture_output=True, text=True)
        return runner(command)
    except FileNotFoundError as error:
        raise MediaAcquisitionError(
            "unsupported_source",
            f"{executable_name} executable was not found.",
            str(error),
        ) from error
    except subprocess.CalledProcessError as error:
        raise MediaAcquisitionError(
            failure_status,
            f"{executable_name} failed while processing media.",
            (error.stderr or error.stdout or str(error)).strip(),
        ) from error


def last_stdout_path(stdout: str, output_dir: Path) -> Path:
    for line in reversed([line.strip() for line in stdout.splitlines() if line.strip()]):
        candidate = Path(line).expanduser()
        if not candidate.is_absolute():
            candidate = output_dir / candidate
        return candidate.resolve()
    return output_dir.resolve()


def _loads_json(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _extract_url_and_content_type(params: dict[str, object]) -> tuple[str, str]:
    request = params.get("request")
    if isinstance(request, dict):
        url = str(request.get("url", ""))
        content_type = _headers_content_type(request.get("headers"))
        if url:
            return url, content_type

    response = params.get("response")
    if isinstance(response, dict):
        url = str(response.get("url", ""))
        content_type = _headers_content_type(response.get("headers")) or str(response.get("mimeType", ""))
        if url:
            return url, content_type

    return "", ""


def _headers_content_type(headers: object) -> str:
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if str(key).lower() == "content-type":
            return str(value)
    return ""


def _looks_like_media_request(url: str, content_type: str) -> bool:
    lowered_type = content_type.lower()
    lowered_url = url.lower()
    return (
        is_stream_manifest_url(url)
        or "mpegurl" in lowered_type
        or "audio/" in lowered_type
        or "video/" in lowered_type
        or any(token in lowered_url for token in (".mp4", ".m4a", ".mp3", ".wav", ".aac"))
    )
