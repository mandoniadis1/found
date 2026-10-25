"""Settings read from .env: first the repo's own folder, then the folder one level above (course rule).
Only PORTKEY_API_KEY is required. Everything else has a working local default. Secrets never go in code."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
for env_dir in (ROOT, ROOT.parent):  # repo folder first, then one level up; the first file to set a value wins
    load_dotenv(env_dir / ".env")


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Local mode (default ON so a fresh clone works with only PORTKEY_API_KEY): emails go to output/outbox/ and can be
# opened from the site, LinkedIn uses a labeled stand-in, and a demo admin account exists. Set 0 anywhere real.
DEV_MODE = _flag("FOUND_DEV_MODE", "1")

# Where links in emails point. The one-command run (python run.py) serves everything on port 8030.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8030").rstrip("/")

DB_PATH = Path(os.getenv("FOUND_DB", str(ROOT / "data" / "found.db")))

# Demo admin for graders (local mode only): admin@yale.edu / found2026
DEMO_ADMIN_EMAIL = "admin@yale.edu"

# Only these (verified) accounts can open the admin review queue.
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}

# Members must sign up with a Yale address.
ALLOWED_EMAIL_DOMAIN = "yale.edu"

# Sign in with LinkedIn (OpenID Connect). Create an app at https://www.linkedin.com/developers/apps,
# add the "Sign In with LinkedIn using OpenID Connect" product, and register the redirect URL below.
LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", f"{FRONTEND_URL}/api/auth/linkedin/callback")
LINKEDIN_CONFIGURED = bool(LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET)
LINKEDIN_DEV_STANDIN = DEV_MODE and not LINKEDIN_CONFIGURED

# Email: "outbox" saves each email as a file in output/outbox/ (nothing is sent). "smtp" and "outlook" really send.
# "outlook" sends from the Outlook/Yale account signed in for mcp_servers/mcp_outlook_server.py (Microsoft Graph,
# Mail.Send), reusing its token cache. Needs OUTLOOK_CLIENT_ID / OUTLOOK_TENANT_ID in the my_app root .env.
MAIL_MODE = os.getenv("MAIL_MODE", "outbox").strip().lower()
MAIL_FROM = os.getenv("MAIL_FROM", "found. <no-reply@found.local>")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
OUTLOOK_CLIENT_ID = os.getenv("OUTLOOK_CLIENT_ID", "")
OUTLOOK_TENANT_ID = os.getenv("OUTLOOK_TENANT_ID", "")
OUTLOOK_TOKEN_CACHE = Path(os.getenv("OUTLOOK_TOKEN_CACHE", str(ROOT.parent / "mcp_servers" / "outlook_token_cache.json")))

# Scout helper budget (gpt-6-luna). When a budget is used up, the helper is hidden for the rest of the day.
SCOUT_MODEL = "gpt-6-luna"
SCOUT_MAX_OUTPUT_TOKENS = int(os.getenv("SCOUT_MAX_OUTPUT_TOKENS", "150"))     # per model call
SCOUT_MESSAGE_TOKENS = int(os.getenv("SCOUT_MESSAGE_TOKENS", "1500"))          # per member message, all calls
SCOUT_VISITOR_DAILY_TOKENS = int(os.getenv("SCOUT_VISITOR_DAILY_TOKENS", "8000"))
SCOUT_DAILY_TOKENS = int(os.getenv("SCOUT_DAILY_TOKENS", "100000"))            # whole site
