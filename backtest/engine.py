"""Long-only schedule executed by VectorBT; same exclusions for benchmark."""

import numpy as np
import pandas as pd
import vectorbt as vbt
from .costs import rates
from .splits import exclusion_mask
from .strategies import STRATEGIES


def simulate(frame, signals, config, strategy_key, parameters, bounds):
    a, b = bounds
    entry, exit, max_hold = STRATEGIES[strategy_key]().decisions(frame, signals, parameters)
    excluded, windows = exclusion_mask(frame, signals, config)
    n = b - a
    orders = np.full(n, np.nan)
    fills = frame.open.to_numpy(float)[a:b].copy()
    held = False
    entry_i = None
    records = []
    current = None
    for i in range(a, b):
        j = i - a
        if excluded[i]:
            continue
        enter = strategy_key == "buy_and_hold" or (i > a and entry[i - 1] and not excluded[i - 1])
        leave = held and i > a and (exit[i - 1] or (max_hold is not None and i - entry_i >= max_hold))
        if leave:
            orders[j] = -np.inf
            held = False
            current.update(
                exit_index=i,
                exit_reason="time_stop" if max_hold is not None and i - entry_i >= max_hold else "signal",
            )
            records.append(current)
            current = None
        # Avoid buying at the open only to force liquidation at this same close.
        if not held and not leave and enter and i < b - 1 and not excluded[i + 1]:
            orders[j] = np.inf
            held = True
            entry_i = i
            current = {"entry_index": i}
        if held and (i == b - 1 or excluded[i + 1]):
            # End-of-data and known retrospective exclusion boundaries liquidate
            # at this close. Exclusions are a data filter, not a tradable forecast.
            orders[j] = -np.inf
            fills[j] = float(frame.iloc[i].close)
            held = False
            current.update(exit_index=i, exit_reason="end_of_data" if i == b - 1 else "data_exclusion")
            records.append(current)
            current = None
    fee, slip = rates(config)
    close = pd.Series(frame.close.to_numpy(float)[a:b], index=pd.DatetimeIndex(frame.ts[a:b]))
    portfolio = vbt.Portfolio.from_orders(
        close,
        size=orders,
        price=fills,
        fees=fee,
        slippage=slip,
        init_cash=config["initial_capital"],
        direction="longonly",
        freq="1D",
    )
    equity = np.asarray(portfolio.value(), float)
    trade_rows = []
    for record in records:
        i, k = record["entry_index"], record["exit_index"]
        entry_price = float(frame.iloc[i].open) * (1 + slip)
        exit_price = float(fills[k - a]) * (1 - slip)
        net = exit_price * (1 - fee) / (entry_price * (1 + fee)) - 1
        trade_rows.append(
            dict(
                entry_ts=frame.iloc[i].ts.isoformat(),
                exit_ts=frame.iloc[k].ts.isoformat(),
                entry_price=entry_price,
                exit_price=exit_price,
                return_pct=net * 100,
                bars_held=k - i,
                exit_reason=record["exit_reason"],
            )
        )
    if len(portfolio.trades.records) != len(trade_rows):
        raise RuntimeError("Trade schedule differs from VectorBT execution")
    capital = config["initial_capital"]
    total = float(equity[-1] / capital - 1)
    returns = np.diff(np.r_[capital, equity]) / np.r_[capital, equity[:-1]]
    rf = (1 + config["risk"]["risk_free_rate_annual"]) ** (1 / config["risk"]["trading_days_per_year"]) - 1
    std = returns.std(ddof=1) if n > 1 else 0
    sharpe = (
        float((returns.mean() - rf) / std * np.sqrt(config["risk"]["trading_days_per_year"]))
        if std > 0
        else None
    )
    peak = np.maximum.accumulate(np.r_[capital, equity])[1:]
    elapsed = max(1, (frame.iloc[b - 1].ts - frame.iloc[a].ts).days + 1)
    metrics = dict(
        total_return=total,
        cagr=float((equity[-1] / capital) ** (365.25 / elapsed) - 1),
        max_drawdown=float(np.min(equity / peak - 1)),
        sharpe=sharpe,
        win_rate=float(np.mean([t["return_pct"] > 0 for t in trade_rows])) if trade_rows else None,
        n_trades=len(trade_rows),
        average_trade_return=float(np.mean([t["return_pct"] / 100 for t in trade_rows]))
        if trade_rows
        else None,
        average_holding_days=float(np.mean([t["bars_held"] for t in trade_rows])) if trade_rows else None,
        exposure=float(np.asarray(portfolio.assets() > 0, dtype=float).mean()),
        excluded_bars=int(excluded[a:b].sum()),
        observations=n,
    )
    indices = np.unique(np.linspace(0, n - 1, min(n, 500), dtype=int))
    curve = [
        [frame.iloc[a + i].ts.tz_convert("Asia/Kolkata").date().isoformat(), float(equity[i])]
        for i in indices
    ]
    return metrics, curve, trade_rows, windows
