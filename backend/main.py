"""found. API (FastAPI). Run from backend/:

    ../.venv/bin/uvicorn main:app --reload --port 8030

Interactive docs at http://127.0.0.1:8030/docs
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

import config
import mailer
import queries
import refresh
import verification as verify
from agent import ScoutUnavailable, run_scout, scout_budget
from auth import COOKIE_NAME, hash_password, new_token, verify_password
from db import connect, init_db, now, save_correction
from models import (
    AFFILIATIONS, INDUSTRIES, JOIN_COMMITMENTS, JOIN_ROLES, OPPORTUNITY_CATEGORIES, ROUNDS, STAGES, Joiner, AdminDecisionIn, ClaimOptions, ClaimRequest,
    CompanyEmailClaimIn, Conversation, Event, EventIn, ExpectedDeadline, Filters, LoginIn, ManualClaimIn, Message,
    MessageIn, Opportunity, ProfileIn, PublicUser, ScoutIn, ScoutOut, SignupIn, StartConversationIn, Startup, StartupIn,
    User,
)

async def _weekly_refresh_loop() -> None:
    """Checks once an hour; when the data is REFRESH_DAYS old (default 7), re-downloads both source sites."""
    while True:
        try:
            if refresh.is_due():
                await asyncio.to_thread(refresh.run_refresh, "weekly")
        except Exception as exc:  # never let the timer crash the server
            print(f"[refresh] scheduler error: {exc}", flush=True)
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_weekly_refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="found. API", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5185", "http://127.0.0.1:5185", "http://localhost:5186", "http://127.0.0.1:5186",
                   "http://localhost:8030", "http://127.0.0.1:8030"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
init_db()

VISITOR_COOKIE = "found_visitor"
ADMIN_COOKIE = "found_admin"  # separate login for the admin console; only sent to /api/admin


# ---------------------------------------------------------------- session helpers

def _split(v: str | None) -> list[str]:
    return [x for x in (v or "").split("|") if x]


def to_user(row: sqlite3.Row) -> User:
    with connect() as conn:
        founder = conn.execute("SELECT 1 FROM startups WHERE founder_id = ? AND status = 'listed'", (row["id"],)).fetchone()
    return User(
        open_to_join=bool(row["open_to_join"]), join_roles=_split(row["join_roles"]),
        join_industries=_split(row["join_industries"]), join_commitment=row["join_commitment"],
        join_pitch=row["join_pitch"], is_founder=bool(founder),
        id=row["id"], first_name=row["first_name"], last_name=row["last_name"], email=row["email"],
        school=row["school"], headline=row["headline"], email_verified=bool(row["email_verified"]),
        linkedin_url=row["linkedin_url"],
        is_moderator=bool(row["is_moderator"]),
        is_admin=bool(row["email_verified"]) and (row["email"].lower() in config.ADMIN_EMAILS or (
            config.DEV_MODE and row["email"].lower() == config.DEMO_ADMIN_EMAIL)),
    )


def load_user(conn: sqlite3.Connection, user_id: int) -> User:
    return to_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def current_user(found_session: Annotated[str | None, Cookie()] = None) -> User | None:
    if not found_session:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.kind = 'member'",
            (found_session,)
        ).fetchone()
    return to_user(row) if row else None


def require_user(user: Annotated[User | None, Depends(current_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Log in first.")
    return user


def require_verified(user: Annotated[User, Depends(require_user)]) -> User:
    if not user.email_verified:
        raise HTTPException(403, "Verify your Yale email first. Check your inbox for the link, or resend it from your profile.")
    return user


def require_admin(found_admin: Annotated[str | None, Cookie()] = None) -> User:
    """Admin console requests use their own session (cookie found_admin), not the public-site login."""
    if not found_admin:
        raise HTTPException(401, "Admin login required.")
    with connect() as conn:
        row = conn.execute("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
                           " WHERE s.token = ? AND s.kind = 'admin'", (found_admin,)).fetchone()
    user = to_user(row) if row else None
    if not user or not user.is_admin:
        raise HTTPException(401, "Admin login required.")
    return user


Viewer = Annotated[User | None, Depends(current_user)]
Member = Annotated[User, Depends(require_user)]
Verified = Annotated[User, Depends(require_verified)]
Admin = Annotated[User, Depends(require_admin)]


def start_session(response: Response, user_id: int) -> None:
    token = new_token()
    with connect() as conn:
        conn.execute("INSERT INTO sessions (token, user_id, created_at, kind) VALUES (?,?,?,'member')",
                     (token, user_id, now()))
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)


def send_yale_verification(conn: sqlite3.Connection, user_id: int, email: str, first_name: str) -> None:
    token = verify.create_email_token(conn, "verify_yale", user_id, email)
    mailer.send(
        email, "Verify your Yale email for found.", f"Welcome to found., {first_name}",
        "Confirm this is your Yale email address so you can message founders, RSVP to events, and claim your startup.",
        "Verify my email", f"{config.FRONTEND_URL}/api/auth/verify-email?token={token}",
    )


# ---------------------------------------------------------------- config & auth

@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/dev/email", response_class=HTMLResponse)
def dev_email(user: Member, to: str | None = None) -> HTMLResponse:
    """LOCAL MODE ONLY: open the newest outbox email sent to you (or to a work email you used to claim a startup),
    so the email links can be tested without a real mail server."""
    if not (config.DEV_MODE and config.MAIL_MODE == "outbox"):
        raise HTTPException(404, "Not found.")
    allowed = {user.email.lower()}
    with connect() as conn:
        allowed |= {r[0] for r in conn.execute("SELECT lower(work_email) FROM claim_requests WHERE user_id = ? AND"
                                                " work_email IS NOT NULL", (user.id,))}
    target = (to or user.email).lower()
    if target not in allowed:
        raise HTTPException(404, "Not found.")
    files = sorted(mailer.OUTBOX.glob(f"*_{target}.html")) if mailer.OUTBOX.exists() else []
    if not files:
        raise HTTPException(404, "No email for that address yet.")
    return HTMLResponse(files[-1].read_text())


@app.get("/api/config")
def site_config() -> dict:
    return {"dev_mode": config.DEV_MODE, "mail_mode": config.MAIL_MODE}


@app.post("/api/auth/signup", response_model=User)
def signup(body: SignupIn, response: Response) -> User:
    email = body.email.lower().strip()
    if not verify.is_yale_email(email):
        raise HTTPException(422, "Use your @yale.edu email. found. is for the Yale community.")
    with connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists. Log in instead.")
        try:
            uid = conn.execute(
                "INSERT INTO users (first_name, last_name, email, password_hash, school, created_at) VALUES (?,?,?,?,?,?)",
                (body.first_name.strip(), body.last_name.strip(), email, hash_password(body.password), body.school, now()),
            ).lastrowid
        except sqlite3.IntegrityError:  # a double-click raced the check above
            raise HTTPException(409, "An account with that email already exists. Log in instead.")
        user = load_user(conn, uid)
        try:
            send_yale_verification(conn, uid, email, body.first_name.strip())
        except Exception as exc:  # account still created; they can use "Resend link" once mail works
            print(f"[mailer] verification email to {email} failed: {exc}", flush=True)
    start_session(response, uid)
    return user


@app.post("/api/auth/resend-verification", status_code=204)
def resend_verification(user: Member) -> None:
    if user.email_verified:
        return
    with connect() as conn:
        try:
            send_yale_verification(conn, user.id, user.email, user.first_name)
        except Exception as exc:
            print(f"[mailer] resend to {user.email} failed: {exc}", flush=True)
            raise HTTPException(503, "We couldn't send the email right now. Please try again in a few minutes.")


@app.get("/api/auth/verify-email")
def verify_email(token: str) -> RedirectResponse:
    with connect() as conn:
        row = verify.use_email_token(conn, token, "verify_yale")
        if row:
            conn.execute("UPDATE users SET email_verified = 1 WHERE id = ? AND email = ?", (row["user_id"], row["email"]))
    return RedirectResponse(f"{config.FRONTEND_URL}/verified?result={'email_ok' if row else 'invalid'}", status_code=303)


@app.post("/api/auth/login", response_model=User)
def login(body: LoginIn, response: Response) -> User:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email.lower().strip(),)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Wrong email or password.")
    start_session(response, row["id"])
    return to_user(row)


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, found_session: Annotated[str | None, Cookie()] = None) -> None:
    if found_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (found_session,))
    response.delete_cookie(COOKIE_NAME)


@app.get("/api/me", response_model=User | None)
def me(user: Viewer) -> User | None:
    return user


LINKEDIN_RE = re.compile(r"^(?:https?://)?(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9\-_%]{2,100})/?(?:[?#].*)?$", re.I)


def clean_linkedin(url: str) -> str | None:
    """'' clears the link; otherwise it must be a LinkedIn profile URL. Not verified: members paste their own."""
    url = url.strip()
    if not url:
        return None
    m = LINKEDIN_RE.match(url)
    if not m:
        raise HTTPException(422, "That doesn't look like a LinkedIn profile link (linkedin.com/in/your-name).")
    return f"https://www.linkedin.com/in/{m.group(1)}"


@app.patch("/api/me", response_model=User)
def update_me(body: ProfileIn, user: Member) -> User:
    with connect() as conn:
        conn.execute("UPDATE users SET school = COALESCE(?, school), headline = COALESCE(?, headline) WHERE id = ?",
                     (body.school, body.headline, user.id))
        if body.linkedin_url is not None:
            conn.execute("UPDATE users SET linkedin_url = ? WHERE id = ?", (clean_linkedin(body.linkedin_url), user.id))
        if body.join_roles is not None and (bad := [r for r in body.join_roles if r not in JOIN_ROLES]):
            raise HTTPException(422, f"Unknown role: {', '.join(bad)}.")
        if body.join_industries is not None and (bad := [i for i in body.join_industries if i not in INDUSTRIES]):
            raise HTTPException(422, f"Unknown industry: {', '.join(bad)}.")
        if body.join_commitment and body.join_commitment not in JOIN_COMMITMENTS:
            raise HTTPException(422, f"Commitment must be one of: {', '.join(JOIN_COMMITMENTS)}.")
        if body.open_to_join and not user.email_verified:
            raise HTTPException(403, "Verify your Yale email before making yourself visible to founders.")
        for col, val in (("open_to_join", None if body.open_to_join is None else int(body.open_to_join)),
                         ("join_roles", None if body.join_roles is None else "|".join(dict.fromkeys(body.join_roles))),
                         ("join_industries", None if body.join_industries is None else "|".join(dict.fromkeys(body.join_industries))),
                         ("join_commitment", None if body.join_commitment is None else (body.join_commitment or None)),
                         ("join_pitch", None if body.join_pitch is None else (body.join_pitch.strip() or None))):
            if val is not None or (col in ("join_commitment", "join_pitch") and getattr(body, col) == ""):
                conn.execute(f"UPDATE users SET {col} = ? WHERE id = ?", (val, user.id))
        return load_user(conn, user.id)


# ---------------------------------------------------------------- joining a startup

@app.get("/api/join")
def join_board() -> dict:
    """Every way into a startup, in one place: listings that are hiring or posted an ask, the Tsai CITY board's startup
    asks (co-founder searches, startups looking for new owners), and upcoming events."""
    with connect() as conn:
        startups = queries.search_startups(conn, has_ask=True, sort="newest")
        hiring = [s for s in queries.search_startups(conn, hiring=True, sort="newest") if s.id not in {x.id for x in startups}]
        asks = queries.search_opportunities(conn, categories=["asks"], sort="newest")
        events = queries.list_events(conn)[:4]
        open_people = conn.execute("SELECT COUNT(*) FROM users WHERE open_to_join = 1 AND email_verified = 1").fetchone()[0]
    return {"startups": [s.model_dump() for s in startups + hiring], "asks": [a.model_dump() for a in asks],
            "events": [e.model_dump() for e in events], "open_people": open_people,
            "roles": JOIN_ROLES, "commitments": JOIN_COMMITMENTS}


@app.get("/api/people/open", response_model=list[Joiner])
def people_open(user: Verified, role: str | None = None, industry: str | None = None,
                commitment: str | None = None) -> list[Joiner]:
    """Members who opted in to being found. Only verified founders (a listed startup on found.) and admins can browse
    it, so it can't be scraped by anyone who just signs up."""
    if not (user.is_founder or user.is_admin):
        raise HTTPException(403, "Only founders with a startup on found. can browse people open to joining. "
                                 "Add or claim your startup first.")
    with connect() as conn:
        rows = conn.execute("SELECT * FROM users WHERE open_to_join = 1 AND email_verified = 1 AND id != ? "
                            "ORDER BY created_at DESC", (user.id,)).fetchall()
    people = [Joiner(id=r["id"], first_name=r["first_name"], last_name=r["last_name"], school=r["school"],
                     headline=r["headline"], linkedin_url=r["linkedin_url"], roles=_split(r["join_roles"]),
                     industries=_split(r["join_industries"]), commitment=r["join_commitment"], pitch=r["join_pitch"])
              for r in rows]
    if role:
        people = [p for p in people if role in p.roles or "Any role" in p.roles]
    if industry:
        people = [p for p in people if industry in p.industries or not p.industries]
    if commitment:
        people = [p for p in people if p.commitment in (commitment, "Flexible", None)]
    return people


