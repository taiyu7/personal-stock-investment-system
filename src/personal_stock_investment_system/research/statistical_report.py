"""Grounded cross-report stock consensus and statistical report generation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from personal_stock_investment_system.research.sources import ResearchReport
from personal_stock_investment_system.research.stock_validation import TaiwanStockDirectory


@dataclass(frozen=True)
class StockMentionEvidence:
    evidence_id: str
    stock_code: str
    company_name: str
    source_id: str
    program: str
    video_title: str
    speaker: str
    direction: str
    opinion: str
    rationale: str
    technical_note: str
    locator: str
    quote: str


@dataclass(frozen=True)
class StockConsensus:
    stock_code: str
    company_name: str
    speaker_count: int
    program_count: int
    mention_count: int
    evidence: tuple[StockMentionEvidence, ...]


@dataclass(frozen=True)
class StatisticalReportResult:
    markdown: str
    filename: str
    provider: str
    model: str


class ResponsesClient(Protocol):
    class Responses(Protocol):
        def create(self, **kwargs: object) -> object: ...

    responses: Responses


def build_stock_consensus(
    reports: tuple[ResearchReport, ...],
    directory: TaiwanStockDirectory,
    *,
    direction: str = "偏多",
) -> tuple[StockConsensus, ...]:
    """Rank officially listed equities by distinct speakers, programs, then traceable mentions."""
    official = {company.code: company for company in directory.companies}
    collected: dict[str, list[StockMentionEvidence]] = {}
    seen_mentions: set[tuple[str, str, str, str]] = set()
    number = 1
    for report in reports:
        source = report.source
        for opinion in report.stock_opinions:
            company = official.get(opinion.stock.strip())
            if company is None or opinion.company.strip() != company.name or opinion.direction != direction:
                continue
            locator = opinion.reference.display_locator() if opinion.reference else "未判定"
            speaker = opinion.speaker.strip()
            mention_key = (source.source_id, speaker, company.code, locator)
            if mention_key in seen_mentions:
                continue
            seen_mentions.add(mention_key)
            technical = "；".join(
                note.rationale for note in report.technical_notes
                if note.stock.strip() == company.code and note.company.strip() == company.name
            )
            evidence = StockMentionEvidence(
                evidence_id=f"{'E' if direction == '偏多' else 'B'}{number:04d}", stock_code=company.code, company_name=company.name,
                source_id=source.source_id, program=source.publisher.strip(), video_title=source.title,
                speaker=speaker, direction=opinion.direction, opinion=opinion.opinion,
                rationale=opinion.rationale, technical_note=technical, locator=locator,
                quote=opinion.reference.quote if opinion.reference else "",
            )
            number += 1
            collected.setdefault(company.code, []).append(evidence)

    results: list[StockConsensus] = []
    for code, mentions in collected.items():
        speakers = {" ".join(item.speaker.split()).casefold() for item in mentions if item.speaker.strip()}
        programs = {" ".join(item.program.split()).casefold() for item in mentions if item.program.strip()}
        results.append(StockConsensus(code, official[code].name, len(speakers), len(programs), len(mentions), tuple(mentions)))
    return tuple(sorted(results, key=lambda item: (-item.speaker_count, -item.program_count, -item.mention_count, item.stock_code)))


def generate_statistical_report(
    reports: tuple[ResearchReport, ...],
    directory: TaiwanStockDirectory,
    *,
    model: str = "",
    client: ResponsesClient | None = None,
    report_date: date | None = None,
) -> StatisticalReportResult:
    if not reports:
        raise ValueError("請至少選取一份固定研究報告。")
    consensus = build_stock_consensus(reports, directory)
    bearish = build_stock_consensus(reports, directory, direction="偏空")
    ranked = consensus[:10]
    model_name = model.strip() or os.getenv("OPENAI_RESEARCH_AGGREGATION_MODEL", "gpt-4.1-mini")
    narratives = _generate_narratives(ranked, model_name, client)
    markdown = _render_statistical_markdown(reports, consensus, bearish, narratives)
    current_date = report_date or date.today()
    titles = "、".join(_filename_title(report.source.title) for report in reports)
    filename = f"{current_date:%Y%m%d}-多來源統計分析報告({titles}).md"
    return StatisticalReportResult(markdown, filename, "openai", model_name)


def _filename_title(title: str) -> str:
    """Preserve the entered video title while replacing filesystem-invalid characters."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", title).strip(" .") or "未命名影片"


