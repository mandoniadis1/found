"""Refresh the source snapshots in data/sources/ from the two public sites found. combines.

    <python with playwright> fetch_sources.py

Both sites load their data with JavaScript, so this opens each page in headless Chromium and saves the
JSON the page itself requests:
  - https://www.yalepitchbook.com/directory   → data/sources/pitchbook_startups.json  (Yale Startup Directory)
  - https://tsaicity.useplop.com/             → data/sources/tsai_posts.json + tsai_upcoming.json
                                                (Tsai CITY "Yale Startup Opportunities" board)

Then rebuild the database with:  python db.py --reset
Needs `pip install playwright && playwright install chromium` (not in requirements.txt; only needed to refresh).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "data" / "sources"


def capture(url: str, wanted: list[str]) -> dict[str, object]:
    """Load url and return the JSON bodies of responses whose URL contains each wanted fragment."""
    found: dict[str, object] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_response(resp):
            for key in wanted:
                if key in resp.url and key not in found and resp.status == 200:
                    try:
                        found[key] = resp.json()
                    except Exception:
                        pass

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(3000)
        browser.close()
    missing = [k for k in wanted if k not in found]
    if missing:
        raise RuntimeError(f"{url}: did not see data requests for {missing}")
    return found


def save(name: str, source_url: str, records) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"source": source_url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "count": len(records), "records": records}
    (OUT / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(f"{name}: {len(records)} records")


if __name__ == "__main__":
    pb = capture("https://www.yalepitchbook.com/directory", ["startups_public"])
    save("pitchbook_startups.json", "https://www.yalepitchbook.com/directory", pb["startups_public"])

    tsai = capture("https://tsaicity.useplop.com/", ["/api/posts", "/api/upcoming"])
    save("tsai_posts.json", "https://tsaicity.useplop.com/", tsai["/api/posts"]["posts"])
    save("tsai_upcoming.json", "https://tsaicity.useplop.com/", tsai["/api/upcoming"]["upcoming"])
