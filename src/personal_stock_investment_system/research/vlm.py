"""Provider-neutral VLM analysis for timestamped technical-analysis screenshots."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from personal_stock_investment_system.research.screenshots import ScreenshotArtifact, ScreenshotCaptureResult
from personal_stock_investment_system.research.sources import SourceReference

VlmProviderName = Literal["fake", "openai", "local"]
VlmAnalysisStatus = Literal[
    "available",
    "needs_verification",
    "not_a_chart",
    "input_unavailable",
    "unsupported_provider",
    "analysis_failed",
]
ObservationCategory = Literal[
    "candlestick",
    "moving_average",
    "volume",
    "support_resistance",
    "pattern",
    "speaker_pointer",
    "other",
]
Confidence = Literal["高", "中", "低", "未判定"]

DEFAULT_OPENAI_VLM_MODEL = "gpt-4.1-mini"
DEFAULT_VLM_PROMPT_VERSION = "technical_chart_v1"
DEFAULT_VLM_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ScreenshotAnalysisInput:
    artifact: ScreenshotArtifact
    source_reference: SourceReference | None = None


@dataclass(frozen=True)
class ChartObservation:
    category: ObservationCategory
    description: str
    evidence: str = ""
    confidence: Confidence = "未判定"
    needs_verification: bool = True
    verification_reason: str = ""


@dataclass(frozen=True)
class StockIdentityCandidate:
    raw_code: str = ""
    raw_company_name: str = ""
    confidence: Confidence = "未判定"
    needs_verification: bool = True


@dataclass(frozen=True)
class VlmChartAnalysisSettings:
    provider: VlmProviderName = "fake"
    model: str = ""
    prompt_version: str = DEFAULT_VLM_PROMPT_VERSION
    schema_version: str = DEFAULT_VLM_SCHEMA_VERSION
    timeout_seconds: float = 60.0


@dataclass(frozen=True)
class VlmChartAnalysisResult:
    screenshot_path: Path
    timestamp_seconds: float
    source_reference: SourceReference | None
    provider: VlmProviderName
    model: str
    prompt_version: str
    schema_version: str
    status: VlmAnalysisStatus
    is_technical_chart: bool | None = None
    chart_type: str = "未判定"
    readability: Confidence = "未判定"
    observations: tuple[ChartObservation, ...] = ()
    stock_candidates: tuple[StockIdentityCandidate, ...] = ()
    analyzed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    status_message: str = ""
    error: str = ""

    def is_available(self) -> bool:
        return self.status in {"available", "needs_verification", "not_a_chart"}


class VisionLanguageModelClient(Protocol):
    def analyze(self, screenshot: ScreenshotAnalysisInput) -> VlmChartAnalysisResult:
        """Analyze one local screenshot without changing stock-verification truth."""


class OpenAIResponsesClient(Protocol):
    class Responses(Protocol):
        def create(self, **kwargs: object) -> object:
            """Create an OpenAI response."""

    responses: Responses


@dataclass
class FakeVisionLanguageModelClient:
    result: VlmChartAnalysisResult
    calls: list[ScreenshotAnalysisInput] = field(default_factory=list)

    def analyze(self, screenshot: ScreenshotAnalysisInput) -> VlmChartAnalysisResult:
        self.calls.append(screenshot)
        return self.result


class UnavailableLocalVisionLanguageModelClient:
    def __init__(self, settings: VlmChartAnalysisSettings) -> None:
        self.settings = settings

    def analyze(self, screenshot: ScreenshotAnalysisInput) -> VlmChartAnalysisResult:
        return _result_for_input(
            screenshot,
            settings=self.settings,
            status="unsupported_provider",
            status_message="本機 VLM adapter 尚未設定；請使用 fake 測試或 OpenAI provider。",
            error="local_vlm_not_configured",
        )


class OpenAIVisionLanguageModelClient:
    def __init__(
        self,
        settings: VlmChartAnalysisSettings | None = None,
        *,
        api_key: str | None = None,
        client: OpenAIResponsesClient | None = None,
    ) -> None:
        configured = settings or VlmChartAnalysisSettings(provider="openai")
        self.settings = VlmChartAnalysisSettings(
            provider="openai",
            model=configured.model or os.getenv("OPENAI_VLM_MODEL", DEFAULT_OPENAI_VLM_MODEL),
            prompt_version=configured.prompt_version,
            schema_version=configured.schema_version,
            timeout_seconds=configured.timeout_seconds,
        )
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self._client = client

    def analyze(self, screenshot: ScreenshotAnalysisInput) -> VlmChartAnalysisResult:
        if not self.api_key and self._client is None:
            return _result_for_input(
                screenshot,
                settings=self.settings,
                status="analysis_failed",
                status_message="缺少 OPENAI_API_KEY，未呼叫雲端 VLM。",
                error="missing_openai_api_key",
            )
        try:
            response = self._responses_client().responses.create(
                model=self.settings.model,
                instructions=_vlm_instructions(),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": _vlm_context(screenshot)},
                            {"type": "input_image", "image_url": _image_data_url(screenshot.artifact.path)},
                        ],
                    }
                ],
                text={"format": _vlm_response_format()},
                temperature=0.0,
                timeout=self.settings.timeout_seconds,
            )
            payload = json.loads(str(getattr(response, "output_text", "")).strip())
            return _result_from_payload(screenshot, self.settings, payload)
        except Exception as error:  # noqa: BLE001 - provider failures are explicit result states.
            return _result_for_input(
                screenshot,
                settings=self.settings,
                status="analysis_failed",
                status_message="OpenAI VLM 圖面分析失敗，未產生推測結果。",
                error=str(error),
            )

    def _responses_client(self) -> OpenAIResponsesClient:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("openai Python SDK is not installed.") from error
        return OpenAI(api_key=self.api_key)


def build_vlm_client(settings: VlmChartAnalysisSettings) -> VisionLanguageModelClient:
    if settings.provider == "openai":
        return OpenAIVisionLanguageModelClient(settings)
    if settings.provider == "local":
        return UnavailableLocalVisionLanguageModelClient(settings)
    raise ValueError("fake VLM requires an explicitly injected FakeVisionLanguageModelClient.")


def analyze_screenshot_capture(
    capture: ScreenshotCaptureResult,
    *,
    settings: VlmChartAnalysisSettings,
    client: VisionLanguageModelClient | None = None,
) -> VlmChartAnalysisResult:
    artifact = capture.artifact
    if not capture.is_available() or artifact is None:
        return VlmChartAnalysisResult(
            screenshot_path=artifact.path if artifact is not None else Path(),
            timestamp_seconds=capture.request.timestamp_seconds,
            source_reference=capture.request.reference,
            provider=settings.provider,
            model=_resolved_model(settings),
            prompt_version=settings.prompt_version,
            schema_version=settings.schema_version,
            status="input_unavailable",
            status_message="截圖 artifact 不可用，未呼叫 VLM。",
            error=capture.error or capture.status,
        )
    screenshot = ScreenshotAnalysisInput(
        artifact=artifact,
        source_reference=artifact.reference or capture.request.reference,
    )
    if not artifact.path.expanduser().resolve().is_file():
        return _result_for_input(
            screenshot,
            settings=settings,
            status="input_unavailable",
            status_message="截圖檔案不存在或不是檔案，未呼叫 VLM。",
            error=str(artifact.path),
        )
    return (client or build_vlm_client(settings)).analyze(screenshot)


def _result_from_payload(
    screenshot: ScreenshotAnalysisInput,
    settings: VlmChartAnalysisSettings,
    payload: object,
) -> VlmChartAnalysisResult:
    if not isinstance(payload, dict):
        raise ValueError("VLM response must be a JSON object.")
    status = _enum_value(payload.get("status"), {"available", "needs_verification", "not_a_chart"}, "status")
    is_technical_chart = _optional_bool(payload.get("is_technical_chart"))
    readability = _confidence(payload.get("readability"))
    observations = tuple(_observation(item) for item in _object_list(payload.get("observations"), "observations"))
    candidates = tuple(_stock_candidate(item) for item in _object_list(payload.get("stock_candidates"), "stock_candidates"))
    if status != "not_a_chart" and (
        is_technical_chart is not True
        or readability in {"低", "未判定"}
        or any(item.needs_verification for item in observations)
        or bool(candidates)
    ):
        status = "needs_verification"
    return VlmChartAnalysisResult(
        screenshot_path=screenshot.artifact.path,
        timestamp_seconds=screenshot.artifact.timestamp_seconds,
        source_reference=screenshot.source_reference,
        provider="openai",
        model=_resolved_model(settings),
        prompt_version=settings.prompt_version,
        schema_version=settings.schema_version,
        status=status,  # type: ignore[arg-type]
        is_technical_chart=is_technical_chart,
        chart_type=_string(payload.get("chart_type"), "未判定"),
        readability=readability,
        observations=observations,
        stock_candidates=candidates,
        status_message=_string(payload.get("status_message")),
    )


def _observation(value: dict[str, object]) -> ChartObservation:
    category = _enum_value(
        value.get("category"),
        {"candlestick", "moving_average", "volume", "support_resistance", "pattern", "speaker_pointer", "other"},
        "observation.category",
    )
    description = _string(value.get("description"))
    if not description:
        raise ValueError("observation.description is required.")
    return ChartObservation(
        category=category,  # type: ignore[arg-type]
        description=description,
        evidence=_string(value.get("evidence")),
        confidence=_confidence(value.get("confidence")),
        needs_verification=bool(value.get("needs_verification", True)),
        verification_reason=_string(value.get("verification_reason")),
    )


def _stock_candidate(value: dict[str, object]) -> StockIdentityCandidate:
    return StockIdentityCandidate(
        raw_code=_string(value.get("raw_code")),
        raw_company_name=_string(value.get("raw_company_name")),
        confidence=_confidence(value.get("confidence")),
        needs_verification=True,
    )


def _vlm_instructions() -> str:
    return (
        "你是投資研究圖面擷取助手，只能描述截圖中實際可見的內容。"
        "分析 K 線、均線、成交量、支撐壓力、型態與講者指圖標記。"
        "看不清楚的日期、價格、均線週期、股票代號或公司名稱不得猜測，必須降低 confidence 並標 needs_verification。"
        "股票代號與公司名稱永遠只是 raw candidate，不能標示為已查證，也不能取代 deterministic verifier。"
        "不得輸出買賣指令、即時投資建議或獲利保證。"
    )


def _vlm_context(screenshot: ScreenshotAnalysisInput) -> str:
    reference = screenshot.source_reference
    return json.dumps(
        {
            "timestamp_seconds": screenshot.artifact.timestamp_seconds,
            "request_reason": screenshot.artifact.reason,
            "transcript_quote": screenshot.artifact.quote or (reference.quote if reference else ""),
            "source_id": reference.source_id if reference else "",
            "source_locator": reference.locator if reference else "",
        },
        ensure_ascii=False,
    )


def _vlm_response_format() -> dict[str, object]:
    confidence = {"type": "string", "enum": ["高", "中", "低", "未判定"]}
    observation = {
        "type": "object",
        "additionalProperties": False,
        "required": ["category", "description", "evidence", "confidence", "needs_verification", "verification_reason"],
        "properties": {
            "category": {
                "type": "string",
                "enum": ["candlestick", "moving_average", "volume", "support_resistance", "pattern", "speaker_pointer", "other"],
            },
            "description": {"type": "string"},
            "evidence": {"type": "string"},
            "confidence": confidence,
            "needs_verification": {"type": "boolean"},
            "verification_reason": {"type": "string"},
        },
    }
    stock_candidate = {
        "type": "object",
        "additionalProperties": False,
        "required": ["raw_code", "raw_company_name", "confidence", "needs_verification"],
        "properties": {
            "raw_code": {"type": "string"},
            "raw_company_name": {"type": "string"},
            "confidence": confidence,
            "needs_verification": {"type": "boolean", "const": True},
        },
    }
    return {
        "type": "json_schema",
        "name": "technical_chart_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "is_technical_chart", "chart_type", "readability", "observations", "stock_candidates", "status_message"],
            "properties": {
                "status": {"type": "string", "enum": ["available", "needs_verification", "not_a_chart"]},
                "is_technical_chart": {"type": ["boolean", "null"]},
                "chart_type": {"type": "string"},
                "readability": confidence,
                "observations": {"type": "array", "items": observation},
                "stock_candidates": {"type": "array", "items": stock_candidate},
                "status_message": {"type": "string"},
            },
        },
    }


def _image_data_url(path: Path) -> str:
    resolved = path.expanduser().resolve()
    mime_type = mimetypes.guess_type(resolved.name)[0] or "image/jpeg"
    return f"data:{mime_type};base64,{base64.b64encode(resolved.read_bytes()).decode('ascii')}"


def _result_for_input(
    screenshot: ScreenshotAnalysisInput,
    *,
    settings: VlmChartAnalysisSettings,
    status: VlmAnalysisStatus,
    status_message: str,
    error: str = "",
) -> VlmChartAnalysisResult:
    return VlmChartAnalysisResult(
        screenshot_path=screenshot.artifact.path,
        timestamp_seconds=screenshot.artifact.timestamp_seconds,
        source_reference=screenshot.source_reference,
        provider=settings.provider,
        model=_resolved_model(settings),
        prompt_version=settings.prompt_version,
        schema_version=settings.schema_version,
        status=status,
        status_message=status_message,
        error=error,
    )


def _resolved_model(settings: VlmChartAnalysisSettings) -> str:
    if settings.provider == "openai":
        return settings.model or os.getenv("OPENAI_VLM_MODEL", DEFAULT_OPENAI_VLM_MODEL)
    return settings.model


def _object_list(value: object, name: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be an array of objects.")
    return value  # type: ignore[return-value]


def _optional_bool(value: object) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ValueError("is_technical_chart must be boolean or null.")


def _confidence(value: object) -> Confidence:
    return _enum_value(value or "未判定", {"高", "中", "低", "未判定"}, "confidence")  # type: ignore[return-value]


def _enum_value(value: object, allowed: set[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} has an unsupported value: {value!r}")
    return value


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default
