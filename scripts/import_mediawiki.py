#!/usr/bin/env python
"""
Import pages from a MediaWiki XML export into PyWiki.

Usage:
    .venv/bin/python scripts/import_mediawiki.py <export.xml> [options]

Options:
    --namespace NS       Target pywiki namespace (default: Main)
    --skip-namespaces    Comma-separated MW namespace numbers to skip
                         (default: 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
                          i.e. skip Talk, User, MediaWiki, Template, Help,
                          Category, File and their Talk counterparts)
    --include-talk       Also import Talk pages (mapped to a 'Talk' namespace)
    --overwrite          Overwrite existing pages (default: skip duplicates)
    --dry-run            Parse and report without writing to the database
    --limit N            Only import the first N pages (useful for testing)

MediaWiki namespace numbers:
    0  = Main (articles)
    1  = Talk
    2  = User
    4  = Wikipedia/Project
    6  = File
    8  = MediaWiki
    10 = Template
    12 = Help
    14 = Category

Example:
    .venv/bin/python scripts/import_mediawiki.py ~/export.xml --dry-run --limit 10
    .venv/bin/python scripts/import_mediawiki.py ~/export.xml --namespace Main
    .venv/bin/python scripts/import_mediawiki.py ~/export.xml --namespace Main --overwrite
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure app package is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory, create_all_tables
from app.models.models import Namespace, Page, PageVersion
from app.services.pages import slugify

# ── MediaWiki XML namespace URI ───────────────────────────────────────────────
MW_NS = "http://www.mediawiki.org/xml/export-0.11/"

# Default MW namespace numbers to skip (non-article namespaces)
DEFAULT_SKIP_NS = {1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class MWPage:
    title: str          # Full MW title (may include "Namespace:Title" prefix)
    mw_ns: int          # MediaWiki namespace number
    local_title: str    # Title without the namespace prefix
    content: str        # Wikitext content of the latest revision
    comment: str        # Edit summary of latest revision
    timestamp: Optional[datetime]
    contributor: str    # Username or IP of latest editor


# ── XML parsing ───────────────────────────────────────────────────────────────

def _tag(name: str) -> str:
    return f"{{{MW_NS}}}{name}"


def parse_export(xml_path: Path) -> list[MWPage]:
    """Parse a MediaWiki XML export and return all pages with their latest revision."""
    pages: list[MWPage] = []

    # Use iterparse to handle large exports without loading the whole file into memory
    context = ET.iterparse(str(xml_path), events=("end",))
    for event, elem in context:
        if elem.tag != _tag("page"):
            continue

        title_el = elem.find(_tag("title"))
        ns_el    = elem.find(_tag("ns"))
        if title_el is None or ns_el is None:
            elem.clear()
            continue

        full_title = (title_el.text or "").strip()
        mw_ns = int(ns_el.text or "0")

        # Strip the namespace prefix from the title (e.g. "Help:Foo" -> "Foo")
        local_title = full_title
        if ":" in full_title and mw_ns != 0:
            local_title = full_title.split(":", 1)[1].strip()

        # Take the latest (last) revision
        revisions = elem.findall(_tag("revision"))
        if not revisions:
            elem.clear()
            continue
        rev = revisions[-1]

        text_el    = rev.find(_tag("text"))
        comment_el = rev.find(_tag("comment"))
        ts_el      = rev.find(_tag("timestamp"))
        contrib_el = rev.find(_tag("contributor"))

        content   = (text_el.text or "") if text_el is not None else ""
        comment   = (comment_el.text or "") if comment_el is not None else ""
        timestamp = None
        if ts_el is not None and ts_el.text:
            try:
                timestamp = datetime.fromisoformat(ts_el.text.replace("Z", "+00:00"))
            except ValueError:
                pass

        contributor = "anonymous"
        if contrib_el is not None:
            uname = contrib_el.find(_tag("username"))
            ip    = contrib_el.find(_tag("ip"))
            if uname is not None and uname.text:
                contributor = uname.text
            elif ip is not None and ip.text:
                contributor = ip.text

        pages.append(MWPage(
            title=full_title,
            mw_ns=mw_ns,
            local_title=local_title,
            content=content,
            comment=comment,
            timestamp=timestamp,
            contributor=contributor,
        ))
        elem.clear()

    return pages


# ── Database helpers ──────────────────────────────────────────────────────────

async def _get_or_create_namespace(db: AsyncSession, name: str) -> Namespace:
    result = await db.execute(select(Namespace).where(Namespace.name == name))
    ns = result.scalar_one_or_none()
    if ns is None:
        ns = Namespace(name=name, description=f"Imported from MediaWiki", default_format="wikitext")
        db.add(ns)
        await db.flush()
        print(f"  [+] Created namespace '{name}'")
    return ns


async def _page_exists(db: AsyncSession, ns_id: str, slug: str) -> bool:
    result = await db.execute(
        select(Page.id).where(Page.namespace_id == ns_id, Page.slug == slug)
    )
    return result.scalar_one_or_none() is not None


async def _get_page(db: AsyncSession, ns_id: str, slug: str) -> Optional[Page]:
    result = await db.execute(
        select(Page).where(Page.namespace_id == ns_id, Page.slug == slug)
    )
    return result.scalar_one_or_none()


async def _next_version(db: AsyncSession, page_id: str) -> int:
    result = await db.execute(
        select(PageVersion.version)
        .where(PageVersion.page_id == page_id)
        .order_by(PageVersion.version.desc())
        .limit(1)
    )
    current = result.scalar_one_or_none()
    return (current or 0) + 1


# ── Import logic ──────────────────────────────────────────────────────────────

async def import_pages(
    xml_path: Path,
    target_namespace: str,
    skip_mw_ns: set[int],
    include_talk: bool,
    overwrite: bool,
    dry_run: bool,
    limit: Optional[int],
) -> None:
    print(f"Parsing {xml_path} …")
    all_pages = parse_export(xml_path)
    print(f"Found {len(all_pages)} pages in export.")

    # Filter by MW namespace
    filtered: list[MWPage] = []
    for p in all_pages:
        if p.mw_ns in skip_mw_ns:
            continue
        if p.mw_ns == 1 and not include_talk:
            continue
        filtered.append(p)

    if limit:
        filtered = filtered[:limit]

    print(f"After filtering: {len(filtered)} pages to import.")

    if dry_run:
        print("\n[DRY RUN] Pages that would be imported:")
        for p in filtered:
            ns_label = target_namespace if p.mw_ns == 0 else f"Talk" if p.mw_ns == 1 else target_namespace
            print(f"  [{ns_label}] {p.local_title!r}  (contributor: {p.contributor})")
        print(f"\n[DRY RUN] {len(filtered)} pages — no changes written.")
        return

    # Ensure tables exist (safe no-op if already present)
    await create_all_tables()

    counts = {"created": 0, "updated": 0, "skipped": 0, "error": 0}

    async with get_session_factory()() as db:
        async with db.begin():
            # Pre-fetch/create namespaces
            ns_cache: dict[str, Namespace] = {}

            for p in filtered:
                # Determine target pywiki namespace
                if p.mw_ns == 1 and include_talk:
                    ns_name = "Talk"
                else:
                    ns_name = target_namespace

                if ns_name not in ns_cache:
                    ns_cache[ns_name] = await _get_or_create_namespace(db, ns_name)
                ns = ns_cache[ns_name]

                title = p.local_title
                slug  = slugify(title)

                if not slug:
                    print(f"  [!] Skipping '{title}' — slugify produced empty string")
                    counts["error"] += 1
                    continue

                existing = await _get_page(db, ns.id, slug)

                if existing and not overwrite:
                    counts["skipped"] += 1
                    continue

                try:
                    if existing:
                        # Update: add a new version
                        ver_num = await _next_version(db, existing.id)
                        version = PageVersion(
                            page_id=existing.id,
                            version=ver_num,
                            content=p.content,
                            format="wikitext",
                            author_id=None,
                            comment=p.comment or "Imported from MediaWiki",
                        )
                        db.add(version)
                        counts["updated"] += 1
                    else:
                        # Create new page + version
                        page = Page(
                            namespace_id=ns.id,
                            title=title,
                            slug=slug,
                            created_by=None,
                        )
                        db.add(page)
                        await db.flush()

                        version = PageVersion(
                            page_id=page.id,
                            version=1,
                            content=p.content,
                            format="wikitext",
                            author_id=None,
                            comment=p.comment or "Imported from MediaWiki",
                        )
                        db.add(version)
                        counts["created"] += 1

                except Exception as exc:
                    print(f"  [!] Error importing '{title}': {exc}")
                    counts["error"] += 1

    print(
        f"\nImport complete: "
        f"{counts['created']} created, "
        f"{counts['updated']} updated, "
        f"{counts['skipped']} skipped (already exist), "
        f"{counts['error']} errors."
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import pages from a MediaWiki XML export into PyWiki.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("xml_file", help="Path to the MediaWiki XML export file")
    parser.add_argument("--namespace", default="Main", metavar="NS",
                        help="Target pywiki namespace (default: Main)")
    parser.add_argument("--skip-namespaces", default="", metavar="N,N,...",
                        help="Comma-separated extra MW namespace numbers to skip")
    parser.add_argument("--include-talk", action="store_true",
                        help="Also import Talk pages into a 'Talk' namespace")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing pages (adds a new version)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report without writing to the database")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Only import the first N pages")
    args = parser.parse_args()

    xml_path = Path(args.xml_file).expanduser().resolve()
    if not xml_path.exists():
        print(f"Error: file not found: {xml_path}", file=sys.stderr)
        sys.exit(1)

    skip_ns = set(DEFAULT_SKIP_NS)
    if args.skip_namespaces:
        for n in args.skip_namespaces.split(","):
            n = n.strip()
            if n.isdigit():
                skip_ns.add(int(n))

    asyncio.run(import_pages(
        xml_path=xml_path,
        target_namespace=args.namespace,
        skip_mw_ns=skip_ns,
        include_talk=args.include_talk,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
