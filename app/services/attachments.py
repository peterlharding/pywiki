#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Attachment service — upload, list, serve, and delete file attachments.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Attachment, Page
from .pages import get_page


# -----------------------------------------------------------------------------

async def upload_attachment(
    db: AsyncSession,
    namespace_name: str,
    page_slug: str,
    file: UploadFile,
    comment: str = "",
    uploaded_by: Optional[str] = None,
) -> Attachment:
    settings = get_settings()

    page, _ = await get_page(db, namespace_name, page_slug)

    # Check for file size
    data = await file.read()
    if len(data) > settings.max_attachment_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_attachment_bytes // 1024 // 1024} MB",
        )

    filename = Path(file.filename or "upload").name

    # Build storage path: data/attachments/<namespace>/<slug>/<filename>
    rel_path = Path(namespace_name) / page_slug / filename
    abs_path = settings.attachment_root_resolved / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(abs_path, "wb") as f:
        await f.write(data)

    # Upsert: replace existing attachment with same filename
    existing = await db.execute(
        select(Attachment).where(
            Attachment.page_id == page.id,
            Attachment.filename == filename,
        )
    )
    att = existing.scalar_one_or_none()
    if att:
        att.content_type = file.content_type or "application/octet-stream"
        att.size_bytes   = len(data)
        att.storage_path = str(rel_path)
        att.comment      = comment
        att.uploaded_by  = uploaded_by
    else:
        att = Attachment(
            page_id=page.id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(data),
            storage_path=str(rel_path),
            comment=comment,
            uploaded_by=uploaded_by,
        )
        db.add(att)

    await db.flush()
    return att


# -----------------------------------------------------------------------------

async def list_attachments(
    db: AsyncSession,
    namespace_name: str,
    page_slug: str,
) -> list[Attachment]:
    page, _ = await get_page(db, namespace_name, page_slug)
    result = await db.execute(
        select(Attachment)
        .where(Attachment.page_id == page.id)
        .order_by(Attachment.filename)
    )
    return list(result.scalars().all())


# -----------------------------------------------------------------------------

async def get_attachment(
    db: AsyncSession,
    namespace_name: str,
    page_slug: str,
    filename: str,
) -> Attachment:
    page, _ = await get_page(db, namespace_name, page_slug)
    result = await db.execute(
        select(Attachment).where(
            Attachment.page_id == page.id,
            Attachment.filename == filename,
        )
    )
    att = result.scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail=f"Attachment '{filename}' not found")
    return att


# -----------------------------------------------------------------------------

async def delete_attachment(
    db: AsyncSession,
    namespace_name: str,
    page_slug: str,
    filename: str,
) -> None:
    settings = get_settings()
    att = await get_attachment(db, namespace_name, page_slug, filename)
    abs_path = settings.attachment_root_resolved / att.storage_path
    try:
        abs_path.unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(att)


# -----------------------------------------------------------------------------

def attachment_url(att: Attachment, base_url: str = "") -> str:
    return f"{base_url}/api/v1/attachments/{att.id}/{att.filename}"


# -----------------------------------------------------------------------------
