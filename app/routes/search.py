#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Search router
=============
GET /api/v1/search?q=...&namespace=...   — full-text search across all pages
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import SearchResult
from app.services.pages import search_pages


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/search", tags=["search"])


# -----------------------------------------------------------------------------

@router.get("", response_model=list[SearchResult])
async def search(
    q:         str           = Query(..., min_length=1, max_length=256, description="Search query"),
    namespace: Optional[str] = Query(None, description="Restrict search to this namespace"),
    skip:      int           = Query(0, ge=0),
    limit:     int           = Query(50, ge=1, le=200),
    db: AsyncSession         = Depends(get_db),
):
    results = await search_pages(db, q, namespace_name=namespace, skip=skip, limit=limit)
    return results


# -----------------------------------------------------------------------------
