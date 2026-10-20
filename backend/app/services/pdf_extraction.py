"""Deterministic PDF text extraction with page-level provenance.

PyMuPDF gives us the page text and, when the PDF defines them, printed page
labels. Scanned PDFs have no text layer and are reported as such instead of
being treated as empty documents.
"""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

MIN_PAGE_TEXT_CHARS = 40


class PdfExtractionError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(slots=True)
class PdfPage:
    page_index: int
    printed_label: str
    text: str
    char_count: int
    has_text: bool


@dataclass(slots=True)
class PdfExtraction:
    pages: list[PdfPage]
    page_count: int
    text_page_count: int
    truncated: bool

    @property
    def status(self) -> str:
        return "extracted" if self.text_page_count else "no_text_layer"


def extract_pdf_pages(
    content: bytes,
    *,
    max_pages: int = 200,
    min_text_chars: int = MIN_PAGE_TEXT_CHARS,
) -> PdfExtraction:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # pymupdf raises several low-level error types
        raise PdfExtractionError("not_pdf", "The file is not a readable PDF.") from exc

    try:
        if document.needs_pass:
            raise PdfExtractionError("password_protected", "The PDF is password protected.")
        page_count = document.page_count
        if page_count < 1:
            raise PdfExtractionError("empty_pdf", "The PDF has no pages.")

        limit = min(page_count, max(max_pages, 1))
        pages: list[PdfPage] = []
        for index in range(limit):
            page = document.load_page(index)
            text = (page.get_text("text") or "").replace("\x00", "")
            try:
                printed_label = page.get_label() or str(index + 1)
            except Exception:
                printed_label = str(index + 1)
            compact = " ".join(text.split())
            pages.append(
                PdfPage(
                    page_index=index + 1,
                    printed_label=printed_label,
                    text=text,
                    char_count=len(text),
                    has_text=len(compact) >= min_text_chars,
                )
            )
    finally:
        document.close()

    return PdfExtraction(
        pages=pages,
        page_count=page_count,
        text_page_count=sum(1 for page in pages if page.has_text),
        truncated=page_count > limit,
    )
