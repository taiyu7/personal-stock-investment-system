"""Research analysis provider boundary."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.sources import (
    CompanyProfileNote,
    ResearchReport,
    ResearchSource,
    SourceReference,
    StockOpinion,
    StockRelation,
    TechnicalAnalysisNote,
    VerifiableHypothesis,
)

ResearchAnalysisProviderName = Literal["rule_based_fallback", "openai", "anthropic_claude"]
ResearchAnalysisStatus = Literal["available", "unsupported_provider", "analysis_failed"]


@dataclass(frozen=True)
class ResearchAnalysisSettings:
    provider: ResearchAnalysisProviderName = "rule_based_fallback"
    model: str = ""


@dataclass(frozen=True)
class ResearchAnalysisResult:
    report: ResearchReport
    provider: ResearchAnalysisProviderName
    model: str = ""
    status: ResearchAnalysisStatus = "available"
    status_message: str = "本機規則彙整完成。"
    error: str = ""

    def is_available(self) -> bool:
        return self.status == "available"


class ResearchAnalysisClient(Protocol):
    def analyze(self, source: ResearchSource) -> ResearchAnalysisResult:
        """Analyze a research source into a structured research report."""


class OpenAIResponsesClient(Protocol):
    class Responses(Protocol):
        def create(self, **kwargs: object) -> object:
            """Create an OpenAI response."""

    responses: Responses


class RuleBasedResearchAnalysisClient:
    def __init__(self, model: str = "rule_based_v1") -> None:
        self.model = model

    def analyze(self, source: ResearchSource) -> ResearchAnalysisResult:
        return ResearchAnalysisResult(
            report=analyze_research_source(source),
            provider="rule_based_fallback",
            model=self.model,
            status_message="本機規則彙整完成。",
        )


class OpenAIResearchAnalysisClient:
    def __init__(
        self,
        model: str = "",
        *,
        api_key: str | None = None,
        client: OpenAIResponsesClient | None = None,
    ) -> None:
        self.model = model or os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self._client = client

    def analyze(self, source: ResearchSource) -> ResearchAnalysisResult:
        fallback = analyze_research_source(source)
        if not self.api_key and self._client is None:
            return _fallback_result(
                fallback,
                provider="openai",
                model=self.model,
                message="缺少 OPENAI_API_KEY，已改用本機規則 fallback 產生報告。",
                error="missing_openai_api_key",
            )
        try:
            response = self._responses_client().responses.create(
                model=self.model,
                instructions=_openai_research_instructions(),
                input=_openai_research_input(source),
                text={"format": _openai_research_response_format()},
                temperature=0.2,
            )
            payload = json.loads(str(getattr(response, "output_text", "")).strip())
            report = _research_report_from_payload(source, payload)
            return ResearchAnalysisResult(
                report=report,
                provider="openai",
                model=self.model,
                status_message=_openai_status_message(response),
            )
        except Exception as error:  # noqa: BLE001 - provider boundary must recover to local fallback.
            return _fallback_result(
                fallback,
                provider="openai",
                model=self.model,
                message="OpenAI 彙整失敗，已改用本機規則 fallback 產生報告。",
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


class UnavailableResearchAnalysisClient:
    def __init__(self, provider: ResearchAnalysisProviderName, model: str = "") -> None:
        self.provider = provider
        self.model = model

    def analyze(self, source: ResearchSource) -> ResearchAnalysisResult:
        fallback = analyze_research_source(source)
        return _fallback_result(
            fallback,
            provider=self.provider,
            model=self.model,
            message=f"{self.provider} 彙整 provider 尚未接上 API；已改用本機規則 fallback 產生報告。",
            error="provider_not_implemented",
        )


def build_research_analysis_client(settings: ResearchAnalysisSettings | None = None) -> ResearchAnalysisClient:
    resolved = settings or ResearchAnalysisSettings()
    if resolved.provider == "rule_based_fallback":
        return RuleBasedResearchAnalysisClient(model=resolved.model or "rule_based_v1")
    if resolved.provider == "openai":
        return OpenAIResearchAnalysisClient(model=resolved.model)
    return UnavailableResearchAnalysisClient(provider=resolved.provider, model=resolved.model)


def analyze_research_source_with_provider(
    source: ResearchSource,
    *,
    settings: ResearchAnalysisSettings | None = None,
    client: ResearchAnalysisClient | None = None,
) -> ResearchAnalysisResult:
    return (client or build_research_analysis_client(settings)).analyze(source)


def _fallback_result(
    report: ResearchReport,
    *,
    provider: ResearchAnalysisProviderName,
    model: str,
    message: str,
    error: str,
) -> ResearchAnalysisResult:
    return ResearchAnalysisResult(
        report=report,
        provider=provider,
        model=model,
        status="analysis_failed" if provider == "openai" else "unsupported_provider",
        status_message=message,
        error=error,
    )


def _openai_research_instructions() -> str:
    return (
        "你是台股投資研究助理。請只根據使用者提供的逐字稿與來源資訊輸出結構化 JSON。"
        "不要自行查網路，不要補不存在的事實，不要給買賣建議。"
        "找不到資料時填入「未判定」或「待查證」。"
        "所有重要結論應盡量保留逐字稿 timestamp 或 quote citation。"
    )


def _openai_research_input(source: ResearchSource) -> str:
    return "\n".join(
        [
            "請將以下研究來源整理成固定 JSON schema。",
            "",
            "來源資訊：",
            f"- source_id: {source.source_id}",
            f"- type: {source.source_type}",
            f"- title: {source.title}",
            f"- url: {source.source_url or '未提供'}",
            f"- publisher: {source.publisher or '未提供'}",
            f"- speakers: {source.display_speakers() or '未提供'}",
            f"- date: {source.published_date or '未提供'}",
            "",
            "逐字稿或來源文字：",
            source.raw_text or source.markdown_text or "未提供",
        ]
    )


def _openai_research_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "stock_research_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "stock_opinions": {"type": "array", "items": _stock_opinion_schema()},
                "stock_relations": {"type": "array", "items": _stock_relation_schema()},
                "company_profiles": {"type": "array", "items": _company_profile_schema()},
                "technical_notes": {"type": "array", "items": _technical_note_schema()},
                "hypotheses": {"type": "array", "items": _hypothesis_schema()},
                "risks_and_counterexamples": {"type": "array", "items": {"type": "string"}},
                "open_questions": {"type": "array", "items": {"type": "string"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "summary",
                "stock_opinions",
                "stock_relations",
                "company_profiles",
                "technical_notes",
                "hypotheses",
                "risks_and_counterexamples",
                "open_questions",
                "next_actions",
            ],
        },
    }


def _stock_opinion_schema() -> dict[str, object]:
    return _object_schema(
        {
            "speaker": {"type": "string"},
            "stock": {"type": "string"},
            "company": {"type": "string"},
            "direction": {"type": "string", "enum": ["偏多", "偏空", "中性", "未判定"]},
            "opinion": {"type": "string"},
            "rationale": {"type": "string"},
            "reference": _reference_schema(),
            "confidence": {"type": "string"},
        }
    )


def _stock_relation_schema() -> dict[str, object]:
    return _object_schema(
        {
            "stock": {"type": "string"},
            "company": {"type": "string"},
            "related_groups": {"type": "array", "items": {"type": "string"}},
            "related_companies": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "reference": _reference_schema(),
        }
    )


def _company_profile_schema() -> dict[str, object]:
    return _object_schema(
        {
            "stock": {"type": "string"},
            "company": {"type": "string"},
            "main_business": {"type": "string"},
            "products_or_services": {"type": "string"},
            "customers_or_markets": {"type": "string"},
            "needs_verification": {"type": "string"},
            "reference": _reference_schema(),
        }
    )


def _technical_note_schema() -> dict[str, object]:
    return _object_schema(
        {
            "stock": {"type": "string"},
            "signal": {"type": "string"},
            "chart_context": {"type": "string"},
            "rationale": {"type": "string"},
            "missing_data": {"type": "string"},
            "reference": _reference_schema(),
        }
    )


def _hypothesis_schema() -> dict[str, object]:
    return _object_schema(
        {
            "hypothesis": {"type": "string"},
            "required_data": {"type": "string"},
            "backtestable": {"type": "string"},
            "initial_rule": {"type": "string"},
            "confidence": {"type": "string"},
        }
    )


def _reference_schema() -> dict[str, object]:
    return _object_schema(
        {
            "locator_type": {"type": "string", "enum": ["timestamp", "page", "section", "unknown"]},
            "locator": {"type": "string"},
            "quote": {"type": "string"},
            "confidence": {"type": "string"},
        }
    )


def _object_schema(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _research_report_from_payload(source: ResearchSource, payload: object) -> ResearchReport:
    if not isinstance(payload, dict):
        raise ValueError("OpenAI response is not a JSON object.")
    return ResearchReport(
        source=source,
        summary=_string(payload.get("summary")),
        stock_opinions=tuple(_stock_opinion(source, item) for item in _list(payload.get("stock_opinions"))),
        stock_relations=tuple(_stock_relation(source, item) for item in _list(payload.get("stock_relations"))),
        company_profiles=tuple(_company_profile(source, item) for item in _list(payload.get("company_profiles"))),
        technical_notes=tuple(_technical_note(source, item) for item in _list(payload.get("technical_notes"))),
        hypotheses=tuple(_hypothesis(item) for item in _list(payload.get("hypotheses"))),
        risks_and_counterexamples=tuple(_string(item) for item in _list(payload.get("risks_and_counterexamples"))) or ("未判定",),
        open_questions=tuple(_string(item) for item in _list(payload.get("open_questions"))) or ("未判定",),
        next_actions=tuple(_string(item) for item in _list(payload.get("next_actions"))) or ("未判定",),
    )


def _stock_opinion(source: ResearchSource, item: object) -> StockOpinion:
    values = _dict(item)
    return StockOpinion(
        speaker=_string(values.get("speaker")),
        stock=_string(values.get("stock")),
        company=_string(values.get("company")),
        direction=_direction(values.get("direction")),
        opinion=_string(values.get("opinion")),
        rationale=_string(values.get("rationale")),
        reference=_reference(source, values.get("reference")),
        confidence=_string(values.get("confidence")),
    )


def _stock_relation(source: ResearchSource, item: object) -> StockRelation:
    values = _dict(item)
    return StockRelation(
        stock=_string(values.get("stock")),
        company=_string(values.get("company")),
        related_groups=tuple(_string(value) for value in _list(values.get("related_groups"))),
        related_companies=tuple(_string(value) for value in _list(values.get("related_companies"))),
        rationale=_string(values.get("rationale")),
        reference=_reference(source, values.get("reference")),
    )


def _company_profile(source: ResearchSource, item: object) -> CompanyProfileNote:
    values = _dict(item)
    return CompanyProfileNote(
        stock=_string(values.get("stock")),
        company=_string(values.get("company")),
        main_business=_string(values.get("main_business")),
        products_or_services=_string(values.get("products_or_services")),
        customers_or_markets=_string(values.get("customers_or_markets")),
        needs_verification=_string(values.get("needs_verification")),
        reference=_reference(source, values.get("reference")),
    )


def _technical_note(source: ResearchSource, item: object) -> TechnicalAnalysisNote:
    values = _dict(item)
    return TechnicalAnalysisNote(
        stock=_string(values.get("stock")),
        signal=_string(values.get("signal")),
        chart_context=_string(values.get("chart_context")),
        rationale=_string(values.get("rationale")),
        missing_data=_string(values.get("missing_data")),
        reference=_reference(source, values.get("reference")),
    )


def _hypothesis(item: object) -> VerifiableHypothesis:
    values = _dict(item)
    return VerifiableHypothesis(
        hypothesis=_string(values.get("hypothesis")),
        required_data=_string(values.get("required_data")),
        backtestable=_string(values.get("backtestable")),
        initial_rule=_string(values.get("initial_rule")),
        confidence=_string(values.get("confidence")),
    )


def _reference(source: ResearchSource, item: object) -> SourceReference | None:
    values = _dict(item)
    if not values:
        return None
    return SourceReference(
        source_id=source.source_id,
        locator_type=_locator_type(values.get("locator_type")),
        locator=_string(values.get("locator")),
        quote=_string(values.get("quote")),
        confidence=_string(values.get("confidence")),
    )


def _openai_status_message(response: object) -> str:
    usage = getattr(response, "usage", None)
    if usage is None:
        return "OpenAI 彙整完成。"
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        return "OpenAI 彙整完成。"
    return f"OpenAI 彙整完成。total_tokens={total_tokens}"


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string(value: object, default: str = "未判定") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default


def _direction(value: object) -> Literal["偏多", "偏空", "中性", "未判定"]:
    text = _string(value)
    if text in {"偏多", "偏空", "中性", "未判定"}:
        return text  # type: ignore[return-value]
    return "未判定"


def _locator_type(value: object) -> Literal["timestamp", "page", "section", "unknown"]:
    text = _string(value, "unknown")
    if text in {"timestamp", "page", "section", "unknown"}:
        return text  # type: ignore[return-value]
    return "unknown"
