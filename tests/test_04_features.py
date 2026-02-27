#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for categories, recent changes, special pages, and printable version."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models import User
from app.services.renderer import extract_categories
from tests.conftest import auth_headers, register_user


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _setup(client, db_session, username, ns_name, fmt="markdown"):
    """Register an admin user and create a namespace."""
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()
    headers = await auth_headers(client, username)
    await client.post("/api/v1/namespaces", json={
        "name": ns_name, "description": "", "default_format": fmt,
    }, headers=headers)
    return headers


async def _create_page(client, ns, title, content, fmt, headers):
    resp = await client.post(f"/api/v1/namespaces/{ns}/pages", json={
        "title": title, "content": content, "format": fmt, "comment": "test",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# =============================================================================
# extract_categories() unit tests
# =============================================================================

def test_extract_categories_wikitext():
    content = "Some text.\n[[Category:Software]]\n[[Category:Python]]"
    cats = extract_categories(content, "wikitext")
    assert cats == ["Python", "Software"]


def test_extract_categories_markdown():
    content = "# Title\n\n[[Category:Tools]]\n[[Category:Open Source]]"
    cats = extract_categories(content, "markdown")
    assert cats == ["Open Source", "Tools"]


def test_extract_categories_rst():
    content = "Title\n=====\n\n.. category:: Science\n.. category:: Research\n"
    cats = extract_categories(content, "rst")
    assert cats == ["Research", "Science"]


def test_extract_categories_case_insensitive_dedup():
    content = "[[Category:Foo]]\n[[category:foo]]\n[[Category:Bar]]"
    cats = extract_categories(content, "wikitext")
    assert len(cats) == 2
    assert "Bar" in cats


def test_extract_categories_empty():
    assert extract_categories("No categories here.", "markdown") == []


def test_extract_categories_wikitext_in_rendered_format():
    content = "= Heading =\n\nSome '''bold''' text.\n\n[[Category:Drones]]"
    cats = extract_categories(content, "wikitext")
    assert cats == ["Drones"]


# =============================================================================
# Category page API / UI tests
# =============================================================================

@pytest.mark.asyncio
async def test_category_page_lists_tagged_pages(client, db_session):
    headers = await _setup(client, db_session, "catuser1", "CatNS1")
    await _create_page(client, "CatNS1", "Alpha Page",
                       "Content.\n[[Category:Science]]", "markdown", headers)
    await _create_page(client, "CatNS1", "Beta Page",
                       "Content.\n[[Category:Science]]", "markdown", headers)
    await _create_page(client, "CatNS1", "Gamma Page",
                       "No category here.", "markdown", headers)

    resp = await client.get("/category/Science")
    assert resp.status_code == 200
    html = resp.text
    assert "Alpha Page" in html
    assert "Beta Page" in html
    assert "Gamma Page" not in html


@pytest.mark.asyncio
async def test_category_page_empty_for_unknown_category(client, db_session):
    await _setup(client, db_session, "catuser2", "CatNS2")
    resp = await client.get("/category/NonExistentCategory")
    assert resp.status_code == 200
    assert "No pages" in resp.text


@pytest.mark.asyncio
async def test_category_page_case_insensitive(client, db_session):
    headers = await _setup(client, db_session, "catuser3", "CatNS3")
    await _create_page(client, "CatNS3", "Tagged Page",
                       "[[Category:Animals]]", "markdown", headers)

    resp = await client.get("/category/Animals")
    assert resp.status_code == 200
    assert "Tagged Page" in resp.text


@pytest.mark.asyncio
async def test_category_links_appear_on_page_view(client, db_session):
    headers = await _setup(client, db_session, "catuser4", "CatNS4")
    await _create_page(client, "CatNS4", "Cat Link Test",
                       "Text.\n[[Category:Tech]]", "markdown", headers)

    resp = await client.get("/wiki/CatNS4/cat-link-test")
    assert resp.status_code == 200
    html = resp.text
    assert "/category/Tech" in html
    assert "Tech" in html


@pytest.mark.asyncio
async def test_wikitext_categories_render_in_footer(client, db_session):
    headers = await _setup(client, db_session, "catuser5", "CatNS5")
    await _create_page(client, "CatNS5", "Wiki Cat Page",
                       "= Title =\n\nSome content.\n\n[[Category:Robotics]]",
                       "wikitext", headers)

    resp = await client.get("/wiki/CatNS5/wiki-cat-page")
    assert resp.status_code == 200
    html = resp.text
    assert "/category/Robotics" in html


# =============================================================================
# Recent Changes UI tests
# =============================================================================

@pytest.mark.asyncio
async def test_recent_changes_page_loads(client, db_session):
    await _setup(client, db_session, "rcuser1", "RCNS1")
    resp = await client.get("/recent")
    assert resp.status_code == 200
    assert "Recent Changes" in resp.text


@pytest.mark.asyncio
async def test_recent_changes_shows_edited_pages(client, db_session):
    headers = await _setup(client, db_session, "rcuser2", "RCNS2")
    await _create_page(client, "RCNS2", "RC Test Page",
                       "Content here.", "markdown", headers)

    resp = await client.get("/recent")
    assert resp.status_code == 200
    assert "RC Test Page" in resp.text


@pytest.mark.asyncio
async def test_recent_changes_namespace_filter(client, db_session):
    headers = await _setup(client, db_session, "rcuser3", "RCNS3")
    await _create_page(client, "RCNS3", "Filtered Page",
                       "Content.", "markdown", headers)

    resp = await client.get("/recent?namespace=RCNS3")
    assert resp.status_code == 200
    assert "Filtered Page" in resp.text


@pytest.mark.asyncio
async def test_recent_changes_namespace_filter_excludes_others(client, db_session):
    headers = await _setup(client, db_session, "rcuser4", "RCNS4")
    await _create_page(client, "RCNS4", "In RCNS4", "Content.", "markdown", headers)

    # Filter on a different namespace — page should not appear
    resp = await client.get("/recent?namespace=RCNS4_other")
    assert resp.status_code == 200
    assert "In RCNS4" not in resp.text


@pytest.mark.asyncio
async def test_recent_changes_limit_param(client, db_session):
    headers = await _setup(client, db_session, "rcuser5", "RCNS5")
    for i in range(5):
        await _create_page(client, "RCNS5", f"RC Limit {i}",
                           f"content {i}", "markdown", headers)

    resp = await client.get("/recent?limit=25")
    assert resp.status_code == 200


# =============================================================================
# Special Pages UI tests
# =============================================================================

@pytest.mark.asyncio
async def test_special_pages_loads(client, db_session):
    resp = await client.get("/special")
    assert resp.status_code == 200
    assert "Special Pages" in resp.text


@pytest.mark.asyncio
async def test_special_pages_shows_stats(client, db_session):
    headers = await _setup(client, db_session, "spuser1", "SPNS1")
    await _create_page(client, "SPNS1", "Stats Page",
                       "Content.", "markdown", headers)

    resp = await client.get("/special")
    assert resp.status_code == 200
    html = resp.text
    assert "Total pages" in html
    assert "Total revisions" in html
    assert "Registered users" in html


@pytest.mark.asyncio
async def test_special_pages_shows_namespaces(client, db_session):
    await _setup(client, db_session, "spuser2", "SPNS2")

    resp = await client.get("/special")
    assert resp.status_code == 200
    assert "SPNS2" in resp.text


@pytest.mark.asyncio
async def test_special_pages_shows_categories(client, db_session):
    headers = await _setup(client, db_session, "spuser3", "SPNS3")
    await _create_page(client, "SPNS3", "Cat Special",
                       "[[Category:SpecialCat]]", "markdown", headers)

    resp = await client.get("/special")
    assert resp.status_code == 200
    assert "SpecialCat" in resp.text


# =============================================================================
# Printable version UI tests
# =============================================================================

@pytest.mark.asyncio
async def test_print_page_loads(client, db_session):
    headers = await _setup(client, db_session, "printuser1", "PNS1")
    await _create_page(client, "PNS1", "Print Me",
                       "# Hello\n\nPrintable content.", "markdown", headers)

    resp = await client.get("/wiki/PNS1/print-me/print")
    assert resp.status_code == 200
    html = resp.text
    assert "Print Me" in html
    assert "Printable content" in html


@pytest.mark.asyncio
async def test_print_page_has_no_nav(client, db_session):
    headers = await _setup(client, db_session, "printuser2", "PNS2")
    await _create_page(client, "PNS2", "No Nav Print",
                       "Content.", "markdown", headers)

    resp = await client.get("/wiki/PNS2/no-nav-print/print")
    assert resp.status_code == 200
    html = resp.text
    # Printable page does not extend base.html — no navbar
    assert 'class="navbar"' not in html


@pytest.mark.asyncio
async def test_print_page_shows_categories(client, db_session):
    headers = await _setup(client, db_session, "printuser3", "PNS3")
    await _create_page(client, "PNS3", "Cat Print",
                       "Text.\n[[Category:PrintCat]]", "markdown", headers)

    resp = await client.get("/wiki/PNS3/cat-print/print")
    assert resp.status_code == 200
    assert "PrintCat" in resp.text


@pytest.mark.asyncio
async def test_print_page_404_for_missing(client, db_session):
    await _setup(client, db_session, "printuser4", "PNS4")
    resp = await client.get("/wiki/PNS4/does-not-exist/print")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_print_page_wikitext(client, db_session):
    headers = await _setup(client, db_session, "printuser5", "PNS5")
    await _create_page(client, "PNS5", "Wiki Print",
                       "= Heading =\n\n'''Bold text'''\n\n[[Category:WikiPrint]]",
                       "wikitext", headers)

    resp = await client.get("/wiki/PNS5/wiki-print/print")
    assert resp.status_code == 200
    html = resp.text
    assert "<h1>" in html
    assert "WikiPrint" in html


# -----------------------------------------------------------------------------
