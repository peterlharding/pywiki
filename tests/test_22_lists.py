#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for list rendering: valid nesting in wikitext, compact list styling."""
# -----------------------------------------------------------------------------

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.services.renderer import RENDERER_VERSION, render

# -----------------------------------------------------------------------------

class _ListNesting(HTMLParser):
    """Records list markup that is not validly nested."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        parent = self.stack[-1] if self.stack else None
        if tag in ("ul", "ol") and parent in ("ul", "ol"):
            self.errors.append(f"<{tag}> directly inside <{parent}>")
        if tag == "li" and parent not in ("ul", "ol"):
            self.errors.append(f"<li> inside <{parent}>")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}>")
            return
        self.stack.pop()


def _wikitext(src: str) -> str:
    html = render(src, "wikitext").split("-->", 1)[1]
    checker = _ListNesting()
    checker.feed(html)
    assert checker.errors == [] and checker.stack == [], (checker.errors, checker.stack, html)
    return html.replace("\n", "")


# =============================================================================
# Wikitext list structure
# =============================================================================

def test_renderer_version_bumped_for_list_markup():
    assert RENDERER_VERSION >= 16


def test_nested_bullets_are_inside_their_parent_item():
    html = _wikitext("* A\n* B\n** B1\n** B2\n* C")
    assert html == "<ul><li>A</li><li>B<ul><li>B1</li><li>B2</li></ul></li><li>C</li></ul>"


def test_nested_numbered_list():
    html = _wikitext("# One\n# Two\n## Two.a\n# Three")
    assert html == "<ol><li>One</li><li>Two<ol><li>Two.a</li></ol></li><li>Three</li></ol>"


def test_numbered_list_inside_bullet():
    html = _wikitext("* Bullet\n*# first\n*# second\n* Back")
    assert html == "<ul><li>Bullet<ol><li>first</li><li>second</li></ol></li><li>Back</li></ul>"


def test_list_starting_below_top_level_gets_empty_parent_item():
    assert _wikitext("** deep\n* shallow") == "<ul><li><ul><li>deep</li></ul></li><li>shallow</li></ul>"


def test_switching_list_type_starts_a_new_list():
    assert _wikitext("* A\n# B") == "<ul><li>A</li></ul><ol><li>B</li></ol>"


@pytest.mark.parametrize("after", ["\nParagraph", "\n; term : definition", "\n{|\n| cell\n|}"])
def test_lists_close_before_other_blocks(after):
    _wikitext("* A\n** B" + after)


def test_list_items_keep_inline_markup():
    assert "<li>'''bold'''" not in _wikitext("* '''bold''' item")
    assert "<li><b>bold</b> item</li>" in _wikitext("* '''bold''' item")


# =============================================================================
# Styling
# =============================================================================

def test_list_styles_are_compact():
    css = (Path(__file__).parent.parent / "app/static/css/wiki.css").read_text()
    assert ".wiki-content li { margin: 0.1em 0; line-height: 1.55; }" in css
    # RST and loose Markdown wrap items in <p>
    assert ".wiki-content li > p { margin: 0; }" in css
    assert ".wiki-content li ul, .wiki-content li ol { margin: 0.1em 0 0.1em 1.5em; }" in css


# -----------------------------------------------------------------------------
