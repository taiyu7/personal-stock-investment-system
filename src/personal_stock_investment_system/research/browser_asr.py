"""End-to-end browser-session media acquisition entrypoint for ASR."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path

from personal_stock_investment_system.research.asr import (
    AsrTranscriptionResult,
    OpenVINOAsrConfig,
    OpenVINOAsrTranscriber,
    SpeechToTextClient,
    build_local_audio_research_source,
)
from personal_stock_investment_system.research.media import (
    AudioPreprocessor,
    BrowserMediaDiscoveryClient,
    BrowserSessionMediaAcquirer,
    FfmpegAudioPreprocessor,
    MediaAcquisitionResult,
    MediaDownloadClient,
    SeleniumBrowserMediaDiscovery,
    SeleniumBrowserSessionConfig,
    YtDlpMediaDownloader,
    safe_filename,
)
from personal_stock_investment_system.research.sources import ResearchSourceImportResult, SourceImportStatus


@dataclass(frozen=True)
class BrowserSessionAsrInput:
    page_url: str
    output_stem: str = ""
    title: str = ""
    raw_output_dir: Path = Path("data/raw/browser-media")
    wav_output_dir: Path = Path("data/processed/asr-audio")
    transcript_output_dir: Path = Path("data/processed/asr-transcripts/openvino")
    chrome_user_data_dir: Path | None = None
    chrome_profile_directory: str = ""
    chrome_binary_path: Path | None = None
    chromedriver_path: Path | None = None
    headless: bool = False
    settle_seconds: float = 3.0
    playback_wait_seconds: float = 10.0
    openvino_model_dir: Path | None = None
    openvino_device: str = "GPU"
    language: str = "zh"
    task: str = "transcribe"
    ytdlp_cookies_from_browser: str = ""
    ytdlp_remote_components: str = ""
    ytdlp_download_page_url: bool = False


@dataclass(frozen=True)
class BrowserSessionAsrResult:
    media_result: MediaAcquisitionResult
    transcription: AsrTranscriptionResult | None = None
    source_import_result: ResearchSourceImportResult | None = None

    @property
    def status(self) -> SourceImportStatus:
        if self.source_import_result is not None:
            return self.source_import_result.status
        return self.media_result.status

    def is_available(self) -> bool:
        if self.source_import_result is not None:
            return self.source_import_result.is_available()
        return self.media_result.is_available()


def run_browser_session_asr_pipeline(
    source_input: BrowserSessionAsrInput,
    *,
    discovery: BrowserMediaDiscoveryClient | None = None,
    downloader: MediaDownloadClient | None = None,
    preprocessor: AudioPreprocessor | None = None,
    speech_to_text: SpeechToTextClient | None = None,
) -> BrowserSessionAsrResult:
    output_stem = source_input.output_stem or safe_filename(source_input.title or source_input.page_url)
    acquirer = BrowserSessionMediaAcquirer(
        discovery=discovery or _default_browser_discovery(source_input),
        downloader=downloader or _default_downloader(source_input),
        preprocessor=preprocessor or FfmpegAudioPreprocessor(),
        raw_output_dir=source_input.raw_output_dir,
        wav_output_dir=source_input.wav_output_dir,
    )
    media_result = acquirer.acquire_for_asr(source_input.page_url, output_stem=output_stem)
    if not media_result.is_available() or media_result.artifact is None:
        return BrowserSessionAsrResult(media_result=media_result)

    transcriber = speech_to_text or _default_transcriber(source_input)
    if transcriber is None:
        return BrowserSessionAsrResult(media_result=media_result)

    transcription = transcriber.transcribe(media_result.artifact.path)
    source_import_result = build_local_audio_research_source(
        media_result.artifact.path,
        client=_FixedTranscriptionClient(transcription),
        title=source_input.title or output_stem,
        source_url=source_input.page_url,
        notes="source=browser_session_asr",
    )
    return BrowserSessionAsrResult(
        media_result=media_result,
        transcription=transcription,
        source_import_result=source_import_result,
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = run_browser_session_asr_pipeline(
        BrowserSessionAsrInput(
            page_url=args.url,
            output_stem=args.output_stem,
            title=args.title,
            raw_output_dir=args.raw_output_dir,
            wav_output_dir=args.wav_output_dir,
            transcript_output_dir=args.transcript_output_dir,
            chrome_user_data_dir=args.chrome_user_data_dir,
            chrome_profile_directory=args.chrome_profile_directory,
            chrome_binary_path=args.chrome_binary_path,
            chromedriver_path=args.chromedriver_path,
            headless=args.headless,
            settle_seconds=args.settle_seconds,
            playback_wait_seconds=args.playback_wait_seconds,
            openvino_model_dir=args.openvino_model_dir,
            openvino_device=args.openvino_device,
            language=args.language,
            task=args.task,
            ytdlp_cookies_from_browser=args.yt_dlp_cookies_from_browser,
            ytdlp_remote_components=args.yt_dlp_remote_components,
            ytdlp_download_page_url=args.yt_dlp_download_page_url,
        )
    )
    print(_format_cli_result(result))
    return 0 if result.is_available() else 1


class _FixedTranscriptionClient:
    def __init__(self, transcription: AsrTranscriptionResult) -> None:
        self.transcription = transcription

    def transcribe(self, audio_path: Path) -> AsrTranscriptionResult:
        del audio_path
        return self.transcription


def _default_browser_discovery(source_input: BrowserSessionAsrInput) -> SeleniumBrowserMediaDiscovery:
    return SeleniumBrowserMediaDiscovery(
        SeleniumBrowserSessionConfig(
            chrome_user_data_dir=source_input.chrome_user_data_dir,
            chrome_profile_directory=source_input.chrome_profile_directory,
            chrome_binary_path=source_input.chrome_binary_path,
            chromedriver_path=source_input.chromedriver_path,
            headless=source_input.headless,
            settle_seconds=source_input.settle_seconds,
            playback_wait_seconds=source_input.playback_wait_seconds,
        )
    )


def _default_downloader(source_input: BrowserSessionAsrInput) -> YtDlpMediaDownloader:
    extra_args: list[str] = []
    output_stem = safe_filename(source_input.output_stem or source_input.title or source_input.page_url)
    output_template = f"{output_stem}.%(ext)s"
    if source_input.ytdlp_cookies_from_browser:
        extra_args.extend(["--cookies-from-browser", source_input.ytdlp_cookies_from_browser])
    if source_input.ytdlp_remote_components:
        extra_args.extend(["--remote-components", source_input.ytdlp_remote_components])
    if source_input.ytdlp_download_page_url:
        return _PageUrlYtDlpMediaDownloader(
            page_url=source_input.page_url,
            output_template=output_template,
            extra_args=tuple(extra_args),
        )
    return YtDlpMediaDownloader(output_template=output_template, extra_args=tuple(extra_args))


@dataclass(frozen=True)
class _PageUrlYtDlpMediaDownloader(YtDlpMediaDownloader):
    page_url: str = ""

    def download(self, media_request, output_dir: Path):
        return super().download(replace(media_request, download_url=self.page_url), output_dir)


def _default_transcriber(source_input: BrowserSessionAsrInput) -> SpeechToTextClient | None:
    if source_input.openvino_model_dir is None:
        return None
    return OpenVINOAsrTranscriber(
        OpenVINOAsrConfig(
            model_dir=source_input.openvino_model_dir,
            device=source_input.openvino_device,
            output_dir=source_input.transcript_output_dir,
            language=source_input.language,
            task=source_input.task,
        )
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire browser-session media and optionally transcribe it with OpenVINO ASR.")
    parser.add_argument("url", help="Page URL to open with a browser session.")
    parser.add_argument("--title", default="", help="Research source title.")
    parser.add_argument("--output-stem", default="", help="Filename stem for the generated ASR-ready WAV.")
    parser.add_argument("--raw-output-dir", type=Path, default=Path("data/raw/browser-media"))
    parser.add_argument("--wav-output-dir", type=Path, default=Path("data/processed/asr-audio"))
    parser.add_argument("--transcript-output-dir", type=Path, default=Path("data/processed/asr-transcripts/openvino"))
    parser.add_argument("--chrome-user-data-dir", type=Path, default=None)
    parser.add_argument("--chrome-profile-directory", default="")
    parser.add_argument("--chrome-binary-path", type=Path, default=None)
    parser.add_argument("--chromedriver-path", type=Path, default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=3.0)
    parser.add_argument("--playback-wait-seconds", type=float, default=10.0)
    parser.add_argument("--openvino-model-dir", type=Path, default=None)
    parser.add_argument("--openvino-device", default="GPU")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--task", default="transcribe")
    parser.add_argument("--yt-dlp-cookies-from-browser", default="")
    parser.add_argument("--yt-dlp-remote-components", default="")
    parser.add_argument("--yt-dlp-download-page-url", action="store_true")
    return parser


def _format_cli_result(result: BrowserSessionAsrResult) -> str:
    lines = [
        f"status={result.status}",
        f"media_status={result.media_result.status}",
        f"media_message={result.media_result.status_message}",
    ]
    if result.media_result.artifact is not None:
        lines.append(f"wav_path={result.media_result.artifact.path}")
    if result.media_result.selected_request is not None:
        lines.append(f"selected_media_url={result.media_result.selected_request.url}")
    if result.transcription is not None:
        lines.append(f"asr_status={result.transcription.status}")
        lines.append(f"transcript_path={result.transcription.transcript_path or ''}")
    if result.source_import_result is not None:
        lines.append(f"source_status={result.source_import_result.status}")
        lines.append(f"source_identifier={result.source_import_result.source_identifier}")
    if result.media_result.error:
        lines.append(f"error={result.media_result.error}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
