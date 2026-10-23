# Phase 2: Signals and Proof

> Part of the Indian Stock Market Research & Analytics Tool.
> Read `PROJECT_OVERVIEW.md` and `PHASE_1.md` first. Phase 1 must be complete before starting this phase.
> This file is the complete specification for Phase 2. An AI agent or developer should be able to build Phase 2 from this file alone.

---

## 1. Goal

Turn raw candles into **machine-readable signals** (indicators, candlestick patterns, trend state, key levels), and then **test honestly whether those signals ever worked** on Indian stocks.

Phase 2 answers two different questions, and keeps them separate:

1. **"What is the chart showing right now?"** (the `signals` module)
2. **"When this thing showed up in the past, what happened next, and was it better than chance?"** (the `backtest` module)

At the end of Phase 2 the user can:

1. Run one command and have indicators, patterns and trend state computed for the whole watchlist.
2. Open a stock page and see **indicator overlays and pattern markers** on the candle chart.
3. Open a **Signal Lab** page showing, for each signal, how prices behaved after it appeared, compared with a baseline, with sample sizes and in-sample / out-of-sample results.
4. Run **strategy backtests** (long-only, with costs, no look-ahead) and view equity curves, trades and metrics against buy-and-hold.
5. Trust the numbers, because every result is reproducible, carries its configuration and code version, and shows how much evidence is behind it.

Phase 2 deliberately uses **no LLM and no AI agents**. Everything is deterministic and free. Phase 4 agents will later read these tables as their evidence.

---

## 2. Scope

### In scope
- `signals/` module: indicators, candlestick patterns, trend state, support/resistance levels, data-quality flags.
- `backtest/` module: event-study statistics for signals and simple strategy backtests.
- Database migrations for: `indicator_values`, `signals`, `signal_stats`, `backtest_runs`, `backtest_results`, `backtest_trades`.
- Configuration files for signals and backtests.
- Dashboard additions: chart overlays, pattern markers, indicator panels, Signal Lab page, Backtests pages, status tiles.
- Logbook events for both modules.
- Tests, including cross-checks between libraries, and failure drills.
- A deeper history backfill in `ingest` (a configuration change, not new code, see section 3).

### Out of scope (do NOT build in Phase 2)
- News, sentiment, embeddings (Phase 3).
- LLM agents or discussion threads (Phase 4).
- Browser agent, scheduler, alerts (Phase 5).
- Short selling, options, futures strategies (long-only equity in Phase 2).
- Intraday signals (daily timeframe only; schemas already support other timeframes).
- Machine-learning price prediction. Phase 2 is rules and statistics only.
- Any order placement or trading function. Ever.
- Any paid service or paid data.

---

## 3. Prerequisites and the one Phase 1 change

| Item | Notes |
|---|---|
| Phase 1 done | Candles table filled and validated, logbook and dashboard working. |
| TA-Lib | Needs the underlying C library. Installation differs by operating system and Python version, so follow the current TA-Lib instructions and **test `import talib` in a tiny script before anything else**. |
| pandas-ta | Check its maintenance status and install source before relying on it (forks and packaging have changed over time). If it is unmaintained or hard to install, rely on TA-Lib and compute the few extras directly with pandas. |
| VectorBT | Open-source community edition. It depends on Numba, which can be strict about Python and NumPy versions. Verify compatibility in the `backtest` module's own environment. |

### Required Phase 1 configuration change: deeper history

Indicators need a **warm-up period**. A 200-day moving average needs 200 candles before its first valid value. Phase 1's default lookback of 365 calendar days gives only roughly 245 trading days, which would leave about 45 usable rows for the 200-day average, and far too few events for meaningful statistics.

Before Phase 2 work, backfill about **3 years** of daily candles:

```yaml
# config/ingest.yaml
default_lookback_days: 1095
```

Verify that your sources actually return that much history (some libraries limit the range). If one source is capped, the others can fill the rest. Re-run `python ingest/main.py --all --days 1095`. Phase 1's idempotent upserts make this safe.

---

## 4. Repository changes

Only these folders change. Everything else stays as in Phase 1.

