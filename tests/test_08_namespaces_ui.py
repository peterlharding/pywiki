#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for namespace management UI (/special/namespaces/...)."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.models import User
from tests.conftest import auth_headers, cookie_auth, register_user


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _setup_admin(client, db_session, username):
    """Register a user, promote to admin, return both API and UI headers."""
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()
    api_hdrs = await auth_headers(client, username)
    ui_hdrs = await cookie_auth(client, username)
    return api_hdrs, ui_hdrs


async def _create_namespace(client, name, fmt, api_headers):
    resp = await client.post("/api/v1/namespaces", json={
        "name": name, "description": f"{name} description", "default_format": fmt,
    }, headers=api_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# =============================================================================
# Namespace list
# =============================================================================

@pytest.mark.asyncio
async def test_ns_list_accessible_to_all(client, db_session):
    """Non-admin users can view the namespace list."""
    await register_user(client, "nsl_plain", "nsl_plain@example.com")
    ui_headers = await cookie_auth(client, "nsl_plain")

    resp = await client.get("/special/namespaces", headers=ui_headers)
    assert resp.status_code == 200
    assert "Namespaces" in resp.text


@pytest.mark.asyncio
async def test_ns_list_shows_namespaces(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nsl_admin1")
    await _create_namespace(client, "ListNS1", "markdown", api_hdrs)
    await _create_namespace(client, "ListNS2", "wikitext", api_hdrs)

    resp = await client.get("/special/namespaces", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "ListNS1" in resp.text
    assert "ListNS2" in resp.text


@pytest.mark.asyncio
async def test_ns_list_shows_format_badge(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nsl_admin2")
    await _create_namespace(client, "BadgeNS", "rst", api_hdrs)

    resp = await client.get("/special/namespaces", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "rst" in resp.text


@pytest.mark.asyncio
async def test_ns_list_shows_create_button_for_admin(client, db_session):
    _, ui_hdrs = await _setup_admin(client, db_session, "nsl_admin3")

    resp = await client.get("/special/namespaces", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "/special/namespaces/create" in resp.text


@pytest.mark.asyncio
async def test_ns_list_no_create_button_for_non_admin(client, db_session):
    await register_user(client, "nsl_seed", "nsl_seed@example.com")  # first = auto-admin
    await register_user(client, "nsl_nonadmin", "nsl_nonadmin@example.com")
    ui_hdrs = await cookie_auth(client, "nsl_nonadmin")

    resp = await client.get("/special/namespaces", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "/special/namespaces/create" not in resp.text


# =============================================================================
# Namespace create
# =============================================================================

@pytest.mark.asyncio
async def test_ns_create_form_requires_admin(client, db_session):
    await register_user(client, "nsc_seed", "nsc_seed@example.com")  # first = auto-admin
    await register_user(client, "nsc_plain", "nsc_plain@example.com")
    ui_hdrs = await cookie_auth(client, "nsc_plain")

    resp = await client.get("/special/namespaces/create", headers=ui_hdrs)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ns_create_form_loads_for_admin(client, db_session):
    _, ui_hdrs = await _setup_admin(client, db_session, "nsc_admin1")

    resp = await client.get("/special/namespaces/create", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "Create Namespace" in resp.text


@pytest.mark.asyncio
async def test_ns_create_creates_namespace(client, db_session):
    _, ui_hdrs = await _setup_admin(client, db_session, "nsc_admin2")

    resp = await client.post(
        "/special/namespaces/create",
        data={"name": "CreatedNS", "description": "A new one", "default_format": "markdown"},
        headers=ui_hdrs,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "CreatedNS" in resp.text


@pytest.mark.asyncio
async def test_ns_create_duplicate_shows_error(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nsc_admin3")
    await _create_namespace(client, "DupNS", "markdown", api_hdrs)

    resp = await client.post(
        "/special/namespaces/create",
        data={"name": "DupNS", "description": "", "default_format": "markdown"},
        headers=ui_hdrs,
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "DupNS" in resp.text


@pytest.mark.asyncio
async def test_ns_create_invalid_name_shows_error(client, db_session):
    _, ui_hdrs = await _setup_admin(client, db_session, "nsc_admin4")

    resp = await client.post(
        "/special/namespaces/create",
        data={"name": "has spaces!", "description": "", "default_format": "markdown"},
        headers=ui_hdrs,
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "Create Namespace" in resp.text


# =============================================================================
# Namespace edit
# =============================================================================

@pytest.mark.asyncio
async def test_ns_edit_form_requires_admin(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "nse_setup1")
    await _create_namespace(client, "EditNS1", "markdown", api_hdrs)

    # nse_setup1 already consumed the first-user slot so nse_plain is non-admin
    await register_user(client, "nse_plain", "nse_plain@example.com")
    ui_hdrs = await cookie_auth(client, "nse_plain")

    resp = await client.get("/special/namespaces/EditNS1/edit", headers=ui_hdrs)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ns_edit_form_loads(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nse_admin1")
    await _create_namespace(client, "EditNS2", "markdown", api_hdrs)

    resp = await client.get("/special/namespaces/EditNS2/edit", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "EditNS2" in resp.text


@pytest.mark.asyncio
async def test_ns_edit_updates_description(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nse_admin2")
    await _create_namespace(client, "EditNS3", "markdown", api_hdrs)

    resp = await client.post(
        "/special/namespaces/EditNS3/edit",
        data={"description": "Updated description", "default_format": "markdown"},
        headers=ui_hdrs,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "EditNS3" in resp.text


@pytest.mark.asyncio
async def test_ns_edit_updates_format(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nse_admin3")
    await _create_namespace(client, "FmtNS", "markdown", api_hdrs)

    resp = await client.post(
        "/special/namespaces/FmtNS/edit",
        data={"description": "", "default_format": "wikitext"},
        headers=ui_hdrs,
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Verify format changed on list page
    list_resp = await client.get("/special/namespaces", headers=ui_hdrs)
    assert "wikitext" in list_resp.text


# =============================================================================
# Namespace delete
# =============================================================================

@pytest.mark.asyncio
async def test_ns_delete_requires_admin(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "nsd_setup1")
    await _create_namespace(client, "DelNS1", "markdown", api_hdrs)

    # nsd_setup1 already consumed the first-user slot so nsd_plain is non-admin
    await register_user(client, "nsd_plain", "nsd_plain@example.com")
    ui_hdrs = await cookie_auth(client, "nsd_plain")

    resp = await client.post("/special/namespaces/DelNS1/delete", headers=ui_hdrs)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ns_delete_removes_namespace(client, db_session):
    api_hdrs, ui_hdrs = await _setup_admin(client, db_session, "nsd_admin1")
    await _create_namespace(client, "DelNS2", "markdown", api_hdrs)

    resp = await client.post(
        "/special/namespaces/DelNS2/delete",
        headers=ui_hdrs,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "DelNS2" not in resp.text


@pytest.mark.asyncio
async def test_ns_delete_nonexistent_returns_404(client, db_session):
    _, ui_hdrs = await _setup_admin(client, db_session, "nsd_admin2")

    resp = await client.post(
        "/special/namespaces/NoSuchNS/delete",
        headers=ui_hdrs,
    )
    assert resp.status_code == 404


# -----------------------------------------------------------------------------
