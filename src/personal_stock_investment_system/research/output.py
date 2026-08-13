"""Output destination settings for rendered research reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from personal_stock_investment_system.research.markdown import build_research_report_filename, render_research_report
from personal_stock_investment_system.research.sources import ResearchReport

OutputDestinationKind = Literal["obsidian_inbox", "custom_path"]

DEFAULT_OBSIDIAN_INBOX_PATH = Path(r"C:\Users\taiyu\Obsidian\個人理財資訊系統\00-inbox")


@dataclass(frozen=True)
class ResearchReportOutputSettings:
    write_to_obsidian_inbox: bool = True
    write_to_custom_path: bool = True
    obsidian_inbox_path: Path = DEFAULT_OBSIDIAN_INBOX_PATH
    custom_output_path: Path | None = None

    @classmethod
    def no_local_files(cls) -> "ResearchReportOutputSettings":
        return cls(write_to_obsidian_inbox=False, write_to_custom_path=False)


@dataclass(frozen=True)
class ResearchReportOutputDestination:
    kind: OutputDestinationKind
    directory: Path


@dataclass(frozen=True)
class WrittenResearchReport:
    kind: OutputDestinationKind
    path: Path


def default_custom_output_path() -> Path:
    return Path.home() / "Desktop"


def resolve_research_report_output_destinations(
    settings: ResearchReportOutputSettings | None = None,
) -> tuple[ResearchReportOutputDestination, ...]:
    current_settings = settings or ResearchReportOutputSettings()
    destinations: list[ResearchReportOutputDestination] = []
    if current_settings.write_to_obsidian_inbox:
        destinations.append(
            ResearchReportOutputDestination(
                kind="obsidian_inbox",
                directory=Path(current_settings.obsidian_inbox_path),
            )
        )
    if current_settings.write_to_custom_path:
        destinations.append(
            ResearchReportOutputDestination(
                kind="custom_path",
                directory=Path(current_settings.custom_output_path or default_custom_output_path()),
            )
        )
    return tuple(destinations)


def write_research_report_outputs(
    report: ResearchReport,
    *,
    settings: ResearchReportOutputSettings | None = None,
    markdown: str | None = None,
    report_date: date | None = None,
) -> tuple[WrittenResearchReport, ...]:
    content = markdown if markdown is not None else render_research_report(report)
    filename = build_research_report_filename(report, report_date=report_date)
    written: list[WrittenResearchReport] = []
    for destination in resolve_research_report_output_destinations(settings):
        destination.directory.mkdir(parents=True, exist_ok=True)
        output_path = destination.directory / filename
        output_path.write_text(content, encoding="utf-8")
        written.append(WrittenResearchReport(kind=destination.kind, path=output_path))
    return tuple(written)
