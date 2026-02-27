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


# Bump this whenever the render pipeline changes so stale cached HTML is
# automatically discarded and re-rendered on next page view.
RENDERER_VERSION = 5
_CACHE_STAMP = f'<!--rv:{RENDERER_VERSION}-->'


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
        writer="html5",
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
    # Strip category tags first so they don't appear in rendered output
    content = re.sub(r"\[\[Category:[^\]]+\]\]\n?", "", content, flags=re.IGNORECASE)

    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label  = (m.group(2) or target).strip()
        slug   = _slugify(target)
        href   = f"{base_url}/wiki/{namespace}/{slug}"
        return f'[{label}]({href})'

    return _WIKILINK_RE.sub(_replace, content)


def _preprocess_wikilinks_rst(content: str, namespace: str, base_url: str = "") -> str:
    """Convert [[...]] wikilinks to RST hyperlinks before rendering."""
    # Strip category tags (both wikitext-style and RST-style) before rendering
    content = re.sub(r"\[\[Category:[^\]]+\]\]\n?", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\.\. category::.*\n?", "", content, flags=re.IGNORECASE)

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
    {| ... |}                                        — tables (MediaWiki syntax)
    Lines not matching any block rule become <p> paragraphs.
    """
    lines = content.splitlines()
    out: list[str] = []
    categories: list[str] = []

    # Sentinel prefix used to pass already-rendered HTML through the main loop
    _SENTINEL = "\x00HTML\x00"

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
        # Bare URLs not already inside an anchor or brackets
        text = re.sub(
            r'(?<!["\'>=\[])(https?://[^\s<>\'"]+ )',
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

    # ── table pre-pass: replace {| ... |} blocks with a sentinel ─────────────

    def _parse_table(table_lines: list[str]) -> str:
        """
        Convert a list of raw wikitext table lines (from {| to |} inclusive)
        into an HTML <table>.

        Supported:
          {| attrs          — table open with optional HTML attributes
          |+ caption        — table caption
          |-                — new row (with optional attrs)
          ! h1 !! h2        — header cells (inline multi-cell with !!)
          | c1 || c2        — data cells  (inline multi-cell with ||)
          |}                — table close
        Cell/header lines may start with per-cell attributes: | attrs | content
        """
        html_rows: list[str] = []
        caption: str | None = None
        current_row_cells: list[str] = []
        in_row = False
        # Table-level attrs from the opening {| line
        table_attrs = ""
        if table_lines:
            first = table_lines[0]
            m = re.match(r"^\{\|(.*)$", first)
            if m:
                table_attrs = m.group(1).strip()

        def _flush_row():
            nonlocal in_row
            if current_row_cells:
                html_rows.append("<tr>" + "".join(current_row_cells) + "</tr>")
                current_row_cells.clear()
            in_row = False

        def _parse_cells(line: str, tag: str) -> list[str]:
            """Split a cell line into individual <td>/<th> elements.
            Handles inline multi-cell (|| / !!) and per-cell attributes.
            """
            # Strip leading | or ! marker
            sep = "||" if tag == "td" else "!!"
            raw = re.sub(r"^[|!]\s*", "", line)
            parts = re.split(re.escape(sep), raw)
            cells: list[str] = []
            for part in parts:
                part = part.strip()
                # Check for per-cell attrs:  attrs | content
                attr_match = re.match(r"^([^|]+)\|(?!\|)(.*)$", part)
                if attr_match:
                    attrs = attr_match.group(1).strip()
                    cell_content = attr_match.group(2).strip()
                else:
                    attrs = ""
                    cell_content = part
                attr_str = f" {attrs}" if attrs else ""
                cells.append(f"<{tag}{attr_str}>{_inline(cell_content)}</{tag}>")
            return cells

        for line in table_lines[1:]:  # skip the opening {| line
            stripped = line.strip()

            # Table close
            if stripped.startswith("|}" ):
                _flush_row()
                continue

            # Caption
            if stripped.startswith("|+"):
                caption = _inline(stripped[2:].strip())
                continue

            # New row
            if stripped.startswith("|-"):
                _flush_row()
                in_row = True
                continue

            # Header cells: ! or !!
            if stripped.startswith("!"):
                if not in_row:
                    in_row = True
                current_row_cells.extend(_parse_cells(stripped, "th"))
                continue

            # Data cells: |
            if stripped.startswith("|"):
                if not in_row:
                    in_row = True
                current_row_cells.extend(_parse_cells(stripped, "td"))
                continue

            # Continuation line (indented cell content) — append to last cell
            if current_row_cells and stripped:
                last = current_row_cells[-1]
                # Strip closing tag, append, re-close
                tag_close = re.search(r"</t[dh]>$", last)
                if tag_close:
                    current_row_cells[-1] = last[:tag_close.start()] + " " + _inline(stripped) + last[tag_close.start():]
                continue

        _flush_row()

        attr_str = f" {table_attrs}" if table_attrs else ""
        # Merge class="wikitable" if not already present
        if "class=" not in attr_str:
            attr_str = " class=\"wikitable\"" + attr_str

        parts = [f"<table{attr_str}>"]
        if caption:
            parts.append(f"<caption>{caption}</caption>")
        parts.extend(html_rows)
        parts.append("</table>")
        return "".join(parts)

    # Replace table blocks with sentinels before the main loop
    processed_lines: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("{|"):
            table_block: list[str] = []
            while i < len(lines):
                table_block.append(lines[i])
                if lines[i].strip().startswith("|}"):
                    i += 1
                    break
                i += 1
            processed_lines.append(_SENTINEL + _parse_table(table_block))
        else:
            processed_lines.append(lines[i])
            i += 1
    lines = processed_lines

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
        # Emit pre-rendered HTML blocks (tables) verbatim
        if line.startswith(_SENTINEL):
            _flush_para()
            _close_lists()
            out.append(line[len(_SENTINEL):])
            continue

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
            f'<a href="{base_url}/category/{c}" class="category-link">{c}</a>'
            for c in categories
        )
        out.append(f'<div class="wiki-categories"><strong><a href="/special/categories">Categories:</a></strong> {cat_links}</div>')

    return "\n".join(out)


# -----------------------------------------------------------------------------
# Category extraction (all formats)
# -----------------------------------------------------------------------------

_MD_CATEGORY_RE  = re.compile(r"\[\[Category:([^\]]+)\]\]", re.IGNORECASE)
_RST_CATEGORY_RE = re.compile(r"\.\.\s+category::\s*(.+)", re.IGNORECASE)


def extract_categories(content: str, fmt: str) -> list[str]:
    """Return a sorted, deduplicated list of category names declared in *content*.

    Markdown / Wikitext : ``[[Category:Name]]``
    RST                 : ``.. category:: Name``
    """
    fmt = fmt.lower()
    names: list[str] = []
    if fmt in ("markdown", "wikitext"):
        names = [m.group(1).strip() for m in _MD_CATEGORY_RE.finditer(content)]
    elif fmt == "rst":
        names = [m.group(1).strip() for m in _RST_CATEGORY_RE.finditer(content)]
    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            result.append(n)
    return sorted(result, key=str.lower)


# -----------------------------------------------------------------------------
# Redirect detection
# -----------------------------------------------------------------------------

_REDIRECT_RE = re.compile(r"^\s*#REDIRECT\s*\[\[([^\]]+)\]\]", re.IGNORECASE)


def parse_redirect(content: str) -> str | None:
    """Return the redirect target title if content is a redirect page, else None.

    Matches ``#REDIRECT [[Target Title]]`` on the first non-blank line.
    """
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _REDIRECT_RE.match(line)
        if m:
            return m.group(1).strip()
        break  # first non-blank line didn't match — not a redirect
    return None


# -----------------------------------------------------------------------------
# External link post-processor
# -----------------------------------------------------------------------------

_EXT_LINK_RE = re.compile(
    r'<a\s([^>]*href=["\'](?:https?://|//)[^"\'>][^>]*)>',
    re.IGNORECASE,
)


def _add_external_link_targets(html: str) -> str:
    """Add target="_blank" rel="noopener noreferrer" to all external <a> tags."""
    def _patch(m: re.Match) -> str:
        attrs = m.group(1)
        if "target=" in attrs:
            return m.group(0)
        return f'<a {attrs} target="_blank" rel="noopener noreferrer">'
    return _EXT_LINK_RE.sub(_patch, html)


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

    return _CACHE_STAMP + _add_external_link_targets(html)


def is_cache_valid(rendered: str | None) -> bool:
    """Return True only if *rendered* was produced by the current renderer version."""
    return rendered is not None and rendered.startswith(_CACHE_STAMP)


# -----------------------------------------------------------------------------
