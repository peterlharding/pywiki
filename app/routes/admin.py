#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Admin router
============
GET    /api/v1/admin/stats       — site statistics     [admin]
GET    /api/v1/admin/config      — site configuration  [admin]
GET    /api/v1/admin/users       — list all users      [admin]
PATCH  /api/v1/admin/users/{username}/activate   [admin]
PATCH  /api/v1/admin/users/{username}/deactivate [admin]
DELETE /api/v1/admin/users/{username}            [admin]
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models import Namespace, Page, PageVersion, User
from app.schemas import (
    AdminConfigResponse, AdminStatsResponse,
    OKResponse, UserAdminResponse,
)
from app.services.users import get_user_by_id, list_users, set_active


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/admin", tags=["admin"])


# -----------------------------------------------------------------------------

async def _require_admin(user_id: str, db: AsyncSession) -> User:
    user = await get_user_by_id(db, user_id)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)

    user_count    = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    admin_count   = (await db.execute(select(func.count()).select_from(User).where(User.is_admin == True))).scalar_one()
    ns_count      = (await db.execute(select(func.count()).select_from(Namespace))).scalar_one()
    page_count    = (await db.execute(select(func.count()).select_from(Page))).scalar_one()
    version_count = (await db.execute(select(func.count()).select_from(PageVersion))).scalar_one()

    return AdminStatsResponse(
        user_count=user_count,
        admin_count=admin_count,
        namespace_count=ns_count,
        page_count=page_count,
        version_count=version_count,
    )


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config", response_model=AdminConfigResponse)
async def get_config(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    settings = get_settings()
    return AdminConfigResponse(
        site_name=settings.site_name,
        base_url=settings.base_url,
        allow_registration=settings.allow_registration,
        default_namespace=settings.default_namespace,
        admin_email=settings.admin_email,
        app_version=settings.app_version,
        environment=settings.environment,
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserAdminResponse])
async def list_all_users(
    skip:  int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    users = await list_users(db, skip=skip, limit=limit)
    return [
        {
            "id":           u.id,
            "username":     u.username,
            "email":        u.email,
            "display_name": u.display_name,
            "is_admin":     u.is_admin,
            "is_active":    u.is_active,
            "created_at":   u.created_at,
        }
        for u in users
    ]


# -----------------------------------------------------------------------------

@router.patch("/users/{username}/activate", response_model=OKResponse)
async def activate_user(
    username: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    await set_active(db, username, is_active=True)
    return OKResponse(message=f"User '{username}' activated")


# -----------------------------------------------------------------------------

@router.patch("/users/{username}/deactivate", response_model=OKResponse)
async def deactivate_user(
    username: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    await set_active(db, username, is_active=False)
    return OKResponse(message=f"User '{username}' deactivated")


# -----------------------------------------------------------------------------

@router.delete("/users/{username}", response_model=OKResponse)
async def delete_user(
    username: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _require_admin(user_id, db)
    from app.services.users import get_user_by_username
    target = await get_user_by_username(db, username)
    if target.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    await db.delete(target)
    return OKResponse(message=f"User '{username}' deleted")


# -----------------------------------------------------------------------------
