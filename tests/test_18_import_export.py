#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for selective export and ZIP import."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import update

from app.models import User
from tests.conftest import auth_headers, cookie_auth, register_user


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _setup(client, db_session, username, ns_name, fmt="markdown"):
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(
        update(User).where(User.username == username).values(is_admin=True)
    )
    await db_session.commit()
    headers = await auth_headers(client, username)
    await client.post("/api/v1/namespaces", json={
        "name": ns_name, "description": "", "default_format": fmt,
    }, headers=headers)
    return headers


async def _create_page(client, ns, title, content, fmt, headers):
    resp = await client.post(f"/api/v1/namespaces/{ns}/pages", json={
        "title": title, "content": content, "format": fmt, "comment": "test",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_zip(*entries):
    """Return a bytes ZIP containing (path, content) entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path, content in entries:
            zf.writestr(path, content)
    buf.seek(0)
    return buf.read()


# =============================================================================
# Full export (GET /wiki/{ns}/export)
# =============================================================================

@pytest.mark.asyncio
async def test_full_export_returns_zip(client, db_session):
    """GET /wiki/{ns}/export downloads a ZIP containing all pages."""
    headers = await _setup(client, db_session, "expuser1", "EXPNS1")
    cookies = await cookie_auth(client, "expuser1")
    await _create_page(client, "EXPNS1", "Alpha", "# Alpha", "markdown", headers)
    await _create_page(client, "EXPNS1", "Beta",  "# Beta",  "markdown", headers)

    resp = await client.get("/wiki/EXPNS1/export", headers=cookies,
                            follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("alpha" in n for n in names)
    assert any("beta" in n for n in names)


@pytest.mark.asyncio
async def test_full_export_requires_login(client, db_session):
    """GET /wiki/{ns}/export redirects to /login when not authenticated."""
    await _setup(client, db_session, "expuser2", "EXPNS2")
    resp = await client.get("/wiki/EXPNS2/export", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


# =============================================================================
# Selective export (POST /wiki/{ns}/export/selected)
# =============================================================================

@pytest.mark.asyncio
async def test_selective_export_subset(client, db_session):
    """POST /wiki/{ns}/export/selected returns only checked pages."""
    headers = await _setup(client, db_session, "seluser1", "SELNS1")
    cookies = await cookie_auth(client, "seluser1")
    await _create_page(client, "SELNS1", "Page One",   "one",   "markdown", headers)
    await _create_page(client, "SELNS1", "Page Two",   "two",   "markdown", headers)
    await _create_page(client, "SELNS1", "Page Three", "three", "markdown", headers)

    resp = await client.post(
        "/wiki/SELNS1/export/selected",
        data={"slugs": ["page-one", "page-three"]},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("page-one" in n for n in names)
    assert any("page-three" in n for n in names)
    assert not any("page-two" in n for n in names)


@pytest.mark.asyncio
async def test_selective_export_empty_redirects(client, db_session):
    """POST /wiki/{ns}/export/selected with no selection redirects back."""
    headers = await _setup(client, db_session, "seluser2", "SELNS2")
    cookies = await cookie_auth(client, "seluser2")
    await _create_page(client, "SELNS2", "Solo", "content", "markdown", headers)

    resp = await client.post(
        "/wiki/SELNS2/export/selected",
        data={},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)


# =============================================================================
# Cross-namespace export (POST /special/export/selected)
# =============================================================================

@pytest.mark.asyncio
async def test_cross_ns_export(client, db_session):
    """POST /special/export/selected merges pages from two namespaces into one ZIP."""
    headers = await _setup(client, db_session, "crossuser1", "CROSSNS1")
    cookies = await cookie_auth(client, "crossuser1")
    await client.post("/api/v1/namespaces", json={
        "name": "CROSSNS2", "description": "", "default_format": "markdown",
    }, headers=headers)
    await _create_page(client, "CROSSNS1", "Alpha", "ns1 content", "markdown", headers)
    await _create_page(client, "CROSSNS2", "Beta",  "ns2 content", "markdown", headers)

    resp = await client.post(
        "/special/export/selected",
        data={"pages": ["CROSSNS1:alpha", "CROSSNS2:beta"]},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert any("CROSSNS1" in n and "alpha" in n for n in names)
    assert any("CROSSNS2" in n and "beta" in n for n in names)


# =============================================================================
# Import (POST /wiki/{ns}/import)
# =============================================================================

@pytest.mark.asyncio
async def test_import_creates_new_pages(client, db_session):
    """ZIP import creates pages that don't exist yet."""
    headers = await _setup(client, db_session, "impuser1", "IMPNS1")
    cookies = await cookie_auth(client, "impuser1")

    zip_bytes = _make_zip(
        ("IMPNS1/my-page.md",  "# My Page\nHello import"),
        ("IMPNS1/second-page.rst", "Second Page\n===========\n\nRST content"),
    )
    resp = await client.post(
        "/wiki/IMPNS1/import",
        files={"zipfile": ("export.zip", zip_bytes, "application/zip")},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "import_ok=2+0" in resp.headers["location"]

    # Verify pages exist
    r1 = await client.get("/wiki/IMPNS1/my-page", headers=cookies)
    assert r1.status_code == 200
    assert "Hello import" in r1.text

    r2 = await client.get("/wiki/IMPNS1/second-page", headers=cookies)
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_import_updates_existing_page(client, db_session):
    """ZIP import adds a new version to an existing page."""
    headers = await _setup(client, db_session, "impuser2", "IMPNS2")
    cookies = await cookie_auth(client, "impuser2")
    await _create_page(client, "IMPNS2", "Existing", "original content", "markdown", headers)

    zip_bytes = _make_zip(("IMPNS2/existing.md", "updated content"))
    resp = await client.post(
        "/wiki/IMPNS2/import",
        files={"zipfile": ("update.zip", zip_bytes, "application/zip")},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "import_ok=0+1" in resp.headers["location"]

    page_resp = await client.get("/wiki/IMPNS2/existing", headers=cookies)
    assert "updated content" in page_resp.text


@pytest.mark.asyncio
async def test_import_attachments(client, db_session):
    """Attachments in the ZIP are imported and linked to their page."""
    headers = await _setup(client, db_session, "impuser3", "IMPNS3")
    cookies = await cookie_auth(client, "impuser3")

    png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16  # minimal PNG-ish bytes
    zip_bytes = _make_zip(
        ("IMPNS3/my-page.md",                        "# My Page"),
        ("IMPNS3/my-page/attachments/diagram.png",   png_data),
        ("IMPNS3/my-page/attachments/notes.txt",     b"some notes"),
    )
    resp = await client.post(
        "/wiki/IMPNS3/import",
        files={"zipfile": ("att.zip", zip_bytes, "application/zip")},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    location = resp.headers["location"]
    assert "import_ok=1+0" in location
    assert "att_ok=2+0" in location

    # Attachments should be retrievable via the API
    att_resp = await client.get("/api/v1/namespaces/IMPNS3/pages/my-page/attachments",
                                headers=headers)
    assert att_resp.status_code == 200
    filenames = [a["filename"] for a in att_resp.json()]
    assert "diagram.png" in filenames
    assert "notes.txt" in filenames


@pytest.mark.asyncio
async def test_import_attachment_update(client, db_session):
    """Re-importing a ZIP updates existing attachment content."""
    headers = await _setup(client, db_session, "impuser3b", "IMPNS3B")
    cookies = await cookie_auth(client, "impuser3b")

    zip_v1 = _make_zip(
        ("IMPNS3B/page-a.md",                    "# Page A"),
        ("IMPNS3B/page-a/attachments/data.txt",  b"version 1"),
    )
    await client.post("/wiki/IMPNS3B/import",
                      files={"zipfile": ("v1.zip", zip_v1, "application/zip")},
                      headers=cookies, follow_redirects=False)

    zip_v2 = _make_zip(
        ("IMPNS3B/page-a.md",                    "# Page A v2"),
        ("IMPNS3B/page-a/attachments/data.txt",  b"version 2"),
    )
    resp = await client.post("/wiki/IMPNS3B/import",
                             files={"zipfile": ("v2.zip", zip_v2, "application/zip")},
                             headers=cookies, follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "att_ok=0+1" in resp.headers["location"]


@pytest.mark.asyncio
async def test_import_rejects_bad_zip(client, db_session):
    """Uploading a non-ZIP file returns an error response."""
    headers = await _setup(client, db_session, "impuser4", "IMPNS4")
    cookies = await cookie_auth(client, "impuser4")

    resp = await client.post(
        "/wiki/IMPNS4/import",
        files={"zipfile": ("bad.zip", b"not a zip file", "application/zip")},
        headers=cookies,
    )
    assert resp.status_code == 400
    assert "not a valid ZIP" in resp.text


@pytest.mark.asyncio
async def test_import_requires_login(client, db_session):
    """POST /wiki/{ns}/import redirects to login when unauthenticated."""
    await _setup(client, db_session, "impuser5", "IMPNS5")
    zip_bytes = _make_zip(("IMPNS5/page.md", "content"))
    resp = await client.post(
        "/wiki/IMPNS5/import",
        files={"zipfile": ("x.zip", zip_bytes, "application/zip")},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]
