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
RENDERER_VERSION = 11
_CACHE_STAMP = f'<!--rv:{RENDERER_VERSION}-->'

# Sentinel injected by _expand_macros() in place of {{toc}} / __TOC__.
# Must be something that survives all three renderers unchanged.
_TOC_SENTINEL = '<!--PYWIKI-TOC-PLACEHOLDER-->'


# -----------------------------------------------------------------------------
# Markdown renderer via mistune
# -----------------------------------------------------------------------------

def _highlight_code(code: str, lang: str, attrs: str | None = None) -> str:
    """Highlight *code* using Pygments.  Falls back to plain <pre><code> on unknown language."""
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, TextLexer
        from pygments.formatters import HtmlFormatter
        from pygments.util import ClassNotFound
        try:
            lexer = get_lexer_by_name(lang.strip(), stripall=True) if lang.strip() else TextLexer()
        except ClassNotFound:
            lexer = TextLexer()
        formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
        return highlight(code, lexer, formatter)
    except ImportError:
        import html as _html
        return f'<pre><code class="language-{lang}">{_html.escape(code)}</code></pre>'


def _make_md_renderer():
    import mistune
    from mistune.plugins.table import table
    from mistune.plugins.formatting import strikethrough
    from mistune.plugins.url import url

    class _HighlightRenderer(mistune.HTMLRenderer):
        def codespan(self, code: str) -> str:
            import html as _html
            return f'<code>{_html.escape(code)}</code>'

        def block_code(self, code: str, **kwargs) -> str:
            info = kwargs.get('info') or ''
            lang = info.split()[0] if info else ''
            if lang:
                return _highlight_code(code, lang)
            import html as _html
            return f'<pre><code>{_html.escape(code)}</code></pre>'

    md = mistune.create_markdown(
        renderer=_HighlightRenderer(escape=False),
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
            "syntax_highlight": "short",
            "doctitle_xform": False,
            "sectsubtitle_xform": False,
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


def _preprocess_wikilinks_md(
    content: str,
    namespace: str,
    base_url: str = "",
    attachments: dict[str, str] | None = None,
) -> str:
    """Convert [[...]] wikilinks and attachment: image refs to markdown before rendering."""
    # Strip category tags first so they don't appear in rendered output
    content = re.sub(r"\[\[Category:[^\]]+\]\]\n?", "", content, flags=re.IGNORECASE)

    # Rewrite attachment:filename shorthand: ![alt](attachment:name.png)
    # Optional size suffix:  attachment:name.png|200x150  |200  |x150
    # Size pattern: 200x150 | 200x | x150 | 200  (no 'px' suffix in MD variant)
    # Groups: (1=W,2=H) | (3=Wonly+x) | (4=Honly) | (5=Wonly)
    _ATT_SIZE_RE = re.compile(r'^(?:(\d+)x(\d+)|(\d+)x|x(\d+)|(\d+))$')
    if attachments:
        def _att_img(m: re.Match) -> str:
            import html as _html
            alt       = m.group(1)
            raw       = m.group(2)          # e.g. "photo.png|200x150" or "photo.png"
            parts     = raw.split("|", 1)
            filename  = parts[0].strip()
            size_str  = parts[1].strip() if len(parts) > 1 else ""
            url       = attachments.get(filename, "")
            if not url:
                return m.group(0)           # leave unchanged if not found
            # Parse optional size
            width = height = ""
            if size_str:
                sm = _ATT_SIZE_RE.match(size_str)
                if sm:
                    width  = sm.group(1) or sm.group(3) or sm.group(5) or ""
                    height = sm.group(2) or sm.group(4) or ""
            if width or height:
                w_attr = f' width="{width}"'   if width  else ""
                h_attr = f' height="{height}"' if height else ""
                return f'<img src="{url}" alt="{_html.escape(alt)}"{w_attr}{h_attr} loading="lazy" />'
            return f'![{alt}]({url})'
        content = re.sub(
            r'!\[([^\]]*)\]\(attachment:([^)]+)\)',
            _att_img,
            content,
        )

    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        label  = (m.group(2) or target).strip()
        slug   = _slugify(target)
        href   = f"{base_url}/wiki/{namespace}/{slug}"
        return f'[{label}]({href})'

    return _WIKILINK_RE.sub(_replace, content)


def _preprocess_wikilinks_rst(
    content: str,
    namespace: str,
    base_url: str = "",
    attachments: dict[str, str] | None = None,
) -> str:
    """Convert [[...]] wikilinks and attachment: image refs to RST before rendering."""
    # Strip category tags (both wikitext-style and RST-style) before rendering
    content = re.sub(r"\[\[Category:[^\]]+\]\]\n?", "", content, flags=re.IGNORECASE)
    content = re.sub(r"\.\. category::.*\n?", "", content, flags=re.IGNORECASE)

    # Resolve attachment: URLs in .. image:: and .. figure:: directives
    # Matches:  .. image:: attachment:filename.png
    #           .. figure:: attachment:filename.png
    if attachments:
        def _att_directive(m: re.Match) -> str:
            directive = m.group(1)   # "image" or "figure"
            filename  = m.group(2)
            url       = attachments.get(filename, "")
            if not url:
                return m.group(0)    # leave unchanged if not found
            return f'.. {directive}:: {url}'
        content = re.sub(
            r'\.\.\s+(image|figure)::\s+attachment:(\S+)',
            _att_directive,
            content,
            flags=re.IGNORECASE,
        )

        # Also resolve bare `attachment:filename` hyperlink targets used as
        # non-image file links: `label <attachment:file.pdf>`_
        def _att_link(m: re.Match) -> str:
            label    = m.group(1)
            filename = m.group(2)
            url      = attachments.get(filename, "")
            if not url:
                return m.group(0)
            return f'`{label} <{url}>`_'
        content = re.sub(
            r'`([^`]+)\s+<attachment:([^>]+)>`_',
            _att_link,
            content,
        )

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


def _render_wikitext(
    content: str,
    namespace: str,
    base_url: str = "",
    attachments: dict[str, str] | None = None,
) -> str:
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
    <syntaxhighlight lang="python">...</syntaxhighlight>  — syntax-highlighted code
    <pre>...</pre>                                   — preformatted / plain code block
    ```lang\n...\n```                               — fenced code block (GitHub style)
     (space-indented line)                           — treated as <pre> block
    Lines not matching any block rule become <p> paragraphs.
    """
    lines = content.splitlines()
    out: list[str] = []
    categories: list[str] = []
    _attachments = attachments or {}

    # Sentinel prefix used to pass already-rendered HTML through the main loop
    _SENTINEL = "\x00HTML\x00"

    # ── code block pre-pass: replace code blocks with sentinels ─────────────

    import html as _html

    def _process_code_blocks(raw_lines: list[str]) -> list[str]:
        result: list[str] = []
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]

            # <syntaxhighlight lang="...">...</syntaxhighlight> (multi-line)
            sh_open = re.match(r'^\s*<syntaxhighlight(?:\s+lang=["\']?([\w+-]+)["\']?)?[^>]*>', line, re.IGNORECASE)
            if sh_open:
                lang = sh_open.group(1) or ''
                code_lines: list[str] = []
                # content may start on the same line after the tag
                rest = re.sub(r'^\s*<syntaxhighlight[^>]*>', '', line, flags=re.IGNORECASE)
                while i < len(raw_lines):
                    close = re.search(r'</syntaxhighlight>', rest, re.IGNORECASE)
                    if close:
                        code_lines.append(rest[:close.start()])
                        break
                    code_lines.append(rest)
                    i += 1
                    rest = raw_lines[i] if i < len(raw_lines) else ''
                code = '\n'.join(code_lines)
                result.append(_SENTINEL + _highlight_code(code, lang))
                i += 1
                continue

            # <pre>...</pre> plain block (multi-line)
            if re.match(r'^\s*<pre\b[^>]*>', line, re.IGNORECASE):
                code_lines = []
                rest = re.sub(r'^\s*<pre\b[^>]*>', '', line, flags=re.IGNORECASE)
                while i < len(raw_lines):
                    close = re.search(r'</pre>', rest, re.IGNORECASE)
                    if close:
                        code_lines.append(rest[:close.start()])
                        break
                    code_lines.append(rest)
                    i += 1
                    rest = raw_lines[i] if i < len(raw_lines) else ''
                code = _html.escape('\n'.join(code_lines))
                result.append(_SENTINEL + f'<pre><code>{code}</code></pre>')
                i += 1
                continue

            # Fenced ``` blocks
            fence = re.match(r'^```([\w+-]*)\s*$', line)
            if fence:
                lang = fence.group(1)
                code_lines = []
                i += 1
                while i < len(raw_lines) and not raw_lines[i].startswith('```'):
                    code_lines.append(raw_lines[i])
                    i += 1
                code = '\n'.join(code_lines)
                result.append(_SENTINEL + (_highlight_code(code, lang) if lang else f'<pre><code>{_html.escape(code)}</code></pre>'))
                i += 1
                continue

            # Space-indented preformatted line (MediaWiki: leading space = <pre>)
            if line.startswith(' ') and line.strip():
                code_lines = []
                while i < len(raw_lines) and raw_lines[i].startswith(' ') and raw_lines[i].strip():
                    code_lines.append(raw_lines[i][1:])  # strip one leading space
                    i += 1
                code = _html.escape('\n'.join(code_lines))
                result.append(_SENTINEL + f'<pre><code>{code}</code></pre>')
                continue

            result.append(line)
            i += 1
        return result

    lines = _process_code_blocks(lines)

    # ── <ref> pre-pass: collect footnotes, replace with superscript markers ──

    _ref_notes: list[str]      = []   # ordered footnote texts
    _ref_names: dict[str, int] = {}   # name → 1-based index

    _REF_NAMED_RE  = re.compile(r'<ref\s+name=["\']([^"\']+)["\'][^>]*>(.*?)</ref>', re.IGNORECASE | re.DOTALL)
    _REF_EMPTY_RE  = re.compile(r'<ref\s+name=["\']([^"\']+)["\'][^/]*/>', re.IGNORECASE)
    _REF_PLAIN_RE  = re.compile(r'<ref>(.*?)</ref>', re.IGNORECASE | re.DOTALL)

    def _make_sup(idx: int) -> str:
        return f'<sup class="reference"><a href="#cite-note-{idx}" id="cite-ref-{idx}">[{idx}]</a></sup>'

    def _sub_refs(text: str) -> str:
        # Named ref with content: <ref name="foo">text</ref>
        def _named(m: re.Match) -> str:
            name = m.group(1)
            note = m.group(2).strip()
            if name in _ref_names:
                idx = _ref_names[name]
            else:
                _ref_notes.append(note)
                idx = len(_ref_notes)
                _ref_names[name] = idx
            return _make_sup(idx)
        text = _REF_NAMED_RE.sub(_named, text)

        # Back-reference: <ref name="foo" /> — reuse existing named ref
        def _backref(m: re.Match) -> str:
            name = m.group(1)
            idx  = _ref_names.get(name)
            if idx is None:
                return m.group(0)   # unknown name — leave as-is
            return _make_sup(idx)
        text = _REF_EMPTY_RE.sub(_backref, text)

        # Plain ref: <ref>text</ref>
        def _plain(m: re.Match) -> str:
            note = m.group(1).strip()
            _ref_notes.append(note)
            idx = len(_ref_notes)
            return _make_sup(idx)
        text = _REF_PLAIN_RE.sub(_plain, text)

        return text

    # Run ref substitution across the whole content as a single string
    # (refs can span conceptual lines; operate before line-splitting for the
    # block loop, but after code-block sentinels are in place so we don't
    # touch code inside pre blocks)
    raw_joined = "\n".join(lines)
    raw_joined = _sub_refs(raw_joined)
    lines = raw_joined.splitlines()

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
            r'(?<!["\'>=\[])(https?://[^\s<>\'"]+)(?=[\s<>\'"]|$)',
            lambda m: f'<a href="{m.group(1)}" class="external">{m.group(1)}</a>',
            text,
        )

        # [[File:name.png]], [[File:name.png|thumb]], [[File:name.png|thumb|Caption]]
        # Supports: |200px  |x150px  |300x200px  (width x height)
        _SIZE_RE = re.compile(r'^(?:(\d+)x(\d+)|(\d+)x|x(\d+)|(\d+))px$', re.IGNORECASE)
        def _file(m: re.Match) -> str:
            parts   = [p.strip() for p in m.group(0)[2:-2].split("|")]
            name    = parts[0][5:].strip()   # strip "File:"
            opts    = {p.lower() for p in parts[1:] if p.lower() in ("thumb", "thumbnail", "frame", "frameless", "border", "left", "right", "center", "none")}
            # Extract size modifier: 200px / x150px / 300x200px / 200x0px
            # Groups: (1=W,2=H) | (3=Wonly+x) | (4=Honly) | (5=Wonly)
            width = height = ""
            for p in parts[1:]:
                sm = _SIZE_RE.match(p.strip())
                if sm:
                    width  = sm.group(1) or sm.group(3) or sm.group(5) or ""
                    height = sm.group(2) or sm.group(4) or ""
                    break
            caption = next((p for p in parts[1:] if p.lower() not in opts and not _SIZE_RE.match(p.strip())), "")
            url     = (_attachments or {}).get(name, "")
            if not url:
                upload_href = f"/special/upload?filename={name}"
                return f'<a href="{upload_href}" class="missing-file" title="Upload {name}">[[{m.group(0)[2:-2]}]]</a>'
            thumb   = "thumb" in opts or "thumbnail" in opts or "frame" in opts
            align_class = next((f"img-{o}" for o in ("left", "right", "center") if o in opts), "img-right" if thumb else "")
            size_attrs  = (f' width="{width}"'  if width  else "") + \
                          (f' height="{height}"' if height else "")
            img_class   = "wiki-thumb" if thumb else "wiki-img"
            img_tag     = f'<img src="{url}" alt="{caption}" class="{img_class}"{size_attrs} loading="lazy" />'
            if thumb:
                cap_html = f'<figcaption>{caption}</figcaption>' if caption else ''
                return f'<figure class="wiki-figure {align_class}">{img_tag}{cap_html}</figure>'
            else:
                return f'<img src="{url}" alt="{caption}" class="{img_class} {align_class}"{size_attrs} loading="lazy" />'
        text = re.sub(r"\[\[(?:File|Image):[^\]|][^\]]*(?:\|[^\]]*)*\]\]", _file, text, flags=re.IGNORECASE)

        # WikiLinks: [[Page|Label]] / [[Page]]
        def _wl(m: re.Match) -> str:
            target = m.group(1).strip()
            label  = (m.group(2) or target).strip()
            # Skip if it's a File:/Image: link (already handled above)
            if target.lower().startswith("file:") or target.lower().startswith("image:"):
                return m.group(0)
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

    _BLOCK_START_RE = re.compile(r"^\s*<(figure|div|table|blockquote|ul|ol|dl|pre|hr)\b", re.IGNORECASE)

    def _flush_para():
        if not para_buf:
            return
        rendered = [_inline(l) for l in para_buf]
        para_buf.clear()
        # If the buffer is a single line that rendered to a block element, emit unwrapped
        if len(rendered) == 1 and _BLOCK_START_RE.match(rendered[0]):
            out.append(rendered[0])
        else:
            out.append(f"<p>{'<br>'.join(rendered)}</p>")

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

        # <references /> — render collected footnote list
        if re.match(r"^\s*<references\s*/>\s*$", stripped, re.IGNORECASE):
            _flush_para()
            _close_lists()
            if _ref_notes:
                items = "\n".join(
                    f'<li id="cite-note-{i}">'
                    f'<a href="#cite-ref-{i}">↑</a> {_inline(note)}'
                    f'</li>'
                    for i, note in enumerate(_ref_notes, 1)
                )
                out.append(f'<div class="references"><ol>{items}</ol></div>')
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
# Macro pre-processor
# -----------------------------------------------------------------------------

# Matches {{toc}}, {{TOC}}, {{ toc }}, etc.
_MACRO_TOC_RE = re.compile(r'\{\{\s*[Tt][Oo][Cc]\s*\}\}')
# MediaWiki magic word (any capitalisation)
_MAGIC_TOC_RE = re.compile(r'__TOC__')


def _expand_macros(content: str) -> str:
    """Replace TOC macro invocations with an HTML sentinel before rendering.

    Recognised forms (all formats):
      - ``{{toc}}`` / ``{{TOC}}`` / ``{{ Toc }}`` — general macro syntax
      - ``__TOC__`` — MediaWiki magic word (primarily wikitext)
    """
    content = _MACRO_TOC_RE.sub(_TOC_SENTINEL, content)
    content = _MAGIC_TOC_RE.sub(_TOC_SENTINEL, content)
    return content


# -----------------------------------------------------------------------------
# TOC post-processor
# -----------------------------------------------------------------------------

_HEADING_RE = re.compile(r'<(h[1-6])(?:\s[^>]*)?>(.+?)</h[1-6]>', re.IGNORECASE | re.DOTALL)
_STRIP_TAGS_RE = re.compile(r'<[^>]+>')
TOC_MIN_HEADINGS = 3   # retained for backward-compat import; no longer used internally


def _slugify_anchor(text: str) -> str:
    """Convert heading text to a URL-safe anchor ID."""
    text = _STRIP_TAGS_RE.sub('', text)   # strip any inline HTML
    text = text.strip().lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-') or 'section'


def _add_toc(html: str) -> str:
    """Add heading anchor IDs and inject a TOC block at the sentinel position.

    - All h1-h6 always get a unique ``id`` attribute for deep-linking.
    - A ``<div class="toc">`` is injected only where the ``_TOC_SENTINEL``
      placeholder appears (placed there by ``_expand_macros()``).  If no
      sentinel is present the TOC is not rendered, regardless of heading count.
    - Nesting mirrors heading depth: h2 → top-level, h3 → one indent, etc.
    """
    headings = list(_HEADING_RE.finditer(html))
    if not headings:
        return html

    # ── assign unique anchor IDs ──────────────────────────────────────────────
    used: dict[str, int] = {}
    heading_data: list[tuple[int, str, str]] = []   # (level, anchor_id, plain_text)

    def _anchor_for(raw_text: str) -> str:
        base = _slugify_anchor(raw_text)
        count = used.get(base, 0)
        used[base] = count + 1
        return base if count == 0 else f'{base}-{count}'

    # Build replacement map: old tag → new tag with id=
    replacements: list[tuple[str, str]] = []
    for m in headings:
        tag   = m.group(1).lower()           # e.g. "h2"
        inner = m.group(2)                    # inner HTML of the heading
        level = int(tag[1])
        plain = _STRIP_TAGS_RE.sub('', inner).strip()
        anchor = _anchor_for(plain)
        heading_data.append((level, anchor, plain))
        old = m.group(0)
        new = f'<{tag} id="{anchor}">{inner}</{tag}>'
        replacements.append((old, new))

    # Apply replacements (replace first occurrence only, in order)
    for old, new in replacements:
        html = html.replace(old, new, 1)

    # ── build TOC ─────────────────────────────────────────────────────────────
    # docutils (RST) HTML-escapes the sentinel inside a <p> tag; normalise it.
    _TOC_SENTINEL_ESC = _TOC_SENTINEL.replace('<', '&lt;').replace('>', '&gt;')
    _SENTINEL_P_RE = re.compile(
        r'<p>' + re.escape(_TOC_SENTINEL_ESC) + r'</p>'
    )
    html = _SENTINEL_P_RE.sub(_TOC_SENTINEL, html)

    if _TOC_SENTINEL not in html:
        return html

    if not heading_data:
        return html.replace(_TOC_SENTINEL, '')

    # Determine base level (smallest h-level present) for relative nesting
    base_level = min(level for level, _, _ in heading_data)

    toc_lines = ['<div class="toc">',
                 '<div class="toc-title">Contents</div>',
                 '<ol class="toc-list">']
    depth_stack: list[int] = []

    for level, anchor, plain in heading_data:
        rel = level - base_level   # 0 = top level
        # Open nested <ol> tags if going deeper
        while len(depth_stack) < rel:
            toc_lines.append('<ol>')
            depth_stack.append(rel)
        # Close nested <ol> tags if going shallower
        while depth_stack and depth_stack[-1] > rel:
            toc_lines.append('</ol>')
            depth_stack.pop()
        toc_lines.append(f'<li><a href="#{anchor}">{plain}</a></li>')

    while depth_stack:
        toc_lines.append('</ol>')
        depth_stack.pop()
    toc_lines.append('</ol>')
    toc_lines.append('</div>')
    toc_html = '\n'.join(toc_lines)

    # Replace the sentinel with the generated TOC block
    html = html.replace(_TOC_SENTINEL, toc_html)

    return html


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

def render(
    content: str,
    fmt: str,
    namespace: str = "Main",
    base_url: str = "",
    attachments: dict[str, str] | None = None,
) -> str:
    """
    Render *content* to HTML.

    Parameters
    ----------
    content     : raw source text
    fmt         : "markdown", "rst", or "wikitext"
    namespace   : wiki namespace name (used for wikilink URL construction)
    base_url    : site base URL prefix for wikilinks
    attachments : optional mapping of filename → URL for inline image resolution.
                  Used by ``[[File:name.png]]`` (wikitext) and
                  ``![alt](attachment:name.png)`` (markdown).
    """
    fmt = fmt.lower()
    content = _expand_macros(content)

    if fmt == "markdown":
        processed = _preprocess_wikilinks_md(content, namespace, base_url, attachments)
        renderer  = _get_md_renderer()
        html      = renderer(processed)
    elif fmt == "rst":
        processed = _preprocess_wikilinks_rst(content, namespace, base_url, attachments)
        html      = _render_rst(processed)
    elif fmt == "wikitext":
        html = _render_wikitext(content, namespace, base_url, attachments)
    else:
        # Fallback — treat as plain text wrapped in <pre>
        import html as _html
        html = f"<pre>{_html.escape(content)}</pre>"

    return _CACHE_STAMP + _add_toc(_add_external_link_targets(html))


def is_cache_valid(rendered: str | None) -> bool:
    """Return True only if *rendered* was produced by the current renderer version."""
    return rendered is not None and rendered.startswith(_CACHE_STAMP)


# -----------------------------------------------------------------------------
