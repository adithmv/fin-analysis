"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
import { changeOperation } from "@/lib/ops";
import { useLogin, LoginRequired } from "./auth";

type Row = {
  id: number;
  module: string;
  kind: string;
  status: string;
  attempts: number;
  pipeline_run: string;
  scheduled_for: string;
  last_error: string;
  run_id: string;
  ts: string;
  severity: string;
  rule_key: string;
  subject: string;
  message: string;
  url: string;
  title: string;
  text: string;
  trust_level: string;
  domain: string;
  extraction_method: string;
};

export function Operations({
  view,
}: {
  view: "jobs" | "alerts" | "documents";
}) {
  const { ready, loggedIn } = useLogin();
  const [rows, setRows] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [filter, setFilter] = useState(""),
    [busy, setBusy] = useState(false),
    [heartbeat, setHeartbeat] = useState("");
  async function load() {
    const c = getBrowserClient();
    if (!c) return;
    const { data, error } = await c
      .from(view)
      .select("*")
      .order(view === "documents" ? "fetched_at" : "id", { ascending: false })
      .limit(200);
    if (error) throw new Error(error.message);
    setRows(data as Row[]);
    if (view === "jobs") {
      const h = await c
        .from("health_checks")
        .select("ts")
        .eq("check_key", "scheduler_heartbeat")
        .order("ts", { ascending: false })
        .limit(1);
      setHeartbeat(h.data?.[0]?.ts || "");
    }
  }
  useEffect(() => {
    if (!loggedIn) return;
    const refresh = () => void load().catch((e) => setError(e.message));
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => clearInterval(timer);
  }, [loggedIn, view]); // eslint-disable-line react-hooks/exhaustive-deps
  async function change(id: number, action: string) {
    setBusy(true);
    setError("");
    try {
      await changeOperation("/api/ops", { id, action });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  return (
    <div className="page">
      <div className="eyebrow">OPERATIONS / PHASE 5</div>
      <h1>
        {view === "jobs"
          ? "Pipeline operations"
          : view === "alerts"
            ? "Alerts"
            : "Collected documents"}
      </h1>
      <p className="subtitle">
        {view === "jobs"
          ? "Recent jobs, retries and recovery. Scheduling is being commissioned."
          : view === "alerts"
            ? "Actionable incidents stay here even when Telegram is unavailable."
            : "External text is untrusted. Follow the original source to verify it."}
      </p>
      <p>
        <Link href="/ops">Jobs</Link> · <Link href="/alerts">Alerts</Link> ·{" "}
        <Link href="/documents">Documents</Link> ·{" "}
        <Link href="/corporate-actions">Adjustment review</Link>
      </p>
      {view === "jobs" && (
        <p className="research-note">
          Scheduler heartbeat:{" "}
          {heartbeat
            ? new Date(heartbeat).toLocaleString("en-IN", {
                timeZone: "Asia/Kolkata",
              })
            : "Not running yet"}
          .{" "}
          {heartbeat && Date.now() - new Date(heartbeat).getTime() > 900000
            ? "Heartbeat is stale."
            : ""}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <label className="search-label">
        Filter by status, source or module{" "}
        <input value={filter} onChange={(e) => setFilter(e.target.value)} />
      </label>
      <p>{rows.length} recent records loaded</p>
      {!rows.length && (
        <section className="panel news-section">
          {view === "documents"
            ? "No browser documents collected yet."
            : "No records yet."}
        </section>
      )}
      {rows
        .filter((r) =>
          [r.status, r.module, r.subject, r.domain, r.severity, r.pipeline_run]
            .join(" ")
            .toLowerCase()
            .includes(filter.toLowerCase()),
        )
        .map((r) => (
          <section
            className="panel news-section"
            key={r.id}
            style={{ marginBottom: 12 }}
          >
            {view === "jobs" ? (
              <>
                <h2>
                  #{r.id} · {r.module} / {r.kind}
                </h2>
                <p>
                  <strong>{r.status}</strong> · {r.attempts} attempts ·{" "}
                  {r.pipeline_run}
                </p>
                <p>
                  Due{" "}
                  {new Date(r.scheduled_for).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                  })}{" "}
                  IST
                </p>
                {r.last_error && <p>{r.last_error}</p>}
                <p>
                  <Link
                    href={r.run_id ? `/logbook/run/${r.run_id}` : "/logbook"}
                  >
                    Inspect logbook
                  </Link>
                </p>
                {["dead", "failed", "cancelled", "skipped"].includes(
                  r.status,
                ) && (
                  <button
                    disabled={busy}
                    onClick={() => void change(r.id, "retry")}
                  >
                    Retry job
                  </button>
                )}
                {["queued", "running"].includes(r.status) && (
                  <button
                    disabled={busy}
                    onClick={() => void change(r.id, "cancel")}
                  >
                    Cancel job
                  </button>
                )}
              </>
            ) : view === "alerts" ? (
              <>
                <h2>
                  {r.severity} · {r.rule_key}
                </h2>
                <p>
                  {r.subject} · {r.status}
                </p>
                <p>{r.message}</p>
                {r.status === "open" && (
                  <button
                    disabled={busy}
                    onClick={() => void change(r.id, "acknowledge")}
                  >
                    Acknowledge
                  </button>
                )}{" "}
                {r.status !== "resolved" && (
                  <button
                    disabled={busy}
                    onClick={() => void change(r.id, "resolve")}
                  >
                    Mark resolved
                  </button>
                )}
                <p className="muted">
                  If the check still fails, the next check opens a new incident.
                </p>
              </>
            ) : (
              <>
                <h2>{r.title || r.domain}</h2>
                <p>
                  {r.status} · {r.trust_level} · {r.extraction_method}
                </p>
                {/^https:\/\//.test(r.url) && (
                  <a href={r.url} target="_blank" rel="noopener noreferrer">
                    Original source
                  </a>
                )}
                <details>
                  <summary>Read untrusted extracted text</summary>
                  <pre
                    style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                  >
                    {r.text}
                  </pre>
                </details>
              </>
            )}
          </section>
        ))}
    </div>
  );
}

export function CriticalAlerts() {
  const { loggedIn } = useLogin();
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!loggedIn) return;
    const refresh = async () => {
      const c = getBrowserClient();
      if (!c) return;
      const { count, error } = await c
        .from("alerts")
        .select("id", { count: "exact", head: true })
        .eq("severity", "critical")
        .neq("status", "resolved");
      if (!error) setCount(count || 0);
    };
    void refresh();
    const t = setInterval(() => void refresh(), 30000);
    return () => clearInterval(t);
  }, [loggedIn]);
  return loggedIn && count > 0 ? (
    <div
      role="status"
      style={{ background: "#fee2e2", color: "#991b1b", padding: "12px 24px" }}
    >
      <Link href="/alerts">
        {count} critical operational {count === 1 ? "alert" : "alerts"} —
        inspect first steps
      </Link>
    </div>
  ) : null;
}