@app.post("/api/me/moderator", response_model=User)
def become_moderator(user: Verified) -> User:
    """Moderators host events. They need a verified Yale email, so events come from real Yale people."""
    with connect() as conn:
        conn.execute("UPDATE users SET is_moderator = 1 WHERE id = ?", (user.id,))
        return load_user(conn, user.id)


# ---------------------------------------------------------------- startups

@app.get("/api/filters", response_model=Filters)
def filters() -> Filters:
    with connect() as conn:
        return queries.filter_options(conn)


@app.get("/api/options")
def options() -> dict:
    return {"industries": INDUSTRIES, "stages": STAGES, "affiliations": AFFILIATIONS, "rounds": ROUNDS,
            "join_roles": JOIN_ROLES, "join_commitments": JOIN_COMMITMENTS,
            "opportunity_categories": OPPORTUNITY_CATEGORIES}


@app.get("/api/startups", response_model=list[Startup])
def list_startups(
    q: str | None = None,
    industry: Annotated[list[str] | None, Query()] = None,
    stage: Annotated[list[str] | None, Query()] = None,
    affiliation: Annotated[list[str] | None, Query()] = None,
    round: Annotated[list[str] | None, Query()] = None,
    location: Annotated[list[str] | None, Query()] = None,
    team_min: int | None = None,
    team_max: int | None = None,
    raised_min: int | None = None,
    hiring: bool | None = None,
    has_ask: bool | None = None,
    sort: str = "name",
) -> list[Startup]:
    with connect() as conn:
        return queries.search_startups(conn, q=q, industries=industry, stages=stage, affiliations=affiliation,
                                       rounds=round, locations=location, team_min=team_min, team_max=team_max,
                                       raised_min=raised_min, hiring=hiring, has_ask=has_ask, sort=sort)


