"""Markdown rendering for fixed-format research source reports."""

from __future__ import annotations

import re
import base64
import json
import hashlib
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
        *_manual_review_alert_lines(report.verification_issues),
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
        "| 人物 | 股票 | 公司 | 方向 | 評價 | 依據 | 原文位置 | 信心 | 原文引述 |",
        "|---|---|---|---|---|---|---|---|---|",
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
            "| 股票 | 公司 | 技術訊號 | 對應圖面 | 判斷依據 | 原文位置 | 待補資料 |",
            "|---|---|---|---|---|---|---|",
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
    if report.entity_classifications:
        lines.extend(
            [
                "",
                "## 人工確認的公司／族群分類",
                "",
                "| 原始對象 | 分類 | 標準股票 | 原文位置 | 查核紀錄 | 確認時間 |",
                "|---|---|---|---|---|---|",
            ]
        )
        lines.extend(
            _table_row([
                " ".join(value for value in (item.raw_code, item.raw_name) if value),
                item.entity_type,
                " ".join(value for value in (item.canonical_code, item.canonical_name) if value) or "不適用",
                item.source_locator,
                item.evidence,
                item.created_at,
            ])
            for item in report.entity_classifications
        )
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


def parse_research_report_markdown(markdown: str) -> ResearchReport:
    """Recover the exact structured report embedded in a generated fixed Markdown file."""
    match = re.search(r"<!-- PSIS_RESEARCH_REPORT_V1:([A-Za-z0-9_=-]+) -->", markdown)
    if match is None:
        return _legacy_report_from_markdown(markdown)
    try:
        payload = json.loads(base64.urlsafe_b64decode(match.group(1).encode("ascii")))
        return _report_from_payload(payload)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("研究報告內的結構化資料無法解析，請重新下載該報告。") from error


