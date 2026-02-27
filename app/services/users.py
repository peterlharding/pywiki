#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
User service — create, authenticate, and manage user accounts.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas import UserCreate, UserUpdate


# -----------------------------------------------------------------------------

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    # Check for existing username / email
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    existing_email = await db.execute(select(User).where(User.email == str(data.email)))
    if existing_email.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    from sqlalchemy import func
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    is_first_user = (user_count == 0)

    user = User(
        username=data.username,
        email=str(data.email),
        display_name=data.display_name or data.username,
        password_hash=hash_password(data.password),
        is_admin=is_first_user,
    )
    db.add(user)
    await db.flush()
    return user


# -----------------------------------------------------------------------------

async def authenticate_user(db: AsyncSession, username: str, password: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return user


# -----------------------------------------------------------------------------

async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -----------------------------------------------------------------------------

async def get_user_by_id_or_none(db: AsyncSession, user_id: str | None) -> User | None:
    if not user_id:
        return None
    return await db.get(User, user_id)


# -----------------------------------------------------------------------------

async def get_user_by_username(db: AsyncSession, username: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -----------------------------------------------------------------------------

async def update_user(db: AsyncSession, user_id: str, data: UserUpdate) -> User:
    user = await get_user_by_id(db, user_id)
    if data.email is not None:
        user.email = str(data.email)
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    await db.flush()
    return user


# -----------------------------------------------------------------------------

async def set_admin(db: AsyncSession, username: str, is_admin: bool) -> User:
    user = await get_user_by_username(db, username)
    user.is_admin = is_admin
    await db.flush()
    return user


# -----------------------------------------------------------------------------

async def set_active(db: AsyncSession, username: str, is_active: bool) -> User:
    user = await get_user_by_username(db, username)
    user.is_active = is_active
    await db.flush()
    return user


# -----------------------------------------------------------------------------

async def list_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    result = await db.execute(select(User).order_by(User.username).offset(skip).limit(limit))
    return list(result.scalars().all())


# -----------------------------------------------------------------------------

async def get_user_contributions(
    db: AsyncSession, user_id: str, limit: int = 20
) -> list[dict]:
    from sqlalchemy import select as sa_select, func
    from app.models import PageVersion, Page, Namespace
    result = await db.execute(
        sa_select(PageVersion, Page, Namespace)
        .join(Page, PageVersion.page_id == Page.id)
        .join(Namespace, Page.namespace_id == Namespace.id)
        .where(PageVersion.author_id == user_id)
        .order_by(PageVersion.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "namespace": ns.name,
            "slug": page.slug,
            "title": page.title,
            "version": ver.version,
            "comment": ver.comment,
            "created_at": ver.created_at,
        }
        for ver, page, ns in rows
    ]


# -----------------------------------------------------------------------------

async def get_user_edit_count(db: AsyncSession, user_id: str) -> int:
    from sqlalchemy import func
    from app.models import PageVersion
    result = await db.execute(
        select(func.count()).select_from(PageVersion).where(PageVersion.author_id == user_id)
    )
    return result.scalar_one()


# -----------------------------------------------------------------------------
