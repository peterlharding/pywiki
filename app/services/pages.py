#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Page service
============
Versioned create / read / update / rename / delete for wiki pages.

Every save appends a new PageVersion row — nothing is overwritten.
Diffs use Python's difflib SequenceMatcher.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import difflib
import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Namespace, Page, PageVersion, User
from app.schemas import PageCreate, PageRename, PageUpdate
from .namespaces import get_namespace_by_name


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a page title to a URL slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


async def _get_page(db: AsyncSession, ns_id: str, slug: str) -> Page:
    result = await db.execute(
        select(Page)
        .where(Page.namespace_id == ns_id, Page.slug == slug)
        .options(
            selectinload(Page.versions).selectinload(PageVersion.author),
        )
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{slug}' not found")
    return page


async def _latest_version(db: AsyncSession, page_id: str) -> Optional[PageVersion]:
    result = await db.execute(
        select(PageVersion)
        .where(PageVersion.page_id == page_id)
        .order_by(PageVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _next_version_number(db: AsyncSession, page_id: str) -> int:
    result = await db.execute(
        select(func.max(PageVersion.version)).where(PageVersion.page_id == page_id)
    )
    current = result.scalar_one_or_none()
    return (current or 0) + 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def create_page(
    db: AsyncSession,
    namespace_name: str,
    data: PageCreate,
    author_id: Optional[str] = None,
) -> tuple[Page, PageVersion]:
    ns = await get_namespace_by_name(db, namespace_name)
    slug = _slugify(data.title)

    exists = await db.execute(
        select(Page).where(Page.namespace_id == ns.id, Page.slug == slug)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Page '{data.title}' already exists in namespace '{namespace_name}'",
        )

    page = Page(namespace_id=ns.id, title=data.title, slug=slug, created_by=author_id)
    db.add(page)
    await db.flush()

    fmt = data.format or ns.default_format
    version = PageVersion(
        page_id=page.id,
        version=1,
        content=data.content,
        format=fmt,
        author_id=author_id,
        comment=data.comment or "Initial version",
    )
    db.add(version)
    await db.flush()

    page, version = await _reload_page_version(db, page.id, version.version)
    return page, version


# -----------------------------------------------------------------------------

async def get_page(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
    version: Optional[int] = None,
) -> tuple[Page, PageVersion]:
    """Return (page, version_row). Defaults to latest version."""
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)

    if version is not None:
        result = await db.execute(
            select(PageVersion)
            .where(PageVersion.page_id == page.id, PageVersion.version == version)
            .options(selectinload(PageVersion.author))
        )
        ver = result.scalar_one_or_none()
        if not ver:
            raise HTTPException(status_code=404, detail=f"Version {version} not found")
    else:
        result = await db.execute(
            select(PageVersion)
            .where(PageVersion.page_id == page.id)
            .options(selectinload(PageVersion.author))
            .order_by(PageVersion.version.desc())
            .limit(1)
        )
        ver = result.scalar_one_or_none()
        if not ver:
            raise HTTPException(status_code=404, detail="Page has no content")

    return page, ver


# -----------------------------------------------------------------------------

async def get_page_by_title(
    db: AsyncSession,
    namespace_name: str,
    title: str,
) -> tuple[Page, PageVersion]:
    """Lookup page by title (case-insensitive) rather than slug."""
    ns = await get_namespace_by_name(db, namespace_name)
    result = await db.execute(
        select(Page)
        .where(Page.namespace_id == ns.id, Page.title.ilike(title))
        .options(selectinload(Page.versions).selectinload(PageVersion.author))
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{title}' not found")
    ver = max(page.versions, key=lambda v: v.version) if page.versions else None
    if not ver:
        raise HTTPException(status_code=404, detail="Page has no content")
    return page, ver


# -----------------------------------------------------------------------------

async def update_page(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
    data: PageUpdate,
    author_id: Optional[str] = None,
) -> tuple[Page, PageVersion]:
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)

    next_ver = await _next_version_number(db, page.id)
    prev = await _latest_version(db, page.id)
    if prev:
        prev.rendered = None   # invalidate cache

    fmt = data.format or (prev.format if prev else ns.default_format)
    new_version = PageVersion(
        page_id=page.id,
        version=next_ver,
        content=data.content,
        format=fmt,
        author_id=author_id,
        comment=data.comment or "",
    )
    db.add(new_version)
    await db.flush()

    page, new_version = await _reload_page_version(db, page.id, new_version.version)
    return page, new_version


# -----------------------------------------------------------------------------

async def rename_page(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
    data: PageRename,
    author_id: Optional[str] = None,
) -> Page:
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)

    old_slug  = page.slug
    old_title = page.title
    new_slug  = _slugify(data.new_title)

    if new_slug != old_slug:
        conflict = await db.execute(
            select(Page).where(Page.namespace_id == ns.id, Page.slug == new_slug)
        )
        if conflict.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A page with title '{data.new_title}' already exists",
            )

    page.title = data.new_title
    page.slug  = new_slug

    # Record the rename as a new version on the page so it appears in history
    if old_slug != new_slug or old_title != data.new_title:
        latest = await db.execute(
            select(func.max(PageVersion.version)).where(PageVersion.page_id == page.id)
        )
        next_ver = (latest.scalar() or 0) + 1
        reason_text = data.reason.strip() if data.reason else ""
        comment = f"Renamed from '{old_title}' to '{data.new_title}'"
        if reason_text:
            comment += f": {reason_text}"
        # Carry forward the current content/format from the most recent version
        last_ver_q = await db.execute(
            select(PageVersion)
            .where(PageVersion.page_id == page.id)
            .order_by(PageVersion.version.desc())
            .limit(1)
        )
        last_ver = last_ver_q.scalar_one_or_none()
        content = last_ver.content if last_ver else ""
        fmt     = last_ver.format  if last_ver else "markdown"
        rename_ver = PageVersion(
            page_id=page.id,
            version=next_ver,
            content=content,
            format=fmt,
            comment=comment,
            author_id=author_id,
        )
        db.add(rename_ver)

    # Optionally leave a redirect stub at the old slug
    if new_slug != old_slug and data.leave_redirect:
        redirect_content = (
            f"#REDIRECT [[{data.new_title}]]\n\n"
            f"This page has been moved to [[{data.new_title}]]."
        )
        redirect_page = Page(
            namespace_id=ns.id,
            title=old_title,
            slug=old_slug,
        )
        db.add(redirect_page)
        await db.flush()
        db.add(PageVersion(
            page_id=redirect_page.id,
            version=1,
            content=redirect_content,
            format="wikitext",
            comment=f"Redirect to '{data.new_title}' after page move",
            author_id=author_id,
        ))

    await db.commit()
    await db.refresh(page)
    return page


