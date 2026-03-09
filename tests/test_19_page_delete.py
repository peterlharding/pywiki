#!/usr/bin/env python
# -----------------------------------------------------------------------------
"""
Tests for the page delete UI route:
  POST /wiki/{namespace}/{slug}/delete
"""
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

async def _setup(client: AsyncClient, db_session, username: str, ns: str) -> dict:
    """Register first user (auto-admin), create namespace, return API headers."""
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(update(User).where(User.username == username).values(is_admin=True))
    await db_session.commit()
    api_hdrs = await auth_headers(client, username)
    await client.post(
        "/api/v1/namespaces",
        json={"name": ns, "description": "", "default_format": "markdown"},
        headers=api_hdrs,
    )
    return api_hdrs


async def _create_page(client: AsyncClient, ns: str, title: str, content: str,
                       headers: dict) -> dict:
    resp = await client.post(
        f"/api/v1/namespaces/{ns}/pages",
        json={"title": title, "content": content, "format": "markdown"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# =============================================================================
# Tests
# =============================================================================

@pytest.mark.asyncio
async def test_delete_page_redirects_to_namespace(client, db_session):
    """POST /wiki/{ns}/{slug}/delete removes the page and redirects to namespace index."""
    headers = await _setup(client, db_session, "deluser1", "DELNS1")
    cookies = await cookie_auth(client, "deluser1")
    await _create_page(client, "DELNS1", "To Delete", "bye", headers)

    resp = await client.post(
        "/wiki/DELNS1/to-delete/delete",
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert resp.headers["location"] == "/wiki/DELNS1"


@pytest.mark.asyncio
async def test_delete_page_page_gone(client, db_session):
    """After deletion the page returns 404."""
    headers = await _setup(client, db_session, "deluser2", "DELNS2")
    cookies = await cookie_auth(client, "deluser2")
    await _create_page(client, "DELNS2", "Vanish", "gone", headers)

    await client.post("/wiki/DELNS2/vanish/delete", headers=cookies)

    resp = await client.get("/wiki/DELNS2/vanish", headers=cookies)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_page_requires_login(client, db_session):
    """Unauthenticated DELETE attempt redirects to login."""
    headers = await _setup(client, db_session, "deluser3", "DELNS3")
    await _create_page(client, "DELNS3", "Protected", "content", headers)

    resp = await client.post(
        "/wiki/DELNS3/protected/delete",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_delete_page_not_found_returns_error(client, db_session):
    """Deleting a non-existent slug returns 404."""
    headers = await _setup(client, db_session, "deluser4", "DELNS4")
    cookies = await cookie_auth(client, "deluser4")

    resp = await client.post(
        "/wiki/DELNS4/no-such-page/delete",
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_page_other_pages_unaffected(client, db_session):
    """Deleting one page does not remove sibling pages in the same namespace."""
    headers = await _setup(client, db_session, "deluser5", "DELNS5")
    cookies = await cookie_auth(client, "deluser5")
    await _create_page(client, "DELNS5", "Keep Me",   "keep",   headers)
    await _create_page(client, "DELNS5", "Delete Me", "delete", headers)

    await client.post("/wiki/DELNS5/delete-me/delete", headers=cookies)

    keep_resp = await client.get("/wiki/DELNS5/keep-me", headers=cookies)
    assert keep_resp.status_code == 200
