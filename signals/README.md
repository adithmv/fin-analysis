# Signals

Computes deterministic daily indicators and research signals for active NSE
watchlist equities. Reads `candles` and `watchlist`; writes `indicator_values`,
`signals`, and `agent_events`. `--all` selects only active `kind=equity` rows. No imports
from ingest or backtest. Configuration: root `.env` and `config/signals.yaml`.

## Run

```powershell
uv venv --python 3.12 signals/.venv
uv pip install --python signals/.venv/Scripts/python.exe -r signals/requirements.txt -e ./shared
signals/.venv/Scripts/python.exe signals/main.py --all
signals/.venv/Scripts/python.exe signals/main.py --symbols RELIANCE --recompute
signals/.venv/Scripts/python.exe signals/main.py --all --since 2025-01-01
signals/.venv/Scripts/python.exe -m pytest signals/tests -q
```

Use the module environment's Python when running `python signals/main.py`.
TA-Lib 0.8.2 wheel includes its native library on this Windows installation.
Pandas TA's published package is a prerelease with additional Numba constraints;
we use TA-Lib plus independent hand/pandas calculations in tests instead.

## Definitions

Series: `sma_<period>`, `ema_<period>`, `rsi_<period>`,
`macd_line/signal/hist_<fast>_<slow>_<signal>`, `adx_<period>`,
`stoch_k/d_<k>_<smooth>_<d>`, `bb_upper/middle/lower_<period>_<stddev>`,
`atr_<period>`, `obv`, `volume_avg_<period>`. Warm-up is null, never zero.
Missing volume makes cumulative OBV unavailable rather than inventing volume.

- `cdl_<name>`: configured TA-Lib pattern outputs, nonzero only; raw sign maps to
  bullish/bearish and magnitude is preserved. This follows the specified mapping,
  including doji; the direction is a pattern convention, not a forecast.
- `sma_50_200_golden_cross` / `death_cross`: strict above/below today after
  at-or-below/at-or-above yesterday. Both inputs must be available.
- `macd_bull_cross` / `macd_bear_cross`: MACD crosses its signal line.
- `rsi_14_oversold` / `overbought`: RSI crosses below/above configured thresholds.
- `bb_lower_touch` / `bb_upper_touch`: close crosses strictly outside the band.
- `new_<window>d_high` / `low`: close reaches the rolling close extreme, emitted
  on transition into the condition, not each consecutive record day.
- `volume_spike`: volume first exceeds the configured multiple of 20-day mean.
- `trend_state`: daily uptrend/downtrend/sideways using close, SMA50, SMA200 and
  ADX14. `unknown` during warm-up; inputs are included in details.
- `swing_high` / `swing_low`: unique extreme within N candles on each side;
  emitted only on the confirmation date, N sessions after the pivot. Pivot date
  and price are in details. Tied extremes are deliberately not pivots.
- `possible_split_or_bonus`: absolute close return above configured threshold.
- `gap_in_data`: missing weekdays between adjacent candles exceed threshold.
- `short_history`: point-in-time history shorter than the longest configured SMA.
- `zero_volume_streak`: first day a zero-volume streak reaches its threshold.

The initial rule set requires SMA50/200, RSI14, ADX14 and volume-average20. These
periods must remain configured unless the rule implementation and version change.
Daily timestamps use midnight IST converted to UTC, matching Phase 1.

## Incremental correctness

For this small universe all history is computed, then only missing/incomplete or
changed days are written. This deliberately improves on a truncated 400-row tail:
OBV is cumulative and EMA/RSI/ADX depend on recursive seeds. Full-history computation
keeps incremental values exactly consistent with full recomputation. Stored trend
rows carry configuration and cumulative candle hashes. New candles, revised
history, deleted trend rows, or missing indicator series trigger replacement.
Each batch of up to 40 days is replaced transactionally with service-only
`replace_signal_days`; stale signals disappear on recompute. A version change
invalidates previous days. Any parameter/rule change requires `logic_version`
to be bumped, even with `--recompute`.

Events: run_start/end, load_candles, compute_indicators, compute_patterns,
compute_rules, quality_check, write_signals. Exceptions are isolated per symbol;
failed symbols give exit 1. No-change writes log skipped. Short histories retain
valid short-period output and explicit flags while unavailable long periods stay
null. Quality checks describe historical data, not recommendations.
