"""Feature tests for the member-facing flows graders try: founder card, messaging both ways, the LinkedIn link, and a
member-submitted startup going through admin approval. Runs a throwaway server + database on port 8043 (your real
database is never touched). Writes output/feature_tests.json.   .venv/bin/python scripts/feature_tests.py"""
import _setup  # noqa: F401

import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 8043
BASE = f"http://127.0.0.1:{PORT}"
DB = Path(tempfile.mkdtemp(prefix="found-features-")) / "test.db"
RESULTS = []


def record(name, passed, detail):
    RESULTS.append({"test": name, "passed": bool(passed), "detail": detail})
    print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")


class Client:
    def __init__(self, email=None, password="found2026", admin=False):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        if email:
            self.call("POST", "/api/admin/login" if admin else "/api/auth/login", {"email": email, "password": password})

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with self.op.open(req, timeout=30) as r:
                txt = r.read().decode()
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            txt = e.read().decode()
            try:
                return e.code, json.loads(txt)
            except ValueError:
                return e.code, txt


def main():
    env = {**os.environ, "FOUND_DB": str(DB), "FOUND_DEV_MODE": "1", "MAIL_MODE": "outbox", "REFRESH_DAYS": "0",
           "FRONTEND_URL": BASE, "PYDANTIC_AI_NO_BANNER": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        run()
    finally:
        proc.terminate()
    out = {"ran_at": time.strftime("%Y-%m-%d %H:%M"), "passed": sum(r["passed"] for r in RESULTS), "total": len(RESULTS),
           "results": RESULTS}
    (_setup.OUTPUT / "feature_tests.json").write_text(json.dumps(out, indent=1))
    print(f"\n{out['passed']}/{out['total']} passed")


def run():
    member = Client("demo@yale.edu")
    founder = Client("test.founder@yale.edu")

    s, found = member.call("GET", "/api/startups?q=Bulldog%20Test")
    card = found[0]["founder"] if found else None
    record("Demo listing shows its founder card", bool(card) and card["first_name"] == "Test" and card["linkedin_url"],
           f"{found[0]['name'] if found else '—'} → founder {card and card['first_name']} {card and card['last_name']}, "
           f"LinkedIn {card and card['linkedin_url']}")

    s, conv = member.call("POST", "/api/conversations", {"user_id": card["id"]})
    s2, msg = member.call("POST", f"/api/conversations/{conv['id']}/messages", {"body": "Hi! Is Bulldog Test Co. hiring?"})
    record("Member can message a founder from the founder card", s == 200 and s2 == 201,
           f"conversation {conv.get('id')} with {conv['other']['first_name']} {conv['other']['last_name']}; message → HTTP {s2}")

    s, inbox = founder.call("GET", "/api/conversations")
    thread = next((c for c in inbox if c["other"]["first_name"] == "Madison"), None)
    s2, msgs = founder.call("GET", f"/api/conversations/{thread['id']}/messages") if thread else (0, [])
    record("Founder receives the message", bool(thread) and any("hiring" in m["body"] for m in msgs),
           f"founder inbox shows '{thread and thread['last_message']}' from {thread and thread['other']['first_name']}")

    s, _ = founder.call("POST", f"/api/conversations/{thread['id']}/messages", {"body": "Not yet, but happy to chat!"})
    s2, msgs = member.call("GET", f"/api/conversations/{conv['id']}/messages")
    record("Founder replies and the member sees it", s == 201 and msgs[-1]["body"].startswith("Not yet"),
           f"thread has {len(msgs)} messages; last: '{msgs[-1]['body']}'")

    outsider = Client("dan@yale.edu")
    s, _ = outsider.call("GET", f"/api/conversations/{conv['id']}/messages")
    record("Other members can't read the conversation", s == 404, f"third member reading the thread → HTTP {s}")

    s, b = member.call("PATCH", "/api/me", {"linkedin_url": "https://evil.example.com/me"})
    s2, me = member.call("PATCH", "/api/me", {"linkedin_url": "linkedin.com/in/demo-member-test"})
    record("LinkedIn link: only LinkedIn profile links are saved", s == 422 and me["linkedin_url"] == "https://www.linkedin.com/in/demo-member-test",
           f"other site → HTTP {s}; 'linkedin.com/in/demo-member-test' saved as {me.get('linkedin_url')}")

    s, sub = member.call("POST", "/api/startups", {"name": "Elm Street Test Labs", "tagline": "Member-submitted test startup",
                                                    "industries": ["Technology"], "affiliations": ["Yale SOM"], "stage": "Idea"})
    s2, public = member.call("GET", "/api/startups?q=Elm%20Street%20Test")
    record("Member-submitted startup waits for review, hidden", s == 201 and sub["status"] == "pending" and public == [],
           f"created as '{sub.get('status')}'; public search returns {len(public)}")

    admin = Client("admin@yale.edu", admin=True)
    s, queue = admin.call("GET", "/api/admin/startups")
    s2, ok = admin.call("POST", f"/api/admin/startups/{sub['id']}/approve", {})
    s3, public = member.call("GET", "/api/startups?q=Elm%20Street%20Test")
    pf = public[0]["founder"] if public else None
    record("Admin approves it and it goes live with the member as founder",
           any(x["id"] == sub["id"] for x in queue) and ok["status"] == "listed" and pf and pf["linkedin_url"],
           f"in admin queue: yes; after approve: '{ok.get('status')}'; public card founder {pf and pf['first_name']} "
           f"{pf and pf['last_name']} with LinkedIn {pf and pf['linkedin_url']}")


main()
