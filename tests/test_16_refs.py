#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Tests for wikitext <ref> / <references /> footnote support.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from app.services.renderer import render


# ── Basic plain refs ──────────────────────────────────────────────────────────

def test_plain_ref_creates_superscript():
    wt = "Some text.<ref>First footnote.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert 'class="reference"' in html
    assert '[1]' in html


def test_plain_ref_footnote_appears_in_references():
    wt = "Text.<ref>My note.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert 'My note.' in html
    assert '<div class="references">' in html


def test_multiple_refs_numbered_sequentially():
    wt = "A<ref>Note one.</ref> B<ref>Note two.</ref> C<ref>Note three.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert '[1]' in html
    assert '[2]' in html
    assert '[3]' in html
    assert 'Note one.' in html
    assert 'Note two.' in html
    assert 'Note three.' in html


def test_no_references_tag_footnotes_still_inline():
    """Refs work even if <references /> is omitted — superscripts still appear."""
    wt = "Text.<ref>Orphan note.</ref>"
    html = render(wt, fmt="wikitext")
    assert 'class="reference"' in html
    assert '[1]' in html


def test_no_refs_no_references_block():
    wt = "Plain text with no footnotes.\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert '<div class="references">' not in html


# ── Named refs ────────────────────────────────────────────────────────────────

def test_named_ref_first_use():
    wt = 'Text.<ref name="src1">Source one.</ref>\n\n<references />'
    html = render(wt, fmt="wikitext")
    assert '[1]' in html
    assert 'Source one.' in html


def test_named_ref_back_reference_reuses_number():
    wt = (
        'First use.<ref name="foo">Foo text.</ref> '
        'Second use.<ref name="foo" />\n\n<references />'
    )
    html = render(wt, fmt="wikitext")
    # Both occurrences link to cite-note-1
    assert html.count('href="#cite-note-1"') == 2
    # Footnote text only appears once
    assert html.count('Foo text.') == 1


def test_mixed_named_and_plain_refs():
    wt = (
        'A<ref name="alpha">Alpha note.</ref> '
        'B<ref>Beta note.</ref> '
        'C<ref name="alpha" />\n\n<references />'
    )
    html = render(wt, fmt="wikitext")
    assert 'Alpha note.' in html
    assert 'Beta note.' in html
    # Alpha is ref [1], Beta is ref [2]; alpha back-ref reuses [1]
    assert html.count('href="#cite-note-1"') == 2
    assert 'href="#cite-note-2"' in html


# ── Anchor IDs ────────────────────────────────────────────────────────────────

def test_ref_anchor_id_on_superscript():
    wt = "Text.<ref>Note.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert 'id="cite-ref-1"' in html


def test_ref_anchor_id_on_footnote_item():
    wt = "Text.<ref>Note.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert 'id="cite-note-1"' in html


def test_back_arrow_in_footnote():
    wt = "Text.<ref>Note.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert '↑' in html


# ── Inline content in refs ────────────────────────────────────────────────────

def test_ref_content_with_external_link():
    wt = 'Text.<ref>[https://example.com Example site]</ref>\n\n<references />'
    html = render(wt, fmt="wikitext")
    assert 'href="https://example.com"' in html
    assert 'Example site' in html


def test_ref_content_with_bold():
    wt = "Text.<ref>'''Bold''' note.</ref>\n\n<references />"
    html = render(wt, fmt="wikitext")
    assert '<b>Bold</b>' in html


# ── References tag variants ───────────────────────────────────────────────────

def test_references_tag_with_spaces():
    wt = "Text.<ref>Note.</ref>\n\n<references  />"
    html = render(wt, fmt="wikitext")
    assert '<div class="references">' in html


def test_references_tag_case_insensitive():
    wt = "Text.<ref>Note.</ref>\n\n<REFERENCES />"
    html = render(wt, fmt="wikitext")
    assert '<div class="references">' in html
