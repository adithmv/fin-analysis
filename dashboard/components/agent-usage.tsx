"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { agentRows, Thread } from "@/lib/agents";
import { useLogin, LoginRequired } from "./auth";
import { dateTime } from "@/lib/types";
type Call = {
  id: string;
  thread_id: string;
  role: string;
  model: string;
  status: string;
  budget_day: string;
  reserved_at: string;
  tokens_in: number | null;
  tokens_out: number | null;
};
export function AgentUsage() {
  const { loggedIn, ready } = useLogin();
  const [rows, R] = useState<Call[]>([]),
    [limit, L] = useState(0),
    [error, E] = useState("");
  useEffect(() => {
    if (!loggedIn) return;
    let active = true;
    const load = () =>
      void Promise.all([
        agentRows<Call>("agent_call_reservations"),
        agentRows<Thread>("threads"),
      ])
        .then(([r, t]) => {
          if (active) {
            R(r);
            const latest = t.sort((a, b) =>
              b.created_at.localeCompare(a.created_at),
            )[0];
            L(
              Number(
                (
                  latest?.config.llm as {
                    limits?: { max_calls_per_day: number };
                  }
                )?.limits?.max_calls_per_day || 0,
              ),
            );
          }
        })
        .catch((e) => {
          if (active) E(e.message);
        });
    load();
    const timer = setInterval(load, 10000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [loggedIn]);
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  const day = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Los_Angeles",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const today = rows.filter((r) => r.budget_day === day);
  return (
    <div className="page">
      <div className="eyebrow">MODEL USAGE / APPLICATION LIMITS</div>
      <h1>Research call budget</h1>
      <p className="subtitle">
        Every reserved attempt counts, including failed calls and interrupted
        requests.
      </p>
      <div className="stats">
        <div>
          <label>CALLS TODAY / CAP</label>
          <strong>
            {today.length} / {limit}
          </strong>
        </div>
        <div>
          <label>INPUT TOKENS</label>
          <strong>
            {today.reduce((n, r) => n + (r.tokens_in || 0), 0).toLocaleString()}
          </strong>
        </div>
        <div>
          <label>OUTPUT TOKENS</label>
          <strong>
            {today
              .reduce((n, r) => n + (r.tokens_out || 0), 0)
              .toLocaleString()}
          </strong>
        </div>
      </div>
      <p className="research-note">
        Budget day {day}, midnight-to-midnight Pacific time. These are
        application caps; Google’s account quota may be lower. Free-tier only;
        billing is never upgraded automatically. Unknown tokens from failed
        calls are shown as unavailable.
      </p>
      {limit > 0 && today.length >= limit * 0.8 && (
        <p role="alert" className="error">
          At least 80% of the daily call budget has been used.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <section className="panel research-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Time (IST)",
                "Role",
                "Discussion",
                "Model",
                "Status",
                "Tokens in / out",
              ].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...today].reverse().map((r) => (
              <tr key={r.id}>
                <td>{dateTime(r.reserved_at)}</td>
                <td>{r.role.replaceAll("_", " ")}</td>
                <td>
                  {r.thread_id ? (
                    <Link href={`/threads/${r.thread_id}`}>
                      Open discussion →
                    </Link>
                  ) : (
                    "Probe"
                  )}
                </td>
                <td>{r.model}</td>
                <td>{r.status}</td>
                <td>
                  {r.status === "success" &&
                  r.tokens_in !== null &&
                  r.tokens_out !== null
                    ? `${r.tokens_in} / ${r.tokens_out}`
                    : "Unavailable"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
