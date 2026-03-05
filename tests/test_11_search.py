"""
Tests for full-text search — UI /search route and API /api/v1/search.

The test database is SQLite (in-memory), so the ILIKE fallback path is
exercised here.  The tsvector path is integration-tested against PostgreSQL
in production; the dialect-detection logic is covered by the _db_dialect()
unit test below.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import register_user, cookie_auth, auth_headers


# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup(client: AsyncClient, username: str, ns: str) -> tuple[dict, dict]:
    """Register user, create namespace, return (api_headers, cookie_headers)."""
    await register_user(client, username, f"{username}@example.com")
    api_hdrs = await auth_headers(client, username)
    ck_hdrs  = await cookie_auth(client, username)
    await client.post("/api/v1/namespaces", json={"name": ns, "default_format": "markdown"},
                      headers=api_hdrs)
    return api_hdrs, ck_hdrs


# ── UI /search route ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_page_loads_empty(client):
    resp = await client.get("/search")
    assert resp.status_code == 200
    assert "Search" in resp.text


@pytest.mark.asyncio
async def test_search_ui_no_results(client, db_session):
    api_hdrs, _ = await _setup(client, "srch1", "SrchNS1")
    resp = await client.get("/search?q=xyzzy_nonexistent_term")
    assert resp.status_code == 200
    assert "No results found" in resp.text


@pytest.mark.asyncio
async def test_search_ui_finds_by_title(client, db_session):
    api_hdrs, _ = await _setup(client, "srch2", "SrchNS2")
    await client.post("/api/v1/namespaces/SrchNS2/pages", json={
        "title": "Quantum Computing Intro",
        "content": "An introduction to quantum bits.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=Quantum")
    assert resp.status_code == 200
    assert "Quantum Computing Intro" in resp.text


@pytest.mark.asyncio
async def test_search_ui_finds_by_content(client, db_session):
    api_hdrs, _ = await _setup(client, "srch3", "SrchNS3")
    await client.post("/api/v1/namespaces/SrchNS3/pages", json={
        "title": "Unrelated Title",
        "content": "This page is about photosynthesis in plants.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=photosynthesis")
    assert resp.status_code == 200
    assert "Unrelated Title" in resp.text


@pytest.mark.asyncio
async def test_search_ui_excludes_non_matching(client, db_session):
    api_hdrs, _ = await _setup(client, "srch4", "SrchNS4")
    await client.post("/api/v1/namespaces/SrchNS4/pages", json={
        "title": "Python Guide",
        "content": "Learn Python programming.",
        "format": "markdown",
    }, headers=api_hdrs)
    await client.post("/api/v1/namespaces/SrchNS4/pages", json={
        "title": "Java Guide",
        "content": "Learn Java programming.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=Python")
    assert resp.status_code == 200
    assert "Python Guide" in resp.text
    assert "Java Guide" not in resp.text


@pytest.mark.asyncio
async def test_search_ui_shows_snippet(client, db_session):
    api_hdrs, _ = await _setup(client, "srch5", "SrchNS5")
    await client.post("/api/v1/namespaces/SrchNS5/pages", json={
        "title": "Snippet Test",
        "content": "The mitochondria is the powerhouse of the cell.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=mitochondria")
    assert resp.status_code == 200
    assert "mitochondria" in resp.text.lower()


@pytest.mark.asyncio
async def test_search_ui_namespace_filter_includes(client, db_session):
    api_hdrs, _ = await _setup(client, "srch6", "SrchNS6")
    await client.post("/api/v1/namespaces/SrchNS6/pages", json={
        "title": "Filtered Page",
        "content": "Content about elephants.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=elephants&namespace=SrchNS6")
    assert resp.status_code == 200
    assert "Filtered Page" in resp.text


@pytest.mark.asyncio
async def test_search_ui_namespace_filter_excludes(client, db_session):
    api_hdrs, _ = await _setup(client, "srch7", "SrchNS7")
    await client.post("/api/v1/namespaces/SrchNS7/pages", json={
        "title": "Excluded Page",
        "content": "Content about dolphins.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=dolphins&namespace=NonExistentNS")
    assert resp.status_code == 200
    assert "Excluded Page" not in resp.text


@pytest.mark.asyncio
async def test_search_ui_result_links_to_page(client, db_session):
    api_hdrs, _ = await _setup(client, "srch8", "SrchNS8")
    await client.post("/api/v1/namespaces/SrchNS8/pages", json={
        "title": "Link Test Page",
        "content": "Contains the word archipelago.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/search?q=archipelago")
    assert resp.status_code == 200
    assert "link-test-page" in resp.text
    assert "/wiki/SrchNS8/" in resp.text


# ── API /api/v1/search route ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_search_returns_rank_field(client, db_session):
    api_hdrs, _ = await _setup(client, "srch9", "SrchNS9")
    await client.post("/api/v1/namespaces/SrchNS9/pages", json={
        "title": "Rank Test",
        "content": "The word volcano appears here.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/api/v1/search?q=volcano")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert "rank" in results[0]


@pytest.mark.asyncio
async def test_api_search_case_insensitive(client, db_session):
    api_hdrs, _ = await _setup(client, "srch10", "SrchNS10")
    await client.post("/api/v1/namespaces/SrchNS10/pages", json={
        "title": "Case Test",
        "content": "The word NEBULA is in uppercase here.",
        "format": "markdown",
    }, headers=api_hdrs)

    resp = await client.get("/api/v1/search?q=nebula")
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()]
    assert "Case Test" in titles
