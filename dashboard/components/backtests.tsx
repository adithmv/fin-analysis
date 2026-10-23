"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createChart, LineSeries, type Time } from "lightweight-charts";
import { readResearch, pct } from "@/lib/research";
import { money, sessionDate, dateTime } from "@/lib/types";
import { ResearchNote } from "./research-note";
type Run = {
  id: string;
  name: string;
  strategy_key: string;
  symbols: string[];
  period_start: string;
  period_end: string;
  created_at: string;
  code_version: string;
  fees_pct: number;
  slippage_pct: number;
  config: Record<string, unknown>;
};
type Result = {
  symbol: string;
  sample: string;
  metrics: Record<string, number | null>;
  benchmark_metrics: Record<string, number | null>;
  equity_curve: [string, number][];
  benchmark_equity_curve: [string, number][];
};
type Trade = {
  id: number;
  symbol: string;
  sample: string;
  entry_ts: string;
  exit_ts: string;
  entry_price: number;
  exit_price: number;
  return_pct: number;
  bars_held: number;
  exit_reason: string;
};
export function Backtests({ runId }: { runId?: string }) {
  const [runs, setRuns] = useState<Run[]>([]),
    [results, setResults] = useState<Result[]>([]),
    [trades, setTrades] = useState<Trade[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(true),
    [symbol, setSymbol] = useState(""),
    [sample, setSample] = useState("out_of_sample");
  useEffect(() => {
    let active = true;
    setBusy(true);
    void Promise.all([
      readResearch<Run>("backtest_runs", runId ? ["id", runId] : undefined),
      runId
        ? readResearch<Result>("backtest_results", ["run_id", runId])
        : Promise.resolve([]),
      runId
        ? readResearch<Trade>("backtest_trades", ["run_id", runId])
        : Promise.resolve([]),
    ])
      .then(([r, v, t]) => {
        if (active) {
          setRuns(r.sort((a, b) => b.created_at.localeCompare(a.created_at)));
          setResults(v);
          setTrades(t);
          setSymbol(v[0]?.symbol ?? "");
        }
      })
      .catch((e) => {
        if (active) setError(String(e));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [runId]);
  const run = runs[0],
    result = results.find((r) => r.symbol === symbol && r.sample === sample);
  const selectedTrades = trades
    .filter((t) => t.symbol === symbol && t.sample === sample)
    .sort((a, b) => a.entry_ts.localeCompare(b.entry_ts));
  const format = (key: string, value: number | null | undefined) =>
    value == null
      ? "—"
      : key === "sharpe" || key === "average_holding_days"
        ? Number(value).toFixed(2)
        : ["n_trades", "observations", "excluded_bars"].includes(key)
          ? String(value)
          : pct(value);
  return (
    <div className="page">
      {runId && (
        <Link className="back" href="/backtests">
          ← All backtests
        </Link>
      )}
      <div className="eyebrow">STRATEGIES / HISTORICAL TESTING</div>
      <h1>{runId ? (run?.name ?? "Backtest details") : "Backtests"}</h1>
      <p className="subtitle">
        Next-open execution, trading costs, and the same-period buy-and-hold
        benchmark.
      </p>
      <ResearchNote />
      {busy && <p role="status">Loading saved runs…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!runId ? (
        <section className="panel research-scroll">
          <table>
            <thead>
              <tr>
                <th>Run / strategy</th>
                <th>Stocks</th>
                <th>Period</th>
                <th>Created</th>
                <th>Code version</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link href={`/backtests/${r.id}`}>{r.name}</Link>
                    <small>{r.strategy_key}</small>
                  </td>
                  <td>{r.symbols.join(", ")}</td>
                  <td>
                    {r.period_start} — {r.period_end}
                  </td>
                  <td>{dateTime(r.created_at)}</td>
                  <td>
                    <code>{r.code_version.slice(0, 8)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!busy && !runs.length && (
            <div className="empty">No saved strategy runs yet.</div>
          )}
        </section>
      ) : run ? (
        <>
          <div className="research-note">
            <strong>Costs per side:</strong> {Number(run.fees_pct).toFixed(2)}%
            fees + {Number(run.slippage_pct).toFixed(2)}% slippage. Illustrative
            assumptions, not verified broker charges. Code{" "}
            <code>{run.code_version.slice(0, 8)}</code>. Exclusion boundaries
            are retrospective data filters.
          </div>
          {(Number(run.config.combinations_tested ?? 1) > 1 ||
            run.config.sweep) && (
            <div className="error">
              Parameter sweep: multiple combinations were tried. The best
              historical result can overstate the evidence.
            </div>
          )}
          <div className="filters">
            <label>
              Stock
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              >
                {run.symbols.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              Sample
              <select
                value={sample}
                onChange={(e) => setSample(e.target.value)}
              >
                <option value="all">All dates</option>
                <option value="in_sample">In-sample</option>
                <option value="out_of_sample">Out-of-sample</option>
              </select>
            </label>
          </div>
          {result && (
            <>
              {Number(result.metrics.total_return) <
                Number(result.benchmark_metrics.total_return) && (
                <p className="error">
                  This strategy lost to buy-and-hold for {symbol} in this
                  sample.
                </p>
              )}
              <section className="panel">
                <div className="panel-heading">
                  <h2>
                    {symbol} · {sample.replaceAll("_", " ")}
                  </h2>
                  <span>Green: strategy · Gold: buy-and-hold</span>
                </div>
                <EquityChart result={result} />
                <div className="research-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Strategy</th>
                        <th>Buy-and-hold</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(result.metrics).map((k) => (
                        <tr key={k}>
                          <td>{k.replaceAll("_", " ")}</td>
                          <td>{format(k, result.metrics[k])}</td>
                          <td>{format(k, result.benchmark_metrics[k])}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
          <h2>In-sample vs out-of-sample</h2>
          <div className="panel research-scroll">
            <table>
              <thead>
                <tr>
                  <th>Sample</th>
                  <th>Strategy return</th>
                  <th>Buy-and-hold</th>
                  <th>Trades</th>
                  <th>Drawdown</th>
                </tr>
              </thead>
              <tbody>
                {results
                  .filter((r) => r.symbol === symbol)
                  .map((r) => (
                    <tr key={r.sample}>
                      <td>{r.sample.replaceAll("_", " ")}</td>
                      <td>{pct(r.metrics.total_return)}</td>
                      <td>{pct(r.benchmark_metrics.total_return)}</td>
                      <td>{r.metrics.n_trades}</td>
                      <td>{pct(r.metrics.max_drawdown)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <h2>Trades · {selectedTrades.length}</h2>
          <div className="panel research-scroll">
            <table>
              <thead>
                <tr>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Entry price</th>
                  <th>Exit price</th>
                  <th>After-cost return</th>
                  <th>Bars held</th>
                  <th>Exit reason</th>
                </tr>
              </thead>
              <tbody>
                {selectedTrades.map((t) => (
                  <tr key={t.id}>
                    <td>{sessionDate(t.entry_ts)}</td>
                    <td>{sessionDate(t.exit_ts)}</td>
                    <td>{money(Number(t.entry_price))}</td>
                    <td>{money(Number(t.exit_price))}</td>
                    <td>{Number(t.return_pct).toFixed(2)}%</td>
                    <td>{t.bars_held}</td>
                    <td>{t.exit_reason.replaceAll("_", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!selectedTrades.length && (
              <div className="empty">No trades in this sample.</div>
            )}
          </div>
          <details className="research-note">
            <summary>
              Parameters, split dates and reproducibility details
            </summary>
            <pre>{JSON.stringify(run.config, null, 2)}</pre>
          </details>
        </>
      ) : (
        !busy && <div className="empty">Run not found.</div>
      )}
    </div>
  );
}
function EquityChart({ result }: { result: Result }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: { textColor: "#687d75" },
    });
    [result.equity_curve, result.benchmark_equity_curve].forEach((curve, i) => {
      chart
        .addSeries(LineSeries, {
          color: i ? "#c39c39" : "#229779",
          lineWidth: 2,
          title: i ? "Buy-and-hold" : "Strategy",
        })
        .setData(
          (curve ?? []).map(([time, value]) => ({ time: time as Time, value })),
        );
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [result]);
  return (
    <div
      ref={ref}
      className="chart"
      role="img"
      aria-label="Strategy equity versus buy-and-hold"
    />
  );
}
