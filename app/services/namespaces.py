#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Namespace service — create, read, list, and delete wiki namespaces.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Namespace, Page
from app.schemas import NamespaceCreate, NamespaceUpdate


# -----------------------------------------------------------------------------

async def create_namespace(db: AsyncSession, data: NamespaceCreate) -> Namespace:
    existing = await db.execute(select(Namespace).where(Namespace.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Namespace '{data.name}' already exists",
        )

    ns = Namespace(
        name=data.name,
        description=data.description,
        default_format=data.default_format,
    )
    db.add(ns)
    await db.flush()
    return ns


# -----------------------------------------------------------------------------

async def get_namespace_by_name(db: AsyncSession, name: str) -> Namespace:
    result = await db.execute(select(Namespace).where(Namespace.name == name))
    ns = result.scalar_one_or_none()
    if not ns:
        raise HTTPException(status_code=404, detail=f"Namespace '{name}' not found")
    return ns


# -----------------------------------------------------------------------------

async def get_namespace_by_id(db: AsyncSession, ns_id: str) -> Namespace:
    ns = await db.get(Namespace, ns_id)
    if not ns:
        raise HTTPException(status_code=404, detail="Namespace not found")
    return ns


# -----------------------------------------------------------------------------

async def list_namespaces(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Namespace]:
    result = await db.execute(
        select(Namespace).order_by(Namespace.name).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


# -----------------------------------------------------------------------------

async def update_namespace(db: AsyncSession, name: str, data: NamespaceUpdate) -> Namespace:
    ns = await get_namespace_by_name(db, name)
    if data.description is not None:
        ns.description = data.description
    if data.default_format is not None:
        ns.default_format = data.default_format
    await db.flush()
    return ns


# -----------------------------------------------------------------------------

async def delete_namespace(db: AsyncSession, name: str) -> None:
    ns = await get_namespace_by_name(db, name)
    count_result = await db.execute(
        select(func.count()).select_from(Page).where(Page.namespace_id == ns.id)
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a namespace that contains pages",
        )
    await db.delete(ns)


# -----------------------------------------------------------------------------

async def get_page_count(db: AsyncSession, ns_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(Page).where(Page.namespace_id == ns_id)
    )
    return result.scalar_one()


# -----------------------------------------------------------------------------
