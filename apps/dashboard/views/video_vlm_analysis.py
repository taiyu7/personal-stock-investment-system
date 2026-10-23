from __future__ import annotations

import os
import math
from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import uuid4

import streamlit as st

from personal_stock_investment_system.research import (
    DEFAULT_OBSIDIAN_INBOX_PATH,
    DEFAULT_OPENAI_VLM_MODEL,
    PhaseOneResearchInput,
    ResearchAnalysisSettings,
    ResearchReportOutputSettings,
    ScreenshotRequest,
    SourceReference,
    VlmChartAnalysisSettings,
    VideoResearchReportInput,
    VideoResearchReportResult,
    analyze_screenshot_capture,
    build_research_report_filename,
    capture_requested_screenshots,
    load_asr_transcription_result,
    run_phase_one_research_source_analysis,
    run_video_research_report_pipeline,
)
from personal_stock_investment_system.research.media import MediaArtifact
from personal_stock_investment_system.research.stock_validation import verify_research_report_stock_mentions
from personal_stock_investment_system.storage import TaiwanStockRepository, sqlite_database_path


TRANSCRIPT_ANALYSIS_PROVIDERS = {
    "本機規則整理": "rule_based_fallback",
    "OpenAI 研究整理": "openai",
}

VLM_PROVIDERS = {
    "只擷取截圖，稍後再分析": "none",
    "OpenAI 雲端 VLM": "openai",
    "本機 VLM（尚未設定）": "local",
}

OUTPUT_DESTINATIONS = ("只在頁面預覽／下載", "Obsidian inbox", "自選資料夾")


def parse_screenshot_request_lines(text: str, source_id: str) -> tuple[ScreenshotRequest, ...]:
    requests: list[ScreenshotRequest] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split("|", maxsplit=2)]
        if len(fields) < 2:
            raise ValueError(f"第 {line_number} 行格式錯誤，請使用「秒數 | 截圖理由 | 逐字稿引用」。")
        try:
            timestamp = float(fields[0])
        except ValueError as error:
            raise ValueError(f"第 {line_number} 行的秒數不是有效數字。") from error
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError(f"第 {line_number} 行的秒數必須是有限的非負數。")
        reason = fields[1]
        if not reason:
            raise ValueError(f"第 {line_number} 行請填寫截圖理由。")
        quote = fields[2] if len(fields) == 3 else ""
        reference = SourceReference(
            source_id=source_id,
            locator_type="timestamp",
            locator=format_video_timestamp(timestamp),
            quote=quote,
            confidence="未判定",
        )
        requests.append(
            ScreenshotRequest(
                timestamp_seconds=timestamp,
                reason=reason,
                quote=quote,
                reference=reference,
            )
        )
    if not requests:
        raise ValueError("請至少輸入一筆截圖時間戳。")
    return tuple(requests)


def format_video_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"


def _resolve_output_settings(destination: str, custom_path: str) -> ResearchReportOutputSettings:
    if destination == "Obsidian inbox":
        return ResearchReportOutputSettings(
            write_to_obsidian_inbox=True,
            write_to_custom_path=False,
            obsidian_inbox_path=DEFAULT_OBSIDIAN_INBOX_PATH,
        )
    if destination == "自選資料夾":
        return ResearchReportOutputSettings(
            write_to_obsidian_inbox=False,
            write_to_custom_path=bool(custom_path.strip()),
            custom_output_path=Path(custom_path).expanduser() if custom_path.strip() else None,
        )
    return ResearchReportOutputSettings.no_local_files()


def _render_pipeline_result(result: VideoResearchReportResult) -> None:
    if result.status == "available":
        st.success("報告已產生。")
    else:
        st.warning("報告目前不完整，後續仍需補資料或人工查證。")
    if result.missing_items:
        st.write("待補項目：" + "、".join(result.missing_items))

    for index, capture in enumerate(st.session_state.get("video_vlm_screenshot_results", ()), start=1):
        with st.container(border=True):
            st.markdown(f"#### 截圖 {index} · {format_video_timestamp(capture.request.timestamp_seconds)}")
            if not capture.is_available() or capture.artifact is None:
                st.warning(capture.status_message or capture.status)
                if capture.error:
                    st.code(capture.error, language=None)
                continue
            st.image(str(capture.artifact.path), caption=capture.artifact.reason)
            st.caption(f"路徑：{capture.artifact.path}")
            st.caption(f"來源引用：{capture.artifact.quote or '未提供'}")

    st.markdown("### 研究報告預覽")
    st.text_area("Markdown 內容", value=result.markdown, height=560, key="video_vlm_report_markdown")
    st.download_button(
        "下載 Markdown 報告",
        data=result.markdown.encode("utf-8"),
        file_name=build_research_report_filename(result.report, report_date=date.today()),
        mime="text/markdown",
        key="download_video_vlm_report",
    )
    for item in result.written_outputs:
        st.success(f"已輸出到 {item.kind}：{item.path}")


