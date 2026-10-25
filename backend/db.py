"""SQLite storage for found.: schema, connection helper, and import of the real source data.

On first start data/found.db is created and filled from the snapshots in data/sources/:
  - pitchbook_startups.json  Yale Startup Directory (yalepitchbook.com/directory): the startups
  - tsai_posts.json          Tsai CITY "Yale Startup Opportunities" board: programs, perks, grants, competitions, asks
  - tsai_upcoming.json       Tsai CITY expected-deadline calendar
Refresh the snapshots with fetch_sources.py, then rebuild with `python db.py --reset`.

Nothing is invented on import. Fields a source doesn't have (team size, funding, location, founders) stay
empty until the founder claims the listing and fills them in. Founder names are only shown when the
Pitchbook listing itself makes them public (display_founders).
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import config
from auth import hash_password

ROOT = config.ROOT
DB_PATH = config.DB_PATH
SOURCES = ROOT / "data" / "sources"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    school TEXT,
    headline TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0,       -- clicked the link sent to their Yale address
    linkedin_sub TEXT UNIQUE,                        -- LinkedIn member id from "Sign in with LinkedIn"
    linkedin_name TEXT,
    linkedin_email TEXT,
    linkedin_picture TEXT,
    linkedin_dev_standin INTEGER NOT NULL DEFAULT 0, -- 1 = connected through the local dev stand-in, not LinkedIn
    linkedin_connected_at TEXT,
    is_moderator INTEGER NOT NULL DEFAULT 0,
    is_test_account INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'member'   -- 'member' (public site) or 'admin' (admin console, separate login)
);
CREATE TABLE IF NOT EXISTS startups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tagline TEXT NOT NULL,           -- the one-line pitch
    description TEXT,                -- longer "about", added by the founder
    stage TEXT NOT NULL,
    website TEXT,
    looking_for TEXT,                -- the startup's public ask (interns, co-founder, investors...)
    founders_public TEXT,            -- only when the source lists founders publicly
    round TEXT,                      -- below: only filled in by a founder who claimed the listing
    raised_usd INTEGER,
    team_size INTEGER,
    location TEXT,
    founded_year INTEGER,
    hiring INTEGER NOT NULL DEFAULT 0,
    founder_id INTEGER REFERENCES users(id),
    founder_verified_via TEXT,       -- how the claim was checked: 'company_email' or 'admin_review'
    status TEXT NOT NULL DEFAULT 'listed',  -- 'listed' (public), 'pending' (awaiting admin review), 'rejected'
    source TEXT NOT NULL,            -- 'yale_pitchbook' or 'member'
    source_id TEXT,
    correction_note TEXT,            -- set when found. corrected the source data (see data/sources/corrections.json)
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS startup_industries (
    startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    industry TEXT NOT NULL,
    PRIMARY KEY (startup_id, industry)
);
CREATE TABLE IF NOT EXISTS startup_affiliations (
    startup_id INTEGER NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    affiliation TEXT NOT NULL,
    PRIMARY KEY (startup_id, affiliation)
);
CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash TEXT PRIMARY KEY,     -- sha256 of the token in the emailed link (the raw token is never stored)
    purpose TEXT NOT NULL,           -- 'verify_yale' or 'claim_company_email'
    user_id INTEGER NOT NULL REFERENCES users(id),
    email TEXT NOT NULL,
    claim_id INTEGER REFERENCES claim_requests(id),
    expires_at TEXT NOT NULL,
    used_at TEXT
);
CREATE TABLE IF NOT EXISTS oauth_states (
    state TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    startup_id INTEGER NOT NULL REFERENCES startups(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    method TEXT NOT NULL,            -- 'company_email' (automatic) or 'manual_review'
    status TEXT NOT NULL,            -- 'email_sent', 'pending', 'approved', 'denied'
    full_name TEXT,
    role TEXT,
    work_email TEXT,
    linkedin_profile_url TEXT,
    evidence_url TEXT,
    note TEXT,
    admin_note TEXT,
    decided_by TEXT,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS scout_usage (
    day TEXT NOT NULL,               -- YYYY-MM-DD
    key TEXT NOT NULL,               -- 'site', 'user:<id>' or 'visitor:<cookie id>'
    tokens INTEGER NOT NULL DEFAULT 0,
    messages INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, key)
);
CREATE TABLE IF NOT EXISTS listing_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    startup_id INTEGER NOT NULL REFERENCES startups(id),
    verdict TEXT NOT NULL,           -- accurate / needs_changes / unclear
    status TEXT NOT NULL,            -- proposed / applied / dismissed / info
    result_json TEXT NOT NULL,
    input_tokens INTEGER, cached_tokens INTEGER, output_tokens INTEGER, cost_usd REAL,
    created_at TEXT NOT NULL,
    decided_at TEXT
);
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    category TEXT NOT NULL,          -- programs / perks / grants / competitions / asks
    title TEXT NOT NULL,
    org TEXT,
    description TEXT,
    website TEXT,
    location TEXT,
    ideal_candidate TEXT,
    apply_url TEXT,
    apply_email TEXT,
    deadline TEXT,                   -- YYYY-MM-DD
    rolling INTEGER NOT NULL DEFAULT 0,
    start_date TEXT,
    grand_prize TEXT,
    curator_note TEXT,
    posted_at TEXT,
    expires_at TEXT
);
CREATE TABLE IF NOT EXISTS expected_deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    organizer TEXT,
    website TEXT,
    expected_window TEXT,
    expected_month INTEGER,
    expected_year INTEGER,
    eligibility_note TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    kind TEXT NOT NULL,              -- 'startup' (one company's event) or 'sector' (broader)
    sector TEXT,
    host_startup_id INTEGER REFERENCES startups(id),
    organizer_id INTEGER NOT NULL REFERENCES users(id),
    starts_at TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rsvps (
    event_id INTEGER NOT NULL REFERENCES events(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (event_id, user_id)
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_a INTEGER NOT NULL REFERENCES users(id),
    user_b INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE (user_a, user_b)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    sender_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            seed(conn)


def migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a database was created, without touching existing rows."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "kind" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN kind TEXT NOT NULL DEFAULT 'member'")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(startups)")}
    if "correction_note" not in cols:
        conn.execute("ALTER TABLE startups ADD COLUMN correction_note TEXT")
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] and not conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (config.DEMO_ADMIN_EMAIL,)).fetchone():
        add_demo_admin(conn)


def add_demo_admin(conn: sqlite3.Connection) -> None:
    """Grader admin account. Only counts as an admin in local mode (FOUND_DEV_MODE=1)."""
    conn.execute(
        "INSERT INTO users (first_name, last_name, email, password_hash, school, headline, email_verified,"
        " is_test_account, created_at) VALUES (?,?,?,?,?,?,1,1,?)",
        ("Demo", "Admin", config.DEMO_ADMIN_EMAIL, hash_password(DEMO_PASSWORD), "Yale SOM", "Demo admin (local mode only)", now()),
    )


# ---------------------------------------------------------------- normalizing source values

# Pitchbook industry → found. industry (short labels; near-duplicates merged).
INDUSTRY_MAP = {
    "Technology": "Technology",
    "Healthcare & Biotechnology": "Health & Biotech",
    "Healthcare": "Health & Biotech",
    "Consumer Products & Services": "Consumer",
    "Retail": "Consumer",
    "Social Impact & Non-Profit": "Social Impact",
    "Social Impact": "Social Impact",
    "CleanTech & Sustainability": "Climate & Sustainability",
    "Education & EdTech": "Education",
    "Media & Entertainment": "Media & Entertainment",
    "Art & Culture": "Media & Entertainment",
    "Financial Services & FinTech": "Fintech",
    "Real Estate & PropTech": "Real Estate",
    "Robotics & Automation": "Robotics",
    "Marketing": "Marketing",
    "Storage & Moving": "Logistics",
}
STAGE_MAP = {"Creation/Building": "Building"}
AFFILIATION_MAP = {"Yale PhD": "Yale Graduate School", "Yale School of Arts & Sciences": "Yale Graduate School"}

# Tsai CITY post type → found. opportunity category.
CATEGORY_MAP = {
    "accelerator": "programs",
    "credits": "perks",
    "grant": "grants",
    "competition": "competitions",
    "student-startups": "asks",
    "alumni-startup": "asks",
    "faculty-startup": "asks",
}

HIRING_RE = re.compile(r"\b(intern|interns|internship|hiring|developer|engineer)\b", re.I)


def split_list(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def clean_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    return url if re.match(r"^https?://", url) else f"https://{url}"


class _TextExtractor(HTMLParser):
    """HTML → plain text with paragraph breaks. Keeps only text, so no source markup reaches the browser."""
    BLOCK = {"p", "br", "li", "div", "h1", "h2", "h3", "h4", "ul", "ol"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.parts.append("\n• ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value: str | None) -> str | None:
    if not value:
        return None
    parser = _TextExtractor()
    parser.feed(value)
    text = html.unescape("".join(parser.parts)).replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or None


def epoch_to_iso(value) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds") if value else None


CORRECTIONS_PATH = SOURCES / "corrections.json"
CORRECTABLE = ("tagline", "description", "stage", "website", "looking_for", "industries", "affiliations")


def load_corrections() -> dict:
    return json.loads(CORRECTIONS_PATH.read_text()) if CORRECTIONS_PATH.exists() else {"pitchbook": {}}


def save_correction(source_id: str, name: str, fields: dict, reason: str) -> None:
    """Record an admin's fix to an imported listing so it survives a data refresh / reset."""
    data = load_corrections()
    entry = data.setdefault("pitchbook", {}).setdefault(source_id, {})
    entry.update({"name": name, **{k: v for k, v in fields.items() if k in CORRECTABLE}, "reason": reason,
                  "corrected_at": datetime.now(timezone.utc).date().isoformat()})
    CORRECTIONS_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False))


