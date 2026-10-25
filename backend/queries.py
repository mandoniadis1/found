"""Read queries shared by the API routes and the AI scout's tools, so both see the same data."""

from __future__ import annotations

import sqlite3

from models import (
    OPPORTUNITY_CATEGORIES, STAGES, Event, ExpectedDeadline, FilterOption, Filters, Opportunity, PublicUser, Startup,
)

STARTUP_SELECT = """
SELECT s.*,
       (SELECT group_concat(industry, '|') FROM startup_industries i WHERE i.startup_id = s.id) AS industries_csv,
       (SELECT group_concat(affiliation, '|') FROM startup_affiliations a WHERE a.startup_id = s.id) AS affiliations_csv,
       u.id AS f_id, u.first_name AS f_first, u.last_name AS f_last, u.school AS f_school,
       u.headline AS f_headline, u.linkedin_url AS f_linkedin
FROM startups s LEFT JOIN users u ON u.id = s.founder_id
"""

STAGE_ORDER = "CASE s.stage " + " ".join(f"WHEN '{st}' THEN {i}" for i, st in enumerate(STAGES)) + " ELSE 99 END"


def public_user(row: sqlite3.Row, prefix: str = "") -> PublicUser:
    g = lambda k: row[prefix + k]  # noqa: E731
    return PublicUser(id=g("id"), first_name=g("first"), last_name=g("last"), school=g("school"),
                      headline=g("headline"), linkedin_url=g("linkedin"))


def user_row_to_public(row: sqlite3.Row) -> PublicUser:
    return PublicUser(id=row["id"], first_name=row["first_name"], last_name=row["last_name"], school=row["school"],
                      headline=row["headline"], linkedin_url=row["linkedin_url"])


def to_startup(row: sqlite3.Row) -> Startup:
    split = lambda v: sorted(v.split("|")) if v else []  # noqa: E731
    return Startup(
        id=row["id"], name=row["name"], tagline=row["tagline"], description=row["description"],
        industries=split(row["industries_csv"]), affiliations=split(row["affiliations_csv"]), stage=row["stage"],
        website=row["website"], looking_for=row["looking_for"], founders_public=row["founders_public"],
        round=row["round"], raised_usd=row["raised_usd"], team_size=row["team_size"], location=row["location"],
        founded_year=row["founded_year"], hiring=bool(row["hiring"]), source=row["source"], status=row["status"],
        correction_note=row["correction_note"],
        claimed=row["founder_id"] is not None, founder_verified_via=row["founder_verified_via"],
        founder=public_user(row, "f_") if row["f_id"] else None,
    )


def search_startups(
    conn: sqlite3.Connection,
    q: str | None = None,
    industries: list[str] | None = None,
    stages: list[str] | None = None,
    affiliations: list[str] | None = None,
    rounds: list[str] | None = None,
    locations: list[str] | None = None,
    team_min: int | None = None,
    team_max: int | None = None,
    raised_min: int | None = None,
    hiring: bool | None = None,
    has_ask: bool | None = None,
    sort: str = "name",
    limit: int = 500,
) -> list[Startup]:
    where, args = ["s.status = 'listed'"], []
    if q:
        where.append("(s.name LIKE ? OR s.tagline LIKE ? OR s.description LIKE ? OR s.looking_for LIKE ?"
                     " OR EXISTS (SELECT 1 FROM startup_industries i WHERE i.startup_id = s.id AND i.industry LIKE ?))")
        args += [f"%{q}%"] * 5
    for table, col, values in (("startup_industries", "industry", industries),
                               ("startup_affiliations", "affiliation", affiliations)):
        if values:
            where.append(f"EXISTS (SELECT 1 FROM {table} t WHERE t.startup_id = s.id AND t.{col} IN"
                         f" ({','.join('?' * len(values))}))")
            args += values
    for col, values in (("s.stage", stages), ("s.round", rounds), ("s.location", locations)):
        if values:
            where.append(f"{col} IN ({','.join('?' * len(values))})")
            args += values
    for clause, value in (("s.team_size >= ?", team_min), ("s.team_size <= ?", team_max), ("s.raised_usd >= ?", raised_min)):
        if value is not None:
            where.append(clause)
            args.append(value)
    if hiring:
        where.append("s.hiring = 1")
    if has_ask:
        where.append("s.looking_for IS NOT NULL")
    order = {"name": "s.name COLLATE NOCASE", "newest": "s.id DESC", "stage": f"{STAGE_ORDER} DESC, s.name COLLATE NOCASE",
             "raised": "s.raised_usd IS NULL, s.raised_usd DESC"}.get(sort, "s.name COLLATE NOCASE")
    sql = STARTUP_SELECT + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {order} LIMIT ?"
    return [to_startup(r) for r in conn.execute(sql, [*args, limit])]


