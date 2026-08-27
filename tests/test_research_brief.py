from personal_stock_investment_system.research import (
    BriefDefenseNote,
    BriefStockNote,
    BriefVerificationSource,
    InvestmentBrief,
    ResearchSource,
    SourceReference,
    render_investment_brief,
)


def test_investment_brief_renders_defense_table_separately():
    source = ResearchSource(
        source_id="src_brief",
        source_type="local_audio",
        title="股市情報局逐字稿",
        source_url="https://www.youtube.com/watch?v=example",
        raw_text="",
    )
    reference = SourceReference(
        source_id=source.source_id,
        locator_type="timestamp",
        locator="00:01:23",
        quote="大立光跳空缺口不封閉續抱",
        confidence="中",
    )
    brief = InvestmentBrief(
        source=source,
        market_context="影片提到資金回流電子股。",
        stock_notes=(
            BriefStockNote(
                stock="3008",
                company="大立光",
                group="CPO 光學",
                trend="跳空創高",
                reason="影片提到 CPO 題材與擴產",
                reference=reference,
                confidence="中",
            ),
        ),
        defense_notes=(
            BriefDefenseNote(
                stock="3008",
                company="大立光",
                group="CPO 光學",
                base_position="高位階噴出",
                support_or_entry="跳空缺口",
                action_note="影片提到缺口不封閉續抱",
                needs_verification="是",
                reference=reference,
            ),
        ),
        verification_sources=(
            BriefVerificationSource(
                title="公開資訊觀測站",
                url="https://mops.twse.com.tw/",
                used_for="查證公司公告",
            ),
        ),
        risks=("高位階個股若爆量不漲需留意。",),
        next_actions=("回查逐字稿確認防守點是否為講者原話。",),
    )

    markdown = render_investment_brief(brief)

    assert markdown.startswith("# 影片投資情報摘要")
    assert "## 影片提到的股票" in markdown
    assert "## 主流股基期防守表" in markdown
    assert "| 3008 | 大立光 | CPO 光學 | 高位階噴出 | 跳空缺口 |" in markdown
    assert "## 查證來源" in markdown
    assert "| 公開資訊觀測站 | https://mops.twse.com.tw/ | 查證公司公告 |" in markdown