def load_source(name: str) -> list[dict]:
    path = SOURCES / name
    return json.loads(path.read_text())["records"] if path.exists() else []


# ---------------------------------------------------------------- seed

DEMO_EMAIL = "demo@yale.edu"
DEMO_PASSWORD = "found2026"
TEST_EMAIL = "dan@yale.edu"  # an obviously-test second account so chat can be tried end to end


def seed(conn: sqlite3.Connection) -> None:
    created = now()

    corrections = load_corrections().get("pitchbook", {})
    for rec in load_source("pitchbook_startups.json"):
        fix = corrections.get(str(rec["id"]), {})
        if fix.get("tagline"):
            rec["description"] = fix["tagline"]
        if fix.get("industries"):
            rec["industry"] = ", ".join(fix["industries"])  # already found. labels; INDUSTRY_MAP leaves them as-is
        if fix.get("affiliations"):
            rec["team"] = ", ".join(fix["affiliations"])
        for k in ("stage", "website"):
            if fix.get(k):
                rec[k] = fix[k]
        if "looking_for" in fix:
            rec["problem"] = fix["looking_for"]
        looking_for = (rec.get("problem") or "").strip() or None
        sid = conn.execute(
            "INSERT INTO startups (name, tagline, stage, website, looking_for, founders_public, hiring, status, source,"
            " source_id, created_at) VALUES (?,?,?,?,?,?,?,'listed',?,?,?)",
            (rec["name"].strip(), (rec.get("description") or "").strip() or "No description listed.",
             STAGE_MAP.get(rec["stage"], rec["stage"]), clean_url(rec.get("website")), looking_for,
             (rec.get("founders") or "").strip() if rec.get("display_founders") else None,
             1 if looking_for and HIRING_RE.search(looking_for) else 0, "yale_pitchbook", str(rec["id"]), created),
        ).lastrowid
        if fix:
            conn.execute("UPDATE startups SET description = COALESCE(?, description), correction_note = ? WHERE id = ?",
                         (fix.get("description"), fix.get("reason") or "Corrected by found.", sid))
        for ind in {INDUSTRY_MAP.get(i, i) for i in split_list(rec.get("industry"))}:
            conn.execute("INSERT INTO startup_industries VALUES (?,?)", (sid, ind))
        for aff in {AFFILIATION_MAP.get(a, a) for a in split_list(rec.get("team"))}:
            conn.execute("INSERT INTO startup_affiliations VALUES (?,?)", (sid, aff))

    seen_posts: set[tuple[str, str | None]] = set()
    for rec in sorted(load_source("tsai_posts.json"), key=lambda r: r.get("created_at") or 0, reverse=True):
        if not rec.get("is_active") or not rec.get("is_approved"):
            continue
        # The board sometimes has the same post twice ("Fellows - Cohort 7" / "Fellows — Cohort 7"): keep the newest.
        key = (re.sub(r"[^a-z0-9]+", "", rec["title"].lower()), rec.get("application_deadline"))
        if key in seen_posts:
            continue
        seen_posts.add(key)
        conn.execute(
            "INSERT INTO opportunities (source_id, category, title, org, description, website, location,"
            " ideal_candidate, apply_url, apply_email, deadline, rolling, start_date, grand_prize, curator_note,"
            " posted_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(rec["id"]), CATEGORY_MAP.get(rec["type"], "programs"), rec["title"].strip(),
             (rec.get("company") or "").strip() or None, html_to_text(rec.get("description")),
             clean_url(rec.get("website")), rec.get("location"), html_to_text(rec.get("ideal_candidate")),
             clean_url(rec.get("apply_url")), rec.get("apply_email"), rec.get("application_deadline"),
             int(bool(rec.get("is_rolling"))), rec.get("start_date"), rec.get("grand_prize"),
             rec.get("curator_note"), epoch_to_iso(rec.get("created_at")), epoch_to_iso(rec.get("expires_at"))),
        )

    for rec in load_source("tsai_upcoming.json"):
        conn.execute(
            "INSERT INTO expected_deadlines (name, category, organizer, website, expected_window, expected_month,"
            " expected_year, eligibility_note) VALUES (?,?,?,?,?,?,?,?)",
            (rec["name"], CATEGORY_MAP.get(rec["type"], "programs"), rec.get("organizer"), clean_url(rec.get("website")),
             rec.get("expected_window"), rec.get("expected_deadline_month"), rec.get("expected_year"),
             rec.get("eligibility_note")),
        )

    demo_id = conn.execute(
        "INSERT INTO users (first_name, last_name, email, password_hash, school, headline, email_verified, created_at)"
        " VALUES (?,?,?,?,?,?,1,?)",
        ("Madison", "Demo", DEMO_EMAIL, hash_password(DEMO_PASSWORD), "Yale SOM", "Exploring the Yale startup scene", created),
    ).lastrowid
    dan_id = conn.execute(
        "INSERT INTO users (first_name, last_name, email, password_hash, school, headline, is_test_account,"
        " email_verified, created_at) VALUES (?,?,?,?,?,?,?,1,?)",
        ("Handsome", "Dan", TEST_EMAIL, hash_password(DEMO_PASSWORD), "Yale College", "Test account for trying messages", 1, created),
    ).lastrowid
    add_demo_admin(conn)
    a, b = sorted((demo_id, dan_id))
    conv = conn.execute("INSERT INTO conversations (user_a, user_b, created_at) VALUES (?,?,?)", (a, b, created)).lastrowid
    conn.execute("INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?,?,?,?)",
                 (conv, dan_id, "Woof! I'm a test account. Log in as dan@yale.edu in another browser to reply as me.", created))


if __name__ == "__main__":
    if "--reset" in sys.argv and DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    with connect() as c:
        counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("startups", "opportunities", "expected_deadlines", "users")}
    print(f"Database ready at {DB_PATH}: {counts}")
