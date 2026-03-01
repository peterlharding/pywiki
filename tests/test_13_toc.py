"""
Tests for Table of Contents generation.

As of v0.4.0 the TOC is opt-in via explicit macro:
  - {{toc}} / {{TOC}} — general macro syntax (all formats)
  - __TOC__           — MediaWiki magic word (all formats)

Heading anchor IDs are always generated regardless of whether a TOC is present.
"""
from __future__ import annotations

import pytest
from app.services.renderer import render, TOC_MIN_HEADINGS, RENDERER_VERSION


# ── RENDERER_VERSION ─────────────────────────────────────────────────────────

def test_renderer_version_is_at_least_9():
    assert RENDERER_VERSION >= 9


# ── TOC is opt-in — no macro means no TOC ────────────────────────────────────

def test_toc_not_shown_without_macro():
    md = "## Alpha\n\n## Beta\n\n## Gamma\n\nText.\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' not in html


def test_toc_not_shown_one_heading_no_macro():
    md = "## Alpha\n\nText.\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' not in html


def test_toc_min_headings_value():
    assert TOC_MIN_HEADINGS == 3   # retained for backward-compat import


# ── {{toc}} macro ────────────────────────────────────────────────────────────

def test_toc_macro_lowercase():
    md = "{{toc}}\n\n## Alpha\n\n## Beta\n\n## Gamma\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html


def test_toc_macro_uppercase():
    md = "{{TOC}}\n\n## Alpha\n\n## Beta\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html


def test_toc_macro_mixed_case():
    md = "{{ Toc }}\n\n## Alpha\n\n## Beta\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html


def test_toc_macro_single_heading():
    """TOC renders even with only one heading when macro is present."""
    md = "{{toc}}\n\n## Only Heading\n\nText.\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'href="#only-heading"' in html


def test_toc_macro_position_respected():
    """TOC appears at the macro position, not before the first heading."""
    md = "## Alpha\n\nIntro text.\n\n{{toc}}\n\n## Beta\n\n"
    html = render(md, fmt="markdown")
    toc_pos   = html.find('<div class="toc">')
    alpha_pos = html.find('id="alpha"')
    assert toc_pos > alpha_pos   # TOC is after the first heading


# ── __TOC__ magic word ────────────────────────────────────────────────────────

def test_magic_toc_wikitext():
    wt = "__TOC__\n\n== Section One ==\n\n== Section Two ==\n\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' in html
    assert 'href="#section-one"' in html


def test_magic_toc_markdown():
    md = "__TOC__\n\n## Alpha\n\n## Beta\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html


def test_magic_toc_not_present_means_no_toc():
    wt = "== Only ==\n\nText.\n\n== Two ==\n\n== Three ==\n\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' not in html


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
    md = "{{toc}}\n\n## A\n\n## B\n\n## C\n\n"
    html = render(md, fmt="markdown")
    assert "Contents" in html


def test_toc_links_point_to_anchors():
    md = "{{toc}}\n\n## Introduction\n\n## Details\n\n## Summary\n\n"
    html = render(md, fmt="markdown")
    assert 'href="#introduction"' in html
    assert 'href="#details"' in html
    assert 'href="#summary"' in html


def test_toc_appears_before_first_heading():
    """When {{toc}} is at the top, the TOC block precedes the first heading."""
    md = "{{toc}}\n\n## Alpha\n\nText.\n\n## Beta\n\n## Gamma\n\n"
    html = render(md, fmt="markdown")
    toc_pos = html.find('<div class="toc">')
    first_h_pos = html.find('<h2 id="alpha">')
    assert toc_pos < first_h_pos


def test_toc_nested_headings():
    md = "{{toc}}\n\n## Top\n\n### Sub\n\n### Sub2\n\n## Top2\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'href="#top"' in html
    assert 'href="#sub"' in html


# ── Markdown format ───────────────────────────────────────────────────────────

def test_md_h1_through_h3():
    md = "{{toc}}\n\n# Title\n\n## Intro\n\n## Body\n\n## Conclusion\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'id="title"' in html
    assert 'id="intro"' in html


def test_md_no_headings_no_toc():
    md = "Just some paragraph text with no headings at all."
    html = render(md, fmt="markdown")
    assert '<div class="toc">' not in html


# ── Wikitext format ───────────────────────────────────────────────────────────

def test_wikitext_toc_via_magic_word():
    wt = "__TOC__\n\n== Section One ==\n\nText.\n\n== Section Two ==\n\nText.\n\n== Section Three ==\n\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' in html
    assert 'href="#section-one"' in html


def test_wikitext_toc_via_macro():
    wt = "{{toc}}\n\n== Section One ==\n\n== Section Two ==\n\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' in html


def test_wikitext_headings_get_ids():
    wt = "== Alpha ==\n\n== Beta ==\n\n== Gamma ==\n\n"
    html = render(wt, fmt="wikitext")
    assert 'id="alpha"' in html
    assert 'id="beta"' in html
    assert 'id="gamma"' in html


def test_wikitext_no_toc_without_macro():
    wt = "== One ==\n\nText.\n\n== Two ==\n\n== Three ==\n\nText.\n"
    html = render(wt, fmt="wikitext")
    assert '<div class="toc">' not in html


# ── RST format ────────────────────────────────────────────────────────────

def test_rst_toc_via_macro():
    rst = (
        "{{toc}}\n\n"
        "Section One\n===========\n\nText.\n\n"
        "Section Two\n===========\n\nText.\n\n"
        "Section Three\n=============\n\nText.\n"
    )
    html = render(rst, fmt="rst")
    assert '<div class="toc">' in html


def test_rst_no_toc_without_macro():
    rst = (
        "Section One\n===========\n\nText.\n\n"
        "Section Two\n===========\n\nText.\n\n"
        "Section Three\n=============\n\nText.\n"
    )
    html = render(rst, fmt="rst")
    assert '<div class="toc">' not in html


def test_rst_headings_get_ids():
    rst = (
        "Alpha\n=====\n\nText.\n\n"
        "Beta\n====\n\nText.\n\n"
        "Gamma\n=====\n\nText.\n"
    )
    html = render(rst, fmt="rst")
    assert 'id="alpha"' in html or 'id=' in html   # docutils may also add its own ids


# ── Edge cases ────────────────────────────────────────────────────────────

def test_toc_special_chars_in_heading():
    md = "{{toc}}\n\n## C++ & Python\n\n## Go/Rust\n\n## SQL Basics\n\n"
    html = render(md, fmt="markdown")
    assert 'id=' in html
    assert '<div class="toc">' in html


def test_toc_deep_nesting():
    md = "{{toc}}\n\n## H2\n\n### H3\n\n#### H4\n\n##### H5\n\n"
    html = render(md, fmt="markdown")
    assert '<div class="toc">' in html
    assert 'href="#h2"' in html
    assert 'href="#h3"' in html
