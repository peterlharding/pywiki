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

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.services.renderer import render


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/render", tags=["render"])


# -----------------------------------------------------------------------------

@router.get("")
async def render_preview(
    content:   str = Query(default="", max_length=1_000_000),
    format:    str = Query(default="markdown"),
    namespace: str = Query(default="Main"),
):
    """Return rendered HTML for a snippet of Markdown or RST — used by the live editor preview."""
    settings = get_settings()
    html = render(content, format, namespace=namespace, base_url=settings.base_url)
    return {"html": html, "format": format}


# -----------------------------------------------------------------------------
