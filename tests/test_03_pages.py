#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for page CRUD, history, diff, and rendering."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models import User, Namespace
from tests.conftest import auth_headers, register_user


# -----------------------------------------------------------------------------

async def _setup(client, db_session, username="pageuser", ns_name="Docs", fmt="markdown"):
    """Register a user (admin), create a namespace, return auth headers."""
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()
    headers = await auth_headers(client, username)
    await client.post("/api/v1/namespaces", json={
        "name": ns_name, "description": "", "default_format": fmt
    }, headers=headers)
    return headers


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_markdown_page(client, db_session):
    headers = await _setup(client, db_session, "u1", "NS1")
    resp = await client.post("/api/v1/namespaces/NS1/pages", json={
        "title": "Hello World",
        "content": "# Hello\n\nThis is **bold**.",
        "format": "markdown",
        "comment": "Initial",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Hello World"
    assert data["slug"] == "hello-world"
    assert data["format"] == "markdown"
    assert "<h1>" in data["rendered"]
    assert "<strong>" in data["rendered"]


@pytest.mark.asyncio
async def test_create_rst_page(client, db_session):
    headers = await _setup(client, db_session, "u2", "NS2", fmt="rst")
    resp = await client.post("/api/v1/namespaces/NS2/pages", json={
        "title": "RST Page",
        "content": "RST Page\n========\n\nThis is *emphasis*.\n",
        "format": "rst",
        "comment": "Initial RST",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "rst"
    assert data["rendered"] is not None


@pytest.mark.asyncio
async def test_create_duplicate_page(client, db_session):
    headers = await _setup(client, db_session, "u3", "NS3")
    payload = {"title": "Dup Page", "content": "x", "format": "markdown"}
    await client.post("/api/v1/namespaces/NS3/pages", json=payload, headers=headers)
    resp = await client.post("/api/v1/namespaces/NS3/pages", json=payload, headers=headers)
    assert resp.status_code == 409


# ── Read ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_page(client, db_session):
    headers = await _setup(client, db_session, "u4", "NS4")
    await client.post("/api/v1/namespaces/NS4/pages", json={
        "title": "Get Me", "content": "content", "format": "markdown"
    }, headers=headers)
    resp = await client.get("/api/v1/namespaces/NS4/pages/get-me")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get Me"


@pytest.mark.asyncio
async def test_get_page_raw(client, db_session):
    headers = await _setup(client, db_session, "u5", "NS5")
    await client.post("/api/v1/namespaces/NS5/pages", json={
        "title": "Raw Test", "content": "raw **content**", "format": "markdown"
    }, headers=headers)
    resp = await client.get("/api/v1/namespaces/NS5/pages/raw-test/raw")
    assert resp.status_code == 200
    assert "raw **content**" in resp.text


@pytest.mark.asyncio
async def test_get_missing_page(client, db_session):
    await _setup(client, db_session, "u6", "NS6")
    resp = await client.get("/api/v1/namespaces/NS6/pages/does-not-exist")
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_page(client, db_session):
    headers = await _setup(client, db_session, "u7", "NS7")
    await client.post("/api/v1/namespaces/NS7/pages", json={
        "title": "Editable", "content": "v1", "format": "markdown"
    }, headers=headers)
    resp = await client.put("/api/v1/namespaces/NS7/pages/editable", json={
        "content": "v2 updated", "comment": "Second edit"
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["version"] == 2
    assert resp.json()["content"] == "v2 updated"


@pytest.mark.asyncio
async def test_update_page_changes_format(client, db_session):
    headers = await _setup(client, db_session, "u8", "NS8")
    await client.post("/api/v1/namespaces/NS8/pages", json={
        "title": "Fmt Change", "content": "# md", "format": "markdown"
    }, headers=headers)
    resp = await client.put("/api/v1/namespaces/NS8/pages/fmt-change", json={
        "content": "Fmt Change\n==========\n\nNow RST.", "format": "rst"
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["format"] == "rst"


# ── History ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history(client, db_session):
    headers = await _setup(client, db_session, "u9", "NS9")
    await client.post("/api/v1/namespaces/NS9/pages", json={
        "title": "Hist Page", "content": "v1", "format": "markdown"
    }, headers=headers)
    await client.put("/api/v1/namespaces/NS9/pages/hist-page", json={
        "content": "v2"
    }, headers=headers)
    await client.put("/api/v1/namespaces/NS9/pages/hist-page", json={
        "content": "v3"
    }, headers=headers)

    resp = await client.get("/api/v1/namespaces/NS9/pages/hist-page/history")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 3
    # Returned in descending order
    assert versions[0]["version"] == 3


# ── Diff ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diff(client, db_session):
    headers = await _setup(client, db_session, "u10", "NS10")
    await client.post("/api/v1/namespaces/NS10/pages", json={
        "title": "Diff Page", "content": "line one\nline two\n", "format": "markdown"
    }, headers=headers)
    await client.put("/api/v1/namespaces/NS10/pages/diff-page", json={
        "content": "line one\nline two modified\nline three\n"
    }, headers=headers)

    resp = await client.get("/api/v1/namespaces/NS10/pages/diff-page/diff/1/2")
    assert resp.status_code == 200
    diff = resp.json()["diff"]
    types = [chunk["type"] for chunk in diff]
    assert "delete" in types or "insert" in types


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_page(client, db_session):
    headers = await _setup(client, db_session, "u11", "NS11")
    await client.post("/api/v1/namespaces/NS11/pages", json={
        "title": "To Delete", "content": "bye", "format": "markdown"
    }, headers=headers)
    resp = await client.delete("/api/v1/namespaces/NS11/pages/to-delete", headers=headers)
    assert resp.status_code == 200
    resp2 = await client.get("/api/v1/namespaces/NS11/pages/to-delete")
    assert resp2.status_code == 404


# ── List & search ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_pages(client, db_session):
    headers = await _setup(client, db_session, "u12", "NS12")
    for i in range(3):
        await client.post("/api/v1/namespaces/NS12/pages", json={
            "title": f"Page {i}", "content": f"content {i}", "format": "markdown"
        }, headers=headers)
    resp = await client.get("/api/v1/namespaces/NS12/pages")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_search_pages(client, db_session):
    headers = await _setup(client, db_session, "u13", "NS13")
    await client.post("/api/v1/namespaces/NS13/pages", json={
        "title": "Python Tutorial",
        "content": "Learn Python programming",
        "format": "markdown"
    }, headers=headers)
    await client.post("/api/v1/namespaces/NS13/pages", json={
        "title": "Java Guide",
        "content": "Learn Java programming",
        "format": "markdown"
    }, headers=headers)

    resp = await client.get("/api/v1/search?q=Python")
    assert resp.status_code == 200
    results = resp.json()
    titles = [r["title"] for r in results]
    assert "Python Tutorial" in titles
    assert "Java Guide" not in titles


# ── Render preview ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_render_markdown(client):
    resp = await client.get("/api/v1/render", params={
        "content": "# Hello\n\nWorld **bold**.",
        "format": "markdown",
        "namespace": "Main",
    })
    assert resp.status_code == 200
    html = resp.json()["html"]
    assert "<h1>" in html
    assert "<strong>" in html


@pytest.mark.asyncio
async def test_render_rst(client):
    resp = await client.get("/api/v1/render", params={
        "content": "Hello\n=====\n\nRST *emphasis*.\n",
        "format": "rst",
        "namespace": "Main",
    })
    assert resp.status_code == 200
    assert resp.json()["html"] is not None


# -----------------------------------------------------------------------------
