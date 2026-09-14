#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for configurable attachment file types: upload rules, serving, rendering."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import update

from app.core.config import get_settings
from app.core.filetypes import (
    DEFAULT_ATTACHMENT_EXTENSIONS,
    content_type_for,
    parse_extension_list,
    sanitize_filename,
)
from app.models import User
from app.services.renderer import render
from tests.conftest import auth_headers, cookie_auth, register_user

NS = "FILES"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# -----------------------------------------------------------------------------
# Fixtures / helpers
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _attachment_settings(tmp_path, monkeypatch):
    """Isolated attachment storage and the default extension list for every test."""
    monkeypatch.setenv("ATTACHMENT_ROOT", str(tmp_path / "attachments"))
    monkeypatch.setenv("ATTACHMENT_EXTENSIONS", ",".join(DEFAULT_ATTACHMENT_EXTENSIONS))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_extensions(monkeypatch, value: str) -> None:
    monkeypatch.setenv("ATTACHMENT_EXTENSIONS", value)
    get_settings.cache_clear()


async def _setup(client, db_session, username="filesuser", content="# Files", fmt="markdown"):
    await register_user(client, username, f"{username}@example.com")
    await db_session.execute(update(User).where(User.username == username).values(is_admin=True))
    await db_session.commit()
    headers = await auth_headers(client, username)
    resp = await client.post("/api/v1/namespaces", json={"name": NS, "description": "", "default_format": fmt}, headers=headers)
    assert resp.status_code == 201, resp.text
    resp = await client.post(f"/api/v1/namespaces/{NS}/pages", json={"title": "Doc Page", "content": content, "format": fmt}, headers=headers)
    assert resp.status_code == 201, resp.text
    return headers


async def _upload(client, headers, filename, data=b"data", content_type="application/octet-stream", slug="doc-page"):
    return await client.post(
        f"/api/v1/namespaces/{NS}/pages/{slug}/attachments",
        files={"file": (filename, data, content_type)},
        headers=headers,
    )


# =============================================================================
# filetypes helpers and configuration
# =============================================================================

def test_parse_extension_list_accepts_commas_spaces_dots_and_case():
    assert parse_extension_list(" pdf, .DOCX  txt,,md ") == {"pdf", "docx", "txt", "md"}


def test_prohibited_extensions_are_dropped_from_configuration(monkeypatch):
    _set_extensions(monkeypatch, "pdf,html,exe,zip")
    settings = get_settings()
    assert settings.allowed_attachment_extensions == {"pdf", "zip"}
    assert settings.ignored_attachment_extensions == {"html", "exe"}


def test_default_extensions_include_requested_document_types():
    allowed = get_settings().allowed_attachment_extensions
    assert {"docx", "xlsx", "txt", "pdf", "md", "png", "jpg"} <= allowed


def test_sanitize_filename_strips_directories_and_unsafe_characters():
    assert sanitize_filename("../../etc/pass<wd>.txt") == "pass_wd_.txt"
    assert sanitize_filename("C:\\Users\\me\\Q3 Budget.xlsx") == "Q3 Budget.xlsx"


def test_content_type_is_derived_from_extension():
    assert content_type_for("Notes.DOCX") == DOCX
    assert content_type_for("readme.md") == "text/plain; charset=utf-8"
    assert content_type_for("blob.unknownext") == "application/octet-stream"


# =============================================================================
# Upload API
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["report.pdf", "Notes.docx", "Budget.xlsx", "notes.txt", "README.md", "SCAN.PDF"])
async def test_upload_accepts_document_types(client, db_session, filename):
    headers = await _setup(client, db_session)
    resp = await _upload(client, headers, filename)
    assert resp.status_code == 201, resp.text
    assert resp.json()["filename"] == filename


