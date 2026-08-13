import sys
from types import SimpleNamespace

import personal_stock_investment_system.research.pdf as pdf_module
from personal_stock_investment_system.research import build_pdf_research_source, extract_text_pages, pdf_to_markdown


def test_text_pdf_can_be_converted_to_markdown_with_page_locator(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_minimal_text_pdf("AI server demand", "valuation risk"))

    markdown = pdf_to_markdown(pdf_path, title="研究報告樣本")

    assert markdown.startswith("# 研究報告樣本")
    assert "來源檔案：sample.pdf" in markdown
    assert "## 第 1 頁" in markdown
    assert "AI server demand" in markdown
    assert "AI server demand)" not in markdown
    assert "## 第 2 頁" in markdown
    assert "valuation risk" in markdown


def test_pdf_research_source_keeps_raw_text_markdown_and_page_range(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(_minimal_text_pdf("first page", "second page"))

    source = build_pdf_research_source(
        pdf_path,
        title="投顧講義",
        publisher="研究機構",
        speakers=("研究員 A", "分析師 B"),
        notes="文字型 PDF 測試",
    )

    assert source.source_type == "pdf"
    assert source.title == "投顧講義"
    assert source.publisher == "研究機構"
    assert source.speakers == ("研究員 A", "分析師 B")
    assert source.source_locator == "pages:1-2"
    assert "[第 1 頁]\nfirst page" in source.raw_text
    assert "## 第 2 頁" in source.markdown_text
    assert source.notes == "文字型 PDF 測試"


def test_missing_pdf_raises_file_not_found(tmp_path):
    missing_pdf = tmp_path / "missing.pdf"

    try:
        extract_text_pages(missing_pdf)
    except FileNotFoundError as error:
        assert "missing.pdf" in str(error)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_pymupdf4llm_backend_uses_page_chunks(tmp_path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    fake_backend = SimpleNamespace(
        to_markdown=lambda path, page_chunks: [
            {"metadata": {"page": 1}, "text": "First page from PyMuPDF4LLM"},
            {"metadata": {"page": 2}, "text": "Second page table | value"},
        ]
    )
    monkeypatch.setitem(sys.modules, "pymupdf4llm", fake_backend)

    markdown = pdf_to_markdown(pdf_path, title="PyMuPDF4LLM 測試", backend="pymupdf4llm")

    assert "## 第 1 頁" in markdown
    assert "First page from PyMuPDF4LLM" in markdown
    assert "## 第 2 頁" in markdown
    assert "Second page table | value" in markdown


def test_pymupdf4llm_backend_has_clear_error_when_missing(tmp_path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    def fail_import(name):
        raise ImportError(name)

    monkeypatch.setattr(pdf_module, "import_module", fail_import)

    try:
        pdf_to_markdown(pdf_path, backend="pymupdf4llm")
    except RuntimeError as error:
        assert "pymupdf4llm" in str(error)
        assert "optional dependency" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def _minimal_text_pdf(page_one_text: str, page_two_text: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        _stream_object(f"BT /F1 12 Tf 72 720 Td ({page_one_text}) Tj ET".encode()),
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R >>",
        _stream_object(f"BT /F1 12 Tf 72 720 Td ({page_two_text}) Tj ET".encode()),
    ]
    body = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{index} 0 obj\n".encode())
        body.extend(content)
        body.extend(b"\nendobj\n")
    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode())
    body.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(body)


def _stream_object(stream: bytes) -> bytes:
    return b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