def get_startup(conn: sqlite3.Connection, startup_id: int) -> Startup | None:
    row = conn.execute(STARTUP_SELECT + " WHERE s.id = ?", (startup_id,)).fetchone()
    return to_startup(row) if row else None


def set_startup_tags(conn: sqlite3.Connection, startup_id: int, industries: list[str], affiliations: list[str]) -> None:
    conn.execute("DELETE FROM startup_industries WHERE startup_id = ?", (startup_id,))
    conn.execute("DELETE FROM startup_affiliations WHERE startup_id = ?", (startup_id,))
    conn.executemany("INSERT INTO startup_industries VALUES (?,?)", [(startup_id, i) for i in dict.fromkeys(industries)])
    conn.executemany("INSERT INTO startup_affiliations VALUES (?,?)", [(startup_id, a) for a in dict.fromkeys(affiliations)])


def filter_options(conn: sqlite3.Connection) -> Filters:
    def counts(sql: str, order: list[str] | None = None) -> list[FilterOption]:
        opts = [FilterOption(value=r[0], count=r[1]) for r in conn.execute(sql)]
        if order:
            opts.sort(key=lambda o: order.index(o.value) if o.value in order else 99)
        return opts

    return Filters(
        industries=counts("SELECT industry, COUNT(*) FROM startup_industries i JOIN startups s ON s.id = i.startup_id"
                          " WHERE s.status = 'listed' GROUP BY industry ORDER BY COUNT(*) DESC"),
        stages=counts("SELECT stage, COUNT(*) FROM startups WHERE status = 'listed' GROUP BY stage", STAGES),
        affiliations=counts("SELECT affiliation, COUNT(*) FROM startup_affiliations a JOIN startups s ON s.id = a.startup_id"
                            " WHERE s.status = 'listed' GROUP BY affiliation ORDER BY COUNT(*) DESC"),
        rounds=counts("SELECT round, COUNT(*) FROM startups WHERE status = 'listed' AND round IS NOT NULL GROUP BY round"),
        locations=counts("SELECT location, COUNT(*) FROM startups WHERE status = 'listed' AND location IS NOT NULL"
                         " GROUP BY location ORDER BY COUNT(*) DESC"),
        with_team_size=conn.execute("SELECT COUNT(*) FROM startups WHERE status = 'listed' AND team_size IS NOT NULL").fetchone()[0],
        with_funding=conn.execute("SELECT COUNT(*) FROM startups WHERE status = 'listed' AND raised_usd IS NOT NULL").fetchone()[0],
        total=conn.execute("SELECT COUNT(*) FROM startups WHERE status = 'listed'").fetchone()[0],
    )


# ---------------------------------------------------------------- opportunities

def to_opportunity(row: sqlite3.Row) -> Opportunity:
    return Opportunity(
        id=row["id"], category=row["category"], category_label=OPPORTUNITY_CATEGORIES.get(row["category"], row["category"]),
        title=row["title"], org=row["org"], description=row["description"], website=row["website"],
        location=row["location"], ideal_candidate=row["ideal_candidate"], apply_url=row["apply_url"],
        apply_email=row["apply_email"], deadline=row["deadline"], rolling=bool(row["rolling"]),
        start_date=row["start_date"], grand_prize=row["grand_prize"], curator_note=row["curator_note"],
        posted_at=row["posted_at"],
    )


