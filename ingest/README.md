# Ingest

Fetches completed daily NSE equity candles with validation and fallback.

## Contracts

Reads: active `watchlist`, latest `candles`, NSE through configured adapters.
Writes: seeds `watchlist` from YAML only when it has no NSE rows; afterwards the
database active list is authoritative. Upserts `candles` and appends `agent_events`.
No imports from other modules except `shared`. Database schema: `db/migrations/001_init.sql`.
Daily `ts` is the trading date at 00:00 Asia/Kolkata, stored as UTC (for example,
2026-10-22 becomes 2026-10-21T18:30:00Z). Chart dates convert back to IST.

## Setup and run

Install the root `requirements-lock.txt` and editable `shared` package. Set
`SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in root `.env`. `config/watchlist.yaml`
provides defaults for a fresh database; change active stocks from the dashboard
after the first seed. Configure approved price sources in `config/ingest.yaml`.

```sh
python ingest/main.py --all
python ingest/main.py --symbols RELIANCE,TCS
python ingest/main.py --all --days 365
python ingest/main.py --all --since 2024-01-01
python ingest/main.py --symbols ITC --source yfinance --days 30
python -m pytest ingest/tests
```

Without date flags, resumes the day after the latest stored candle; first run
uses 365 calendar days. `--days`/`--since` explicitly refetch that range. Today is
eligible only after 18:00 IST; weekends are skipped. Exchange holidays are not
yet a maintained calendar, so weekday gaps generate warnings. Historical holes
before the latest candle require an explicit date-range refresh.

Each source attempt runs in a killable subprocess with a 60-second cap. Transient
failures retry up to three attempts with exponential backoff; a detected 403/429
disables that source for the run. Validation failure falls through immediately.
Delays, ordering, retry counts, cross-checks and tolerances live in YAML. Upserts
use `(symbol, exchange, timeframe, ts)`, in batches of 500. Valid earlier batches
can remain after a later database failure; rerunning safely completes the work.
Database prices are numeric; serialization uses decimal strings from source data.

## Source behavior and limitations

- jugaad: raw NSE response preserves UTC timestamps and filters exact symbol/EQ
  series. `stock_df` is deliberately avoided because the installed version drops
  timestamp timezone information. Stored as unadjusted.
- OpenChart: exact symbol matching is required. On 2026-10-23 its equity search
  returned unrelated index entries here; the adapter rejected these rather than
  storing the wrong instrument. It remains optional in the fallback list.
- yfinance: uses `.NS`, inclusive dates converted to Yahoo's exclusive end, with
  `auto_adjust=False`. Yahoo OHLC can still be split-adjusted, so `adjusted=true`.
  A differently adjusted source is rejected when a series already exists; a
  source outage can therefore leave last-good data rather than mix price bases.
- Cross-check tries available alternative sources until one succeeds, compares
  the last five stored sessions, records differences, and never overwrites data.
  Different adjustment bases are disclosed in metadata.
- `api_calls` counts adapter fetch operations, not every internal HTTP request.
  Some source libraries suppress HTTP errors internally, limiting classification.
- No scheduler, broker integration, indicators, or trading functions in Phase 1.

## Events and exit codes

`sync_watchlist`, `run_start`, `fetch_candles`, `validate_candles`,
`write_candles`, `crosscheck`, `source_disabled`, `adjustment_mismatch`,
`symbol_end`, `run_end`. One UUID groups a pipeline run. `run_end` reflects failures
and warnings (it does not blindly claim success). Exit 1 for any failed symbol or
configuration/database failure; exit 0 for successful/skipped symbols with
nonfatal warnings. Logging failures warn on stderr; they never crash collection.
# Phase 5 calendar and adjustments

`python ingest/hardening.py calendar --years 2023,2024,2025,2026` refreshes the
calendar using the pinned holiday library and sourced overrides in
`config/calendar.yaml`. Unknown years fail closed instead of assuming every
weekday is open. Stored candle dates are cross-checked and conflicts recorded as
health checks. Refresh annually and when exchange circulars change. The 2026
baseline is [NSE CMTR71775](https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf),
amended for [January 15](https://nsearchives.nseindia.com/content/circulars/CMTR72260.pdf).
Special sessions have individual official circular links in the configuration.

`python ingest/hardening.py propose` inserts unreviewed split/bonus factors;
re-running never replaces a human decision. Ambiguous/conflicting ratios remain
in the corporate-action review queue. A 1:1 bonus gives 0.5; face value 10 to 2
gives 0.2. Products apply only before the ex-date and only once that ex-date is
inside stored history. Volume changes inversely. Yahoo's already-adjusted OHLC
passes through unchanged. Cash dividends are not adjusted: this is not a total
return series. Approval must precede the default adjusted-basis switch and the
comparison of recomputed studies. Calendar corrections require signal recomputation.

