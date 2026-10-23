"""End-to-end browser-session media acquisition entrypoint for ASR."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Callable

from personal_stock_investment_system.research.asr import (
    AsrTranscriptionResult,
    OpenAIAsrConfig,
    OpenAIAsrTranscriber,
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
    MediaAcquisitionError,
    MediaAcquisitionResult,
    MediaArtifact,
    MediaDownloadClient,
    SeleniumBrowserMediaDiscovery,
    SeleniumBrowserSessionConfig,
    YtDlpMediaDownloader,
    safe_filename,
)
from personal_stock_investment_system.research.sources import ResearchSource, ResearchSourceImportResult, SourceImportStatus
from personal_stock_investment_system.research.youtube_captions import (
    CaptionFetchResult, fetch_youtube_captions, fetch_youtube_captions_in_browser, save_caption_transcript,
)
from personal_stock_investment_system.research.youtube import parse_youtube_video_id

DEFAULT_OPENVINO_TRANSCRIPT_OUTPUT_DIR = Path("data/processed/asr-transcripts/openvino")
DEFAULT_OPENAI_TRANSCRIPT_OUTPUT_DIR = Path("data/processed/asr-transcripts/openai")
BrowserSessionAsrProgressCallback = Callable[[str, str, str], None]
CaptionFetcher = Callable[..., CaptionFetchResult]


@dataclass(frozen=True)
class BrowserSessionAsrInput:
    page_url: str
    output_stem: str = ""
    title: str = ""
    raw_output_dir: Path = Path("data/raw/browser-media")
    wav_output_dir: Path = Path("data/processed/asr-audio")
    transcript_output_dir: Path = DEFAULT_OPENVINO_TRANSCRIPT_OUTPUT_DIR
    asr_provider: str = ""
    chrome_user_data_dir: Path | None = None
    chrome_profile_directory: str = ""
    chrome_binary_path: Path | None = None
    chromedriver_path: Path | None = None
    headless: bool = False
    settle_seconds: float = 3.0
    playback_wait_seconds: float = 10.0
    openvino_model_dir: Path | None = None
    openvino_device: str = "GPU"
    openai_transcription_model: str = ""
    openai_transcription_prompt: str = ""
    openai_chunk_length_seconds: float = 180.0
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
    caption_diagnostic: str = ""

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
    on_progress: BrowserSessionAsrProgressCallback | None = None,
    caption_fetcher: CaptionFetcher = fetch_youtube_captions,
    browser_caption_fetcher: CaptionFetcher = fetch_youtube_captions_in_browser,
) -> BrowserSessionAsrResult:
    output_stem = source_input.output_stem or safe_filename(source_input.title or source_input.page_url)
    try:
        parse_youtube_video_id(source_input.page_url)
        is_youtube = True
    except ValueError:
        is_youtube = False
    if is_youtube and source_input.asr_provider not in {"", "none"}:
        _emit_progress(on_progress, "captions", "running", "正在檢查 YouTube 現成字幕。")
        try:
            captions = caption_fetcher(
                source_input.page_url,
                cookies_from_browser=source_input.ytdlp_cookies_from_browser,
                remote_components=source_input.ytdlp_remote_components,
                work_dir=source_input.transcript_output_dir,
            )
        except Exception as error:  # noqa: BLE001 - caption failure must not block the existing ASR fallback.
            captions = CaptionFetchResult(error=f"字幕檢查失敗（{type(error).__name__}），改用音訊轉錄。")
        if not captions.segments:
            first_error = captions.error
            try:
                browser_captions = browser_caption_fetcher(source_input.page_url, _browser_config(source_input))
            except Exception as error:  # noqa: BLE001 - continue to ASR when browser subtitles also fail.
                browser_captions = CaptionFetchResult(error=f"瀏覽器字幕檢查失敗（{type(error).__name__}）。")
            captions = browser_captions if browser_captions.segments else CaptionFetchResult(
                error=f"{first_error} {browser_captions.error}".strip(),
                track_found=captions.track_found or browser_captions.track_found,
            )
        if captions.segments:
            transcript = save_caption_transcript(
                captions, source_input.transcript_output_dir / f"{safe_filename(output_stem)}-captions.json",
            )
            _emit_progress(on_progress, "captions", "success", transcript.status_message)
            source = ResearchSource(
                source_type="youtube_public", title=source_input.title or output_stem,
                source_url=source_input.page_url,
                raw_text="\n".join(f"[{segment.display_timestamp()}] {segment.text}" for segment in captions.segments),
                source_locator=source_input.page_url,
                notes=f"transcript_source=youtube_captions;language={captions.language}",
            )
            return BrowserSessionAsrResult(
                media_result=MediaAcquisitionResult(
                    status="available", source_identifier=source_input.page_url,
                    status_message="已使用 YouTube 現成字幕；無須下載影片音訊。",
                ),
                transcription=transcript,
                source_import_result=ResearchSourceImportResult(
                    source=source, status="available", source_identifier=source_input.page_url,
                    status_message=transcript.status_message,
                ),
            )
        caption_diagnostic = captions.error or "未取得現成字幕，改用音訊轉錄。"
        if captions.track_found:
            caption_diagnostic = (
                f"{caption_diagnostic} 已確認影片有字幕軌，但目前無法讀取字幕內容；"
                "為避免意外下載長影片並執行 ASR，已停止處理。請稍後重試或在進階模式貼上逐字稿。"
            )
            _emit_progress(on_progress, "captions", "failed", caption_diagnostic)
            return BrowserSessionAsrResult(
                media_result=MediaAcquisitionResult(
                    status="transcript_unavailable", source_identifier=source_input.page_url,
                    status_message="影片有字幕，但目前無法讀取；未啟動音訊轉錄。",
                ),
                caption_diagnostic=caption_diagnostic,
            )
        _emit_progress(on_progress, "captions", "failed", caption_diagnostic)
    else:
        caption_diagnostic = ""
    acquirer = BrowserSessionMediaAcquirer(
        discovery=discovery or _default_browser_discovery(source_input),
        downloader=downloader or _default_downloader(source_input),
        preprocessor=preprocessor or FfmpegAudioPreprocessor(),
        raw_output_dir=source_input.raw_output_dir,
        wav_output_dir=source_input.wav_output_dir,
    )
    _emit_progress(on_progress, "media", "running", "正在取得影片媒體並轉換 ASR 音訊。")
    media_result = acquirer.acquire_for_asr(source_input.page_url, output_stem=output_stem)
    if not media_result.is_available() or media_result.artifact is None:
        _emit_progress(on_progress, "media", "failed", media_result.status_message)
        return BrowserSessionAsrResult(media_result=media_result, caption_diagnostic=caption_diagnostic)
    _emit_progress(on_progress, "media", "success", media_result.status_message)

    result = _transcribe_media_result(
        source_input,
        media_result,
        speech_to_text=speech_to_text,
        on_progress=on_progress,
    )
    return replace(result, caption_diagnostic=caption_diagnostic)


def run_existing_media_asr_pipeline(
    source_input: BrowserSessionAsrInput,
    media_path: Path,
    *,
    preprocessor: AudioPreprocessor | None = None,
    speech_to_text: SpeechToTextClient | None = None,
) -> BrowserSessionAsrResult:
    """Continue ASR from an already-downloaded local media artifact."""
    resolved_media_path = media_path.expanduser().resolve()
    if not resolved_media_path.is_file():
        return BrowserSessionAsrResult(
            media_result=MediaAcquisitionResult(
                status="media_unavailable",
                source_identifier=str(media_path),
                status_message="指定的既有媒體檔不存在，無法接續轉錄。",
                error=f"missing_media_file: {resolved_media_path}",
            )
        )

    output_stem = source_input.output_stem or resolved_media_path.stem
    wav_path = source_input.wav_output_dir / f"{safe_filename(output_stem)}-16k-mono.wav"
    raw_artifact = MediaArtifact(
        path=resolved_media_path,
        source_url=source_input.page_url,
        artifact_type="stream",
        notes="reused_existing_media=true",
    )
    try:
        wav_artifact = (preprocessor or FfmpegAudioPreprocessor()).to_asr_wav(raw_artifact, wav_path)
    except MediaAcquisitionError as error:
        return BrowserSessionAsrResult(
            media_result=MediaAcquisitionResult(
                status=error.status,
                source_identifier=str(resolved_media_path),
                status_message=error.status_message,
                error=error.error,
            )
        )

    return _transcribe_media_result(
        source_input,
        MediaAcquisitionResult(
            status="available",
            source_identifier=str(resolved_media_path),
            artifact=wav_artifact,
            status_message="已使用既有媒體轉成 16 kHz mono WAV，準備轉錄。",
        ),
        speech_to_text=speech_to_text,
    )


def _transcribe_media_result(
    source_input: BrowserSessionAsrInput,
    media_result: MediaAcquisitionResult,
    *,
    speech_to_text: SpeechToTextClient | None,
    on_progress: BrowserSessionAsrProgressCallback | None = None,
) -> BrowserSessionAsrResult:
    if media_result.artifact is None:
        return BrowserSessionAsrResult(media_result=media_result)

    transcriber = speech_to_text or _default_transcriber(source_input)
    if transcriber is None:
        return BrowserSessionAsrResult(media_result=media_result)

    _emit_progress(on_progress, "transcription", "running", "正在使用選定的 ASR provider 產生逐字稿。")
    transcription = transcriber.transcribe(media_result.artifact.path)
    _emit_progress(
        on_progress,
        "transcription",
        "success" if transcription.status == "available" else "failed",
        transcription.status_message,
    )
    source_import_result = build_local_audio_research_source(
        media_result.artifact.path,
        client=_FixedTranscriptionClient(transcription),
        title=source_input.title or source_input.output_stem or media_result.artifact.path.stem,
        source_url=source_input.page_url,
        notes="source=browser_session_asr",
    )
    return BrowserSessionAsrResult(
        media_result=media_result,
        transcription=transcription,
        source_import_result=source_import_result,
    )


def _emit_progress(
    callback: BrowserSessionAsrProgressCallback | None,
    stage: str,
    status: str,
    message: str,
) -> None:
    if callback is not None:
        callback(stage, status, message)


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
            asr_provider=args.asr_provider,
            chrome_user_data_dir=args.chrome_user_data_dir,
            chrome_profile_directory=args.chrome_profile_directory,
            chrome_binary_path=args.chrome_binary_path,
            chromedriver_path=args.chromedriver_path,
            headless=args.headless,
            settle_seconds=args.settle_seconds,
            playback_wait_seconds=args.playback_wait_seconds,
            openvino_model_dir=args.openvino_model_dir,
            openvino_device=args.openvino_device,
            openai_transcription_model=args.openai_transcription_model,
            openai_transcription_prompt=args.openai_transcription_prompt,
            openai_chunk_length_seconds=args.openai_chunk_length_seconds,
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
    return SeleniumBrowserMediaDiscovery(_browser_config(source_input))


def _browser_config(source_input: BrowserSessionAsrInput) -> SeleniumBrowserSessionConfig:
    return SeleniumBrowserSessionConfig(
        chrome_user_data_dir=source_input.chrome_user_data_dir,
        chrome_profile_directory=source_input.chrome_profile_directory,
        chrome_binary_path=source_input.chrome_binary_path,
        chromedriver_path=source_input.chromedriver_path,
        headless=source_input.headless,
        settle_seconds=source_input.settle_seconds,
        playback_wait_seconds=source_input.playback_wait_seconds,
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
    provider = source_input.asr_provider or ("openvino" if source_input.openvino_model_dir is not None else "none")
    if provider == "none":
        return None
    if provider == "openai":
        return OpenAIAsrTranscriber(
            OpenAIAsrConfig(
                model=source_input.openai_transcription_model,
                output_dir=_transcript_output_dir(source_input, "openai"),
                language=source_input.language,
                prompt=source_input.openai_transcription_prompt,
                chunk_length_seconds=source_input.openai_chunk_length_seconds,
            )
        )
    if provider == "openvino" and source_input.openvino_model_dir is not None:
        return OpenVINOAsrTranscriber(
            OpenVINOAsrConfig(
                model_dir=source_input.openvino_model_dir,
                device=source_input.openvino_device,
                output_dir=_transcript_output_dir(source_input, "openvino"),
                language=source_input.language,
                task=source_input.task,
            )
        )
    return None


def _transcript_output_dir(source_input: BrowserSessionAsrInput, provider: str) -> Path:
    if provider == "openai" and source_input.transcript_output_dir == DEFAULT_OPENVINO_TRANSCRIPT_OUTPUT_DIR:
        return DEFAULT_OPENAI_TRANSCRIPT_OUTPUT_DIR
    return source_input.transcript_output_dir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire browser-session media and optionally transcribe it with ASR.")
    parser.add_argument("url", help="Page URL to open with a browser session.")
    parser.add_argument("--title", default="", help="Research source title.")
    parser.add_argument("--output-stem", default="", help="Filename stem for the generated ASR-ready WAV.")
    parser.add_argument("--raw-output-dir", type=Path, default=Path("data/raw/browser-media"))
    parser.add_argument("--wav-output-dir", type=Path, default=Path("data/processed/asr-audio"))
    parser.add_argument("--transcript-output-dir", type=Path, default=DEFAULT_OPENVINO_TRANSCRIPT_OUTPUT_DIR)
    parser.add_argument(
        "--asr-provider",
        choices=("none", "openvino", "openai"),
        default="",
        help="ASR provider. Default: openvino when --openvino-model-dir is set, otherwise none.",
    )
    parser.add_argument("--chrome-user-data-dir", type=Path, default=None)
    parser.add_argument("--chrome-profile-directory", default="")
    parser.add_argument("--chrome-binary-path", type=Path, default=None)
    parser.add_argument("--chromedriver-path", type=Path, default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=3.0)
    parser.add_argument("--playback-wait-seconds", type=float, default=10.0)
    parser.add_argument("--openvino-model-dir", type=Path, default=None)
    parser.add_argument("--openvino-device", default="GPU")
    parser.add_argument("--openai-transcription-model", default="")
    parser.add_argument("--openai-transcription-prompt", default="")
    parser.add_argument("--openai-chunk-length-seconds", type=float, default=180.0)
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
        for warning in result.transcription.warnings:
            lines.append(f"asr_warning={warning}")
        if result.transcription.error:
            lines.append(f"asr_error={result.transcription.error}")
    if result.source_import_result is not None:
        lines.append(f"source_status={result.source_import_result.status}")
        lines.append(f"source_identifier={result.source_import_result.source_identifier}")
    if result.media_result.error:
        lines.append(f"error={result.media_result.error}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
