"""Research source models and Markdown report rendering."""

from personal_stock_investment_system.research.markdown import (
    build_research_report_filename,
    render_research_report,
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
    "build_research_report_filename",
    "render_research_report",
]
