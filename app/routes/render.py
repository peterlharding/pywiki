#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Render endpoint — live preview for the editor.

GET /api/v1/render?content=...&format=markdown&namespace=Main
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.attachments import attachment_url, list_attachments
from app.services.renderer import render


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/render", tags=["render"])


# -----------------------------------------------------------------------------

@router.get("")
async def render_preview(
    content:   str = Query(default="", max_length=1_000_000),
    format:    str = Query(default="markdown"),
    namespace: str = Query(default="Main"),
    slug:      str = Query(default=""),
    db:        AsyncSession = Depends(get_db),
):
    """Return rendered HTML for a snippet of Markdown or RST — used by the live editor preview."""
    settings = get_settings()
    att_map: dict[str, str] | None = None
    if slug:
        try:
            atts = await list_attachments(db, namespace, slug)
            if atts:
                att_map = {a.filename: attachment_url(a, settings.base_url) for a in atts}
        except Exception:
            pass
    html = render(content, format, namespace=namespace, base_url=settings.base_url, attachments=att_map)
    return {"html": html, "format": format}


# -----------------------------------------------------------------------------