@app.get("/api/startups/mine", response_model=list[Startup])
def my_startups(user: Member) -> list[Startup]:
    with connect() as conn:
        rows = conn.execute(queries.STARTUP_SELECT + " WHERE s.founder_id = ? ORDER BY s.name", (user.id,))
        return [queries.to_startup(r) for r in rows]


@app.get("/api/startups/{startup_id}", response_model=Startup)
def startup_detail(startup_id: int, user: Viewer) -> Startup:
    with connect() as conn:
        s = queries.get_startup(conn, startup_id)
    # Startups waiting for review are only visible to the person who submitted them and to admins.
    if not s or (s.status != "listed" and not (user and (user.is_admin or (s.founder and s.founder.id == user.id)))):
        raise HTTPException(404, "Startup not found.")
    return s


def _check_startup(body: StartupIn) -> None:
    if bad := [i for i in body.industries if i not in INDUSTRIES]:
        raise HTTPException(422, f"Unknown industry: {', '.join(bad)}.")
    if body.stage not in STAGES:
        raise HTTPException(422, f"Stage must be one of: {', '.join(STAGES)}.")
    if body.round and body.round not in ROUNDS:
        raise HTTPException(422, f"Round must be one of: {', '.join(ROUNDS)}.")


def _startup_values(body: StartupIn) -> tuple:
    blank = lambda v: (v or "").strip() or None  # noqa: E731
    return (body.name.strip(), body.tagline.strip(), blank(body.description), body.stage, blank(body.website),
            blank(body.looking_for), body.round or None, body.raised_usd, body.team_size, blank(body.location),
            body.founded_year, int(body.hiring))


