#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Markup renderer
===============
Renders wiki page content to HTML.

Supported formats:
  - markdown  : rendered via mistune (with extras: tables, fenced code, strikethrough)
  - rst       : rendered via docutils

Both formats support [[WikiLink]] style inter-page links which are rewritten
to the correct wiki URL before final HTML output.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import re
from typing import Optional


# -----------------------------------------------------------------------------
# Markdown renderer via mistune
# -----------------------------------------------------------------------------

def _make_md_renderer():
    import mistune
    from mistune.plugins.table import table
    from mistune.plugins.formatting import strikethrough
    from mistune.plugins.url import url

    md = mistune.create_markdown(
        escape=False,
        plugins=[table, strikethrough, url],
    )
    return md


_md_renderer = None


def _get_md_renderer():
    global _md_renderer
    if _md_renderer is None:
        _md_renderer = _make_md_renderer()
    return _md_renderer


# -----------------------------------------------------------------------------
# RST renderer via docutils
# -----------------------------------------------------------------------------

def _render_rst(content: str) -> str:
    from docutils.core import publish_parts
    parts = publish_parts(
        source=content,
        writer_name="html5",
        settings_overrides={
            "halt_level": 5,
            "report_level": 5,
            "input_encoding": "unicode",
            "output_encoding": "unicode",
        },
    )
    return parts["body"]


# -----------------------------------------------------------------------------
# WikiLink rewriting  [[Page Title]] → <a href="/wiki/Namespace/page-title">
# -----------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def _rewrite_wikilinks(html: str, namespace: str, base_url: str = "") -> str:
    """
    Replace [[Page Title]] and [[Page Title|Display Text]] patterns in the
    already-rendered HTML with proper anchor tags.

    Note: wikilinks in markdown/rst source are replaced *before* rendering so
    they appear as plain <a> tags in output.
    """
    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label  = (m.group(2) or target).strip()
        slug   = _slugify(target)
        href   = f"{base_url}/wiki/{namespace}/{slug}"
        return f'<a href="{href}" class="wikilink">{label}</a>'

    return _WIKILINK_RE.sub(_replace, html)


def _preprocess_wikilinks_md(content: str, namespace: str, base_url: str = "") -> str:
    """Convert [[...]] wikilinks to markdown links before rendering."""
    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label  = (m.group(2) or target).strip()
        slug   = _slugify(target)
        href   = f"{base_url}/wiki/{namespace}/{slug}"
        return f'[{label}]({href})'

    return _WIKILINK_RE.sub(_replace, content)


def _preprocess_wikilinks_rst(content: str, namespace: str, base_url: str = "") -> str:
    """Convert [[...]] wikilinks to RST hyperlinks before rendering."""
    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label  = (m.group(2) or target).strip()
        slug   = _slugify(target)
        href   = f"{base_url}/wiki/{namespace}/{slug}"
        return f'`{label} <{href}>`_'

    return _WIKILINK_RE.sub(_replace, content)


# -----------------------------------------------------------------------------
# Slug helper
# -----------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a page title to a URL slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# -----------------------------------------------------------------------------
# Wikitext (MediaWiki syntax) renderer
# -----------------------------------------------------------------------------

_CATEGORY_RE = re.compile(r"\[\[Category:([^\]]+)\]\]", re.IGNORECASE)


