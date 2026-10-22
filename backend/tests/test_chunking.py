"""The passage chunker.

The chunker is the one place where a citation can go wrong, so the tests are
about provenance: a passage must be a verbatim span of the page it claims.
"""

from __future__ import annotations

from app.services.chunking import (
    chunk_page,
    chunk_pages,
    detect_clause,
    detect_heading,
    split_blocks,
)
from app.services.requirement_service import normalize_for_match

PAGE = """
1. Scope of work

The contractor shall supply, install and commission the complete system at the
site, and shall keep the works free from any defect during the defects
liability period.

1.1 The contractor shall be responsible for obtaining every statutory
approval that the work requires before the work begins.

2. Payments

2.1 Payment shall be made within thirty days of the invoice being received
and certified by the engineer.
"""


def test_a_heading_is_detected() -> None:
    assert detect_heading("1. Scope of work") == "1. Scope of work"
    assert detect_heading("SCOPE OF WORK") == "SCOPE OF WORK"
    assert detect_heading("Section 4 - General conditions") is not None
    assert detect_heading("The contractor shall pay the wages on time.") is None


def test_a_clause_number_is_detected() -> None:
    assert detect_clause("1.1 The contractor shall be responsible.") == "1.1"
    assert detect_clause("2. Payment shall be made") == "2"
    assert detect_clause("(a) the first item") == "(a)"
    assert detect_clause("The contractor shall pay the wages.") is None


def test_a_page_is_split_into_blocks() -> None:
    blocks = split_blocks(PAGE)
    kinds = [block.kind for block in blocks]
    assert "heading" in kinds
    assert "clause" in kinds
    # A paragraph broken over several lines is one block, not three.
    body = [block for block in blocks if block.kind == "body"]
    assert any("defects liability period" in block.text for block in body)


def test_a_passage_is_a_verbatim_span_of_its_page() -> None:
    passages = chunk_page(1, "1", PAGE)
    assert passages
    for passage in passages:
        span = PAGE[passage.start : passage.end]
        assert normalize_for_match(span) == normalize_for_match(passage.text)


def test_a_passage_carries_its_section_and_clause() -> None:
    passages = chunk_page(1, "1", PAGE)
    headings = [passage.section_heading for passage in passages]
    assert any("Scope of work" in (heading or "") for heading in headings)
    clauses = [passage.clause_number for passage in passages]
    assert any(clause and clause.startswith("1.1") for clause in clauses)


def test_a_heading_starts_a_new_passage() -> None:
    passages = chunk_page(1, "1", PAGE)
    # The first passage is the heading itself, the next ones are the clauses.
    assert passages[0].text.startswith("1. Scope of work")
    assert len(passages) >= 3


def test_a_passage_stays_inside_the_size_limit() -> None:
    long_page = "\n\n".join(
        f"{index}. Clause {index} " + " ".join(["word"] * 60) for index in range(1, 20)
    )
    passages = chunk_page(1, "1", long_page, max_words=80, max_chars=600)
    assert passages
    for passage in passages:
        assert passage.word_count <= 80 + 60


def test_the_overlap_is_kept_separate_from_the_quotable_text() -> None:
    long_page = "\n\n".join(
        f"{index}. Clause {index} " + " ".join(["word"] * 60) for index in range(1, 20)
    )
    passages = chunk_page(1, "1", long_page, max_words=80, overlap_words=10)
    assert passages
    assert passages[1].context
    # The passage text is still a contiguous span of the page.
    for passage in passages:
        span = long_page[passage.start : passage.end]
        assert normalize_for_match(span) == normalize_for_match(passage.text)


def test_an_empty_page_gives_no_passage() -> None:
    assert chunk_page(1, "1", "   \n  ") == []


def test_the_chunk_index_continues_across_pages() -> None:
    pages = [
        {"page_index": 1, "printed_label": "i", "text": PAGE},
        {"page_index": 2, "printed_label": "ii", "text": PAGE},
    ]
    passages = chunk_pages(pages)
    assert [passage.chunk_index for passage in passages] == list(range(len(passages)))
    assert passages[0].page_index == 1
    assert passages[-1].page_index == 2


def test_a_page_without_text_is_skipped() -> None:
    pages = [
        {"page_index": 1, "printed_label": "i", "text": ""},
        {"page_index": 2, "printed_label": "ii", "text": PAGE},
    ]
    passages = chunk_pages(pages)
    assert passages
    assert all(passage.page_index == 2 for passage in passages)
