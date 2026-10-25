"""Scout: the small Explore-page helper. gpt-6-luna only, through Portkey, on a strict token budget.

How it stays cheap: ONE model call per question. The model only turns the question into search filters
(models.ScoutQuery). Code runs the search and writes the reply sentence from the real results (tools.py),
so there's no second call, no tool schemas, and no search results sent back to the model.

Budgets (set in config.py / .env):
  - per model call:     SCOUT_MAX_OUTPUT_TOKENS output tokens, no reasoning
  - per member message: at most 2 model calls (1 + one retry if the output is malformed), SCOUT_MESSAGE_TOKENS
  - per visitor per day and for the whole site per day: SCOUT_VISITOR_DAILY_TOKENS / SCOUT_DAILY_TOKENS
When the SITE budget can't cover one more message, the page hides the helper for the day. When only one
visitor's budget is used up, the helper stays and tells them (cutely) to come back tomorrow.
Every run is appended to output/audit_trail.json.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timezone
from functools import cache

from openai import AsyncOpenAI
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider

import config
from db import connect
from models import ChatTurn, ScoutOut, ScoutQuery, User
from tools import describe, find_opportunities, find_startups

PROMPT_PATH = config.BACKEND / "prompts" / "prompt.md"
AUDIT_PATH = config.ROOT / "output" / "audit_trail.json"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

LIMITS = UsageLimits(request_limit=2, total_tokens_limit=config.SCOUT_MESSAGE_TOKENS)
# No reasoning: cheapest and fastest, and gpt-6-luna only allows tools on chat completions with reasoning off.
SETTINGS = OpenAIChatModelSettings(max_tokens=config.SCOUT_MAX_OUTPUT_TOKENS, openai_reasoning_effort="none")
HISTORY_TURNS = 2  # only the member's last 2 questions are re-sent, as one short line (for "what about SOM?")

LIMIT_REPLY = "I couldn't find that quickly. Try the filters on the left."
OTHER_REPLY = "I can only help find Yale startups and opportunities. Try something like \"climate startups\" or \"grants due soon\"."


class MissingAPIKey(RuntimeError):
    pass


class ScoutUnavailable(RuntimeError):
    """A daily token budget is used up. scope is 'site' (hide the helper) or 'visitor' (say come back tomorrow)."""

    def __init__(self, scope: str):
        super().__init__(scope)
        self.scope = scope


# ---------------------------------------------------------------- budget ledger

def _today() -> str:
    return date.today().isoformat()


def _used(conn, key: str) -> int:
    row = conn.execute("SELECT tokens FROM scout_usage WHERE day = ? AND key = ?", (_today(), key)).fetchone()
    return row["tokens"] if row else 0


def scout_budget(key: str) -> tuple[bool, bool]:
    """(site_ok, visitor_ok): whether each daily budget can still cover one full message."""
    if not os.getenv("PORTKEY_API_KEY"):
        return False, False
    with connect() as conn:
        site_left = config.SCOUT_DAILY_TOKENS - _used(conn, "site")
        visitor_left = config.SCOUT_VISITOR_DAILY_TOKENS - _used(conn, key)
    return site_left >= config.SCOUT_MESSAGE_TOKENS, visitor_left >= config.SCOUT_MESSAGE_TOKENS


def _record(key: str, tokens: int) -> None:
    with connect() as conn:
        for k in (key, "site"):
            conn.execute(
                "INSERT INTO scout_usage (day, key, tokens, messages) VALUES (?,?,?,1)"
                " ON CONFLICT(day, key) DO UPDATE SET tokens = tokens + excluded.tokens, messages = messages + 1",
                (_today(), k, tokens),
            )


# ---------------------------------------------------------------- agent

@cache
def build_agent() -> Agent[None, ScoutQuery]:
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKey("PORTKEY_API_KEY is missing from the .env file.")
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=api_key,
                         default_headers={"x-portkey-api-key": api_key}, max_retries=1, timeout=30)
    model = OpenAIChatModel(config.SCOUT_MODEL, provider=OpenAIProvider(openai_client=client))
    return Agent(model, output_type=ScoutQuery, instructions=PROMPT_PATH.read_text(), retries=1,
                 model_settings=SETTINGS)


def build_input(message: str, history: list[ChatTurn]) -> str:
    earlier = [t.content[:120] for t in history if t.role == "user"][-HISTORY_TURNS:]
    return (f"Earlier: {' | '.join(earlier)}\n" if earlier else "") + f"Now: {message[:300]}"


_audit_lock = asyncio.Lock()


def _short(value, n: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[:n] + "…"


async def append_audit(entry: dict) -> None:
    async with _audit_lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        trail = json.loads(AUDIT_PATH.read_text()) if AUDIT_PATH.exists() else []
        trail.append(entry)
        AUDIT_PATH.write_text(json.dumps(trail, indent=2))


async def run_scout(message: str, history: list[ChatTurn], viewer: User | None, budget_key: str) -> ScoutOut:
    site_ok, visitor_ok = scout_budget(budget_key)
    if not site_ok or not visitor_ok:
        raise ScoutUnavailable("site" if not site_ok else "visitor")
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stop_reason, out, tokens, query, tok = "error", None, 0, None, {}
    try:
        try:
            result = await build_agent().run(build_input(message, history), usage_limits=LIMITS)
        except UsageLimitExceeded:
            stop_reason, tokens = "usage_limit", config.SCOUT_MESSAGE_TOKENS  # charge the full per-message cap
            out = ScoutOut(reply=LIMIT_REPLY)
            return out
        u = result.usage
        tok = {"input_tokens": u.input_tokens or 0, "cached_tokens": u.cache_read_tokens or 0, "output_tokens": u.output_tokens or 0}
        tokens = tok["input_tokens"] + tok["output_tokens"]
        query = result.output
        if query.kind == "startups":
            startups, total = find_startups(query)
            out = ScoutOut(reply=describe(query, total), startups=startups, tools_used=["search_startups"])
        elif query.kind == "opportunities":
            opps, total = find_opportunities(query)
            out = ScoutOut(reply=describe(query, total), opportunities=opps, tools_used=["search_opportunities"])
        else:
            out = ScoutOut(reply=OTHER_REPLY)
        stop_reason = "final_output"
        return out
    finally:
        if tokens:
            _record(budget_key, tokens)
        if out is not None:
            out.site_available, out.visitor_available = scout_budget(budget_key)
        await append_audit({
            "time": started, "model": config.SCOUT_MODEL, "budget_key": budget_key.split(":")[0],
            "message": _short(message, 200), "query": query.model_dump(exclude_defaults=True) if query else None,
            "agent": "scout", "stop_reason": stop_reason, "tokens": tokens, **tok,
            "reply": _short(out.reply, 300) if out else None,
            "cards": {"startups": [s.id for s in out.startups], "opportunities": [o.id for o in out.opportunities]} if out else {},
        })
