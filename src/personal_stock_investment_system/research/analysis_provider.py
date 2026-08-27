"""Research analysis provider boundary."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.brief import (
    BriefDefenseNote,
    BriefStockNote,
    BriefVerificationSource,
    InvestmentBrief,
    render_investment_brief,
)
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
ResearchReportStyle = Literal["structured_report", "investment_brief"]

TECHNICAL_SIGNAL_EXAMPLES = (
    "均線",
    "量能",
    "缺口",
    "KD",
    "支撐",
    "壓力",
    "打底",
    "突破",
    "跌破",
    "漲停",
    "長黑",
    "長紅",
    "三陽開泰",
    "仙人指路",
)


@dataclass(frozen=True)
class ResearchAnalysisSettings:
    provider: ResearchAnalysisProviderName = "rule_based_fallback"
    model: str = ""
    enable_web_search: bool = True
    report_style: ResearchReportStyle = "structured_report"


@dataclass(frozen=True)
class ResearchAnalysisResult:
    report: ResearchReport
    provider: ResearchAnalysisProviderName
    model: str = ""
    status: ResearchAnalysisStatus = "available"
    status_message: str = "本機規則彙整完成。"
    error: str = ""
    markdown: str = ""

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
        enable_web_search: bool | None = None,
        report_style: ResearchReportStyle = "structured_report",
    ) -> None:
        self.model = model or os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini")
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
        self._client = client
        self.enable_web_search = _web_search_enabled() if enable_web_search is None else enable_web_search
        self.report_style = report_style

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
            request: dict[str, object] = {
                "model": self.model,
                "instructions": _openai_research_instructions(
                    self.enable_web_search,
                    report_style=self.report_style,
                ),
                "input": _openai_research_input(
                    source,
                    enable_web_search=self.enable_web_search,
                    report_style=self.report_style,
                ),
                "text": {"format": _openai_response_format(self.report_style)},
                "temperature": 0.2,
            }
            if self.enable_web_search:
                request["tools"] = [{"type": "web_search_preview", "search_context_size": "medium"}]
            response = self._responses_client().responses.create(**request)
            payload = json.loads(str(getattr(response, "output_text", "")).strip())
            report = _research_report_from_payload(source, payload)
            markdown = ""
            if self.report_style == "investment_brief":
                markdown = render_investment_brief(_investment_brief_from_payload(source, payload))
            return ResearchAnalysisResult(
                report=report,
                provider="openai",
                model=self.model,
                status_message=_openai_status_message(response),
                markdown=markdown,
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
        return OpenAIResearchAnalysisClient(
            model=resolved.model,
            enable_web_search=resolved.enable_web_search,
            report_style=resolved.report_style,
        )
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


def _openai_research_instructions(
    enable_web_search: bool = True,
    *,
    report_style: ResearchReportStyle = "structured_report",
) -> str:
    brief_web_policy = (
        "可以使用 web search 查證股票代碼、公司名、產業事件、供應鏈說法與近期事件；"
        "凡是使用網路查證的事實，必須在 verification_sources 填入來源標題、URL 與用途。"
        "若網路來源與影片說法不同，請保留影片說法但標示待查證或低信心。"
        if enable_web_search
        else "不要自行查網路；外部事實一律標示待查證。"
    )
    if report_style == "investment_brief":
        return (
            "你是台股投資情報整理助理。請區分影片逐字稿內容與網路查證結果。"
            "任務目標是產生 NotebookLM-like 的閱讀版情報摘要：完整盤點影片提到的所有股票、走勢、原因、族群脈絡、風險，以及獨立的主流股基期防守表。"
            "寧可保留低信心或待查證項目，也不要只留下少數代表股。"
            "主流股基期防守表是本報告的獨立 section，不屬於固定結構化研究報告。"
            f"{brief_web_policy}"
            "不要補不存在的事實，不要把影片說法包裝成已查證事實，也不要替使用者下單。"
            "所有重要結論應盡量保留逐字稿 timestamp 或 quote citation。"
        )
    return (
        "你是台股投資研究助理。請只根據使用者提供的逐字稿與來源資訊輸出結構化 JSON。"
        "這份是固定結構化研究報告，不要加入主流股基期防守表。"
        "第一層是完整抽取：請盡可能逐檔抽取影片提到的股票、代碼、族群、講者態度、走勢、原因與操作條件，放入既有欄位；寧可多列低信心項目，不要只留下少數代表股。"
        f"{_technical_analysis_policy()}"
        "不要補不存在的事實，不要替使用者下單。"
        "股票名稱、代碼、供應鏈、訂單、價格點位或公司業務若來自逐字稿但未被外部查核，needs_verification 填「是」。"
        "找不到資料時填入「未判定」或「待查證」。所有重要結論應盡量保留逐字稿 timestamp 或 quote citation。"
    )


def _openai_research_input(
    source: ResearchSource,
    *,
    enable_web_search: bool = True,
    report_style: ResearchReportStyle = "structured_report",
) -> str:
    verification_policy = _verification_policy(enable_web_search, report_style)
    style_policy = (
        "輸出閱讀版情報摘要，包含完整股票盤點與主流股基期防守表。"
        if report_style == "investment_brief"
        else "輸出固定結構化研究報告，不要混入主流股基期防守表。"
    )
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
            "整理要求：",
            "- 詳細告訴我這個影片提到哪些股票、走勢如何、原因是什麼。",
            "- 不要只產生一句話摘要；請先完整列股，再彙整族群。",
            "- 股票代碼或公司名聽起來不確定時仍可列出，但 confidence 降低，且 needs_verification 標「是」。",
            "- 操作語氣請轉成「影片提到的條件與防守點」，不要改寫成直接買賣指令。",
            f"- {_technical_analysis_policy()}",
            f"- {style_policy}",
            f"- {verification_policy}",
            "",
            "逐字稿或來源文字：",
            source.raw_text or source.markdown_text or "未提供",
        ]
    )


def _openai_response_format(report_style: ResearchReportStyle) -> dict[str, object]:
    if report_style == "investment_brief":
        return _openai_investment_brief_response_format()
    return _openai_research_response_format()


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


def _openai_investment_brief_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "stock_investment_brief",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "stock_notes": {"type": "array", "items": _brief_stock_note_schema()},
                "defense_notes": {"type": "array", "items": _brief_defense_note_schema()},
                "verification_sources": {"type": "array", "items": _brief_verification_source_schema()},
                "risks": {"type": "array", "items": {"type": "string"}},
                "next_actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "summary",
                "stock_notes",
                "defense_notes",
                "verification_sources",
                "risks",
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


def _brief_stock_note_schema() -> dict[str, object]:
    return _object_schema(
        {
            "stock": {"type": "string"},
            "company": {"type": "string"},
            "group": {"type": "string"},
            "trend": {"type": "string"},
            "reason": {"type": "string"},
            "reference": _reference_schema(),
            "confidence": {"type": "string"},
        }
    )


def _brief_defense_note_schema() -> dict[str, object]:
    return _object_schema(
        {
            "stock": {"type": "string"},
            "company": {"type": "string"},
            "group": {"type": "string"},
            "base_position": {"type": "string"},
            "support_or_entry": {"type": "string"},
            "action_note": {"type": "string"},
            "needs_verification": {"type": "string"},
            "reference": _reference_schema(),
        }
    )


def _brief_verification_source_schema() -> dict[str, object]:
    return _object_schema(
        {
            "title": {"type": "string"},
            "url": {"type": "string"},
            "used_for": {"type": "string"},
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


def _investment_brief_from_payload(source: ResearchSource, payload: object) -> InvestmentBrief:
    if not isinstance(payload, dict):
        raise ValueError("OpenAI response is not a JSON object.")
    return InvestmentBrief(
        source=source,
        title="影片投資情報摘要",
        market_context=_string(payload.get("summary")),
        stock_notes=tuple(_brief_stock_note(source, item) for item in _list(payload.get("stock_notes"))),
        defense_notes=tuple(_brief_defense_note(source, item) for item in _list(payload.get("defense_notes"))),
        verification_sources=tuple(
            _brief_verification_source(item) for item in _list(payload.get("verification_sources"))
        ),
        risks=tuple(_string(item) for item in _list(payload.get("risks"))) or ("未判定",),
        next_actions=tuple(_string(item) for item in _list(payload.get("next_actions"))) or ("未判定",),
    )


def _brief_stock_note(source: ResearchSource, item: object) -> BriefStockNote:
    values = _dict(item)
    return BriefStockNote(
        stock=_string(values.get("stock")),
        company=_string(values.get("company")),
        group=_string(values.get("group")),
        trend=_string(values.get("trend")),
        reason=_string(values.get("reason")),
        reference=_reference(source, values.get("reference")),
        confidence=_string(values.get("confidence")),
    )


def _brief_defense_note(source: ResearchSource, item: object) -> BriefDefenseNote:
    values = _dict(item)
    return BriefDefenseNote(
        stock=_string(values.get("stock")),
        company=_string(values.get("company")),
        group=_string(values.get("group")),
        base_position=_string(values.get("base_position")),
        support_or_entry=_string(values.get("support_or_entry")),
        action_note=_string(values.get("action_note")),
        needs_verification=_string(values.get("needs_verification")),
        reference=_reference(source, values.get("reference")),
    )


def _brief_verification_source(item: object) -> BriefVerificationSource:
    values = _dict(item)
    return BriefVerificationSource(
        title=_string(values.get("title")),
        url=_string(values.get("url")),
        used_for=_string(values.get("used_for")),
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


def _verification_policy(enable_web_search: bool, report_style: ResearchReportStyle) -> str:
    if report_style == "investment_brief":
        if enable_web_search:
            return "可以查網路；查到的外部來源請填入 verification_sources。"
        return "不可查網路；verification_sources 可留空。"
    if enable_web_search:
        return "可以查網路；若外部資訊不足，請把相關項目的 needs_verification 填「是」。"
    return "不可查網路；股票代碼、公司名、供應鏈、訂單、財報與事件日期等外部事實請標示待查證。"


def _technical_analysis_policy() -> str:
    examples = "、".join(TECHNICAL_SIGNAL_EXAMPLES)
    return (
        "技術分析不可只挑代表案例；每一檔 stock_opinions 若 rationale、opinion 或逐字稿附近提到"
        "技術面、價量、型態、支撐壓力、均線、指標或老師自創術語，就必須同步建立 technical_notes。"
        f"觸發詞例子包含：{examples}；這只是範例清單，不是完整固定清單。"
        "遇到來賓自己的技術詞彙也要保留原詞，並在 signal 或 rationale 說明其上下文。"
        "technical_notes.stock 必須對應 stock_opinions.stock 或加權指數；資料不足仍要列出，missing_data 填待補 K 線、量能、均線或圖面資料。"
    )


def _web_search_enabled() -> bool:
    value = os.getenv("OPENAI_RESEARCH_ANALYSIS_WEB_SEARCH", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}
