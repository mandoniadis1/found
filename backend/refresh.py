"""Refresh found.'s data from the two source sites, without a browser. Runs weekly while the server is up
(REFRESH_DAYS, default 7), from the admin console ("Refresh now"), or by hand:

    ../.venv/bin/python refresh.py          (from backend/)

  - Tsai CITY "Yale Startup Opportunities" board: its public JSON feeds (/api/posts, /api/upcoming).
  - Yale Startup Directory (yalepitchbook.com): the page reads a public Supabase table with a read-only key that is
    shipped in the site's own JavaScript. We find that key the same way a browser does, at refresh time, so nothing
    from their site is stored in this repo.

Safety checks before anything changes: each feed must parse, have the expected fields, and not shrink by more than
half compared with the last snapshot (a broken or empty response must never wipe the directory). Then the snapshots
in data/sources/ are replaced (the previous ones are kept in data/sources/previous/) and the database is updated in
place by db.sync_sources(): users, claims, corrections, events and messages are never touched.
"""

from __future__ import annotations

import json
import re
import shutil
import ssl
import sys
import threading
import urllib.request
from datetime import datetime, timedelta, timezone

import certifi

import config
from db import SOURCES, connect, now, sync_sources

TLS = ssl.create_default_context(cafile=certifi.where())
PITCHBOOK_PAGE = "https://www.yalepitchbook.com/directory"
TSAI_BASE = "https://tsaicity.useplop.com"
REFRESH_DAYS = int(__import__("os").getenv("REFRESH_DAYS", "7"))  # 0 turns the weekly refresh off
MIN_KEEP = 0.5   # refuse a refresh that would drop more than half of a source


class RefreshError(RuntimeError):
    pass


_running = threading.Lock()  # one refresh at a time (weekly timer and the admin button can't overlap)


def _get(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "found-refresh/1.0 (Yale student project)", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30, context=TLS) as resp:
        return resp.read(20_000_000).decode("utf-8", "replace")


def fetch_tsai() -> tuple[list[dict], list[dict]]:
    first = json.loads(_get(f"{TSAI_BASE}/api/posts?page=1"))
    posts = list(first["posts"])
    for page in range(2, int(first.get("pages") or 1) + 1):
        posts += json.loads(_get(f"{TSAI_BASE}/api/posts?page={page}"))["posts"]
    upcoming = json.loads(_get(f"{TSAI_BASE}/api/upcoming"))["upcoming"]
    return posts, upcoming


def fetch_pitchbook() -> list[dict]:
    page = _get(PITCHBOOK_PAGE)
    for src in re.findall(r'<script[^>]+src="([^"]+\.js)"', page):
        js = _get(src if src.startswith("http") else "https://www.yalepitchbook.com" + src)
        url = re.search(r"https://[a-z0-9]+\.supabase\.co", js)
        key = re.search(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", js)
        if url and key:
            headers = {"apikey": key.group(0), "Authorization": f"Bearer {key.group(0)}"}
            return json.loads(_get(f"{url.group(0)}/rest/v1/startups_public?select=*", headers))
    raise RefreshError("couldn't find the directory's data feed on yalepitchbook.com (the site may have changed)")


def _check(name: str, records: list[dict], required: tuple[str, ...], previous: int) -> None:
    if not isinstance(records, list) or not records:
        raise RefreshError(f"{name}: no records returned")
    missing = [f for f in required if f not in records[0]]
    if missing:
        raise RefreshError(f"{name}: records are missing fields {missing} (the source format changed)")
    if previous and len(records) < previous * MIN_KEEP:
        raise RefreshError(f"{name}: only {len(records)} records vs {previous} last time; refusing to apply")


def _previous_count(file: str) -> int:
    path = SOURCES / file
    return json.loads(path.read_text())["count"] if path.exists() else 0


def _save(file: str, source: str, records: list[dict]) -> None:
    (SOURCES / "previous").mkdir(parents=True, exist_ok=True)
    if (SOURCES / file).exists():
        shutil.copy2(SOURCES / file, SOURCES / "previous" / file)
    payload = {"source": source, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "count": len(records), "records": records}
    (SOURCES / file).write_text(json.dumps(payload, indent=1, ensure_ascii=False))


def last_success() -> str | None:
    """When the data was last refreshed: the newest successful refresh, else the snapshot's own date."""
    with connect() as conn:
        row = conn.execute("SELECT MAX(finished_at) FROM source_refreshes WHERE status = 'ok'").fetchone()
    if row and row[0]:
        return row[0]
    path = SOURCES / "pitchbook_startups.json"
    return json.loads(path.read_text())["fetched_at"] if path.exists() else None


def next_due() -> str | None:
    last = last_success()
    if not REFRESH_DAYS or not last:
        return None
    return (datetime.fromisoformat(last) + timedelta(days=REFRESH_DAYS)).isoformat(timespec="seconds")


def is_due() -> bool:
    due = next_due()
    return bool(due) and datetime.now(timezone.utc) >= datetime.fromisoformat(due)


def run_refresh(trigger: str) -> dict:
    """Download, check, save snapshots, sync the database. Every attempt is logged in source_refreshes."""
    if not _running.acquire(blocking=False):
        return {"status": "skipped", "error": "A refresh is already running."}
    try:
        return _run(trigger)
    finally:
        _running.release()


def _run(trigger: str) -> dict:
    with connect() as conn:
        rid = conn.execute("INSERT INTO source_refreshes (started_at, trigger, status) VALUES (?,?,'running')",
                           (now(), trigger)).lastrowid
    try:
        pitchbook = fetch_pitchbook()
        posts, upcoming = fetch_tsai()
        _check("Yale Startup Directory", pitchbook, ("id", "name", "description", "industry", "stage", "team"),
               _previous_count("pitchbook_startups.json"))
        _check("Tsai CITY posts", posts, ("id", "type", "title", "description"), _previous_count("tsai_posts.json"))
        _check("Tsai CITY expected deadlines", upcoming, ("name", "type"), _previous_count("tsai_upcoming.json") // 2)
        with connect() as conn:
            stats = sync_sources(conn, pitchbook, posts, upcoming)
        _save("pitchbook_startups.json", PITCHBOOK_PAGE, pitchbook)
        _save("tsai_posts.json", TSAI_BASE + "/", posts)
        _save("tsai_upcoming.json", TSAI_BASE + "/", upcoming)
        stats |= {"pitchbook_records": len(pitchbook), "tsai_posts": len(posts), "tsai_upcoming": len(upcoming)}
        with connect() as conn:
            conn.execute("UPDATE source_refreshes SET status='ok', finished_at=?, stats_json=? WHERE id=?",
                         (now(), json.dumps(stats), rid))
        print(f"[refresh] ok ({trigger}): {stats}", flush=True)
        return {"status": "ok", **stats}
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"[:500]
        with connect() as conn:
            conn.execute("UPDATE source_refreshes SET status='failed', finished_at=?, error=? WHERE id=?", (now(), msg, rid))
        print(f"[refresh] failed ({trigger}): {msg}", flush=True)
        return {"status": "failed", "error": msg}


def history(limit: int = 10) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM source_refreshes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(r), "stats": json.loads(r["stats_json"]) if r["stats_json"] else None} for r in rows]


if __name__ == "__main__":
    from db import init_db
    init_db()
    result = run_refresh("command line")
    print(json.dumps(result, indent=1))
    sys.exit(0 if result["status"] == "ok" else 1)
