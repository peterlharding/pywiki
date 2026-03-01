"""
Tests for syntax highlighting across all three formats.

Pygments is always available in the venv, so we test the full highlighted
output path (span elements with class names).  All tests use the renderer
directly — no HTTP round-trip needed.
"""
from __future__ import annotations

import pytest
from app.services.renderer import render


# ── Markdown fenced code blocks ───────────────────────────────────────────────

def test_md_fenced_python_produces_highlight_div():
    html = render("```python\nx = 1\n```", fmt="markdown")
    assert '<div class="highlight">' in html


def test_md_fenced_python_contains_span():
    html = render("```python\nx = 1\n```", fmt="markdown")
    assert "<span" in html


def test_md_fenced_unknown_lang_falls_back_to_pre():
    html = render("```zzznotalang\nhello\n```", fmt="markdown")
    assert "<pre>" in html or '<div class="highlight">' in html


def test_md_fenced_no_lang_produces_pre():
    html = render("```\nplain text\n```", fmt="markdown")
    assert "<pre>" in html
    assert "plain text" in html


def test_md_fenced_javascript():
    html = render("```javascript\nconsole.log('hi');\n```", fmt="markdown")
    assert '<div class="highlight">' in html


def test_md_fenced_sql():
    html = render("```sql\nSELECT * FROM pages;\n```", fmt="markdown")
    assert '<div class="highlight">' in html


def test_md_inline_code_not_highlighted():
    html = render("Use `print()` to output.", fmt="markdown")
    assert "<code>" in html
    assert "print()" in html


# ── Wikitext <syntaxhighlight> ─────────────────────────────────────────────

def test_wikitext_syntaxhighlight_tag():
    html = render('<syntaxhighlight lang="python">\nx = 1\n</syntaxhighlight>', fmt="wikitext")
    assert '<div class="highlight">' in html


def test_wikitext_syntaxhighlight_contains_span():
    html = render('<syntaxhighlight lang="python">\ndef foo(): pass\n</syntaxhighlight>', fmt="wikitext")
    assert "<span" in html


def test_wikitext_syntaxhighlight_no_lang_falls_back():
    html = render('<syntaxhighlight>\nhello world\n</syntaxhighlight>', fmt="wikitext")
    assert "hello world" in html
    assert "<pre>" in html or '<div class="highlight">' in html


def test_wikitext_pre_tag_produces_pre():
    html = render('<pre>\nhello\n</pre>', fmt="wikitext")
    assert "<pre>" in html
    assert "hello" in html


def test_wikitext_fenced_block_with_lang():
    html = render('```python\nprint("hi")\n```', fmt="wikitext")
    assert '<div class="highlight">' in html


def test_wikitext_fenced_block_no_lang():
    html = render('```\nplain\n```', fmt="wikitext")
    assert "<pre>" in html
    assert "plain" in html


def test_wikitext_space_indented_produces_pre():
    html = render(' indented code line', fmt="wikitext")
    assert "<pre>" in html
    assert "indented code line" in html


def test_wikitext_code_does_not_interfere_with_surrounding_text():
    content = "Before\n```python\nx = 1\n```\nAfter"
    html = render(content, fmt="wikitext")
    assert "Before" in html
    assert "After" in html
    assert '<div class="highlight">' in html


# ── RST code blocks ───────────────────────────────────────────────────────────

def test_rst_code_block_produces_pre():
    rst = "Example::\n\n    x = 1\n"
    html = render(rst, fmt="rst")
    assert "<pre" in html
    assert "x = 1" in html


def test_rst_inline_code():
    html = render("Use ``print()`` to output.", fmt="rst")
    assert "print()" in html
    assert "literal" in html or "<code>" in html or "<tt" in html


# ── RENDERER_VERSION ─────────────────────────────────────────────────────────

def test_renderer_version_is_current():
    from app.services.renderer import RENDERER_VERSION
    assert RENDERER_VERSION >= 7
