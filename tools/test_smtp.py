#!/usr/bin/env python
"""
Standalone SMTP test script.

Usage (from project root, in WSL):
    python tools/test_smtp.py --to you@example.com

All SMTP settings are read from the project .env file automatically,
or can be overridden with command-line flags.

Examples:
    # Use .env settings, send to a specific address
    python tools/test_smtp.py --to plh@performiq.com

    # Override specific settings
    python tools/test_smtp.py --to test@example.com --host smtp-relay.brevo.com --port 587

    # Test with explicit credentials (bypasses .env)
    python tools/test_smtp.py --to test@example.com \\
        --host smtp-relay.brevo.com --port 587 \\
        --user myuser --password mypassword \\
        --from noreply@example.com
"""

import argparse
import asyncio
import os
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pathlib import Path


# ---------------------------------------------------------------------------
# Load .env from project root (if present)
# ---------------------------------------------------------------------------

def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv(Path(__file__).parent.parent / ".env")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Send a test email via SMTP")
    p.add_argument("--to",       required=True,  help="Recipient email address")
    p.add_argument("--host",     default=os.environ.get("SMTP_HOST", ""),     help="SMTP hostname")
    p.add_argument("--port",     default=int(os.environ.get("SMTP_PORT", "587")), type=int, help="SMTP port")
    p.add_argument("--user",     default=os.environ.get("SMTP_USER", ""),     help="SMTP username")
    p.add_argument("--password", default=os.environ.get("SMTP_PASSWORD", ""), help="SMTP password")
    p.add_argument("--from",     dest="sender",
                   default=os.environ.get("SMTP_FROM", "noreply@example.com"), help="From address")
    p.add_argument("--tls",      default=os.environ.get("SMTP_TLS", "true").lower() == "true",
                   action=argparse.BooleanOptionalAction, help="Use STARTTLS (port 587)")
    p.add_argument("--ssl",      default=os.environ.get("SMTP_SSL", "false").lower() == "true",
                   action=argparse.BooleanOptionalAction, help="Use implicit SSL (port 465)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

async def send_test(args) -> None:
    if not args.host:
        print("ERROR: SMTP_HOST is not set. Add it to .env or pass --host.")
        sys.exit(1)

    subject = "PyWiki SMTP test"
    body    = (
        "This is a test email from the PyWiki SMTP test script.\n\n"
        "If you received this, your SMTP configuration is working correctly.\n"
    )

    print(f"  To: |{args.to}|")
    print(f"From: |{args.sender}|")

    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"]    = args.sender
    msg["To"]      = args.to

    msg.attach(MIMEText(body, "plain"))

    print(f"Connecting to {args.host}:{args.port}  "
          f"ssl={args.ssl}  starttls={args.tls}  "
          f"user={args.user or '(none)'}")

    import aiosmtplib

    try:
        await aiosmtplib.send(
            msg,
            hostname=args.host,
            port=args.port,
            username=args.user or None,
            password=args.password or None,
            use_tls=args.ssl,
            start_tls=args.tls,
        )
        print(f"\n✓ Email sent successfully to {args.to}")
    except Exception as exc:
        print(f"\n✗ SMTP send failed: {exc}")
        print("\nThings to check:")
        print("  - SMTP credentials (username / password)")
        print("  - Port + TLS flags: port 587 → --tls / --no-ssl  |  port 465 → --ssl / --no-tls")
        print("  - Sender address verified with the mail provider")
        print("  - Brevo: Transactional → Email → Logs for delivery status")
        sys.exit(1)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    print(f"Sending test email to: {args.to}")
    print(f"From:                  {args.sender}")
    asyncio.run(send_test(args))
