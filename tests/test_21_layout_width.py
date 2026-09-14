#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""Tests for the LAYOUT_MAX_WIDTH setting and the layout width toggle markup."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _layout_default(monkeypatch):
    monkeypatch.setenv("LAYOUT_MAX_WIDTH", "auto")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _use_width(monkeypatch, value: str) -> None:
    monkeypatch.setenv("LAYOUT_MAX_WIDTH", value)
    get_settings.cache_clear()


# =============================================================================
# Setting
# =============================================================================

def test_layout_max_width_defaults_to_auto(monkeypatch):
    monkeypatch.delenv("LAYOUT_MAX_WIDTH")
    assert Settings(_env_file=None).layout_max_width == "auto"


@pytest.mark.parametrize(("value", "expected"), [
    ("auto", "auto"),
    ("FULL", "full"),
    (" 1600 ", "1600px"),
    ("1920px", "1920px"),
    ("100rem", "100rem"),
    ("90%", "90%"),
])
def test_layout_max_width_accepts_keywords_and_css_lengths(value, expected):
    assert Settings(layout_max_width=value).layout_max_width == expected


@pytest.mark.parametrize("value", ["wide", "1600pt", "-5px", "100%; } body { display:none"])
def test_layout_max_width_rejects_other_values(value):
    with pytest.raises(ValidationError, match="LAYOUT_MAX_WIDTH"):
        Settings(layout_max_width=value)


# =============================================================================
# Page markup
# =============================================================================

@pytest.mark.asyncio
async def test_pages_carry_configured_width_and_toggle(client):
    resp = await client.get("/")
    assert '<html lang="en" id="html-root" data-layout-width="auto">' in resp.text
    assert 'id="width-toggle"' in resp.text
    assert "limitWidth" in resp.text


@pytest.mark.asyncio
async def test_configured_width_reaches_the_page(client, monkeypatch):
    _use_width(monkeypatch, "1600")
    resp = await client.get("/")
    assert 'data-layout-width="1600px"' in resp.text


@pytest.mark.asyncio
async def test_error_pages_use_the_same_layout(client, monkeypatch):
    _use_width(monkeypatch, "full")
    resp = await client.get("/no/such/page")
    assert resp.status_code == 404
    assert 'data-layout-width="full"' in resp.text


def test_stylesheet_follows_the_width_toggle():
    from pathlib import Path
    css = (Path(__file__).parent.parent / "app/static/css/wiki.css").read_text()
    assert "--max-w:      var(--limit-w);" in css
    assert ':root[data-width="full"] { --max-w: 100%; }' in css
    assert "--max-w:      1200px" not in css


# -----------------------------------------------------------------------------
