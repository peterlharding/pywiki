"""
Tests for math rendering support (KaTeX).

Wikitext: <math>...</math> and <math display="block">...</math>
Markdown:  $...$ and $$...$$  (passed through as-is for KaTeX client-side)
RST:       :math:`...` (docutils emits <span class="math">; no server transform needed)
"""
import pytest
from app.services.renderer import render


# ---------------------------------------------------------------------------
# Wikitext — <math> tag
# ---------------------------------------------------------------------------

def test_wikitext_inline_math():
    html = render(r"<math>x^2 + y^2 = z^2</math>", "wikitext")
    assert r"\(x^2 + y^2 = z^2\)" in html


def test_wikitext_display_math():
    html = render(r'<math display="block">E = mc^2</math>', "wikitext")
    assert r"\[E = mc^2\]" in html


def test_wikitext_display_math_shorthand():
    """<math display="inline"> should NOT produce display (block) output."""
    html = render(r'<math display="inline">\alpha + \beta</math>', "wikitext")
    assert r"\(" in html
    assert r"\[" not in html


def test_wikitext_math_multiline():
    src = "<math display=\"block\">\n\\frac{a}{b}\n</math>"
    html = render(src, "wikitext")
    assert r"\[" in html
    assert r"\frac{a}{b}" in html
    assert r"\]" in html


def test_wikitext_math_inline_in_paragraph():
    html = render("The formula <math>E=mc^2</math> is famous.", "wikitext")
    assert r"\(E=mc^2\)" in html
    assert "famous" in html


def test_wikitext_math_not_escaped():
    """LaTeX content must not be HTML-escaped by the renderer."""
    html = render(r"<math>a < b</math>", "wikitext")
    assert r"\(a < b\)" in html or r"\(a &lt; b\)" not in html


# ---------------------------------------------------------------------------
# Markdown — $ and $$ delimiters passed through unchanged
# ---------------------------------------------------------------------------

def test_markdown_inline_math_passthrough():
    """$...$ must survive Markdown rendering so KaTeX can process it client-side."""
    html = render(r"The value is $x^2$.", "markdown")
    assert "$x^2$" in html or r"\(x^2\)" in html


def test_markdown_display_math_passthrough():
    """$$...$$ must survive Markdown rendering."""
    html = render("$$\nE = mc^2\n$$", "markdown")
    assert "E = mc^2" in html


# ---------------------------------------------------------------------------
# RST — :math: role emits <span class="math"> which KaTeX handles client-side
# ---------------------------------------------------------------------------

def test_rst_inline_math_span():
    """:math:`...` role should produce a <span> containing the LaTeX."""
    html = render(r"The value is :math:`x^2`.", "rst")
    assert "x^2" in html
    assert "<span" in html
