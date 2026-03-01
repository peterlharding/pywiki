"""
Tests for inline image embedding across all three formats.

Renderer is tested directly (no HTTP round-trip needed for embedding logic).
Upload/serve integration is covered via the attachment API tests already in
test_03_pages.py / test_04_attachments.py (if present).
"""
from __future__ import annotations

import pytest
from app.services.renderer import render, RENDERER_VERSION


# ── RENDERER_VERSION ─────────────────────────────────────────────────────────

def test_renderer_version_is_8():
    assert RENDERER_VERSION == 8


# ── Wikitext [[File:]] rendering ──────────────────────────────────────────────

ATT = {"photo.png": "/api/v1/attachments/abc/photo.png",
       "diagram.gif": "/api/v1/attachments/def/diagram.gif"}


def test_wikitext_file_thumb_renders_figure():
    wt = "[[File:photo.png|thumb|My caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "<figure" in html
    assert 'class="wiki-figure' in html
    assert 'src="/api/v1/attachments/abc/photo.png"' in html
    assert "<figcaption>My caption</figcaption>" in html


def test_wikitext_file_thumb_no_caption():
    wt = "[[File:photo.png|thumb]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "<figure" in html
    assert "<figcaption>" not in html


def test_wikitext_file_inline_no_thumb():
    wt = "[[File:photo.png]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert '<img' in html
    assert 'src="/api/v1/attachments/abc/photo.png"' in html
    assert "<figure" not in html


def test_wikitext_file_align_right():
    wt = "[[File:photo.png|thumb|right|Caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "img-right" in html


def test_wikitext_file_align_left():
    wt = "[[File:photo.png|thumb|left|Caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "img-left" in html


def test_wikitext_file_missing_shows_placeholder():
    wt = "[[File:notfound.png|thumb|Caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'class="missing-file"' in html
    assert "<figure" not in html
    assert "<img" not in html


def test_wikitext_file_no_attachments_dict_shows_placeholder():
    wt = "[[File:photo.png|thumb|Caption]]"
    html = render(wt, fmt="wikitext", attachments=None)
    assert 'class="missing-file"' in html


def test_wikitext_file_case_insensitive():
    wt = "[[file:photo.png|thumb|Caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'src="/api/v1/attachments/abc/photo.png"' in html


def test_wikitext_file_does_not_break_regular_wikilinks():
    wt = "[[File:photo.png|thumb]] and [[Other Page]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'class="wikilink"' in html
    assert "Other Page" in html
    assert "<figure" in html


def test_wikitext_multiple_files():
    wt = "[[File:photo.png|thumb|First]] and [[File:diagram.gif|thumb|Second]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert html.count("<figure") == 2
    assert "First" in html
    assert "Second" in html


# ── Markdown attachment: shorthand ────────────────────────────────────────────

def test_md_attachment_shorthand_resolved():
    md = "![My photo](attachment:photo.png)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert 'src="/api/v1/attachments/abc/photo.png"' in html
    assert 'alt="My photo"' in html


def test_md_attachment_shorthand_missing_unchanged():
    md = "![Alt text](attachment:notfound.png)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert "attachment:notfound.png" in html


def test_md_attachment_shorthand_no_att_dict_unchanged():
    md = "![Alt](attachment:photo.png)"
    html = render(md, fmt="markdown", attachments=None)
    assert "attachment:photo.png" in html


def test_md_regular_image_url_unaffected():
    md = "![Alt](https://example.com/img.png)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert 'src="https://example.com/img.png"' in html


def test_md_multiple_attachments():
    md = "![A](attachment:photo.png) and ![B](attachment:diagram.gif)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert "/attachments/abc/photo.png" in html
    assert "/attachments/def/diagram.gif" in html


# ── Markdown attachment: size suffix ─────────────────────────────────────────

def test_md_attachment_width_only():
    md = "![photo](attachment:photo.png|200)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert 'width="200"' in html
    assert 'src="/api/v1/attachments/abc/photo.png"' in html
    assert 'height=' not in html


def test_md_attachment_height_only():
    md = "![photo](attachment:photo.png|x150)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert 'height="150"' in html
    assert 'width=' not in html


def test_md_attachment_width_and_height():
    md = "![photo](attachment:photo.png|300x200)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert 'width="300"' in html
    assert 'height="200"' in html


def test_md_attachment_no_size_stays_markdown_img():
    md = "![photo](attachment:photo.png)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert '<img' in html
    assert 'width=' not in html
    assert 'height=' not in html


def test_md_attachment_size_missing_file_unchanged():
    md = "![photo](attachment:notfound.png|200x100)"
    html = render(md, fmt="markdown", attachments=ATT)
    assert "notfound.png" in html
    assert 'width=' not in html


# ── Wikitext [[File:]] size modifiers ────────────────────────────────────────

def test_wikitext_file_width_only():
    wt = "[[File:photo.png|200px]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'width="200"' in html
    assert 'height=' not in html


def test_wikitext_file_height_only():
    wt = "[[File:photo.png|x150px]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'height="150"' in html
    assert 'width=' not in html


def test_wikitext_file_width_and_height():
    wt = "[[File:photo.png|300x200px]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert 'width="300"' in html
    assert 'height="200"' in html


def test_wikitext_file_thumb_with_size():
    wt = "[[File:photo.png|thumb|200px|My caption]]"
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "<figure" in html
    assert 'width="200"' in html
    assert "My caption" in html


# ── No attachments — no regressions ──────────────────────────────────────────

def test_wikitext_no_file_syntax_unaffected():
    wt = "== Section ==\n\nJust text.\n\n== Other ==\n\n== Third =="
    html = render(wt, fmt="wikitext", attachments=ATT)
    assert "<img" not in html
    assert "<figure" not in html


def test_md_no_attachment_syntax_unaffected():
    md = "## Hello\n\nJust text with **bold**.\n\n## Bye\n\n## Three"
    html = render(md, fmt="markdown", attachments=ATT)
    assert "<img" not in html