@pytest.mark.asyncio
async def test_upload_ignores_client_content_type(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _upload(client, headers, "Notes.docx", content_type="text/html")
    assert resp.status_code == 201
    assert resp.json()["content_type"] == DOCX


@pytest.mark.asyncio
async def test_upload_rejects_prohibited_type(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _upload(client, headers, "setup.exe")
    assert resp.status_code == 415
    assert "security" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_type_not_in_allowed_list(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _upload(client, headers, "archive.zip")
    assert resp.status_code == 415
    detail = resp.json()["detail"]
    assert "'.zip' files are not allowed" in detail
    assert "docx" in detail and "pdf" in detail


@pytest.mark.asyncio
async def test_upload_rejects_file_without_extension(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _upload(client, headers, "Makefile")
    assert resp.status_code == 415
    assert "extension" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_rejected_upload_creates_no_attachment(client, db_session):
    headers = await _setup(client, db_session)
    await _upload(client, headers, "payload.html", b"<script>alert(1)</script>")
    listing = await client.get(f"/api/v1/namespaces/{NS}/pages/doc-page/attachments")
    assert listing.json() == []


@pytest.mark.asyncio
async def test_configured_extensions_are_enforced(client, db_session, monkeypatch):
    headers = await _setup(client, db_session)
    _set_extensions(monkeypatch, "pdf zip html")
    assert (await _upload(client, headers, "archive.zip")).status_code == 201
    assert (await _upload(client, headers, "photo.png")).status_code == 415
    # Prohibited types stay blocked even when an admin lists them
    assert (await _upload(client, headers, "page.html")).status_code == 415


# =============================================================================
# Serving
# =============================================================================

async def _served(client, headers, filename, data=b"data"):
    att = (await _upload(client, headers, filename, data)).json()
    return await client.get(att["url"].replace("http://localhost:8000", ""))


@pytest.mark.asyncio
async def test_pdf_is_served_inline_without_sandbox(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _served(client, headers, "report.pdf", b"%PDF-1.4")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"].startswith("inline")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in resp.headers


@pytest.mark.asyncio
async def test_markdown_is_served_inline_as_plain_text(client, db_session):
    headers = await _setup(client, db_session)
    resp = await _served(client, headers, "README.md", b"# Hi")
    assert resp.headers["content-type"] == "text/plain; charset=utf-8"
    assert resp.headers["content-disposition"].startswith("inline")
    assert "sandbox" in resp.headers["content-security-policy"]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename", ["Notes.docx", "diagram.svg"])
async def test_active_or_office_files_are_downloads(client, db_session, filename):
    headers = await _setup(client, db_session)
    resp = await _served(client, headers, filename)
    assert resp.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in resp.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_filename_with_spaces_has_a_working_url(client, db_session):
    headers = await _setup(client, db_session)
    att = (await _upload(client, headers, "Q3 Budget.xlsx")).json()
    assert att["url"].endswith("/Q3%20Budget.xlsx")
    resp = await client.get(att["url"].replace("http://localhost:8000", ""))
    assert resp.status_code == 200


# =============================================================================
# Rendering
# =============================================================================

ATT = {"report.pdf": "/api/v1/attachments/1/report.pdf", "photo.png": "/api/v1/attachments/2/photo.png"}


def test_markdown_attachment_link_resolves():
    html = render("[Q3 report](attachment:report.pdf)", "markdown", attachments=ATT)
    assert '<a href="/api/v1/attachments/1/report.pdf">Q3 report</a>' in html


def test_markdown_missing_attachment_link_offers_upload():
    html = render("[Spec](attachment:spec.pdf)", "markdown")
    assert 'href="/special/upload?filename=spec.pdf"' in html
    assert 'class="missing-file"' in html


def test_wikitext_media_link():
    html = render("[[Media:report.pdf]] and [[Media:report.pdf|The report]]", "wikitext", attachments=ATT)
    assert '<a href="/api/v1/attachments/1/report.pdf" class="wiki-file">report.pdf</a>' in html
    assert '<a href="/api/v1/attachments/1/report.pdf" class="wiki-file">The report</a>' in html
    assert "wikilink" not in html


def test_wikitext_file_syntax_links_non_images():
    html = render("[[File:report.pdf|Quarterly]] [[File:photo.png]]", "wikitext", attachments=ATT)
    assert '<a href="/api/v1/attachments/1/report.pdf" class="wiki-file">Quarterly</a>' in html
    assert '<img src="/api/v1/attachments/2/photo.png"' in html


def test_wikitext_missing_media_offers_upload():
    html = render("[[Media:minutes.pdf]]", "wikitext")
    assert 'href="/special/upload?filename=minutes.pdf"' in html


def test_same_site_links_do_not_open_new_tabs():
    base = "https://wiki.example.com"
    html = render("[[Other Page]] [ext](https://example.org)", "markdown", base_url=base)
    assert f'<a href="{base}/wiki/Main/other-page">' in html
    assert '<a href="https://example.org" target="_blank" rel="noopener noreferrer">' in html


# =============================================================================
# UI: page view, editor, Special:Upload, cache, ZIP import
# =============================================================================

@pytest.mark.asyncio
async def test_page_link_resolves_after_upload(client, db_session):
    """Cached HTML from before an upload must not keep showing the red upload link."""
    headers = await _setup(client, db_session, content="See [the report](attachment:report.pdf)")
    cookies = await cookie_auth(client, "filesuser")
    before = await client.get(f"/wiki/{NS}/doc-page", headers=cookies)
    assert 'class="missing-file"' in before.text

    att = (await _upload(client, headers, "report.pdf")).json()
    after = await client.get(f"/wiki/{NS}/doc-page", headers=cookies)
    assert 'class="missing-file"' not in after.text
    assert f'href="{att["url"]}">the report</a>' in after.text

    await client.delete(f"/api/v1/namespaces/{NS}/pages/doc-page/attachments/report.pdf", headers=headers)
    gone = await client.get(f"/wiki/{NS}/doc-page", headers=cookies)
    assert 'class="missing-file"' in gone.text


@pytest.mark.asyncio
async def test_page_view_lists_files_and_upload_link(client, db_session):
    headers = await _setup(client, db_session)
    await _upload(client, headers, "Notes.docx", b"x" * 2048)
    await _upload(client, headers, "photo.png", b"\x89PNG")
    cookies = await cookie_auth(client, "filesuser")
    resp = await client.get(f"/wiki/{NS}/doc-page", headers=cookies)
    assert "Files (<span data-attachment-count>1</span>)" in resp.text
    assert "Images (<span data-attachment-count>1</span>)" in resp.text
    assert "Notes.docx" in resp.text and "2.0 KB" in resp.text
    assert f'href="/special/upload?namespace={NS}&amp;page=doc-page' in resp.text


@pytest.mark.asyncio
async def test_editor_accepts_configured_types(client, db_session):
    await _setup(client, db_session)
    cookies = await cookie_auth(client, "filesuser")
    resp = await client.get(f"/wiki/{NS}/doc-page/edit", headers=cookies)
    assert 'accept=".bmp,.docx,' in resp.text
    assert "Drop files here" in resp.text
    assert 'accept="image/*"' not in resp.text


@pytest.mark.asyncio
async def test_special_upload_rejects_disallowed_type(client, db_session):
    await _setup(client, db_session)
    cookies = await cookie_auth(client, "filesuser")
    resp = await client.post(
        "/special/upload",
        data={"namespace_name": NS, "slug": "doc-page"},
        files={"file": ("tool.exe", b"MZ", "application/octet-stream")},
        headers=cookies,
    )
    assert resp.status_code == 200
    assert "not allowed for security reasons" in resp.text
    assert 'class="alert alert-error"' in resp.text


@pytest.mark.asyncio
async def test_special_upload_shows_link_syntax_for_documents(client, db_session):
    await _setup(client, db_session)
    cookies = await cookie_auth(client, "filesuser")
    resp = await client.post(
        "/special/upload",
        data={"namespace_name": NS, "slug": "doc-page"},
        files={"file": ("Notes.docx", b"PK", DOCX)},
        headers=cookies,
    )
    assert 'class="alert alert-success"' in resp.text
    assert "[[Media:Notes.docx]]" in resp.text
    assert "Allowed types:" in resp.text


@pytest.mark.asyncio
async def test_zip_import_skips_disallowed_attachments(client, db_session):
    headers = await _setup(client, db_session)
    cookies = await cookie_auth(client, "filesuser")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{NS}/doc-page.md", "# Files")
        zf.writestr(f"{NS}/doc-page/attachments/notes.txt", b"notes")
        zf.writestr(f"{NS}/doc-page/attachments/virus.exe", b"MZ")
    resp = await client.post(
        f"/wiki/{NS}/import",
        files={"zipfile": ("import.zip", buf.getvalue(), "application/zip")},
        headers=cookies,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "att_ok=1+0" in resp.headers["location"]
    assert "att_skipped=1" in resp.headers["location"]

    listing = await client.get(f"/api/v1/namespaces/{NS}/pages/doc-page/attachments", headers=headers)
    assert [a["filename"] for a in listing.json()] == ["notes.txt"]

    banner = await client.get(resp.headers["location"], headers=cookies)
    assert "<strong>1</strong> attachment(s) skipped" in banner.text


# -----------------------------------------------------------------------------
