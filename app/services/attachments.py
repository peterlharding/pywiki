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
from urllib.parse import quote

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.filetypes import (
    PROHIBITED_EXTENSIONS,
    content_type_for,
    extension_of,
    sanitize_filename,
)
from app.models import Attachment, Page, PageVersion

from .pages import get_page

# -----------------------------------------------------------------------------

def validate_attachment_filename(filename: str | None) -> str:
    """Return the sanitized filename, or raise 415 if its type may not be uploaded."""
    settings = get_settings()
    name     = sanitize_filename(filename or "")
    ext      = extension_of(name)
    allowed  = ", ".join(sorted(settings.allowed_attachment_extensions))

    if not ext:
        detail = f"File must have an extension. Allowed types: {allowed}"
    elif ext in PROHIBITED_EXTENSIONS:
        detail = f"'.{ext}' files are not allowed for security reasons."
    elif ext not in settings.allowed_attachment_extensions:
        detail = f"'.{ext}' files are not allowed. Allowed types: {allowed}"
    else:
        return name
    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=detail)


# -----------------------------------------------------------------------------

async def save_attachment(
    db: AsyncSession,
    page: Page,
    namespace_name: str,
    filename: str,
    data: bytes,
    comment: str = "",
    uploaded_by: str | None = None,
) -> tuple[Attachment, bool]:
    """Validate, store and upsert one attachment.  Returns (attachment, created)."""
    settings = get_settings()
    filename = validate_attachment_filename(filename)

    if len(data) > settings.max_attachment_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_attachment_bytes // 1024 // 1024} MB",
        )

    # Build storage path: data/attachments/<namespace>/<slug>/<filename>
    rel_path = Path(namespace_name) / page.slug / filename
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
    created = att is None
    if att is None:
        att = Attachment(page_id=page.id, filename=filename)
        db.add(att)
    att.content_type = content_type_for(filename)
    att.size_bytes   = len(data)
    att.storage_path = str(rel_path)
    att.comment      = comment
    att.uploaded_by  = uploaded_by

    await invalidate_rendered_html(db, page.id)
    await db.flush()
    return att, created


# -----------------------------------------------------------------------------

async def upload_attachment(
    db: AsyncSession,
    namespace_name: str,
    page_slug: str,
    file: UploadFile,
    comment: str = "",
    uploaded_by: str | None = None,
) -> Attachment:
    page, _ = await get_page(db, namespace_name, page_slug)
    validate_attachment_filename(file.filename)   # reject before reading the body
    data = await file.read()
    att, _ = await save_attachment(
        db, page, namespace_name, file.filename or "", data,
        comment=comment, uploaded_by=uploaded_by,
    )
    return att


# -----------------------------------------------------------------------------

async def invalidate_rendered_html(db: AsyncSession, page_id: str) -> None:
    """Drop cached HTML for a page; attachment links resolve differently once files change."""
    await db.execute(
        update(PageVersion).where(PageVersion.page_id == page_id).values(rendered=None)
    )


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

async def attachment_map(db: AsyncSession, page_id: str, base_url: str = "") -> dict[str, str]:
    """{filename: url} for every attachment on a page, as the renderer expects."""
    result = await db.execute(select(Attachment).where(Attachment.page_id == page_id))
    return {a.filename: attachment_url(a, base_url) for a in result.scalars().all()}


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
    await invalidate_rendered_html(db, att.page_id)
    await db.delete(att)


# -----------------------------------------------------------------------------

def attachment_url(att: Attachment, base_url: str = "") -> str:
    return f"{base_url}/api/v1/attachments/{att.id}/{quote(att.filename)}"


# -----------------------------------------------------------------------------