```
market-research/
├── config/
│   ├── signals.yaml              # NEW
│   └── backtest.yaml             # NEW
├── db/
│   └── migrations/
│       ├── 002_signals.sql       # NEW
│       └── 003_backtest.sql      # NEW
├── signals/                      # filled in
│   ├── README.md
│   ├── requirements.txt          # ta-lib, pandas, numpy, (pandas-ta if usable)
│   ├── main.py
│   ├── indicators/
│   │   ├── trend.py              # SMA, EMA, MACD, ADX
│   │   ├── momentum.py           # RSI, Stochastic
│   │   ├── volatility.py         # Bollinger Bands, ATR
│   │   └── volume.py             # OBV, volume average
│   ├── patterns/
│   │   └── candles.py            # TA-Lib candlestick wrappers
│   ├── rules/
│   │   ├── crossovers.py         # indicator-based signal rules
│   │   ├── trend_state.py        # uptrend / downtrend / sideways
│   │   └── levels.py             # swing highs/lows, support/resistance
│   ├── quality.py                # data-quality flags
│   └── tests/
├── backtest/                     # filled in
│   ├── README.md
│   ├── requirements.txt          # vectorbt, pandas, numpy
│   ├── main.py
│   ├── event_study.py            # forward returns after signals
│   ├── strategies/
│   │   ├── base.py
│   │   ├── sma_cross.py
│   │   ├── rsi_reversion.py
│   │   ├── pattern_trend.py
│   │   └── buy_and_hold.py
│   ├── costs.py
│   ├── splits.py                 # in-sample / out-of-sample
│   └── tests/
└── dashboard/                    # extended (see section 10)
```

The `signals/` and `backtest/` folders keep their own dependency files. **They never import each other.** The backtest module reads the `candles` and `signals` tables only.

---

## 5. Database design

Same conventions as Phase 1: timestamps in UTC `timestamptz`, daily rows use the session date at 00:00 IST converted to UTC, `numeric` for prices and values, and **all writes are idempotent** (upsert on the primary key).

### 5.1 `002_signals.sql`

```sql
-- Indicator values: one row per symbol, timestamp and series.
create table indicator_values (
  symbol      text        not null,
  exchange    text        not null default 'NSE',
  timeframe   text        not null default '1d',
  ts          timestamptz not null,
  series_key  text        not null,    -- e.g. 'sma_50', 'rsi_14', 'macd_line_12_26_9', 'bb_upper_20_2'
  value       numeric,                 -- null during warm-up
  computed_at timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts, series_key)
);
create index indicator_values_lookup_idx
  on indicator_values (symbol, timeframe, series_key, ts desc);

-- Signals: discrete things that happened on a given day.
create table signals (
  symbol        text        not null,
  exchange      text        not null default 'NSE',
  timeframe     text        not null default '1d',
  ts            timestamptz not null,
  signal_key    text        not null,   -- e.g. 'cdl_engulfing', 'rsi_14_oversold', 'sma_50_200_golden_cross'
  signal_type   text        not null
                check (signal_type in ('pattern','indicator','trend','level','data_flag')),
  direction     text
                check (direction in ('bullish','bearish','neutral')),
  raw_value     numeric,                -- e.g. TA-Lib raw output such as 100 / -100
  description   text        not null,   -- human-readable sentence (Phase 4 agents will read this)
  details       jsonb       not null default '{}'::jsonb,
  logic_version text        not null,   -- version of the rules that produced this row
  computed_at   timestamptz not null default now(),
  primary key (symbol, exchange, timeframe, ts, signal_key)
);
create index signals_key_idx    on signals (signal_key, ts desc);
create index signals_symbol_idx on signals (symbol, timeframe, ts desc);
```

### 5.2 `003_backtest.sql`

```sql
-- Event-study results: what happened after each signal.
create table signal_stats (
  id                 bigserial primary key,
  stats_run_id       uuid        not null,
  signal_key         text        not null,
  direction          text,
  scope              text        not null,   -- a symbol, or 'POOLED' for all watchlist stocks
  sample             text        not null
                     check (sample in ('all','in_sample','out_of_sample')),
  horizon_days       integer     not null,   -- 1, 3, 5, 10, 20
  n_events           integer     not null,   -- raw count of occurrences
  n_independent      integer     not null,   -- count after removing overlapping events
  mean_return        numeric,                -- directional, see section 7.4
  median_return      numeric,
  win_rate           numeric,
  baseline_mean      numeric,                -- same stock/period, all days, same direction
  edge               numeric,                -- mean_return - baseline_mean
  sufficient_sample  boolean     not null,   -- n_independent >= configured minimum
  period_start       date,
  period_end         date,
  config             jsonb       not null default '{}'::jsonb,
  logic_version      text        not null,
  computed_at        timestamptz not null default now()
);
create index signal_stats_lookup_idx on signal_stats (signal_key, scope, sample, horizon_days);

-- One row per backtest execution.
create table backtest_runs (
  id            uuid        primary key,
  name          text        not null,
  strategy_key  text        not null,
  config        jsonb       not null,        -- full parameters, fees, slippage, split dates
  symbols       text[]      not null,
  period_start  date        not null,
  period_end    date        not null,
  fees_pct      numeric     not null,
  slippage_pct  numeric     not null,
  code_version  text        not null,        -- git commit hash
  created_at    timestamptz not null default now()
);

-- Per-symbol, per-sample results.
create table backtest_results (
  run_id             uuid    not null references backtest_runs(id) on delete cascade,
  symbol             text    not null,
  sample             text    not null check (sample in ('all','in_sample','out_of_sample')),
  metrics            jsonb   not null,       -- total_return, cagr, max_drawdown, sharpe, win_rate, n_trades, exposure
  benchmark_metrics  jsonb   not null,       -- buy-and-hold for the same stock and period
  equity_curve       jsonb,                  -- downsampled [[date, value], ...]
  primary key (run_id, symbol, sample)
);

create table backtest_trades (
  id           bigserial primary key,
  run_id       uuid        not null references backtest_runs(id) on delete cascade,
  symbol       text        not null,
  entry_ts     timestamptz not null,
  exit_ts      timestamptz not null,
  entry_price  numeric     not null,
  exit_price   numeric     not null,
  return_pct   numeric     not null,         -- after costs
  bars_held    integer     not null,
  exit_reason  text                          -- 'signal', 'time_stop', 'end_of_data'
);
create index backtest_trades_run_idx on backtest_trades (run_id, symbol, entry_ts);
```