def _generate_narratives(
    ranked: tuple[StockConsensus, ...], model: str, client: ResponsesClient | None
) -> dict[str, dict[str, str]]:
    if not ranked:
        return {}
    if client is None:
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError("openai Python SDK 尚未安裝，無法產生統計分析報告。") from error
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    if not os.getenv("OPENAI_API_KEY") and client.__class__.__name__ == "OpenAI":
        raise RuntimeError("尚未設定 OPENAI_API_KEY。")
    prompt_payload = [
        {
            "stock_code": item.stock_code,
            "company_name": item.company_name,
            "evidence": [
                {
                    "id": evidence.evidence_id,
                    "program": evidence.program or "節目未標示",
                    "video_title": evidence.video_title,
                    "speaker": evidence.speaker or "講者未標示",
                    "direction": evidence.direction,
                    "opinion": evidence.opinion,
                    "rationale": evidence.rationale,
                    "technical_note": evidence.technical_note,
                    "locator": evidence.locator,
                    "quote": evidence.quote,
                }
                for evidence in item.evidence
                if evidence.direction == "偏多"
            ],
        }
        for item in ranked
    ]
    response = client.responses.create(
        model=model,
        instructions=(
            "你只負責將輸入的一份或多份研究報告證據合併成繁體中文看多原因與技術防守摘要。"
            "禁止使用外部知識、網路搜尋或推測；只能改寫 evidence 欄位已提供的內容。"
            "每個原因與防守摘要都必須附上對應 evidence id，格式為〔E0001〕。"
            "若技術防守資料不足，明確寫『來源未提供足夠技術防守依據』，不可自行建議均線、價位或操作。"
            "只輸出 json object，並符合回應中指定的 JSON Schema；禁止加入其他欄位。"
        ),
        input=json.dumps(prompt_payload, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "stock_statistical_report_narratives",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "stocks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "stock_code": {"type": "string"},
                                    "bullish_reason": {"type": "string"},
                                    "technical_defense": {"type": "string"},
                                    "evidence_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": [
                                    "stock_code",
                                    "bullish_reason",
                                    "technical_defense",
                                    "evidence_ids",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["stocks"],
                    "additionalProperties": False,
                },
            }
        },
    )
    payload = json.loads(str(getattr(response, "output_text", "")))
    allowed_codes = {item.stock_code for item in ranked}
    evidence_by_code = {
        item.stock_code: {source.evidence_id for source in item.evidence if source.direction == "偏多"}
        for item in ranked
    }
    narratives: dict[str, dict[str, str]] = {}
    for raw in payload.get("stocks", []):
        code = str(raw.get("stock_code", ""))
        evidence_ids = tuple(str(value) for value in raw.get("evidence_ids", []))
        if code not in allowed_codes or not evidence_ids or not set(evidence_ids) <= evidence_by_code[code]:
            continue
        invalid_citations = {
            value for value in re.findall(r"〔([^〕]+)〕", str(raw.get("bullish_reason", "")) + str(raw.get("technical_defense", "")))
            if value not in evidence_ids
        }
        for key in ("bullish_reason", "technical_defense"):
            text = str(raw.get(key, "")).strip()
            if invalid_citations:
                text = re.sub(r"〔[^〕]+〕", "", text).strip()
            if invalid_citations or (text and not re.search(r"〔E\d{4}〕", text)):
                text += " " + " ".join(f"〔{value}〕" for value in evidence_ids)
            raw[key] = text or "來源未提供足夠資料。"
        if not any(evidence.technical_note.strip() for item in ranked if item.stock_code == code for evidence in item.evidence):
            raw["technical_defense"] = "來源未提供足夠技術防守依據。"
        narratives[code] = raw
    for item in ranked:
        narratives.setdefault(item.stock_code, {
            "bullish_reason": "來源資料不足，未能合併成可靠摘要。",
            "technical_defense": "來源未提供足夠技術防守依據。",
        })
    return narratives


