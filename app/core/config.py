#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Application configuration.

All values can be overridden via environment variables or a .env file.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app._version import __version__ as _pkg_version
from app.core.filetypes import (
    DEFAULT_ATTACHMENT_EXTENSIONS,
    PROHIBITED_EXTENSIONS,
    parse_extension_list,
)

# -----------------------------------------------------------------------------

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        # PYWIKI_ENV_FILE selects another settings file; set it to "" to read none
        env_file=os.environ.get("PYWIKI_ENV_FILE", ".env") or None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────

    app_name: str = "PyWiki"
    app_version: str = _pkg_version
    base_url: str = "http://localhost:8000"
    debug: bool = False
    environment: Literal["development", "testing", "production"] = "development"

    # ── Database ───────────────────────────────────────────────────────────

    database_url: str = "postgresql+asyncpg://pywiki:pywiki@localhost/pywiki"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Auth / JWT ─────────────────────────────────────────────────────────

    secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-a-random-64-char-hex-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8   # 8 hours
    refresh_token_expire_days: int = 30

    # ── Storage ────────────────────────────────────────────────────────────

    attachment_root: Path = Path("./data/attachments")
    max_attachment_bytes: int = 50 * 1024 * 1024   # 50 MB
    # Uploadable file extensions, comma- or space-separated (like MediaWiki's
    # $wgFileExtensions).  Extensions in filetypes.PROHIBITED_EXTENSIONS are
    # always refused, even if listed here.
    attachment_extensions: str = ",".join(DEFAULT_ATTACHMENT_EXTENSIONS)

    # ── SMTP / email ──────────────────────────────────────────────────────────

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_tls: bool = True            # STARTTLS on port 587
    smtp_ssl: bool = False           # Implicit TLS on port 465
    require_email_verification: bool = False   # Set True to block login until email confirmed

    # ── Wiki defaults ──────────────────────────────────────────────────────

    default_namespace: str = "Main"
    site_name: str = "PyWiki"
    admin_email: str = "admin@example.com"
    allow_registration: bool = True

    # ── Layout ─────────────────────────────────────────────────────────────

    # Maximum width of the page layout, as the default for readers who have not
    # used the width toggle.  "auto" limits it to 90% of the reader's screen
    # (never below 1200px); "full" fills the window; or give a CSS length such
    # as "1600px", "100rem" or "90%" (a bare number means px).
    layout_max_width: str = "auto"

    @field_validator("layout_max_width")
    @classmethod
    def _validate_layout_max_width(cls, value: str) -> str:
        value = value.strip().lower()
        if re.fullmatch(r"\d+(?:\.\d+)?", value):
            value += "px"
        if value in ("auto", "full") or re.fullmatch(r"\d+(?:\.\d+)?(?:px|rem|em|vw|%)", value):
            return value
        raise ValueError(
            "LAYOUT_MAX_WIDTH must be 'auto', 'full' or a CSS length such as 1600px, 100rem or 90%"
        )

    # ── CORS ───────────────────────────────────────────────────────────────

    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
    ]

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

    @property
    def allowed_attachment_extensions(self) -> frozenset[str]:
        return parse_extension_list(self.attachment_extensions) - PROHIBITED_EXTENSIONS

    @property
    def ignored_attachment_extensions(self) -> frozenset[str]:
        """Configured extensions that are dropped because they are prohibited."""
        return parse_extension_list(self.attachment_extensions) & PROHIBITED_EXTENSIONS

    @property
    def attachment_root_resolved(self) -> Path:
        p = self.attachment_root
        p.mkdir(parents=True, exist_ok=True)
        return p


# -----------------------------------------------------------------------------

@lru_cache
def get_settings() -> Settings:
    return Settings()


# -----------------------------------------------------------------------------