### 5.3 Realtime and access
- Enable Realtime on `signals` only if you want live updates; `indicator_values` is large and should be read on demand, not streamed.
- Apply the same read-only RLS policies used in Phase 1 to all new tables. Writes come only from Python modules with the service key.

---

## 6. `signals/` module

### 6.1 Job
Read candles from `candles`, compute indicators, patterns, trend state and levels, and write `indicator_values` and `signals`. Emit logbook events throughout.

### 6.2 Command line

```
python signals/main.py --symbols RELIANCE,TCS     # specific stocks
python signals/main.py --all                      # whole active watchlist
python signals/main.py --all --recompute          # ignore watermarks, recompute everything
python signals/main.py --all --since 2025-01-01   # recompute from a date
```

### 6.3 Incremental computation (watermark)

No jobs table is needed yet. For each symbol:

1. Find the latest `ts` already stored in `indicator_values` for that symbol (the watermark).
2. Load candles from `watermark - warm-up window` onward. The warm-up window is the longest indicator period plus a safety buffer (for example 400 candles).
3. Compute everything on that tail.
4. **Write only rows newer than the watermark** (plus any rows `--recompute` demands).

This keeps daily runs fast while giving correct values, because new indicator values depend on earlier candles.

### 6.4 Indicators

Configured in `config/signals.yaml` (see section 9). Suggested starter set:

| Group | Series |
|---|---|
| Trend | SMA 20, 50, 200; EMA 12, 26; MACD line, signal and histogram (12, 26, 9); ADX 14 |
| Momentum | RSI 14; Stochastic (14, 3, 3) |
| Volatility | Bollinger Bands (20, 2) upper/middle/lower; ATR 14 |
| Volume | OBV; 20-day volume average |

Rules:
- Series are stored under stable `series_key` names that include the parameters, for example `sma_50`, `rsi_14`, `macd_hist_12_26_9`.
- Values during the warm-up period are stored as null (or not stored), never as zero.
- **Cross-check:** where both TA-Lib and pandas-ta provide the same indicator, a test compares them within a small tolerance. A mismatch fails the test and must be understood before continuing.

### 6.5 Candlestick patterns

Use TA-Lib's pattern functions. TA-Lib reports 61 of them, each returning a signed value: positive for bullish, negative for bearish, zero for none. Typically the value is plus or minus 100, though some patterns can return other magnitudes, so **store the raw value** in `raw_value` and derive `direction` from its sign.

Start with a short, well-known list instead of all 61 (more patterns mean more chances of finding "patterns that worked" by luck):

| TA-Lib function | Pattern |
|---|---|
| CDLDOJI | Doji |
| CDLHAMMER | Hammer |
| CDLINVERTEDHAMMER | Inverted hammer |
| CDLHANGINGMAN | Hanging man |
| CDLSHOOTINGSTAR | Shooting star |
| CDLENGULFING | Bullish / bearish engulfing |
| CDLHARAMI | Harami |
| CDLPIERCING | Piercing line |
| CDLDARKCLOUDCOVER | Dark cloud cover |
| CDLMORNINGSTAR | Morning star |
| CDLEVENINGSTAR | Evening star |
| CDL3WHITESOLDIERS | Three white soldiers |
| CDL3BLACKCROWS | Three black crows |
| CDLMARUBOZU | Marubozu |
| CDLSPINNINGTOP | Spinning top |

