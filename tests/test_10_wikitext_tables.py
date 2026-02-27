#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for wikitext table syntax rendering."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest

from app.services.renderer import render


# =============================================================================
# Basic table structure
# =============================================================================

def test_table_produces_table_tag():
    html = render("{|\n|-\n| cell\n|}", "wikitext")
    assert "<table" in html
    assert "</table>" in html


def test_table_gets_wikitable_class_by_default():
    html = render("{|\n|-\n| cell\n|}", "wikitext")
    assert 'class="wikitable"' in html


def test_table_preserves_explicit_class():
    html = render('{| class="my-table"\n|-\n| cell\n|}', "wikitext")
    assert 'class="my-table"' in html
    assert "wikitable" not in html


def test_table_preserves_extra_attrs():
    html = render('{| style="width:50%"\n|-\n| cell\n|}', "wikitext")
    assert 'style="width:50%"' in html


# =============================================================================
# Cells and rows
# =============================================================================

def test_table_single_data_cell():
    html = render("{|\n|-\n| Hello\n|}", "wikitext")
    assert "<td>Hello</td>" in html


def test_table_multiple_cells_on_one_row():
    html = render("{|\n|-\n| A || B || C\n|}", "wikitext")
    assert "<td>A</td>" in html
    assert "<td>B</td>" in html
    assert "<td>C</td>" in html


def test_table_cells_on_separate_lines():
    html = render("{|\n|-\n| A\n| B\n|}", "wikitext")
    assert "<td>A</td>" in html
    assert "<td>B</td>" in html


def test_table_multiple_rows():
    html = render("{|\n|-\n| R1C1\n|-\n| R2C1\n|}", "wikitext")
    assert html.count("<tr>") == 2
    assert "<td>R1C1</td>" in html
    assert "<td>R2C1</td>" in html


# =============================================================================
# Header cells
# =============================================================================

def test_table_header_cells():
    html = render("{|\n|-\n! Name !! Age\n|}", "wikitext")
    assert "<th>Name</th>" in html
    assert "<th>Age</th>" in html


def test_table_header_row_then_data_row():
    src = "{|\n|-\n! Name !! Age\n|-\n| Alice || 30\n|}"
    html = render(src, "wikitext")
    assert "<th>Name</th>" in html
    assert "<th>Age</th>" in html
    assert "<td>Alice</td>" in html
    assert "<td>30</td>" in html


def test_table_implicit_first_row_without_row_separator():
    """Header row without a leading |- should still be emitted."""
    html = render("{|\n! Col1 !! Col2\n|-\n| v1 || v2\n|}", "wikitext")
    assert "<th>Col1</th>" in html
    assert "<td>v1</td>" in html


# =============================================================================
# Caption
# =============================================================================

def test_table_caption():
    html = render("{|\n|+ My Caption\n|-\n| cell\n|}", "wikitext")
    assert "<caption>My Caption</caption>" in html


# =============================================================================
# Per-cell attributes
# =============================================================================

def test_table_cell_with_attrs():
    html = render('{|\n|-\n| style="color:red" | Red Text\n|}', "wikitext")
    assert 'style="color:red"' in html
    assert "Red Text" in html


def test_table_header_with_attrs():
    html = render('{|\n|-\n! colspan="2" | Wide Header\n|}', "wikitext")
    assert 'colspan="2"' in html
    assert "Wide Header" in html


# =============================================================================
# Inline markup inside cells
# =============================================================================

def test_table_cell_with_bold():
    html = render("{|\n|-\n| '''bold'''\n|}", "wikitext")
    assert "<b>bold</b>" in html


def test_table_cell_with_wikilink():
    html = render("{|\n|-\n| [[Some Page]]\n|}", "wikitext", namespace="Main")
    assert 'class="wikilink"' in html
    assert "Some Page" in html


def test_table_cell_with_external_link():
    html = render("{|\n|-\n| [https://example.com Example]\n|}", "wikitext")
    assert 'href="https://example.com"' in html
    assert "Example" in html


# =============================================================================
# Table mixed with surrounding content
# =============================================================================

def test_table_preceded_by_paragraph():
    src = "Intro text.\n\n{|\n|-\n| cell\n|}"
    html = render(src, "wikitext")
    assert "<p>Intro text.</p>" in html
    assert "<table" in html


def test_table_followed_by_paragraph():
    src = "{|\n|-\n| cell\n|}\n\nClosing text."
    html = render(src, "wikitext")
    assert "<table" in html
    assert "<p>Closing text.</p>" in html


def test_multiple_tables_in_same_page():
    src = "{|\n|-\n| T1\n|}\n\n{|\n|-\n| T2\n|}"
    html = render(src, "wikitext")
    assert html.count("<table") == 2
    assert "<td>T1</td>" in html
    assert "<td>T2</td>" in html


# =============================================================================
# Real-world example
# =============================================================================

def test_table_realistic_example():
    src = """{| class="wikitable"
|+ Programming Languages
|-
! Language !! Paradigm !! Typing
|-
| Python || Multi-paradigm || Dynamic
|-
| Go || Concurrent || Static
|-
| Haskell || Functional || Static
|}"""
    html = render(src, "wikitext")
    assert "<caption>Programming Languages</caption>" in html
    assert "<th>Language</th>" in html
    assert "<th>Paradigm</th>" in html
    assert "<td>Python</td>" in html
    assert "<td>Go</td>" in html
    assert "<td>Static</td>" in html
    assert html.count("<tr>") == 4  # 1 header row + 3 data rows


# -----------------------------------------------------------------------------
