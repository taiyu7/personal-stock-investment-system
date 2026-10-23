from __future__ import annotations

import os
import re
import multiprocessing
from queue import Empty
from io import BytesIO
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from personal_stock_investment_system.research import (
    BrowserSessionAsrInput,
    BrowserSessionAsrResult,
    DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS,
    DEFAULT_OBSIDIAN_INBOX_PATH,
    DEFAULT_OPENAI_TRANSCRIPTION_MODEL,
    PhaseOneResearchInput,
    ResearchAnalysisSettings,
    ResearchReportOutputSettings,
    MopsCompanyDirectoryClient,
    build_research_report_filename,
    run_browser_session_asr_pipeline,
    run_existing_media_asr_pipeline,
    QuickReportProgressEvent,
    QuickVideoReportBatchResult,
    QuickVideoReportInput,
    QuickVideoReportResult,
    ResearchCorrectionRule,
    ResearchCorrectionRuleRepository,
    apply_research_correction_rules,
    parse_issue_target,
    parse_research_report_markdown,
    generate_statistical_report,
    build_quick_video_report_filename,
    run_quick_video_research_report,
    run_phase_one_research_source_analysis,
    render_research_report,
    sync_taiwan_stock_directory,
)
from personal_stock_investment_system.research.media import SeleniumBrowserSessionConfig, safe_filename
from personal_stock_investment_system.research.entrypoint import AvailableYouTubeCaptionClient
from personal_stock_investment_system.research.batch_job import run_video_batch_job, terminate_video_batch_process
from personal_stock_investment_system.storage import TaiwanStockRepository, sqlite_database_path


INPUT_KIND_OPTIONS = {
    "手動文字／逐字稿": "manual_text",
    "ASR 逐字稿 JSON": "asr_transcript_json",
    "PDF 路徑": "pdf",
    "公開 YouTube URL": "youtube_public",
}

ANALYSIS_PROVIDER_OPTIONS = {
    "本機規則 fallback": "rule_based_fallback",
    "OpenAI": "openai",
    "Claude（尚未接 API）": "anthropic_claude",
}

REPORT_STYLE_OPTIONS = {
    "固定研究報告（可做多來源統計）": "structured_report",
    "投資情報摘要（含主流股基期防守表）": "investment_brief",
}

TRANSCRIPTION_PROVIDER_OPTIONS = {
    "只產生 WAV": "none",
    "OpenAI": "openai",
    "OpenVINO": "openvino",
}

DEFAULT_BROWSER_ASR_SETTINGS = {
    "chrome_user_data_dir": "data/local/psis-browser-asr-debug-profile",
    "chrome_binary_path": "/usr/bin/chromium",
    "chromedriver_path": "/usr/bin/chromedriver",
    "headless": True,
    "yt_dlp_cookies_from_browser": "",
    "yt_dlp_remote_components": "ejs:github",
    "openvino_model_dir": r"data\local\openvino\breeze-asr-25-fp32",
    "openvino_device": "GPU",
    "language": "zh",
    "settle_seconds": 3.0,
    "playback_wait_seconds": 20.0,
}

WINDOWS_BROWSER_ASR_SETTINGS = {
    **DEFAULT_BROWSER_ASR_SETTINGS,
    "chrome_user_data_dir": r"data\local\psis-browser-asr-debug-profile",
    "chrome_binary_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "chromedriver_path": r"data\local\chromedriver\chromedriver-win64\chromedriver.exe",
    "headless": False,
    "yt_dlp_cookies_from_browser": r"chrome:C:\Users\taiyu\AppData\Local\psis-browser-asr-profile\Default",
}

QUICK_REPORT_TIMELINE_STEPS = (
    ("validate", "驗證輸入與公司清單"),
    ("captions", "檢查影片現成字幕"),
    ("media", "取得影片媒體並轉換 ASR 音訊"),
    ("transcription", "音訊轉錄（無可用字幕時）"),
    ("analysis", "OpenAI 研究彙整"),
    ("render", "查核股票身分並產生 Markdown"),
    ("complete", "摘要報告完成"),
)


def get_default_browser_asr_settings() -> dict[str, str | float]:
    return WINDOWS_BROWSER_ASR_SETTINGS if os.name == "nt" else DEFAULT_BROWSER_ASR_SETTINGS


def _option_value(options: dict[str, str], label: str | None, default_label: str) -> str:
    return options.get(label or default_label, options[default_label])


def build_browser_asr_input(
    *,
    page_url: str,
    output_stem: str,
    title: str,
    asr_provider: str,
    chrome_user_data_dir: str,
    chrome_binary_path: str,
    chromedriver_path: str,
    headless: bool,
    settle_seconds: float,
    playback_wait_seconds: float,
    yt_dlp_cookies_from_browser: str,
    yt_dlp_remote_components: str,
    yt_dlp_download_page_url: bool,
    openvino_model_dir: str,
    openvino_device: str,
    openai_transcription_model: str,
    openai_transcription_prompt: str,
    openai_chunk_length_seconds: float,
    language: str,
) -> BrowserSessionAsrInput:
    return BrowserSessionAsrInput(
        page_url=page_url.strip(),
        output_stem=output_stem.strip(),
        title=title.strip(),
        asr_provider=asr_provider,
        chrome_user_data_dir=Path(chrome_user_data_dir) if chrome_user_data_dir.strip() else None,
        chrome_binary_path=Path(chrome_binary_path) if chrome_binary_path.strip() else None,
        chromedriver_path=Path(chromedriver_path) if chromedriver_path.strip() else None,
        headless=headless,
        settle_seconds=settle_seconds,
        playback_wait_seconds=playback_wait_seconds,
        ytdlp_cookies_from_browser=yt_dlp_cookies_from_browser.strip(),
        ytdlp_remote_components=yt_dlp_remote_components.strip(),
        ytdlp_download_page_url=yt_dlp_download_page_url,
        openvino_model_dir=Path(openvino_model_dir) if openvino_model_dir.strip() else None,
        openvino_device=openvino_device.strip() or "GPU",
        openai_transcription_model=openai_transcription_model.strip(),
        openai_transcription_prompt=openai_transcription_prompt.strip(),
        openai_chunk_length_seconds=openai_chunk_length_seconds,
        language=language.strip() or "zh",
    )


def _selected_input_label_from_transcript(transcript_json_path: str) -> str:
    return "ASR 逐字稿 JSON" if transcript_json_path.strip() else "手動文字／逐字稿"


def _is_available_status(status: str) -> bool:
    return status == "available"


