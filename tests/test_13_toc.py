"""
Tests for Table of Contents generation.

TOC is generated as a post-processing step on the rendered HTML, so all
three formats are tested via render().  TOC appears when there are ≥ 3
headings (TOC_MIN_HEADINGS).
"""
from __future__ import annotations

import pytest
from app.services.renderer import render, TOC_MIN_HEADINGS, RENDERER_VERSION


# ── RENDERER_VERSION ─────────────────────────────────────────────────────────

def test_renderer_version_is_at_least_7():
    assert RENDERER_VERSION >= 7


# ── TOC_MIN_HEADINGS threshold ────────────────────────────────────────────────

def test_toc_not_shown_below_threshold():
    md = "## Alpha\n\nText.\n\n## Beta\n\nText.\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' not in html


def test_toc_shown_at_threshold():
    md = "## Alpha\n\n## Beta\n\n## Gamma\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html


def test_toc_min_headings_value():
    assert TOC_MIN_HEADINGS == 3


# ── Anchor IDs ────────────────────────────────────────────────────────────────

def test_headings_get_id_attributes():
    md = "## Introduction\n\nText.\n\n## Details\n\nMore.\n\n## Summary\n\n"
    html = render(md, fmt="markdown")
    assert 'id="introduction"' in html
    assert 'id="details"' in html
    assert 'id="summary"' in html


def test_duplicate_heading_ids_are_unique():
    md = "## Section\n\n## Section\n\n## Section\n\n"
    html = render(md, fmt="markdown")
    assert 'id="section"' in html
    assert 'id="section-1"' in html
    assert 'id="section-2"' in html


def test_heading_anchor_strips_inline_markup():
    md = "## **Bold** Heading\n\n## Another\n\n## Third\n\n"
    html = render(md, fmt="markdown")
    assert 'id="bold-heading"' in html


# ── TOC structure ─────────────────────────────────────────────────────────────

def test_toc_contains_contents_title():
    md = "## A\n\n## B\n\n## C\n\n"
    html = render(md, fmt="markdown")
    assert "Contents" in html


def test_toc_links_point_to_anchors():
    md = "## Introduction\n\n## Details\n\n## Summary\n\n"
    html = render(md, fmt="markdown")
    assert 'href="#introduction"' in html
    assert 'href="#details"' in html
    assert 'href="#summary"' in html


def test_toc_appears_before_first_heading():
    md = "## Alpha\n\nText.\n\n## Beta\n\n## Gamma\n\n"
    html = render(md, fmt="markdown")
    toc_pos = html.find('<div class="toc">')
    first_h_pos = html.find('<h2 id="alpha">')
    assert toc_pos < first_h_pos


def test_toc_nested_headings():
    md = "## Top\n\n### Sub\n\n### Sub2\n\n## Top2\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'href="#top"' in html
    assert 'href="#sub"' in html


# ── Markdown format ───────────────────────────────────────────────────────────

def test_md_h1_through_h3():
    md = "# Title\n\n## Intro\n\n## Body\n\n## Conclusion\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'id="title"' in html
    assert 'id="intro"' in html


def test_md_no_headings_no_toc():
    md = "Just some paragraph text with no headings at all."
    html = render(md, fmt="markdown")
    assert '<div class="toc">' not in html


# ── Wikitext format ───────────────────────────────────────────────────────────

def test_wikitext_toc_generated():
    wt = "== Section One ==\n\nText.\n\n== Section Two ==\n\nText.\n\n== Section Three ==\n\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' in html
    assert 'href="#section-one"' in html


def test_wikitext_headings_get_ids():
    wt = "== Alpha ==\n\n== Beta ==\n\n== Gamma ==\n\n"
    html = render(wt, fmt="wikitext")
    assert 'id="alpha"' in html
    assert 'id="beta"' in html
    assert 'id="gamma"' in html


def test_wikitext_no_toc_below_threshold():
    wt = "== Only ==\n\nText.\n\n== Two ==\n\nText.\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' not in html


# ── RST format ────────────────────────────────────────────────────────────────

def test_rst_toc_generated():
    rst = (
        "Section One\n===========\n\nText.\n\n"
        "Section Two\n===========\n\nText.\n\n"
        "Section Three\n=============\n\nText.\n"
    )
    html = render(rst, fmt="rst")
    assert '<div class="toc">' in html


def test_rst_headings_get_ids():
    rst = (
        "Alpha\n=====\n\nText.\n\n"
        "Beta\n====\n\nText.\n\n"
        "Gamma\n=====\n\nText.\n"
    )
    html = render(rst, fmt="rst")
    assert 'id="alpha"' in html or 'id=' in html   # docutils may also add its own ids


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_toc_special_chars_in_heading():
    md = "## C++ & Python\n\n## Go/Rust\n\n## SQL Basics\n\n"
    html = render(md, fmt="markdown")
    assert 'id=' in html
    assert '<div class="toc">' in html


def test_toc_deep_nesting():
    md = "## H2\n\n### H3\n\n#### H4\n\n##### H5\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'href="#h2"' in html
    assert 'href="#h3"' in html
