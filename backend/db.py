"""SQLite storage for found.: schema, connection helper, and import of the real source data.

On first start data/found.db is created and filled from the snapshots in data/sources/:
  - pitchbook_startups.json  Yale Startup Directory (yalepitchbook.com/directory): the startups
  - tsai_posts.json          Tsai CITY "Yale Startup Opportunities" board: programs, perks, grants, competitions, asks
  - tsai_upcoming.json       Tsai CITY expected-deadline calendar
They're refreshed weekly (or on demand) by refresh.py, which updates the database in place via sync_sources().

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
    linkedin_url TEXT,                               -- optional link to their LinkedIn profile (self-reported)
    open_to_join INTEGER NOT NULL DEFAULT 0,         -- opted in to being found by founders who are hiring
    join_roles TEXT,                                 -- '|'-separated, e.g. Engineering|Design
    join_industries TEXT,                            -- '|'-separated found. industries
    join_commitment TEXT,                            -- Internship / Part-time / Full-time / Co-founder / Flexible
    join_pitch TEXT,                                 -- one line about what they'd bring
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
CREATE TABLE IF NOT EXISTS source_refreshes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    trigger TEXT NOT NULL,           -- 'weekly' / 'admin' / 'command line'
    status TEXT NOT NULL,            -- 'ok' / 'failed' / 'skipped'
    stats_json TEXT,
    error TEXT
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
    user_cols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
    for col, ddl in (("linkedin_url", "TEXT"), ("open_to_join", "INTEGER NOT NULL DEFAULT 0"), ("join_roles", "TEXT"),
                     ("join_industries", "TEXT"), ("join_commitment", "TEXT"), ("join_pitch", "TEXT")):
        if col not in user_cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(startups)")}
    if "correction_note" not in cols:
        conn.execute("ALTER TABLE startups ADD COLUMN correction_note TEXT")
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] and not conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (config.DEMO_ADMIN_EMAIL,)).fetchone():
        add_demo_admin(conn)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        ensure_demo_founder(conn)
        ensure_demo_joiner(conn)


def ensure_demo_joiner(conn: sqlite3.Connection) -> None:
    """LOCAL MODE ONLY: the demo member is open to joining a startup (once), so the founder side has someone to show."""
    if not config.DEV_MODE or conn.execute("SELECT 1 FROM users WHERE email = ? AND join_commitment IS NOT NULL",
                                           (DEMO_EMAIL,)).fetchone():
        return
    conn.execute(
        "UPDATE users SET open_to_join = 1, join_roles = 'Product|Business & sales',"
        " join_industries = 'Climate & Sustainability|Fintech', join_commitment = 'Part-time',"
        " join_pitch = 'SOM student who loves early-stage ops; can help with customer interviews and go-to-market.'"
        " WHERE email = ?", (DEMO_EMAIL,))


def ensure_demo_founder(conn: sqlite3.Connection) -> None:
    """LOCAL MODE ONLY: a fake founder who owns a clearly labeled demo listing, so graders can try the founder card,
    "Message founder" and replies without claiming a real company. Never created when FOUND_DEV_MODE=0."""
    if not config.DEV_MODE or conn.execute("SELECT 1 FROM users WHERE email = ?", (DEMO_FOUNDER_EMAIL,)).fetchone():
        return
    created = now()
    uid = conn.execute(
        "INSERT INTO users (first_name, last_name, email, password_hash, school, headline, linkedin_url, email_verified,"
        " is_test_account, created_at) VALUES (?,?,?,?,?,?,?,1,1,?)",
        ("Test", "Founder", DEMO_FOUNDER_EMAIL, hash_password(DEMO_PASSWORD), "Yale SOM",
         "Fake test account for trying messages and founder cards",
         "https://www.linkedin.com/in/found-demo-test-founder", created),
    ).lastrowid
    sid = conn.execute(
        "INSERT INTO startups (name, tagline, description, stage, looking_for, hiring, founder_id, founder_verified_via,"
        " status, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (DEMO_STARTUP, "Demo listing for testing found. Not a real company.",
         "This listing exists only in local mode so you can see a founder card, open the founder's LinkedIn link, and "
         "message the founder (log in as test.founder@yale.edu / found2026 to reply).",
         "Idea", "Testers: send me a message to try found.'s messaging.", 0, uid, "admin_review", "listed", "demo", created),
    ).lastrowid
    conn.executemany("INSERT INTO startup_industries VALUES (?,?)", [(sid, "Technology")])
    conn.executemany("INSERT INTO startup_affiliations VALUES (?,?)", [(sid, "Yale SOM")])


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

# Test accounts for local mode (graders). All use the password found2026. None are real people or companies.
DEMO_FOUNDER_EMAIL = "test.founder@yale.edu"
DEMO_STARTUP = "Bulldog Test Co."
DEMO_EMAIL = "demo@yale.edu"
DEMO_PASSWORD = "found2026"
TEST_EMAIL = "dan@yale.edu"  # an obviously-test second account so chat can be tried end to end


def _pitchbook_values(rec: dict, fix: dict) -> dict:
    """One Pitchbook record → found. startup fields, with any saved correction applied on top."""
    rec = dict(rec)
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
    return {
        "name": rec["name"].strip(),
        "tagline": (rec.get("description") or "").strip() or "No description listed.",
        "stage": STAGE_MAP.get(rec["stage"], rec["stage"]),
        "website": clean_url(rec.get("website")),
        "looking_for": looking_for,
        "founders_public": (rec.get("founders") or "").strip() if rec.get("display_founders") else None,
        "hiring": 1 if looking_for and HIRING_RE.search(looking_for) else 0,
        "description": fix.get("description"),
        "correction_note": (fix.get("reason") or "Corrected by found.") if fix else None,
        "industries": sorted({INDUSTRY_MAP.get(i, i) for i in split_list(rec.get("industry"))}),
        "affiliations": sorted({AFFILIATION_MAP.get(a, a) for a in split_list(rec.get("team"))}),
    }


def _set_tags(conn: sqlite3.Connection, sid: int, industries: list[str], affiliations: list[str]) -> None:
    conn.execute("DELETE FROM startup_industries WHERE startup_id = ?", (sid,))
    conn.execute("DELETE FROM startup_affiliations WHERE startup_id = ?", (sid,))
    conn.executemany("INSERT INTO startup_industries VALUES (?,?)", [(sid, i) for i in industries])
    conn.executemany("INSERT INTO startup_affiliations VALUES (?,?)", [(sid, a) for a in affiliations])


def _opportunity_rows(posts: list[dict]) -> list[tuple]:
    rows, seen = [], set()
    for rec in sorted(posts, key=lambda r: r.get("created_at") or 0, reverse=True):
        if not rec.get("is_active") or not rec.get("is_approved"):
            continue
        # The board sometimes has the same post twice ("Fellows - Cohort 7" / "Fellows — Cohort 7"): keep the newest.
        key = (re.sub(r"[^a-z0-9]+", "", rec["title"].lower()), rec.get("application_deadline"))
        if key in seen:
            continue
        seen.add(key)
        rows.append((str(rec["id"]), CATEGORY_MAP.get(rec["type"], "programs"), rec["title"].strip(),
                     (rec.get("company") or "").strip() or None, html_to_text(rec.get("description")),
                     clean_url(rec.get("website")), rec.get("location"), html_to_text(rec.get("ideal_candidate")),
                     clean_url(rec.get("apply_url")), rec.get("apply_email"), rec.get("application_deadline"),
                     int(bool(rec.get("is_rolling"))), rec.get("start_date"), rec.get("grand_prize"),
                     rec.get("curator_note"), epoch_to_iso(rec.get("created_at")), epoch_to_iso(rec.get("expires_at"))))
    return rows


OPP_COLS = ("source_id, category, title, org, description, website, location, ideal_candidate, apply_url, apply_email,"
            " deadline, rolling, start_date, grand_prize, curator_note, posted_at, expires_at")


def sync_sources(conn: sqlite3.Connection, pitchbook: list[dict], posts: list[dict], upcoming: list[dict]) -> dict:
    """Bring the database in line with the source data. Used for the first import and for every refresh.

    Startups (matched by Pitchbook id): new ones are added; unclaimed ones are updated from the source with saved
    corrections applied; listings a founder has claimed are left as the founder edited them; listings that vanished
    from the source are hidden (status 'removed'), never deleted, and come back if they reappear. Member-added
    startups, users, claims, events and messages are never touched. Opportunities and expected deadlines are owned by
    the Tsai CITY board, so they're replaced (matched by post id so ids stay stable)."""
    stats = {"startups_added": 0, "startups_updated": 0, "startups_kept_claimed": 0, "startups_removed": 0,
             "opportunities_added": 0, "opportunities_updated": 0, "opportunities_removed": 0, "deadlines": 0}
    created = now()
    corrections = load_corrections().get("pitchbook", {})
    existing = {r["source_id"]: r for r in conn.execute(
        "SELECT id, source_id, founder_id, status FROM startups WHERE source = 'yale_pitchbook'")}
    incoming = set()
    for rec in pitchbook:
        sid_src = str(rec["id"])
        incoming.add(sid_src)
        v = _pitchbook_values(rec, corrections.get(sid_src, {}))
        row = existing.get(sid_src)
        if row is None:
            sid = conn.execute(
                "INSERT INTO startups (name, tagline, description, stage, website, looking_for, founders_public, hiring,"
                " correction_note, status, source, source_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,'listed',?,?,?)",
                (v["name"], v["tagline"], v["description"], v["stage"], v["website"], v["looking_for"],
                 v["founders_public"], v["hiring"], v["correction_note"], "yale_pitchbook", sid_src, created),
            ).lastrowid
            _set_tags(conn, sid, v["industries"], v["affiliations"])
            stats["startups_added"] += 1
        elif row["founder_id"] is not None:
            stats["startups_kept_claimed"] += 1  # the verified founder's edits win over the source
            if row["status"] == "removed":
                conn.execute("UPDATE startups SET status = 'listed' WHERE id = ?", (row["id"],))
        else:
            conn.execute(
                "UPDATE startups SET name=?, tagline=?, description=COALESCE(?, description), stage=?, website=?,"
                " looking_for=?, founders_public=?, hiring=?, correction_note=?, status='listed' WHERE id = ?",
                (v["name"], v["tagline"], v["description"], v["stage"], v["website"], v["looking_for"],
                 v["founders_public"], v["hiring"], v["correction_note"], row["id"]),
            )
            _set_tags(conn, row["id"], v["industries"], v["affiliations"])
            stats["startups_updated"] += 1
    for src, row in existing.items():
        if src not in incoming and row["status"] == "listed":
            conn.execute("UPDATE startups SET status = 'removed' WHERE id = ?", (row["id"],))
            stats["startups_removed"] += 1

    rows = _opportunity_rows(posts)
    old = {r[0]: r[1] for r in conn.execute("SELECT source_id, id FROM opportunities")}
    keep = set()
    for r in rows:
        if r[0] in old:
            conn.execute(f"UPDATE opportunities SET ({OPP_COLS}) = ({','.join('?' * len(r))}) WHERE id = ?", (*r, old[r[0]]))
            stats["opportunities_updated"] += 1
        else:
            conn.execute(f"INSERT INTO opportunities ({OPP_COLS}) VALUES ({','.join('?' * len(r))})", r)
            stats["opportunities_added"] += 1
        keep.add(r[0])
    for src, oid in old.items():
        if src not in keep:
            conn.execute("DELETE FROM opportunities WHERE id = ?", (oid,))
            stats["opportunities_removed"] += 1

    conn.execute("DELETE FROM expected_deadlines")
    for rec in upcoming:
        conn.execute(
            "INSERT INTO expected_deadlines (name, category, organizer, website, expected_window, expected_month,"
            " expected_year, eligibility_note) VALUES (?,?,?,?,?,?,?,?)",
            (rec["name"], CATEGORY_MAP.get(rec["type"], "programs"), rec.get("organizer"), clean_url(rec.get("website")),
             rec.get("expected_window"), rec.get("expected_deadline_month"), rec.get("expected_year"),
             rec.get("eligibility_note")),
        )
        stats["deadlines"] += 1
    return stats


def seed(conn: sqlite3.Connection) -> None:
    created = now()
    sync_sources(conn, load_source("pitchbook_startups.json"), load_source("tsai_posts.json"),
                 load_source("tsai_upcoming.json"))

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
    ensure_demo_founder(conn)
    ensure_demo_joiner(conn)
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
