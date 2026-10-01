import json
from pathlib import Path

from personal_stock_investment_system.research import (
    ScreenshotArtifact,
    ScreenshotCaptureResult,
    ScreenshotRequest,
    SourceReference,
)
from personal_stock_investment_system.research.vlm import (
    ChartObservation,
    FakeVisionLanguageModelClient,
    OpenAIVisionLanguageModelClient,
    ScreenshotAnalysisInput,
    StockIdentityCandidate,
    VlmChartAnalysisResult,
    VlmChartAnalysisSettings,
    analyze_screenshot_capture,
)


class FakeResponses:
    def __init__(self, output_text: str = "", error: Exception | None = None):
        self.output_text = output_text
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return type("Response", (), {"output_text": self.output_text})()


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


def _capture(tmp_path: Path, *, status="available") -> ScreenshotCaptureResult:
    reference = SourceReference(
        source_id="video-1",
        locator_type="timestamp",
        locator="00:01:23",
        quote="這根 K 突破壓力。",
    )
    request = ScreenshotRequest(
        timestamp_seconds=83.25,
        reason="確認 K 線與成交量",
        quote=reference.quote,
        reference=reference,
    )
    artifact = None
    if status == "available":
        path = tmp_path / "frame.jpg"
        path.write_bytes(b"fake jpeg bytes")
        artifact = ScreenshotArtifact(
            path=path,
            timestamp_seconds=request.timestamp_seconds,
            reason=request.reason,
            quote=request.quote,
            reference=reference,
        )
    return ScreenshotCaptureResult(status=status, request=request, artifact=artifact)


def test_fake_vlm_preserves_traceability_and_does_not_verify_stock_identity(tmp_path):
    capture = _capture(tmp_path)
    expected = VlmChartAnalysisResult(
        screenshot_path=capture.artifact.path,
        timestamp_seconds=83.25,
        source_reference=capture.request.reference,
        provider="fake",
        model="fake-vlm-v1",
        prompt_version="technical_chart_v1",
        schema_version="1.0",
        status="needs_verification",
        is_technical_chart=True,
        chart_type="K 線圖",
        readability="中",
        observations=(
            ChartObservation(
                category="support_resistance",
                description="畫面上方有水平壓力線。",
                evidence="可見水平標記線",
                confidence="中",
                needs_verification=True,
                verification_reason="價位文字不清楚",
            ),
        ),
        stock_candidates=(StockIdentityCandidate(raw_code="2330", confidence="中"),),
    )
    client = FakeVisionLanguageModelClient(expected)

    result = analyze_screenshot_capture(
        capture,
        settings=VlmChartAnalysisSettings(provider="fake", model="fake-vlm-v1"),
        client=client,
    )

    assert result == expected
    assert result.source_reference == capture.request.reference
    assert result.stock_candidates[0].needs_verification is True
    assert len(client.calls) == 1


def test_fake_vlm_supports_all_in_scope_observation_categories(tmp_path):
    capture = _capture(tmp_path)
    categories = (
        "candlestick",
        "moving_average",
        "volume",
        "support_resistance",
        "pattern",
        "speaker_pointer",
    )
    expected = VlmChartAnalysisResult(
        screenshot_path=capture.artifact.path,
        timestamp_seconds=capture.artifact.timestamp_seconds,
        source_reference=capture.request.reference,
        provider="fake",
        model="fake-vlm-v1",
        prompt_version="technical_chart_v1",
        schema_version="1.0",
        status="needs_verification",
        is_technical_chart=True,
        chart_type="K 線圖",
        readability="中",
        observations=tuple(
            ChartObservation(
                category=category,
                description=f"fake {category} observation",
                evidence="測試資料，不代表真實判讀。",
                confidence="中",
                needs_verification=True,
                verification_reason="尚未以真實 K 線圖人工驗收",
            )
            for category in categories
        ),
    )

    result = analyze_screenshot_capture(
        capture,
        settings=VlmChartAnalysisSettings(provider="fake", model="fake-vlm-v1"),
        client=FakeVisionLanguageModelClient(expected),
    )

    assert tuple(item.category for item in result.observations) == categories
    assert all(item.needs_verification for item in result.observations)


def test_capture_unavailable_does_not_call_vlm(tmp_path):
    capture = _capture(tmp_path, status="capture_unavailable")
    client = FakeVisionLanguageModelClient(
        VlmChartAnalysisResult(
            screenshot_path=Path(),
            timestamp_seconds=0,
            source_reference=None,
            provider="fake",
            model="",
            prompt_version="technical_chart_v1",
            schema_version="1.0",
            status="available",
        )
    )

    result = analyze_screenshot_capture(
        capture,
        settings=VlmChartAnalysisSettings(provider="fake", model="fake-vlm-v1"),
        client=client,
    )

    assert result.status == "input_unavailable"
    assert result.error == "capture_unavailable"
    assert client.calls == []


def test_missing_screenshot_file_does_not_call_vlm(tmp_path):
    capture = _capture(tmp_path)
    capture.artifact.path.unlink()
    client = FakeVisionLanguageModelClient(
        VlmChartAnalysisResult(
            screenshot_path=Path(),
            timestamp_seconds=0,
            source_reference=None,
            provider="fake",
            model="",
            prompt_version="technical_chart_v1",
            schema_version="1.0",
            status="available",
        )
    )

    result = analyze_screenshot_capture(capture, settings=VlmChartAnalysisSettings(provider="fake"), client=client)

    assert result.status == "input_unavailable"
    assert client.calls == []