Notes:
- TA-Lib needs its input arrays as floating-point type. Convert the `numeric` columns before calling.
- Signal keys use a clear prefix, for example `cdl_engulfing`.
- Every pattern row gets a `description`, such as "Bullish engulfing on RELIANCE (raw value +100)".
- Patterns should be recorded **with the trend state at the time** in `details` (for example `{"trend_state": "downtrend"}`), because a reversal pattern means something different inside a trend than in a sideways market. The backtest module will use this.

### 6.6 Indicator-based signal rules (`rules/crossovers.py`)

Simple, explicit rules. Each emits a row into `signals` on the day the condition becomes true (not every day it stays true):

| signal_key | Rule | Direction |
|---|---|---|
| `sma_50_200_golden_cross` | SMA 50 crosses above SMA 200 | bullish |
| `sma_50_200_death_cross` | SMA 50 crosses below SMA 200 | bearish |
| `macd_bull_cross` / `macd_bear_cross` | MACD line crosses signal line | bullish / bearish |
| `rsi_14_oversold` | RSI 14 falls below 30 | bullish (mean-reversion idea) |
| `rsi_14_overbought` | RSI 14 rises above 70 | bearish (mean-reversion idea) |
| `bb_lower_touch` / `bb_upper_touch` | Close beyond Bollinger band | bullish / bearish |
| `new_20d_high` / `new_20d_low` | Close at highest / lowest of 20 days | bullish / bearish |
| `volume_spike` | Volume above a multiple of the 20-day average (configurable) | neutral |

All thresholds live in `config/signals.yaml`. The `direction` describes the **idea behind the rule**, not a prediction. Whether it worked is exactly what the backtest module measures.

### 6.7 Trend state (`rules/trend_state.py`)

One `trend_state` signal per stock per day, classified by transparent rules (all configurable). Suggested default:

- **Uptrend:** close above SMA 50, SMA 50 above SMA 200, and ADX above a threshold (for example 20).
- **Downtrend:** close below SMA 50, SMA 50 below SMA 200, and ADX above the threshold.
- **Sideways:** everything else.

Store the rule inputs in `details` so the classification is explainable. Because it is written daily, this table grows quickly. That is acceptable for a small watchlist; if it becomes heavy, store only state **changes**.

### 6.8 Support and resistance (`rules/levels.py`)

Keep this simple and deterministic: **swing highs and swing lows** (a candle whose high/low is the extreme of the N candles on each side, with N configurable, for example 5). Store them as `level` signals with `details` such as `{"kind": "swing_high", "price": 2850.5}`.

Important: a swing point is only **confirmed N candles later**. The signal's `ts` must be the **confirmation date**, not the swing date, otherwise backtests would use information that was not yet known (look-ahead bias). Put the swing date in `details`.

### 6.9 Data-quality flags (`quality.py`)

Phase 2 must not trust data blindly, especially because Phase 1 stores unadjusted prices by default.

Emit `data_flag` signals for:

| Flag | Condition |
|---|---|
| `possible_split_or_bonus` | Single-day close-to-close move beyond a threshold (for example 20%). |
| `gap_in_data` | A run of missing weekdays longer than a few days (a few missing days can be holidays). |
| `short_history` | Fewer candles than the longest warm-up period. |
| `zero_volume_streak` | Several consecutive zero-volume days. |

Consequences:
- Symbols with `short_history` are skipped for long-period indicators, with a logbook `skipped` event.
- The backtest module **excludes a window around every `possible_split_or_bonus` flag** (configurable, for example plus or minus 20 days), or refuses to run on that symbol until the data is fixed. Unadjusted splits create fake crashes and fake signals.

### 6.10 Logbook events for `signals`

| Moment | action | status |
|---|---|---|
| Run starts | `run_start` | started |
| Per symbol, load candles | `load_candles` | success / skipped (short history) |
| Per symbol, indicators | `compute_indicators` | success / failed |
| Per symbol, patterns | `compute_patterns` | success / failed |
| Per symbol, rules and trend | `compute_rules` | success / failed |
| Per symbol, quality | `quality_check` | success / warning |
| Per symbol, write | `write_signals` | success / failed (with row counts) |
| Run ends | `run_end` | success (totals) |

One failing symbol never stops the run.

---

## 7. `backtest/` module

### 7.1 Job
Two kinds of work, both reading only `candles` and `signals`:

1. **Event study:** for each signal, measure forward returns over several horizons and compare with a baseline.
2. **Strategy backtest:** simulate simple long-only strategies with costs and report metrics against buy-and-hold.

### 7.2 Command line

```
python backtest/main.py events --all                       # event study for all signals
python backtest/main.py events --signal cdl_engulfing      # one signal
python backtest/main.py strategy sma_cross --all           # strategy backtest
python backtest/main.py strategy rsi_reversion --symbols TCS,INFY
python backtest/main.py strategy buy_and_hold --all        # benchmark
```

### 7.3 Core rules that protect against fooling yourself

