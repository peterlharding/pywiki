#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Tests for email verification and password reset flows.

Email sending is patched out via unittest.mock so no SMTP server is needed.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import register_user
from app.core.config import get_settings


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _register_ui(client, username="uiuser", email="ui@example.com",
                       password="pass1234!"):
    return await client.post("/register", data={
        "username": username,
        "email": email,
        "password": password,
        "display_name": username.title(),
    }, follow_redirects=False)


# -----------------------------------------------------------------------------
# Email service unit tests
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_no_smtp_prints_stdout(capsys):
    """When SMTP is not configured, email is printed to stdout (no crash)."""
    from app.services.email import send_email
    await send_email("user@example.com", "Test subject", "Test body")
    captured = capsys.readouterr()
    assert "Test subject" in captured.out
    assert "user@example.com" in captured.out


@pytest.mark.asyncio
async def test_send_verification_email_no_smtp(capsys):
    from app.services.email import send_verification_email
    await send_verification_email("u@example.com", "alice", "tok123")
    captured = capsys.readouterr()
    assert "tok123" in captured.out
    assert "alice" in captured.out


@pytest.mark.asyncio
async def test_send_reset_email_no_smtp(capsys):
    from app.services.email import send_password_reset_email
    await send_password_reset_email("u@example.com", "bob", "resettok")
    captured = capsys.readouterr()
    assert "resettok" in captured.out
    assert "bob" in captured.out


# -----------------------------------------------------------------------------
# User service token helpers
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_and_verify_email_token(db_session):
    from app.services.users import create_user, set_verification_token, verify_email_token
    from app.schemas import UserCreate

    user = await create_user(db_session, UserCreate(
        username="verifytest", email="verify@example.com",
        password="pass1234!", display_name="Verify Test",
    ))
    await db_session.flush()

    assert not user.email_verified
    token = await set_verification_token(db_session, user)
    assert token
    assert user.verification_token == token

    verified = await verify_email_token(db_session, token)
    assert verified.email_verified
    assert verified.verification_token is None


@pytest.mark.asyncio
async def test_verify_email_bad_token(db_session):
    from fastapi import HTTPException
    from app.services.users import verify_email_token

    with pytest.raises(HTTPException) as exc_info:
        await verify_email_token(db_session, "bad-token-xyz")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_set_and_consume_reset_token(db_session):
    from app.services.users import create_user, set_reset_token, consume_reset_token
    from app.schemas import UserCreate

    user = await create_user(db_session, UserCreate(
        username="resettest", email="reset@example.com",
        password="oldpass1234!", display_name="Reset Test",
    ))
    await db_session.flush()
    old_hash = user.password_hash

    _, token = await set_reset_token(db_session, "reset@example.com")
    assert token
    assert user.reset_token == token
    assert user.reset_token_expires is not None

    updated = await consume_reset_token(db_session, token, "newpass5678!")
    assert updated.password_hash != old_hash
    assert updated.reset_token is None
    assert updated.reset_token_expires is None


@pytest.mark.asyncio
async def test_reset_token_wrong_email(db_session):
    from fastapi import HTTPException
    from app.services.users import set_reset_token

    with pytest.raises(HTTPException) as exc_info:
        await set_reset_token(db_session, "nobody@example.com")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_consume_expired_reset_token(db_session):
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    from app.services.users import create_user, set_reset_token, consume_reset_token
    from app.schemas import UserCreate

    user = await create_user(db_session, UserCreate(
        username="expiredtest", email="expired@example.com",
        password="pass1234!", display_name="Expired",
    ))
    await db_session.flush()
    _, token = await set_reset_token(db_session, "expired@example.com")

    # Force the expiry into the past
    user.reset_token_expires = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await consume_reset_token(db_session, token, "newpass5678!")
    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail.lower()


# -----------------------------------------------------------------------------
# UI routes — email verification disabled (default)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_no_verification_redirects_home(client):
    """Default: no email verification required — register goes straight to home."""
    resp = await _register_ui(client)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_forgot_password_form_renders(client):
    resp = await client.get("/forgot-password")
    assert resp.status_code == 200
    assert b"Forgot Password" in resp.content


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_no_error_shown(client):
    """Always returns the 'sent' success view to avoid email enumeration."""
    resp = await client.post("/forgot-password",
                             data={"email": "nobody@example.com"},
                             follow_redirects=False)
    assert resp.status_code == 200
    assert b"password reset link" in resp.content.lower()


@pytest.mark.asyncio
async def test_reset_password_form_renders(client):
    resp = await client.get("/reset-password?token=sometoken")
    assert resp.status_code == 200
    assert b"Reset Password" in resp.content


@pytest.mark.asyncio
async def test_reset_password_mismatch(client):
    resp = await client.post("/reset-password", data={
        "token": "tok",
        "password": "newpass123!",
        "password2": "different!",
    }, follow_redirects=False)
    assert resp.status_code == 400
    assert b"do not match" in resp.content.lower()


@pytest.mark.asyncio
async def test_reset_password_bad_token(client):
    resp = await client.post("/reset-password", data={
        "token": "invalid-token",
        "password": "newpass123!",
        "password2": "newpass123!",
    }, follow_redirects=False)
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# UI routes — email verification ENABLED
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_with_verification_shows_pending(client):
    """When require_email_verification=True, registration shows verify_pending page."""
    get_settings.cache_clear()
    with patch.dict("os.environ", {"REQUIRE_EMAIL_VERIFICATION": "true"}):
        get_settings.cache_clear()
        with patch("app.services.email.send_email", new_callable=AsyncMock) as mock_send:
            resp = await _register_ui(client, username="veruser", email="ver@example.com")
            assert resp.status_code == 200
            assert b"Verify Your Email" in resp.content
            mock_send.assert_awaited_once()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_full_verification_flow(client, db_session):
    """Register → token stored → /verify-email → logged in."""
    get_settings.cache_clear()
    with patch.dict("os.environ", {"REQUIRE_EMAIL_VERIFICATION": "true"}):
        get_settings.cache_clear()
        with patch("app.services.email.send_email", new_callable=AsyncMock):
            await _register_ui(client, username="flowuser", email="flow@example.com")

    # Fetch the token directly from DB
    from sqlalchemy import select
    from app.models import User
    result = await db_session.execute(select(User).where(User.username == "flowuser"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.verification_token is not None

    # Visit the verification link
    resp = await client.get(f"/verify-email?token={user.verification_token}",
                            follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    # Confirm flag set in DB
    await db_session.refresh(user)
    assert user.email_verified
    assert user.verification_token is None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_full_reset_flow(client, db_session):
    """Register → forgot password → token stored → reset → login succeeds."""
    await register_user(client, username="resetflow", email="rf@example.com",
                        password="original123!")

    with patch("app.services.email.send_email", new_callable=AsyncMock):
        resp = await client.post("/forgot-password", data={"email": "rf@example.com"},
                                 follow_redirects=False)
    assert resp.status_code == 200
    assert b"reset link" in resp.content.lower()

    # Grab token from DB
    from sqlalchemy import select
    from app.models import User
    result = await db_session.execute(select(User).where(User.username == "resetflow"))
    user = result.scalar_one()
    token = user.reset_token
    assert token

    # Submit new password
    resp = await client.post("/reset-password", data={
        "token": token,
        "password": "newpass456!",
        "password2": "newpass456!",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert "reset=1" in resp.headers["location"]

    # Login with new password
    resp = await client.post("/api/v1/auth/token",
                             data={"username": "resetflow", "password": "newpass456!"},
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert resp.status_code == 200
