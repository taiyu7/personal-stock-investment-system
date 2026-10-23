import subprocess
from pathlib import Path

from personal_stock_investment_system.research.youtube_captions import (
    fetch_youtube_captions, fetch_youtube_captions_in_browser, parse_webvtt,
)


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
    def runner(command, **kwargs):
        assert "--skip-download" in command
        assert "--write-auto-subs" in command
        output = Path(command[command.index("--output") + 1])
        output.parent.joinpath("caption.en.vtt").write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nEnglish\n", encoding="utf-8"
        )
        output.parent.joinpath("caption.zh-TW.vtt").write_text(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n中文\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    result = fetch_youtube_captions("https://www.youtube.com/watch?v=dQw4w9WgXcQ", work_dir=tmp_path, runner=runner)
    assert result.language == "zh-TW"
    assert [segment.text for segment in result.segments] == ["中文"]


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
            return [{"baseUrl": "https://www.youtube.com/api/timedtext?v=OH9SPy88MLk", "languageCode": "zh-TW"}]

        def execute_async_script(self, script, url):
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
