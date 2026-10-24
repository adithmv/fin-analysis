"use client";
import { useEffect, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { dateTime } from "@/lib/types";
import { pct } from "@/lib/research";
type Source = {
  source_key: string;
  name: string;
  enabled: boolean;
  last_success_at: string | null;
  consecutive_failures: number;
  items_24h: number;
  items_7d: number;
  duplicate_rate: number | null;
  link_coverage: number | null;
  assumed_time_rate: number | null;
  newest_publication: string | null;
  notes: string | null;
};
export function SourceHealth() {
  const [rows, R] = useState<Source[]>([]),
    [error, E] = useState(""),
    [loading, L] = useState(true);
  useEffect(() => {
    let active = true;
    async function load() {
      const c = getBrowserClient();
      if (!c) throw new Error("Database connection unavailable");
      const { data, error } = await c
        .from("news_source_health")
        .select("*")
        .order("source_key");
      if (error) throw error;
      if (active) {
        R(data as Source[]);
        E("");
      }
    }
    const refresh = () =>
      void load()
        .catch((e) => {
          if (active) E(String(e.message));
        })
        .finally(() => {
          if (active) L(false);
        });
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  return (
    <div className="page">
      <div className="eyebrow">COLLECTION / HEALTH</div>
      <h1>News sources</h1>
      <p className="subtitle">
        Check which sources are fresh, quiet, or need attention.
      </p>
      <p className="research-note">
        Refreshes every 15 seconds. Item counts reflect newly stored articles,
        including historical backfills. Quiet sources are not necessarily
        broken. A source disables after five failed polls and needs a manual
        review.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {loading && <p role="status">Loading sources…</p>}
      <section className="panel research-scroll">
        <table>
          <thead>
            <tr>
              {[
                "Source",
                "Health",
                "Last success (IST)",
                "New items 24h / 7d",
                "Failures",
                "Duplicates",
                "Stock link coverage",
                "Assumed times",
              ].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const state = !s.enabled
                ? "Disabled"
                : s.consecutive_failures
                  ? "Failing"
                  : s.newest_publication &&
                      Date.now() - Date.parse(s.newest_publication) > 7 * 864e5
                    ? "Stale"
                    : s.items_24h === 0
                      ? "Quiet"
                      : "Healthy";
              return (
                <tr key={s.source_key}>
                  <td>
                    <strong>{s.name}</strong>
                    {s.notes && <small>{s.notes}</small>}
                  </td>
                  <td>
                    <span
                      className={`badge ${["Disabled", "Failing"].includes(state) ? "failed" : state === "Healthy" ? "success" : "warning"}`}
                    >
                      {state}
                    </span>
                  </td>
                  <td>
                    {s.last_success_at ? dateTime(s.last_success_at) : "Never"}
                  </td>
                  <td>
                    {s.items_24h} / {s.items_7d}
                  </td>
                  <td>{s.consecutive_failures}</td>
                  <td>{pct(s.duplicate_rate)}</td>
                  <td>{pct(s.link_coverage)}</td>
                  <td>{pct(s.assumed_time_rate)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