def _legacy_report_from_markdown(markdown: str) -> ResearchReport:
    """Parse the fixed visible tables from older reports that predate the embedded payload."""
    from personal_stock_investment_system.research.sources import (
        CompanyProfileNote,
        EntityClassification,
        ResearchSource,
        StockOpinion,
        StockRelation,
        TechnicalAnalysisNote,
        VerifiableHypothesis,
        VerificationIssue,
    )

    metadata: dict[str, str] = {}
    for line in markdown.splitlines():
        if line.startswith("- ") and "：" in line:
            key, value = line[2:].split("：", maxsplit=1)
            metadata[key] = value.strip()
    def metadata_value(key: str, default: str = "") -> str:
        value = metadata.get(key, "").strip()
        return default if value in {"", "未判定"} else value

    title = metadata_value("標題", "未命名研究來源")
    source_id = "legacy_" + hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12]
    source = ResearchSource(
        source_type=(metadata.get("類型") if metadata.get("類型") in {"youtube_public", "pdf", "manual_text", "local_audio", "local_video"} else "youtube_public"),
        title=title,
        raw_text="",
        source_id=source_id,
        source_url=metadata_value("來源"),
        publisher=metadata_value("發布者"),
        speakers=tuple(filter(None, metadata_value("講者／來賓").split("、"))),
        published_date=metadata_value("日期"),
    )

    def ref(locator: str, quote: str = "") -> SourceReference | None:
        if (not locator or locator == "未判定") and not quote:
            return None
        locator_type = "timestamp" if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?$", locator) else "unknown"
        return SourceReference(source_id=source_id, locator_type=locator_type, locator=locator, quote=quote)

    def table(section: str) -> list[list[str]]:
        lines = markdown.splitlines()
        begin = next((index + 1 for index, line in enumerate(lines) if line.strip() == f"## {section}"), len(lines))
        result = []
        for line in lines[begin:]:
            if line.startswith("## "):
                break
            if not line.strip().startswith("|"):
                continue
            cells = [cell.replace("\\|", "|").replace("<br>", "\n").strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if cells and not all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                if not result:
                    result.append(cells)  # header
                else:
                    result.append(cells)
        return result[1:]

    opinions = []
    for row in table("人物對股票的評價"):
        if len(row) >= 8:
            opinions.append(
                StockOpinion(
                    row[0], row[1], row[2], row[3], row[4], row[5],
                    ref(row[6], row[8] if len(row) >= 9 else ""), row[7],
                )
            )
    relations = []
    for row in table("股票與族群關聯"):
        if len(row) >= 6:
            relations.append(StockRelation(row[0], row[1], tuple(x for x in row[2].split("、") if x and x != "未判定"), tuple(x for x in row[3].split("、") if x and x != "未判定"), row[4], ref(row[5])))
    profiles = []
    for row in table("提到的公司是做什麼的"):
        if len(row) >= 7:
            profiles.append(CompanyProfileNote(row[0], row[1], row[2], row[3], row[4], row[5], ref(row[6])))
    technical = []
    for row in table("技術分析"):
        if len(row) >= 7:
            technical.append(TechnicalAnalysisNote(row[0], row[1], row[2], row[3], row[4], row[6], ref(row[5])))
    issues = []
    for row in table("查核標記"):
        if len(row) >= 7:
            issues.append(VerificationIssue(row[0], row[1], row[2], row[3], row[4], (), ref(row[5]), row[6]))
    hypotheses = []
    for row in table("可驗證假設"):
        if len(row) >= 5:
            hypotheses.append(VerifiableHypothesis(*row[:5]))
    classifications = []
    for row in table("人工確認的公司／族群分類"):
        if len(row) < 6:
            continue
        raw_code, _, raw_name = row[0].partition(" ")
        canonical_code, _, canonical_name = row[2].partition(" ")
        if row[2] == "不適用":
            canonical_code, canonical_name = "", ""
        classifications.append(
            EntityClassification(
                raw_code=raw_code,
                raw_name=raw_name or raw_code,
                entity_type=row[1],
                canonical_code=canonical_code,
                canonical_name=canonical_name,
                source_locator=row[3],
                evidence=row[4],
                created_at=row[5],
            )
        )

    def bullets(section: str) -> tuple[str, ...]:
        lines = markdown.splitlines()
        begin = next((index + 1 for index, line in enumerate(lines) if line.strip() == f"## {section}"), len(lines))
        return tuple(line[2:].strip() for line in lines[begin:] if line.startswith("- ") and not line.startswith("- 未判定"))

    summary_heading = "## 一句話摘要"
    summary_lines = markdown.split(summary_heading, maxsplit=1)[1].split("\n## ", maxsplit=1)[0].strip() if summary_heading in markdown else "未判定"
    return ResearchReport(
        source=source, summary=summary_lines, stock_opinions=tuple(opinions), stock_relations=tuple(relations),
        company_profiles=tuple(profiles), technical_notes=tuple(technical), verification_issues=tuple(issues),
        hypotheses=tuple(hypotheses), risks_and_counterexamples=bullets("風險與反例"),
        open_questions=bullets("待查問題"), next_actions=bullets("後續行動"),
        entity_classifications=tuple(classifications),
    )


def _report_from_payload(payload: dict[str, object]) -> ResearchReport:
    from personal_stock_investment_system.research.sources import (
        CompanyProfileNote,
        EntityClassification,
        ResearchSource,
        StockOpinion,
        StockRelation,
        TechnicalAnalysisNote,
        VerifiableHypothesis,
        VerificationIssue,
    )

    source_payload = dict(payload["source"])
    source_payload["speakers"] = tuple(source_payload.get("speakers", ()))
    source = ResearchSource(**source_payload)

    def reference(values):
        return SourceReference(**values) if isinstance(values, dict) else None

    def rows(name, constructor, tuple_fields=()):
        result = []
        for raw in payload.get(name, ()):
            values = dict(raw)
            for field_name in tuple_fields:
                values[field_name] = tuple(values.get(field_name, ()))
            if "reference" in values:
                values["reference"] = reference(values["reference"])
            result.append(constructor(**values))
        return tuple(result)

    return ResearchReport(
        source=source,
        summary=payload.get("summary", "未判定"),
        stock_opinions=rows("stock_opinions", StockOpinion),
        stock_relations=rows("stock_relations", StockRelation, ("related_groups", "related_companies")),
        company_profiles=rows("company_profiles", CompanyProfileNote),
        technical_notes=rows("technical_notes", TechnicalAnalysisNote),
        verification_issues=rows("verification_issues", VerificationIssue, ("external_sources",)),
        hypotheses=rows("hypotheses", VerifiableHypothesis),
        risks_and_counterexamples=tuple(payload.get("risks_and_counterexamples", ())),
        open_questions=tuple(payload.get("open_questions", ())),
        next_actions=tuple(payload.get("next_actions", ())),
        entity_classifications=rows("entity_classifications", EntityClassification),
    )


def _manual_review_alert_lines(issues: tuple[VerificationIssue, ...]) -> list[str]:
    uncertain = tuple(issue for issue in issues if issue.status not in {"已查證", "已修正"})
    if not uncertain:
        return []
    lines = [
        "## ⚠️ 產出前先人工確認",
        "",
        "> 下列項目無法由本機公司清單安全自動修正，請先核對原始影片或逐字稿。",
        "",
    ]
    for issue in uncertain:
        locator = _reference_locator(issue.reference)
        lines.append(
            f"- **{_display(issue.status)}｜{_display(issue.target)}**："
            f"{_display(issue.evidence)}（原文位置：{locator}）"
        )
    lines.append("")
    return lines


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
            item.reference.quote if item.reference else "",
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
            item.company,
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
