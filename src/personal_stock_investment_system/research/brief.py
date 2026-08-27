"""NotebookLM-like investment briefing Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass

from personal_stock_investment_system.research.sources import ResearchSource, SourceReference


@dataclass(frozen=True)
class BriefStockNote:
    stock: str = "未判定"
    company: str = "未判定"
    group: str = "未判定"
    trend: str = "未判定"
    reason: str = "未判定"
    reference: SourceReference | None = None
    confidence: str = "未判定"


@dataclass(frozen=True)
class BriefDefenseNote:
    stock: str = "未判定"
    company: str = "未判定"
    group: str = "未判定"
    base_position: str = "未判定"
    support_or_entry: str = "未判定"
    action_note: str = "未判定"
    needs_verification: str = "是"
    reference: SourceReference | None = None


@dataclass(frozen=True)
class BriefVerificationSource:
    title: str = "未判定"
    url: str = "未判定"
    used_for: str = "未判定"


@dataclass(frozen=True)
class InvestmentBrief:
    source: ResearchSource
    title: str = "影片投資情報摘要"
    market_context: str = "未判定"
    stock_notes: tuple[BriefStockNote, ...] = ()
    defense_notes: tuple[BriefDefenseNote, ...] = ()
    verification_sources: tuple[BriefVerificationSource, ...] = ()
    risks: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()


def render_investment_brief(brief: InvestmentBrief) -> str:
    lines = [
        f"# {brief.title}",
        "",
        "## 來源資訊",
        "",
        f"- 類型：{_display(brief.source.source_type)}",
        f"- 標題：{_display(brief.source.title)}",
        f"- 來源：{_display(brief.source.source_url)}",
        f"- 發布者：{_display(brief.source.publisher)}",
        f"- 講者／來賓：{_display(brief.source.display_speakers())}",
        f"- 日期：{_display(brief.source.published_date)}",
        "",
        "## 市場脈絡",
        "",
        _display(brief.market_context),
        "",
        "## 影片提到的股票",
        "",
        "| 股票 | 公司 | 族群 | 走勢 | 原因 | 原文位置 | 信心 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.extend(_stock_note_row(item) for item in brief.stock_notes)
    lines.extend(
        [
            "",
            "## 主流股基期防守表",
            "",
            "| 股票 | 公司 | 族群 | 基期與位階 | 防守點/切入點 | 操作筆記 | 待查證 | 原文位置 |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_defense_note_row(item) for item in brief.defense_notes)
    lines.extend(
        [
            "",
            "## 查證來源",
            "",
            "| 來源 | URL | 用途 |",
            "|---|---|---|",
        ]
    )
    lines.extend(_verification_source_row(item) for item in brief.verification_sources)
    lines.extend(["", "## 風險提醒", "", *_bullet_lines(brief.risks)])
    lines.extend(["", "## 後續行動", "", *_bullet_lines(brief.next_actions), ""])
    return "\n".join(lines)


def _stock_note_row(item: BriefStockNote) -> str:
    return _table_row(
        [
            item.stock,
            item.company,
            item.group,
            item.trend,
            item.reason,
            _reference_locator(item.reference),
            item.confidence,
        ]
    )


def _defense_note_row(item: BriefDefenseNote) -> str:
    return _table_row(
        [
            item.stock,
            item.company,
            item.group,
            item.base_position,
            item.support_or_entry,
            item.action_note,
            item.needs_verification,
            _reference_locator(item.reference),
        ]
    )


def _verification_source_row(item: BriefVerificationSource) -> str:
    return _table_row([item.title, item.url, item.used_for])


def _reference_locator(reference: SourceReference | None) -> str:
    if reference is None:
        return "未判定"
    return reference.display_locator()


def _bullet_lines(items: tuple[str, ...]) -> list[str]:
    if not items:
        return ["- 未判定"]
    return [f"- {_display(item)}" for item in items]


def _table_row(values: list[str]) -> str:
    return "| " + " | ".join(_escape_table_cell(_display(value)) for value in values) + " |"


def _display(value: str) -> str:
    return value.strip() if value and value.strip() else "未判定"


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")
