"""Pydantic types: API request/response shapes and the assistant's structured reply."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

INDUSTRIES = [
    "Climate & Sustainability", "Consumer", "Education", "Fintech", "Health & Biotech", "Logistics", "Marketing",
    "Media & Entertainment", "Real Estate", "Robotics", "Social Impact", "Technology",
]
# Pitchbook's stages, in order from earliest to latest.
STAGES = ["Idea", "Building", "Proof of Concept", "Testing", "Launched: Pre-revenue", "Launched: Revenue", "Launched: Growth"]
AFFILIATIONS = [
    "Yale College", "Yale SOM", "Yale Graduate School", "Yale School of Medicine", "Yale School of Public Health",
    "Yale SEAS", "Yale Law School", "Yale School of the Environment", "Yale Jackson School", "Yale School of Architecture",
    "Yale Professor", "Yale Alumni",
]
ROUNDS = ["Bootstrapped", "Grant-funded", "Pre-seed", "Seed", "Series A", "Series B+"]
OPPORTUNITY_CATEGORIES = {
    "programs": "Accelerators, programs & events",
    "perks": "Perks & credits",
    "grants": "Grants",
    "competitions": "Competitions",
    "asks": "Startup asks",
}


# ---------------------------------------------------------------- users & auth

class User(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    school: str | None = None
    headline: str | None = None
    email_verified: bool = False
    linkedin_connected: bool = False
    linkedin_name: str | None = None
    linkedin_picture: str | None = None
    linkedin_dev_standin: bool = False
    is_moderator: bool = False
    is_admin: bool = False


class PublicUser(BaseModel):
    """What other members can see about a person (no email)."""
    id: int
    first_name: str
    last_name: str
    school: str | None = None
    headline: str | None = None
    linkedin_verified: bool = False  # signed in with LinkedIn


class SignupIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: str = Field(pattern=EMAIL, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    school: str | None = None


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=200)
    password: str


class ProfileIn(BaseModel):
    school: str | None = None
    headline: str | None = Field(default=None, max_length=140)


# ---------------------------------------------------------------- startups

class Startup(BaseModel):
    id: int
    name: str
    tagline: str
    description: str | None = None
    industries: list[str]
    affiliations: list[str]
    stage: str
    website: str | None = None
    looking_for: str | None = None
    founders_public: str | None = None
    # Only known once a founder claims the listing and fills them in.
    round: str | None = None
    raised_usd: int | None = None
    team_size: int | None = None
    location: str | None = None
    founded_year: int | None = None
    hiring: bool = False
    source: str
    correction_note: str | None = None
    status: str = "listed"
    claimed: bool = False
    founder_verified_via: str | None = None
    founder: PublicUser | None = None


class StartupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(min_length=1, max_length=400)
    description: str | None = Field(default=None, max_length=2000)
    industries: list[str] = Field(min_length=1, max_length=4)
    affiliations: list[str] = Field(min_length=1, max_length=4)
    stage: str
    website: str | None = None
    looking_for: str | None = Field(default=None, max_length=1500)
    round: str | None = None
    raised_usd: int | None = Field(default=None, ge=0)
    team_size: int | None = Field(default=None, ge=1, le=10_000)
    location: str | None = Field(default=None, max_length=80)
    founded_year: int | None = Field(default=None, ge=1950, le=2100)
    hiring: bool = False
    correction_reason: str | None = Field(default=None, max_length=500)  # admins: why the source data was wrong


class FilterOption(BaseModel):
    value: str
    count: int


class Filters(BaseModel):
    industries: list[FilterOption]
    stages: list[FilterOption]
    affiliations: list[FilterOption]
    rounds: list[FilterOption]      # empty until founders add a round
    locations: list[FilterOption]   # empty until founders add a location
    with_team_size: int             # how many listings have a team size
    with_funding: int               # how many listings have an amount raised
    total: int


# ---------------------------------------------------------------- claims & review

class CompanyEmailClaimIn(BaseModel):
    work_email: str = Field(pattern=EMAIL, max_length=200)


class ManualClaimIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    role: str = Field(min_length=2, max_length=120)
    work_email: str | None = Field(default=None, max_length=200)
    linkedin_profile_url: str = Field(min_length=10, max_length=300)
    evidence_url: str | None = Field(default=None, max_length=500)
    note: str = Field(min_length=10, max_length=2000)


class ClaimOptions(BaseModel):
    company_domain: str | None  # e.g. "daemo.ai"; None when the website isn't on the startup's own domain
    has_pending_request: bool = False


class ClaimRequest(BaseModel):
    id: int
    startup_id: int
    startup_name: str
    method: str
    status: str
    full_name: str | None = None
    role: str | None = None
    work_email: str | None = None
    linkedin_profile_url: str | None = None
    evidence_url: str | None = None
    note: str | None = None
    admin_note: str | None = None
    created_at: str
    decided_at: str | None = None
    # requester identity, shown to admins only
    requester_name: str | None = None
    requester_email: str | None = None
    requester_linkedin_name: str | None = None
    requester_linkedin_email: str | None = None
    requester_linkedin_dev_standin: bool = False


class AdminDecisionIn(BaseModel):
    admin_note: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------- opportunities (Tsai CITY board)

class Opportunity(BaseModel):
    id: int
    category: str
    category_label: str
    title: str
    org: str | None = None
    description: str | None = None
    website: str | None = None
    location: str | None = None
    ideal_candidate: str | None = None
    apply_url: str | None = None
    apply_email: str | None = None
    deadline: str | None = None
    rolling: bool = False
    start_date: str | None = None
    grand_prize: str | None = None
    curator_note: str | None = None
    posted_at: str | None = None


class ExpectedDeadline(BaseModel):
    id: int
    name: str
    category: str
    organizer: str | None = None
    website: str | None = None
    expected_window: str | None = None
    expected_month: int | None = None
    expected_year: int | None = None
    eligibility_note: str | None = None


# ---------------------------------------------------------------- events

class Event(BaseModel):
    id: int
    title: str
    description: str
    kind: Literal["startup", "sector"]
    sector: str | None = None
    host_startup: str | None = None
    host_startup_id: int | None = None
    organizer: PublicUser
    starts_at: str
    location: str
    capacity: int
    attending: int
    i_am_going: bool = False


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1500)
    kind: Literal["startup", "sector"]
    sector: str | None = None
    host_startup_id: int | None = None
    starts_at: str  # ISO "YYYY-MM-DDTHH:MM"
    location: str = Field(min_length=1, max_length=160)
    capacity: int = Field(ge=1, le=5000)


# ---------------------------------------------------------------- messages

class Message(BaseModel):
    id: int
    sender_id: int
    body: str
    created_at: str


class Conversation(BaseModel):
    id: int
    other: PublicUser
    last_message: str | None = None
    last_at: str | None = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class StartConversationIn(BaseModel):
    user_id: int


# ---------------------------------------------------------------- AI scout

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ScoutIn(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    history: list[ChatTurn] = []


Industry = Literal["Climate & Sustainability", "Consumer", "Education", "Fintech", "Health & Biotech", "Logistics",
                   "Marketing", "Media & Entertainment", "Real Estate", "Robotics", "Social Impact", "Technology"]
Stage = Literal["Idea", "Building", "Proof of Concept", "Testing", "Launched: Pre-revenue", "Launched: Revenue",
                "Launched: Growth"]
Affiliation = Literal["Yale College", "Yale SOM", "Yale Graduate School", "Yale School of Medicine",
                      "Yale School of Public Health", "Yale Professor", "Yale Alumni"]
Category = Literal["programs", "perks", "grants", "competitions", "asks"]


class ScoutQuery(BaseModel):
    """What the helper model returns: just search filters. Code runs the search and writes the reply."""
    kind: Literal["startups", "opportunities", "other"]
    keywords: str = ""
    industries: list[Industry] = []
    stages: list[Stage] = []
    affiliations: list[Affiliation] = []
    hiring_only: bool = False
    categories: list[Category] = []
    within_days: int | None = None


class ScoutOut(BaseModel):
    reply: str
    startups: list[Startup] = []
    events: list[Event] = []
    opportunities: list[Opportunity] = []
    tools_used: list[str] = []
    site_available: bool = True     # False once the whole site's daily budget is used up: the page hides the helper
    visitor_available: bool = True  # False once this visitor's daily budget is used up: "come back tomorrow"
