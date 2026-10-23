import json
import subprocess
from pathlib import Path

from personal_stock_investment_system.research.youtube_captions import (
    CaptionFetchResult, fetch_youtube_captions, fetch_youtube_captions_in_browser,
    parse_webvtt, save_caption_transcript,
)
from personal_stock_investment_system.research.asr import AsrTranscriptSegment


def test_parse_webvtt_keeps_timestamps_and_removes_duplicate_cue():
    content = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>台積電 2330</c>

00:00:03.000 --> 00:00:04.000
台積電 2330

00:00:04.000 --> 00:00:06.000
需求成長
"""
    segments = parse_webvtt(content)
    assert [(item.text, item.start_seconds) for item in segments] == [
        ("台積電 2330", 1.0), ("需求成長", 4.0)
    ]


def test_fetch_prefers_traditional_chinese_caption_without_video_download(tmp_path):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        assert "--skip-download" in command
        if "--dump-single-json" in command:
            return subprocess.CompletedProcess(
                command, 0,
                json.dumps({
                    "subtitles": {"zh-TW": [{"ext": "vtt"}]},
                    "automatic_captions": {"zh-TW": [{"ext": "vtt"}], "en": [{"ext": "vtt"}]},
                }), "",
            )
        assert "--write-auto-subs" in command
        assert command[command.index("--sub-langs") + 1] == "zh-TW"
        output = Path(command[command.index("--output") + 1])
        output.parent.joinpath("caption.zh-TW.vtt").write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n中文\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = fetch_youtube_captions("https://www.youtube.com/watch?v=dQw4w9WgXcQ", work_dir=tmp_path, runner=runner)
    assert result.language == "zh-TW"
    assert [segment.text for segment in result.segments] == ["中文"]
    assert len(commands) == 2


def test_fetch_ignores_other_languages_when_supported_chinese_is_absent(tmp_path):
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command, 0,
            json.dumps({"subtitles": {"zh-Hant": [{"ext": "vtt"}]},
                        "automatic_captions": {"en-orig": [{"ext": "vtt"}]}}), "",
        )

    result = fetch_youtube_captions("https://www.youtube.com/watch?v=dQw4w9WgXcQ", work_dir=tmp_path, runner=runner)
    assert not result.segments
    assert "zh-TW" in result.error
    assert len(commands) == 1


def test_fetch_uses_simplified_after_traditional_track_fails_and_converts_it(tmp_path):
    requested = []

    def runner(command, **kwargs):
        if "--dump-single-json" in command:
            return subprocess.CompletedProcess(
                command, 0,
                json.dumps({"subtitles": {
                    "zh-TW": [{"ext": "vtt"}], "zh-Hans": [{"ext": "vtt"}],
                }, "automatic_captions": {"en": [{"ext": "vtt"}]}}), "",
            )
        language = command[command.index("--sub-langs") + 1]
        requested.append(language)
        if language == "zh-TW":
            return subprocess.CompletedProcess(command, 1, "", "HTTP Error 429")
        output = Path(command[command.index("--output") + 1])
        output.parent.joinpath("caption.zh-Hans.vtt").write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n汉字经济\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = fetch_youtube_captions("https://www.youtube.com/watch?v=dQw4w9WgXcQ", work_dir=tmp_path, runner=runner)
    assert requested == ["zh-TW", "zh-Hans"]
    assert result.language == "zh-Hans"
    assert result.converted_to_traditional
    assert result.segments[0].text == "漢字經濟"


def test_caption_failure_explains_why_asr_fallback_runs(tmp_path):
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "Failed to resolve 'www.youtube.com'")

    result = fetch_youtube_captions("https://www.youtube.com/watch?v=dQw4w9WgXcQ", work_dir=tmp_path, runner=runner)
    assert not result.segments
    assert "DNS" in result.error


def test_browser_can_read_existing_youtube_caption_track():
    class FakeDriver:
        def set_page_load_timeout(self, seconds):
            pass

        def get(self, url):
            assert "OH9SPy88MLk" in url

        def execute_script(self, script):
            return [
                {"baseUrl": "https://www.youtube.com/api/timedtext?lang=en", "languageCode": "en"},
                {"baseUrl": "https://www.youtube.com/api/timedtext?lang=zh-Hans", "languageCode": "zh-Hans"},
                {"baseUrl": "https://www.youtube.com/api/timedtext?lang=zh-TW", "languageCode": "zh-TW"},
            ]

        def execute_async_script(self, script, url):
            assert "lang=zh-TW" in url
            return "WEBVTT\n\n00:00:12.000 --> 00:00:14.000\n現成字幕\n"

        def quit(self):
            self.closed = True

    driver = FakeDriver()
    result = fetch_youtube_captions_in_browser(
        "https://www.youtube.com/watch?v=OH9SPy88MLk", None,
        driver_factory=lambda config: driver,
    )
    assert result.language == "zh-TW"
    assert result.segments[0].start_seconds == 12.0
    assert driver.closed


def test_browser_converts_simplified_caption_to_traditional():
    class FakeDriver:
        def set_page_load_timeout(self, seconds):
            pass

        def get(self, url):
            pass

        def execute_script(self, script):
            return [{"baseUrl": "https://www.youtube.com/api/timedtext?lang=zh-CN", "languageCode": "zh-CN"}]

        def execute_async_script(self, script, url):
            return "WEBVTT\n\n00:00:12.000 --> 00:00:14.000\n汉字经济\n"

        def quit(self):
            pass

    result = fetch_youtube_captions_in_browser(
        "https://www.youtube.com/watch?v=OH9SPy88MLk", None,
        driver_factory=lambda config: FakeDriver(),
    )
    assert result.language == "zh-CN"
    assert result.converted_to_traditional
    assert result.segments[0].text == "漢字經濟"


def test_browser_does_not_fetch_non_chinese_caption_languages():
    class FakeDriver:
        def set_page_load_timeout(self, seconds):
            pass

        def get(self, url):
            pass

        def execute_script(self, script):
            return [{"baseUrl": "https://www.youtube.com/api/timedtext?lang=en", "languageCode": "en"}]

        def execute_async_script(self, script, url):
            raise AssertionError("不應下載英文字幕")

        def quit(self):
            pass

    result = fetch_youtube_captions_in_browser(
        "https://www.youtube.com/watch?v=OH9SPy88MLk", None,
        driver_factory=lambda config: FakeDriver(),
    )
    assert not result.segments
    assert not result.track_found
    assert "zh-TW" in result.error


def test_saved_transcript_records_simplified_source_and_conversion(tmp_path):
    result = CaptionFetchResult(
        (AsrTranscriptSegment("漢字經濟", 1.0, 2.0),),
        language="zh-Hans", track_found=True, converted_to_traditional=True,
    )
    saved = save_caption_transcript(result, tmp_path / "captions.json")
    payload = json.loads(saved.transcript_path.read_text(encoding="utf-8"))
    assert payload["language"] == "zh-Hans"
    assert payload["converted_to_traditional"] is True
    assert payload["segments"][0]["text"] == "漢字經濟"
    assert "zh-Hans→繁體中文" in saved.status_message
