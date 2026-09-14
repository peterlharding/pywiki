#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Attachment file types
=====================
Which file extensions may be uploaded, and how stored files are served.

The allowed list is configurable (``ATTACHMENT_EXTENSIONS``); the prohibited
list is not, and always wins.  Content types are derived from the extension,
never from what the uploading client claims.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import mimetypes
import re
from collections.abc import Iterable
from pathlib import PurePosixPath

# -----------------------------------------------------------------------------

IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"})

DEFAULT_ATTACHMENT_EXTENSIONS = (
    "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
    "pdf", "txt", "md", "docx", "xlsx",
)

# Never accepted, even when listed in ATTACHMENT_EXTENSIONS: content a browser
# could run on the wiki's origin, or that an OS or web server could execute.
# Modelled on MediaWiki's $wgProhibitedFileExtensions.
PROHIBITED_EXTENSIONS = frozenset({
    "html", "htm", "xhtml", "xht", "shtml", "jhtml", "mht", "mhtml", "xml",
    "js", "jsb", "mjs", "hta",
    "php", "phtml", "php3", "php4", "php5", "phps", "phar",
    "pl", "py", "cgi", "sh", "ps1",
    "exe", "scr", "dll", "msi", "vbs", "bat", "com", "pif", "cmd", "vxd", "cpl", "jar",
})

# Served with Content-Disposition: inline so the browser displays them.
# Everything else (including SVG, which can carry scripts) is a download.
INLINE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp", "bmp", "pdf", "txt", "md"})

_CONTENT_TYPES = {
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "gif":  "image/gif",
    "webp": "image/webp",
    "svg":  "image/svg+xml",
    "bmp":  "image/bmp",
    "pdf":  "application/pdf",
    # Markdown as text/plain so browsers show it instead of downloading it
    "txt":  "text/plain; charset=utf-8",
    "md":   "text/plain; charset=utf-8",
    "csv":  "text/csv; charset=utf-8",
    "doc":  "application/msword",
    "xls":  "application/vnd.ms-excel",
    "ppt":  "application/vnd.ms-powerpoint",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt":  "application/vnd.oasis.opendocument.text",
    "ods":  "application/vnd.oasis.opendocument.spreadsheet",
    "zip":  "application/zip",
}

_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# -----------------------------------------------------------------------------

def extension_of(filename: str) -> str:
    """Lower-case extension without the dot ("" when there is none)."""
    return PurePosixPath(filename).suffix[1:].lower()


def is_image(filename: str) -> bool:
    return extension_of(filename) in IMAGE_EXTENSIONS


def parse_extension_list(value: str | Iterable[str]) -> frozenset[str]:
    """Parse "pdf, .DOCX txt" (commas and/or whitespace) into {"pdf", "docx", "txt"}."""
    items = re.split(r"[\s,]+", value) if isinstance(value, str) else value
    return frozenset(item.strip().lstrip(".").lower() for item in items if item.strip().lstrip("."))


def sanitize_filename(filename: str) -> str:
    """Drop any directory part and replace characters that are unsafe in paths or HTML."""
    name = PurePosixPath(filename.replace("\\", "/")).name
    return _UNSAFE_FILENAME_CHARS.sub("_", name).strip()


def content_type_for(filename: str) -> str:
    ext = extension_of(filename)
    if ext in _CONTENT_TYPES:
        return _CONTENT_TYPES[ext]
    return mimetypes.guess_type(f"file.{ext}")[0] or "application/octet-stream"


def serves_inline(filename: str) -> bool:
    return extension_of(filename) in INLINE_EXTENSIONS


# -----------------------------------------------------------------------------