# -----------------------------------------------------------------------------

async def delete_page(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
) -> None:
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)
    await db.delete(page)


# -----------------------------------------------------------------------------

async def list_pages(
    db: AsyncSession,
    namespace_name: str,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
) -> list[dict]:
    """Return lightweight summaries (no content body)."""
    ns = await get_namespace_by_name(db, namespace_name)

    max_ver_sub = (
        select(
            PageVersion.page_id,
            func.max(PageVersion.version).label("max_ver"),
        )
        .group_by(PageVersion.page_id)
        .subquery()
    )

    q = (
        select(Page, PageVersion, User)
        .join(max_ver_sub, Page.id == max_ver_sub.c.page_id)
        .join(
            PageVersion,
            (PageVersion.page_id == Page.id) &
            (PageVersion.version == max_ver_sub.c.max_ver),
        )
        .outerjoin(User, User.id == PageVersion.author_id)
        .where(Page.namespace_id == ns.id)
        .order_by(Page.title)
        .offset(skip)
        .limit(limit)
    )

    if search:
        q = q.where(Page.title.ilike(f"%{search}%"))

    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "id":              p.id,
            "namespace":       namespace_name,
            "title":           p.title,
            "slug":            p.slug,
            "version":         v.version,
            "format":          v.format,
            "author_username": u.username if u else None,
            "updated_at":      v.created_at,
        }
        for p, v, u in rows
    ]


