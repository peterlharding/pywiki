#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for namespace endpoints."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user


# -----------------------------------------------------------------------------

async def _admin_headers(client: AsyncClient) -> dict:
    await register_user(client, "nsadmin", "nsadmin@example.com")
    # Make admin via direct DB manipulation through auth endpoint isn't exposed —
    # use the make-admin endpoint after a second admin bootstraps it.
    # For tests, patch the user directly.
    from sqlalchemy import select
    from app.models import User
    # We rely on the test DB fixture; let's just call make-admin after promoting via DB
    headers = await auth_headers(client, "nsadmin")
    return headers


@pytest.mark.asyncio
async def test_list_namespaces_empty(client: AsyncClient):
    resp = await client.get("/api/v1/namespaces")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_namespace_requires_admin(client: AsyncClient):
    await register_user(client, "user1", "user1@example.com")
    headers = await auth_headers(client, "user1")
    resp = await client.post("/api/v1/namespaces", json={
        "name": "TestNS",
        "description": "A test namespace",
        "default_format": "markdown",
    }, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_namespace_as_admin(client: AsyncClient, db_session):
    """Promote user to admin via DB then create namespace."""
    await register_user(client, "adminuser", "adminuser@example.com")

    # Promote to admin directly in DB
    from sqlalchemy import update
    from app.models import User
    await db_session.execute(
        update(User).where(User.username == "adminuser").values(is_admin=True)
    )
    await db_session.commit()

    headers = await auth_headers(client, "adminuser")
    resp = await client.post("/api/v1/namespaces", json={
        "name": "MyNS",
        "description": "Created by admin",
        "default_format": "rst",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "MyNS"
    assert data["default_format"] == "rst"


@pytest.mark.asyncio
async def test_get_namespace(client: AsyncClient, db_session):
    await register_user(client, "admin2", "admin2@example.com")
    from sqlalchemy import update
    from app.models import User
    await db_session.execute(
        update(User).where(User.username == "admin2").values(is_admin=True)
    )
    await db_session.commit()

    headers = await auth_headers(client, "admin2")
    await client.post("/api/v1/namespaces", json={
        "name": "Wiki", "description": "", "default_format": "markdown"
    }, headers=headers)

    resp = await client.get("/api/v1/namespaces/Wiki")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Wiki"


@pytest.mark.asyncio
async def test_invalid_namespace_format(client: AsyncClient, db_session):
    await register_user(client, "admin3", "admin3@example.com")
    from sqlalchemy import update
    from app.models import User
    await db_session.execute(
        update(User).where(User.username == "admin3").values(is_admin=True)
    )
    await db_session.commit()

    headers = await auth_headers(client, "admin3")
    resp = await client.post("/api/v1/namespaces", json={
        "name": "NS2", "description": "", "default_format": "html"
    }, headers=headers)
    assert resp.status_code == 422


# -----------------------------------------------------------------------------