def test_local_provider_is_explicitly_unsupported_without_runtime(tmp_path):
    result = analyze_screenshot_capture(
        _capture(tmp_path),
        settings=VlmChartAnalysisSettings(provider="local", model="local-placeholder"),
    )

    assert result.status == "unsupported_provider"
    assert result.error == "local_vlm_not_configured"


def test_openai_vlm_builds_image_request_and_parses_schema(tmp_path):
    capture = _capture(tmp_path)
    payload = {
        "status": "needs_verification",
        "is_technical_chart": True,
        "chart_type": "K 線圖",
        "readability": "中",
        "observations": [
            {
                "category": "moving_average",
                "description": "價格位於可見均線上方。",
                "evidence": "K 棒在均線上方",
                "confidence": "中",
                "needs_verification": True,
                "verification_reason": "均線週期標籤不清楚",
            }
        ],
        "stock_candidates": [
            {
                "raw_code": "2330",
                "raw_company_name": "台積電",
                "confidence": "中",
                "needs_verification": True,
            }
        ],
        "status_message": "圖面可部分判讀。",
    }
    responses = FakeResponses(json.dumps(payload, ensure_ascii=False))
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision", timeout_seconds=12)
    client = OpenAIVisionLanguageModelClient(settings, api_key="test-key", client=FakeOpenAIClient(responses))

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "needs_verification"
    assert result.provider == "openai"
    assert result.observations[0].category == "moving_average"
    assert result.stock_candidates[0].needs_verification is True
    assert responses.kwargs["model"] == "gpt-test-vision"
    assert responses.kwargs["timeout"] == 12
    content = responses.kwargs["input"][0]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert "deterministic verifier" in responses.kwargs["instructions"]


def test_openai_vlm_invalid_json_returns_analysis_failed(tmp_path):
    capture = _capture(tmp_path)
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")
    client = OpenAIVisionLanguageModelClient(
        settings,
        api_key="test-key",
        client=FakeOpenAIClient(FakeResponses("not-json")),
    )

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "analysis_failed"
    assert result.observations == ()
    assert result.error


def test_openai_vlm_provider_error_returns_analysis_failed(tmp_path):
    capture = _capture(tmp_path)
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")
    client = OpenAIVisionLanguageModelClient(
        settings,
        api_key="test-key",
        client=FakeOpenAIClient(FakeResponses(error=RuntimeError("provider unavailable"))),
    )

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "analysis_failed"
    assert result.status_message == "OpenAI VLM 圖面分析失敗，未產生推測結果。"
    assert result.error == "provider unavailable"


def test_openai_vlm_unknown_enum_does_not_guess(tmp_path):
    capture = _capture(tmp_path)
    payload = {
        "status": "probably_a_chart",
        "is_technical_chart": True,
        "chart_type": "K 線圖",
        "readability": "中",
        "observations": [],
        "stock_candidates": [],
        "status_message": "",
    }
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")
    client = OpenAIVisionLanguageModelClient(
        settings,
        api_key="test-key",
        client=FakeOpenAIClient(FakeResponses(json.dumps(payload, ensure_ascii=False))),
    )

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "analysis_failed"
    assert "unsupported value" in result.error


def test_openai_vlm_low_readability_is_forced_to_needs_verification(tmp_path):
    capture = _capture(tmp_path)
    payload = {
        "status": "available",
        "is_technical_chart": True,
        "chart_type": "未判定",
        "readability": "低",
        "observations": [],
        "stock_candidates": [],
        "status_message": "畫面模糊。",
    }
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")
    client = OpenAIVisionLanguageModelClient(
        settings,
        api_key="test-key",
        client=FakeOpenAIClient(FakeResponses(json.dumps(payload, ensure_ascii=False))),
    )

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "needs_verification"
    assert result.readability == "低"


def test_openai_vlm_empty_or_missing_schema_fields_fail_closed(tmp_path):
    capture = _capture(tmp_path)
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")

    for output_text in ("", json.dumps({"status": "available"})):
        client = OpenAIVisionLanguageModelClient(
            settings,
            api_key="test-key",
            client=FakeOpenAIClient(FakeResponses(output_text)),
        )

        result = analyze_screenshot_capture(capture, settings=settings, client=client)

        assert result.status == "analysis_failed"
        assert result.observations == ()


def test_openai_vlm_timeout_returns_analysis_failed(tmp_path):
    capture = _capture(tmp_path)
    settings = VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision")
    client = OpenAIVisionLanguageModelClient(
        settings,
        api_key="test-key",
        client=FakeOpenAIClient(FakeResponses(error=TimeoutError("request timed out"))),
    )

    result = analyze_screenshot_capture(capture, settings=settings, client=client)

    assert result.status == "analysis_failed"
    assert result.error == "request timed out"


def test_openai_vlm_missing_key_does_not_call_api(tmp_path):
    capture = _capture(tmp_path)
    result = OpenAIVisionLanguageModelClient(
        VlmChartAnalysisSettings(provider="openai", model="gpt-test-vision"),
        api_key="",
    ).analyze(ScreenshotAnalysisInput(artifact=capture.artifact))

    assert result.status == "analysis_failed"
    assert result.error == "missing_openai_api_key"
