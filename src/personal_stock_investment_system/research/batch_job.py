"""Run a video-report batch in a process that the dashboard can terminate."""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

from personal_stock_investment_system.research.correction_rules import (
    ResearchCorrectionRuleRepository,
    apply_research_correction_rules,
)
from personal_stock_investment_system.research.markdown import render_research_report
from personal_stock_investment_system.research.quick_video_report import (
    QuickVideoReportBatchItem,
    QuickVideoReportBatchResult,
    QuickVideoReportInput,
    QuickVideoReportResult,
    BrowserSessionAsrInput,
    build_quick_video_report_filename,
    run_quick_video_research_report,
)
from personal_stock_investment_system.research.statistical_report import generate_statistical_report
from personal_stock_investment_system.research.stock_validation import TaiwanStockDirectory


def terminate_video_batch_process(process: Any) -> None:
    """Stop the report worker and its active media converter/downloader."""
    if not process.is_alive() or process.pid is None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        try:
            group_id = os.getpgid(process.pid)
            if group_id == process.pid:
                os.killpg(group_id, signal.SIGTERM)
            else:
                process.terminate()
        except ProcessLookupError:
            return
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)


def run_video_batch_job(
    pending: tuple[tuple[int, QuickVideoReportInput, BrowserSessionAsrInput], ...],
    retained: tuple[QuickVideoReportBatchItem, ...],
    invalid: tuple[tuple[int, str], ...],
    directory: TaiwanStockDirectory | None,
    database_path: Path,
    output_queue: Any,
) -> None:
    """Send progress and finished reports to the parent; no Streamlit calls in this process."""
    if os.name != "nt":
        os.setsid()  # Own process group, so cancellation also stops yt-dlp and ffmpeg children.
    finished = {item.index: item for item in retained}
    try:
        for index, request, browser_input in pending:
            def progress(event, *, current=index):
                output_queue.put(("progress", current, event))

            try:
                result = run_quick_video_research_report(
                    request, browser_input, stock_directory=directory, progress_callback=progress,
                )
            except Exception as error:  # noqa: BLE001 - preserve previously completed reports.
                result = QuickVideoReportResult(
                    request, build_quick_video_report_filename(request), (), error=str(error),
                )
            item = QuickVideoReportBatchItem(index, request, browser_input, result)
            finished[index] = item
            output_queue.put(("item", item))

        output_queue.put(("aggregate", "套用人工查核規則並產生統計分析報告。"))
        rules = ResearchCorrectionRuleRepository(database_path).list_rules() if finished else ()
        corrected = []
        for item in sorted(finished.values(), key=lambda value: value.index):
            original = item.original_result or item.result
            if original.research_result is None:
                corrected.append(item)
                continue
            report = apply_research_correction_rules(original.research_result.report, rules, directory)
            markdown = render_research_report(report)
            analysis = replace(original.research_result.analysis_result, report=report, markdown=markdown)
            research = replace(original.research_result, report=report, markdown=markdown, analysis_result=analysis)
            corrected.append(replace(item, original_result=original, result=replace(original, research_result=research)))
        batch = QuickVideoReportBatchResult(tuple(corrected), invalid)
        reports = tuple(
            item.result.research_result.report for item in batch.items
            if item.result.is_available and item.result.research_result is not None
        )
        if reports and directory is not None:
            try:
                batch = replace(batch, statistical_report=generate_statistical_report(reports, directory))
            except Exception as error:  # noqa: BLE001 - individual reports remain downloadable.
                batch = replace(batch, aggregation_error=str(error))
        output_queue.put(("done", batch))
    except Exception as error:  # noqa: BLE001 - report worker failure to dashboard.
        output_queue.put(("error", str(error)))
