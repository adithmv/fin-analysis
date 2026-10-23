"use client";
import { useEffect, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { pct, readResearch } from "@/lib/research";
import { ResearchNote } from "./research-note";
type Stat = {
  id: number;
  stats_run_id: string;
  signal_key: string;
  direction: string;
  scope: string;
  sample: string;
  horizon_days: number;
  n_events: number;
  n_independent: number;
  mean_return: number | null;
  win_rate: number | null;
  baseline_mean: number | null;
  edge: number | null;
  sufficient_sample: boolean;
  config: Record<string, unknown>;
  computed_at: string;
};
export function SignalLab() {
  const [rows, setRows] = useState<Stat[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [signal, setSignal] = useState(""),
    [scope, setScope] = useState("POOLED"),
    [horizon, setHorizon] = useState("5"),
    [sample, setSample] = useState("out_of_sample");
  useEffect(() => {
    let active = true;
    async function load() {
      const client = getBrowserClient();
      if (!client) throw new Error("Database connection unavailable");
      const { data, error } = await client
        .from("signal_stats")
        .select("stats_run_id")
        .order("computed_at", { ascending: false })
        .limit(1);
      if (error) throw error;
      if (data.length) {
        const all = await readResearch<Stat>("signal_stats", [
          "stats_run_id",
          data[0].stats_run_id,
        ]);
        if (active) setRows(all);
      }
    }
    void load()
      .catch((e) => {
        if (active) setError(String(e.message ?? e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const filtered = rows.filter(
    (r) =>
      (!signal || r.signal_key === signal) &&
      (!scope || r.scope === scope) &&
      (!horizon || r.horizon_days === Number(horizon)) &&
      r.sample === sample,
  );
  const counterpart = (r: Stat, s: string) =>
    rows.find(
      (x) =>
        x.signal_key === r.signal_key &&
        x.direction === r.direction &&
        x.scope === r.scope &&
        x.horizon_days === r.horizon_days &&
        x.sample === s,
    );
  return (
    <div className="page">
      <div className="eyebrow">SIGNALS / HISTORICAL EVIDENCE</div>
      <h1>Signal Lab</h1>
      <p className="subtitle">
        Did a signal beat its matched baseline, and did that hold up on later
        data?
      </p>
      <ResearchNote />
      {loading && <p role="status">Loading event studies…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="stats">
        <div>
          <label>SIGNALS TESTED</label>
          <strong>{new Set(rows.map((r) => r.signal_key)).size}</strong>
        </div>
        <div>
          <label>HORIZONS TESTED</label>
          <strong>{new Set(rows.map((r) => r.horizon_days)).size}</strong>
        </div>
        <div>
          <label>PARAMETER COMBINATIONS</label>
          <strong>{String(rows[0]?.config.combinations_tested ?? 0)}</strong>
        </div>
      </div>
      <p className="attribution">
        More signals and horizons mean more chances to find an apparent edge by
        luck. Pooled events may be correlated across stocks.
      </p>
      <section className="panel">
        <div className="filters">
          <label>
            Signal
            <select value={signal} onChange={(e) => setSignal(e.target.value)}>
              <option value="">All signals</option>
              {[...new Set(rows.map((r) => r.signal_key))].sort().map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <label>
            Scope
            <select value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="">All scopes</option>
              {[...new Set(rows.map((r) => r.scope))].sort().map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <label>
            Horizon
            <select
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
            >
              <option value="">All horizons</option>
              {[1, 3, 5, 10, 20].map((k) => (
                <option key={k} value={k}>
                  {k} sessions
                </option>
              ))}
            </select>
          </label>
          <label>
            Sample
            <select value={sample} onChange={(e) => setSample(e.target.value)}>
              <option value="all">All dates</option>
              <option value="in_sample">In-sample</option>
              <option value="out_of_sample">Out-of-sample</option>
            </select>
          </label>
        </div>
        <div className="research-scroll">
          <table>
            <thead>
              <tr>
                {[
                  "Signal / direction",
                  "Scope",
                  "Horizon",
                  "Sample",
                  "Events / independent",
                  "Mean return",
                  "Win rate",
                  "Baseline",
                  "Edge",
                  "IS edge / n",
                  "OOS edge / n",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr
                  key={r.id}
                  className={r.sufficient_sample ? "" : "insufficient"}
                >
                  <td>
                    {r.signal_key}
                    <small>
                      {r.direction}
                      {!r.sufficient_sample && " · Insufficient sample"}
                    </small>
                  </td>
                  <td>{r.scope}</td>
                  <td>{r.horizon_days}</td>
                  <td>{r.sample.replaceAll("_", " ")}</td>
                  <td>
                    {r.n_events} / <strong>{r.n_independent}</strong>
                  </td>
                  <td>{pct(r.mean_return)}</td>
                  <td>{pct(r.win_rate)}</td>
                  <td>{pct(r.baseline_mean)}</td>
                  <td>{pct(r.edge)}</td>
                  {["in_sample", "out_of_sample"].map((s) => {
                    const other = counterpart(r, s);
                    return (
                      <td key={s}>
                        {pct(other?.edge)} / {other?.n_independent ?? 0}
                        {!other?.sufficient_sample && (
                          <small>Insufficient sample</small>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !filtered.length && (
          <div className="empty">
            No event-study results match these filters.
          </div>
        )}
      </section>
      {rows[0] && (
        <details className="research-note">
          <summary>Run provenance · {rows[0].stats_run_id}</summary>
          <pre>{JSON.stringify(rows[0].config, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
