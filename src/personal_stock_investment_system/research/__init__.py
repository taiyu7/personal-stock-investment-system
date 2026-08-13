"""Research source models and Markdown report rendering."""

from personal_stock_investment_system.research.analysis import analyze_research_source
from personal_stock_investment_system.research.markdown import (
    build_research_report_filename,
    render_research_report,
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
    SourceReference,
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
    "SourceReference",
    "StockOpinion",
    "StockRelation",
    "TechnicalAnalysisNote",
    "VerifiableHypothesis",
    "PdfPageText",
    "YouTubeImportResult",
    "YouTubeTranscriptSegment",
    "YouTubeVideoMetadata",
    "analyze_research_source",
    "build_research_report_filename",
    "build_pdf_research_source",
    "build_youtube_research_source",
    "extract_text_pages",
    "parse_youtube_video_id",
    "pdf_to_markdown",
    "render_research_report",
]
