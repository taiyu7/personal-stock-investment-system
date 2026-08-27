import pandas as pd

from apps.dashboard.components import layout
from apps.dashboard.components.layout import SIDEBAR_PAGES
from apps.dashboard.components.market_cards import get_recent_trading_rows
from pathlib import Path

from apps.dashboard.views.research_source_analysis import (
    ANALYSIS_PROVIDER_OPTIONS,
    INPUT_KIND_OPTIONS,
    TRANSCRIPTION_PROVIDER_OPTIONS,
    _is_available_status,
    _option_value,
    build_browser_asr_input,
)


def test_recent_rows_calculates_change_from_previous_close():
    dates = pd.date_range("2026-08-01", periods=6, freq="D")
    history = pd.DataFrame(
        {
            "Open": [100, 101, 102, 103, 104, 105],
            "High": [102, 103, 104, 105, 106, 108],
            "Low": [99, 100, 101, 102, 103, 104],
            "Close": [101, 102, 103, 104, 105, 107],
        },
        index=dates,
    )

    rows = get_recent_trading_rows(history)

    assert len(rows) == 5
    assert rows.iloc[-1]["相對前日漲跌"] == 2
    assert rows.iloc[-1]["相對前日漲跌幅"] == 2 / 105 * 100


def test_recent_rows_returns_empty_when_required_price_columns_are_missing():
    history = pd.DataFrame({"Close": [100.0, 101.0]})

    rows = get_recent_trading_rows(history)

    assert rows.empty


def test_research_source_analysis_is_available_from_sidebar_navigation():
    assert "研究來源分析" in SIDEBAR_PAGES
    assert SIDEBAR_PAGES.index("研究來源分析") == 1


def test_sidebar_uses_session_page_for_active_button(monkeypatch):
    rendered_buttons = []

    class FakeSessionState(dict):
        def __getattr__(self, key):
            return self[key]

        def __setattr__(self, key, value):
            self[key] = value

    class FakeSidebar:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_button(label, *, key, type, width, on_click, args):
        rendered_buttons.append((label, type))
        if label == "研究來源分析":
            on_click(*args)
        return False

    monkeypatch.setattr(layout.st, "sidebar", FakeSidebar())
    monkeypatch.setattr(layout.st, "button", fake_button)
    monkeypatch.setattr(layout.st, "session_state", FakeSessionState(current_page="研究來源分析"))

    selected_page = layout.render_sidebar("市場交易儀表板")

    assert selected_page == "研究來源分析"
    assert ("研究來源分析", "primary") in rendered_buttons
    assert ("市場交易儀表板", "secondary") in rendered_buttons


def test_research_source_analysis_supports_transcript_json_and_provider_choice():
    assert INPUT_KIND_OPTIONS["ASR 逐字稿 JSON"] == "asr_transcript_json"
    assert ANALYSIS_PROVIDER_OPTIONS["本機規則 fallback"] == "rule_based_fallback"
    assert ANALYSIS_PROVIDER_OPTIONS["OpenAI"] == "openai"
    assert ANALYSIS_PROVIDER_OPTIONS["Claude（尚未接 API）"] == "anthropic_claude"


def test_research_source_analysis_supports_browser_asr_provider_choice():
    assert TRANSCRIPTION_PROVIDER_OPTIONS["只產生 WAV"] == "none"
    assert TRANSCRIPTION_PROVIDER_OPTIONS["OpenAI"] == "openai"
    assert TRANSCRIPTION_PROVIDER_OPTIONS["OpenVINO"] == "openvino"


def test_research_source_analysis_checks_asr_status_without_import_result_helper():
    assert _is_available_status("available") is True
    assert _is_available_status("transcript_unavailable") is False


def test_research_source_analysis_falls_back_when_segmented_control_returns_none():
    assert _option_value(TRANSCRIPTION_PROVIDER_OPTIONS, None, "OpenAI") == "openai"
    assert _option_value(INPUT_KIND_OPTIONS, None, "手動文字／逐字稿") == "manual_text"
    assert _option_value(ANALYSIS_PROVIDER_OPTIONS, "OpenAI", "本機規則 fallback") == "openai"


def test_research_source_analysis_builds_browser_asr_input_from_ui_values():
    source_input = build_browser_asr_input(
        page_url=" https://www.youtube.com/watch?v=qAv7WTF-yY8 ",
        output_stem=" manual-verify-060 ",
        title=" 測試影片 ",
        asr_provider="openai",
        chrome_user_data_dir=r"data\local\psis-browser-asr-debug-profile",
        chrome_binary_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        chromedriver_path=r"data\local\chromedriver\chromedriver-win64\chromedriver.exe",
        headless=True,
        settle_seconds=3.0,
        playback_wait_seconds=20.0,
        yt_dlp_cookies_from_browser=r" chrome:C:\Users\taiyu\AppData\Local\psis-browser-asr-profile\Default ",
        yt_dlp_remote_components=" ejs:github ",
        yt_dlp_download_page_url=True,
        openvino_model_dir=r"data\local\openvino\breeze-asr-25-fp32",
        openvino_device=" GPU ",
        openai_transcription_model=" gpt-4o-mini-transcribe ",
        openai_transcription_prompt=" 台股詞彙：台積電、CPO、瀚荃。 ",
        openai_chunk_length_seconds=180.0,
        language=" zh ",
    )

    assert source_input.page_url == "https://www.youtube.com/watch?v=qAv7WTF-yY8"
    assert source_input.output_stem == "manual-verify-060"
    assert source_input.title == "測試影片"
    assert source_input.asr_provider == "openai"
    assert source_input.chrome_user_data_dir == Path(r"data\local\psis-browser-asr-debug-profile")
    assert source_input.headless is True
    assert source_input.ytdlp_cookies_from_browser == r"chrome:C:\Users\taiyu\AppData\Local\psis-browser-asr-profile\Default"
    assert source_input.ytdlp_remote_components == "ejs:github"
    assert source_input.ytdlp_download_page_url is True
    assert source_input.openvino_model_dir == Path(r"data\local\openvino\breeze-asr-25-fp32")
    assert source_input.openvino_device == "GPU"
    assert source_input.openai_transcription_model == "gpt-4o-mini-transcribe"
    assert source_input.openai_transcription_prompt == "台股詞彙：台積電、CPO、瀚荃。"
    assert source_input.openai_chunk_length_seconds == 180.0
    assert source_input.language == "zh"
