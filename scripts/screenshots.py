"""Capture the screenshots used in report.html and slides.html (needs Playwright; dev-only).
Run against a server started on a COPY of the database:  <python-with-playwright> scripts/screenshots.py http://localhost:8042 <db copy>"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, DB = sys.argv[1], sys.argv[2]
OUT = Path(__file__).resolve().parent.parent / "output" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def shot(page, name, full=False):
    page.wait_for_timeout(450)
    page.screenshot(path=str(OUT / f"{name}.jpg"), type="jpeg", quality=80, full_page=full)
    print("saved", name)


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()

    # ---- public site
    pg.goto(BASE + "/"); pg.wait_for_selector(".startup-card"); shot(pg, "01_explore")
    pg.mouse.wheel(0, 640); shot(pg, "02_directory")
    pg.goto(BASE + "/opportunities"); pg.wait_for_selector(".opp-card"); shot(pg, "03_opportunities")
    pg.goto(BASE + "/"); pg.fill(".search input", "Home Catalyst"); pg.wait_for_timeout(700)
    pg.locator(".startup-card .stretched").first.click(); pg.wait_for_selector(".stats"); shot(pg, "04_corrected_listing")

    # ---- Scout: a real run (the trace in the report) and the per-visitor limit
    pg.goto(BASE + "/"); pg.wait_for_selector(".scout-fab"); pg.click(".scout-fab")
    pg.fill(".scout-input input", "climate startups making revenue"); pg.click(".scout-input button")
    pg.wait_for_selector(".bubble-row.assistant .bubble:not(.typing)", timeout=60000); shot(pg, "05_scout_run")
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE scout_usage SET tokens = 99999 WHERE key LIKE 'visitor:%' AND day = ?", (date.today().isoformat(),))
    pg.fill(".scout-input input", "fintech startups"); pg.click(".scout-input button")
    pg.wait_for_selector(".bubble.tired", timeout=30000); shot(pg, "06_scout_limit")
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM scout_usage")

    # ---- verification gates
    pg2 = ctx.new_page()
    pg2.goto(BASE + "/signup"); pg2.fill("input >> nth=0", "Eve"); pg2.fill("input >> nth=1", "Outsider")
    pg2.fill("input[type=email]", "eve@gmail.com"); pg2.fill("input[type=password] >> nth=0", "password123")
    pg2.fill("input[type=password] >> nth=1", "password123"); pg2.click("button.btn-dark"); pg2.wait_for_selector(".error")
    shot(pg2, "07_yale_only")
    pg2.fill("input[type=email]", "sam.founder@yale.edu"); pg2.fill("input >> nth=0", "Sam"); pg2.fill("input >> nth=1", "Founder")
    pg2.click("button.btn-dark"); pg2.wait_for_selector("text=Check your inbox")
    pg2.goto(BASE + "/profile"); pg2.wait_for_selector(".verify-banner"); shot(pg2, "08_verify_gate")
    pg2.goto(BASE + "/api/dev/email"); shot(pg2, "09_verification_email")
    href = pg2.locator("a").first.get_attribute("href").replace("http://localhost:8042", BASE)
    pg2.goto(href); pg2.wait_for_selector("text=Your Yale email is verified")
    pg2.goto(BASE + "/profile"); pg2.click(".btn-linkedin"); pg2.wait_for_selector("text=Development stand-in")
    pg2.click("text=Sign in (dev)"); pg2.wait_for_selector("text=LinkedIn connected."); shot(pg2, "10_profile_verified")
    pg2.goto(BASE + "/"); pg2.fill(".search input", "Daemo"); pg2.wait_for_timeout(700)
    pg2.locator(".startup-card .stretched").first.click(); pg2.click("text=Claim this startup"); pg2.wait_for_selector(".claim-option")
    shot(pg2, "11_claim_options")
    pg2.click("text=Request a manual review"); pg2.fill("input[placeholder^='e.g. Co-founder']", "Co-founder & CTO")
    pg2.fill("input[placeholder^='https://www.linkedin.com/in']", "https://www.linkedin.com/in/sam-founder")
    pg2.fill("textarea", "I co-founded Daemo AI in 2024; my LinkedIn still lists my previous role.")
    pg2.click("text=Send for review"); pg2.wait_for_selector("text=Request sent")
    pg2.goto(BASE + "/events"); pg2.wait_for_timeout(500)

    # ---- admin console
    pa = ctx.new_page()
    pa.goto(BASE + "/admin/"); pa.wait_for_selector(".login"); shot(pa, "12_admin_login")
    pa.fill("input[type=email]", "admin@yale.edu"); pa.fill("input[type=password]", "found2026"); pa.click(".btn.primary")
    pa.wait_for_selector(".stats"); shot(pa, "13_admin_dashboard")
    pa.click("a[href='/admin/claims']"); pa.wait_for_selector(".card"); shot(pa, "14_admin_claim")
    pa.click("a[href='/admin/audits']"); pa.wait_for_selector(".card"); shot(pa, "15_admin_audits")
    pa.click("a[href='/admin/listings']"); pa.wait_for_selector(".table"); pa.fill(".search", "Mundaly"); pa.wait_for_timeout(600)
    pa.click("table button.btn.sm"); pa.wait_for_selector(".audit-result .card", timeout=120000); shot(pa, "16_audit_run")

    # ---- events with moderator ideas (make Sam a moderator on this copy)
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE users SET is_moderator = 1 WHERE email = 'sam.founder@yale.edu'")
    pg2.reload(); pg2.goto(BASE + "/events"); pg2.click("text=+ Host an event"); pg2.wait_for_selector(".ideas"); pg2.click(".idea >> nth=0")
    shot(pg2, "17_moderator_ideas")
    b.close()
