# Backtest

Deterministic event studies and long-only VectorBT simulations. Reads stored `candles`, `signals` and the active `watchlist`; writes `signal_stats`, `backtest_runs`, `backtest_results`, `backtest_trades` and `agent_events`. No network price fetching, recommendations, or order placement.

Use Python 3.12 in a separate environment. Install `requirements-lock.txt` and `pip install -e shared` from the repository root. Plotly is pinned to 5.24.1 because VectorBT's plotting imports are incompatible with Plotly 7.

```powershell
backtest/.venv/Scripts/python.exe backtest/main.py events --all
backtest/.venv/Scripts/python.exe backtest/main.py events --signal cdl_engulfing
backtest/.venv/Scripts/python.exe backtest/main.py strategy sma_cross --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy rsi_reversion --symbols TCS,INFY
backtest/.venv/Scripts/python.exe backtest/main.py strategy pattern_trend --all
backtest/.venv/Scripts/python.exe backtest/main.py strategy buy_and_hold --all
backtest/.venv/Scripts/python.exe -m pytest backtest/tests -q
```

Configuration: `config/backtest.yaml`, overridable with `--config`. Defaults are illustrative costs (0.10% fees and 0.05% slippage on each side), not verified broker charges. Every run stores the complete config, git commit, source-file hash, working-tree status, dependency versions, data hashes, signal versions, split dates and number of parameter combinations (one; no automated sweep). Missing or stale signals cause a clear failure. New runs have new IDs; identical inputs and configuration reproduce numbers. The logbook records start, loading, exclusions, computations, writes and completion/failure. Database reads retry transient transport errors up to three attempts; persistent errors fail the run.

## Timing and calculations

Signals known at close i enter at open i+1. Event horizon h exits at close i+h, so h=1 means the next session's open-to-close return. Each side pays fees and slippage. Bullish events use the net long return; bearish events use negative gross return minus the same round-trip cost penalty. Unlike simply negating a net long return, costs never become a bearish benefit. This is directional evidence, not a short-selling execution model.

Raw event counts include eligible occurrences. Independent events are greedily spaced more than h sessions apart per stock and signal/direction; statistics use those independent events. Baselines use all eligible dates for the same stock, direction, horizon and sample with identical costs. Pooled baselines weight each stock by its independent-event count; cross-stock events can still be correlated. Returns are fractions in storage, except `backtest_trades.return_pct`, which is percent.

The chronological 70/30 split is per stock. Neither signals nor outcomes cross a sample boundary. Indicators retain earlier warm-up history; positions do not. In-sample and out-of-sample simulations each start with the same initial capital. Strategy signals are evaluated at close and filled next open, with one long position and no same-session re-entry. SMA crossover, RSI reversion, bullish pattern plus trend, and buy-and-hold are available. Time stops exit at open after the configured number of held bars; final holdings close at the final session's close.

Short history, gaps, and windows around suspected splits are excluded. A position closes at the close preceding an exclusion. This is retrospective data filtering, not a forecast a trader could have made. Benchmarks use exactly the same exclusions and sample dates. Flat excluded periods remain in the equity/annualisation calendar. Average holding days means trading-bar intervals. Exposure is the fraction of sessions holding assets at close. Sharpe uses daily returns (including the initial cost), sample standard deviation, configured annual risk-free rate and 250 trading days. CAGR uses actual calendar duration, minimum one day. Drawdown includes starting capital. Curves retain at most 500 evenly spaced observations; metrics use every observation.

## Interpretation

A positive edge in both samples, with sufficient independent evidence across several stocks, is a hypothesis worth watching. One positive stock/horizon with a small sample is likely noise. Good in-sample and weak out-of-sample results suggest fitting to the past. These are historical results on a small watchlist, not predictions or advice. Finding no edge is useful. Changing parameters after viewing out-of-sample results makes that sample part of the research process; reserve fresh data for confirmation.
# Phase 3 event sources

`events --source news` and `events --source sentiment` read only stored tables.
Use `--event-type earnings_result` to narrow news studies. Canonical story groups,
known timestamps and links with at least the configured confidence are mandatory.
Entries are at the effective session open, exits at close h-1 sessions later.
Phase 2 split/gap/warm-up exclusions and chronological samples remain in force.
Independent entries are spaced more than h sessions, conservatively matching Phase 2.

Signed returns include fees/slippage. Abnormal rows subtract the signed NIFTY 50
gross return over exactly the same entry/exit dates; every stock session must be
present in the index. Absolute moves are **before costs**, based on the raw stock
move (or raw stock minus index move), so directionless news can be studied as
volatility. Baselines use the same eligible windows, direction, costs and adjustment.
Pooled baselines are weighted by independent event count, and correlated stocks
are not independent market experiments. Config, source/input hashes, model/rule
versions and number of tested key/horizon/adjustment combinations are saved.

