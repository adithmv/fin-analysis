"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { agentRows, Report, Thread } from "@/lib/agents";
import { useLogin, LoginRequired } from "./auth";

type Outcome = {
  report_id: string;
  horizon_days: number;
  entry_date: string;
  exit_date: string;
  realized_return: number;
  benchmark_return: number;
  excess_return: number;
  directional_hit: boolean | null;
};
const pct = (v: number) => `${(100 * v).toFixed(2)}%`;
function score(rows: Outcome[]) {
  const scored = rows.filter((r) => r.directional_hit !== null),
    n = scored.length;
  if (!n) return "No directional outcomes yet";
  const p = scored.filter((r) => r.directional_hit).length / n,
    z = 1.96,
    d = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / d,
    half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d;
  return `${pct(p)} · ${n} outcomes · 95% interval ${pct(centre - half)}–${pct(centre + half)}`;
}
export function TrackRecord() {
  const { loggedIn, ready } = useLogin();
  const [reports, R] = useState<Report[]>([]),
    [threads, T] = useState<Thread[]>([]),
    [outcomes, O] = useState<Outcome[]>([]),
    [error, E] = useState("");
  const [mode, M] = useState("live"),
    [horizon, H] = useState(10);
  useEffect(() => {
    if (!loggedIn) return;
    let active = true;
    const load = () =>
      void Promise.all([
        agentRows<Report>("analysis_reports"),
        agentRows<Thread>("threads"),
        agentRows<Outcome>("report_outcomes", undefined, "report_id"),
      ])
        .then(([r, t, o]) => {
          if (active) {
            R(r);
            T(t);
            O(o);
          }
        })
        .catch((e) => {
          if (active) E(e.message);
        });
    load();
    const timer = setInterval(load, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [loggedIn]);
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  const selected = reports.filter(
    (r) =>
      Boolean(threads.find((t) => t.id === r.thread_id)?.config.replay) ===
      (mode === "replay"),
  );
  const byId = new Map(selected.map((r) => [r.id, r]));
  const relevant = outcomes.filter(
    (o) => o.horizon_days === horizon && byId.has(o.report_id),
  );
  const clean = relevant.filter(
    (o) => !byId.get(o.report_id)?.verification_summary.severe,
  );
  const groups = ["stance", "confidence", "evidence_strength"] as const;
  return (
    <div className="page">
      <div className="eyebrow">RESEARCH / MEASURED OUTCOMES</div>
      <h1>Report track record</h1>
      <p className="subtitle">
        Frozen research views, measured against subsequent stock and NIFTY
        returns.
      </p>
      <div className="filters">
        <label>
          Report set{" "}
          <select value={mode} onChange={(e) => M(e.target.value)}>
            <option value="live">Live reports</option>
            <option value="replay">Historical replays</option>
          </select>
        </label>
        <label>
          Trading sessions{" "}
          <select value={horizon} onChange={(e) => H(Number(e.target.value))}>
            {[1, 3, 5, 10, 20].map((h) => (
              <option key={h}>{h}</option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      <section className="panel">
        <h2>Directional accuracy</h2>
        <p>{score(clean)}</p>
        <p>
          {selected.length} reports · {relevant.length} mature outcomes ·{" "}
          {selected.length - relevant.length} pending ·{" "}
          {relevant.length - clean.length} excluded for severe verification
          failures.
        </p>
        <p className="research-note">
          Fewer than 30 independent outcomes cannot establish reliability.
          Repeated reports on the same stock and overlapping windows are
          correlated. The interval describes raw observations and can overstate
          precision. A 50% coin-flip comparison is descriptive, not a
          significance test.
        </p>
        <p>
          Always-bullish benchmark:{" "}
          {clean.length
            ? pct(
                clean.filter((o) => Number(o.excess_return) > 0).length /
                  clean.length,
              )
            : "No outcomes yet"}
          . Neutral and mixed reports have no directional hit score.
        </p>
      </section>
      {groups.map((key) => (
        <section className="panel" key={key}>
          <h2>By {key.replaceAll("_", " ")}</h2>
          {[...new Set(selected.map((r) => r[key]))].sort().map((value) => (
            <p key={value}>
              <strong>{value}</strong> —{" "}
              {score(
                clean.filter((o) => byId.get(o.report_id)?.[key] === value),
              )}
            </p>
          ))}
          {!selected.length && <p>No reports in this set yet.</p>}
        </section>
      ))}
      <section className="panel research-scroll">
        <h2>Outcome ledger</h2>
        <table>
          <thead>
            <tr>
              {[
                "Report",
                "Stance",
                "Verification",
                "Entry / exit",
                "Stock",
                "NIFTY",
                "Excess",
                "Hit",
              ].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {selected.map((r) => {
              const o = relevant.find((v) => v.report_id === r.id);
              return (
                <tr key={r.id}>
                  <td>
                    <Link href={`/threads/${r.thread_id}`}>
                      {r.symbol} · {r.as_of_date}
                    </Link>
                  </td>
                  <td>{r.stance}</td>
                  <td>
                    {r.verification_summary.severe
                      ? "Excluded: severe failure"
                      : "Eligible"}
                  </td>
                  <td>
                    {o
                      ? `${o.entry_date} / ${o.exit_date}`
                      : "Pending complete sessions"}
                  </td>
                  <td>{o ? pct(Number(o.realized_return)) : "—"}</td>
                  <td>{o ? pct(Number(o.benchmark_return)) : "—"}</td>
                  <td>{o ? pct(Number(o.excess_return)) : "—"}</td>
                  <td>
                    {o?.directional_hit == null
                      ? "—"
                      : o.directional_hit
                        ? "Yes"
                        : "No"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      <p className="research-note">
        Entry is the first stored session opening after report creation (after
        the historical cutoff for replays). Exit is the close of the selected
        trading-session horizon. Stock and index dates must match; flagged data
        stays pending. Returns are gross price changes, without trading costs or
        dividends. Reports and saved outcomes are never rewritten by grading.
      </p>
    </div>
  );
}
