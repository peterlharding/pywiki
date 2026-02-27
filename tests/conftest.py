#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Pytest fixtures for PyWiki tests.
Uses an in-memory SQLite database so no external services are needed.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import create_app


# -----------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# -----------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session_factory(db_engine):
    """Shared sessionmaker — both client and db_session use this."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session(db_session_factory):
    """Direct DB session for test setup (admin promotion, etc)."""
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine, db_session_factory):
    """HTTP test client wired to an isolated in-memory DB."""
    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# -----------------------------------------------------------------------------
# Helper functions for tests
# -----------------------------------------------------------------------------

async def register_user(client: AsyncClient, username: str = "testuser",
                         email: str = "test@example.com",
                         password: str = "testpass123") -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
        "display_name": username.title(),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def login_user(client: AsyncClient, username: str = "testuser",
                     password: str = "testpass123") -> str:
    resp = await client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def auth_headers(client: AsyncClient, username: str = "testuser",
                       password: str = "testpass123") -> dict:
    token = await login_user(client, username, password)
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
