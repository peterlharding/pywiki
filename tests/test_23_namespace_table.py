#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for the namespace index page table layout."""
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


def test_selection_column_overrides_first_column_width():
    css = (Path(__file__).parent.parent / "app/static/css/wiki.css").read_text()
    first_col = css.index(".wiki-table td:first-child, .wiki-table th:first-child { min-width: 180px; width: 40%; }")
    select_col = css.index(".wiki-table th.col-select, .wiki-table td.col-select {")
    # Same specificity, so the selection rule must come later to win
    assert select_col > first_col
    assert "width: 1%;" in css[select_col:select_col + 120]


# -----------------------------------------------------------------------------