def _render_wikitext(content: str, namespace: str, base_url: str = "") -> str:
    """
    Convert a subset of MediaWiki wikitext to HTML.

    Supported syntax
    ----------------
    = H1 =  /  == H2 ==  / ... / ====== H6 ======
    '''bold'''  /  ''italic''  /  '''''bold-italic'''''
    [[Page Title]]  /  [[Page Title|Display Text]]   — inter-wiki links
    [[Category:Name]]                                — stripped, collected in footer
    [https://example.com Display]                    — external links
    ----                                             — <hr>
    * item  /  ** nested                             — unordered lists
    # item  /  ## nested                             — ordered lists
    ; term : definition                              — definition lists
    {{template}}                                     — rendered as an info box placeholder
    Lines not matching any block rule become <p> paragraphs.
    """
    lines = content.splitlines()
    out: list[str] = []
    categories: list[str] = []

    # ── inline markup ────────────────────────────────────────────────────────

    def _inline(text: str) -> str:
        # Strip category tags (collected separately)
        text = _CATEGORY_RE.sub("", text)

        # External links: [URL Display Text]
        text = re.sub(
            r"\[(\w+://[^\s\]]+)\s+([^\]]+)\]",
            lambda m: f'<a href="{m.group(1)}" class="external">{m.group(2)}</a>',
            text,
        )
        # Bare external links: [URL]
        text = re.sub(
            r"\[(\w+://[^\s\]]+)\]",
            lambda m: f'<a href="{m.group(1)}" class="external">{m.group(1)}</a>',
            text,
        )

        # WikiLinks: [[Page|Label]] / [[Page]]
        def _wl(m: re.Match) -> str:
            target = m.group(1).strip()
            label  = (m.group(2) or target).strip()
            slug   = _slugify(target)
            href   = f"{base_url}/wiki/{namespace}/{slug}"
            return f'<a href="{href}" class="wikilink">{label}</a>'
        text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", _wl, text)

        # Bold-italic (must come before bold/italic individually)
        text = re.sub(r"'{5}(.+?)'{5}", r"<b><i>\1</i></b>", text)
        # Bold
        text = re.sub(r"'{3}(.+?)'{3}", r"<b>\1</b>", text)
        # Italic
        text = re.sub(r"'{2}(.+?)'{2}", r"<i>\1</i>", text)

        return text

    # ── collect categories first ──────────────────────────────────────────────
    for line in lines:
        for m in _CATEGORY_RE.finditer(line):
            categories.append(m.group(1).strip())

    # ── block-level pass ─────────────────────────────────────────────────────
    in_ul: list[int] = []   # stack of depths for <ul>
    in_ol: list[int] = []   # stack of depths for <ol>
    in_dl = False
    para_buf: list[str] = []

    def _flush_para():
        if para_buf:
            out.append(f"<p>{'<br>'.join(_inline(l) for l in para_buf)}</p>")
            para_buf.clear()

    def _close_lists():
        nonlocal in_dl
        while in_ul:
            out.append("</ul>")
            in_ul.pop()
        while in_ol:
            out.append("</ol>")
            in_ol.pop()
        if in_dl:
            out.append("</dl>")
            in_dl = False

    for line in lines:
        # Strip category tags from display
        stripped = _CATEGORY_RE.sub("", line).rstrip()

        # Blank line → flush paragraph / close lists
        if not stripped.strip():
            _flush_para()
            _close_lists()
            continue

        # Headings: = H1 = … ====== H6 ======
        m = re.match(r"^(={1,6})\s*(.+?)\s*=+\s*$", stripped)
        if m:
            _flush_para()
            _close_lists()
            level = min(len(m.group(1)), 6)
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^-{4,}\s*$", stripped):
            _flush_para()
            _close_lists()
            out.append("<hr>")
            continue

        # Templates: {{...}} — render as a notice box
        if re.match(r"^\{\{.+\}\}\s*$", stripped):
            _flush_para()
            _close_lists()
            inner = re.sub(r"^\{\{|\}\}$", "", stripped).strip()
            out.append(
                f'<div class="wiki-template"><strong>{{{{</strong> {_inline(inner)} '
                f'<strong>}}}}</strong></div>'
            )
            continue

        # Unordered list: * / ** / ***
        m = re.match(r"^(\*+)\s*(.*)", stripped)
        if m:
            _flush_para()
            while in_ol:
                out.append("</ol>")
                in_ol.pop()
            if in_dl:
                out.append("</dl>")
                in_dl = False
            depth = len(m.group(1))
            while len(in_ul) < depth:
                out.append("<ul>")
                in_ul.append(len(in_ul) + 1)
            while len(in_ul) > depth:
                out.append("</ul>")
                in_ul.pop()
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue

        # Ordered list: # / ## / ###
        m = re.match(r"^(#+)\s*(.*)", stripped)
        if m:
            _flush_para()
            while in_ul:
                out.append("</ul>")
                in_ul.pop()
            if in_dl:
                out.append("</dl>")
                in_dl = False
            depth = len(m.group(1))
            while len(in_ol) < depth:
                out.append("<ol>")
                in_ol.append(len(in_ol) + 1)
            while len(in_ol) > depth:
                out.append("</ol>")
                in_ol.pop()
            out.append(f"<li>{_inline(m.group(2))}</li>")
            continue

        # Definition list: ; term : definition
        m = re.match(r"^;\s*(.+?)\s*:\s*(.*)", stripped)
        if m:
            _flush_para()
            _close_lists()
            if not in_dl:
                out.append("<dl>")
                in_dl = True
            out.append(f"<dt>{_inline(m.group(1))}</dt><dd>{_inline(m.group(2))}</dd>")
            continue

        # Plain text — accumulate into paragraph
        _close_lists()
        para_buf.append(stripped)

    # Flush anything remaining
    _flush_para()
    _close_lists()

    # Append categories footer if any were found
    if categories:
        cat_links = " · ".join(
            f'<a href="{base_url}/search?q=Category:{c}&namespace={namespace}" '
            f'class="category-link">{c}</a>'
            for c in categories
        )
        out.append(f'<div class="wiki-categories"><strong>Categories:</strong> {cat_links}</div>')

    return "\n".join(out)


# -----------------------------------------------------------------------------
# Public render function
# -----------------------------------------------------------------------------

def render(content: str, fmt: str, namespace: str = "Main", base_url: str = "") -> str:
    """
    Render *content* to HTML.

    Parameters
    ----------
    content   : raw source text
    fmt       : "markdown" or "rst"
    namespace : wiki namespace name (used for wikilink URL construction)
    base_url  : site base URL prefix for wikilinks
    """
    fmt = fmt.lower()

    if fmt == "markdown":
        processed = _preprocess_wikilinks_md(content, namespace, base_url)
        renderer  = _get_md_renderer()
        html      = renderer(processed)
    elif fmt == "rst":
        processed = _preprocess_wikilinks_rst(content, namespace, base_url)
        html      = _render_rst(processed)
    elif fmt == "wikitext":
        html = _render_wikitext(content, namespace, base_url)
    else:
        # Fallback — treat as plain text wrapped in <pre>
        import html as _html
        html = f"<pre>{_html.escape(content)}</pre>"

    return html


# -----------------------------------------------------------------------------
