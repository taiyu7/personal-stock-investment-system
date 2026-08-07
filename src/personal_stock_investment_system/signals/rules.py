"""Rules for classifying market sections as bullish, neutral, or bearish."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


BULLISH = "偏多"
NEUTRAL = "中性"
BEARISH = "偏空"


class SnapshotLike(Protocol):
    change_percent: float | None


@dataclass(frozen=True)
class SectionSignal:
    section_key: str
    label: str
    score: float
    valid_count: int
    reason: str


@dataclass(frozen=True)
class MarketSummary:
    label: str
    score: float
    reason: str


def classify_score(score: float) -> str:
    if score >= 0.35:
        return BULLISH
    if score <= -0.35:
        return BEARISH
    return NEUTRAL


def score_snapshot(snapshot: SnapshotLike, section_key: str) -> float | None:
    if snapshot.change_percent is None:
        return None
    return -snapshot.change_percent if section_key == "macro" else snapshot.change_percent


def build_section_signal(section_key: str, snapshots: list[SnapshotLike]) -> SectionSignal:
    scores = [score for snapshot in snapshots if (score := score_snapshot(snapshot, section_key)) is not None]
    if not scores:
        return SectionSignal(section_key, NEUTRAL, 0, 0, "資料不足，暫以中性看待。")
    average_score = sum(scores) / len(scores)
    label = classify_score(average_score)
    notes = {"global_indices": "全球主要指數反映國際風險偏好。", "ai_semiconductors": "AI 與半導體指標股牽動台股科技族群情緒。", "macro": "美元與美債殖利率上升時，通常對股市估值較不利。", "taiwan_market": "台灣市場與台積電走勢反映本地盤勢動能。"}
    reason = f"{notes.get(section_key, '此區塊反映市場方向。')} 目前以 {len(scores)} 筆有效資料計算，分數 {average_score:+.2f}，判斷為{label}。"
    return SectionSignal(section_key, label, average_score, len(scores), reason)


def build_market_summary(signals: list[SectionSignal]) -> MarketSummary:
    valid_signals = [signal for signal in signals if signal.valid_count > 0]
    if not valid_signals:
        return MarketSummary(NEUTRAL, 0, "目前沒有足夠資料形成市場方向判斷。")
    score = sum(signal.score for signal in valid_signals) / len(valid_signals)
    counts = {label: sum(signal.label == label for signal in valid_signals) for label in (BULLISH, NEUTRAL, BEARISH)}
    reason = f"目前 {counts[BULLISH]} 個區塊偏多、{counts[NEUTRAL]} 個區塊中性、{counts[BEARISH]} 個區塊偏空，整體分數 {score:+.2f}。"
    return MarketSummary(classify_score(score), score, reason)
