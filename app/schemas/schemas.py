#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Pydantic v2 schemas for request validation and response serialisation.
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Shared
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OKResponse(BaseModel):
    ok: bool = True
    message: str = "success"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auth
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds


# -----------------------------------------------------------------------------

class RefreshRequest(BaseModel):
    refresh_token: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Users
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=256)
    display_name: str = Field(default="", max_length=128)

    @field_validator("username")
    @classmethod
    def username_not_reserved(cls, v: str) -> str:
        reserved = {"admin", "system", "guest", "anonymous"}
        if v.lower() in reserved:
            raise ValueError(f"Username '{v}' is reserved")
        return v


# -----------------------------------------------------------------------------

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = Field(None, max_length=128)
    password: Optional[str] = Field(None, min_length=8, max_length=256)


# -----------------------------------------------------------------------------

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Namespaces
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTENT_FORMATS = {"markdown", "rst", "wikitext"}


class NamespaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    description: str = Field(default="", max_length=1000)
    default_format: str = Field(default="markdown")

    @field_validator("default_format")
    @classmethod
    def valid_format(cls, v: str) -> str:
        if v not in CONTENT_FORMATS:
            raise ValueError(f"default_format must be one of: {', '.join(sorted(CONTENT_FORMATS))}")
        return v


# -----------------------------------------------------------------------------

class NamespaceUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=1000)
    default_format: Optional[str] = None

    @field_validator("default_format")
    @classmethod
    def valid_format(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTENT_FORMATS:
            raise ValueError(f"default_format must be one of: {', '.join(sorted(CONTENT_FORMATS))}")
        return v


# -----------------------------------------------------------------------------

class NamespaceResponse(BaseModel):
    id: str
    name: str
    description: str
    default_format: str
    page_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    content: str = Field(default="", max_length=10_000_000)
    format: str = Field(default="markdown")
    comment: str = Field(default="", max_length=512)

    @field_validator("format")
    @classmethod
    def valid_format(cls, v: str) -> str:
        if v not in CONTENT_FORMATS:
            raise ValueError(f"format must be one of: {', '.join(sorted(CONTENT_FORMATS))}")
        return v


# -----------------------------------------------------------------------------

class PageUpdate(BaseModel):
    content: str = Field(..., max_length=10_000_000)
    format: Optional[str] = None
    comment: str = Field(default="", max_length=512)

    @field_validator("format")
    @classmethod
    def valid_format(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTENT_FORMATS:
            raise ValueError(f"format must be one of: {', '.join(sorted(CONTENT_FORMATS))}")
        return v


# -----------------------------------------------------------------------------

class PageRename(BaseModel):
    new_title: str = Field(..., min_length=1, max_length=512)


# -----------------------------------------------------------------------------

class PageVersionResponse(BaseModel):
    id: str
    version: int
    content: str
    format: str
    author_id: Optional[str]
    author_username: Optional[str]
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------

class PageResponse(BaseModel):
    id: str
    namespace: str
    title: str
    slug: str
    version: int
    content: str
    format: str
    rendered: Optional[str]
    author_id: Optional[str]
    author_username: Optional[str]
    comment: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------

class PageSummary(BaseModel):
    """Lightweight listing item — no content body."""
    id: str
    namespace: str
    title: str
    slug: str
    version: int
    format: str
    author_username: Optional[str]
    updated_at: datetime

    model_config = {"from_attributes": True}


# -----------------------------------------------------------------------------

class DiffResponse(BaseModel):
    namespace: str
    slug: str
    from_version: int
    to_version: int
    diff: list[dict]   # list of {type: "equal"|"insert"|"delete", lines: [...]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Attachments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AttachmentResponse(BaseModel):
    id: str
    page_id: str
    filename: str
    content_type: str
    size_bytes: int
    comment: str
    uploaded_by: Optional[str]
    uploaded_at: datetime
    url: str

    model_config = {"from_attributes": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SearchResult(BaseModel):
    namespace: str
    title: str
    slug: str
    snippet: str
    updated_at: datetime


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Admin
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AdminStatsResponse(BaseModel):
    user_count: int
    admin_count: int
    namespace_count: int
    page_count: int
    version_count: int


class AdminConfigResponse(BaseModel):
    site_name: str
    base_url: str
    allow_registration: bool
    default_namespace: str
    admin_email: str
    app_version: str
    environment: str


class UserAdminResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
