#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for auth endpoints."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, login_user, register_user


# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "password123",
        "display_name": "Alice",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["is_admin"] is True  # first registered user is auto-promoted to admin


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    await register_user(client, "bob", "bob@example.com")
    resp = await client.post("/api/v1/auth/register", json={
        "username": "bob",
        "email": "bob2@example.com",
        "password": "password123",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_reserved_username(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "username": "admin",
        "email": "admin@example.com",
        "password": "password123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await register_user(client, "carol", "carol@example.com")
    token = await login_user(client, "carol")
    assert token


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await register_user(client, "dave", "dave@example.com")
    resp = await client.post(
        "/api/v1/auth/token",
        data={"username": "dave", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient):
    await register_user(client, "eve", "eve@example.com")
    headers = await auth_headers(client, "eve")
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "eve"


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# -----------------------------------------------------------------------------
