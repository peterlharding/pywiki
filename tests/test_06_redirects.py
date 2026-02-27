#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for #REDIRECT page handling."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.models import User
from tests.conftest import auth_headers, cookie_auth, register_user


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _setup(client, db_session, username, ns_name, fmt="wikitext"):
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
# #REDIRECT handling
# =============================================================================

@pytest.mark.asyncio
async def test_redirect_page_issues_302(client, db_session):
    """A page whose content starts with #REDIRECT should issue a 302."""
    api_headers = await _setup(client, db_session, "rduser1", "RDNS1")
    await _create_page(client, "RDNS1", "Target Page", "Destination content.", "wikitext", api_headers)
    await _create_page(
        client, "RDNS1", "Old Name",
        "#REDIRECT [[Target Page]]",
        "wikitext", api_headers,
    )

    resp = await client.get("/wiki/RDNS1/old-name", follow_redirects=False)
    assert resp.status_code == 302
    assert "target-page" in resp.headers["location"]


@pytest.mark.asyncio
async def test_redirect_page_redirected_from_notice(client, db_session):
    """After following a redirect the target page shows a 'Redirected from' notice."""
    api_headers = await _setup(client, db_session, "rduser2", "RDNS2")
    await _create_page(client, "RDNS2", "Destination", "Content here.", "wikitext", api_headers)
    await _create_page(
        client, "RDNS2", "Old Slug",
        "#REDIRECT [[Destination]]",
        "wikitext", api_headers,
    )

    resp = await client.get("/wiki/RDNS2/old-slug", follow_redirects=True)
    assert resp.status_code == 200
    assert "Redirected from" in resp.text
    assert "old-slug" in resp.text


@pytest.mark.asyncio
async def test_redirect_bypass_with_redirect_no(client, db_session):
    """?redirect=no lets you view the stub page directly without following the redirect."""
    api_headers = await _setup(client, db_session, "rduser3", "RDNS3")
    await _create_page(client, "RDNS3", "Real Page", "Content.", "wikitext", api_headers)
    await _create_page(
        client, "RDNS3", "Stub Page",
        "#REDIRECT [[Real Page]]",
        "wikitext", api_headers,
    )

    resp = await client.get("/wiki/RDNS3/stub-page?redirect=no", follow_redirects=False)
    assert resp.status_code == 200
    assert "Stub Page" in resp.text


@pytest.mark.asyncio
async def test_move_with_redirect_stub_auto_redirects(client, db_session):
    """After a move with leave_redirect, visiting the old slug redirects to the new one."""
    api_headers = await _setup(client, db_session, "rduser4", "RDNS4")
    await _create_page(client, "RDNS4", "Moving Page", "Content.", "wikitext", api_headers)
    ui_headers = await cookie_auth(client, "rduser4")

    await client.post(
        "/wiki/RDNS4/moving-page/move",
        data={"new_title": "Moved Page", "leave_redirect": "1"},
        headers=ui_headers,
    )

    resp = await client.get("/wiki/RDNS4/moving-page", follow_redirects=False)
    assert resp.status_code == 302
    assert "moved-page" in resp.headers["location"]


@pytest.mark.asyncio
async def test_redirect_case_insensitive_keyword(client, db_session):
    """#redirect (lowercase) should also be detected."""
    api_headers = await _setup(client, db_session, "rduser5", "RDNS5")
    await _create_page(client, "RDNS5", "Target", "Content.", "wikitext", api_headers)
    await _create_page(
        client, "RDNS5", "Lower Redirect",
        "#redirect [[Target]]",
        "wikitext", api_headers,
    )

    resp = await client.get("/wiki/RDNS5/lower-redirect", follow_redirects=False)
    assert resp.status_code == 302
    assert "target" in resp.headers["location"]


@pytest.mark.asyncio
async def test_redirect_not_triggered_when_viewing_version(client, db_session):
    """Viewing a specific ?version=N of a redirect stub should not redirect."""
    api_headers = await _setup(client, db_session, "rduser6", "RDNS6")
    await _create_page(client, "RDNS6", "Dest Page", "Content.", "wikitext", api_headers)
    await _create_page(
        client, "RDNS6", "Version Stub",
        "#REDIRECT [[Dest Page]]",
        "wikitext", api_headers,
    )

    resp = await client.get("/wiki/RDNS6/version-stub?version=1", follow_redirects=False)
    assert resp.status_code == 200


# -----------------------------------------------------------------------------
