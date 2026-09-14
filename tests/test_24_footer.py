#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""The footer credits the pywiki project, not the instance's SITE_NAME."""
# -----------------------------------------------------------------------------

from __future__ import annotations

import pytest

from app.core.config import get_settings

# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_footer_names_the_project_not_the_site(client, monkeypatch):
    monkeypatch.setenv("SITE_NAME", "Expanse Wiki")
    get_settings.cache_clear()
    try:
        html = (await client.get("/")).text
    finally:
        get_settings.cache_clear()

    footer = html[html.index('<footer class="site-footer">'):html.index("</footer>")]
    assert '<a class="footer-project" href="https://github.com/peterlharding/pywiki">pywiki</a>' in footer
    assert f"v{get_settings().app_version}" in footer
    assert "Expanse Wiki" not in footer
    # The site name still brands the rest of the page
    assert '<a class="nav-logo" href="/">Expanse Wiki</a>' in html


# -----------------------------------------------------------------------------