@app.post("/api/startups", response_model=Startup, status_code=201)
def create_startup(body: StartupIn, user: Verified) -> Startup:
    """New startups go to the admin review queue and stay hidden until approved."""
    _check_startup(body)
    with connect() as conn:
        sid = conn.execute(
            "INSERT INTO startups (name, tagline, description, stage, website, looking_for, round, raised_usd, team_size,"
            " location, founded_year, hiring, founder_id, founder_verified_via, status, source, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'admin_review','pending','member',?)",
            (*_startup_values(body), user.id, now()),
        ).lastrowid
        queries.set_startup_tags(conn, sid, body.industries, body.affiliations)
        return queries.get_startup(conn, sid)


@app.put("/api/startups/{startup_id}", response_model=Startup)
def update_startup(startup_id: int, body: StartupIn, user: Verified) -> Startup:
    """The verified founder can edit their listing. Admins can edit any listing to fix wrong source data; for
    imported listings that fix is also saved to data/sources/corrections.json so it survives a data refresh."""
    _check_startup(body)
    with connect() as conn:
        row = conn.execute("SELECT founder_id, source, source_id FROM startups WHERE id = ?", (startup_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Startup not found.")
        if row["founder_id"] != user.id and not user.is_admin:
            raise HTTPException(403, "Only the verified founder can edit this listing.")
        if user.is_admin and row["founder_id"] != user.id and row["source"] == "yale_pitchbook":
            reason = (body.correction_reason or "").strip() or "Corrected by found."
            save_correction(row["source_id"], body.name.strip(), {
                "tagline": body.tagline.strip(), "description": (body.description or "").strip() or None,
                "stage": body.stage, "website": (body.website or "").strip() or None,
                "looking_for": (body.looking_for or "").strip() or None,
                "industries": body.industries, "affiliations": body.affiliations,
            }, reason)
            conn.execute("UPDATE startups SET correction_note = ? WHERE id = ?", (reason, startup_id))
        conn.execute(
            "UPDATE startups SET name=?, tagline=?, description=?, stage=?, website=?, looking_for=?, round=?,"
            " raised_usd=?, team_size=?, location=?, founded_year=?, hiring=? WHERE id = ?",
            (*_startup_values(body), startup_id),
        )
        queries.set_startup_tags(conn, startup_id, body.industries, body.affiliations)
        return queries.get_startup(conn, startup_id)


# ---------------------------------------------------------------- claiming a listing

def _claimable(conn: sqlite3.Connection, startup_id: int, user: User) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM startups WHERE id = ? AND status = 'listed'", (startup_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Startup not found.")
    if row["founder_id"] is not None:
        raise HTTPException(409, "This startup has already been claimed.")
    return row


def _claim_row_to_model(r: sqlite3.Row, admin: bool = False) -> ClaimRequest:
    c = ClaimRequest(
        id=r["id"], startup_id=r["startup_id"], startup_name=r["startup_name"], method=r["method"], status=r["status"],
        full_name=r["full_name"], role=r["role"], work_email=r["work_email"],
        linkedin_profile_url=r["linkedin_profile_url"], evidence_url=r["evidence_url"], note=r["note"],
        admin_note=r["admin_note"], created_at=r["created_at"], decided_at=r["decided_at"],
    )
    if admin:
        c.requester_name = f"{r['first_name']} {r['last_name']}"
        c.requester_email = r["email"]
        c.requester_linkedin_url = r["linkedin_url"]
    return c


CLAIM_SELECT = """
SELECT c.*, s.name AS startup_name, u.first_name, u.last_name, u.email, u.linkedin_url
FROM claim_requests c JOIN startups s ON s.id = c.startup_id JOIN users u ON u.id = c.user_id
"""


@app.get("/api/startups/{startup_id}/claim-options", response_model=ClaimOptions)
def claim_options(startup_id: int, user: Member) -> ClaimOptions:
    with connect() as conn:
        row = conn.execute("SELECT website FROM startups WHERE id = ?", (startup_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Startup not found.")
        pending = conn.execute("SELECT 1 FROM claim_requests WHERE startup_id = ? AND user_id = ? AND status IN"
                               " ('pending', 'email_sent')", (startup_id, user.id)).fetchone()
    return ClaimOptions(company_domain=verify.company_domain(row["website"]), has_pending_request=bool(pending))


@app.post("/api/startups/{startup_id}/claim/company-email", status_code=202)
def claim_by_company_email(startup_id: int, body: CompanyEmailClaimIn, user: Verified) -> dict:
    """Automatic path: we email a link to an address on the startup's own domain. Clicking it proves the claim."""
    with connect() as conn:
        s = _claimable(conn, startup_id, user)
        domain = verify.company_domain(s["website"])
        work_email = body.work_email.lower().strip()
        if not domain:
            raise HTTPException(422, "This listing's website isn't on its own domain, so request a manual review instead.")
        if not verify.email_matches_domain(work_email, domain):
            raise HTTPException(422, f"Use an email address at {domain}.")
        cid = conn.execute(
            "INSERT INTO claim_requests (startup_id, user_id, method, status, full_name, work_email, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (startup_id, user.id, "company_email", "email_sent", f"{user.first_name} {user.last_name}", work_email, now()),
        ).lastrowid
        token = verify.create_email_token(conn, "claim_company_email", user.id, work_email, claim_id=cid)
    mailer.send(
        work_email, f"Confirm you're with {s['name']} on found.", f"Claim {s['name']} on found.",
        f"{user.first_name} {user.last_name} ({user.email}) asked to manage the {s['name']} listing on found. "
        "Click below to confirm you work there.", "Confirm and claim", f"{config.FRONTEND_URL}/api/claims/verify?token={token}",
    )
    return {"sent_to": work_email}


@app.get("/api/claims/verify")
def verify_claim_email(token: str) -> RedirectResponse:
    with connect() as conn:
        row = verify.use_email_token(conn, token, "claim_company_email")
        claim = conn.execute("SELECT * FROM claim_requests WHERE id = ?", (row["claim_id"],)).fetchone() if row else None
        startup = conn.execute("SELECT founder_id FROM startups WHERE id = ?", (claim["startup_id"],)).fetchone() if claim else None
        if not claim or claim["status"] != "email_sent" or startup["founder_id"] is not None:
            return RedirectResponse(f"{config.FRONTEND_URL}/verified?result=invalid", status_code=303)
        conn.execute("UPDATE claim_requests SET status = 'approved', decided_at = ?, decided_by = 'company email link'"
                     " WHERE id = ?", (now(), claim["id"]))
        conn.execute("UPDATE startups SET founder_id = ?, founder_verified_via = 'company_email' WHERE id = ?",
                     (claim["user_id"], claim["startup_id"]))
    return RedirectResponse(f"{config.FRONTEND_URL}/verified?result=claim_ok&startup={claim['startup_id']}", status_code=303)


@app.post("/api/startups/{startup_id}/claim/manual", response_model=ClaimRequest, status_code=201)
def claim_by_manual_review(startup_id: int, body: ManualClaimIn, user: Verified) -> ClaimRequest:
    """Fallback: the founder can't verify automatically, so the request goes to the site owner's review queue."""
    with connect() as conn:
        _claimable(conn, startup_id, user)
        if conn.execute("SELECT 1 FROM claim_requests WHERE startup_id = ? AND user_id = ? AND status = 'pending'",
                        (startup_id, user.id)).fetchone():
            raise HTTPException(409, "You already have a review request for this startup.")
        cid = conn.execute(
            "INSERT INTO claim_requests (startup_id, user_id, method, status, full_name, role, work_email,"
            " linkedin_profile_url, evidence_url, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (startup_id, user.id, "manual_review", "pending", body.full_name.strip(), body.role.strip(),
             (body.work_email or "").strip() or None, body.linkedin_profile_url.strip(),
             (body.evidence_url or "").strip() or None, body.note.strip(), now()),
        ).lastrowid
        return _claim_row_to_model(conn.execute(CLAIM_SELECT + " WHERE c.id = ?", (cid,)).fetchone())


@app.get("/api/claims/mine", response_model=list[ClaimRequest])
def my_claims(user: Member) -> list[ClaimRequest]:
    with connect() as conn:
        rows = conn.execute(CLAIM_SELECT + " WHERE c.user_id = ? ORDER BY c.id DESC", (user.id,))
        return [_claim_row_to_model(r) for r in rows]


# ---------------------------------------------------------------- admin console (separate site, site owner only)

@app.post("/api/admin/login", response_model=User)
def admin_login(body: LoginIn, response: Response) -> User:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (body.email.lower().strip(),)).fetchone()
    user = to_user(row) if row and verify_password(body.password, row["password_hash"]) else None
    if not user or not user.is_admin:  # same message either way: don't reveal who is an admin
        raise HTTPException(401, "Wrong email or password, or this account isn't an admin.")
    token = new_token()
    with connect() as conn:
        conn.execute("INSERT INTO sessions (token, user_id, created_at, kind) VALUES (?,?,?,'admin')",
                     (token, user.id, now()))
    response.set_cookie(ADMIN_COOKIE, token, httponly=True, samesite="strict", path="/api/admin",
                        max_age=60 * 60 * 8)  # 8-hour admin sessions
    return user


@app.post("/api/admin/logout", status_code=204)
def admin_logout(response: Response, found_admin: Annotated[str | None, Cookie()] = None) -> None:
    if found_admin:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ? AND kind = 'admin'", (found_admin,))
    response.delete_cookie(ADMIN_COOKIE, path="/api/admin")


@app.get("/api/admin/me", response_model=User)
def admin_me(admin: Admin) -> User:
    return admin


@app.get("/api/admin/overview")
def admin_overview(admin: Admin) -> dict:
    from datetime import date
    with connect() as conn:
        one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731
        today = date.today().isoformat()
        return {
            "pending_claims": one("SELECT COUNT(*) FROM claim_requests WHERE status = 'pending'"),
            "pending_startups": one("SELECT COUNT(*) FROM startups WHERE status = 'pending'"),
            "members": one("SELECT COUNT(*) FROM users WHERE is_test_account = 0"),
            "verified_members": one("SELECT COUNT(*) FROM users WHERE email_verified = 1 AND is_test_account = 0"),
            "linkedin_members": one("SELECT COUNT(*) FROM users WHERE linkedin_url IS NOT NULL"),
            "open_to_join": one("SELECT COUNT(*) FROM users WHERE open_to_join = 1"),
            "moderators": one("SELECT COUNT(*) FROM users WHERE is_moderator = 1"),
            "listed_startups": one("SELECT COUNT(*) FROM startups WHERE status = 'listed'"),
            "claimed_startups": one("SELECT COUNT(*) FROM startups WHERE founder_id IS NOT NULL AND status = 'listed'"),
            "corrected_startups": one("SELECT COUNT(*) FROM startups WHERE correction_note IS NOT NULL"),
            "upcoming_events": one("SELECT COUNT(*) FROM events WHERE starts_at >= date('now', 'localtime')"),
            "scout_tokens_today": one("SELECT COALESCE(SUM(tokens), 0) FROM scout_usage WHERE day = ? AND key = 'site'", today),
            "scout_questions_today": one("SELECT COALESCE(SUM(messages), 0) FROM scout_usage WHERE day = ? AND key = 'site'", today),
            "scout_daily_budget": config.SCOUT_DAILY_TOKENS,
            "mail_mode": config.MAIL_MODE,
        }


@app.get("/api/admin/members")
def admin_members(admin: Admin) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT u.id, u.first_name, u.last_name, u.email, u.school, u.email_verified, u.linkedin_url,"
            " u.is_moderator, u.is_test_account, u.open_to_join,"
            " u.created_at, (SELECT COUNT(*) FROM startups s WHERE s.founder_id = u.id) AS startups"
            " FROM users u ORDER BY u.created_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/admin/scout-usage")