These are not optional. They are what makes Phase 2 a research tool instead of a pattern-flattering machine.

1. **No look-ahead.** A signal computed from day *t*'s close can only be acted on **after** day *t*. Default: enter at the **open of day t+1**. Never use day *t*'s own close as the fill price for a decision made with day *t*'s close, and never use information confirmed later (see swing points in 6.8). Verify the library's fill-price and shifting behaviour with a tiny hand-checked example before trusting it.
2. **Costs and slippage always on.** Default to configurable percentages per side (`fees_pct`, `slippage_pct` in `config/backtest.yaml`). Starting values are placeholders: replace them with figures from your own broker's charge sheet and current statutory charges, which you should verify rather than assume.
3. **Baseline always shown.** A signal that is followed by +1% on average means nothing if the stock rises +1% on average anyway. Every result is compared with the unconditional average over the same period.
4. **Sample size always shown.** Results with too few independent events are labelled "insufficient sample" and are never presented as findings.
5. **In-sample and out-of-sample.** Split time chronologically (for example the first 70% is in-sample, the last 30% is out-of-sample). Tuning is allowed only on in-sample; the out-of-sample number is the honest one. Never shuffle time.
6. **Long-only.** No shorting in Phase 2. Bearish signals are evaluated as "did the price fall afterwards?", not as short trades.
7. **Reproducible.** Every run stores its full configuration and the git commit hash. The same inputs must reproduce the same numbers.
8. **Beware many tests.** Testing many signals, horizons and parameters will produce some impressive-looking results by luck. Report how many combinations were tested, and treat in-sample winners as hypotheses, not facts.

### 7.4 Event study (`event_study.py`)

For each signal row and each horizon *h* in a configurable list (for example 1, 3, 5, 10, 20 trading days):

- **Entry price:** open of the next trading day after the signal date.
- **Exit price:** close of the *h*-th trading day after entry (define precisely and document in the README).
- **Raw return:** exit divided by entry minus one, after applying cost and slippage assumptions.
- **Directional return:** raw return multiplied by +1 for bullish signals and -1 for bearish signals, so a positive number always means "the signal's idea worked".

Aggregate per `(signal_key, scope, sample, horizon)` where scope is each symbol and a `POOLED` group across the watchlist:

| Field | Meaning |
|---|---|
| `n_events` | All occurrences. |
| `n_independent` | Occurrences after dropping any signal that fires within *h* days of the previously counted one (overlapping outcomes are not independent evidence). |
| `mean_return`, `median_return`, `win_rate` | Directional statistics. |
| `baseline_mean` | Average directional return on **all** days for the same stock and period. |
| `edge` | `mean_return - baseline_mean`. This is the number that matters. |
| `sufficient_sample` | True only if `n_independent` meets the configured minimum (for example 30). |

Also exclude events falling inside data-quality exclusion windows (section 6.9).

### 7.5 Strategies

Each strategy is a small class implementing a common interface (inputs: candles and signals for one symbol; output: entry and exit signals), so new ones can be added without touching the engine.

| Strategy key | Idea | Entry | Exit |
|---|---|---|---|
| `sma_cross` | Trend following | SMA fast crosses above SMA slow | Fast crosses below slow |
| `rsi_reversion` | Mean reversion | RSI below lower threshold | RSI above exit level, or time stop |
| `pattern_trend` | Pattern plus filter | Chosen bullish pattern while trend state is as configured | Fixed holding days, or time stop |
| `buy_and_hold` | Benchmark | First day | Last day |