# -----------------------------------------------------------------------------

async def get_page_history(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
) -> list[PageVersion]:
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)
    return sorted(page.versions, key=lambda v: v.version, reverse=True)


# -----------------------------------------------------------------------------

async def get_diff(
    db: AsyncSession,
    namespace_name: str,
    slug: str,
    from_ver: int,
    to_ver: int,
) -> list[dict]:
    """
    Return a structured diff between two versions.
    Each item: {"type": "equal"|"insert"|"delete", "lines": ["..."]}
    """
    ns = await get_namespace_by_name(db, namespace_name)
    page = await _get_page(db, ns.id, slug)

    ver_map = {v.version: v for v in page.versions}
    a_ver = ver_map.get(from_ver)
    b_ver = ver_map.get(to_ver)

    if not a_ver:
        raise HTTPException(status_code=404, detail=f"Version {from_ver} not found")
    if not b_ver:
        raise HTTPException(status_code=404, detail=f"Version {to_ver} not found")

    a_lines = a_ver.content.splitlines(keepends=True)
    b_lines = b_ver.content.splitlines(keepends=True)

    diff_groups = []
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            diff_groups.append({"type": "equal",  "lines": a_lines[i1:i2]})
        elif tag == "replace":
            diff_groups.append({"type": "delete", "lines": a_lines[i1:i2]})
            diff_groups.append({"type": "insert", "lines": b_lines[j1:j2]})
        elif tag == "delete":
            diff_groups.append({"type": "delete", "lines": a_lines[i1:i2]})
        elif tag == "insert":
            diff_groups.append({"type": "insert", "lines": b_lines[j1:j2]})

    return diff_groups


# -----------------------------------------------------------------------------

