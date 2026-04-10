"""Unit tests for the Nugget Bridge chunker."""

from __future__ import annotations

import tiktoken

from smogon_vgc_mcp.fetcher.nugget_bridge_chunk import (
    _MAX_TOKENS,
    _MIN_TOKENS,
    _OVERLAP_TOKENS,
    _TARGET_TOKENS,
    chunk_post,
)

_ENC = tiktoken.get_encoding("cl100k_base")


def _toks(text: str) -> int:
    return len(_ENC.encode(text, disallowed_special=()))


def _para(word: str, n: int) -> str:
    """Build a deterministic paragraph with ``n`` repetitions of ``word``."""
    return " ".join([word] * n)


def test_empty_html_yields_no_chunks():
    assert chunk_post("") == []
    assert chunk_post("   ") == []
    assert chunk_post("<p></p>") == []


def test_single_short_paragraph_one_chunk():
    html = "<p>A short paragraph about Landorus-Therian's role on rain teams.</p>"
    chunks = chunk_post(html)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_index == 0
    assert c.section_heading is None
    assert "Landorus-Therian" in c.text
    assert c.token_count == _toks(c.text)


def test_heading_is_prepended_to_chunk_text():
    html = "<h2>Team Report</h2><p>Kartana led most matches with Beast Boost.</p>"
    chunks = chunk_post(html)
    assert len(chunks) == 1
    assert chunks[0].section_heading == "Team Report"
    assert chunks[0].text.startswith("# Team Report\n\n")
    assert "Kartana" in chunks[0].text


def test_chunks_split_when_section_exceeds_target():
    # Four ~200-token paragraphs → should pack into 2-3 chunks under one H2.
    para = _para("lorem", 200)
    assert _toks(para) >= 180
    html = f"<h2>Analysis</h2><p>{para}</p><p>{para}</p><p>{para}</p><p>{para}</p>"
    chunks = chunk_post(html)
    assert len(chunks) >= 2
    # Every chunk must respect the hard max
    for c in chunks:
        assert c.token_count <= _MAX_TOKENS + 5, c.token_count
    # All chunks belong to the same section
    assert all(c.section_heading == "Analysis" for c in chunks)
    # Indices start at 0 and are contiguous
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_overlap_within_same_section():
    # Build two big paragraphs that must split into multiple chunks, then
    # verify later chunks reference tokens from the prior chunk's tail.
    para_a = _para("alpha", 220)
    para_b = _para("beta", 220)
    para_c = _para("gamma", 220)
    html = f"<h2>S</h2><p>{para_a}</p><p>{para_b}</p><p>{para_c}</p>"
    chunks = chunk_post(html)
    assert len(chunks) >= 2
    # Chunks 1+ should contain some content from the preceding chunk's tail
    for i in range(1, len(chunks)):
        prior_tail_words = chunks[i - 1].text.split()[-10:]
        assert any(w in chunks[i].text for w in prior_tail_words), (
            f"chunk {i} missing overlap with chunk {i - 1}"
        )


def test_overlap_does_not_cross_h2_boundary():
    para = _para("content", 300)
    html = (
        f"<h2>First Section</h2><p>{para}</p>"
        f"<h2>Second Section</h2><p>Short second-section opener.</p>"
    )
    chunks = chunk_post(html)
    first_section = [c for c in chunks if c.section_heading == "First Section"]
    second_section = [c for c in chunks if c.section_heading == "Second Section"]
    assert first_section and second_section
    # Second section's first chunk must NOT contain the overlap word
    # from the first section.
    assert "content" not in second_section[0].text.split("\n\n", 1)[-1]


def test_table_collapsed_to_marker():
    html = (
        "<h2>Sets</h2>"
        "<p>Here is the Kartana set we ran:</p>"
        "<table><tr><th>Kartana @ Life Orb</th></tr>"
        "<tr><td>Ability: Beast Boost</td></tr>"
        "<tr><td>EVs: 252 Atk / 4 Def / 252 Spe</td></tr></table>"
        "<p>The Life Orb boosted Leaf Blade damage into bulky walls.</p>"
    )
    chunks = chunk_post(html)
    combined = "\n".join(c.text for c in chunks)
    assert "[set-table:" in combined
    assert "Kartana @ Life Orb" in combined  # used as the marker label
    assert "EVs: 252 Atk" not in combined  # table body was stripped
    assert "boosted Leaf Blade" in combined  # surrounding prose preserved


def test_preheading_content_gets_none_heading_section():
    html = "<p>Intro paragraph before any heading appears.</p><h2>Body</h2><p>Body paragraph.</p>"
    chunks = chunk_post(html)
    assert chunks[0].section_heading is None
    assert "Intro paragraph" in chunks[0].text
    assert any(c.section_heading == "Body" for c in chunks)


def test_h3_kept_as_subheading_inside_section():
    html = (
        "<h2>Strategy</h2>"
        "<h3>Lead Match-ups</h3>"
        "<p>Kartana + Tapu Lele is strong into Trick Room leads.</p>"
    )
    chunks = chunk_post(html)
    assert len(chunks) == 1
    assert chunks[0].section_heading == "Strategy"
    assert "## Lead Match-ups" in chunks[0].text


def test_oversize_single_paragraph_stands_alone():
    # One giant paragraph well past the hard max.
    giant = _para("huge", 900)
    assert _toks(giant) > _MAX_TOKENS
    html = f"<h2>Doc</h2><p>{giant}</p>"
    chunks = chunk_post(html)
    assert len(chunks) == 1
    assert chunks[0].token_count >= _toks(giant)


def test_min_token_target_respected_when_possible():
    # Several small paragraphs should pack together rather than emit a
    # sub-min-token chunk.
    paras = "".join(f"<p>{_para('small', 30)}</p>" for _ in range(10))
    html = f"<h2>Packed</h2>{paras}"
    chunks = chunk_post(html)
    # With ~30 tokens × 10 ≈ 300 tokens total, expect exactly 1 chunk.
    assert len(chunks) == 1
    assert chunks[0].token_count >= _MIN_TOKENS


def test_chunk_token_count_matches_encoded_length():
    html = "<h2>Verify</h2><p>" + _para("verify", 80) + "</p>"
    chunks = chunk_post(html)
    for c in chunks:
        assert c.token_count == _toks(c.text)


def test_overlap_constant_is_within_bounds():
    assert 0 < _OVERLAP_TOKENS < _MIN_TOKENS < _TARGET_TOKENS < _MAX_TOKENS
