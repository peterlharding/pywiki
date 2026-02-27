#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Namespaces router
=================
GET    /api/v1/namespaces                  — list namespaces
POST   /api/v1/namespaces                  — create namespace  [auth]
GET    /api/v1/namespaces/{name}           — get namespace
PUT    /api/v1/namespaces/{name}           — update namespace  [auth]
DELETE /api/v1/namespaces/{name}           — delete namespace  [auth, admin]
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas import NamespaceCreate, NamespaceResponse, NamespaceUpdate, OKResponse
from app.services import namespaces as ns_svc
from app.services.users import get_user_by_id


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


# -----------------------------------------------------------------------------

@router.get("", response_model=list[NamespaceResponse])
async def list_namespaces(
    skip:  int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    namespaces = await ns_svc.list_namespaces(db, skip=skip, limit=limit)
    results = []
    for ns in namespaces:
        count = await ns_svc.get_page_count(db, ns.id)
        results.append({
            "id":             ns.id,
            "name":           ns.name,
            "description":    ns.description,
            "default_format": ns.default_format,
            "page_count":     count,
            "created_at":     ns.created_at,
        })
    return results


# -----------------------------------------------------------------------------

@router.post("", response_model=NamespaceResponse, status_code=201)
async def create_namespace(
    data: NamespaceCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, user_id)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    ns = await ns_svc.create_namespace(db, data)
    return {
        "id":             ns.id,
        "name":           ns.name,
        "description":    ns.description,
        "default_format": ns.default_format,
        "page_count":     0,
        "created_at":     ns.created_at,
    }


# -----------------------------------------------------------------------------

@router.get("/{name}", response_model=NamespaceResponse)
async def get_namespace(name: str, db: AsyncSession = Depends(get_db)):
    ns = await ns_svc.get_namespace_by_name(db, name)
    count = await ns_svc.get_page_count(db, ns.id)
    return {
        "id":             ns.id,
        "name":           ns.name,
        "description":    ns.description,
        "default_format": ns.default_format,
        "page_count":     count,
        "created_at":     ns.created_at,
    }


# -----------------------------------------------------------------------------

@router.put("/{name}", response_model=NamespaceResponse)
async def update_namespace(
    name: str,
    data: NamespaceUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, user_id)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    ns = await ns_svc.update_namespace(db, name, data)
    count = await ns_svc.get_page_count(db, ns.id)
    return {
        "id":             ns.id,
        "name":           ns.name,
        "description":    ns.description,
        "default_format": ns.default_format,
        "page_count":     count,
        "created_at":     ns.created_at,
    }


# -----------------------------------------------------------------------------

@router.delete("/{name}", response_model=OKResponse)
async def delete_namespace(
    name: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(db, user_id)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    await ns_svc.delete_namespace(db, name)
    return OKResponse(message=f"Namespace '{name}' deleted")


# -----------------------------------------------------------------------------
