# Indian Market Research

Personal, read-only NSE stock research. Phase 1 builds daily price ingestion,
validation, an action logbook, and a live dashboard. No order placement or LLMs.

See [PHASE_1.md](PHASE_1.md) for the specification and
[docs/VERIFICATION.md](docs/VERIFICATION.md) for verified behavior and limitations.
Each completed step is checked, committed with a plain-language description,
and pushed to GitHub.

## Modules

Python modules cooperate through database tables, importing only `shared`.
`ingest` writes candles, `logbook` reads events, and `dashboard` displays both.
Later phases add signals, backtesting, news, and evidence-based discussions.

All displayed findings are analysis for research, not investment recommendations.

## Quick start (Windows PowerShell)

Prerequisites: Python 3.12+, Node 22 LTS, a free Supabase project. This workspace
already has a Python 3.12 environment and local credentials configured. For a
fresh checkout:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install -e ./shared
Copy-Item .env.example .env
```

Apply `db/migrations/001_init.sql` once to a new Supabase project. Fill root `.env`
with its URL, Python secret key, and public dashboard key. Never commit `.env`.
Copy only the two `NEXT_PUBLIC_` settings to `dashboard/.env.local`.

```powershell
.venv\Scripts\python.exe ingest/main.py --all
.venv\Scripts\python.exe logbook/main.py tail
npm ci --prefix dashboard
npm run dev --prefix dashboard
```

Open http://127.0.0.1:3000. Edit `config/watchlist.yaml` for tracked stocks;
ingestion synchronizes it at startup. Run manually when daily data is needed.

## Verification commands

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check shared ingest logbook scripts
.venv\Scripts\python.exe scripts/verify_cloud.py
.venv\Scripts\python.exe scripts/failure_drills.py
npm run build --prefix dashboard
npm run test:e2e --prefix dashboard
```

The fallback drill stores a small SBIN history; the invalid-symbol drill is
`python ingest/main.py --symbols NOTASTOCK,TCS --days 7` and should exit 1 while
still completing TCS. These are intentional failures in the real logbook.

## Boundaries

Single user, NSE daily equities only in Phase 1; no orders, paid APIs, or LLMs.
The specified public-key dashboard uses **public read-only** policies, so these
tables must contain only public market data and sanitized operational events.
Private portfolio data requires authenticated owner policies in a later change.
NSE and Yahoo worked in verification; OpenChart currently fails exact equity
lookup. Adjusted and unadjusted series are not silently mixed.

Module READMEs describe contracts, configuration, commands and known limitations.
Future phases are placeholders. Scheduling remains manual; no jobs table yet.
