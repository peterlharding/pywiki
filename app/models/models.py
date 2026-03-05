#!/usr/bin/env python
#
#
# ----------------------------------------------------------------------------
"""
ORM Models for PyWiki
======================

Tables
------
users           — accounts with hashed passwords
namespaces      — wiki namespaces (like MediaWiki namespaces)
pages           — wiki pages within a namespace
page_versions   — append-only version history (one row per save)
attachments     — files uploaded to a page

Content format stored per-version: "markdown" or "rst"
All primary keys are UUIDs.  Timestamps stored in UTC.
"""
# ----------------------------------------------------------------------------

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, BigInteger,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ----------------------------------------------------------------------------

def _uuid_col(primary_key=False, nullable=False, **kw):
    """UUID column stored as String(36) — works for both SQLite and PostgreSQL."""
    return mapped_column(
        String(36),
        primary_key=primary_key,
        nullable=nullable,
        default=lambda: str(uuid.uuid4()),
        **kw,
    )


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class User(Base):
    __tablename__ = "users"

    id:           Mapped[str]  = _uuid_col(primary_key=True)
    username:     Mapped[str]  = mapped_column(String(64),  unique=True, nullable=False, index=True)
    email:        Mapped[str]  = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str]  = mapped_column(String(128), nullable=False, default="")
    password_hash:Mapped[str]  = mapped_column(String(255), nullable=False)
    is_active:    Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified:       Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    verification_token:   Mapped[str | None]    = mapped_column(String(128), nullable=True, index=True)
    reset_token:          Mapped[str | None]    = mapped_column(String(128), nullable=True, index=True)
    reset_token_expires:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    page_versions: Mapped[list["PageVersion"]] = relationship(back_populates="author")
    attachments:   Mapped[list["Attachment"]]  = relationship(back_populates="uploaded_by_user")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "username":     self.username,
            "email":        self.email,
            "display_name": self.display_name,
            "is_admin":     self.is_admin,
            "is_active":    self.is_active,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# namespaces
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Namespace(Base):
    """
    Wiki namespace — like MediaWiki namespaces (Main, Talk, Help, etc.).
    The default content format for new pages is stored here but can be
    overridden per-page.
    """
    __tablename__ = "namespaces"

    id:             Mapped[str]        = _uuid_col(primary_key=True)
    name:           Mapped[str]        = mapped_column(String(128), unique=True, nullable=False, index=True)
    description:    Mapped[str]        = mapped_column(Text, default="", nullable=False)
    default_format: Mapped[str]        = mapped_column(String(16), default="markdown", nullable=False)
    created_at:     Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    pages: Mapped[list["Page"]] = relationship(back_populates="namespace", cascade="all, delete-orphan")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# pages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("namespace_id", "slug", name="uq_pages_ns_slug"),
    )

    id:           Mapped[str]        = _uuid_col(primary_key=True)
    namespace_id: Mapped[str]        = mapped_column(String(36), ForeignKey("namespaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title:        Mapped[str]        = mapped_column(String(512), nullable=False, index=True)
    slug:         Mapped[str]        = mapped_column(String(512), nullable=False, index=True)
    created_by:   Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    namespace:   Mapped["Namespace"]           = relationship(back_populates="pages")
    creator:     Mapped["User | None"]         = relationship(foreign_keys=[created_by])
    versions:    Mapped[list["PageVersion"]]   = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="PageVersion.version",
    )
    attachments: Mapped[list["Attachment"]]   = relationship(back_populates="page", cascade="all, delete-orphan")

    @property
    def latest_version(self) -> "PageVersion | None":
        return self.versions[-1] if self.versions else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# page_versions  (append-only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PageVersion(Base):
    __tablename__ = "page_versions"
    __table_args__ = (
        UniqueConstraint("page_id", "version", name="uq_page_versions_page_ver"),
        Index("ix_page_versions_page_latest", "page_id", "version"),
    )

    id:         Mapped[str]        = _uuid_col(primary_key=True)
    page_id:    Mapped[str]        = mapped_column(String(36), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    version:    Mapped[int]        = mapped_column(Integer, nullable=False)
    content:    Mapped[str]        = mapped_column(Text, nullable=False, default="")
    # "markdown" or "rst" — stored per-version so format can change over time
    format:     Mapped[str]        = mapped_column(String(16), nullable=False, default="markdown")
    # Cached rendered HTML (cleared on save)
    rendered:   Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id:  Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    comment:    Mapped[str]        = mapped_column(String(512), default="", nullable=False)
    created_at: Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    page:   Mapped["Page"]       = relationship(back_populates="versions")
    author: Mapped["User | None"] = relationship(back_populates="page_versions")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# attachments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("page_id", "filename", name="uq_attachments_page_file"),
    )

    id:           Mapped[str]        = _uuid_col(primary_key=True)
    page_id:      Mapped[str]        = mapped_column(String(36), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    filename:     Mapped[str]        = mapped_column(String(255), nullable=False)
    content_type: Mapped[str]        = mapped_column(String(128), default="application/octet-stream", nullable=False)
    size_bytes:   Mapped[int]        = mapped_column(BigInteger, default=0, nullable=False)
    storage_path: Mapped[str]        = mapped_column(String(512), nullable=False)
    uploaded_by:  Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    comment:      Mapped[str]        = mapped_column(String(512), default="", nullable=False)
    uploaded_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=_utcnow)

    page:             Mapped["Page"]       = relationship(back_populates="attachments")
    uploaded_by_user: Mapped["User | None"] = relationship(back_populates="attachments")
