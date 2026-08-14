"""Shared data models for first-phase research source analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

SourceType = Literal["youtube_public", "pdf", "manual_text"]
LocatorType = Literal["timestamp", "page", "section", "unknown"]
OpinionDirection = Literal["偏多", "偏空", "中性", "未判定"]
SourceImportStatus = Literal[
    "available",
    "manual_fallback",
    "transcript_unavailable",
    "login_required",
    "unsupported_source",
    "media_unavailable",
    "caption_language_unavailable",
    "capture_unavailable",
]


def new_source_id(prefix: str = "src") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def current_collected_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ResearchSource:
    source_type: SourceType
    title: str
    raw_text: str
    source_id: str = field(default_factory=new_source_id)
    source_url: str = ""
    publisher: str = ""
    speaker: str = ""
    speakers: tuple[str, ...] = ()
    published_date: str = ""
    collected_at: str = field(default_factory=current_collected_at)
    language: str = "zh-TW"
    markdown_text: str = ""
    source_locator: str = ""
    notes: str = ""

    def display_speakers(self) -> str:
        if self.speakers:
            return "、".join(speaker for speaker in self.speakers if speaker.strip())
        return self.speaker


@dataclass(frozen=True)
class ResearchSourceImportResult:
    source: ResearchSource
    status: SourceImportStatus
    source_identifier: str = ""
    status_message: str = ""
    error: str = ""

    def is_available(self) -> bool:
        return self.status in {"available", "manual_fallback"}


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    locator_type: LocatorType = "unknown"
    locator: str = ""
    quote: str = ""
    confidence: str = "未判定"

    def display_locator(self) -> str:
        if self.locator:
            return self.locator
        if self.locator_type == "unknown":
            return "未判定"
        return self.locator_type


@dataclass(frozen=True)
class StockOpinion:
    speaker: str
    stock: str
    company: str = ""
    direction: OpinionDirection = "未判定"
    opinion: str = "未判定"
    rationale: str = "未判定"
    reference: SourceReference | None = None
    confidence: str = "未判定"


@dataclass(frozen=True)
class StockRelation:
    stock: str
    company: str = ""
    related_groups: tuple[str, ...] = ()
    related_companies: tuple[str, ...] = ()
    rationale: str = "未判定"
    reference: SourceReference | None = None


@dataclass(frozen=True)
class CompanyProfileNote:
    stock: str
    company: str = ""
    main_business: str = "待查證：來源未說明公司主要業務。"
    products_or_services: str = "待查證"
    customers_or_markets: str = "待查證"
    needs_verification: str = "是"
    reference: SourceReference | None = None


@dataclass(frozen=True)
class TechnicalAnalysisNote:
    stock: str
    signal: str = "未判定"
    chart_context: str = "未判定"
    rationale: str = "未判定"
    missing_data: str = ""
    reference: SourceReference | None = None


@dataclass(frozen=True)
class VerifiableHypothesis:
    hypothesis: str
    required_data: str = "待查證"
    backtestable: str = "未判定"
    initial_rule: str = "未判定"
    confidence: str = "未判定"


@dataclass(frozen=True)
class ResearchReport:
    source: ResearchSource
    summary: str = "未判定"
    stock_opinions: tuple[StockOpinion, ...] = ()
    stock_relations: tuple[StockRelation, ...] = ()
    company_profiles: tuple[CompanyProfileNote, ...] = ()
    technical_notes: tuple[TechnicalAnalysisNote, ...] = ()
    hypotheses: tuple[VerifiableHypothesis, ...] = ()
    risks_and_counterexamples: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
