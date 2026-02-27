#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for page move / rename."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models import User
from tests.conftest import auth_headers, cookie_auth, register_user


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
# Page move / rename UI tests
# =============================================================================

@pytest.mark.asyncio
async def test_move_page_form_loads(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser1", "MVNS1")
    await _create_page(client, "MVNS1", "Health SHorts", "Content.", "wikitext", api_headers)
    ui_headers = await cookie_auth(client, "mvuser1")

    resp = await client.get("/wiki/MVNS1/health-shorts", headers=ui_headers)
    assert resp.status_code == 200
    assert "/wiki/MVNS1/health-shorts/move" in resp.text

    resp = await client.get("/wiki/MVNS1/health-shorts/move", headers=ui_headers)
    assert resp.status_code == 200
    assert "Health SHorts" in resp.text
    assert "New title" in resp.text


@pytest.mark.asyncio
async def test_move_page_redirects_unauthenticated(client, db_session):
    headers = await _setup(client, db_session, "mvuser2", "MVNS2")
    await _create_page(client, "MVNS2", "To Move", "Content.", "markdown", headers)

    resp = await client.get("/wiki/MVNS2/to-move/move", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_move_page_renames_and_redirects(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser3", "MVNS3")
    await _create_page(client, "MVNS3", "Health SHorts", "Content.", "wikitext", api_headers)
    ui_headers = await cookie_auth(client, "mvuser3")

    resp = await client.post(
        "/wiki/MVNS3/health-shorts/move",
        data={"new_title": "Health Shorts Exercise"},
        headers=ui_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/wiki/MVNS3/health-shorts-exercise" in resp.headers["location"]

    assert (await client.get("/wiki/MVNS3/health-shorts-exercise")).status_code == 200


@pytest.mark.asyncio
async def test_move_page_preserves_history(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser4", "MVNS4")
    await _create_page(client, "MVNS4", "Original Title", "v1 content.", "markdown", api_headers)
    ui_headers = await cookie_auth(client, "mvuser4")

    await client.post(
        "/wiki/MVNS4/original-title/move",
        data={"new_title": "Renamed Title"},
        headers=ui_headers,
    )

    hist = await client.get("/wiki/MVNS4/renamed-title/history")
    assert hist.status_code == 200
    assert "Renamed Title" in hist.text


@pytest.mark.asyncio
async def test_move_page_same_slug_title_fix(client, db_session):
    """Renaming 'Health SHorts' -> 'Health Shorts' keeps the same slug — must succeed."""
    api_headers = await _setup(client, db_session, "mvuser6", "MVNS6")
    await _create_page(client, "MVNS6", "Health SHorts", "Content.", "wikitext", api_headers)
    ui_headers = await cookie_auth(client, "mvuser6")

    resp = await client.post(
        "/wiki/MVNS6/health-shorts/move",
        data={"new_title": "Health Shorts"},
        headers=ui_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "/wiki/MVNS6/health-shorts" in resp.headers["location"]

    page_resp = await client.get("/wiki/MVNS6/health-shorts")
    assert page_resp.status_code == 200
    assert "<h1>Health Shorts</h1>" in page_resp.text


@pytest.mark.asyncio
async def test_move_page_reason_in_history(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser7", "MVNS7")
    await _create_page(client, "MVNS7", "Old Title", "Content.", "markdown", api_headers)
    ui_headers = await cookie_auth(client, "mvuser7")

    await client.post(
        "/wiki/MVNS7/old-title/move",
        data={"new_title": "New Title", "reason": "Fixing typo"},
        headers=ui_headers,
    )

    hist = await client.get("/wiki/MVNS7/new-title/history")
    assert hist.status_code == 200
    assert "Fixing typo" in hist.text


@pytest.mark.asyncio
async def test_move_page_redirect_stub_created(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser8", "MVNS8")
    await _create_page(client, "MVNS8", "Source Page", "Content.", "markdown", api_headers)
    ui_headers = await cookie_auth(client, "mvuser8")

    await client.post(
        "/wiki/MVNS8/source-page/move",
        data={"new_title": "Destination Page", "leave_redirect": "1"},
        headers=ui_headers,
    )

    # Old slug redirects to new page
    old = await client.get("/wiki/MVNS8/source-page", follow_redirects=True)
    assert old.status_code == 200
    assert "Destination Page" in old.text

    # Stub is viewable directly with ?redirect=no
    stub = await client.get("/wiki/MVNS8/source-page?redirect=no", follow_redirects=False)
    assert stub.status_code == 200

    # New page also exists
    new = await client.get("/wiki/MVNS8/destination-page")
    assert new.status_code == 200
    assert "Destination Page" in new.text


@pytest.mark.asyncio
async def test_move_page_no_redirect_stub_when_unchecked(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser9", "MVNS9")
    await _create_page(client, "MVNS9", "Alpha Page", "Content.", "markdown", api_headers)
    ui_headers = await cookie_auth(client, "mvuser9")

    await client.post(
        "/wiki/MVNS9/alpha-page/move",
        data={"new_title": "Beta Page"},  # no leave_redirect
        headers=ui_headers,
    )

    old = await client.get("/wiki/MVNS9/alpha-page")
    assert old.status_code == 404


@pytest.mark.asyncio
async def test_move_page_duplicate_title_shows_error(client, db_session):
    api_headers = await _setup(client, db_session, "mvuser5", "MVNS5")
    await _create_page(client, "MVNS5", "Page One", "Content.", "markdown", api_headers)
    await _create_page(client, "MVNS5", "Page Two", "Content.", "markdown", api_headers)
    ui_headers = await cookie_auth(client, "mvuser5")

    resp = await client.post(
        "/wiki/MVNS5/page-one/move",
        data={"new_title": "Page Two"},
        headers=ui_headers,
    )
    assert resp.status_code == 400
    assert "Page One" in resp.text


# -----------------------------------------------------------------------------
