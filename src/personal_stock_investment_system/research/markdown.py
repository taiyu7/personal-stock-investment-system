"""Markdown rendering for fixed-format research source reports."""

from __future__ import annotations

import re
from datetime import date

from personal_stock_investment_system.research.sources import (
    CompanyProfileNote,
    ResearchReport,
    SourceReference,
    StockOpinion,
    StockRelation,
    TechnicalAnalysisNote,
    VerifiableHypothesis,
    VerificationIssue,
)


def build_research_report_filename(report: ResearchReport, report_date: date | None = None) -> str:
    current_date = report_date or date.today()
    title = _slugify_title(report.source.title)
    return f"{current_date.isoformat()}_{report.source.source_type}_{title}.md"


def render_research_report(report: ResearchReport) -> str:
    source = report.source
    lines = [
        "# 研究來源分析報告",
        "",
        "## 來源資訊",
        "",
        f"- 類型：{source.source_type}",
        f"- 標題：{_display(source.title)}",
        f"- 來源：{_display(source.source_url)}",
        f"- 發布者：{_display(source.publisher)}",
        f"- 講者／來賓：{_display(source.display_speakers())}",
        f"- 日期：{_display(source.published_date)}",
        f"- 匯入時間：{_display(source.collected_at)}",
        "",
        "## 一句話摘要",
        "",
        _display(report.summary),
        "",
        "## 人物對股票的評價",
        "",
        "| 人物 | 股票 | 公司 | 方向 | 評價 | 依據 | 原文位置 | 信心 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    lines.extend(_stock_opinion_row(item) for item in report.stock_opinions)
    lines.extend(
        [
            "",
            "## 股票與族群關聯",
            "",
            "| 股票 | 公司 | 相關族群 | 關聯公司/供應鏈 | 關聯理由 | 原文位置 |",
            "|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_stock_relation_row(item) for item in report.stock_relations)
    lines.extend(
        [
            "",
            "## 提到的公司是做什麼的",
            "",
            "| 股票 | 公司 | 主要業務 | 產品/服務 | 客戶/市場 | 待查證 | 原文位置 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_company_profile_row(item) for item in report.company_profiles)
    lines.extend(
        [
            "",
            "## 技術分析",
            "",
            "| 股票 | 技術訊號 | 對應圖面 | 判斷依據 | 原文位置 | 待補資料 |",
            "|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_technical_note_row(item) for item in report.technical_notes)
    lines.extend(
        [
            "",
            "## 查核標記",
            "",
            "| 類型 | 對象 | 影片說法 | 查核狀態 | 查核依據/來源 | 原文位置 | 信心 |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(_verification_issue_row(item) for item in report.verification_issues)
    lines.extend(
        [
            "",
            "## 可驗證假設",
            "",
            "| 假設 | 需要資料 | 可否回測 | 初步規則 | 信心 |",
            "|---|---|---|---|---|",
        ]
    )
    lines.extend(_hypothesis_row(item) for item in report.hypotheses)
    lines.extend(
        [
            "",
            "## 風險與反例",
            "",
            *_bullet_lines(report.risks_and_counterexamples),
            "",
            "## 待查問題",
            "",
            *_bullet_lines(report.open_questions),
            "",
            "## 後續行動",
            "",
            *_bullet_lines(report.next_actions),
            "",
        ]
    )
    return "\n".join(lines)


def _stock_opinion_row(item: StockOpinion) -> str:
    return _table_row(
        [
            item.speaker,
            item.stock,
            item.company,
            item.direction,
            item.opinion,
            item.rationale,
            _reference_locator(item.reference),
            item.confidence,
        ]
    )


def _stock_relation_row(item: StockRelation) -> str:
    return _table_row(
        [
            item.stock,
            item.company,
            "、".join(item.related_groups) or "未判定",
            "、".join(item.related_companies) or "未判定",
            item.rationale,
            _reference_locator(item.reference),
        ]
    )


def _company_profile_row(item: CompanyProfileNote) -> str:
    return _table_row(
        [
            item.stock,
            item.company,
            item.main_business,
            item.products_or_services,
            item.customers_or_markets,
            item.needs_verification,
            _reference_locator(item.reference),
        ]
    )


def _technical_note_row(item: TechnicalAnalysisNote) -> str:
    return _table_row(
        [
            item.stock,
            item.signal,
            item.chart_context,
            item.rationale,
            _reference_locator(item.reference),
            item.missing_data,
        ]
    )


def _verification_issue_row(item: VerificationIssue) -> str:
    evidence = item.evidence
    if item.external_sources:
        evidence = f"{evidence}；來源：" + "、".join(item.external_sources)
    return _table_row(
        [
            item.item_type,
            item.target,
            item.claim,
            item.status,
            evidence,
            _reference_locator(item.reference),
            item.confidence,
        ]
    )


def _hypothesis_row(item: VerifiableHypothesis) -> str:
    return _table_row([item.hypothesis, item.required_data, item.backtestable, item.initial_rule, item.confidence])


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


def _slugify_title(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]+', "", title).strip()
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned[:32] or "未命名研究來源"
