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

    s, by_name = member.call("GET", "/api/members/search?q=test")
    s2, by_startup = member.call("GET", "/api/members/search?q=Bulldog")
    s3, hidden = member.call("GET", "/api/members/search?q=admin")
    record("Find someone to message by name or startup", any(m["first_name"] == "Test" for m in by_name)
           and any(m["startup"] == "Bulldog Test Co." for m in by_startup) and hidden == [],
           f"'test' → {[m['first_name'] + ' ' + m['last_name'] for m in by_name]}; 'Bulldog' → {[m['startup'] for m in by_startup]}; "
           f"'admin' (not opted in, not a founder) → {hidden}")

    newbie = Client()
    newbie.call("POST", "/api/auth/signup", {"first_name": "New", "last_name": "Member", "email": "new.member@yale.edu", "password": "password123"})
    s, b = newbie.call("GET", "/api/members/search?q=test")
    record("Unverified accounts can't search members", s == 403, f"before verifying the Yale email → HTTP {s}")

    s, withf = member.call("GET", "/api/startups?has_founder=true")
    record("'Founder on found.' filter shows only messageable startups", s == 200 and withf and all(x["founder"] for x in withf),
           f"{len(withf)} startup(s), all with a founder on found.: {[x['name'] for x in withf]}")

    joiner = Client("dan@yale.edu")
    s, me = joiner.call("PATCH", "/api/me", {"open_to_join": True, "join_roles": ["Engineering"], "join_industries": ["Robotics"],
                                             "join_commitment": "Internship", "join_pitch": "Builds robots, wants a summer internship"})
    record("A member with no startup can opt in to being found", s == 200 and me["open_to_join"] and me["join_roles"] == ["Engineering"],
           f"open_to_join={me.get('open_to_join')}, roles={me.get('join_roles')}, commitment={me.get('join_commitment')}")

    s, b = joiner.call("GET", "/api/people/open")
    s2, people = founder.call("GET", "/api/people/open")
    names = [f"{p['first_name']} {p['last_name']}" for p in people] if s2 == 200 else []
    record("Only founders can browse people open to joining", s == 403 and s2 == 200 and "Handsome Dan" in names
           and all("email" not in p for p in people),
           f"non-founder → HTTP {s}; founder sees {names} (no emails returned)")

    s, eng = founder.call("GET", "/api/people/open?role=Engineering")
    s2, des = founder.call("GET", "/api/people/open?role=Design&industry=Robotics")
    record("Founders can filter by role and industry", any(p["first_name"] == "Handsome" for p in eng)
           and not any(p["first_name"] == "Handsome" for p in des),
           f"role=Engineering → {[p['first_name'] for p in eng]}; role=Design → {[p['first_name'] for p in des]}")

    joiner.call("PATCH", "/api/me", {"open_to_join": False})
    s, people = founder.call("GET", "/api/people/open")
    record("Opting out hides the member again", not any(p["first_name"] == "Handsome" for p in people),
           f"after opting out, founder sees {[p['first_name'] for p in people]}")

    s, board = member.call("GET", "/api/join")
    record("Join page gathers every way in", s == 200 and len(board["startups"]) > 0 and len(board["asks"]) > 0,
           f"{len(board['startups'])} startups looking for people, {len(board['asks'])} co-founder searches / startup asks, "
           f"{len(board['events'])} upcoming events")

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
