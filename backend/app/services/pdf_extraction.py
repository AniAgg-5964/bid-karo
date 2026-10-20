"""Deterministic PDF text extraction with page-level provenance.

PyMuPDF gives us the page text and, when the PDF defines them, printed page
labels. Pages without a text layer can optionally be transcribed by an
injected OCR callable; those pages are labelled ``ocr`` so callers never claim
they are verbatim text-layer content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pymupdf

MIN_PAGE_TEXT_CHARS = 40

OcrCallable = Callable[[bytes], str]


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
    text_source: str = "text_layer"  # text_layer | ocr | empty


@dataclass(slots=True)
class PdfExtraction:
    pages: list[PdfPage]
    page_count: int
    text_page_count: int
    truncated: bool
    ocr_page_count: int = 0
    ocr_failed_pages: int = 0
    ocr_skipped_pages: int = 0

    @property
    def status(self) -> str:
        return "extracted" if self.text_page_count else "no_text_layer"


def extract_pdf_pages(
    content: bytes,
    *,
    max_pages: int = 200,
    min_text_chars: int = MIN_PAGE_TEXT_CHARS,
    ocr: OcrCallable | None = None,
    ocr_dpi: int = 250,
    ocr_max_pages: int = 40,
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
        ocr_attempts = 0
        ocr_failed = 0
        ocr_skipped = 0

        for index in range(limit):
            page = document.load_page(index)
            text = (page.get_text("text") or "").replace("\x00", "")
            text_source = "text_layer"
            compact = " ".join(text.split())

            if len(compact) < min_text_chars and ocr is not None:
                if ocr_attempts >= max(ocr_max_pages, 0):
                    ocr_skipped += 1
                else:
                    ocr_attempts += 1
                    try:
                        pixmap = page.get_pixmap(dpi=max(ocr_dpi, 100), colorspace=pymupdf.csGRAY)
                        recognized = (ocr(pixmap.tobytes("png")) or "").replace("\x00", "")
                        recognized_compact = " ".join(recognized.split())
                        if len(recognized_compact) >= min_text_chars:
                            text = recognized
                            compact = recognized_compact
                            text_source = "ocr"
                        else:
                            text_source = "empty"
                    except Exception:
                        ocr_failed += 1
                        text_source = "empty"
            elif len(compact) < min_text_chars:
                text_source = "empty"

            try:
                printed_label = page.get_label() or str(index + 1)
            except Exception:
                printed_label = str(index + 1)

            pages.append(
                PdfPage(
                    page_index=index + 1,
                    printed_label=printed_label,
                    text=text,
                    char_count=len(text),
                    has_text=len(compact) >= min_text_chars,
                    text_source=text_source,
                )
            )
    finally:
        document.close()

    return PdfExtraction(
        pages=pages,
        page_count=page_count,
        text_page_count=sum(1 for page in pages if page.has_text),
        truncated=page_count > limit,
        ocr_page_count=sum(1 for page in pages if page.text_source == "ocr"),
        ocr_failed_pages=ocr_failed,
        ocr_skipped_pages=ocr_skipped,
    )
