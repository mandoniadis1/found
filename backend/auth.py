"""Password hashing and session cookies.

Passwords are stored as PBKDF2-SHA256 with a random salt (never plain text). A login creates a
random session token stored in the sessions table and sent to the browser as an HttpOnly cookie,
so page JavaScript can't read it.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 240_000
COOKIE_NAME = "found_session"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
    return hmac.compare_digest(check, digest)


def new_token() -> str:
    return secrets.token_urlsafe(32)
