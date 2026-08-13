"""Minimal text-based PDF to Markdown conversion for research sources."""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

from personal_stock_investment_system.research.sources import ResearchSource

PdfBackend = Literal["builtin", "pymupdf4llm"]


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str


def pdf_to_markdown(pdf_path: Path | str, title: str | None = None, backend: PdfBackend = "builtin") -> str:
    path = Path(pdf_path)
    pages = extract_text_pages(path, backend=backend)
    heading = title or path.stem
    lines = [f"# {heading}", "", f"來源檔案：{path.name}", ""]
    for page in pages:
        lines.extend([f"## 第 {page.page_number} 頁", "", page.text or "（本頁未抽取到文字）", ""])
    return "\n".join(lines).strip() + "\n"


def build_pdf_research_source(
    pdf_path: Path | str,
    *,
    title: str | None = None,
    source_url: str = "",
    publisher: str = "",
    speaker: str = "",
    speakers: tuple[str, ...] = (),
    published_date: str = "",
    notes: str = "",
    backend: PdfBackend = "builtin",
) -> ResearchSource:
    path = Path(pdf_path)
    pages = extract_text_pages(path, backend=backend)
    markdown_text = pdf_to_markdown(path, title, backend=backend)
    raw_text = "\n\n".join(f"[第 {page.page_number} 頁]\n{page.text}" for page in pages)
    page_numbers = [page.page_number for page in pages]
    source_locator = f"pages:{min(page_numbers)}-{max(page_numbers)}" if page_numbers else "pages:unknown"
    return ResearchSource(
        source_type="pdf",
        title=title or path.stem,
        source_url=source_url,
        publisher=publisher,
        speaker=speaker,
        speakers=speakers,
        published_date=published_date,
        raw_text=raw_text,
        markdown_text=markdown_text,
        source_locator=source_locator,
        notes=notes,
    )


def extract_text_pages(pdf_path: Path | str, backend: PdfBackend = "builtin") -> tuple[PdfPageText, ...]:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if backend == "pymupdf4llm":
        return _extract_text_pages_with_pymupdf4llm(path)
    if backend != "builtin":
        raise ValueError(f"Unsupported PDF backend: {backend}")
    data = path.read_bytes()
    stream_texts = [_extract_stream_text(stream) for stream in _iter_pdf_streams(data)]
    pages = [PdfPageText(index, text) for index, text in enumerate(stream_texts, start=1) if text]
    return tuple(pages) or (PdfPageText(1, ""),)


def _extract_text_pages_with_pymupdf4llm(pdf_path: Path) -> tuple[PdfPageText, ...]:
    pymupdf4llm = _load_pymupdf4llm()
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    if isinstance(chunks, str):
        return (PdfPageText(1, _normalize_text(chunks)),)
    pages = []
    for index, chunk in enumerate(chunks, start=1):
        text = _chunk_text(chunk)
        metadata = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
        page_number = int(metadata.get("page") or metadata.get("page_number") or index)
        pages.append(PdfPageText(page_number, text))
    return tuple(pages) or (PdfPageText(1, ""),)


def _load_pymupdf4llm() -> Any:
    try:
        return import_module("pymupdf4llm")
    except ImportError as error:
        raise RuntimeError(
            "PyMuPDF4LLM backend requires optional dependency `pymupdf4llm`. "
            "Install it before using backend='pymupdf4llm'."
        ) from error


def _chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return _normalize_text(str(chunk.get("text", "")))
    return _normalize_text(str(chunk))


def _iter_pdf_streams(data: bytes) -> list[bytes]:
    streams: list[bytes] = []
    for match in re.finditer(rb"<<(?P<dict>.*?)>>\s*stream\r?\n(?P<body>.*?)\r?\nendstream", data, re.DOTALL):
        stream_dict = match.group("dict")
        body = match.group("body")
        if b"/FlateDecode" in stream_dict:
            try:
                body = zlib.decompress(body)
            except zlib.error:
                continue
        streams.append(body)
    return streams


def _extract_stream_text(stream: bytes) -> str:
    text_parts = []
    for raw_value in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", stream):
        text_parts.append(_decode_pdf_literal(raw_value))
    for array_body in re.findall(rb"\[(.*?)\]\s*TJ", stream, re.DOTALL):
        for raw_value in re.findall(rb"\((?:\\.|[^\\)])*\)", array_body):
            text_parts.append(_decode_pdf_literal(raw_value[1:-1]))
    return _normalize_text(" ".join(part for part in text_parts if part))


def _decode_pdf_literal(value: bytes) -> str:
    unescaped = (
        value.replace(rb"\(", b"(")
        .replace(rb"\)", b")")
        .replace(rb"\\", b"\\")
        .replace(rb"\n", b"\n")
        .replace(rb"\r", b"\r")
        .replace(rb"\t", b"\t")
    )
    return unescaped.decode("utf-8", errors="ignore")


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
