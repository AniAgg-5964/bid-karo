"""Passage chunking for the retrieval index.

The existing ``chunk_pages`` in the requirement service groups whole pages for
the extraction call. That is the right shape for a model that reads a document
once. Retrieval needs the other shape: passages *inside* a page, small enough to
be a useful answer and large enough to carry a clause.

Two rules shape the code:

* **A passage is a verbatim span of its page.** Every passage keeps the
  character offsets of the page text it came from, so the quote gate can still
  prove that the passage exists on the page it claims.
* **A passage follows the document's structure.** Headings and clause markers
  end a block, a heading starts a new passage, and a passage never mixes two
  sections. The overlap between two passages is kept in a separate field, so
  the passage text itself stays a contiguous, quotable span.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_MAX_WORDS = 220
DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_WORDS = 40

# A named part of a document ("Section 4 - General conditions").
_NAMED_PART_RE = re.compile(
    r"^(?:section|part|chapter|annexure|schedule|appendix)\b[^.]{0,80}", re.IGNORECASE
)

# A numbered title ("3. Scope of work"). It has to be short and free of the
# words that mark a sentence, otherwise a numbered clause would be read as a
# heading.
_NUMBERED_TITLE_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S")
_CAPS_RE = re.compile(r"^[A-Z][A-Z0-9 ,&()\-/]{4,80}$")
_SENTENCE_WORDS_RE = re.compile(
    r"\b(?:shall|must|will|should|is|are|was|were|has|have|had|been|be|"
    r"required|notwithstanding|provided|subject\s+to|including)\b",
    re.IGNORECASE,
)
MAX_HEADING_CHARS = 60

# A clause marker at the start of a paragraph.
_CLAUSE_RE = re.compile(
    r"^(?:"
    r"(?P<number>\d+(?:\.\d+)*)\)?[.)]?\s+"
    r"|\((?P<letter>[a-zA-Z])\)\s+"
    r"|(?P<roman>[ivxlcIVXLC]{1,6})[.)]\s+"
    r"|(?P<item>[a-zA-Z])[.)]\s+"
    r")"
)

# A trailing clause marker on a heading-like line ("3.2 The contractor shall").
_INLINE_CLAUSE_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+\S")

_WHITESPACE_RE = re.compile(r"[ \t ]+")


@dataclass(slots=True)
class Block:
    """A structural block of a page."""

    text: str
    kind: str  # heading | clause | body
    start: int
    end: int
    clause_number: str | None = None
    heading: str | None = None


@dataclass(slots=True)
class Passage:
    """One retrievable passage, with the provenance needed to cite it."""

    text: str
    page_index: int
    printed_page: str
    chunk_index: int
    start: int
    end: int
    section_heading: str | None = None
    clause_number: str | None = None
    context: str = ""
    word_count: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def embedding_text(self) -> str:
        """What the model sees: the passage, with the carried context in front."""
        if self.context:
            return f"{self.context}\n{self.text}"
        return self.text


def _words(text: str) -> int:
    return len(text.split())


def detect_heading(line: str) -> str | None:
    """The heading of a line, or None when the line is not a heading."""
    stripped = line.strip()
    if not stripped or len(stripped) > 90:
        return None
    if stripped.endswith((".", ";", ",")):
        return None
    if _NAMED_PART_RE.match(stripped):
        return stripped
    if _CAPS_RE.match(stripped):
        return stripped
    if (
        _NUMBERED_TITLE_RE.match(stripped)
        and len(stripped) <= MAX_HEADING_CHARS
        and not _SENTENCE_WORDS_RE.search(stripped)
    ):
        return stripped
    return None


def detect_clause(line: str) -> str | None:
    """The clause number a line starts with, or None."""
    stripped = line.strip()
    if not stripped:
        return None
    match = _CLAUSE_RE.match(stripped)
    if not match:
        return None
    number = match.group("number")
    if number:
        return number
    letter = match.group("letter")
    if letter:
        return f"({letter})"
    roman = match.group("roman")
    if roman:
        return f"{roman})"
    item = match.group("item")
    if item:
        return f"{item})"
    return None


def split_blocks(text: str) -> list[Block]:
    """Split a page into structural blocks.

    A line that starts a heading or a clause ends the previous block. Every
    other line continues the current block, because a PDF page is often a
    paragraph broken over several lines.
    """
    blocks: list[Block] = []
    offset = 0
    current_lines: list[str] = []
    current_start = 0
    current_kind = "body"
    current_clause: str | None = None
    current_heading: str | None = None

    def flush() -> None:
        nonlocal current_lines, current_kind, current_clause, current_heading
        if not current_lines:
            return
        body = " ".join(part.strip() for part in current_lines if part.strip())
        if body:
            end = current_start + sum(len(part) for part in current_lines) + len(
                current_lines
            ) - 1
            blocks.append(
                Block(
                    text=body,
                    kind=current_kind,
                    start=current_start,
                    end=min(end, max(len(text), current_start)),
                    clause_number=current_clause,
                    heading=current_heading,
                )
            )
        current_lines = []
        current_kind = "body"
        current_clause = None
        current_heading = None

    for line in text.splitlines():
        line_start = offset
        offset += len(line) + 1
        stripped = line.strip()
        if not stripped:
            flush()
            continue

        heading = detect_heading(stripped)
        clause = detect_clause(stripped)
        if heading:
            flush()
            current_lines = [line]
            current_start = line_start
            current_kind = "heading"
            current_heading = heading
            # A numbered title keeps its number, so the citation can show it.
            current_clause = clause
            continue
        if clause:
            flush()
            current_lines = [line]
            current_start = line_start
            current_kind = "clause"
            current_clause = clause
            inline = _INLINE_CLAUSE_RE.match(stripped)
            if inline:
                current_heading = stripped
            continue

        if not current_lines:
            current_start = line_start
        current_lines.append(line)

    flush()
    return blocks


def _tail(text: str, count: int) -> str:
    """The last ``count`` words of a text, for the overlap."""
    if count <= 0:
        return ""
    words = text.split()
    if len(words) <= count:
        return text
    return " ".join(words[-count:])


def chunk_page(
    page_index: int,
    printed_page: str,
    text: str,
    *,
    max_words: int = DEFAULT_MAX_WORDS,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
    start_index: int = 0,
) -> list[Passage]:
    """Split one page into passages."""
    if not (text or "").strip():
        return []

    blocks = split_blocks(text)
    if not blocks:
        return []

    passages: list[Passage] = []
    buffer: list[Block] = []
    buffer_words = 0
    current_heading: str | None = None
    current_clause: str | None = None
    context = ""

    def close() -> None:
        nonlocal buffer, buffer_words, context, current_clause
        if not buffer:
            return
        body = "\n".join(block.text for block in buffer)
        start = buffer[0].start
        end = buffer[-1].end
        passages.append(
            Passage(
                text=body,
                page_index=page_index,
                printed_page=printed_page,
                chunk_index=start_index + len(passages),
                start=start,
                end=end,
                section_heading=current_heading,
                clause_number=current_clause,
                context=context,
                word_count=buffer_words,
            )
        )
        context = _tail(body, overlap_words)
        buffer = []
        buffer_words = 0

    for block in blocks:
        if block.kind == "heading":
            # A heading starts a new passage: a passage must not mix sections.
            close()
            current_heading = block.heading or block.text
            current_clause = block.clause_number
            buffer = [block]
            buffer_words = _words(block.text)
            close()
            continue

        if block.kind == "clause":
            if buffer:
                close()
            current_clause = block.clause_number
            if block.heading:
                current_heading = block.heading

        block_words = _words(block.text)
        if buffer and (
            buffer_words + block_words > max_words
            or sum(len(item.text) for item in buffer) + len(block.text) > max_chars
        ):
            close()
        buffer.append(block)
        buffer_words += block_words

    close()
    return passages


def chunk_pages(
    pages: list[dict],
    *,
    max_words: int = DEFAULT_MAX_WORDS,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[Passage]:
    """Split a list of stored pages into passages.

    Each page is a mapping with ``page_index``, ``printed_label`` and ``text``.
    The passage index continues across the pages of one document.
    """
    passages: list[Passage] = []
    index = 0
    for page in pages:
        text = page.get("text") or ""
        if not text.strip():
            continue
        page_passages = chunk_page(
            int(page.get("page_index") or 0),
            str(page.get("printed_label") or page.get("page_index") or ""),
            text,
            max_words=max_words,
            max_chars=max_chars,
            overlap_words=overlap_words,
            start_index=index,
        )
        text_source = str(page.get("text_source") or "text_layer")
        for passage in page_passages:
            passage.metadata["text_source"] = text_source
        passages.extend(page_passages)
        index += len(page_passages)
    return passages


def content_hash(passages: list[Passage]) -> str:
    """A stable hash of the passages, used to detect an unchanged document."""
    import hashlib

    digest = hashlib.sha256()
    for passage in passages:
        digest.update(passage.text.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()
