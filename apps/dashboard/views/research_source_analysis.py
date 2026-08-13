from __future__ import annotations

from pathlib import Path

import streamlit as st

from personal_stock_investment_system.research import (
    DEFAULT_OBSIDIAN_INBOX_PATH,
    PhaseOneResearchInput,
    ResearchReportOutputSettings,
    build_research_report_filename,
    run_phase_one_research_source_analysis,
)


INPUT_KIND_OPTIONS = {
    "手動文字／逐字稿": "manual_text",
    "PDF 路徑": "pdf",
    "公開 YouTube URL": "youtube_public",
}


def render_research_source_analysis_page() -> None:
    st.subheader("研究來源分析")
    st.caption("輸入公開影片、PDF 或手動文字，產生第一階段固定格式研究報告。")

    input_label = st.radio("來源類型", tuple(INPUT_KIND_OPTIONS), horizontal=True)
    input_kind = INPUT_KIND_OPTIONS[input_label]

    title = st.text_input("標題", value="")
    publisher = st.text_input("發布者／頻道／機構", value="")
    speaker = st.text_input("主要講者", value="")
    notes = st.text_area("備註", value="", height=80)

    youtube_url = ""
    pdf_path = None
    manual_text = ""
    if input_kind == "youtube_public":
        youtube_url = st.text_input("公開 YouTube URL", value="")
        manual_text = st.text_area("手動逐字稿或摘要 fallback", value="", height=220)
    elif input_kind == "pdf":
        pdf_value = st.text_input("PDF 路徑", value="")
        pdf_path = Path(pdf_value) if pdf_value.strip() else None
    else:
        manual_text = st.text_area("手動文字／逐字稿", value="", height=260)

    st.markdown("### 輸出目的地")
    write_to_obsidian = st.checkbox("輸出到 Obsidian inbox", value=True)
    write_to_custom = st.checkbox("輸出到自選路徑", value=True)
    obsidian_path = st.text_input("Obsidian inbox 路徑", value=str(DEFAULT_OBSIDIAN_INBOX_PATH))
    custom_path = st.text_input("自選輸出路徑", value=str(Path.home() / "Desktop"))

    output_settings = ResearchReportOutputSettings(
        write_to_obsidian_inbox=write_to_obsidian,
        write_to_custom_path=write_to_custom,
        obsidian_inbox_path=Path(obsidian_path),
        custom_output_path=Path(custom_path) if custom_path.strip() else None,
    )

    if st.button("產生研究報告", type="primary"):
        try:
            result = run_phase_one_research_source_analysis(
                PhaseOneResearchInput(
                    input_kind=input_kind,  # type: ignore[arg-type]
                    title=title,
                    manual_text=manual_text,
                    youtube_url=youtube_url,
                    pdf_path=pdf_path,
                    publisher=publisher,
                    speaker=speaker,
                    notes=notes,
                ),
                output_settings=output_settings,
            )
        except Exception as error:  # noqa: BLE001 - Streamlit page should show recoverable user input errors.
            st.error(str(error))
            return

        for status in result.statuses:
            if "transcript_unavailable" in status or "未取得" in status or "未抽取" in status:
                st.warning(status)
            else:
                st.info(status)
        if result.written_outputs:
            for item in result.written_outputs:
                st.success(f"{item.kind}：{item.path}")
        st.markdown("### 研究報告 Markdown")
        st.text_area("研究報告 Markdown", value=result.markdown, height=520)
        st.download_button(
            "下載 Markdown",
            data=result.markdown.encode("utf-8"),
            file_name=build_research_report_filename(result.report),
            mime="text/markdown",
        )
