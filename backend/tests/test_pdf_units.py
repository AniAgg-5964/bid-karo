from __future__ import annotations

import io

import pymupdf
import pytest
from PIL import Image, ImageDraw

from app.services.download import DownloadError, _validate_public_url
from app.services.pdf_extraction import PdfExtractionError, extract_pdf_pages
from app.services.requirement_service import (
    _category,
    _mandatory,
    chunk_pages,
    normalize_for_match,
)
from tests.conftest import SAMPLE_PAGES, make_pdf


def test_extract_pdf_pages_keeps_page_provenance(sample_pdf: bytes):
    extraction = extract_pdf_pages(sample_pdf)
    assert extraction.page_count == 3
    assert extraction.text_page_count == 3
    assert extraction.status == "extracted"
    assert extraction.truncated is False
    assert [page.page_index for page in extraction.pages] == [1, 2, 3]
    assert "average annual turnover" in extraction.pages[0].text
    assert extraction.pages[0].printed_label == "1"


def test_scanned_pdf_is_not_treated_as_text():
    extraction = extract_pdf_pages(make_pdf([" "]))
    assert extraction.text_page_count == 0
    assert extraction.status == "no_text_layer"


def _scanned_pdf(text: str) -> bytes:
    image = Image.new("RGB", (1400, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 80), text, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")

    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(pymupdf.Rect(30, 30, 582, 762), stream=buffer.getvalue())
    data = document.tobytes()
    document.close()
    return data


def test_ocr_transcribes_scanned_pages_and_labels_the_source():
    seen: list[bytes] = []

    def fake_ocr(png: bytes) -> str:
        seen.append(png)
        return (
            "The bidder shall have an average annual turnover of at least "
            "INR 5 crore during the last three financial years."
        )

    extraction = extract_pdf_pages(_scanned_pdf("Turnover requirement"), ocr=fake_ocr)
    assert seen
    assert extraction.ocr_page_count == 1
    assert extraction.text_page_count == 1
    assert extraction.status == "extracted"
    assert extraction.pages[0].text_source == "ocr"
    assert "average annual turnover" in extraction.pages[0].text


def test_ocr_page_cap_is_reported():
    extraction = extract_pdf_pages(
        _scanned_pdf("Turnover requirement"),
        ocr=lambda png: "A sufficiently long piece of recognised OCR text for this test page.",
        ocr_max_pages=0,
    )
    assert extraction.ocr_page_count == 0
    assert extraction.ocr_skipped_pages == 1
    assert extraction.status == "no_text_layer"


def test_unreadable_pdf_is_rejected():
    with pytest.raises(PdfExtractionError) as excinfo:
        extract_pdf_pages(b"not a pdf")
    assert excinfo.value.reason == "not_pdf"


def test_page_limit_is_reported(sample_pdf: bytes):
    extraction = extract_pdf_pages(sample_pdf, max_pages=2)
    assert len(extraction.pages) == 2
    assert extraction.page_count == 3
    assert extraction.truncated is True


def test_chunking_respects_page_and_char_limits():
    pages = [
        {"page_index": index, "has_text": True, "text": "x" * 40}
        for index in range(1, 6)
    ]
    pages.append({"page_index": 6, "has_text": False, "text": ""})

    chunks = chunk_pages(pages, max_chars=100, max_pages_per_chunk=6)
    assert [len(chunk.pages) for chunk in chunks] == [2, 2, 1]
    assert all(page["has_text"] for chunk in chunks for page in chunk.pages)

    by_pages = chunk_pages(pages, max_chars=10_000, max_pages_per_chunk=2)
    assert [len(chunk.pages) for chunk in by_pages] == [2, 2, 1]


def test_normalization_handles_quotes_and_whitespace():
    assert normalize_for_match("  The  bidder\u00a0shall\u2019s  ") == "the bidder shall's"
    assert normalize_for_match("A \u201cquoted\u201d value") == 'a "quoted" value'
    assert normalize_for_match("Line one\nLine two") == "line one line two"


def test_category_and_mandatory_mapping():
    assert _category("Submission") == "submission"
    assert _category("legal") == "other"
    assert _mandatory("required") == "yes"
    assert _mandatory("Optional") == "no"
    assert _mandatory("maybe") == "unknown"


def test_private_hosts_are_rejected_for_downloads():
    with pytest.raises(DownloadError) as excinfo:
        _validate_public_url("http://localhost/tender.pdf")
    assert excinfo.value.reason == "private_host"

    with pytest.raises(DownloadError) as excinfo:
        _validate_public_url("http://127.0.0.1/tender.pdf")
    assert excinfo.value.reason == "private_host"

    with pytest.raises(DownloadError) as excinfo:
        _validate_public_url("ftp://example.com/tender.pdf")
    assert excinfo.value.reason == "invalid_url"


def test_sample_page_text_is_available():
    assert "Late bids shall be rejected." in SAMPLE_PAGES[1]
