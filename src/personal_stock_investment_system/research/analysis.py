"""Rule-based first-pass analysis for research source text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from personal_stock_investment_system.research.sources import (
    CompanyProfileNote,
    OpinionDirection,
    ResearchReport,
    ResearchSource,
    SourceReference,
    StockOpinion,
    StockRelation,
    TechnicalAnalysisNote,
    VerifiableHypothesis,
)

GROUP_KEYWORDS = (
    "AI 伺服器",
    "半導體",
    "IC 設計",
    "PCB",
    "散熱",
    "軍工",
    "電動車",
    "生技",
    "金融",
    "航運",
)
TECHNICAL_KEYWORDS = (
    "突破",
    "回測",
    "均線",
    "季線",
    "月線",
    "成交量放大",
    "爆量",
    "帶量長紅",
    "跳空",
    "箱型整理",
    "頭部",
    "底部",
    "壓力",
    "支撐",
)
BULLISH_KEYWORDS = ("偏多", "看好", "受惠", "正向", "帶動", "機會", "突破", "成長")
BEARISH_KEYWORDS = ("偏空", "看壞", "下跌", "風險", "衰退", "估值過高", "題材退潮", "轉弱")
NEUTRAL_KEYWORDS = ("中性", "觀望", "等待", "不追價", "留意")
RISK_KEYWORDS = ("風險", "估值", "庫存", "衰退", "不追價", "轉弱", "跌破")
CHART_CONTEXT_KEYWORDS = ("這張圖", "這裡", "這根 K", "這根K", "圖面", "K 線", "K線")


@dataclass(frozen=True)
class TextChunk:
    text: str
    locator_type: str = "unknown"
    locator: str = ""


@dataclass(frozen=True)
class StockMention:
    stock: str
    company: str


def analyze_research_source(source: ResearchSource) -> ResearchReport:
    chunks = _source_chunks(source)
    mentions = _mentions_by_stock(chunks)
    stock_opinions = _stock_opinions(source, chunks)
    stock_relations = _stock_relations(source, chunks, mentions)
    company_profiles = _company_profiles(source, chunks, mentions)
    technical_notes = _technical_notes(source, chunks, mentions)
    hypotheses = _hypotheses(stock_opinions, stock_relations, technical_notes)
    risks = _risks(chunks)
    open_questions = _open_questions(company_profiles, stock_opinions)

    return ResearchReport(
        source=source,
        summary=_summary(stock_opinions),
        stock_opinions=stock_opinions,
        stock_relations=stock_relations,
        company_profiles=company_profiles,
        technical_notes=technical_notes,
        hypotheses=hypotheses,
        risks_and_counterexamples=risks,
        open_questions=open_questions,
        next_actions=_next_actions(open_questions, hypotheses),
    )


def _source_chunks(source: ResearchSource) -> tuple[TextChunk, ...]:
    text = source.raw_text or source.markdown_text
    chunks: list[TextChunk] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        timestamp_match = re.match(r"^\[(?P<locator>\d{2}:\d{2}(?::\d{2})?)\]\s*(?P<text>.+)$", stripped)
        if timestamp_match:
            chunks.extend(_sentence_chunks(timestamp_match.group("text"), "timestamp", timestamp_match.group("locator")))
            continue
        page_match = re.match(r"^\[第\s*(?P<page>\d+)\s*頁\]\s*(?P<text>.*)$", stripped)
        if page_match:
            locator = f"第 {page_match.group('page')} 頁"
            remainder = page_match.group("text")
            if remainder:
                chunks.extend(_sentence_chunks(remainder, "page", locator))
            continue
        chunks.extend(_sentence_chunks(stripped, "unknown", ""))
    return tuple(chunks)


def _sentence_chunks(text: str, locator_type: str, locator: str) -> list[TextChunk]:
    return [
        TextChunk(sentence.strip(), locator_type, locator)
        for sentence in re.split(r"(?<=[。！？!?；;])\s*", text)
        if sentence.strip()
    ]


def _mentions_by_stock(chunks: tuple[TextChunk, ...]) -> dict[str, StockMention]:
    mentions: dict[str, StockMention] = {}
    for chunk in chunks:
        for mention in _stock_mentions(chunk.text):
            if mention.stock not in mentions or (not mentions[mention.stock].company and mention.company):
                mentions[mention.stock] = mention
    return mentions


def _stock_mentions(text: str) -> tuple[StockMention, ...]:
    mentions: dict[str, StockMention] = {}
    for match in re.finditer(r"(?P<company>[\u4e00-\u9fffA-Za-z]{2,12})[（(](?P<stock>\d{4})[)）]", text):
        mentions[match.group("stock")] = StockMention(match.group("stock"), match.group("company"))
    for match in re.finditer(r"(?P<stock>\d{4})\s*(?P<company>[\u4e00-\u9fffA-Za-z]{2,12})?(?=[，,。；;：:\s]|$)", text):
        stock = match.group("stock")
        company = _clean_company(match.group("company") or "") or mentions.get(stock, StockMention(stock, "")).company
        mentions[stock] = StockMention(stock, company)
    return tuple(mentions.values())


def _stock_opinions(source: ResearchSource, chunks: tuple[TextChunk, ...]) -> tuple[StockOpinion, ...]:
    opinions: list[StockOpinion] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in chunks:
        for mention in _stock_mentions(chunk.text):
            direction = _direction(chunk.text)
            if direction == "未判定" and not any(keyword in chunk.text for keyword in (*TECHNICAL_KEYWORDS, *RISK_KEYWORDS)):
                continue
            speaker = _speaker(source, chunk.text)
            key = (speaker, mention.stock, chunk.text)
            if key in seen:
                continue
            seen.add(key)
            opinions.append(
                StockOpinion(
                    speaker=speaker,
                    stock=mention.stock,
                    company=mention.company,
                    direction=direction,
                    opinion=_opinion_text(chunk.text),
                    rationale=_rationale(chunk.text),
                    reference=_reference(source, chunk),
                    confidence="中" if direction != "未判定" else "低",
                )
            )
    return tuple(opinions)


def _stock_relations(
    source: ResearchSource,
    chunks: tuple[TextChunk, ...],
    mentions: dict[str, StockMention],
) -> tuple[StockRelation, ...]:
    relations: dict[str, StockRelation] = {}
    for chunk in chunks:
        groups = tuple(group for group in GROUP_KEYWORDS if group in chunk.text)
        if not groups:
            continue
        chunk_mentions = _stock_mentions(chunk.text)
        for mention in chunk_mentions:
            related_companies = _related_companies(chunk.text, chunk_mentions, mention.company)
            relations[mention.stock] = StockRelation(
                stock=mention.stock,
                company=mention.company or mentions.get(mention.stock, StockMention(mention.stock, "")).company,
                related_groups=groups,
                related_companies=related_companies or ("未判定",),
                rationale="原文提及：" + "、".join(groups),
                reference=_reference(source, chunk),
            )
    return tuple(relations.values())


def _company_profiles(
    source: ResearchSource,
    chunks: tuple[TextChunk, ...],
    mentions: dict[str, StockMention],
) -> tuple[CompanyProfileNote, ...]:
    profiles: dict[str, CompanyProfileNote] = {}
    for stock, mention in mentions.items():
        profile_chunk = _first_chunk(chunks, stock, ("主要業務", "產品", "服務", "做的是"))
        if profile_chunk:
            profiles[stock] = CompanyProfileNote(
                stock=stock,
                company=mention.company,
                main_business=_business_text(profile_chunk.text),
                products_or_services=_products_text(profile_chunk.text),
                customers_or_markets="待查證",
                needs_verification="來源提及，仍待查證",
                reference=_reference(source, profile_chunk),
            )
        else:
            profiles[stock] = CompanyProfileNote(
                stock=stock,
                company=mention.company,
                reference=_reference(source, _first_stock_chunk(chunks, stock)),
            )
    return tuple(profiles.values())


def _technical_notes(
    source: ResearchSource,
    chunks: tuple[TextChunk, ...],
    mentions: dict[str, StockMention],
) -> tuple[TechnicalAnalysisNote, ...]:
    notes: list[TechnicalAnalysisNote] = []
    for chunk in chunks:
        signals = tuple(keyword for keyword in TECHNICAL_KEYWORDS if keyword in chunk.text)
        if not signals:
            continue
        for mention in _stock_mentions(chunk.text):
            notes.append(
                TechnicalAnalysisNote(
                    stock=mention.stock,
                    signal="、".join(signals),
                    chart_context=_chart_context(chunk.text),
                    rationale=_opinion_text(chunk.text),
                    missing_data=_missing_chart_data(chunk.text),
                    reference=_reference(source, chunk),
                )
            )
    if notes:
        return tuple(notes)
    return ()


def _hypotheses(
    opinions: tuple[StockOpinion, ...],
    relations: tuple[StockRelation, ...],
    technical_notes: tuple[TechnicalAnalysisNote, ...],
) -> tuple[VerifiableHypothesis, ...]:
    hypotheses: list[VerifiableHypothesis] = []
    relation_by_stock = {relation.stock: relation for relation in relations}
    technical_by_stock = {note.stock: note for note in technical_notes}
    for opinion in opinions:
        relation = relation_by_stock.get(opinion.stock)
        if relation and opinion.direction in {"偏多", "中性"}:
            group_text = "、".join(group for group in relation.related_groups if group != "未判定") or "相關族群"
            target = opinion.company or opinion.stock
            hypotheses.append(
                VerifiableHypothesis(
                    hypothesis=f"{group_text}需求或題材升溫時，{target}可能相對受惠。",
                    required_data=f"{group_text}需求指標、{target}營收、股價相對強弱",
                    backtestable="可",
                    initial_rule="題材或營收成長且股價相對大盤轉強",
                    confidence="中",
                )
            )
        technical = technical_by_stock.get(opinion.stock)
        if technical:
            hypotheses.append(
                VerifiableHypothesis(
                    hypothesis=f"{opinion.stock}出現{technical.signal}時，後續強弱可被驗證。",
                    required_data="OHLCV、均線、成交量",
                    backtestable="可",
                    initial_rule=f"觀察{technical.signal}後 5 至 20 日報酬與回撤",
                    confidence="中",
                )
            )
    return _unique_hypotheses(hypotheses)


def _risks(chunks: tuple[TextChunk, ...]) -> tuple[str, ...]:
    risks = [_opinion_text(chunk.text) for chunk in chunks if any(keyword in chunk.text for keyword in RISK_KEYWORDS)]
    return tuple(dict.fromkeys(risks)) or ("未判定",)


def _open_questions(
    profiles: tuple[CompanyProfileNote, ...],
    opinions: tuple[StockOpinion, ...],
) -> tuple[str, ...]:
    questions: list[str] = []
    for profile in profiles:
        if profile.main_business.startswith("待查證"):
            target = profile.company or profile.stock
            questions.append(f"{target}的主要業務與營收占比需要查證。")
    if any(opinion.direction == "中性" for opinion in opinions):
        questions.append("中性或觀望結論需要哪些價格、營收或估值資料確認？")
    return tuple(dict.fromkeys(questions)) or ("未判定",)


def _next_actions(
    open_questions: tuple[str, ...],
    hypotheses: tuple[VerifiableHypothesis, ...],
) -> tuple[str, ...]:
    actions: list[str] = []
    if open_questions != ("未判定",):
        actions.append("查證待查問題中的公司業務、營收占比與估值資料。")
    if hypotheses:
        actions.append("整理假設所需資料，評估是否可進入後續回測或人工驗證。")
    return tuple(actions) or ("未判定",)


def _summary(opinions: tuple[StockOpinion, ...]) -> str:
    if not opinions:
        return "未判定"
    parts = [f"{opinion.speaker}對{opinion.company or opinion.stock}為{opinion.direction}" for opinion in opinions[:3]]
    return "；".join(parts) + "。"


def _direction(text: str) -> OpinionDirection:
    has_bullish = any(keyword in text for keyword in BULLISH_KEYWORDS)
    has_bearish = any(keyword in text for keyword in BEARISH_KEYWORDS)
    has_neutral = any(keyword in text for keyword in NEUTRAL_KEYWORDS)
    if has_neutral or (has_bullish and has_bearish):
        return "中性"
    if has_bullish:
        return "偏多"
    if has_bearish:
        return "偏空"
    return "未判定"


def _speaker(source: ResearchSource, text: str) -> str:
    for speaker in source.speakers:
        if speaker and speaker in text:
            return speaker
    if source.speaker and source.speaker in text:
        return source.speaker
    match = re.search(r"(主持人|研究員|分析師|來賓|講者|法人)\s*[A-Za-z0-9\u4e00-\u9fff]*", text)
    if match:
        return match.group(0).strip()
    return source.display_speakers() or "未判定"


def _opinion_text(text: str) -> str:
    return text.strip(" 。；;")


def _rationale(text: str) -> str:
    matched = [keyword for keyword in (*GROUP_KEYWORDS, *TECHNICAL_KEYWORDS, *RISK_KEYWORDS) if keyword in text]
    if matched:
        return "原文提到：" + "、".join(dict.fromkeys(matched))
    return "原文提及股票觀點"


def _reference(source: ResearchSource, chunk: TextChunk | None) -> SourceReference | None:
    if chunk is None:
        return None
    return SourceReference(
        source_id=source.source_id,
        locator_type=chunk.locator_type,  # type: ignore[arg-type]
        locator=chunk.locator,
        quote=chunk.text,
        confidence="中",
    )


def _related_companies(text: str, mentions: tuple[StockMention, ...], own_company: str) -> tuple[str, ...]:
    companies = [mention.company for mention in mentions if mention.company and mention.company != own_company]
    for match in re.finditer(r"(?:關聯公司|供應鏈包含|供應鏈包括)[:：]?\s*([^。；;，,]+(?:、[^。；;，,]+)*)", text):
        companies.extend(part.strip() for part in re.split(r"[、,，]", match.group(1)) if part.strip())
    return tuple(dict.fromkeys(companies))


def _clean_company(company: str) -> str:
    cleaned = company.strip()
    for marker in ("主要業務", "供應鏈", "帶量", "突破", "受惠", "題材", "需求", "風險"):
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[0]
    return cleaned


def _first_chunk(chunks: tuple[TextChunk, ...], stock: str, keywords: tuple[str, ...]) -> TextChunk | None:
    for chunk in chunks:
        if stock in chunk.text and any(keyword in chunk.text for keyword in keywords):
            return chunk
    return None


def _first_stock_chunk(chunks: tuple[TextChunk, ...], stock: str) -> TextChunk | None:
    for chunk in chunks:
        if stock in chunk.text:
            return chunk
    return None


def _business_text(text: str) -> str:
    match = re.search(r"(?:主要業務是|主要業務為|做的是)([^。；;]+)", text)
    if match:
        return match.group(1).strip(" ：:")
    return _opinion_text(text)


def _products_text(text: str) -> str:
    match = re.search(r"(?:產品是|產品為|產品包含|服務是|服務為)([^。；;]+)", text)
    if match:
        return match.group(1).strip(" ：:")
    return "來源提及，待結構化"


def _chart_context(text: str) -> str:
    if any(keyword in text for keyword in CHART_CONTEXT_KEYWORDS):
        return "需要人工補圖：原文提到圖面，但逐字稿未包含畫面資訊。"
    return "來源文字描述技術訊號，未含圖面。"


def _missing_chart_data(text: str) -> str:
    if any(keyword in text for keyword in CHART_CONTEXT_KEYWORDS):
        return "K 線截圖"
    return "未判定"


def _unique_hypotheses(hypotheses: list[VerifiableHypothesis]) -> tuple[VerifiableHypothesis, ...]:
    seen: set[str] = set()
    unique: list[VerifiableHypothesis] = []
    for hypothesis in hypotheses:
        if hypothesis.hypothesis in seen:
            continue
        seen.add(hypothesis.hypothesis)
        unique.append(hypothesis)
    return tuple(unique)
