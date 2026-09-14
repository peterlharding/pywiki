#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for table layout: selection columns, content-sized columns, label/value tables."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import auth_headers, register_user

# -----------------------------------------------------------------------------

async def _namespace_page(client) -> str:
    await register_user(client, "tableuser", "tableuser@example.com")
    headers = await auth_headers(client, "tableuser")
    await client.post("/api/v1/namespaces", json={"name": "TBL", "description": "", "default_format": "markdown"}, headers=headers)
    await client.post("/api/v1/namespaces/TBL/pages", json={"title": "A Fairly Long Page Title", "content": "x", "format": "markdown"}, headers=headers)
    resp = await client.get("/wiki/TBL")
    assert resp.status_code == 200
    return resp.text


@pytest.mark.asyncio
async def test_checkbox_column_is_marked_as_selection_column(client):
    html = await _namespace_page(client)
    assert '<th class="col-select"><input type="checkbox" id="select-all-ns"' in html
    assert '<td class="col-select"><input type="checkbox" name="slugs" value="a-fairly-long-page-title"' in html
    assert '<th class="col-title">Title</th>' in html
    # The old inline width did nothing against the stylesheet's 40% first-column rule
    assert 'style="width:2rem;"' not in html


@pytest.mark.asyncio
async def test_row_checkboxes_have_accessible_labels(client):
    html = await _namespace_page(client)
    assert 'aria-label="Select all pages"' in html
    assert 'aria-label="Select A Fairly Long Page Title"' in html


@pytest.mark.asyncio
async def test_table_scrolls_inside_its_own_container(client):
    html = await _namespace_page(client)
    assert re.search(r'<div class="table-scroll">\s*<table class="wiki-table">', html)


def test_tables_size_columns_to_content():
    css = (Path(__file__).parent.parent / "app/static/css/wiki.css").read_text()
    # A blanket 40% first column squeezed tables whose first column is a control
    assert ".wiki-table td:first-child, .wiki-table th:first-child" not in css
    select_col = css.index(".wiki-table th.col-select, .wiki-table td.col-select {")
    assert "width: 1%;" in css[select_col:select_col + 120]
    assert ".wiki-table.kv-table td:first-child { width: 40%; }" in css


@pytest.mark.asyncio
async def test_history_compare_radios_are_selection_columns(client):
    await register_user(client, "histuser", "histuser@example.com")
    headers = await auth_headers(client, "histuser")
    await client.post("/api/v1/namespaces", json={"name": "HIST", "description": "", "default_format": "markdown"}, headers=headers)
    await client.post("/api/v1/namespaces/HIST/pages", json={"title": "Changing", "content": "v1", "format": "markdown"}, headers=headers)
    await client.put("/api/v1/namespaces/HIST/pages/changing", json={"content": "v2", "format": "markdown", "comment": "second"}, headers=headers)
    html = (await client.get("/wiki/HIST/changing/history")).text
    assert html.count('<td class="col-select"><input type="radio" name="from_ver"') == 2
    assert html.count('<td class="col-select"><input type="radio" name="to_ver"') == 2
    assert 'aria-label="Compare from version 2"' in html


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/special/health", "/special/status"])
async def test_status_pages_have_no_stray_markdown_rules(client, path):
    html = (await client.get(path)).text
    assert "\n---\n" not in html
    assert 'class="wiki-table kv-table"' in html


# -----------------------------------------------------------------------------
