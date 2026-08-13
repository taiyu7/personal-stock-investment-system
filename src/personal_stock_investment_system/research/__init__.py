"""Research source models and Markdown report rendering."""

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
    "build_research_report_filename",
    "build_pdf_research_source",
    "extract_text_pages",
    "pdf_to_markdown",
    "render_research_report",
]
