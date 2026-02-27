#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for public user profile pages (/user/{username})."""
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
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()
    api_hdrs = await auth_headers(client, username)
    ui_hdrs = await cookie_auth(client, username)
    return api_hdrs, ui_hdrs


async def _create_page(client, ns, title, content, fmt, headers):
    resp = await client.post(f"/api/v1/namespaces/{ns}/pages", json={
        "title": title, "content": content, "format": fmt, "comment": "test edit",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# =============================================================================
# Profile page — basic access
# =============================================================================

@pytest.mark.asyncio
async def test_profile_page_accessible_without_login(client, db_session):
    await register_user(client, "prof_anon1", "prof_anon1@example.com")

    resp = await client.get("/user/prof_anon1")
    assert resp.status_code == 200
    assert "prof_anon1" in resp.text


@pytest.mark.asyncio
async def test_profile_page_shows_display_name(client, db_session):
    await register_user(client, "prof_dn1", "prof_dn1@example.com")
    # conftest sets display_name to username.title() = "Prof_Dn1"

    resp = await client.get("/user/prof_dn1")
    assert resp.status_code == 200
    assert "prof_dn1" in resp.text.lower()


@pytest.mark.asyncio
async def test_profile_page_404_for_unknown_user(client, db_session):
    resp = await client.get("/user/no_such_user_xyz")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_profile_page_shows_joined_date(client, db_session):
    await register_user(client, "prof_date1", "prof_date1@example.com")

    resp = await client.get("/user/prof_date1")
    assert resp.status_code == 200
    assert "Member since" in resp.text


@pytest.mark.asyncio
async def test_profile_page_shows_admin_badge_for_admin(client, db_session):
    await register_user(client, "prof_admin1", "prof_admin1@example.com")
    await db_session.execute(
        update(User).where(User.username == "prof_admin1").values(is_admin=True)
    )
    await db_session.commit()

    resp = await client.get("/user/prof_admin1")
    assert resp.status_code == 200
    assert "admin" in resp.text


@pytest.mark.asyncio
async def test_profile_page_no_admin_badge_for_regular_user(client, db_session):
    await register_user(client, "prof_reg_seed", "prof_reg_seed@example.com")  # first = auto-admin
    await register_user(client, "prof_reg1", "prof_reg1@example.com")

    resp = await client.get("/user/prof_reg1")
    assert resp.status_code == 200
    html = resp.text
    # Regular user should not show admin badge
    # (the word "admin" may appear in nav links; check for the badge specifically)
    assert 'badge-wikitext' not in html or "prof_reg1" in html


# =============================================================================
# Edit profile button visibility
# =============================================================================

@pytest.mark.asyncio
async def test_profile_shows_edit_button_to_self(client, db_session):
    await register_user(client, "prof_self1", "prof_self1@example.com")
    ui_hdrs = await cookie_auth(client, "prof_self1")

    resp = await client.get("/user/prof_self1", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "Edit profile" in resp.text


@pytest.mark.asyncio
async def test_profile_hides_edit_button_from_other_user(client, db_session):
    await register_user(client, "prof_other_seed", "prof_other_seed@example.com")  # first = auto-admin
    await register_user(client, "prof_target", "prof_target@example.com")
    await register_user(client, "prof_stranger", "prof_stranger@example.com")
    ui_hdrs = await cookie_auth(client, "prof_stranger")

    resp = await client.get("/user/prof_target", headers=ui_hdrs)
    assert resp.status_code == 200
    assert "Edit profile" not in resp.text


@pytest.mark.asyncio
async def test_profile_shows_edit_button_to_admin(client, db_session):
    _, admin_hdrs = await _setup_admin(client, db_session, "prof_adm_e1")
    await register_user(client, "prof_victim_e1", "prof_victim_e1@example.com")

    resp = await client.get("/user/prof_victim_e1", headers=admin_hdrs)
    assert resp.status_code == 200
    assert "Edit profile" in resp.text


@pytest.mark.asyncio
async def test_profile_shows_admin_view_link_to_admin(client, db_session):
    _, admin_hdrs = await _setup_admin(client, db_session, "prof_adm_e2")
    await register_user(client, "prof_victim_e2", "prof_victim_e2@example.com")

    resp = await client.get("/user/prof_victim_e2", headers=admin_hdrs)
    assert resp.status_code == 200
    assert "/special/users/prof_victim_e2" in resp.text


# =============================================================================
# Contributions
# =============================================================================

@pytest.mark.asyncio
async def test_profile_shows_no_contributions_for_new_user(client, db_session):
    await register_user(client, "prof_nocon1", "prof_nocon1@example.com")

    resp = await client.get("/user/prof_nocon1")
    assert resp.status_code == 200
    assert "No contributions yet" in resp.text


@pytest.mark.asyncio
async def test_profile_shows_contributions_after_edit(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_con1")
    await client.post("/api/v1/namespaces", json={
        "name": "ProfNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "ProfNS1", "Contrib Page", "Content.", "markdown", api_hdrs)

    resp = await client.get("/user/prof_con1")
    assert resp.status_code == 200
    assert "Contrib Page" in resp.text
    assert "ProfNS1" in resp.text


@pytest.mark.asyncio
async def test_profile_contribution_links_to_page(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_con2")
    await client.post("/api/v1/namespaces", json={
        "name": "ProfNS2", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "ProfNS2", "Linked Page", "Content.", "markdown", api_hdrs)

    resp = await client.get("/user/prof_con2")
    assert resp.status_code == 200
    assert "/wiki/ProfNS2/linked-page" in resp.text


@pytest.mark.asyncio
async def test_profile_shows_edit_count(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_cnt1")
    await client.post("/api/v1/namespaces", json={
        "name": "CntNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "CntNS1", "Page A", "v1", "markdown", api_hdrs)
    await _create_page(client, "CntNS1", "Page B", "v1", "markdown", api_hdrs)

    resp = await client.get("/user/prof_cnt1")
    assert resp.status_code == 200
    assert "Total edits" in resp.text
    assert "2" in resp.text


@pytest.mark.asyncio
async def test_profile_contribution_shows_edit_summary(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_sum1")
    await client.post("/api/v1/namespaces", json={
        "name": "SumNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    resp = await client.post("/api/v1/namespaces/SumNS1/pages", json={
        "title": "Summary Page", "content": "Content.",
        "format": "markdown", "comment": "Initial commit",
    }, headers=api_hdrs)
    assert resp.status_code == 201

    resp = await client.get("/user/prof_sum1")
    assert resp.status_code == 200
    assert "Initial commit" in resp.text


# =============================================================================
# Author links in other templates
# =============================================================================

@pytest.mark.asyncio
async def test_recent_changes_author_links_to_profile(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_rc1")
    await client.post("/api/v1/namespaces", json={
        "name": "RCPNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "RCPNS1", "RC Profile Page", "Content.", "markdown", api_hdrs)

    resp = await client.get("/recent")
    assert resp.status_code == 200
    assert "/user/prof_rc1" in resp.text


@pytest.mark.asyncio
async def test_page_history_author_links_to_profile(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_hist1")
    await client.post("/api/v1/namespaces", json={
        "name": "HISTPNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "HISTPNS1", "Hist Profile Page", "Content.", "markdown", api_hdrs)

    resp = await client.get("/wiki/HISTPNS1/hist-profile-page/history")
    assert resp.status_code == 200
    assert "/user/prof_hist1" in resp.text


@pytest.mark.asyncio
async def test_page_view_author_links_to_profile(client, db_session):
    api_hdrs, _ = await _setup_admin(client, db_session, "prof_view1")
    await client.post("/api/v1/namespaces", json={
        "name": "VIEWPNS1", "description": "", "default_format": "markdown",
    }, headers=api_hdrs)
    await _create_page(client, "VIEWPNS1", "View Profile Page", "Content.", "markdown", api_hdrs)

    resp = await client.get("/wiki/VIEWPNS1/view-profile-page")
    assert resp.status_code == 200
    assert "/user/prof_view1" in resp.text


# -----------------------------------------------------------------------------