def admin_scout_usage(admin: Admin) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT day, tokens, messages FROM scout_usage WHERE key = 'site' ORDER BY day DESC LIMIT 14")
        return [dict(r) for r in rows]


@app.get("/api/admin/data-sources")
def admin_data_sources(admin: Admin) -> dict:
    with connect() as conn:
        counts = {
            "startups_listed": conn.execute("SELECT COUNT(*) FROM startups WHERE status='listed' AND source='yale_pitchbook'").fetchone()[0],
            "startups_removed": conn.execute("SELECT COUNT(*) FROM startups WHERE status='removed'").fetchone()[0],
            "opportunities": conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0],
            "expected_deadlines": conn.execute("SELECT COUNT(*) FROM expected_deadlines").fetchone()[0],
        }
    return {"refresh_days": refresh.REFRESH_DAYS, "last_success": refresh.last_success(), "next_due": refresh.next_due(),
            "counts": counts, "history": refresh.history()}


@app.post("/api/admin/data-sources/refresh")
async def admin_refresh_now(admin: Admin) -> dict:
    return await asyncio.to_thread(refresh.run_refresh, "admin")


@app.get("/api/admin/startups/all", response_model=list[Startup])
def admin_all_startups(admin: Admin, q: str | None = None) -> list[Startup]:
    with connect() as conn:
        sql = queries.STARTUP_SELECT + (" WHERE s.name LIKE ? OR s.tagline LIKE ?" if q else "") + " ORDER BY s.name COLLATE NOCASE"
        rows = conn.execute(sql, (f"%{q}%", f"%{q}%") if q else ())
        return [queries.to_startup(r) for r in rows]


