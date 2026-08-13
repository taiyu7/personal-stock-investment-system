from personal_stock_investment_system.research import ResearchSource, analyze_research_source, render_research_report


def test_fixed_transcript_can_be_analyzed_into_fixed_markdown_report():
    source = ResearchSource(
        source_id="src_analysis_sample",
        source_type="manual_text",
        title="AI 伺服器與台股供應鏈逐字稿",
        publisher="公開財經頻道",
        speakers=("主持人 C", "研究員 A", "分析師 B"),
        collected_at="2026-08-13T09:00:00+00:00",
        raw_text="\n".join(
            [
                "[00:01:23] 研究員 A 認為 2330 台積電：AI 伺服器需求帶動半導體，方向偏多。",
                "[00:02:10] 研究員 A 說 2330 台積電主要業務是晶圓代工，產品包含先進製程服務。",
                "[00:03:05] 分析師 B 提醒 2382 廣達：AI 伺服器題材正向，但短線估值風險升高，方向中性。",
                "[00:04:00] 分析師 B 看這張圖，2382 廣達帶量長紅突破月線，但需要回測支撐。",
                "[00:05:15] 主持人 C 補充 2382 廣達供應鏈包含緯創、英業達，屬於AI 伺服器族群。",
            ]
        ),
    )

    report = analyze_research_source(source)
    markdown = render_research_report(report)

    assert markdown.startswith("# 研究來源分析報告")
    assert "## 人物對股票的評價" in markdown
    assert "| 研究員 A | 2330 | 台積電 | 偏多 |" in markdown
    assert "| 分析師 B | 2382 | 廣達 | 中性 |" in markdown
    assert "00:01:23" in markdown
    assert "00:03:05" in markdown
    assert "## 股票與族群關聯" in markdown
    assert "| 2330 | 台積電 | AI 伺服器、半導體 |" in markdown
    assert "| 2382 | 廣達 | AI 伺服器 | 緯創、英業達" in markdown
    assert "## 提到的公司是做什麼的" in markdown
    assert "| 2330 | 台積電 | 晶圓代工，產品包含先進製程服務 | 先進製程服務 |" in markdown
    assert "| 2382 | 廣達 | 待查證：來源未說明公司主要業務。 | 待查證 |" in markdown
    assert "## 技術分析" in markdown
    assert "| 2382 | 突破、回測、月線、帶量長紅、支撐 | 需要人工補圖" in markdown
    assert "## 可驗證假設" in markdown
    assert "AI 伺服器、半導體需求或題材升溫時，台積電可能相對受惠。" in markdown
    assert "2382出現突破、回測、月線、帶量長紅、支撐時，後續強弱可被驗證。" in markdown
    assert "## 風險與反例" in markdown
    assert "短線估值風險升高" in markdown
    assert "## 待查問題" in markdown
    assert "廣達的主要業務與營收占比需要查證。" in markdown


def test_analysis_marks_unknown_values_instead_of_guessing():
    source = ResearchSource(
        source_id="src_unknown_analysis",
        source_type="manual_text",
        title="缺資訊來源",
        raw_text="[00:00:10] 主持人 C 今天提到市場很熱鬧，但沒有說明股票與理由。",
    )

    report = analyze_research_source(source)
    markdown = render_research_report(report)

    assert report.summary == "未判定"
    assert report.stock_opinions == ()
    assert "## 一句話摘要\n\n未判定" in markdown
    assert "## 風險與反例\n\n- 未判定" in markdown
    assert "## 待查問題\n\n- 未判定" in markdown
