import subprocess
from pathlib import Path

from personal_stock_investment_system.research import (
    BrowserSessionMediaAcquirer,
    ChromePerformanceLogMediaDiscovery,
    DiscoveredMediaRequest,
    FfmpegAudioPreprocessor,
    MediaArtifact,
    MediaDownloadClient,
    SeleniumBrowserMediaDiscovery,
    SeleniumBrowserSessionConfig,
    YtDlpMediaDownloader,
    extract_media_requests_from_chrome_performance_logs,
    select_stream_manifest,
)


def test_extract_media_requests_from_chrome_performance_logs_reads_m3u8_request():
    entries = [
        {
            "message": (
                '{"message":{"method":"Network.requestWillBeSent",'
                '"params":{"request":{"url":"https://example.test/page"}}}}'
            )
        },
        {
            "message": (
                '{"message":{"method":"Network.requestWillBeSent",'
                '"params":{"request":{"url":"https://cdn.example.test/live/playlist.m3u8?token=abc"}}}}'
            )
        },
        {
            "message": (
                '{"message":{"method":"Network.responseReceived",'
                '"params":{"response":{"url":"https://cdn.example.test/live/playlist.m3u8?token=abc",'
                '"mimeType":"application/vnd.apple.mpegurl"}}}}'
            )
        },
    ]

    requests = extract_media_requests_from_chrome_performance_logs(entries)

    assert requests == (
        DiscoveredMediaRequest(
            url="https://cdn.example.test/live/playlist.m3u8?token=abc",
            method="Network.requestWillBeSent",
        ),
    )


def test_select_stream_manifest_prefers_m3u8():
    requests = (
        DiscoveredMediaRequest("https://cdn.example.test/audio.m4a", content_type="audio/mp4"),
        DiscoveredMediaRequest("https://cdn.example.test/index.m3u8"),
    )

    selected = select_stream_manifest(requests)

    assert selected == requests[1]


class FakeDiscovery:
    def __init__(self, requests: tuple[DiscoveredMediaRequest, ...]) -> None:
        self.requests = requests

    def discover(self, page_url: str) -> tuple[DiscoveredMediaRequest, ...]:
        assert page_url == "https://example.test/member-video"
        return self.requests


class FakeDownloader(MediaDownloadClient):
    def download(self, media_request: DiscoveredMediaRequest, output_dir: Path) -> MediaArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "source.mp4"
        path.write_bytes(b"fake media")
        return MediaArtifact(path=path, source_url=media_request.url, artifact_type="stream")


class FakePreprocessor:
    def to_asr_wav(self, artifact: MediaArtifact, output_path: Path) -> MediaArtifact:
        assert artifact.path.name == "source.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake wav")
        return MediaArtifact(
            path=output_path,
            source_url=artifact.source_url,
            artifact_type="audio_wav",
            mime_type="audio/wav",
            sample_rate_hz=16000,
            channels=1,
        )


def test_browser_session_media_acquirer_downloads_and_preprocesses_for_asr(tmp_path):
    acquirer = BrowserSessionMediaAcquirer(
        discovery=FakeDiscovery((DiscoveredMediaRequest("https://cdn.example.test/index.m3u8"),)),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        raw_output_dir=tmp_path / "raw",
        wav_output_dir=tmp_path / "wav",
    )

    result = acquirer.acquire_for_asr("https://example.test/member-video", output_stem="episode-1")

    assert result.status == "available"
    assert result.artifact is not None
    assert result.artifact.path == (tmp_path / "wav" / "episode-1-16k-mono.wav").resolve()
    assert result.artifact.sample_rate_hz == 16000
    assert result.selected_request == DiscoveredMediaRequest("https://cdn.example.test/index.m3u8")


def test_browser_session_media_acquirer_reports_missing_manifest(tmp_path):
    acquirer = BrowserSessionMediaAcquirer(
        discovery=FakeDiscovery(()),
        downloader=FakeDownloader(),
        preprocessor=FakePreprocessor(),
        raw_output_dir=tmp_path / "raw",
        wav_output_dir=tmp_path / "wav",
    )

    result = acquirer.acquire_for_asr("https://example.test/member-video")

    assert result.status == "media_unavailable"
    assert result.artifact is None
    assert "No m3u8" in result.status_message


