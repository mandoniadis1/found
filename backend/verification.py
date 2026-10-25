"""Identity checks: Yale email links and company-domain claim emails. (LinkedIn is just a self-reported profile link.)

What each check proves:
  - Yale email link    → the member controls a @yale.edu inbox.
  - Company email link → the member controls an inbox on the startup's own domain (e.g. name@daemo.ai). This is the
                         automatic proof of founder status. Anything else goes to manual admin review.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import urllib.parse
from datetime import datetime, timedelta, timezone

import config
from db import now


TOKEN_TTL = timedelta(hours=24)

# Website hosts that aren't the startup's own domain (link-in-bio pages, site builders, social, universities).
SHARED_HOSTS = {
    "linktr.ee", "github.io", "github.com", "wixsite.com", "squarespace.com", "notion.site", "notion.so", "vercel.app",
    "netlify.app", "carrd.co", "webflow.io", "framer.website", "framer.ai", "google.com", "sites.google.com",
    "linkedin.com", "instagram.com", "facebook.com", "medium.com", "substack.com", "yale.edu", "wordpress.com",
    "bubbleapps.io", "glide.page", "apple.com", "play.google.com", "tiktok.com", "x.com", "twitter.com",
}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_email_token(conn: sqlite3.Connection, purpose: str, user_id: int, email: str,
                       claim_id: int | None = None) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + TOKEN_TTL).isoformat(timespec="seconds")
    conn.execute("INSERT INTO email_tokens (token_hash, purpose, user_id, email, claim_id, expires_at) VALUES (?,?,?,?,?,?)",
                 (_hash(token), purpose, user_id, email, claim_id, expires))
    return token


def use_email_token(conn: sqlite3.Connection, token: str, purpose: str) -> sqlite3.Row | None:
    """Return the token row and mark it used, or None if it's unknown, used, expired, or for another purpose."""
    row = conn.execute("SELECT * FROM email_tokens WHERE token_hash = ? AND purpose = ?", (_hash(token), purpose)).fetchone()
    if not row or row["used_at"] or row["expires_at"] < now():
        return None
    conn.execute("UPDATE email_tokens SET used_at = ? WHERE token_hash = ?", (now(), row["token_hash"]))
    return row


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower().strip()


def is_yale_email(email: str) -> bool:
    return email_domain(email) == config.ALLOWED_EMAIL_DOMAIN


def company_domain(website: str | None) -> str | None:
    """The startup's own domain from its website, or None for shared hosts (linktr.ee, *.github.io, ...)."""
    if not website:
        return None
    host = (urllib.parse.urlparse(website if "://" in website else f"https://{website}").hostname or "").lower()
    for prefix in ("www.", "app.", "get.", "try.", "use.", "join.", "go."):
        host = host.removeprefix(prefix)
    if not host or "." not in host:
        return None
    if any(host == h or host.endswith("." + h) for h in SHARED_HOSTS):
        return None
    return host


def email_matches_domain(email: str, domain: str) -> bool:
    """name@daemo.ai or name@team.daemo.ai match daemo.ai. Nothing broader (no @ai, no @co.uk)."""
    d = email_domain(email)
    return d == domain or d.endswith("." + domain)