def _render_browser_asr_status(result: BrowserSessionAsrResult) -> None:
    if result.caption_diagnostic:
        st.warning(result.caption_diagnostic)
    if result.transcription is not None and result.transcription.status_message.startswith("已使用 YouTube 現成字幕"):
        st.info(result.media_result.status_message)
    elif result.media_result.is_available():
        st.success("音檔已取得並轉成 16 kHz mono WAV。")
    else:
        st.error(result.media_result.status_message or "音檔取得失敗。")
        if result.media_result.error:
            st.code(_safe_media_error(result.media_result.error), language=None)
    if result.media_result.artifact is not None:
        st.code(str(result.media_result.artifact.path), language=None)
    if result.transcription is not None:
        if _is_available_status(result.transcription.status):
            st.success(result.transcription.status_message)
        else:
            st.warning(result.transcription.status_message or "逐字稿尚未產生。")
        if result.transcription.transcript_path is not None:
            st.code(str(result.transcription.transcript_path), language=None)
        for warning in result.transcription.warnings:
            st.warning(warning)
        if result.transcription.error:
            st.error(result.transcription.error)


def _safe_media_error(error: str) -> str:
    redacted = re.sub(
        r"(?i)(authorization|cookie|api[_ -]?key|token|password)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        error,
    )
    return re.sub(
        r"https?://[^\s?]+\?[^\s]+",
        lambda match: urlunsplit(urlsplit(match.group())._replace(query="[redacted]")),
        redacted,
    )


def _existing_media_candidates(output_stem: str, raw_output_dir: Path = Path("data/raw/browser-media")) -> tuple[Path, ...]:
    safe_stem = safe_filename(output_stem)
    if not safe_stem or not raw_output_dir.exists():
        return ()
    return tuple(path.resolve() for path in raw_output_dir.glob(f"{safe_stem}.*") if path.is_file() and path.stat().st_size > 0)


def _store_transcript_result(result: BrowserSessionAsrResult, page_url: str) -> None:
    if result.transcription is not None and result.transcription.transcript_path is not None:
        st.session_state["research_asr_transcript_json_path"] = str(result.transcription.transcript_path)
        st.session_state["research_asr_source_url"] = page_url.strip()


def render_research_source_analysis_page() -> None:
    st.subheader("影音生成摘要報告")
    st.caption("快速模式只需三個欄位即可產生固定研究報告；進階模式保留原有完整設定。")
    quick_tab, statistics_tab, advanced_tab = st.tabs(("快速產生報告", "產生統計分析報告", "進階模式"))
    with quick_tab:
        _render_quick_video_report_page()
    with statistics_tab:
        _render_statistical_report_page()
    with advanced_tab:
        _render_advanced_research_source_analysis_page()


