#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Email service — send transactional emails via SMTP (aiosmtplib).

If SMTP_HOST is not configured, emails are printed to stdout (dev mode).
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------

async def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    """Send an email.  Falls back to stdout logging when SMTP is not configured."""
    settings = get_settings()

    if not settings.smtp_host:
        log.warning("SMTP not configured — printing email to stdout")
        print(f"\n{'='*60}")
        print(f"TO:      {to}")
        print(f"SUBJECT: {subject}")
        print(f"{'='*60}")
        print(body_text)
        print(f"{'='*60}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_from
    msg["To"]      = to
    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    import aiosmtplib

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_ssl,
        start_tls=settings.smtp_tls,
    )


# -----------------------------------------------------------------------------

async def send_verification_email(to: str, username: str, token: str) -> None:
    settings = get_settings()
    url = f"{settings.base_url}/verify-email?token={token}"
    subject = f"[{settings.site_name}] Verify your email address"
    body_text = (
        f"Hello {username},\n\n"
        f"Please verify your email address by visiting:\n\n"
        f"  {url}\n\n"
        f"This link will remain valid until you use it.\n\n"
        f"If you did not register on {settings.site_name}, ignore this message.\n"
    )
    body_html = (
        f"<p>Hello <strong>{username}</strong>,</p>"
        f"<p>Please verify your email address by clicking the link below:</p>"
        f"<p><a href=\"{url}\">{url}</a></p>"
        f"<p>If you did not register on {settings.site_name}, ignore this message.</p>"
    )
    await send_email(to, subject, body_text, body_html)


# -----------------------------------------------------------------------------

async def send_password_reset_email(to: str, username: str, token: str) -> None:
    settings = get_settings()
    url = f"{settings.base_url}/reset-password?token={token}"
    subject = f"[{settings.site_name}] Password reset request"
    body_text = (
        f"Hello {username},\n\n"
        f"A password reset was requested for your account. Visit:\n\n"
        f"  {url}\n\n"
        f"This link expires in 1 hour.\n\n"
        f"If you did not request a reset, ignore this message.\n"
    )
    body_html = (
        f"<p>Hello <strong>{username}</strong>,</p>"
        f"<p>A password reset was requested for your account. Click the link below:</p>"
        f"<p><a href=\"{url}\">{url}</a></p>"
        f"<p>This link expires in <strong>1 hour</strong>.</p>"
        f"<p>If you did not request a reset, ignore this message.</p>"
    )
    await send_email(to, subject, body_text, body_html)
