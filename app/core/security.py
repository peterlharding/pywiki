#!/usr/bin/env python
#
#
# ----------------------------------------------------------------------------
"""
Security utilities
==================
- Password hashing (bcrypt)
- JWT access and refresh token creation/verification
- FastAPI dependencies for extracting the current user
"""
# ----------------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt as _bcrypt_lib
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt


# -----------------------------------------------------------------------------

from .config import get_settings

# ----------------------------------------------------------------------------
# Password hashing
# ----------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


# ----------------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ----------------------------------------------------------------------------
# JWT tokens
# ----------------------------------------------------------------------------

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
_oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


# ----------------------------------------------------------------------------

def _settings():
    return get_settings()


# ----------------------------------------------------------------------------

def create_access_token(subject: str | int, extra: dict | None = None) -> str:
    s = _settings()
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=s.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.secret_key, algorithm=s.algorithm)


# ----------------------------------------------------------------------------

def create_refresh_token(subject: str | int) -> str:
    s = _settings()
    expire = datetime.now(tz=timezone.utc) + timedelta(days=s.refresh_token_expire_days)
    return jwt.encode(
        {"sub": str(subject), "exp": expire, "type": "refresh"},
        s.secret_key,
        algorithm=s.algorithm,
    )


# ----------------------------------------------------------------------------

def decode_token(token: str) -> dict[str, Any]:
    s = _settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
        if payload.get("sub") is None:
            raise _credentials_error()
        return payload
    except JWTError:
        raise _credentials_error()


# -----------------------------------------------------------------------------

def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ----------------------------------------------------------------------------
# FastAPI dependencies — API (Bearer token)
# ----------------------------------------------------------------------------

async def get_current_user_id(token: str = Depends(_oauth2_scheme)) -> str:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise _credentials_error()
    return payload["sub"]


# ----------------------------------------------------------------------------

async def get_optional_user_id(token: str | None = Depends(_oauth2_optional)) -> str | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload["sub"]
    except HTTPException:
        pass
    return None


# ----------------------------------------------------------------------------
# FastAPI dependency — API or UI (Bearer token OR cookie)
# ----------------------------------------------------------------------------

async def get_current_user_id_bearer_or_cookie(
    request: Request,
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)),
) -> str:
    """Accept a Bearer token (API clients) or an access_token cookie (browser UI)."""
    # 1. Bearer token from Authorization header
    if token:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload["sub"]

    # 2. Cookie (browser UI — httponly so JS can't read it, but browser sends it)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        try:
            payload = decode_token(cookie_token)
            if payload.get("type") == "access":
                return payload["sub"]
        except HTTPException:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ----------------------------------------------------------------------------
# FastAPI dependencies — UI (session cookie)
# ----------------------------------------------------------------------------

async def get_current_user_id_cookie(request: Request) -> str | None:
    """Extract user_id from a signed session cookie for UI routes."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") == "access":
            return payload["sub"]
    except HTTPException:
        pass
    return None


# ----------------------------------------------------------------------------

def get_refreshed_user_id_cookie(request: Request) -> tuple[str | None, str | None]:
    """Return (user_id, new_access_token | None).

    Tries the access_token cookie first.  If it is missing or expired, falls
    back to the refresh_token cookie and issues a fresh access token so the
    caller can set it on the outgoing response.
    """
    # 1. Valid access token — fast path.
    access = request.cookies.get("access_token")
    if access:
        try:
            payload = decode_token(access)
            if payload.get("type") == "access":
                return payload["sub"], None
        except HTTPException:
            pass

    # 2. Expired / missing access token — try the refresh token.
    refresh = request.cookies.get("refresh_token")
    if not refresh:
        return None, None
    try:
        payload = decode_token(refresh)
        if payload.get("type") == "refresh":
            user_id = payload["sub"]
            new_access = create_access_token(user_id)
            return user_id, new_access
    except HTTPException:
        pass
    return None, None


# ----------------------------------------------------------------------------
