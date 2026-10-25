# found.

**Every Yale startup and every opportunity to fund it, in one verified, searchable place.**

found. combines the [Yale Startup Directory](https://www.yalepitchbook.com/directory) (122 startups) and the
[Tsai CITY Yale Startup Opportunities board](https://tsaicity.useplop.com/) (130 programs, grants, competitions,
perks and asks) into one site, verifies members with their Yale email and LinkedIn, lets founders prove and claim
their listing, and uses two small AI agents (gpt-6-luna):

- **Scout** (Explore page): turns a question into search filters in one cheap call; the database supplies every answer.
- **Listing Auditor** (admin console): reads a startup's own website and proposes corrections with verified quotes.

**Report:** [open in browser](https://mandoniadis1.github.io/found/report.html) ([file](report.html)) · **Slides:** [open in browser](https://mandoniadis1.github.io/found/slides.html) ([file](slides.html)). Both files also open by double-clicking after download.

## Run it (about 3 minutes)

Needs **Python 3.11+**. No Node.js needed (the web apps are prebuilt in `frontend/dist` and `admin/dist`).

1. Put your key in a file named `.env`, **in this folder or the folder above it**:
   ```
   PORTKEY_API_KEY=your-key
   ```
2. Install and start (from this folder):

   **Mac / Linux**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python run.py
   ```
   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\python run.py
   ```
3. Open **http://localhost:8030** (it opens automatically). The admin console is at **http://localhost:8030/admin**.

The database is created from the included data on first start. Stop with Ctrl+C.

### Demo accounts (local mode)

| Where | Email | Password |
|---|---|---|
| Public site | `demo@yale.edu` (verified member) | `found2026` |
| Public site | `dan@yale.edu` (second member, to try messages) | `found2026` |
| Admin console `/admin` | `admin@yale.edu` | `found2026` |

Or create your own account with any `@yale.edu` address. In local mode nothing is emailed: after signing up, click
**"Open your email"** in the yellow banner to see the verification email and click its link. "Sign in with LinkedIn"
goes to a clearly labeled local stand-in until real LinkedIn keys are configured.

### Things to try

1. **Explore**: filter by industry + stage + Yale affiliation; click a card; the "Closing soon" boxes.
2. **Ask Scout** (bottom-right of Explore): e.g. *"climate startups making revenue"* or *"grants due in the next month"*.
3. **Opportunities**: categories, "Due in 30 days", the "On the horizon" calendar.
4. **Claim a startup**: sign up, verify your email, connect LinkedIn (stand-in), open a startup, click *Claim this startup*.
5. **Admin console** (`/admin`): review claims, run **Audit** on a listing (e.g. Mundaly), apply or dismiss the suggestion.

## Data

- `data/sources/` holds the data the app imports on first start (small, included):
  `pitchbook_startups.json`, `tsai_posts.json`, `tsai_upcoming.json`, plus `corrections.json` (fixes applied on top).
- **Kept up to date automatically:** while the app runs, it re-downloads both sites every 7 days (`REFRESH_DAYS` in
  `.env`; `0` turns it off). The admin console's dashboard shows the last/next refresh and has a **Refresh now** button.
  You can also run `cd backend && ../.venv/bin/python refresh.py`. A refresh never removes users, claims, corrections,
  events or messages; a listing that disappears from the source is hidden, not deleted, and a download that looks broken
  (missing fields, or less than half the previous size) is refused.
- **Switch datasets:** replace those files (same format) and rebuild the database with
  `.venv/bin/python backend/db.py --reset`.
- To use a different database file, set `FOUND_DB=/path/to/file.db` in `.env`.

## How it's built

| Part | Where |
|---|---|
| API, auth, verification, budgets, serving the web apps | `backend/main.py`, `auth.py`, `verification.py`, `config.py`, `mailer.py` |
| Agent 1 · Scout | `backend/agent.py`, `backend/tools.py`, `backend/prompts/prompt.md` |
| Agent 2 · Listing Auditor | `backend/auditor.py`, `backend/prompts/auditor.md` |
| Data model and import | `backend/db.py`, `backend/queries.py`, `backend/models.py` |
| Public site (React + Vite + TypeScript) | `frontend/` (built into `frontend/dist`) |
| Admin console (React + Vite + TypeScript) | `admin/` (built into `admin/dist`) |
| Append-only log of every agent run | `output/audit_trail.json` |

Model: **gpt-6-luna only**, through Portkey (`PORTKEY_API_KEY`).

## Evidence for the report (re-runnable)

| Script | Output |
|---|---|
| `.venv/bin/python scripts/eval_scout.py` | `output/eval_scout.json`: 20-question accuracy and tokens, one-call vs two-call Scout |
| `.venv/bin/python scripts/safety_tests.py` | `output/safety_tests.json`: 15 attacks on the defenses (uses a throwaway database) |
| `.venv/bin/python scripts/audit_all.py` | `output/audit_all.json`: Listing Auditor run on every listing with its own website |
| `.venv/bin/python scripts/build_report.py` | `report.html`, `slides.html` (every number read from the files above) |

## Development (optional)

Hot-reloading dev servers instead of the prebuilt apps (needs Node 20+):
```bash
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8030   # API
cd frontend && npm install && npm run dev                           # public site → http://localhost:5185
cd admin && npm install && npm run dev                              # admin → http://localhost:5186/admin/
```
Rebuild the prebuilt apps with `npm run build` in `frontend/` and `admin/`. Optional settings (real email, LinkedIn
keys, budgets) are listed in `.env.example`; none are needed to run the app.
