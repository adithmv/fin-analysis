"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
import {
  Thread,
  Message,
  Report,
  Pack,
  agentRows,
  requestAnalysis,
} from "@/lib/agents";
import { dateTime, sessionDate } from "@/lib/types";
import { titleCase } from "@/lib/news";
import { useLogin, LoginRequired } from "./auth";

export function ReportCard({ report: r }: { report: Report }) {
  return (
    <section className="panel news-section report-card">
      <div className="heading">
        <h2>Research report</h2>
        <div className="news-chips">
          <span className="badge">{r.stance}</span>
          <span className="badge">{r.confidence} confidence</span>
          <span
            className={`badge ${["none", "weak"].includes(r.evidence_strength) ? "warning" : "success"}`}
          >
            {r.evidence_strength} evidence
          </span>
        </div>
      </div>
      {["none", "weak"].includes(r.evidence_strength) && (
        <p className="research-note">
          The signals cited here have no demonstrated edge meeting the required
          stored-statistics checks.
        </p>
      )}
      <p className="message-text">{r.summary_md}</p>
      <p className="attribution">
        The stance, confidence and evidence-strength badges above are set by
        code. Narrative interpretation is not independently verified; inspect
        the structured claims below.
      </p>
      {(["key_points", "risks", "invalidation"] as const).map((key) => (
        <div key={key}>
          <h3>{titleCase(key)}</h3>
          {r[key].length ? (
            <ul>
              {r[key].map((p, i) => (
                <li key={i}>{p.text}</li>
              ))}
            </ul>
          ) : (
            <p>No independently supported item was retained.</p>
          )}
        </div>
      ))}
      <h3>Evidence strength, computed by code</h3>
      <ul>
        {r.evidence_strength_why.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
      <details>
        <summary>What changed & data quality</summary>
        <pre>{JSON.stringify(r.what_changed, null, 2)}</pre>
        {r.data_quality_notes.map((n, i) => (
          <p key={i}>{n}</p>
        ))}
      </details>
      <p className="attribution">
        Horizon: {r.horizon_days} sessions · {r.disclaimer}
      </p>
    </section>
  );
}

export function ThreadDetail({ id }: { id: string }) {
  const { loggedIn, ready } = useLogin();
  const [thread, T] = useState<Thread | null>(null),
    [messages, M] = useState<Message[]>([]),
    [report, R] = useState<Report | null>(null),
    [pack, P] = useState<Pack | null>(null),
    [error, E] = useState(""),
    [question, Q] = useState(""),
    [busy, B] = useState(false),
    [notice, N] = useState(""),
    [selected, S] = useState<string | null>(null),
    [calls, C] = useState(0),
    [eventRuns, ER] = useState<Record<number, string>>({}),
    [limit, L] = useState(0),
    [requests, J] = useState<
      { id: number; status: string; error: string | null }[]
    >([]);
  useEffect(() => {
    if (selected)
      document
        .querySelector(".evidence-inspector")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [selected]);
  useEffect(() => {
    if (!loggedIn) return;
    let active = true;
    const c = getBrowserClient()!;
    async function load() {
      const [ts, ms, rs, ps, us, qs] = await Promise.all([
        agentRows<Thread>("threads", ["id", id]),
        agentRows<Message>("messages", ["thread_id", id], "seq"),
        agentRows<Report>("analysis_reports", ["thread_id", id]),
        agentRows<{ pack: Pack }>(
          "evidence_packs",
          ["thread_id", id],
          "thread_id",
        ),
        agentRows<{ budget_day: string; event_id: number; run_id: string }>(
          "agent_call_reservations",
        ),
        agentRows<{ id: number; status: string; error: string | null }>(
          "analysis_requests",
          ["thread_id", id],
        ),
      ]);
      if (active) {
        T(ts[0] || null);
        M(ms);
        R(rs[0] || null);
        P(ps[0]?.pack || null);
        J(qs);
        ER(
          Object.fromEntries(
            us.filter((u) => u.event_id).map((u) => [u.event_id, u.run_id]),
          ),
        );
        const budgetDay = new Intl.DateTimeFormat("en-CA", {
          timeZone: "America/Los_Angeles",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).format(new Date());
        C(us.filter((u) => u.budget_day === budgetDay).length);
        L(
          Number(
            (ts[0]?.config.llm as { limits?: { max_calls_per_day: number } })
              ?.limits?.max_calls_per_day || 0,
          ),
        );
        E("");
      }
    }
    const refresh = () =>
      void load().catch((e) => {
        if (active) E(e.message);
      });
    refresh();
    const timer = setInterval(refresh, 5000);
    const channel = c
      .channel(`discussion-${id}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "messages",
          filter: `thread_id=eq.${id}`,
        },
        refresh,
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "threads",
          filter: `id=eq.${id}`,
        },
        refresh,
      )
      .subscribe();
    return () => {
      active = false;
      clearInterval(timer);
      void c.removeChannel(channel);
    };
  }, [id, loggedIn]);
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  async function ask(e: React.FormEvent) {
    e.preventDefault();
    B(true);
    try {
      await requestAnalysis({
        kind: "question",
        thread_id: id,
        question_text: question.trim(),
      });
      Q("");
      N(
        "Question queued. The local worker will answer using this discussion’s frozen evidence.",
      );
    } catch (e) {
      E((e as Error).message);
    } finally {
      B(false);
    }
  }
  const evidence = pack?.items.find((i) => i.evidence_id === selected);
  return (
    <div className="page">
      <Link className="back" href="/threads">
        ← Discussions
      </Link>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {thread ? (
        <>
          <div className="eyebrow">
            {thread.thread_date} · {thread.kind} ·{" "}
            {Boolean(thread.config.replay) ? "REPLAY" : "LIVE RESEARCH"}
          </div>
          <h1>{thread.symbol}: the evidence and the debate</h1>
          <p className="subtitle">
            {titleCase(thread.status)} · Data cutoff{" "}
            {dateTime(thread.data_cutoff_ts)} IST
          </p>
          {thread.failure_reason && (
            <p className="error">{thread.failure_reason}</p>
          )}
          {report && <ReportCard report={report} />}
          <section aria-label="Research discussion" className="discussion">
            {messages.map((m) => (
              <article
                key={m.id}
                className={`panel message role-${m.author_role}`}
              >
                <div className="message-heading">
                  <strong>{titleCase(m.author_role)}</strong>
                  <span>
                    {m.round ? `Round ${m.round} · ` : ""}
                    {dateTime(m.created_at)} IST
                  </span>
                  <span
                    className={`badge ${m.verification_status === "verified" ? "success" : m.verification_status === "unverified" ? "failed" : "warning"}`}
                  >
                    {m.author_type === "agent" ? "Claims: " : ""}
                    {titleCase(m.verification_status)}
                  </span>
                </div>
                <div className="news-chips">
                  {m.stance && <span className="badge">{m.stance}</span>}
                  {m.confidence && (
                    <span className="badge">{m.confidence} confidence</span>
                  )}
                </div>
                <p
                  className={`message-text ${["partial", "unverified"].includes(m.verification_status) ? "unverified-prose" : ""}`}
                >
                  {m.content_md}
                </p>
                {m.author_type === "agent" && (
                  <small>
                    Verification labels apply to structured claims. Narrative
                    interpretation is not checked. Inspect the claim-by-claim
                    evidence below.
                  </small>
                )}
                <div className="claim-list">
                  {m.claims.map((c) => {
                    const v = m.verification_notes.find(
                      (n) => n.claim_id === c.id,
                    );
                    return (
                      <div
                        key={c.id}
                        className={`claim ${v?.status === "unverified" ? "rejected-claim" : ""}`}
                      >
                        <span className="badge">
                          {v?.status || "unverified"}
                        </span>
                        <span>{c.text}</span>
                        {c.evidence_id && (
                          <button
                            className="evidence-chip"
                            onClick={() => S(c.evidence_id)}
                          >
                            {c.evidence_id} · inspect evidence
                          </button>
                        )}
                        {v?.reasons?.map((reason, i) => (
                          <small key={i}>{reason}</small>
                        ))}
                      </div>
                    );
                  })}
                </div>
                {m.verification_notes
                  .filter((n) => n.reason)
                  .map((n, i) => (
                    <p className="attribution" key={i}>
                      {n.reason}
                      {n.value != null ? `: ${n.value}` : ""}
                    </p>
                  ))}
                <details>
                  <summary>How this was produced</summary>
                  <p>
                    {m.llm_model || "Code / user"} · Prompt{" "}
                    {thread.prompt_version} · Tokens {m.tokens_in || 0} in /{" "}
                    {m.tokens_out || 0} out
                  </p>
                  <p>
                    Recorded event IDs:{" "}
                    {m.event_ids.join(", ") || "None (no model call)"}
                  </p>
                  <Link
                    href={`/logbook/run/${m.event_ids.map((id) => eventRuns[id]).find(Boolean) || thread.run_id}`}
                  >
                    Open run logbook →
                  </Link>
                </details>
              </article>
            ))}
          </section>
          {evidence && (
            <section
              className="panel news-section evidence-inspector"
              role="region"
              aria-label="Selected evidence"
            >
              <div className="heading">
                <h2>Evidence {selected}</h2>
                <button onClick={() => S(null)}>Close evidence</button>
              </div>
              <p>
                Frozen source row used by the verifier. Later database revisions
                do not rewrite this snapshot.
              </p>
              <pre>{JSON.stringify(evidence, null, 2)}</pre>
              {typeof evidence.ref.symbol === "string" && (
                <Link
                  className="small-link"
                  href={`/stocks/${evidence.ref.symbol}${typeof evidence.ref.ts === "string" ? `?date=${sessionDate(evidence.ref.ts)}` : ""}`}
                >
                  Open stock chart at this date →
                </Link>
              )}
              {evidence.ref.type === "article" && (
                <Link className="small-link" href={`/news/${evidence.ref.id}`}>
                  Open source article →
                </Link>
              )}
            </section>
          )}
          <section className="panel news-section">
            <h2>Ask about the evidence</h2>
            <p className="attribution">
              Public market research only. Do not include personal holdings,
              account details or credentials. The question and public evidence
              are sent to the configured Gemini provider.
            </p>
            <p>
              Remaining application call budget: {Math.max(0, limit - calls)} /{" "}
              {limit} · resets at midnight Pacific time
            </p>
            <form onSubmit={ask}>
              <label className="search-label">
                Your research question
                <textarea
                  required
                  maxLength={2000}
                  rows={4}
                  value={question}
                  onChange={(e) => Q(e.target.value)}
                  placeholder="Which evidence contradicts the bullish case?"
                />
              </label>
              <button disabled={busy || !pack || calls >= limit}>
                {busy ? "Queuing…" : "Ask the research assistant"}
              </button>
            </form>
            {notice && <p role="status">{notice}</p>}
            {requests.slice(-3).map((r) => (
              <p className="attribution" key={r.id}>
                Request {r.id}: {r.status}
                {r.error ? ` · ${r.error}` : ""}
              </p>
            ))}
          </section>
          <details className="research-note">
            <summary>View the frozen evidence pack</summary>
            <pre>{JSON.stringify(pack, null, 2)}</pre>
          </details>
        </>
      ) : (
        <p role="status">Loading discussion, or no access to this thread…</p>
      )}
    </div>
  );
}