# ---------------------------------------------------------------- Listing Auditor (agent 2, admin only)

def _audit_row(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "startup_id": r["startup_id"], "verdict": r["verdict"], "status": r["status"],
            "created_at": r["created_at"], "decided_at": r["decided_at"], "result": json.loads(r["result_json"])}


@app.post("/api/admin/startups/{startup_id}/audit")
async def admin_audit_startup(startup_id: int, admin: Admin) -> dict:
    from auditor import audit_listing
    with connect() as conn:
        s = queries.get_startup(conn, startup_id)
    if not s:
        raise HTTPException(404, "Startup not found.")
    try:
        res = await audit_listing(s)
    except Exception as exc:
        print(f"[auditor] error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(503, "The auditor couldn't finish. Try again in a minute.")
    status = "proposed" if res.report.verdict == "needs_changes" else "info"
    with connect() as conn:
        aid = conn.execute(
            "INSERT INTO listing_audits (startup_id, verdict, status, result_json, input_tokens, cached_tokens,"
            " output_tokens, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (startup_id, res.report.verdict, status, res.model_dump_json(), res.input_tokens, res.cached_tokens,
             res.output_tokens, res.cost_usd, now()),
        ).lastrowid
        return _audit_row(conn.execute("SELECT * FROM listing_audits WHERE id = ?", (aid,)).fetchone())


@app.get("/api/admin/audits")
def admin_audits(admin: Admin) -> list[dict]:
    with connect() as conn:
        return [_audit_row(r) for r in conn.execute("SELECT * FROM listing_audits ORDER BY id DESC LIMIT 200")]


@app.post("/api/admin/audits/{audit_id}/{decision}")
def admin_decide_audit(audit_id: int, decision: str, admin: Admin) -> dict:
    """Approve applies the auditor's suggestion to the listing and records it in data/sources/corrections.json."""
    if decision not in ("apply", "dismiss"):
        raise HTTPException(404, "Not found.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM listing_audits WHERE id = ?", (audit_id,)).fetchone()
        if not row or row["status"] != "proposed":
            raise HTTPException(409, "This audit has no pending suggestion.")
        if decision == "apply":
            res = json.loads(row["result_json"])
            rep, sid = res["report"], row["startup_id"]
            s = queries.get_startup(conn, sid)
            tagline = rep.get("suggested_tagline") or s.tagline
            industries = rep.get("suggested_industries") or s.industries
            reason = f"{rep['summary']} (Found by the Listing Auditor; approved by an admin.)"
            conn.execute("UPDATE startups SET tagline = ?, correction_note = ? WHERE id = ?", (tagline, reason, sid))
            queries.set_startup_tags(conn, sid, industries, s.affiliations)
            if s.source == "yale_pitchbook":
                src = conn.execute("SELECT source_id FROM startups WHERE id = ?", (sid,)).fetchone()[0]
                save_correction(src, s.name, {"tagline": tagline, "industries": industries}, reason)
        conn.execute("UPDATE listing_audits SET status = ?, decided_at = ? WHERE id = ?",
                     ("applied" if decision == "apply" else "dismissed", now(), audit_id))
        return _audit_row(conn.execute("SELECT * FROM listing_audits WHERE id = ?", (audit_id,)).fetchone())


# ---------------------------------------------------------------- admin review queue (site owner only)

