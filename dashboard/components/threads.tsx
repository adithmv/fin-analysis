"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Thread, Report, agentRows, requestAnalysis } from "@/lib/agents";
import { useLogin, LoginRequired } from "./auth";
import { titleCase } from "@/lib/news";
export function Threads() {
  const { loggedIn, ready } = useLogin();
  const [rows, R] = useState<Thread[]>([]),
    [calls, C] = useState<{ thread_id: string }[]>([]),
    [reports, F] = useState<Report[]>([]),
    [error, E] = useState(""),
    [symbol, S] = useState(""),
    [status, T] = useState(""),
    [stance, V] = useState(""),
    [strength, H] = useState(""),
    [day, D] = useState(""),
    [runSymbol, U] = useState("TCS"),
    [notice, N] = useState(""),
    [busy, B] = useState(false);
  useEffect(() => {
    if (!loggedIn) return;
    let active = true;
    const load = () =>
      void Promise.all([
        agentRows<Thread>("threads"),
        agentRows<Report>("analysis_reports"),
        agentRows<{ thread_id: string }>("agent_call_reservations"),
      ])
        .then(([t, r, calls]) => {
          if (active) {
            R(t);
            F(r);
            C(calls);
            E("");
          }
        })
        .catch((e) => {
          if (active) E(e.message);
        });
    load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [loggedIn]);
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  const visible = rows
    .filter((t) => {
      const r = reports.find((r) => r.thread_id === t.id);
      return (
        (!symbol || t.symbol === symbol) &&
        (!status || t.status === status) &&
        (!stance || r?.stance === stance) &&
        (!strength || r?.evidence_strength === strength) &&
        (!day || t.thread_date === day)
      );
    })
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  async function submit() {
    B(true);
    try {
      await requestAnalysis({ kind: "analysis", symbol: runSymbol });
      N("Request queued. The local agent worker will pick it up.");
    } catch (e) {
      E((e as Error).message);
    } finally {
      B(false);
    }
  }
  return (
    <div className="page">
      <div className="eyebrow">EVIDENCE / COUNTER-ARGUMENT / REVIEW</div>
      <h1>Research discussions</h1>
      <p className="subtitle">
        Follow each role’s case and inspect the facts behind it.
      </p>
      <p className="research-note">
        The verifier checks stored facts and references, not the quality of
        reasoning. News accuracy review is pending. Confidence is capped when
        measured evidence is weak.
      </p>
      <section className="panel">
        <div className="filters">
          <label>
            Analyze stock
            <select value={runSymbol} onChange={(e) => U(e.target.value)}>
              {["TCS", "RELIANCE", "INFY", "HDFCBANK", "ICICIBANK"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <button disabled={busy} onClick={() => void submit()}>
            Run analysis now
          </button>
          <Link href="/usage">View model budget →</Link>
        </div>
        {notice && (
          <p role="status" className="attribution">
            {notice}
          </p>
        )}
        <div className="filters">
          {[
            {
              name: "Symbol",
              value: symbol,
              set: S,
              values: [...new Set(rows.map((t) => t.symbol))],
            },
            {
              name: "Status",
              value: status,
              set: T,
              values: [
                "queued",
                "running",
                "completed",
                "failed",
                "budget_exhausted",
                "skipped",
              ],
            },
            {
              name: "Stance",
              value: stance,
              set: V,
              values: ["bullish", "bearish", "neutral", "mixed"],
            },
            {
              name: "Evidence strength",
              value: strength,
              set: H,
              values: ["none", "weak", "moderate", "strong"],
            },
          ].map((f) => (
            <label key={f.name}>
              {f.name}
              <select value={f.value} onChange={(e) => f.set(e.target.value)}>
                <option value="">All</option>
                {f.values.map((v) => (
                  <option key={v} value={v}>
                    {titleCase(v)}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <label>
            Research date
            <input
              type="date"
              value={day}
              onChange={(e) => D(e.target.value)}
            />
          </label>
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="research-scroll">
          <table>
            <thead>
              <tr>
                {[
                  "Discussion",
                  "Status",
                  "Stance",
                  "Confidence",
                  "Evidence strength",
                  "Verification",
                  "Model calls",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((t) => {
                const r = reports.find((r) => r.thread_id === t.id);
                return (
                  <tr
                    key={t.id}
                    className={t.status === "skipped" ? "insufficient" : ""}
                  >
                    <td>
                      <Link className="stock-symbol" href={`/threads/${t.id}`}>
                        {t.symbol} →
                      </Link>
                      <small>
                        {t.thread_date} · {t.kind}
                        {Boolean(t.config.replay) && " · REPLAY"}
                      </small>
                    </td>
                    <td>
                      <span
                        className={`badge ${t.status === "completed" ? "success" : t.status === "failed" ? "failed" : "warning"}`}
                      >
                        {titleCase(t.status)}
                      </span>
                      {t.failure_reason && <small>{t.failure_reason}</small>}
                    </td>
                    <td>{r?.stance || "Pending"}</td>
                    <td>{r?.confidence || "—"}</td>
                    <td>{r?.evidence_strength || "—"}</td>
                    <td>
                      {r
                        ? `${r.verification_summary.verified || 0} verified / ${r.verification_summary.partial || 0} partial messages`
                        : "—"}
                    </td>
                    <td>{calls.filter((c) => c.thread_id === t.id).length}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!visible.length && (
          <p className="empty">
            No discussions match these filters. Start an analysis when the local
            worker is ready.
          </p>
        )}
      </section>
    </div>
  );
}
