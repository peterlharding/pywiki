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

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app._version import __version__ as _pkg_version


# -----------------------------------------------------------------------------

class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
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

    database_url: str = "sqlite+aiosqlite:///./pywiki.db"
    db_echo: bool = False

    # ── Auth / JWT ─────────────────────────────────────────────────────────

    secret_key: str = "CHANGE-ME-IN-PRODUCTION-use-a-random-64-char-hex-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8   # 8 hours
    refresh_token_expire_days: int = 30

    # ── Storage ────────────────────────────────────────────────────────────

    attachment_root: Path = Path("./data/attachments")
    max_attachment_bytes: int = 50 * 1024 * 1024   # 50 MB

    # ── Wiki defaults ──────────────────────────────────────────────────────

    default_namespace: str = "Main"
    site_name: str = "PyWiki"
    admin_email: str = "admin@example.com"
    allow_registration: bool = True

    # ── CORS ───────────────────────────────────────────────────────────────

    cors_origins: list[str] = [
        "http://localhost:8000",
        "http://localhost:3000",
    ]

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"

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