@app.get("/api/admin/claims", response_model=list[ClaimRequest])
def admin_claims(admin: Admin, status: str = "pending") -> list[ClaimRequest]:
    with connect() as conn:
        rows = conn.execute(CLAIM_SELECT + " WHERE c.status = ? ORDER BY c.id", (status,))
        return [_claim_row_to_model(r, admin=True) for r in rows]


@app.post("/api/admin/claims/{claim_id}/{decision}", response_model=ClaimRequest)
def admin_decide_claim(claim_id: int, decision: str, body: AdminDecisionIn, admin: Admin) -> ClaimRequest:
    if decision not in ("approve", "deny"):
        raise HTTPException(404, "Not found.")
    with connect() as conn:
        claim = conn.execute("SELECT * FROM claim_requests WHERE id = ?", (claim_id,)).fetchone()
        if not claim or claim["status"] != "pending":
            raise HTTPException(409, "This request isn't waiting for review.")
        if decision == "approve":
            owner = conn.execute("SELECT founder_id FROM startups WHERE id = ?", (claim["startup_id"],)).fetchone()
            if owner["founder_id"] is not None:
                raise HTTPException(409, "Someone else already claimed this startup.")
            conn.execute("UPDATE startups SET founder_id = ?, founder_verified_via = 'admin_review' WHERE id = ?",
                         (claim["user_id"], claim["startup_id"]))
        conn.execute("UPDATE claim_requests SET status = ?, admin_note = ?, decided_by = ?, decided_at = ? WHERE id = ?",
                     ("approved" if decision == "approve" else "denied", body.admin_note, admin.email, now(), claim_id))
        return _claim_row_to_model(conn.execute(CLAIM_SELECT + " WHERE c.id = ?", (claim_id,)).fetchone(), admin=True)


@app.get("/api/admin/startups", response_model=list[Startup])
def admin_pending_startups(admin: Admin) -> list[Startup]:
    with connect() as conn:
        rows = conn.execute(queries.STARTUP_SELECT + " WHERE s.status = 'pending' ORDER BY s.id")
        return [queries.to_startup(r) for r in rows]


@app.post("/api/admin/startups/{startup_id}/{decision}", response_model=Startup)
def admin_decide_startup(startup_id: int, decision: str, admin: Admin) -> Startup:
    if decision not in ("approve", "reject"):
        raise HTTPException(404, "Not found.")
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM startups WHERE id = ? AND status = 'pending'", (startup_id,)).fetchone():
            raise HTTPException(409, "This startup isn't waiting for review.")
        conn.execute("UPDATE startups SET status = ? WHERE id = ?",
                     ("listed" if decision == "approve" else "rejected", startup_id))
        return queries.get_startup(conn, startup_id)


# ---------------------------------------------------------------- opportunities (Tsai CITY board)

@app.get("/api/opportunities", response_model=list[Opportunity])
def opportunities(
    q: str | None = None,
    category: Annotated[list[str] | None, Query()] = None,
    within_days: int | None = None,
    sort: str = "deadline",
) -> list[Opportunity]:
    with connect() as conn:
        return queries.search_opportunities(conn, q=q, categories=category, deadline_within_days=within_days, sort=sort)


@app.get("/api/opportunities/counts")
def opportunity_counts() -> dict[str, int]:
    with connect() as conn:
        return queries.opportunity_counts(conn)


@app.get("/api/opportunities/{opp_id}", response_model=Opportunity)
def opportunity(opp_id: int) -> Opportunity:
    with connect() as conn:
        o = queries.get_opportunity(conn, opp_id)
    if not o:
        raise HTTPException(404, "Opportunity not found.")
    return o


@app.get("/api/deadlines", response_model=list[ExpectedDeadline])
def deadlines() -> list[ExpectedDeadline]:
    with connect() as conn:
        return queries.expected_deadlines(conn)


# ---------------------------------------------------------------- events

@app.get("/api/events", response_model=list[Event])
def events(user: Viewer, sector: str | None = None) -> list[Event]:
    with connect() as conn:
        return queries.list_events(conn, viewer_id=user.id if user else None, sector=sector)


@app.post("/api/events", response_model=Event, status_code=201)
def create_event(body: EventIn, user: Verified) -> Event:
    if not user.is_moderator:
        raise HTTPException(403, "Only moderators can host events. Sign up as a moderator on your profile.")
    with connect() as conn:
        if body.kind == "startup":
            if body.host_startup_id is None:
                raise HTTPException(422, "Pick which of your startups is hosting.")
            owner = conn.execute("SELECT founder_id FROM startups WHERE id = ? AND status = 'listed'",
                                 (body.host_startup_id,)).fetchone()
            if not owner or owner["founder_id"] != user.id:
                raise HTTPException(403, "You can only host startup events for your own (verified) startup.")
        eid = conn.execute(
            "INSERT INTO events (title, description, kind, sector, host_startup_id, organizer_id, starts_at, location,"
            " capacity, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (body.title, body.description, body.kind, body.sector or None,
             body.host_startup_id if body.kind == "startup" else None, user.id, body.starts_at, body.location,
             body.capacity, now()),
        ).lastrowid
        conn.execute("INSERT INTO rsvps VALUES (?,?,?)", (eid, user.id, now()))
        return queries.get_event(conn, eid, user.id)


