# Indian Market Research

Personal NSE stock research with read-only market analysis. Daily price ingestion, an action logbook,
technical signals, news and semantic memory, event studies, strategy backtests, evidence-linked Gemini discussions, and a live dashboard.
No order placement.

See [PHASE_1.md](PHASE_1.md) for the specification and
[docs/VERIFICATION.md](docs/VERIFICATION.md) for Phase 1 verification. Phase 2 is
specified in [PHASE_2.md](PHASE_2.md), with evidence and limitations in
[docs/PHASE_2_VERIFICATION.md](docs/PHASE_2_VERIFICATION.md).
Each completed step is checked, committed with a plain-language description,
and pushed to GitHub.

## Modules

Python modules cooperate through database tables, importing only `shared`.
`ingest` writes candles, `signals` derives indicators and dated signals,
`backtest` measures their historical results, and `dashboard` displays the tables.
`news` collects and processes public headlines locally. `logbook` reads the shared action events.
Phase 4 adds research agents; its specification is in `PHASE_4.md`.

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

Apply the files in `db/migrations/` in numeric order to a new Supabase project. Fill root `.env`
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

## Phase 2 workflow

Use separate Python 3.12 environments: the signal and VectorBT dependency sets
have different NumPy/Pandas requirements. Do not combine them in the root environment.

```powershell
python -m venv signals/.venv
signals/.venv/Scripts/python.exe -m pip install -r signals/requirements-lock.txt -e ./shared
python -m venv backtest/.venv
backtest/.venv/Scripts/python.exe -m pip install -r backtest/requirements-lock.txt -e ./shared
.venv/Scripts/python.exe ingest/main.py --all --days 1095
signals/.venv/Scripts/python.exe signals/main.py --all
backtest/.venv/Scripts/python.exe backtest/main.py events --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy sma_cross --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy rsi_reversion --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy pattern_trend --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy buy_and_hold --all
```

Stock pages now show overlays and signals. `/lab` compares event returns with
baselines; `/backtests` compares strategies with buy-and-hold. All are read-only.

## Verification commands

Phase 3 setup and commands are in [news/README.md](news/README.md). Start its local
memory service for `/search` and similar-event panels. The dashboard also adds
`/news`, `/sources`, stock sentiment and corporate actions, and news/sentiment Lab studies.
Human accuracy review of the exported 100-item sample remains pending at the user's request.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check shared ingest logbook scripts
.venv\Scripts\python.exe scripts/verify_cloud.py
.venv\Scripts\python.exe scripts/failure_drills.py
signals/.venv/Scripts/python.exe -m pytest signals/tests -q
backtest/.venv/Scripts/python.exe -m pytest backtest/tests -q
npm run build --prefix dashboard
npm run test:e2e --prefix dashboard
```

The fallback drill stores a small SBIN history; the invalid-symbol drill is
`python ingest/main.py --symbols NOTASTOCK,TCS --days 7` and should exit 1 while
still completing TCS. These are intentional failures in the real logbook.

## Boundaries

Single user, NSE daily equities; no orders or paid APIs. Phase 4 adds the selected Gemini free-tier research provider.
The specified public-key dashboard uses **public read-only** policies, so these
tables must contain only public market data and sanitized operational events.
Phase 4 discussions and questions use authenticated single-owner policies; portfolio data remains out of scope.
NSE and Yahoo worked in verification; OpenChart currently fails exact equity
lookup. Adjusted and unadjusted series are not silently mixed.

Module READMEs describe contracts, configuration, commands and known limitations.
Phase 4 setup and commands are in [analysis-agents/README.md](analysis-agents/README.md). Sign in at `/login` for discussions, questions, model usage and report track records. The local worker must run to process dashboard requests. Scheduling remains manual; Phase 5 is not implemented.
