"""Research analysis provider boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.sources import ResearchReport, ResearchSource

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


class UnavailableResearchAnalysisClient:
    def __init__(self, provider: ResearchAnalysisProviderName, model: str = "") -> None:
        self.provider = provider
        self.model = model

    def analyze(self, source: ResearchSource) -> ResearchAnalysisResult:
        fallback = analyze_research_source(source)
        return ResearchAnalysisResult(
            report=fallback,
            provider=self.provider,
            model=self.model,
            status="unsupported_provider",
            status_message=f"{self.provider} 彙整 provider 尚未接上 API；已改用本機規則 fallback 產生報告。",
            error="provider_not_implemented",
        )


def build_research_analysis_client(settings: ResearchAnalysisSettings | None = None) -> ResearchAnalysisClient:
    resolved = settings or ResearchAnalysisSettings()
    if resolved.provider == "rule_based_fallback":
        return RuleBasedResearchAnalysisClient(model=resolved.model or "rule_based_v1")
    return UnavailableResearchAnalysisClient(provider=resolved.provider, model=resolved.model)


def analyze_research_source_with_provider(
    source: ResearchSource,
    *,
    settings: ResearchAnalysisSettings | None = None,
    client: ResearchAnalysisClient | None = None,
) -> ResearchAnalysisResult:
    return (client or build_research_analysis_client(settings)).analyze(source)