@app.post("/api/events/{event_id}/rsvp", response_model=Event)
def toggle_rsvp(event_id: int, user: Verified) -> Event:
    with connect() as conn:
        ev = queries.get_event(conn, event_id, user.id)
        if not ev:
            raise HTTPException(404, "Event not found.")
        if ev.i_am_going:
            conn.execute("DELETE FROM rsvps WHERE event_id = ? AND user_id = ?", (event_id, user.id))
        elif ev.attending >= ev.capacity:
            raise HTTPException(409, "This event is full.")
        else:
            conn.execute("INSERT INTO rsvps VALUES (?,?,?)", (event_id, user.id, now()))
        return queries.get_event(conn, event_id, user.id)


# ---------------------------------------------------------------- messages (member to member)

@app.get("/api/members/{user_id}", response_model=PublicUser)
def member(user_id: int) -> PublicUser:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Member not found.")
    return queries.user_row_to_public(row)


@app.get("/api/conversations", response_model=list[Conversation])
def conversations(user: Member) -> list[Conversation]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, u.*,
                      (SELECT body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_body,
                      (SELECT created_at FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_at
               FROM conversations c
               JOIN users u ON u.id = CASE WHEN c.user_a = ? THEN c.user_b ELSE c.user_a END
               WHERE c.user_a = ? OR c.user_b = ?
               ORDER BY COALESCE(last_at, c.created_at) DESC""",
            (user.id, user.id, user.id),
        ).fetchall()
        return [Conversation(id=r[0], other=queries.user_row_to_public(r), last_message=r["last_body"],
                             last_at=r["last_at"]) for r in rows]


@app.post("/api/conversations", response_model=Conversation)
def start_conversation(body: StartConversationIn, user: Verified) -> Conversation:
    if body.user_id == user.id:
        raise HTTPException(422, "You can't message yourself.")
    a, b = sorted((user.id, body.user_id))
    with connect() as conn:
        other = conn.execute("SELECT * FROM users WHERE id = ?", (body.user_id,)).fetchone()
        if not other:
            raise HTTPException(404, "Member not found.")
        conn.execute("INSERT OR IGNORE INTO conversations (user_a, user_b, created_at) VALUES (?,?,?)", (a, b, now()))
        cid = conn.execute("SELECT id FROM conversations WHERE user_a = ? AND user_b = ?", (a, b)).fetchone()[0]
    return Conversation(id=cid, other=queries.user_row_to_public(other))


def _my_conversation(conn: sqlite3.Connection, cid: int, user: User) -> None:
    row = conn.execute("SELECT user_a, user_b FROM conversations WHERE id = ?", (cid,)).fetchone()
    if not row or user.id not in (row["user_a"], row["user_b"]):
        raise HTTPException(404, "Conversation not found.")


@app.get("/api/conversations/{cid}/messages", response_model=list[Message])
def messages(cid: int, user: Member) -> list[Message]:
    with connect() as conn:
        _my_conversation(conn, cid, user)
        rows = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY id", (cid,))
        return [Message(id=r["id"], sender_id=r["sender_id"], body=r["body"], created_at=r["created_at"]) for r in rows]


@app.post("/api/conversations/{cid}/messages", response_model=Message, status_code=201)
def send_message(cid: int, body: MessageIn, user: Verified) -> Message:
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "Message is empty.")
    with connect() as conn:
        _my_conversation(conn, cid, user)
        created = now()
        mid = conn.execute("INSERT INTO messages (conversation_id, sender_id, body, created_at) VALUES (?,?,?,?)",
                           (cid, user.id, text, created)).lastrowid
    return Message(id=mid, sender_id=user.id, body=text, created_at=created)


# ---------------------------------------------------------------- Scout helper (gpt-6-luna, budgeted)

def _scout_key(request: Request, response: Response, user: User | None) -> str:
    if user:
        return f"user:{user.id}"
    visitor = request.cookies.get(VISITOR_COOKIE)
    if not visitor:
        visitor = secrets.token_urlsafe(12)
        response.set_cookie(VISITOR_COOKIE, visitor, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 365)
    return f"visitor:{visitor}"


@app.get("/api/scout/status")
def scout_status(request: Request, response: Response, user: Viewer) -> dict:
    site_ok, visitor_ok = scout_budget(_scout_key(request, response, user))
    return {"site_available": site_ok, "visitor_available": visitor_ok}


@app.post("/api/scout", response_model=ScoutOut)
async def scout(body: ScoutIn, request: Request, response: Response, user: Viewer) -> ScoutOut:
    try:
        return await run_scout(body.message, body.history, user, _scout_key(request, response, user))
    except ScoutUnavailable as exc:
        raise HTTPException(429, f"{exc.scope}_limit")  # "site_limit" hides the helper; "visitor_limit" says come back
    except Exception as exc:  # model/network trouble: the page shows a friendly "try again" message
        print(f"[scout] error: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(503, "scout_error")


# ---------------------------------------------------------------- built web apps (one-command run: python run.py)
# The public site (frontend/dist) is served at / and the admin console (admin/dist) at /admin, so a fresh clone
# needs only Python. During development the Vite dev servers on 5185 / 5186 are used instead.

FRONTEND_DIST = config.ROOT / "frontend" / "dist"
ADMIN_DIST = config.ROOT / "admin" / "dist"


def _spa_file(dist, path: str):
    candidate = (dist / path).resolve()
    if path and candidate.is_file() and dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(404, "The web app isn't built. See README (npm run build), or use the dev servers.")
    return FileResponse(index)


@app.get("/admin", include_in_schema=False)
def admin_root() -> RedirectResponse:
    return RedirectResponse("/admin/")  # the admin app lives under /admin/ (without the slash it renders blank)


@app.get("/admin/{path:path}", include_in_schema=False)
def admin_app(path: str = ""):
    return _spa_file(ADMIN_DIST, path)


@app.get("/{path:path}", include_in_schema=False)
def public_app(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    return _spa_file(FRONTEND_DIST, path)
