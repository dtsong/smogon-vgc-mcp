"""Heading-aware chunker for Nugget Bridge WordPress posts.

Walks the rendered HTML, groups paragraphs under their nearest preceding
``<h1>``/``<h2>``/``<h3>``, and packs them into ~500-token chunks using
tiktoken's ``cl100k_base`` encoding (the tokenizer shared by OpenAI's
``text-embedding-3-small`` and Claude's tool-use payloads, close enough
for budget planning).

Chunking rules:
- Soft target: 500 tokens. Hard max: 750. Soft min: 150.
- 80-token tail overlap between consecutive chunks **within the same H2
  section**. Crossing an H2 boundary resets the overlap.
- Section heading prepended to chunk text as ``# <heading>\n\n`` so the
  heading is part of the embedded context.
- Set-table stripping: ``<table>`` blocks are replaced with a one-line
  marker ``[set-table: <first-cell>]`` so RAG still surfaces the
  surrounding discussion without re-embedding structured data that lives
  in ``nb_sets``.

This module is pure (no DB, no network) and takes raw HTML as input.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import tiktoken
from bs4 import BeautifulSoup, PageElement, Tag

_ENCODING_NAME = "cl100k_base"
_TARGET_TOKENS = 500
_MAX_TOKENS = 750
_MIN_TOKENS = 150
_OVERLAP_TOKENS = 80

_BLOCK_TAGS = {"p", "li", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6"}
_HEADING_TAGS = {"h1", "h2", "h3"}
_SECTION_BOUNDARY_TAGS = {"h1", "h2"}


@dataclass
class Chunk:
    """One packed chunk ready for ``nb_chunks`` insertion."""

    chunk_index: int
    text: str
    token_count: int
    section_heading: str | None


@dataclass
class _Block:
    """One flattened block from the HTML walk: a paragraph, list item,
    heading, or set-table marker."""

    kind: str  # "text" | "heading" | "marker"
    text: str
    heading_level: int | None = None  # only set when kind == "heading"


def _get_encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _table_marker(table: Tag) -> str:
    """Reduce a ``<table>`` to a single-line marker. Uses the first
    non-empty cell as the label so set tables like '|Kartana|Life Orb|...'
    still hint at which Pokemon the table describes."""
    first_cell = ""
    for cell in table.find_all(("th", "td")):
        text = _collapse_whitespace(cell.get_text(" ", strip=True))
        if text:
            first_cell = text
            break
    label = first_cell[:60] if first_cell else "table"
    return f"[set-table: {label}]"


def _flatten_blocks(soup: BeautifulSoup) -> list[_Block]:
    """Walk the parsed HTML top-down and produce an ordered list of
    blocks. Nested structure is ignored — ``<div><p>x</p></div>`` and
    ``<p>x</p>`` yield the same block. Tables are collapsed to markers."""
    blocks: list[_Block] = []
    seen: set[int] = set()

    def visit(node: PageElement) -> None:
        if not isinstance(node, Tag):
            return
        if id(node) in seen:
            return
        name = node.name.lower() if node.name else ""

        if name == "table":
            blocks.append(_Block(kind="marker", text=_table_marker(node)))
            _mark_subtree(node, seen)
            return

        if name in _HEADING_TAGS:
            text = _collapse_whitespace(node.get_text(" ", strip=True))
            if text:
                blocks.append(_Block(kind="heading", text=text, heading_level=int(name[1])))
            _mark_subtree(node, seen)
            return

        if name in _BLOCK_TAGS:
            text = _collapse_whitespace(node.get_text(" ", strip=True))
            if text:
                blocks.append(_Block(kind="text", text=text))
            _mark_subtree(node, seen)
            return

        for child in node.children:
            visit(child)

    def _mark_subtree(node: Tag, marked: set[int]) -> None:
        marked.add(id(node))
        for descendant in node.descendants:
            if isinstance(descendant, Tag):
                marked.add(id(descendant))

    root = soup.body if soup.body else soup
    visit(root)
    return blocks


def _token_count(enc: tiktoken.Encoding, text: str) -> int:
    return len(enc.encode(text, disallowed_special=()))


def _tail_overlap(enc: tiktoken.Encoding, text: str, overlap_tokens: int) -> str:
    """Return the last ~``overlap_tokens`` tokens of ``text`` as a
    decoded string, for prepending to the next chunk."""
    if overlap_tokens <= 0 or not text:
        return ""
    tokens = enc.encode(text, disallowed_special=())
    if len(tokens) <= overlap_tokens:
        return text
    tail = tokens[-overlap_tokens:]
    return enc.decode(tail)


def _pack_section(
    enc: tiktoken.Encoding,
    blocks: Iterable[_Block],
    section_heading: str | None,
    start_index: int,
) -> list[Chunk]:
    """Pack blocks from a single section (same H1/H2 boundary) into
    chunks. Overlap is applied only *inside* this section."""
    packed: list[Chunk] = []
    heading_prefix = f"# {section_heading}\n\n" if section_heading else ""
    heading_tokens = _token_count(enc, heading_prefix) if heading_prefix else 0

    buffer_parts: list[str] = []
    buffer_tokens = 0
    index = start_index

    def flush(carry_overlap: bool) -> str:
        """Emit one chunk; return the overlap tail for the next buffer."""
        nonlocal buffer_parts, buffer_tokens, index
        if not buffer_parts:
            return ""
        body = "\n\n".join(buffer_parts)
        text = heading_prefix + body
        packed.append(
            Chunk(
                chunk_index=index,
                text=text,
                token_count=heading_tokens + buffer_tokens,
                section_heading=section_heading,
            )
        )
        index += 1
        overlap = _tail_overlap(enc, body, _OVERLAP_TOKENS) if carry_overlap else ""
        buffer_parts = []
        buffer_tokens = 0
        return overlap

    for block in blocks:
        if block.kind == "heading":
            # H3 inside an H2 section: promote as a bold sub-label.
            piece = f"## {block.text}"
        else:
            piece = block.text

        piece_tokens = _token_count(enc, piece)

        # A single oversize paragraph: emit any pending buffer, then the
        # oversize piece as its own chunk. No overlap applies to the
        # oversize emission.
        if piece_tokens > _MAX_TOKENS:
            flush(carry_overlap=False)
            packed.append(
                Chunk(
                    chunk_index=index,
                    text=heading_prefix + piece,
                    token_count=heading_tokens + piece_tokens,
                    section_heading=section_heading,
                )
            )
            index += 1
            continue

        prospective = buffer_tokens + piece_tokens
        if prospective > _TARGET_TOKENS and buffer_tokens >= _MIN_TOKENS:
            overlap = flush(carry_overlap=True)
            if overlap:
                buffer_parts.append(overlap)
                buffer_tokens = _token_count(enc, overlap)
            buffer_parts.append(piece)
            buffer_tokens += piece_tokens
        else:
            buffer_parts.append(piece)
            buffer_tokens = prospective

    flush(carry_overlap=False)
    return packed


def _split_sections(
    blocks: list[_Block],
) -> list[tuple[str | None, list[_Block]]]:
    """Group blocks by section boundary (H1/H2). H3 stays inside the
    enclosing section as a sub-heading. Pre-heading blocks land in a
    leading ``None``-heading section."""
    sections: list[tuple[str | None, list[_Block]]] = []
    current_heading: str | None = None
    current: list[_Block] = []
    for block in blocks:
        if block.kind == "heading" and block.heading_level in (1, 2):
            if current:
                sections.append((current_heading, current))
                current = []
            current_heading = block.text
            continue
        current.append(block)
    if current:
        sections.append((current_heading, current))
    return sections


def chunk_post(content_html: str) -> list[Chunk]:
    """Chunk a WordPress post's rendered HTML into ~500-token pieces.

    Args:
        content_html: ``content.rendered`` from the WP REST API response.

    Returns:
        Ordered list of :class:`Chunk`. Empty if the post has no
        meaningful text.
    """
    if not content_html or not content_html.strip():
        return []

    soup = BeautifulSoup(content_html, "html.parser")
    blocks = _flatten_blocks(soup)
    if not blocks:
        return []

    enc = _get_encoder()
    sections = _split_sections(blocks)
    chunks: list[Chunk] = []
    next_index = 0
    for heading, section_blocks in sections:
        packed = _pack_section(enc, section_blocks, heading, next_index)
        chunks.extend(packed)
        next_index += len(packed)
    return chunks
