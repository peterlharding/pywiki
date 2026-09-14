#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for category pages living in the Category namespace (MediaWiki model)."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.models import User
from app.services.renderer import render
from tests.conftest import auth_headers, cookie_auth, register_user

# -----------------------------------------------------------------------------

async def _setup(client, db_session, username="catmodel"):
    """Admin user, a Main namespace and the Category namespace (seeded at startup in real runs)."""
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(update(User).where(User.username == username).values(is_admin=True))
    await db_session.commit()
    headers = await auth_headers(client, username)
    for ns in ("Main", "Category"):
        await client.post("/api/v1/namespaces", json={"name": ns, "description": "", "default_format": "markdown"}, headers=headers)
    return headers


async def _page(client, headers, title, content, fmt="markdown", ns="Main"):
    resp = await client.post(f"/api/v1/namespaces/{ns}/pages", json={"title": title, "content": content, "format": fmt}, headers=headers)
    assert resp.status_code == 201, resp.text


# =============================================================================
# Category page
# =============================================================================

@pytest.mark.asyncio
async def test_old_category_url_redirects_to_category_namespace(client):
    resp = await client.get("/category/Fruit Dishes", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/wiki/Category/fruit-dishes"


@pytest.mark.asyncio
async def test_category_page_lists_members_from_all_formats(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Scones", "Baked.\n\n.. category:: Baking", fmt="rst")
    await _page(client, headers, "Bread", "Loaf.\n[[Category:Baking]]", fmt="wikitext")
    await _page(client, headers, "Salad", "Leaves.\n\n[[Category:Greens]]")

    resp = await client.get("/wiki/Category/baking")
    assert resp.status_code == 200
    assert "<h1>Category: Baking</h1>" in resp.text
    assert "Scones" in resp.text and "Bread" in resp.text
    assert "Salad" not in resp.text


@pytest.mark.asyncio
async def test_category_names_differing_only_in_case_or_spacing_are_one_category(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Apple Pie", "[[Category:Fruit Dishes]]")
    await _page(client, headers, "Plum Crumble", "[[Category:fruit dishes]]")
    html = (await client.get("/wiki/Category/fruit-dishes")).text
    assert "Apple Pie" in html and "Plum Crumble" in html
    assert "The following 2 pages are in this category." in html


@pytest.mark.asyncio
async def test_description_page_is_shown_with_members(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Scones", ".. category:: Baking", fmt="rst")
    await _page(client, headers, "Baking", "Things from an **oven**.", ns="Category")

    cookies = await cookie_auth(client, "catmodel")
    html = (await client.get("/wiki/Category/baking", headers=cookies)).text
    assert '<div class="wiki-content category-description">' in html
    assert "<strong>oven</strong>" in html
    assert "Scones" in html
    assert 'href="/wiki/Category/baking/edit"' in html
    assert 'href="/wiki/Category/baking/history"' in html


@pytest.mark.asyncio
async def test_creating_a_description_returns_to_the_category_page(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Salad", "[[Category:Greens]]")
    cookies = await cookie_auth(client, "catmodel")

    page = (await client.get("/wiki/Category/greens", headers=cookies)).text
    assert 'href="/create?namespace=Category&amp;title=Greens"' in page

    resp = await client.post(
        "/create",
        data={"namespace_name": "Category", "title": "Greens", "content": "Leafy things."},
        headers=cookies, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/wiki/Category/greens"
    assert "Leafy things." in (await client.get("/wiki/Category/greens")).text


@pytest.mark.asyncio
async def test_description_without_members(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Planned", "Nothing here yet.", ns="Category")
    resp = await client.get("/wiki/Category/planned")
    assert resp.status_code == 200
    assert "No pages are currently tagged with this category." in resp.text


@pytest.mark.asyncio
async def test_unknown_category_is_not_found(client, db_session):
    await _setup(client, db_session)
    resp = await client.get("/wiki/Category/no-such-thing")
    assert resp.status_code == 404
    assert "Category: No such thing" in resp.text


# =============================================================================
# Listings
# =============================================================================

@pytest.mark.asyncio
async def test_category_namespace_lists_every_category(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Scones", ".. category:: Baking", fmt="rst")
    await _page(client, headers, "Salad", "[[Category:Greens]]")
    await _page(client, headers, "Baking", "Oven things.", ns="Category")
    await _page(client, headers, "Planned", "Later.", ns="Category")

    cookies = await cookie_auth(client, "catmodel")
    html = (await client.get("/wiki/Category", headers=cookies)).text
    for slug, name in (("baking", "Baking"), ("greens", "Greens"), ("planned", "Planned")):
        assert f'<a href="/wiki/Category/{slug}">{name}</a>' in html
    assert html.count('<span class="badge">described</span>') == 2
    assert 'href="/create?namespace=Category&amp;title=Greens"' in html


@pytest.mark.asyncio
async def test_special_categories_includes_rst_categories(client, db_session):
    """Regression: categories declared only with RST ``.. category::`` were missing."""
    headers = await _setup(client, db_session)
    await _page(client, headers, "Scones", "Baked.\n\n.. category:: Baking", fmt="rst")
    await _page(client, headers, "Salad", "[[Category:Greens]]")
    html = (await client.get("/special/categories")).text
    assert '<a href="/wiki/Category/baking">Baking</a>' in html
    assert '<a href="/wiki/Category/greens">Greens</a>' in html


@pytest.mark.asyncio
async def test_special_pages_counts_only_categories_in_use(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Salad", "[[Category:Greens]]")
    await _page(client, headers, "Planned", "Later.", ns="Category")
    cookies = await cookie_auth(client, "catmodel")
    html = (await client.get("/special", headers=cookies)).text
    assert "1 category currently in use." in html


# =============================================================================
# Links
# =============================================================================

@pytest.mark.asyncio
async def test_page_category_bar_links_to_category_namespace(client, db_session):
    headers = await _setup(client, db_session)
    await _page(client, headers, "Apple Pie", "Pie.\n\n[[Category:Fruit Dishes]]")
    html = (await client.get("/wiki/Main/apple-pie")).text
    assert '<a href="/wiki/Category/fruit-dishes" class="category-link">Fruit Dishes</a>' in html


def test_wikitext_category_footer_links_to_category_namespace():
    html = render("Text\n[[Category:Fruit Dishes]]", "wikitext", base_url="https://wiki.example.com")
    assert 'href="https://wiki.example.com/wiki/Category/fruit-dishes" class="category-link"' in html


# -----------------------------------------------------------------------------
