"""Searches Scout runs. The model never calls these directly: it only turns the question into filters (one cheap
call), and code runs the search and writes the reply. That keeps each question to a single small model call."""

from __future__ import annotations

import queries
from db import connect
from models import Opportunity, ScoutQuery, Startup

MAX_CARDS = 4

CATEGORY_WORDS = {"programs": "programs", "perks": "perks", "grants": "grants", "competitions": "competitions",
                  "asks": "startup asks"}


def find_startups(q: ScoutQuery) -> tuple[list[Startup], int]:
    with connect() as conn:
        results = queries.search_startups(conn, q=q.keywords or None, industries=q.industries or None,
                                          stages=q.stages or None, affiliations=q.affiliations or None,
                                          hiring=q.hiring_only or None, has_ask=q.looking_for_people or None)
    return results[:MAX_CARDS], len(results)


def find_opportunities(q: ScoutQuery) -> tuple[list[Opportunity], int]:
    with connect() as conn:
        results = queries.search_opportunities(conn, q=q.keywords or None, categories=q.categories or None,
                                               deadline_within_days=q.within_days)
    return results[:MAX_CARDS], len(results)


def describe(q: ScoutQuery, total: int) -> str:
    """A plain sentence built from the filters and the real result count (no model-written facts)."""
    if q.kind == "startups":
        bits = [", ".join(q.industries) if q.industries else ""]
        noun = "startup" if total == 1 else "startups"
        where = []
        if q.stages:
            where.append("at " + " or ".join(q.stages))
        if q.affiliations:
            where.append("from " + " or ".join(q.affiliations))
        if q.hiring_only:
            where.append("that are hiring")
        if q.looking_for_people:
            where.append("looking for people to join")
        if q.keywords:
            where.append(f'matching "{q.keywords}"')
        subject = " ".join(b for b in [*bits, noun] if b)
    else:
        noun = ", ".join(CATEGORY_WORDS.get(c, c) for c in q.categories) if q.categories else (
            "opportunity" if total == 1 else "opportunities")
        where = []
        if q.within_days:
            where.append(f"due in the next {q.within_days} days")
        if q.keywords:
            where.append(f'matching "{q.keywords}"')
        subject = noun
    detail = (" " + " ".join(where)) if where else ""
    if total == 0:
        return f"I didn't find any {subject}{detail}. Try fewer filters, or use the filters on the left."
    shown = min(total, MAX_CARDS)
    lead = f"Here {'is' if shown == 1 else 'are'} {shown}" + (f" of {total}" if total > shown else "")
    return f"{lead} {subject}{detail}."