async def search_pages(
    db: AsyncSession,
    query: str,
    namespace_name: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Full-text search across page titles and latest content."""
    max_ver_sub = (
        select(
            PageVersion.page_id,
            func.max(PageVersion.version).label("max_ver"),
        )
        .group_by(PageVersion.page_id)
        .subquery()
    )

    q = (
        select(Page, PageVersion, Namespace)
        .join(max_ver_sub, Page.id == max_ver_sub.c.page_id)
        .join(
            PageVersion,
            (PageVersion.page_id == Page.id) &
            (PageVersion.version == max_ver_sub.c.max_ver),
        )
        .join(Namespace, Namespace.id == Page.namespace_id)
        .where(
            Page.title.ilike(f"%{query}%") |
            PageVersion.content.ilike(f"%{query}%")
        )
        .order_by(Page.title)
        .offset(skip)
        .limit(limit)
    )

    if namespace_name:
        q = q.where(Namespace.name == namespace_name)

    result = await db.execute(q)
    rows = result.all()

    results = []
    for p, v, ns in rows:
        # Extract a snippet around the first match
        content = v.content
        idx = content.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 80)
            end   = min(len(content), idx + 160)
            snippet = "..." + content[start:end].replace("\n", " ") + "..."
        else:
            snippet = content[:160].replace("\n", " ") + "..."

        results.append({
            "namespace": ns.name,
            "title":     p.title,
            "slug":      p.slug,
            "snippet":   snippet,
            "updated_at": v.created_at,
        })

    return results


# -----------------------------------------------------------------------------

async def get_all_categories(
    db: AsyncSession,
    starts_with: str = "",
) -> list[dict]:
    """Return all categories declared across the wiki with their page counts.

    Each dict has: name, count.  Sorted case-insensitively by name.
    Optionally filter to names starting with *starts_with* (case-insensitive).
    """
    from app.services.renderer import extract_categories

    max_ver_sub = (
        select(PageVersion.page_id, func.max(PageVersion.version).label("max_ver"))
        .group_by(PageVersion.page_id)
        .subquery()
    )
    q = (
        select(PageVersion.content, PageVersion.format)
        .join(max_ver_sub,
              (PageVersion.page_id == max_ver_sub.c.page_id)
              & (PageVersion.version == max_ver_sub.c.max_ver))
        .where(PageVersion.content.ilike("%[[Category:%"))
    )
    rows = (await db.execute(q)).all()

    counts: dict[str, int] = {}
    for content, fmt in rows:
        for cat in extract_categories(content, fmt):
            key = cat.lower()
            # Store the first-seen casing as the canonical name
            if key not in counts:
                counts[key] = {"name": cat, "count": 0}
            counts[key]["count"] += 1

    results = list(counts.values())
    if starts_with:
        results = [r for r in results if r["name"].lower().startswith(starts_with.lower())]
    return sorted(results, key=lambda r: r["name"].lower())


async def get_pages_in_category(
    db: AsyncSession,
    category_name: str,
) -> list[dict]:
    """Return all pages whose latest version content contains [[Category:name]].

    Case-insensitive match.  Returns dicts with: namespace, title, slug,
    version, format, author, updated_at — sorted alphabetically by title.
    """
    import re as _re
    pattern = _re.compile(
        r"\[\[Category:" + _re.escape(category_name) + r"\]\]",
        _re.IGNORECASE,
    )

    max_ver_sub = (
        select(PageVersion.page_id, func.max(PageVersion.version).label("max_ver"))
        .group_by(PageVersion.page_id)
        .subquery()
    )
    q = (
        select(Page, PageVersion, Namespace, User)
        .join(max_ver_sub, Page.id == max_ver_sub.c.page_id)
        .join(
            PageVersion,
            (PageVersion.page_id == Page.id)
            & (PageVersion.version == max_ver_sub.c.max_ver),
        )
        .join(Namespace, Namespace.id == Page.namespace_id)
        .outerjoin(User, User.id == PageVersion.author_id)
        .order_by(Page.title)
    )
    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "namespace": ns.name,
            "title": p.title,
            "slug": p.slug,
            "version": v.version,
            "format": v.format,
            "author": u.username if u else "anonymous",
            "updated_at": v.created_at,
        }
        for p, v, ns, u in rows
        if pattern.search(v.content)
    ]


async def get_recent_changes(
    db: AsyncSession,
    limit: int = 50,
    namespace_name: Optional[str] = None,
) -> list[dict]:
    """Return the most recently edited pages (one row per page, latest version).

    Each dict has: namespace, title, slug, version, format, comment, author, updated_at.
    """
    max_ver_sub = (
        select(PageVersion.page_id, func.max(PageVersion.version).label("max_ver"))
        .group_by(PageVersion.page_id)
        .subquery()
    )
    q = (
        select(Page, PageVersion, Namespace, User)
        .join(max_ver_sub, Page.id == max_ver_sub.c.page_id)
        .join(
            PageVersion,
            (PageVersion.page_id == Page.id)
            & (PageVersion.version == max_ver_sub.c.max_ver),
        )
        .join(Namespace, Namespace.id == Page.namespace_id)
        .outerjoin(User, User.id == PageVersion.author_id)
        .order_by(PageVersion.created_at.desc())
        .limit(limit)
    )
    if namespace_name:
        q = q.where(Namespace.name == namespace_name)

    result = await db.execute(q)
    return [
        {
            "namespace": ns.name,
            "title": p.title,
            "slug": p.slug,
            "version": v.version,
            "format": v.format,
            "comment": v.comment,
            "author": u.username if u else "anonymous",
            "updated_at": v.created_at,
        }
        for p, v, ns, u in result.all()
    ]


async def _reload_page_version(
    db: AsyncSession, page_id: str, version_num: int
) -> tuple[Page, PageVersion]:
    """Reload page and specific version with all relationships eagerly loaded."""
    db.expire_all()
    result = await db.execute(
        select(Page)
        .where(Page.id == page_id)
        .options(
            selectinload(Page.versions).selectinload(PageVersion.author),
            selectinload(Page.attachments),
        )
    )
    page = result.scalar_one()
    matches = [v for v in page.versions if v.version == version_num]
    if not matches:
        raise RuntimeError(f"Version {version_num} not found after flush")
    return page, matches[0]


# -----------------------------------------------------------------------------