def _render_statistical_report_page() -> None:
    st.markdown("#### 產生統計分析報告")
    st.caption("選取至少兩份固定研究報告 Markdown；股票排名與三項計數由程式計算，OpenAI 只負責依附證據整合文字。")
    files = st.file_uploader(
        "選取多份固定研究報告 Markdown",
        type=("md",),
        accept_multiple_files=True,
        key="statistical_report_uploads",
        help="可多選固定研究報告檔案；支援最新下載版本，也可匯入舊版固定格式報告。",
    )
    default_model = os.getenv("OPENAI_RESEARCH_AGGREGATION_MODEL", os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini"))
    model = st.text_input("OpenAI 模型", value=default_model, key="statistical_report_model")
    st.session_state.setdefault("statistical_report_result", None)
    if st.button("產生統計分析報告", type="primary", icon=":material/analytics:", key="generate_statistical_report"):
        try:
            reports = tuple(parse_research_report_markdown(file.getvalue().decode("utf-8")) for file in files or ())
            if len(reports) < 2:
                raise ValueError("請至少選取兩份固定研究報告。")
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("尚未設定 OPENAI_API_KEY，無法產生統計分析報告。")
            directory = TaiwanStockRepository(sqlite_database_path()).load_directory()
            if directory is None or not directory.companies:
                raise ValueError("本機沒有可用公司清單，請先在進階模式同步官方上市／上櫃公司清單。")
            correction_rules = _correction_rule_repository().list_rules()
            reports = tuple(
                apply_research_correction_rules(report, correction_rules, directory)
                for report in reports
            )
            st.session_state["statistical_report_result"] = generate_statistical_report(reports, directory, model=model)
            st.session_state["statistical_report_error"] = ""
        except Exception as error:  # noqa: BLE001 - show provider and parser errors inside this page.
            st.session_state["statistical_report_error"] = str(error)
            st.session_state["statistical_report_result"] = None
    if st.session_state.get("statistical_report_error"):
        st.error(st.session_state["statistical_report_error"])
    result = st.session_state.get("statistical_report_result")
    if result is not None:
        st.success(f"已完成統計分析（{result.provider}／{result.model}）。")
        st.caption(f"下載檔名：{result.filename}")
        st.markdown(result.markdown)
        st.download_button(
            "下載統計分析報告 Markdown", data=result.markdown.encode("utf-8"),
            file_name=result.filename, mime="text/markdown", icon=":material/download:",
        )


def _render_quick_video_report_page() -> None:
    st.markdown("#### 快速產生報告")
    st.caption("優先使用 YouTube 現成字幕；沒有可用字幕時使用 OpenAI 音訊轉錄。研究彙整固定使用 OpenAI，並以本機公司清單查核股票身分。")
    count = st.number_input("本次影片數", min_value=1, max_value=10, value=2, step=1, key="quick_video_batch_count")
    st.session_state.setdefault("quick_video_report_batch_result", None)
    with st.form("quick_video_report_batch_form", border=False):
        entries = []
        for index in range(int(count)):
            st.markdown(f"**影片 {index + 1}**")
            url_col, date_col, title_col = st.columns((2, 1, 1))
            video_url = url_col.text_input("影片連結", placeholder="https://www.youtube.com/watch?v=...", key=f"quick_video_batch_url_{index}")
            published_date = date_col.date_input(
                "影片日期", value=None, format="YYYY-MM-DD", key=f"quick_video_batch_date_{index}",
                help="必填，格式固定為 YYYY-MM-DD。",
            )
            title = title_col.text_input("影片名稱", key=f"quick_video_batch_title_{index}")
            entries.append((video_url, published_date, title))
        submitted = st.form_submit_button(
            "依序產生報告並統計", type="primary", icon=":material/auto_awesome:",
            disabled=st.session_state.get("quick_video_batch_job") is not None,
        )

    if submitted:
        _run_quick_video_report_batch(entries)
    if st.session_state.get("quick_video_batch_job") is not None:
        _render_quick_batch_job()
    result = st.session_state.get("quick_video_report_batch_result")
    if isinstance(result, QuickVideoReportBatchResult):
        _render_quick_video_report_batch_result(result)
    _render_correction_rules_manager()


def _build_quick_video_browser_input(request: QuickVideoReportInput) -> BrowserSessionAsrInput:
    browser_settings = get_default_browser_asr_settings()
    filename = build_quick_video_report_filename(request)
    return build_browser_asr_input(
        page_url=request.video_url, output_stem=Path(filename).stem, title=request.title, asr_provider="openai",
        chrome_user_data_dir=str(browser_settings["chrome_user_data_dir"]),
        chrome_binary_path=str(browser_settings["chrome_binary_path"]),
        chromedriver_path=str(browser_settings["chromedriver_path"]), headless=bool(browser_settings["headless"]),
        settle_seconds=float(browser_settings["settle_seconds"]),
        playback_wait_seconds=float(browser_settings["playback_wait_seconds"]),
        yt_dlp_cookies_from_browser=str(browser_settings["yt_dlp_cookies_from_browser"]),
        yt_dlp_remote_components=str(browser_settings["yt_dlp_remote_components"]),
        yt_dlp_download_page_url=True, openvino_model_dir=str(browser_settings["openvino_model_dir"]),
        openvino_device=str(browser_settings["openvino_device"]),
        openai_transcription_model=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", DEFAULT_OPENAI_TRANSCRIPTION_MODEL),
        openai_transcription_prompt=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_PROMPT", ""),
        openai_chunk_length_seconds=float(os.getenv("OPENAI_AUDIO_CHUNK_LENGTH_SECONDS", DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS)),
        language=str(browser_settings["language"]),
    )


def _run_quick_video_report_batch(entries) -> None:
    if st.session_state.get("quick_video_batch_job") is not None:
        st.warning("已有批次正在處理。請先等待完成或按「強制中斷」。")
        return
    if not os.getenv("OPENAI_API_KEY"):
        st.error("尚未設定 OPENAI_API_KEY，無法執行 OpenAI 逐字稿與研究彙整。")
        return
    repository = TaiwanStockRepository(sqlite_database_path())
    directory = repository.load_directory()
    latest_sync = repository.latest_sync(status="success")
    valid = []
    invalid = []
    for index, (video_url, published_date, title) in enumerate(entries, start=1):
        errors = []
        if published_date is None:
            errors.append("影片日期必填，格式固定為 YYYY-MM-DD。")
        if not video_url.strip():
            errors.append("影片連結必填。")
        elif urlsplit(video_url.strip()).scheme not in {"http", "https"} or not urlsplit(video_url.strip()).netloc:
            errors.append("影片連結必須是有效的 HTTP(S) URL。")
        if not title.strip():
            errors.append("影片名稱必填。")
        if errors:
            invalid.append((index, "；".join(errors)))
            continue
        request = QuickVideoReportInput(video_url.strip(), published_date, title.strip())
        valid.append((index, request, _build_quick_video_browser_input(request)))

    previous = st.session_state.get("quick_video_report_batch_result")
    retained = []
    pending = []
    current_indices = {index for index, _request, _browser_input in valid}
    for index, request, browser_input in valid:
        old = next((item for item in previous.items if item.index == index), None) if isinstance(previous, QuickVideoReportBatchResult) else None
        if old is not None and old.request == request and old.result.is_available:
            retained.append(old)
        else:
            pending.append((index, request, browser_input))
    if not pending and len(retained) < 2:
        st.session_state["quick_video_report_batch_result"] = QuickVideoReportBatchResult(tuple(retained), tuple(invalid))
        return
    _launch_quick_batch_job(
        tuple(pending), tuple(retained), tuple(invalid), directory,
        tuple(sorted(current_indices)), {index: request.title for index, request, _ in valid},
        latest_sync is not None and latest_sync.is_stale(),
    )


def _launch_quick_batch_job(pending, retained, invalid, directory, indices, titles, stale) -> None:
    context = multiprocessing.get_context("spawn")
    output_queue = context.Queue()
    process = context.Process(
        target=run_video_batch_job,
        args=(pending, retained, invalid, directory, sqlite_database_path(), output_queue),
        daemon=True,
    )
    try:
        process.start()
    except Exception as error:  # noqa: BLE001 - keep existing reports when the worker cannot start.
        output_queue.close()
        st.error(f"無法啟動報告處理程序：{error}")
        return
    st.session_state["quick_video_batch_job"] = {
        "process": process, "queue": output_queue,
        "items": {item.index: item for item in retained}, "events": {},
        "invalid": invalid, "indices": indices,
        "titles": titles, "stale": stale,
        "aggregate": False,
    }


@st.fragment(run_every="1s")
def _render_quick_batch_job() -> None:
    job = st.session_state.get("quick_video_batch_job")
    if job is None:
        return
    completed = None
    error = ""
    while True:
        try:
            message = job["queue"].get_nowait()
        except Empty:
            break
        if message[0] == "progress":
            job["events"].setdefault(message[1], []).append(message[2])
        elif message[0] == "item":
            item = message[1]
            job["items"][item.index] = item
        elif message[0] == "aggregate":
            job["aggregate"] = True
        elif message[0] == "done":
            completed = message[1]
        elif message[0] == "error":
            error = message[1]
    if completed is not None:
        st.session_state["quick_video_report_batch_result"] = completed
        st.session_state["quick_video_batch_stale"] = job["stale"]
        _close_quick_batch_job(job)
        st.rerun()
    if error or not job["process"].is_alive():
        _finish_interrupted_batch(job, error or "處理程序意外結束。")
        st.rerun()
    with st.container(border=True):
        st.info("正在產生報告；可隨時強制中斷，已完成的個別報告會保留。")
        if st.button("強制中斷", type="secondary", icon=":material/stop_circle:", key="stop_quick_video_batch"):
            terminate_video_batch_process(job["process"])
            _finish_interrupted_batch(job, "已由使用者強制中斷。")
            st.rerun()
        lines = []
        for index in job["indices"]:
            latest_events = {event.step_id: event for event in job["events"].get(index, ())}
            item = job["items"].get(index)
            state = (
                "完成" if item is not None and item.result.is_available else
                "失敗" if item is not None else
                "處理中" if latest_events else "等待中"
            )
            lines.append(f"影片 {index}｜{job['titles'][index]}｜{state}")
            for step_id, label in QUICK_REPORT_TIMELINE_STEPS:
                event = latest_events.get(step_id)
                marker = {"pending": "○", "running": "▶", "success": "✓", "failed": "✕"}.get(event.status if event else "pending", "○")
                lines.append(f"  {marker} {label}")
                if event is not None and event.message:
                    lines.append(f"    {_safe_media_error(event.message)}")
        if job["aggregate"]:
            lines.append("▶ 套用查核規則並產生統計分析報告")
        st.text("\n".join(lines))


def _finish_interrupted_batch(job, message: str) -> None:
    items = tuple(job["items"][index] for index in sorted(job["items"]))
    st.session_state["quick_video_report_batch_result"] = QuickVideoReportBatchResult(
        items, job["invalid"], aggregation_error=message,
    )
    _close_quick_batch_job(job)


def _close_quick_batch_job(job) -> None:
    job["process"].join(timeout=0.2)
    job["queue"].close()
    st.session_state["quick_video_batch_job"] = None


def _apply_rules_to_batch(
    batch: QuickVideoReportBatchResult,
    repository: ResearchCorrectionRuleRepository,
    directory,
) -> QuickVideoReportBatchResult:
    items = tuple(
        replace(
            item,
            original_result=item.original_result or item.result,
            result=_refresh_quick_result_with_rules(item.original_result or item.result, repository, directory),
        )
        for item in batch.items
    )
    refreshed = replace(batch, items=items, statistical_report=None, aggregation_error="")
    reports = tuple(
        item.result.research_result.report for item in items
        if item.result.is_available and item.result.research_result is not None
    )
    if len(reports) >= 2 and directory is not None:
        try:
            return replace(refreshed, statistical_report=generate_statistical_report(reports, directory))
        except Exception as error:  # noqa: BLE001 - keep every completed per-video report available.
            return replace(refreshed, aggregation_error=str(error))
    return refreshed


def _recompute_batch_aggregate(batch: QuickVideoReportBatchResult, directory) -> QuickVideoReportBatchResult:
    reports = tuple(
        item.result.research_result.report for item in batch.items
        if item.result.is_available and item.result.research_result is not None
    )
    if len(reports) < 2 or directory is None:
        return replace(batch, statistical_report=None, aggregation_error="")
    try:
        return replace(batch, statistical_report=generate_statistical_report(reports, directory), aggregation_error="")
    except Exception as error:  # noqa: BLE001 - individual reports remain available.
        return replace(batch, statistical_report=None, aggregation_error=str(error))


def _render_quick_video_report_batch_result(batch: QuickVideoReportBatchResult) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("影片總數", batch.total_count)
    metric_cols[1].metric("成功", batch.success_count)
    metric_cols[2].metric("失敗", batch.failure_count)
    metric_cols[3].metric("輸入無效", len(batch.invalid_items))
    if batch.invalid_items:
        with st.expander("無效輸入", expanded=True):
            for index, error in batch.invalid_items:
                st.error(f"影片 {index}：{error}")
    if batch.failure_count and st.session_state.get("quick_video_batch_job") is None:
        if st.button("只重試失敗影片", type="secondary", icon=":material/replay:", key="retry_failed_video_reports"):
            repository = TaiwanStockRepository(sqlite_database_path())
            directory = repository.load_directory()
            failed = tuple(
                (item.index, item.request, item.browser_input)
                for item in batch.items if not item.result.is_available
            )
            retained = tuple(item for item in batch.items if item.result.is_available)
            _launch_quick_batch_job(
                failed, retained, batch.invalid_items, directory,
                tuple(item.index for item in batch.items),
                {item.index: item.request.title for item in batch.items},
                False,
            )
            st.rerun()
    if batch.success_count and batch.success_count < 2:
        st.info("個別報告已保留；至少兩份成功報告才能產生統計分析報告。")
    if batch.aggregation_error:
        st.error(f"統計分析報告未完成，但個別報告仍可使用：{batch.aggregation_error}")
    for item in batch.items:
        with st.expander(f"影片 {item.index}｜{item.request.title}｜{'成功' if item.result.is_available else '失敗'}", expanded=not item.result.is_available):
            if not item.result.is_available:
                st.error(_safe_media_error(item.result.error or "摘要報告未完成。"))
                continue
            if item.result.browser_asr_result is not None and item.result.browser_asr_result.caption_diagnostic:
                st.warning(item.result.browser_asr_result.caption_diagnostic)
            st.download_button(
                "下載個別報告 Markdown", data=item.result.markdown.encode("utf-8"),
                file_name=item.result.filename, mime="text/markdown", key=f"download_quick_report_{item.index}",
                icon=":material/download:",
            )
            _render_manual_review_panel(item.result, batch_index=item.index)
            st.caption(f"下載檔名：{item.result.filename}")
            st.markdown(_research_report_preview_markdown(item.result.markdown))
    if batch.statistical_report is not None:
        st.markdown("#### 統計分析報告預覽")
        st.markdown(batch.statistical_report.markdown)
        st.download_button(
            "下載統計分析報告 Markdown", data=batch.statistical_report.markdown.encode("utf-8"),
            file_name=batch.statistical_report.filename, mime="text/markdown", key="download_batch_statistical_report",
        )
        st.download_button(
            "下載全部個別報告＋統計分析報告（ZIP）",
            data=_batch_report_zip(batch),
            file_name=batch.statistical_report.filename.removesuffix(".md") + ".zip",
            mime="application/zip", key="download_batch_all_reports", icon=":material/folder_zip:",
        )


def _batch_report_zip(batch: QuickVideoReportBatchResult) -> bytes:
    archive = BytesIO()
    used_names: set[str] = set()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for item in batch.items:
            if not item.result.is_available:
                continue
            name = item.result.filename
            if name in used_names:
                name = f"影片{item.index}-{name}"
            used_names.add(name)
            bundle.writestr(name, _research_report_preview_markdown(item.result.markdown))
        if batch.statistical_report is not None:
            bundle.writestr(batch.statistical_report.filename, batch.statistical_report.markdown)
    return archive.getvalue()


def _correction_rule_repository() -> ResearchCorrectionRuleRepository:
    return ResearchCorrectionRuleRepository(sqlite_database_path())


def _render_correction_rules_manager() -> None:
    repository = _correction_rule_repository()
    with st.expander("永久修正規則管理", expanded=False):
        rules = repository.list_rules()
        if not rules:
            st.caption("尚未建立規則。可在個別報告的人工查核區確認並儲存。")
            return
        entity_labels = {
            "taiwan_stock": "台灣上市／上櫃公司",
            "foreign_stock": "外國股票",
            "etf": "ETF",
            "sector": "族群／主題",
            "non_stock": "非股票（排除）",
        }
        for index, rule in enumerate(rules):
            label = (
                f"{'啟用' if rule.enabled else '停用'}｜{rule.raw_code} {rule.raw_name} → "
                f"{entity_labels.get(rule.entity_type, rule.entity_type)} "
                f"{rule.canonical_code} {rule.canonical_name}"
            ).strip()
            with st.container(border=True):
                st.write(label)
                st.caption(f"建立：{rule.created_at or '未記錄'}｜更新：{rule.updated_at or '未記錄'}")
                control_a, control_b = st.columns(2)
                if control_a.button("停用" if rule.enabled else "啟用", key=f"correction_rule_toggle_{index}"):
                    repository.set_enabled(rule, not rule.enabled)
                    _refresh_batch_after_rule_change(repository)
                    st.rerun()
                if control_b.button("刪除", key=f"correction_rule_delete_{index}"):
                    repository.delete_rule(rule)
                    _refresh_batch_after_rule_change(repository)
                    st.rerun()


def _refresh_batch_after_rule_change(repository: ResearchCorrectionRuleRepository) -> None:
    batch = st.session_state.get("quick_video_report_batch_result")
    if not isinstance(batch, QuickVideoReportBatchResult):
        return
    directory = TaiwanStockRepository(sqlite_database_path()).load_directory()
    st.session_state["quick_video_report_batch_result"] = _apply_rules_to_batch(batch, repository, directory)


def _refresh_quick_result_with_rules(
    result: QuickVideoReportResult,
    repository: ResearchCorrectionRuleRepository,
    directory,
) -> QuickVideoReportResult:
    if result.research_result is None:
        return result
    report = apply_research_correction_rules(result.research_result.report, repository.list_rules(), directory)
    markdown = render_research_report(report)
    analysis_result = replace(result.research_result.analysis_result, report=report, markdown=markdown)
    research_result = replace(result.research_result, report=report, markdown=markdown, analysis_result=analysis_result)
    return replace(result, research_result=research_result)


def _render_manual_review_panel(result: QuickVideoReportResult, *, batch_index: int) -> None:
    if result.research_result is None:
        return
    report = result.research_result.report
    pending = [
        (index, issue)
        for index, issue in enumerate(report.verification_issues)
        if issue.status not in {"已查證", "已修正"}
    ]
    repository = _correction_rule_repository()
    directory = TaiwanStockRepository(sqlite_database_path()).load_directory()
    widget_prefix = f"manual_review_{batch_index}"
    with st.expander("人工查核與永久修正規則", expanded=bool(pending)):
        if pending:
            st.caption("選定正確分類或官方公司後，畫面會立即更新；勾選永久規則則會套用到後續完全相同的原始寫法。")
            by_index = dict(pending)
            selected_index = st.selectbox(
                "待查核項目",
                options=[index for index, _issue in pending],
                format_func=lambda index: f"{by_index[index].status}｜{by_index[index].target}｜{by_index[index].reference.display_locator() if by_index[index].reference else '未判定'}",
                key=f"{widget_prefix}_issue_index",
            )
            issue = by_index[selected_index]
            raw_code, raw_name = parse_issue_target(issue.target)
            reference = issue.reference.display_locator() if issue.reference else "未判定"
            st.info(f"{issue.claim}\n\n查核依據：{issue.evidence}\n\n原文位置：{reference}")
            kind_by_label = {
                "台灣上市／上櫃公司": "taiwan_stock",
                "外國股票": "foreign_stock",
                "ETF": "etf",
                "族群／主題": "sector",
                "非股票（排除）": "non_stock",
            }
            type_label = st.selectbox("正確分類", tuple(kind_by_label), key=f"{widget_prefix}_entity_type")
            company_options = tuple(directory.companies) if directory else ()
            selected_company = None
            if kind_by_label[type_label] == "taiwan_stock":
                if not company_options:
                    st.warning("尚無本機官方公司清單，請先在進階模式同步。")
                else:
                    selected_company = st.selectbox(
                        "官方公司清單中的正確公司",
                        options=(None, *company_options),
                        format_func=lambda company: "請明確選擇公司" if company is None else f"{company.code} {company.name}",
                        key=f"{widget_prefix}_company_explicit",
                    )
            manual_code = ""
            manual_name = ""
            if kind_by_label[type_label] in {"foreign_stock", "etf"}:
                item_kind = "Ticker／代號" if kind_by_label[type_label] == "foreign_stock" else "ETF 代號"
                item_name = "公司名稱" if kind_by_label[type_label] == "foreign_stock" else "ETF 名稱"
                manual_code = st.text_input(
                    item_kind,
                    value=raw_code,
                    key=f"{widget_prefix}_manual_code_{selected_index}",
                )
                manual_name = st.text_input(
                    item_name,
                    value=raw_name,
                    key=f"{widget_prefix}_manual_name_{selected_index}",
                )
            with st.form(f"{widget_prefix}_correction_form"):
                remember = st.checkbox("儲存為永久規則（僅精確符合原始代號與名稱時套用）", value=True)
                needs_manual_identity = kind_by_label[type_label] in {"foreign_stock", "etf"}
                invalid_manual_identity = needs_manual_identity and not (manual_code.strip() and manual_name.strip())
                apply_clicked = st.form_submit_button(
                    "確認並更新報告",
                    type="primary",
                    disabled=(kind_by_label[type_label] == "taiwan_stock" and selected_company is None)
                    or invalid_manual_identity,
                )
            if apply_clicked:
                rule = ResearchCorrectionRule(
                    raw_code=raw_code,
                    raw_name=raw_name,
                    entity_type=kind_by_label[type_label],
                    canonical_code=selected_company.code if selected_company else manual_code.strip(),
                    canonical_name=selected_company.name if selected_company else manual_name.strip(),
                )
                if remember:
                    repository.save_rule(rule)
                    batch = st.session_state.get("quick_video_report_batch_result")
                    if isinstance(batch, QuickVideoReportBatchResult):
                        st.session_state["quick_video_report_batch_result"] = _apply_rules_to_batch(batch, repository, directory)
                else:
                    updated_report = apply_research_correction_rules(report, (rule,), directory)
                    markdown = render_research_report(updated_report)
                    analysis = replace(result.research_result.analysis_result, report=updated_report, markdown=markdown)
                    research = replace(result.research_result, report=updated_report, markdown=markdown, analysis_result=analysis)
                    updated = replace(result, research_result=research)
                    batch = st.session_state.get("quick_video_report_batch_result")
                    if isinstance(batch, QuickVideoReportBatchResult):
                        items = tuple(replace(item, result=updated) if item.index == batch_index else item for item in batch.items)
                        st.session_state["quick_video_report_batch_result"] = _recompute_batch_aggregate(replace(batch, items=items), directory)
                st.rerun()
        else:
            st.caption("目前沒有待查核項目。")


def _run_quick_video_report(*, video_url: str, published_date: object, title: str) -> None:
    st.session_state["quick_video_report_result"] = None
    if published_date is None:
        st.error("請選擇影片日期，格式固定為 YYYY-MM-DD。")
        return
    if not os.getenv("OPENAI_API_KEY"):
        st.error("尚未設定 OPENAI_API_KEY，無法執行 OpenAI 逐字稿與研究彙整。")
        return

    request = QuickVideoReportInput(
        video_url=video_url.strip(),
        published_date=published_date,
        title=title.strip(),
    )
    stock_repository = TaiwanStockRepository(sqlite_database_path())
    stock_directory = stock_repository.load_directory()
    latest_sync = stock_repository.latest_sync(status="success")
    browser_settings = get_default_browser_asr_settings()
    filename = build_quick_video_report_filename(request)
    browser_input = build_browser_asr_input(
        page_url=request.video_url,
        output_stem=Path(filename).stem,
        title=request.title,
        asr_provider="openai",
        chrome_user_data_dir=str(browser_settings["chrome_user_data_dir"]),
        chrome_binary_path=str(browser_settings["chrome_binary_path"]),
        chromedriver_path=str(browser_settings["chromedriver_path"]),
        headless=bool(browser_settings["headless"]),
        settle_seconds=float(browser_settings["settle_seconds"]),
        playback_wait_seconds=float(browser_settings["playback_wait_seconds"]),
        yt_dlp_cookies_from_browser=str(browser_settings["yt_dlp_cookies_from_browser"]),
        yt_dlp_remote_components=str(browser_settings["yt_dlp_remote_components"]),
        yt_dlp_download_page_url=True,
        openvino_model_dir=str(browser_settings["openvino_model_dir"]),
        openvino_device=str(browser_settings["openvino_device"]),
        openai_transcription_model=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", DEFAULT_OPENAI_TRANSCRIPTION_MODEL),
        openai_transcription_prompt=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_PROMPT", ""),
        openai_chunk_length_seconds=float(
            os.getenv("OPENAI_AUDIO_CHUNK_LENGTH_SECONDS", DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS)
        ),
        language=str(browser_settings["language"]),
    )

    timeline = st.container(border=True)
    timeline.caption("處理進度")
    timeline_slot = timeline.empty()
    timeline_events: list[QuickReportProgressEvent] = []
    _render_quick_report_timeline(timeline_slot, timeline_events)
    status = st.status("準備產生摘要報告…", expanded=True)

    def show_progress(event: QuickReportProgressEvent) -> None:
        timeline_events.append(event)
        _render_quick_report_timeline(timeline_slot, timeline_events)
        marker = {"running": "▶", "success": "✓", "failed": "✕", "pending": "○"}[event.status]
        detail = f"：{event.message}" if event.message else ""
        status.write(f"{marker} {event.label}{detail}")
        if event.status == "failed":
            status.update(label=f"{event.label}失敗", state="error", expanded=True)
        elif event.status == "running":
            status.update(label=event.label, state="running", expanded=True)

    result = run_quick_video_research_report(
        request,
        browser_input,
        stock_directory=stock_directory,
        progress_callback=show_progress,
    )
    if result.is_available:
        status.update(label="摘要報告已完成", state="complete", expanded=True)
        if latest_sync is not None and latest_sync.is_stale():
            st.warning("本機公司清單已超過一天未更新；本報告已使用最後成功同步版本查核。")
    else:
        status.update(label="摘要報告未完成", state="error", expanded=True)
    st.session_state["quick_video_report_result"] = _refresh_quick_result_with_rules(
        result,
        _correction_rule_repository(),
        stock_directory,
    )


def _render_quick_report_timeline(slot, events: list[QuickReportProgressEvent]) -> None:
    latest_status = {event.step_id: event.status for event in events}
    lines: list[str] = []
    for index, (step_id, label) in enumerate(QUICK_REPORT_TIMELINE_STEPS):
        marker = {"pending": "○", "running": "▶", "success": "✓", "failed": "✕"}.get(
            latest_status.get(step_id, "pending"),
            "○",
        )
        lines.append(f"{marker} {label}")
        if index < len(QUICK_REPORT_TIMELINE_STEPS) - 1:
            lines.append("│")
    slot.text("\n".join(lines))


def _research_report_preview_markdown(markdown: str) -> str:
    """Hide the machine-readable import payload from the human-facing report preview."""
    return re.sub(r"\n?<!-- PSIS_RESEARCH_REPORT_V1:[A-Za-z0-9_=-]+ -->\s*$", "", markdown).rstrip()


def _render_quick_video_report_result(result: QuickVideoReportResult) -> None:
    if not result.is_available:
        st.error(result.error or "摘要報告未完成。")
        return
    st.success("摘要報告已完成，並已用本機公司清單查核股票代號與公司名稱。")
    st.caption(f"下載檔名：{result.filename}")
    st.markdown("#### 摘要報告 Markdown")
    st.text_area(
        "摘要報告 Markdown",
        value=_research_report_preview_markdown(result.markdown),
        height=520,
        key="quick_video_report_markdown",
    )
    st.download_button(
        "下載 Markdown",
        data=result.markdown.encode("utf-8"),
        file_name=result.filename,
        mime="text/markdown",
        icon=":material/download:",
    )


def _render_advanced_research_source_analysis_page() -> None:
    st.markdown("#### 進階模式")
    st.caption("輸入逐字稿、PDF 或公開影片來源，產生固定格式研究報告。")

    st.markdown("### 1. 取得逐字稿")
    st.caption("YouTube 影片優先使用現成字幕；沒有可用字幕時才從音訊產生逐字稿，成功後會自動帶到下一段。")
    st.session_state.setdefault("research_asr_transcript_json_path", "")
    st.session_state.setdefault("research_asr_source_url", "")
    browser_asr_settings = get_default_browser_asr_settings()

    with st.form("browser_asr_form"):
        browser_page_url = st.text_input(
            "影片 URL",
            value=st.session_state["research_asr_source_url"],
            placeholder="https://www.youtube.com/watch?v=...",
        )
        transcription_label = st.segmented_control(
            "轉錄 provider",
            tuple(TRANSCRIPTION_PROVIDER_OPTIONS),
            default="OpenAI",
            help="OpenAI 適合直接產生逐字稿；OpenVINO 適合本機模型；只產生 WAV 則先不做 ASR。",
        )
        transcription_provider = _option_value(TRANSCRIPTION_PROVIDER_OPTIONS, transcription_label, "OpenAI")
        if transcription_provider == "openai":
            st.info(
                "OpenAI 轉錄會先把長音檔依 chunk 秒數切段。chunk 越短通常越能降低長段漏字或截斷風險，但 API 呼叫次數會增加。"
            )
        elif transcription_provider == "openvino":
            st.info("OpenVINO 走本機模型，不會使用 OpenAI transcription prompt。")
        output_stem = st.text_input("輸出檔名前綴", value="manual-verify-dashboard-asr")
        browser_title = st.text_input("逐字稿標題", value="")

        with st.expander("瀏覽器與下載設定", expanded=False):
            chrome_user_data_dir = st.text_input(
                "Chrome user data dir",
                value=str(browser_asr_settings["chrome_user_data_dir"]),
            )
            chrome_binary_path = st.text_input(
                "Chrome binary path",
                value=str(browser_asr_settings["chrome_binary_path"]),
            )
            chromedriver_path = st.text_input(
                "ChromeDriver path",
                value=str(browser_asr_settings["chromedriver_path"]),
            )
            headless = st.checkbox("Headless browser", value=bool(browser_asr_settings["headless"]))
            yt_dlp_download_page_url = st.checkbox("yt-dlp 直接下載頁面 URL", value=True)
            yt_dlp_cookies_from_browser = st.text_input(
                "yt-dlp cookies from browser",
                value=str(browser_asr_settings["yt_dlp_cookies_from_browser"]),
            )
            yt_dlp_remote_components = st.text_input(
                "yt-dlp remote components",
                value=str(browser_asr_settings["yt_dlp_remote_components"]),
            )
            settle_seconds = st.number_input(
                "瀏覽器等待秒數",
                min_value=0.0,
                max_value=60.0,
                value=float(browser_asr_settings["settle_seconds"]),
                step=1.0,
            )
            playback_wait_seconds = st.number_input(
                "播放等待秒數",
                min_value=0.0,
                max_value=120.0,
                value=float(browser_asr_settings["playback_wait_seconds"]),
                step=1.0,
            )

        with st.expander("ASR provider 設定", expanded=False):
            openai_transcription_model = st.text_input(
                "OpenAI transcription model",
                value=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_MODEL", DEFAULT_OPENAI_TRANSCRIPTION_MODEL),
                help="可手動切換 OpenAI ASR 模型；預設使用成本較低的 gpt-4o-mini-transcribe。",
            )
            openai_chunk_length_seconds = st.number_input(
                "OpenAI chunk 秒數",
                min_value=30.0,
                max_value=900.0,
                value=float(os.getenv("OPENAI_AUDIO_CHUNK_LENGTH_SECONDS", DEFAULT_OPENAI_CHUNK_LENGTH_SECONDS)),
                step=30.0,
                help="可手動調整。建議先用 180 秒；若逐字稿仍漏很多股票，可試 120 秒。",
            )
            if openai_chunk_length_seconds <= 180:
                st.info("目前 chunk 設定偏保守，適合台股影片這種專有名詞密集的內容。")
            else:
                st.warning("chunk 超過 180 秒時，長段內容較容易漏掉細節；若發現股票缺漏，先改回 120 或 180 秒。")
            openai_transcription_prompt = st.text_area(
                "OpenAI transcription prompt",
                value=os.getenv("OPENAI_AUDIO_TRANSCRIPTION_PROMPT", ""),
                height=90,
                help="這裡只提示 ASR 可能出現的詞彙，讓逐字稿更準；股票代碼查核會由 #58 的腳本處理。",
            )
            if openai_transcription_prompt.strip():
                st.info("這段 prompt 會送進 OpenAI transcription API，用來降低台股專有詞誤聽。它不會驗證股票代碼。")
            else:
                st.warning("目前沒有 ASR prompt；#59 詞彙表完成前，可先手動貼常見公司名、代碼與產業詞。")
            openvino_model_dir = st.text_input(
                "OpenVINO model dir",
                value=str(browser_asr_settings["openvino_model_dir"]),
            )
            openvino_device = st.text_input("OpenVINO device", value=str(browser_asr_settings["openvino_device"]))
            language = st.text_input("語言", value=str(browser_asr_settings["language"]))

        if transcription_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            st.warning("尚未設定 OPENAI_API_KEY；OpenAI 轉錄會失敗。")

        transcribe_submitted = st.form_submit_button("產生逐字稿", type="primary")

    if transcribe_submitted:
        if not browser_page_url.strip():
            st.error("請先輸入影片 URL。")
        else:
            try:
                browser_asr_result = run_browser_session_asr_pipeline(
                    build_browser_asr_input(
                        page_url=browser_page_url,
                        output_stem=output_stem,
                        title=browser_title,
                        asr_provider=transcription_provider,
                        chrome_user_data_dir=chrome_user_data_dir,
                        chrome_binary_path=chrome_binary_path,
                        chromedriver_path=chromedriver_path,
                        headless=headless,
                        settle_seconds=float(settle_seconds),
                        playback_wait_seconds=float(playback_wait_seconds),
                        yt_dlp_cookies_from_browser=yt_dlp_cookies_from_browser,
                        yt_dlp_remote_components=yt_dlp_remote_components,
                        yt_dlp_download_page_url=yt_dlp_download_page_url,
                        openvino_model_dir=openvino_model_dir,
                        openvino_device=openvino_device,
                        openai_transcription_model=openai_transcription_model,
                        openai_transcription_prompt=openai_transcription_prompt,
                        openai_chunk_length_seconds=float(openai_chunk_length_seconds),
                        language=language,
                    )
                )
            except Exception as error:  # noqa: BLE001 - Streamlit page should show recoverable pipeline errors.
                st.error(str(error))
            else:
                _render_browser_asr_status(browser_asr_result)
                _store_transcript_result(browser_asr_result, browser_page_url)

    if transcribe_submitted and "browser_asr_result" in locals() and not browser_asr_result.is_available():
        media_candidates = _existing_media_candidates(output_stem)
        if media_candidates:
            st.warning("偵測到同名媒體檔，無須重新下載即可接續 WAV 與 ASR。")
            selected_media_path = st.selectbox(
                "使用既有媒體檔",
                media_candidates,
                format_func=str,
                key="research_existing_media_path",
            )
            if st.button("使用既有媒體繼續轉錄", icon=":material/play_arrow:", key="resume_existing_media"):
                with st.spinner("從既有媒體轉檔並產生逐字稿…"):
                    resumed_result = run_existing_media_asr_pipeline(
                        build_browser_asr_input(
                            page_url=browser_page_url,
                            output_stem=output_stem,
                            title=browser_title,
                            asr_provider=transcription_provider,
                            chrome_user_data_dir=chrome_user_data_dir,
                            chrome_binary_path=chrome_binary_path,
                            chromedriver_path=chromedriver_path,
                            headless=headless,
                            settle_seconds=float(settle_seconds),
                            playback_wait_seconds=float(playback_wait_seconds),
                            yt_dlp_cookies_from_browser=yt_dlp_cookies_from_browser,
                            yt_dlp_remote_components=yt_dlp_remote_components,
                            yt_dlp_download_page_url=yt_dlp_download_page_url,
                            openvino_model_dir=openvino_model_dir,
                            openvino_device=openvino_device,
                            openai_transcription_model=openai_transcription_model,
                            openai_transcription_prompt=openai_transcription_prompt,
                            openai_chunk_length_seconds=float(openai_chunk_length_seconds),
                            language=language,
                        ),
                        selected_media_path,
                    )
                _render_browser_asr_status(resumed_result)
                _store_transcript_result(resumed_result, browser_page_url)

    st.markdown("### 2. 產生研究報告")
    default_input_label = _selected_input_label_from_transcript(st.session_state["research_asr_transcript_json_path"])
    input_label = st.segmented_control("來源類型", tuple(INPUT_KIND_OPTIONS), default=default_input_label)
    input_kind = _option_value(INPUT_KIND_OPTIONS, input_label, default_input_label)

    title = st.text_input("標題", value="")
    publisher = st.text_input("發布者／頻道／機構", value="")
    speaker = st.text_input("主要講者", value="")
    notes = st.text_area("備註", value="", height=80)

    youtube_url = ""
    pdf_path = None
    transcript_json_path = None
    manual_text = ""
    source_url = ""
    if input_kind == "youtube_public":
        youtube_url = st.text_input("公開 YouTube URL", value="")
        manual_text = st.text_area("手動逐字稿或摘要 fallback", value="", height=220)
    elif input_kind == "asr_transcript_json":
        transcript_json_value = st.text_input(
            "ASR 逐字稿 JSON 路徑",
            value=st.session_state["research_asr_transcript_json_path"],
            placeholder=r"data\processed\asr-transcripts\openvino\manual-verify-001-asr.json",
        )
        transcript_json_path = Path(transcript_json_value) if transcript_json_value.strip() else None
        source_url = st.text_input("原始影片 URL", value=st.session_state["research_asr_source_url"])
    elif input_kind == "pdf":
        pdf_value = st.text_input("PDF 路徑", value="")
        pdf_path = Path(pdf_value) if pdf_value.strip() else None
    else:
        manual_text = st.text_area("手動文字／逐字稿", value="", height=260)
        source_url = st.text_input("來源 URL", value="")

    st.markdown("### 彙整方式")
    report_style_label = st.segmented_control(
        "報告類型",
        tuple(REPORT_STYLE_OPTIONS),
        default="固定研究報告（可做多來源統計）",
        help="固定研究報告給多來源統計；投資情報摘要給單支影片閱讀，不混用。",
    )
    report_style = _option_value(REPORT_STYLE_OPTIONS, report_style_label, "固定研究報告（可做多來源統計）")
    if report_style == "structured_report":
        st.info("固定研究報告會保留結構化欄位，方便之後做來源次數、族群熱度與講者態度統計。")
    else:
        st.info("投資情報摘要可以包含主流股基期防守表，但不應拿來直接做多來源次數統計。")
    verify_stock_mentions = False
    stock_repository = TaiwanStockRepository(sqlite_database_path())
    local_stock_directory = stock_repository.load_directory()
    if report_style == "structured_report":
        verify_stock_mentions = st.checkbox(
            "使用本機公司清單查核股票代號與公司名稱",
            value=True,
            help="報告只讀取本機 SQLite；同步按鈕才會連線官方來源更新資料。",
        )
        with st.container(border=True):
            st.markdown("#### 台股公司清單")
            if st.button("同步官方上市／上櫃公司清單", icon=":material/sync:"):
                with st.spinner("同步官方公司清單到本機 SQLite…"):
                    sync_result = sync_taiwan_stock_directory(
                        client=MopsCompanyDirectoryClient(),
                        repository=stock_repository,
                    )
                local_stock_directory = sync_result.directory
                if sync_result.status == "success":
                    st.success(sync_result.status_message)
                else:
                    st.warning(f"{sync_result.status_message} {sync_result.error}")
            latest_sync = stock_repository.latest_sync(status="success")
            if local_stock_directory is None:
                st.warning("本機尚無上市／上櫃公司清單；請先同步，否則本次報告不做股票身分查核。")
            else:
                st.write(f"本機可用公司：{len(local_stock_directory.companies)} 筆")
                if latest_sync is not None:
                    st.caption(f"最後成功同步（UTC）：{latest_sync.completed_at}")
                    if latest_sync.is_stale():
                        st.warning("本機公司清單已超過一天未更新，建議先同步再產生研究報告。")
    analysis_label = st.segmented_control(
        "研究彙整 provider",
        tuple(ANALYSIS_PROVIDER_OPTIONS),
        default="本機規則 fallback",
    )
    analysis_provider = _option_value(ANALYSIS_PROVIDER_OPTIONS, analysis_label, "本機規則 fallback")
    default_model = "rule_based_v1"
    if analysis_provider == "openai":
        default_model = os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini")
    elif analysis_provider == "anthropic_claude":
        default_model = ""
    analysis_model = st.text_input("模型／版本", value=default_model)
    if analysis_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        st.warning("尚未設定 OPENAI_API_KEY；本次會改用本機規則 fallback。")
    if report_style == "investment_brief" and analysis_provider != "openai":
        st.warning("投資情報摘要目前只由 OpenAI provider 產生；其他 provider 會回到固定研究報告。")
    if analysis_provider == "anthropic_claude":
        st.warning("Claude provider 還沒有接上真實 API；本次會明確標示未支援並改用本機規則 fallback。")

    st.markdown("### 輸出目的地")
    write_to_obsidian = st.checkbox("輸出到 Obsidian inbox", value=True)
    write_to_custom = st.checkbox("輸出到自選路徑", value=True)
    obsidian_path = st.text_input("Obsidian inbox 路徑", value=str(DEFAULT_OBSIDIAN_INBOX_PATH))
    custom_path = st.text_input("自選輸出路徑", value=str(Path.home() / "Desktop"))

    output_settings = ResearchReportOutputSettings(
        write_to_obsidian_inbox=write_to_obsidian,
        write_to_custom_path=write_to_custom,
        obsidian_inbox_path=Path(obsidian_path),
        custom_output_path=Path(custom_path) if custom_path.strip() else None,
    )

    if st.button("產生研究報告", type="primary"):
        stock_directory = stock_repository.load_directory() if verify_stock_mentions else None
        try:
            result = run_phase_one_research_source_analysis(
                PhaseOneResearchInput(
                    input_kind=input_kind,  # type: ignore[arg-type]
                    title=title,
                    manual_text=manual_text,
                    youtube_url=youtube_url,
                    pdf_path=pdf_path,
                    transcript_json_path=transcript_json_path,
                    source_url=source_url,
                    publisher=publisher,
                    speaker=speaker,
                    notes=notes,
                ),
                output_settings=output_settings,
                analysis_settings=ResearchAnalysisSettings(
                    provider=analysis_provider,  # type: ignore[arg-type]
                    model=analysis_model,
                    report_style=report_style,  # type: ignore[arg-type]
                ),
                youtube_client=_advanced_youtube_caption_client(title, publisher) if input_kind == "youtube_public" else None,
                stock_directory=stock_directory,
            )
        except Exception as error:  # noqa: BLE001 - Streamlit page should show recoverable user input errors.
            st.error(str(error))
            return

        for status in result.statuses:
            if "transcript_unavailable" in status or "未取得" in status or "未抽取" in status or "尚未接上" in status:
                st.warning(status)
            else:
                st.info(status)
        with st.container(border=True):
            st.write(f"彙整 provider：{result.analysis_result.provider}")
            st.write(f"彙整狀態：{result.analysis_result.status}")
            if result.analysis_result.model:
                st.write(f"模型／版本：{result.analysis_result.model}")
        if result.written_outputs:
            for item in result.written_outputs:
                st.success(f"{item.kind}：{item.path}")
        st.markdown("### 研究報告 Markdown")
        st.text_area(
            "研究報告 Markdown",
            value=_research_report_preview_markdown(result.markdown),
            height=520,
        )
        st.download_button(
            "下載 Markdown",
            data=result.markdown.encode("utf-8"),
            file_name=build_research_report_filename(result.report),
            mime="text/markdown",
        )


def _advanced_youtube_caption_client(title: str, publisher: str) -> AvailableYouTubeCaptionClient:
    settings = get_default_browser_asr_settings()
    return AvailableYouTubeCaptionClient(
        title=title, channel=publisher,
        browser_config=SeleniumBrowserSessionConfig(
            chrome_user_data_dir=Path(str(settings["chrome_user_data_dir"])),
            chrome_binary_path=Path(str(settings["chrome_binary_path"])),
            chromedriver_path=Path(str(settings["chromedriver_path"])),
            headless=bool(settings["headless"]),
            settle_seconds=float(settings["settle_seconds"]),
        ),
    )