def search_opportunities(conn: sqlite3.Connection, q: str | None = None, categories: list[str] | None = None,
                         deadline_within_days: int | None = None, sort: str = "deadline",
                         limit: int = 500) -> list[Opportunity]:
    # Hide posts the board has expired, and dated deadlines that have already passed.
    where = ["(o.expires_at IS NULL OR o.expires_at >= datetime('now'))",
             "(o.deadline IS NULL OR o.deadline >= date('now', 'localtime'))"]
    args: list = []
    if q:
        where.append("(o.title LIKE ? OR o.org LIKE ? OR o.description LIKE ? OR o.location LIKE ?)")
        args += [f"%{q}%"] * 4
    if categories:
        where.append(f"o.category IN ({','.join('?' * len(categories))})")
        args += categories
    if deadline_within_days is not None:
        where.append("o.deadline IS NOT NULL AND o.deadline <= date('now', 'localtime', ?)")
        args.append(f"+{deadline_within_days} days")
    order = {"deadline": "o.deadline IS NULL, o.deadline, o.posted_at DESC",
             "newest": "o.posted_at DESC"}.get(sort, "o.posted_at DESC")
    sql = f"SELECT o.* FROM opportunities o WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?"
    return [to_opportunity(r) for r in conn.execute(sql, [*args, limit])]


def get_opportunity(conn: sqlite3.Connection, opp_id: int) -> Opportunity | None:
    row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    return to_opportunity(row) if row else None


def opportunity_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT category, COUNT(*) FROM opportunities WHERE (expires_at IS NULL OR expires_at >= datetime('now'))"
        " AND (deadline IS NULL OR deadline >= date('now', 'localtime')) GROUP BY category")
    return {r[0]: r[1] for r in rows}


def expected_deadlines(conn: sqlite3.Connection) -> list[ExpectedDeadline]:
    rows = conn.execute("SELECT * FROM expected_deadlines ORDER BY expected_year, expected_month, name")
    return [ExpectedDeadline(**dict(r)) for r in rows]


# ---------------------------------------------------------------- events

EVENT_SELECT = """
SELECT e.*, s.name AS host_name,
       u.id AS o_id, u.first_name AS o_first, u.last_name AS o_last, u.school AS o_school,
       u.headline AS o_headline, u.linkedin_url AS o_linkedin,
       (SELECT COUNT(*) FROM rsvps r WHERE r.event_id = e.id) AS attending,
       EXISTS (SELECT 1 FROM rsvps r WHERE r.event_id = e.id AND r.user_id = ?) AS mine
FROM events e
JOIN users u ON u.id = e.organizer_id
LEFT JOIN startups s ON s.id = e.host_startup_id
"""


def to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"], title=row["title"], description=row["description"], kind=row["kind"], sector=row["sector"],
        host_startup=row["host_name"], host_startup_id=row["host_startup_id"], organizer=public_user(row, "o_"),
        starts_at=row["starts_at"], location=row["location"], capacity=row["capacity"], attending=row["attending"],
        i_am_going=bool(row["mine"]),
    )


def list_events(conn: sqlite3.Connection, viewer_id: int | None = None, sector: str | None = None,
                upcoming_only: bool = True) -> list[Event]:
    where, args = [], [viewer_id or -1]
    if sector:
        where.append("e.sector = ?")
        args.append(sector)
    if upcoming_only:
        where.append("e.starts_at >= date('now', 'localtime')")
    sql = EVENT_SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY e.starts_at"
    return [to_event(r) for r in conn.execute(sql, args)]


def get_event(conn: sqlite3.Connection, event_id: int, viewer_id: int | None = None) -> Event | None:
    row = conn.execute(EVENT_SELECT + " WHERE e.id = ?", (viewer_id or -1, event_id)).fetchone()
    return to_event(row) if row else None