All strategies:
- Are long-only, one position per symbol at a time.
- Apply the timing rule in 7.3 (enter next open).
- Use fixed position sizing per symbol (for example 100% of that symbol's own test capital). Portfolio-level allocation is out of scope.

### 7.6 Metrics

Per symbol and sample, and compared with buy-and-hold over the identical period:

- Total return, annualised return (CAGR), maximum drawdown
- Sharpe-style ratio (document the assumed risk-free rate and annualisation; keep it configurable)
- Win rate, number of trades, average trade return, average holding days
- Exposure (fraction of time in the market)
- Equity curve (downsampled)

Highlight when a strategy **loses to buy-and-hold** after costs. For most simple rules on a small set of stocks, that is a common and perfectly valid finding.

### 7.7 Parameter sweeps

Allowed (for example several SMA lengths), under these rules:
- Choose the best parameters using **in-sample only**.
- Report the same parameters' **out-of-sample** result next to it.
- Store how many parameter combinations were tried in the run's `config`.
- The dashboard must show a warning when a result came from a sweep.

### 7.8 Logbook events for `backtest`

| Moment | action | status |
|---|---|---|
| Run starts | `run_start` | started |
| Load data | `load_data` | success / failed / skipped |
| Exclusions applied | `apply_exclusions` | warning (counts of excluded windows) |
| Event study per signal | `event_study` | success / failed |
| Strategy per symbol | `run_strategy` | success / failed |
| Write results | `write_results` | success / failed |
| Run ends | `run_end` | success (totals, combinations tested) |

---

## 8. Honest interpretation guide (put this in the backtest README and on the dashboard)

- A positive edge **in-sample and out-of-sample, with a sufficient independent sample, across several stocks** is a reasonable hypothesis worth watching.
- A positive edge in one stock, one horizon, with a small sample, is most likely noise.
- Good in-sample and poor out-of-sample usually means the idea was fitted to the past.
- Results describe the past on a small watchlist. They are not predictions and not advice.
- Indicators and patterns rarely give strong standalone edges. Finding "no edge" is a useful result, because it stops you trusting a signal that does not deserve it.

---

## 9. Configuration

### 9.1 `config/signals.yaml`

```yaml
timeframe: 1d
warmup_candles: 400
logic_version: "2.0.0"      # bump when any rule changes; stored on every signal row

indicators:
  sma: [20, 50, 200]
  ema: [12, 26]
  rsi: [14]
  macd: {fast: 12, slow: 26, signal: 9}
  bollinger: {period: 20, stddev: 2}
  atr: [14]
  adx: [14]
  stochastic: {k: 14, d: 3, smooth: 3}
  obv: true
  volume_avg: [20]

patterns:
  - CDLDOJI
  - CDLHAMMER
  - CDLINVERTEDHAMMER
  - CDLHANGINGMAN
  - CDLSHOOTINGSTAR
  - CDLENGULFING
  - CDLHARAMI
  - CDLPIERCING
  - CDLDARKCLOUDCOVER
  - CDLMORNINGSTAR
  - CDLEVENINGSTAR
  - CDL3WHITESOLDIERS
  - CDL3BLACKCROWS
  - CDLMARUBOZU
  - CDLSPINNINGTOP

rules:
  rsi_oversold: 30
  rsi_overbought: 70
  breakout_window_days: 20
  volume_spike_multiple: 2.0

trend_state:
  adx_threshold: 20

levels:
  swing_window: 5

quality:
  split_jump_threshold_percent: 20
  max_missing_weekdays_in_row: 5
  zero_volume_streak_days: 5
```

### 9.2 `config/backtest.yaml`

```yaml
horizons_days: [1, 3, 5, 10, 20]
min_independent_events: 30
sample_split:
  in_sample_fraction: 0.7      # chronological split, never shuffled

costs:                         # PLACEHOLDERS. Replace with your broker's real charges.
  fees_pct_per_side: 0.10
  slippage_pct_per_side: 0.05

timing:
  entry: next_open             # act on the next day's open after the signal
  exit_for_events: horizon_close

exclusions:
  around_split_flag_days: 20

risk:
  risk_free_rate_annual: 0.0   # set deliberately; document your choice
  trading_days_per_year: 250   # confirm and keep consistent

strategies:
  sma_cross:      {fast: 50, slow: 200}
  rsi_reversion:  {entry_below: 30, exit_above: 50, max_hold_days: 20}
  pattern_trend:  {pattern: cdl_engulfing, trend: uptrend, hold_days: 10}
```

---

## 10. Dashboard additions

Phase 2 dashboard work is **read-only**, like Phase 1.

### 10.1 Stock page (`/stocks/[symbol]`) extended
- **Overlays on the candle chart:** toggles for SMA 20/50/200, EMA, Bollinger Bands.
- **Pattern markers:** small markers on candles where a pattern signal occurred, coloured by direction, with a tooltip showing `description` and the trend state.
- **Indicator panels** under the chart: RSI (with 30/70 lines), MACD (line, signal, histogram), volume with its average.
- **Signals list:** recent signals for this stock, newest first, with filters by type and direction.
- **Trend state badge** at the top (uptrend / downtrend / sideways) with the rule inputs on hover.
- **Data-quality badges:** visible warning if `possible_split_or_bonus` or `short_history` flags exist.
- Marker/overlay data is read on demand for the visible date range, not streamed.

### 10.2 `/lab` Signal Lab
- Table of event-study results: signal, direction, horizon, scope (stock or pooled), sample, **n_independent**, mean return, win rate, **baseline**, **edge**.
- Filters: signal, scope, horizon, sample (all / in-sample / out-of-sample).
- Clear visual treatment:
  - "Insufficient sample" rows greyed out with a label.
  - In-sample and out-of-sample edge **side by side**, so a collapse out-of-sample is obvious.
  - A permanent short note explaining baseline and edge.
- A small panel: number of signals and horizons tested (so multiple-testing risk is visible).

### 10.3 `/backtests` and `/backtests/[runId]`
- List of runs: name, strategy, symbols, period, created date, code version.
- Run detail: parameters and costs, per-symbol metrics next to buy-and-hold, equity curve versus buy-and-hold, in-sample versus out-of-sample, trade list with the exit reason.
- A prominent warning on sweep-derived results and on any strategy that loses to buy-and-hold.

### 10.4 Status strip and live feed
- Add tiles for `signals` and `backtest` to the Phase 1 status strip.
- Their logbook events appear in the existing live feed and filters with no extra work, because they use the same writer.

---

## 11. Build tasks (do in this order)

| # | Task | Check |
|---|---|---|
| 1 | Backfill about 3 years of candles (section 3) | Each watchlist stock has roughly 700+ daily rows (verify per source). |
| 2 | Add `002_signals.sql`, run it, extend read-only RLS | New tables exist; browser can read but not write. |
| 3 | Create `signals/` with its own environment; test `import talib` | Import works in a tiny script. |
| 4 | Implement trend, momentum, volatility and volume indicators | Output has nulls only in the warm-up period. |
| 5 | **Cross-check** TA-Lib against pandas-ta (or hand calculation) | Values agree within tolerance in tests. |
| 6 | Implement incremental watermark logic | Second run writes nothing new; adding one candle writes exactly that day. |
| 7 | Implement pattern wrappers with `description` and trend context | A hand-built doji / engulfing sample is detected with the right sign. |
| 8 | Implement crossover rules, `trend_state`, and swing levels (confirmation-date rule) | Unit tests with hand-made series pass, including the no-look-ahead check for levels. |
| 9 | Implement `quality.py` flags | A fake 50% jump triggers `possible_split_or_bonus`. |
| 10 | Wire logbook events; run on the full watchlist | Events appear live on the dashboard; one forced failure does not stop the run. |
| 11 | Dashboard: chart overlays, pattern markers, indicator panels, signals list | Chart matches independently computed values for a spot-checked day. |
| 12 | Add `003_backtest.sql`, run it | Tables exist. |
| 13 | Create `backtest/` with its own environment; confirm VectorBT installs | A tiny sample backtest runs. |
| 14 | Hand-verify timing: tiny dataset, known signal, check the fill is next open, with costs | Numbers match a manual calculation. |
| 15 | Implement `event_study.py` including baseline and independent counts | Hand-built case gives the expected counts and edge. |
| 16 | Implement exclusions around split flags | Excluded windows are logged as `warning`. |
| 17 | Implement strategies and metrics; buy-and-hold benchmark | Benchmark matches a manual total return. |
| 18 | Implement chronological in-sample / out-of-sample split | No overlap or shuffling; verified by a test. |
| 19 | Write results with config and git commit hash | Re-running with the same config reproduces the numbers. |
| 20 | Dashboard: Signal Lab, Backtests list and detail | Insufficient-sample rows are visibly marked; sweep warning appears. |
| 21 | Failure drills (section 13) | All pass. |
| 22 | Write READMEs including the interpretation guide (section 8) | A new reader can run and understand Phase 2 from them. |

---

## 12. Module README requirements

Same format as Phase 1: purpose, reads, writes, config, how to run, logbook events, known limitations. Additionally:

- `signals/README.md`: the exact definition of every `signal_key`, the `logic_version` policy (bump on any rule change), and the daily-timestamp convention.
- `backtest/README.md`: the timing rule, the exit definition for event studies, cost assumptions, the sample split, and the interpretation guide.

---

## 13. Testing and failure drills

### Unit tests
- **Indicators:** compared against a second library or hand-calculated values on small samples; warm-up rows are null.
- **Patterns:** synthetic candle sequences designed to be (and not be) a specific pattern.
- **Rules:** crossovers fire only on the crossing day, not every day the condition holds.
- **Swing levels:** a swing high is not emitted before its confirmation date.
- **Quality flags:** each flag has a triggering and a non-triggering example.
- **Event study:** a tiny hand-made series where returns, baseline, edge and independent counts are known.
- **Backtest engine:** known trades produce known returns after costs; entry is the next open; buy-and-hold matches the manual result.
- **Split:** in-sample dates are strictly earlier than out-of-sample dates.

### Failure drills (all must pass)

| Drill | Expected result |
|---|---|
| Symbol with fewer candles than the warm-up | `skipped` event with a reason; other symbols continue. |
| Candle series with an injected 50% one-day jump | `possible_split_or_bonus` flag; backtest excludes the window and logs a `warning`. |
| A gap of many missing days | `gap_in_data` flag; no crash. |
| Run signals twice in a row | No duplicates; second run writes nothing new. |
| Delete the latest day's signals, re-run | Exactly that day is recomputed. |
| Change a rule and bump `logic_version`, re-run with `--recompute` | Old rows replaced; new version visible in the rows. |
| Backtest with a signal that has too few events | Result appears as "insufficient sample", never as a finding. |
| Run the same backtest twice | Identical numbers; both runs store the same config and commit hash. |
| Break the database key | Clear error, non-zero exit, nothing silently lost. |
| Dashboard open while signals run | Events stream into the live feed; overlays refresh on reload. |

---

## 14. Acceptance criteria (Definition of Done)

Phase 2 is complete when **all** are true:

- [ ] About 3 years of validated candles exist for every watchlist stock.
- [ ] `002_signals.sql` and `003_backtest.sql` are applied; new tables have read-only RLS for the browser.
- [ ] `python signals/main.py --all` computes indicators, patterns, rules, trend state, levels and quality flags.
- [ ] Re-running it is incremental and creates no duplicates.
- [ ] TA-Lib and pandas-ta (or hand-calculated) values agree in tests.
- [ ] Levels and signals never use information that was not yet known on their `ts` (look-ahead tests pass).
- [ ] The backtest timing rule (next-open entry, costs applied) is verified on a hand-checked example.
- [ ] Event-study results include baseline, edge, independent counts, and in-sample / out-of-sample splits.
- [ ] At least three strategies plus buy-and-hold run, each reporting metrics against the benchmark.
- [ ] Every backtest run stores its full configuration and git commit hash and is reproducible.
- [ ] Split/bonus-flagged windows are excluded from statistics.
- [ ] Dashboard shows overlays, pattern markers, indicator panels, Signal Lab and Backtests pages, with insufficient-sample and sweep warnings.
- [ ] Every action of both modules appears in `agent_events` with a shared `run_id` per run.
- [ ] All failure drills in section 13 pass.
- [ ] No module imports another module's code (only `shared/`).
- [ ] No paid service, no trading function, no secret in git or in browser code.

---

## 15. Risks and how to handle them

| Risk | Handling |
|---|---|
| Unadjusted splits and bonuses create fake signals and fake backtest results | Quality flags, exclusion windows, and a refusal to trust flagged symbols. Consider adding a split-adjusted source later (a Phase 5 hardening item). |
| Look-ahead bias | Next-open timing, swing-confirmation dates, hand-checked tests. |
| Overfitting from many tests | Report combinations tested; out-of-sample reporting; minimum sample; treat winners as hypotheses. |
| Overlapping events inflate evidence | Independent-event counts. |
| Library installation or version problems (TA-Lib C library, Numba) | Separate environments per module; tiny smoke tests first; pin versions once working. |
| Small watchlist gives noisy statistics | Pooled scope, minimum sample, and honest "insufficient" labels. Expand the watchlist gradually if the free data sources allow. |
| Cost assumptions are wrong | Placeholders are labelled as such; replace with real broker charges before trusting results. |
| Dashboard makes weak results look impressive | Mandatory baseline, sample size and out-of-sample columns; permanent explanatory note. |
| Over-building | Stick to section 2. Anything else waits for its phase. |

---

## 16. Rules for any AI agent working on Phase 2

1. Read `PROJECT_OVERVIEW.md`, `PHASE_1.md` and this file before writing code.
2. Work only in the folder for the task at hand. `signals/` and `backtest/` never import each other or any other module (only `shared/`).
3. Do not change existing tables. New tables or columns need a new numbered migration and README updates.
4. Log every real action with the shared logbook writer.
5. Bump `logic_version` whenever any signal rule or parameter changes.
6. Never remove the baseline, sample-size, or out-of-sample columns from results to make them look better.
7. Never fabricate or hard-code backtest numbers. Everything must come from stored data and reproducible code.
8. Do not add paid services, order placement, or shorting.
9. Do not start Phase 3+ work, even if it looks easy.
10. If a library's behaviour is uncertain (installation, fill-price semantics, parameter meanings), say so and test it with a small hand-checked script instead of guessing.
11. Never present results as predictions or investment advice.

---

## 17. What Phase 3 and Phase 4 will need from Phase 2

- A stable `signals` table with human-readable `description` text, so agents can cite evidence without re-deriving it.
- `signal_stats` and `backtest_results` that tell agents **how much a signal deserves to be trusted**. In Phase 4, an agent that mentions "bullish engulfing" should be able to attach its measured edge and sample size, or say it has none.
- Trend state and data-quality flags available as context for every stock.
- In Phase 3, news events will be compared against price moves using the same event-study approach, so keep `event_study.py` generic enough to take any dated event list (not just signal rows).
- A decision, made after running manually for a while, on whether Phase 5 scheduling will be cron-based or a `jobs` table. Phase 2 uses simple watermarks and does not need either.
