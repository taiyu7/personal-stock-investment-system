from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from personal_stock_investment_system.research import (
    BrowserSessionAsrInput,
    BrowserSessionAsrResult,
    DEFAULT_OBSIDIAN_INBOX_PATH,
    DEFAULT_OPENAI_TRANSCRIPTION_MODEL,
    PhaseOneResearchInput,
    ResearchAnalysisSettings,
    ResearchReportOutputSettings,
    build_research_report_filename,
    run_browser_session_asr_pipeline,
    run_phase_one_research_source_analysis,
)


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


def get_default_browser_asr_settings() -> dict[str, str | float]:
    return WINDOWS_BROWSER_ASR_SETTINGS if os.name == "nt" else DEFAULT_BROWSER_ASR_SETTINGS


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
        language=language.strip() or "zh",
    )


def _selected_input_label_from_transcript(transcript_json_path: str) -> str:
    return "ASR 逐字稿 JSON" if transcript_json_path.strip() else "手動文字／逐字稿"


def _is_available_status(status: str) -> bool:
    return status == "available"


def _render_browser_asr_status(result: BrowserSessionAsrResult) -> None:
    if result.media_result.is_available():
        st.success("音檔已取得並轉成 16 kHz mono WAV。")
    else:
        st.error(result.media_result.status_message or "音檔取得失敗。")
    if result.media_result.artifact is not None:
            st.code(str(result.media_result.artifact.path), language=None)
    if result.transcription is not None:
        if _is_available_status(result.transcription.status):
            st.success("逐字稿已產生。")
        else:
            st.warning(result.transcription.status_message or "逐字稿尚未產生。")
        if result.transcription.transcript_path is not None:
            st.code(str(result.transcription.transcript_path), language=None)
        if result.transcription.error:
            st.error(result.transcription.error)


def render_research_source_analysis_page() -> None:
    st.subheader("研究來源分析")
    st.caption("輸入逐字稿、PDF 或公開影片來源，產生固定格式研究報告。")

    st.markdown("### 1. 取得逐字稿")
    st.caption("影片 URL 先轉成 ASR 逐字稿 JSON；成功後會自動帶到下一段。")
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
        )
        transcription_provider = TRANSCRIPTION_PROVIDER_OPTIONS[transcription_label]
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
            )
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
                        language=language,
                    )
                )
            except Exception as error:  # noqa: BLE001 - Streamlit page should show recoverable pipeline errors.
                st.error(str(error))
            else:
                _render_browser_asr_status(browser_asr_result)
                if (
                    browser_asr_result.transcription is not None
                    and browser_asr_result.transcription.transcript_path is not None
                ):
                    st.session_state["research_asr_transcript_json_path"] = str(
                        browser_asr_result.transcription.transcript_path
                    )
                    st.session_state["research_asr_source_url"] = browser_page_url.strip()

    st.markdown("### 2. 產生研究報告")
    default_input_label = _selected_input_label_from_transcript(st.session_state["research_asr_transcript_json_path"])
    input_label = st.segmented_control("來源類型", tuple(INPUT_KIND_OPTIONS), default=default_input_label)
    input_kind = INPUT_KIND_OPTIONS[input_label]

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
    analysis_label = st.segmented_control(
        "研究彙整 provider",
        tuple(ANALYSIS_PROVIDER_OPTIONS),
        default="本機規則 fallback",
    )
    analysis_provider = ANALYSIS_PROVIDER_OPTIONS[analysis_label]
    default_model = "rule_based_v1"
    if analysis_provider == "openai":
        default_model = os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini")
    elif analysis_provider == "anthropic_claude":
        default_model = ""
    analysis_model = st.text_input("模型／版本", value=default_model)
    if analysis_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        st.warning("尚未設定 OPENAI_API_KEY；本次會改用本機規則 fallback。")
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
                ),
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
        st.text_area("研究報告 Markdown", value=result.markdown, height=520)
        st.download_button(
            "下載 Markdown",
            data=result.markdown.encode("utf-8"),
            file_name=build_research_report_filename(result.report),
            mime="text/markdown",
        )