def _render_statistical_markdown(
    reports: tuple[ResearchReport, ...],
    consensus: tuple[StockConsensus, ...],
    bearish: tuple[StockConsensus, ...],
    narratives: dict[str, dict[str, str]],
) -> str:
    lines = [
        "# 多來源統計分析報告", "",
        f"- 納入報告：{len(reports)} 份",
        "- 排名順序：不同講者數 → 不同節目數 → 可追溯提及次數；同分依股票代號排序。",
        "- 股票身分：只納入官方上市／上櫃公司清單可確認的台股。",
        "- 節目數只計入影片頁面可取得的頻道／發布者名稱；無法確認時不猜測，該來源不計入節目數。",
        "- 資料來源：以下所有摘要僅根據已選取報告中的逐字稿分析結果，不查詢外部資料。", "",
        "## 下一個交易日多頭股票 Top 10", "",
    ]
    if not consensus:
        lines.append("所選報告沒有可由官方公司清單確認的偏多股票提及。")
    for rank, item in enumerate(consensus[:10], start=1):
        narrative = narratives.get(item.stock_code, {})
        speakers = "、".join(sorted({e.speaker for e in item.evidence if e.direction == "偏多" and e.speaker})) or "未標示"
        programs = "、".join(sorted({e.program for e in item.evidence if e.direction == "偏多" and e.program})) or "未標示"
        lines.extend([
            f"### {rank}. {item.company_name}（{item.stock_code}）",
            f"- 不同講者數：{item.speaker_count}",
            f"- 不同節目數：{item.program_count}",
            f"- 可追溯提及次數：{item.mention_count}",
            f"- 節目／講者：{programs}／{speakers}",
            f"- 看多原因：{narrative.get('bullish_reason', '來源資料不足。')}",
            f"- 技術與防守點：{narrative.get('technical_defense', '來源未提供足夠技術防守依據。')}",
        ])
        references = [e for e in item.evidence if e.direction == "偏多"]
        lines.append("- 證據：" + "；".join(
            f"〔{e.evidence_id}〕{e.program or '節目未標示'}／{e.speaker or '講者未標示'}（{e.video_title}，{e.locator}）"
            for e in references
        ))
        lines.append("")
    lines.extend(["## 其餘偏多個股", ""])
    others = [item for item in consensus[10:]]
    lines.extend(
        f"- {item.company_name}（{item.stock_code}）：講者 {item.speaker_count}、節目 {item.program_count}、提及 {item.mention_count} 次。"
        for item in others
    )
    if not others:
        lines.append("- 無。")
    lines.extend(["", "## 偏空個股與多空分歧", ""])
    if not bearish:
        lines.append("- 沒有可由官方清單確認的偏空股票提及。")
    for item in bearish:
        lines.append(
            f"- {item.company_name}（{item.stock_code}）：講者 {item.speaker_count}、節目 {item.program_count}、提及 {item.mention_count} 次。"
            + " 證據："
            + "；".join(f"〔{e.evidence_id}〕{e.program or '節目未標示'}／{e.speaker or '講者未標示'}（{e.video_title}，{e.locator}）" for e in item.evidence)
        )
    bull_codes = {item.stock_code for item in consensus}
    both = bull_codes & {item.stock_code for item in bearish}
    lines.extend(["", "多空分歧個股：" + ("、".join(f"{code} {next(i.company_name for i in consensus if i.stock_code == code)}" for code in sorted(both)) if both else "無。")])
    group_sources: dict[str, set[str]] = {}
    group_titles: dict[str, set[str]] = {}
    group_locators: dict[str, set[str]] = {}
    for report in reports:
        for relation in report.stock_relations:
            for group in relation.related_groups:
                if group.strip() and group.strip() != "未判定":
                    group_sources.setdefault(group.strip(), set()).add(report.source.source_id)
                    group_titles.setdefault(group.strip(), set()).add(report.source.title)
                    group_locators.setdefault(group.strip(), set()).add(
                        relation.reference.display_locator() if relation.reference else "未判定"
                    )
    lines.extend(["", "## 跨來源族群共識", ""])
    if group_sources:
        lines.extend(
            f"- {group}：出現在 {len(group_sources[group])} 份來源報告（"
            + "、".join(sorted(group_titles[group]))
            + "；原文位置 " + "、".join(sorted(group_locators[group])) + "）。"
            for group in sorted(group_sources, key=lambda value: (-len(group_sources[value]), value))
        )
    else:
        lines.append("- 來源報告未提供可彙整的族群關聯。")
    classifications = [
        (report.source.title, item)
        for report in reports for item in report.entity_classifications
        if item.entity_type != "taiwan_stock"
    ]
    classification_labels = {
        "foreign_stock": "外國股票",
        "etf": "ETF",
        "sector": "族群／主題",
        "non_stock": "非股票（排除）",
    }
    lines.extend(["", "## 已人工分類的非台股項目", ""])
    lines.extend(
        f"- {title}｜{classification_labels.get(item.entity_type, item.entity_type)}："
        f"{' '.join(value for value in (item.canonical_code, item.canonical_name) if value) or ' '.join(value for value in (item.raw_code, item.raw_name) if value)}"
        f"（原始提及：{' '.join(value for value in (item.raw_code, item.raw_name) if value)}；{item.source_locator}）"
        for title, item in classifications
    )
    if not classifications:
        lines.append("- 無。")
    risks = [(report.source.title, risk) for report in reports for risk in report.risks_and_counterexamples if risk.strip() and risk != "未判定"]
    lines.extend(["", "## 來源中的風險與反例", ""])
    lines.extend(f"- {title}：{risk}" for title, risk in risks)
    if not risks:
        lines.append("- 來源報告未提供。")
    lines.extend(["", "## 待查核項目", ""])
    unresolved = [
        (report.source.title, issue)
        for report in reports for issue in report.verification_issues
        if issue.status not in {"已查證", "已修正"}
    ]
    lines.extend(
        f"- {title}｜{issue.status}：{issue.target}；{issue.evidence}（{issue.reference.display_locator() if issue.reference else '未判定'}）"
        for title, issue in unresolved
    )
    if not unresolved:
        lines.append("- 無。")
    lines.append("")
    return "\n".join(lines)
