"""Run the Listing Auditor on every listed startup that has its own website (4 at a time).
Results go to the admin console's "Listing audits" page (nothing is changed until an admin applies a fix) and a
summary goes to output/audit_all.json.   .venv/bin/python scripts/audit_all.py [--limit N]"""
import _setup  # noqa: F401  (sets paths)

import asyncio
import json
import sys
import time

import queries
from auditor import audit_listing
from db import connect, now
from verification import company_domain

LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None


async def main():
    with connect() as conn:
        startups = [s for s in queries.search_startups(conn, limit=1000) if company_domain(s.website)]
    startups = startups[:LIMIT] if LIMIT else startups
    sem = asyncio.Semaphore(4)
    results = []

    async def one(s):
        async with sem:
            t0 = time.time()
            try:
                r = await audit_listing(s)
            except Exception as exc:
                print(f"  ! {s.name}: {type(exc).__name__}: {exc}")
                return
            r_secs = round(time.time() - t0, 1)
            with connect() as conn:
                conn.execute(
                    "INSERT INTO listing_audits (startup_id, verdict, status, result_json, input_tokens, cached_tokens,"
                    " output_tokens, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (s.id, r.report.verdict, "proposed" if r.report.verdict == "needs_changes" else "info",
                     r.model_dump_json(), r.input_tokens, r.cached_tokens, r.output_tokens, r.cost_usd, now()))
            results.append({"startup": s.name, "verdict": r.report.verdict, "seconds": r_secs,
                            "pages": len(r.pages_read), "input": r.input_tokens, "cached": r.cached_tokens,
                            "output": r.output_tokens, "cost_usd": r.cost_usd, "dropped_quotes": r.dropped_quotes,
                            "flagged": len(r.flagged_lines), "stop": r.stop_reason,
                            "summary": r.report.summary,
                            "suggested_industries": r.report.suggested_industries,
                            "current_industries": s.industries})
            print(f"  {len(results):3d}/{len(startups)} {r.report.verdict:13s} {s.name}")

    t = time.time()
    await asyncio.gather(*(one(s) for s in startups))
    summary = {
        "ran_at": now(), "audited": len(results), "wall_seconds": round(time.time() - t, 1),
        "verdicts": {v: sum(r["verdict"] == v for r in results) for v in ("accurate", "needs_changes", "unclear")},
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 5),
        "tokens": {k: sum(r[k] for r in results) for k in ("input", "cached", "output")},
        "dropped_quotes": sum(r["dropped_quotes"] for r in results),
        "flagged_lines": sum(r["flagged"] for r in results),
        "results": sorted(results, key=lambda r: r["startup"].lower()),
    }
    (_setup.OUTPUT / "audit_all.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=1))


asyncio.run(main())
