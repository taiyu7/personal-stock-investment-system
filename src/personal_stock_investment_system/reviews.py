"""Daily review formatting shared by the dashboard and future AI workflows."""

from __future__ import annotations

from personal_stock_investment_system.market_data.service import MarketReport, QuoteSnapshot


def format_snapshot_line(snapshot: QuoteSnapshot) -> str:
    if snapshot.price is None:
        return f"{snapshot.name}：資料不足"
    if snapshot.change is None or snapshot.change_percent is None:
        return f"{snapshot.name}：{snapshot.price:,.2f}"
    return f"{snapshot.name}：{snapshot.price:,.2f} ({snapshot.change:+,.2f} / {snapshot.change_percent:+.2f}%)"


def build_market_note(report: MarketReport) -> str:
    lines = [f"市場總結：{report.summary.label}", report.summary.reason, ""]
    for section in report.sections:
        lines.extend([f"{section.section.title}：{section.signal.label}", section.signal.reason])
        lines.extend(format_snapshot_line(snapshot) for snapshot in section.snapshots)
        lines.append("")
    return "\n".join(lines).strip()


def build_daily_review_text(trade_date: str, fields: dict[str, str]) -> str:
    def value(key: str) -> str:
        return fields.get(key, "").strip() or "（待補）"

    return f"""# {trade_date} 股市交易紀錄

## 盤前功課

### 前日市場資料
{value("market_note")}

### 重大新聞／財報／法說／政策題材
{value("premarket_news")}

### 持股狀況分析
{value("holding_analysis")}

### 持股水位
{value("holding_level_before")}

### 昨日主流族群
{value("yesterday_groups")}

## 盤後復盤

### 市場狀態
{value("market_status")}

### 今日強勢族群
{value("strong_groups")}

### 是否符合盤前劇本
{value("plan_match")}

### 今日交易紀錄（股票／進出場／結果）
{value("trade_records")}

### 持股水位
{value("holding_level_after")}

### 做對的事
{value("good_actions")}

### 犯的錯
{value("mistakes")}

### 情緒狀態與備註
{value("emotion_notes")}
"""
