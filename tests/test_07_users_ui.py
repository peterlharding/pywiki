#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for user management UI (/special/users/...)."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.models import User
from tests.conftest import auth_headers, cookie_auth, register_user


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _make_admin(db_session, username):
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()


async def _setup_admin(client, db_session, username):
    """Register a user and promote to admin."""
    await register_user(client, username, f"{username}@example.com")
    await _make_admin(db_session, username)
    return await cookie_auth(client, username)


# =============================================================================
# User list
# =============================================================================

@pytest.mark.asyncio
async def test_user_list_requires_admin(client, db_session):
    """Non-admin users cannot access /special/users."""
    await register_user(client, "ul_seed", "ul_seed@example.com")  # first = auto-admin
    await register_user(client, "ul_plain", "ul_plain@example.com")
    ui_headers = await cookie_auth(client, "ul_plain")

    resp = await client.get("/special/users", headers=ui_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_list_unauthenticated(client, db_session):
    resp = await client.get("/special/users", follow_redirects=False)
    # 403 since no user cookie — HTTPException
    assert resp.status_code in (302, 403)


@pytest.mark.asyncio
async def test_user_list_shows_users(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "ul_admin1")
    await register_user(client, "ul_other", "ul_other@example.com")

    resp = await client.get("/special/users", headers=ui_headers)
    assert resp.status_code == 200
    assert "ul_admin1" in resp.text
    assert "ul_other" in resp.text


@pytest.mark.asyncio
async def test_user_list_shows_admin_badge(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "ul_admin2")

    resp = await client.get("/special/users", headers=ui_headers)
    assert resp.status_code == 200
    assert "admin" in resp.text


@pytest.mark.asyncio
async def test_user_list_has_create_button_for_admin(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "ul_admin3")

    resp = await client.get("/special/users", headers=ui_headers)
    assert resp.status_code == 200
    assert "/special/users/create" in resp.text


# =============================================================================
# User view
# =============================================================================

@pytest.mark.asyncio
async def test_user_view_accessible_to_all(client, db_session):
    """Any visitor can view a user profile page."""
    await register_user(client, "uv_user1", "uv_user1@example.com")

    resp = await client.get("/special/users/uv_user1")
    assert resp.status_code == 200
    assert "uv_user1" in resp.text


@pytest.mark.asyncio
async def test_user_view_hides_email_from_non_admin(client, db_session):
    await register_user(client, "uv_user2", "secret@example.com")

    resp = await client.get("/special/users/uv_user2")
    assert resp.status_code == 200
    assert "secret@example.com" not in resp.text


@pytest.mark.asyncio
async def test_user_view_shows_email_to_admin(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "uv_admin1")
    await register_user(client, "uv_user3", "visible@example.com")

    resp = await client.get("/special/users/uv_user3", headers=ui_headers)
    assert resp.status_code == 200
    assert "visible@example.com" in resp.text


@pytest.mark.asyncio
async def test_user_view_404_for_unknown(client, db_session):
    resp = await client.get("/special/users/does_not_exist")
    assert resp.status_code == 404


# =============================================================================
# User edit
# =============================================================================

@pytest.mark.asyncio
async def test_user_edit_form_accessible_to_self(client, db_session):
    await register_user(client, "ue_self1", "ue_self1@example.com")
    ui_headers = await cookie_auth(client, "ue_self1")

    resp = await client.get("/special/users/ue_self1/edit", headers=ui_headers)
    assert resp.status_code == 200
    assert "ue_self1" in resp.text


@pytest.mark.asyncio
async def test_user_edit_form_blocked_for_other_non_admin(client, db_session):
    await register_user(client, "ue_target", "ue_target@example.com")
    await register_user(client, "ue_intruder", "ue_intruder@example.com")
    ui_headers = await cookie_auth(client, "ue_intruder")

    resp = await client.get("/special/users/ue_target/edit", headers=ui_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_edit_updates_display_name(client, db_session):
    await register_user(client, "ue_dn1", "ue_dn1@example.com")
    ui_headers = await cookie_auth(client, "ue_dn1")

    resp = await client.post(
        "/special/users/ue_dn1/edit",
        data={"display_name": "New Display Name", "email": "ue_dn1@example.com",
              "new_password": "", "is_active": "1"},
        headers=ui_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "New Display Name" in resp.text


@pytest.mark.asyncio
async def test_admin_can_edit_other_user(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "ue_admin1")
    await register_user(client, "ue_victim", "ue_victim@example.com")

    resp = await client.get("/special/users/ue_victim/edit", headers=ui_headers)
    assert resp.status_code == 200
    assert "ue_victim" in resp.text


@pytest.mark.asyncio
async def test_admin_can_toggle_admin_flag(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "ue_admin2")
    await register_user(client, "ue_promote", "ue_promote@example.com")

    resp = await client.post(
        "/special/users/ue_promote/edit",
        data={"display_name": "ue_promote", "email": "ue_promote@example.com",
              "new_password": "", "is_admin": "1", "is_active": "1"},
        headers=ui_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200

    # Promoted user can now access admin-only page
    promoted_headers = await cookie_auth(client, "ue_promote")
    list_resp = await client.get("/special/users", headers=promoted_headers)
    assert list_resp.status_code == 200


# =============================================================================
# User create (admin only)
# =============================================================================

@pytest.mark.asyncio
async def test_user_create_form_requires_admin(client, db_session):
    await register_user(client, "uc_seed", "uc_seed@example.com")  # first = auto-admin
    await register_user(client, "uc_plain", "uc_plain@example.com")
    ui_headers = await cookie_auth(client, "uc_plain")

    resp = await client.get("/special/users/create", headers=ui_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_user_create_form_loads_for_admin(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "uc_admin1")

    resp = await client.get("/special/users/create", headers=ui_headers)
    assert resp.status_code == 200
    assert "Create User" in resp.text


@pytest.mark.asyncio
async def test_user_create_creates_user(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "uc_admin2")

    resp = await client.post(
        "/special/users/create",
        data={
            "username": "uc_newbie",
            "display_name": "New Bie",
            "email": "uc_newbie@example.com",
            "password": "password123",
        },
        headers=ui_headers,
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "uc_newbie" in resp.text


@pytest.mark.asyncio
async def test_user_create_with_admin_flag(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "uc_admin3")

    await client.post(
        "/special/users/create",
        data={
            "username": "uc_newadmin",
            "email": "uc_newadmin@example.com",
            "password": "password123",
            "is_admin": "1",
        },
        headers=ui_headers,
        follow_redirects=True,
    )

    # New admin can access user list (created with password "password123")
    new_admin_headers = await cookie_auth(client, "uc_newadmin", password="password123")
    resp = await client.get("/special/users", headers=new_admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_user_create_duplicate_username_shows_error(client, db_session):
    ui_headers = await _setup_admin(client, db_session, "uc_admin4")
    await register_user(client, "uc_existing", "uc_existing@example.com")

    resp = await client.post(
        "/special/users/create",
        data={
            "username": "uc_existing",
            "email": "other@example.com",
            "password": "password123",
        },
        headers=ui_headers,
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "already taken" in resp.text


# -----------------------------------------------------------------------------
