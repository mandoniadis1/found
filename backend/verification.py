"""Identity checks: Yale email links, Sign in with LinkedIn (OpenID Connect), and company-domain claim emails.

What each check proves:
  - Yale email link    → the member controls a @yale.edu inbox.
  - LinkedIn sign-in   → the member controls a real LinkedIn account (we get its name, email, photo, member id).
                         LinkedIn's sign-in does NOT share work history, so it can't prove someone founded a startup.
  - Company email link → the member controls an inbox on the startup's own domain (e.g. name@daemo.ai). This is the
                         automatic proof of founder status. Anything else goes to manual admin review.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import certifi

import config
from db import now

TLS = ssl.create_default_context(cafile=certifi.where())  # see mailer.py

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


# ---------------------------------------------------------------- Sign in with LinkedIn (OpenID Connect)

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


def new_oauth_state(conn: sqlite3.Connection, user_id: int) -> str:
    state = secrets.token_urlsafe(24)
    conn.execute("INSERT INTO oauth_states VALUES (?,?,?)", (state, user_id, now()))
    return state


def use_oauth_state(conn: sqlite3.Connection, state: str, user_id: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(timespec="seconds")
    row = conn.execute("SELECT * FROM oauth_states WHERE state = ?", (state,)).fetchone()
    conn.execute("DELETE FROM oauth_states WHERE state = ? OR created_at < ?", (state, cutoff))
    return bool(row and row["user_id"] == user_id and row["created_at"] >= cutoff)


def linkedin_authorize_url(state: str) -> str:
    return LINKEDIN_AUTH_URL + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": config.LINKEDIN_CLIENT_ID, "redirect_uri": config.LINKEDIN_REDIRECT_URI,
        "state": state, "scope": "openid profile email",
    })


def linkedin_userinfo(code: str) -> dict:
    """Exchange the authorization code for a token, then fetch the member's OpenID userinfo."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code, "redirect_uri": config.LINKEDIN_REDIRECT_URI,
        "client_id": config.LINKEDIN_CLIENT_ID, "client_secret": config.LINKEDIN_CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(LINKEDIN_TOKEN_URL, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15, context=TLS) as resp:
        access_token = json.load(resp)["access_token"]
    req = urllib.request.Request(LINKEDIN_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(req, timeout=15, context=TLS) as resp:
        return json.load(resp)  # sub, name, given_name, family_name, picture, email, email_verified, locale
