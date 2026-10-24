# Analysis agents

Manual, evidence-only Gemini research discussions. Eight roles/rounds read a frozen public-market snapshot: technical analyst, news analyst, bull, bear, bull rebuttal, bear rebuttal, risk manager and summariser. Code checks their claims and computes evidence strength. There is no agent browsing, executable tool, order interface or scheduler.

## Local setup

```powershell
python -m venv analysis-agents/.venv
analysis-agents/.venv/Scripts/python.exe -m pip install -r analysis-agents/requirements-lock.txt -e ./shared
```

Apply `db/migrations/007_agents.sql` after the earlier migrations. Migration 006 was already used by Phase 3. Root `.env` holds `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` and `GEMINI_API_KEY`. It is ignored by Git. The dashboard receives only public Supabase connection settings.

Provision the single owner once:

```powershell
analysis-agents/.venv/Scripts/python.exe analysis-agents/setup_user.py --email your-email@example.com
```

The setup script writes a randomly generated `DASHBOARD_PASSWORD` and the configured `DASHBOARD_EMAIL` to root `.env`, without printing them. Existing accounts are not silently reset. Sign in at `/login` using those local values. The owner is recorded in a private table, never in editable user metadata. Signing up a second account grants no research access.

## Commands

```powershell
analysis-agents/.venv/Scripts/python.exe analysis-agents/main.py run --symbol TCS
analysis-agents/.venv/Scripts/python.exe analysis-agents/main.py run --all
analysis-agents/.venv/Scripts/python.exe analysis-agents/main.py run --symbol TCS --force --on-demand
analysis-agents/.venv/Scripts/python.exe analysis-agents/main.py usage
analysis-agents/.venv/Scripts/python.exe analysis-agents/main.py serve
backtest/.venv/Scripts/python.exe backtest/main.py grade-reports
```

Daily runs are idempotent per stock/date. `--force` overrides material-change gating, but never overrides stale-data rejection or a daily duplicate. Use `--on-demand` for an intentional fresh discussion. `--as-of YYYY-MM-DD` selects the IST end-of-day cutoff and tags the thread as a replay; future cutoffs are refused. Historical availability includes ingestion/computation time, so old dates before this workspace collected its data usually have **no available evidence**, even when a candle's market date is older. Replays cannot pretend newly downloaded history was already known.

`serve` polls the authenticated request queue every five seconds. `--once` handles the next pending request and exits. Only one worker/run process can hold the local workspace lock. Interrupted local threads are marked failed at restart; an active-request journal marks an interrupted question failed without replaying messages. A process crash in the narrow gap between database claiming and journal creation can leave a request running; inspect it before a manual retry. Multiple machines sharing this database are not supported as workers in this phase.

## Provider and budgets

`config/llm.yaml` selects `gemini-3.5-flash-lite`, verified with Google's model API and a live generation on 24 October 2026. Application caps: 5 requests/minute, 60,000 estimated input tokens/minute, 150 calls/Pacific budget day, 14 calls/thread and 3 calls/question. These are application caps, **not verified account entitlements**. AI Studio may impose lower quotas. The provider never upgrades billing or switches to a paid model automatically.

Each attempt is reserved atomically in Postgres before network activity. Failed calls, repairs, and interrupted attempts still count. A conservative character estimate controls the local input token budget; actual returned input/output token usage is recorded separately. Retries are bounded, with backoff for transport/429/5xx failures. A persistent quota failure stops the thread and keeps its partial transcript. No synthetic completed report is made. Three early provider probes were reconciled into the reservation ledger from their real logbook events; their unknown token counts remain null.

Gemini receives only the public-market evidence and a validated public research question. Free-tier inputs may be used by Google for product improvement. Do not submit personal holdings, credentials or private documents. The client warns about this; a conservative question filter rejects obvious private data, but cannot prove that arbitrary prose is nonpersonal. The optional Ollama adapter is loopback-only and has not been installed or live-tested here.