def test_chrome_performance_log_discovery_ignores_page_url():
    discovery = ChromePerformanceLogMediaDiscovery(
        (
            {
                "message": (
                    '{"message":{"method":"Network.responseReceived",'
                    '"params":{"response":{"url":"https://cdn.example.test/index.m3u8",'
                    '"headers":{"Content-Type":"application/vnd.apple.mpegurl"}}}}}'
                )
            },
        )
    )

    assert discovery.discover("https://example.test") == (
        DiscoveredMediaRequest(
            "https://cdn.example.test/index.m3u8",
            content_type="application/vnd.apple.mpegurl",
            method="Network.responseReceived",
        ),
    )


class FakeBrowserDriver:
    def __init__(self) -> None:
        self.opened_url = ""
        self.timeout_seconds = 0
        self.executed_scripts: list[str] = []
        self.quit_called = False

    def set_page_load_timeout(self, seconds: int) -> None:
        self.timeout_seconds = seconds

    def get(self, url: str) -> None:
        self.opened_url = url

    def execute_script(self, script: str) -> object:
        self.executed_scripts.append(script)
        return None

    def get_log(self, log_type: str) -> list[object]:
        assert log_type == "performance"
        return [
            {
                "message": (
                    '{"message":{"method":"Network.requestWillBeSent",'
                    '"params":{"request":{"url":"https://cdn.example.test/stream.m3u8"}}}}'
                )
            }
        ]

    def quit(self) -> None:
        self.quit_called = True


def test_selenium_browser_media_discovery_uses_existing_driver_boundary():
    driver = FakeBrowserDriver()
    sleeps: list[float] = []
    discovery = SeleniumBrowserMediaDiscovery(
        config=SeleniumBrowserSessionConfig(page_load_timeout_seconds=42, settle_seconds=0.5, playback_wait_seconds=1.5),
        driver_factory=lambda config: driver,
        sleeper=sleeps.append,
    )

    requests = discovery.discover("https://example.test/member-video")

    assert requests == (
        DiscoveredMediaRequest("https://cdn.example.test/stream.m3u8", method="Network.requestWillBeSent"),
    )
    assert driver.timeout_seconds == 42
    assert driver.opened_url == "https://example.test/member-video"
    assert driver.executed_scripts
    assert driver.quit_called is True
    assert sleeps == [0.5, 1.5]


def test_yt_dlp_downloader_builds_shell_free_command(tmp_path):
    commands: list[list[str]] = []

    def runner(command):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout=str(tmp_path / "raw" / "download.mp4"), stderr="")

    downloader = YtDlpMediaDownloader(executable="yt-dlp-test", runner=runner)

    artifact = downloader.download(DiscoveredMediaRequest("https://cdn.example.test/index.m3u8"), tmp_path / "raw")

    assert artifact.path == (tmp_path / "raw" / "download.mp4").resolve()
    assert commands == [
        [
            "yt-dlp-test",
            "--no-progress",
            "--print",
            "after_move:filepath",
            "-o",
            str((tmp_path / "raw").resolve() / "%(title).200B.%(ext)s"),
            "https://cdn.example.test/index.m3u8",
        ]
    ]


def test_ffmpeg_audio_preprocessor_builds_16k_mono_wav_command(tmp_path):
    commands: list[list[str]] = []
    source = tmp_path / "source.mp4"
    source.write_bytes(b"fake media")

    def runner(command):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    preprocessor = FfmpegAudioPreprocessor(executable="ffmpeg-test", runner=runner)
    output_path = tmp_path / "processed" / "sample.wav"

    artifact = preprocessor.to_asr_wav(MediaArtifact(path=source), output_path)

    assert artifact.path == output_path.resolve()
    assert artifact.sample_rate_hz == 16000
    assert artifact.channels == 1
    assert commands == [
        [
            "ffmpeg-test",
            "-y",
            "-i",
            str(source.resolve()),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path.resolve()),
        ]
    ]
