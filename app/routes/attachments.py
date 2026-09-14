#!/usr/bin/env python
#
#
# ----------------------------------------------------------------------------
"""
Attachments router
==================
GET    /api/v1/namespaces/{ns}/pages/{slug}/attachments              — list
POST   /api/v1/namespaces/{ns}/pages/{slug}/attachments              — upload [auth]
GET    /api/v1/namespaces/{ns}/pages/{slug}/attachments/{filename}   — download
DELETE /api/v1/namespaces/{ns}/pages/{slug}/attachments/{filename}   — delete [auth]
GET    /attachments/{att_id}/{filename}                              — direct URL
"""
# ----------------------------------------------------------------------------

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ----------------------------------------------------------------------------
from app.core.config import get_settings
from app.core.database import get_db
from app.core.filetypes import content_type_for, extension_of, serves_inline
from app.core.security import get_current_user_id_bearer_or_cookie as get_current_user_id
from app.models import Attachment
from app.schemas import AttachmentResponse, OKResponse
from app.services.attachments import (
    attachment_url,
    delete_attachment,
    get_attachment,
    list_attachments,
    upload_attachment,
)

# ----------------------------------------------------------------------------

router = APIRouter(tags=["attachments"])

_page_prefix = "/namespaces/{namespace_name}/pages/{slug}/attachments"


# ── List ──────────────────────────────────────────────────────────────────── 

@router.get(_page_prefix, response_model=list[AttachmentResponse])
async def list_page_attachments(
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    atts = await list_attachments(db, namespace_name, slug)
    return [
        {**_att_dict(a), "url": attachment_url(a, settings.base_url)}
        for a in atts
    ]


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post(_page_prefix, response_model=AttachmentResponse, status_code=201)
async def upload_page_attachment(
    namespace_name: str,
    slug: str,
    file: UploadFile,
    comment: str     = Form(default=""),
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    att = await upload_attachment(db, namespace_name, slug, file, comment=comment, uploaded_by=user_id)
    return {**_att_dict(att), "url": attachment_url(att, settings.base_url)}


# ── Download ──────────────────────────────────────────────────────────────────

@router.get(f"{_page_prefix}/{{filename}}")
async def download_attachment(
    namespace_name: str,
    slug: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    att = await get_attachment(db, namespace_name, slug, filename)
    return _file_response(att)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete(f"{_page_prefix}/{{filename}}", response_model=OKResponse)
async def delete_page_attachment(
    namespace_name: str,
    slug: str,
    filename: str,
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await delete_attachment(db, namespace_name, slug, filename)
    return OKResponse(message=f"Attachment '{filename}' deleted")


# ── Direct attachment URL (by UUID) ──────────────────────────────────────────

@router.get("/attachments/{att_id}/{filename}")
async def serve_attachment(
    att_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Attachment).where(Attachment.id == att_id, Attachment.filename == filename)
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return _file_response(att)


# -----------------------------------------------------------------------------

# Uploaded files are untrusted: never let the browser sniff a different type, and
# sandbox anything it renders so scripts in e.g. an SVG cannot touch the wiki origin.
# PDFs are exempt from the sandbox because Chrome's PDF viewer refuses to run under it.
_SANDBOX_CSP = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"


def _file_response(att) -> FileResponse:
    settings = get_settings()
    abs_path = settings.attachment_root_resolved / att.storage_path
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    headers = {"X-Content-Type-Options": "nosniff"}
    if extension_of(att.filename) != "pdf":
        headers["Content-Security-Policy"] = _SANDBOX_CSP
    return FileResponse(
        path=str(abs_path),
        media_type=content_type_for(att.filename),
        filename=att.filename,
        content_disposition_type="inline" if serves_inline(att.filename) else "attachment",
        headers=headers,
    )


# -----------------------------------------------------------------------------

def _att_dict(att) -> dict:
    return {
        "id":           att.id,
        "page_id":      att.page_id,
        "filename":     att.filename,
        "content_type": att.content_type,
        "size_bytes":   att.size_bytes,
        "comment":      att.comment,
        "uploaded_by":  att.uploaded_by,
        "uploaded_at":  att.uploaded_at,
        "url":          "",  # overridden by callers
    }


# -----------------------------------------------------------------------------
