"""Research source models and Markdown report rendering."""

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.asr import (
    DEFAULT_BREEZE_ASR_MODEL,
    AsrTranscriptSegment,
    AsrTranscriptionResult,
    BreezeAsrCliConfig,
    BreezeAsrCliTranscriber,
    SpeechToTextClient,
    build_local_audio_research_source,
)
from personal_stock_investment_system.research.entrypoint import (
    PhaseOneResearchInput,
    PhaseOneResearchResult,
    TranscriptUnavailableYouTubeClient,
    run_phase_one_research_source_analysis,
)
from personal_stock_investment_system.research.markdown import (
    build_research_report_filename,
    render_research_report,
)
from personal_stock_investment_system.research.output import (
    DEFAULT_OBSIDIAN_INBOX_PATH,
    ResearchReportOutputDestination,
    ResearchReportOutputSettings,
    WrittenResearchReport,
    default_custom_output_path,
    resolve_research_report_output_destinations,
    write_research_report_outputs,
)
from personal_stock_investment_system.research.pdf import (
    PdfPageText,
    build_pdf_research_source,
    extract_text_pages,
    pdf_to_markdown,
)
from personal_stock_investment_system.research.sources import (
    CompanyProfileNote,
    ResearchReport,
    ResearchSource,
    ResearchSourceImportResult,
    SourceReference,
    SourceImportStatus,
    StockOpinion,
    StockRelation,
    TechnicalAnalysisNote,
    VerifiableHypothesis,
)
from personal_stock_investment_system.research.youtube import (
    YouTubeImportResult,
    YouTubeTranscriptSegment,
    YouTubeVideoMetadata,
    build_youtube_research_source,
    parse_youtube_video_id,
)

__all__ = [
    "CompanyProfileNote",
    "ResearchReport",
    "ResearchSource",
    "ResearchSourceImportResult",
    "SourceReference",
    "SourceImportStatus",
    "StockOpinion",
    "StockRelation",
    "TechnicalAnalysisNote",
    "VerifiableHypothesis",
    "PdfPageText",
    "DEFAULT_BREEZE_ASR_MODEL",
    "AsrTranscriptSegment",
    "AsrTranscriptionResult",
    "BreezeAsrCliConfig",
    "BreezeAsrCliTranscriber",
    "YouTubeImportResult",
    "YouTubeTranscriptSegment",
    "YouTubeVideoMetadata",
    "DEFAULT_OBSIDIAN_INBOX_PATH",
    "PhaseOneResearchInput",
    "PhaseOneResearchResult",
    "ResearchReportOutputDestination",
    "ResearchReportOutputSettings",
    "SpeechToTextClient",
    "TranscriptUnavailableYouTubeClient",
    "WrittenResearchReport",
    "analyze_research_source",
    "build_research_report_filename",
    "build_local_audio_research_source",
    "build_pdf_research_source",
    "build_youtube_research_source",
    "default_custom_output_path",
    "extract_text_pages",
    "parse_youtube_video_id",
    "pdf_to_markdown",
    "render_research_report",
    "resolve_research_report_output_destinations",
    "run_phase_one_research_source_analysis",
    "write_research_report_outputs",
]