Current provider references: [pricing](https://ai.google.dev/gemini-api/docs/pricing), [quotas](https://ai.google.dev/gemini-api/docs/rate-limits), [structured output](https://ai.google.dev/gemini-api/docs/structured-output).

## Evidence and verification

`data/asof_db.py` allowlists tables, paginates bounded reads and rejects market, ingestion, computation or statistics-period timestamps later than the cutoff. Daily bars are not available before the IST close. Unknown news publication times are excluded. Private questions, credentials and log payloads never enter the evidence pack. Operational thread/request/usage reads are separate from market-evidence reads.

The complete pack is stored with a hash. A smaller deterministic subset enters each prompt; every included reference retains its frozen ID. JSON delimiters neutralize markup. Earlier agents' unverified claims and unverified free prose are withheld from subsequent prompts. Strict output schemas and a one-repair policy lint prevent malformed or trading-instruction output from being published as an agent message.

The verifier checks reference existence in the database-derived snapshot, cutoff, numeric tolerance, event fields, historical edge sign and sample qualification. It marks descriptive interpretation partial and identifies unsupported numbers in prose. It cannot establish whether an argument is sound or reliably detect every unsupported nonnumeric sentence. Verified means checked against stored fields, not independently proven true. Source/classifier errors can remain. Phase 3's human-labelled accuracy evaluation remains pending at the user's request.

Only accepted claims enter the final summary. Unsupported report points are withheld. Evidence strength requires positive in-sample and out-of-sample results from the **same** statistics run, at the report horizon, with sufficient independent events. Strong evidence also needs distinct signal families aligned with the stored trend. News-derived evidence cannot establish moderate/strong strength while human review is pending. Weak/absent evidence caps confidence low; too few accepted facts or severe verification failures force neutral. Conflicting cited technical directions become mixed.

Read-only helpers in `tools/` expose bounded candles, indicators, signals, statistics, news, actions, quality and previous-report views over the frozen pack. Semantic search uses only the loopback news service and intersects results with the original frozen articles; it is explicitly anecdotal. Tools cannot expand a thread beyond its frozen coverage. The question responder uses the same snapshot and verifier, and tool/model event IDs link to the logbook. No LLM-directed tool calling is enabled.

## Dashboard and security

`/threads` shows discussions, filters, verification counts and calls. `/threads/[id]` shows live messages, counter-arguments, rejected claims, source snapshots and the final report. Evidence links open the stock chart at the cited IST date. Questions and run-now actions only insert `analysis_requests`; a local worker must be running to process them. `/usage` shows the Pacific-day call ledger. `/track-record` separates live and replay outcomes and excludes severe verification failures from its headline score.

All research tables have RLS. Anonymous users cannot read private discussions; only the configured owner can read them and insert allowed request fields. The browser cannot write messages, reports, request statuses, ownership, or budget reservations. Existing public-market tables and sanitized logbook events remain public read-only. No private question text belongs in those logs.

## Grading and limitations

Grading belongs to `backtest/`; the agents module does not import that module. Entry is the first matching market opening strictly after live report creation/cutoff, or after the historical cutoff for a replay. Exit is the close of the selected trading-session horizon. Exact stock/index session matching and quality exclusions are required. Outcomes are append-only and immature data stays pending. Returns are gross price returns without dividends or trading costs; they measure a research stance rather than an executable strategy.

Directional hit means positive excess return for bullish reports or negative excess return for bearish reports; neutral/mixed has no hit score. The dashboard includes a descriptive always-bullish comparator, a 50% coin-flip reference and Wilson intervals. Repeated/overlapping reports are correlated, so raw counts and intervals cannot establish independent statistical significance. With fewer than 30 independent observations no reliability claim is warranted.

Tests use fake providers only:

```powershell
analysis-agents/.venv/Scripts/python.exe -m pytest analysis-agents/tests -q
backtest/.venv/Scripts/python.exe -m pytest backtest/tests -q
npm run test:e2e --prefix dashboard
```

The browser checks use configured local owner credentials, never commit them, and make no Gemini calls. Live acceptance runs are separate from automated tests. Verification findings and remaining work are recorded in `docs/PHASE_4_VERIFICATION.md`.