def render_video_vlm_analysis_page() -> None:
    st.subheader("投顧影片VLM 技術分析")
    st.warning("此頁面目前為未完成版本：流程已接上截圖、VLM 與報告 adapter，後續仍需優化與人工驗收。")
    st.info("後續優先優化項目：研究來源分析頁面。")
    st.caption(
        "目前支援合法本機影片與既有 ASR 逐字稿 JSON。頁面可依時間戳擷取截圖，選擇是否執行 VLM，並產生完整研究報告。"
    )
    st.caption("Docker Dashboard 請先將影片放在專案 data/raw/videos/，路徑使用 data/raw/videos/檔名.mp4。")

    with st.form("video_vlm_pipeline_form"):
        video_path_value = st.text_input(
            "本機影片路徑",
            value=st.session_state.get("video_vlm_video_path", ""),
            placeholder="data/raw/videos/advisor-video.mp4",
        )
        transcript_path_value = st.text_input(
            "ASR 逐字稿 JSON 路徑",
            value=st.session_state.get("research_asr_transcript_json_path", ""),
            placeholder="data/processed/asr-transcripts/openai/advisor-video.json",
            help="可先在「研究來源分析」產生逐字稿，再回到本頁；也可直接輸入已有逐字稿路徑。",
        )
        source_url = st.text_input(
            "影片來源 URL（選填）",
            value=st.session_state.get("research_asr_source_url", ""),
        )
        title = st.text_input("影片標題（選填）", value="")
        timestamp_lines = st.text_area(
            "截圖時間戳與引用",
            value="",
            height=130,
            placeholder="83.25 | 確認支撐壓力與成交量 | 講者原文引用\n126 | 確認型態 |",
            help="每行一筆，格式為「秒數 | 截圖理由 | 逐字稿引用」。至少需要一筆。",
        )

        st.markdown("#### 逐字稿研究整理")
        analysis_label = st.selectbox("整理方式", tuple(TRANSCRIPT_ANALYSIS_PROVIDERS), index=0)
        analysis_provider = TRANSCRIPT_ANALYSIS_PROVIDERS[analysis_label]
        analysis_model = st.text_input(
            "研究整理模型",
            value=os.getenv("OPENAI_RESEARCH_ANALYSIS_MODEL", "gpt-4.1-mini")
            if analysis_provider == "openai"
            else "rule_based_v1",
        )
        analysis_opt_in = False
        if analysis_provider == "openai":
            st.warning("選擇 OpenAI 研究整理後，逐字稿內容會傳送至 OpenAI。")
            analysis_opt_in = st.checkbox("我同意將逐字稿送至 OpenAI 進行研究整理。", value=False)

        st.markdown("#### VLM 圖面分析")
        vlm_label = st.selectbox("VLM provider", tuple(VLM_PROVIDERS), index=0)
        vlm_provider = VLM_PROVIDERS[vlm_label]
        vlm_model = st.text_input(
            "VLM 模型",
            value=os.getenv("OPENAI_VLM_MODEL", DEFAULT_OPENAI_VLM_MODEL)
            if vlm_provider == "openai"
            else ("未設定" if vlm_provider == "local" else "未執行"),
        )
        vlm_opt_in = False
        if vlm_provider == "openai":
            st.warning("選擇 OpenAI 雲端 VLM 後，每張截圖及對應 timestamp、理由與逐字稿引用都會傳送到 OpenAI。")
            vlm_opt_in = st.checkbox("我同意將本次截圖與引用送至 OpenAI VLM。", value=False)
        elif vlm_provider == "local":
            st.info("本機 VLM adapter 尚未設定，執行後會回傳 unsupported_provider。")

        st.markdown("#### 報告輸出")
        output_destination = st.selectbox("輸出目的地", OUTPUT_DESTINATIONS, index=0)
        custom_output_path = ""
        if output_destination == "自選資料夾":
            custom_output_path = st.text_input("自選輸出資料夾", value="")
        submitted = st.form_submit_button("擷取截圖並產生報告", type="primary")

    if submitted:
        if analysis_provider == "openai" and not analysis_opt_in:
            st.error("請先確認是否同意將逐字稿傳送給 OpenAI。")
            return
        if vlm_provider == "openai" and not vlm_opt_in:
            st.error("請先確認是否同意將截圖與引用傳送給 OpenAI VLM。")
            return
        video_path = Path(video_path_value).expanduser()
        transcript_path = Path(transcript_path_value).expanduser()
        if not video_path.is_file():
            st.error("找不到本機影片檔，請確認目前 Dashboard 執行環境可讀取該路徑。")
            return
        if not transcript_path.is_file():
            st.error("找不到 ASR 逐字稿 JSON，請先在「研究來源分析」產生逐字稿，或確認路徑。")
            return
        if analysis_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            st.error("尚未設定 OPENAI_API_KEY，無法執行 OpenAI 研究整理。")
            return
        if vlm_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            st.error("尚未設定 OPENAI_API_KEY，無法執行 OpenAI VLM。")
            return
        if output_destination == "自選資料夾" and not custom_output_path.strip():
            st.error("請輸入自選報告輸出資料夾。")
            return
        try:
            transcript = load_asr_transcription_result(transcript_path)
            if not transcript.segments:
                raise ValueError(transcript.status_message or "逐字稿沒有可用段落。")
            analysis_result = run_phase_one_research_source_analysis(
                PhaseOneResearchInput(
                    input_kind="asr_transcript_json",
                    title=title.strip() or transcript_path.stem,
                    transcript_json_path=transcript_path,
                    source_url=source_url.strip(),
                ),
                output_settings=ResearchReportOutputSettings.no_local_files(),
                analysis_settings=ResearchAnalysisSettings(
                    provider=analysis_provider,  # type: ignore[arg-type]
                    model=analysis_model.strip(),
                    enable_web_search=False,
                    report_style="structured_report",
                ),
            )
            source = replace(analysis_result.source, source_type="local_video")
            report = replace(analysis_result.report, source=source)
            report_analysis = replace(analysis_result.analysis_result, report=report)
            stock_directory = TaiwanStockRepository(sqlite_database_path()).load_directory()
            if stock_directory is not None:
                report = verify_research_report_stock_mentions(report, stock_directory)
                report_analysis = replace(report_analysis, report=report)
            requests = parse_screenshot_request_lines(timestamp_lines, source.source_id)
            output_dir = Path("data/processed/screenshots")
            prefix = f"vlm-{uuid4().hex[:8]}"
            with st.status("正在擷取截圖並整理報告…", expanded=True) as status:
                captures = capture_requested_screenshots(
                    video_path,
                    requests,
                    output_dir,
                    filename_prefix=prefix,
                )
                st.write(f"截圖完成：{sum(item.is_available() for item in captures)} / {len(captures)} 張可用。")
                vlm_settings = VlmChartAnalysisSettings(
                    provider=vlm_provider if vlm_provider != "none" else "fake",  # type: ignore[arg-type]
                    model=vlm_model.strip(),
                )
                vlm_results = (
                    tuple(analyze_screenshot_capture(item, settings=vlm_settings) for item in captures)
                    if vlm_provider != "none"
                    else ()
                )
                pipeline_input = VideoResearchReportInput(
                    analysis_result=report_analysis,
                    media_artifact=MediaArtifact(
                        path=video_path.resolve(),
                        source_url=source_url.strip(),
                        artifact_type="video",
                    ),
                    transcription_result=transcript,
                    screenshot_results=captures,
                    vlm_results=vlm_results,
                    asr_backend="由既有 ASR JSON 匯入",
                    asr_model="由逐字稿 JSON 提供",
                )
                result = run_video_research_report_pipeline(
                    pipeline_input,
                    output_settings=_resolve_output_settings(output_destination, custom_output_path),
                )
                status.update(label="影片技術分析報告已產生", state="complete")
            st.session_state["video_vlm_video_path"] = str(video_path)
            st.session_state["video_vlm_screenshot_results"] = captures
            st.session_state["video_vlm_result"] = result
        except Exception as error:  # noqa: BLE001 - show recoverable local input and adapter errors.
            st.error(str(error))
            return

    result = st.session_state.get("video_vlm_result")
    if result is not None:
        _render_pipeline_result(result)

    st.divider()
    st.caption("後續待辦：優先優化「研究來源分析」頁面的流程與操作，再補本頁端到端人工驗收。")
