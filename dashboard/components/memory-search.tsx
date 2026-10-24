"use client";
import { useState } from "react";
import Link from "next/link";
import { dateTime } from "@/lib/types";
import { pct } from "@/lib/research";
import { titleCase } from "@/lib/news";
import { NewsNote } from "./news-feed";
type Hit = {
  article_id: string;
  title: string;
  summary: string;
  source_key: string;
  published_at: string;
  similarity: number;
  symbols: { symbol: string }[];
  sentiment: { score: number; label: string }[];
};
export function MemorySearch() {
  const [q, Q] = useState(""),
    [symbol, S] = useState(""),
    [start, A] = useState(""),
    [end, Z] = useState(""),
    [rows, R] = useState<Hit[]>([]),
    [error, E] = useState(""),
    [busy, B] = useState(false),
    [searched, H] = useState(false);
  async function search(e: React.FormEvent) {
    e.preventDefault();
    B(true);
    E("");
    R([]);
    try {
      const params = new URLSearchParams({ q, symbol });
      if (start) params.set("start", `${start}T00:00:00+05:30`);
      if (end) {
        const next = new Date(`${end}T00:00:00+05:30`);
        next.setUTCDate(next.getUTCDate() + 1);
        params.set("end", next.toISOString());
      }
      const res = await fetch(`/api/memory?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      R(data);
      H(true);
    } catch (e) {
      E((e as Error).message);
    } finally {
      B(false);
    }
  }
  return (
    <div className="page">
      <div className="eyebrow">LOCAL MEMORY / MEANING SEARCH</div>
      <h1>Search past stories</h1>
      <p className="subtitle">
        Find related headlines by meaning, with a model running on this
        computer.
      </p>
      <NewsNote />
      <section className="panel news-section">
        <form onSubmit={search}>
          <label className="search-label">
            What are you researching?
            <input
              required
              maxLength={500}
              value={q}
              onChange={(e) => Q(e.target.value)}
              placeholder="What happened when the RBI raised rates?"
            />
          </label>
          <div className="filters">
            <label>
              Symbol
              <select value={symbol} onChange={(e) => S(e.target.value)}>
                <option value="">All symbols</option>
                {[
                  "RELIANCE",
                  "TCS",
                  "INFY",
                  "HDFCBANK",
                  "ICICIBANK",
                  "MARKET",
                ].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            <label>
              From (IST)
              <input
                type="date"
                value={start}
                onChange={(e) => A(e.target.value)}
              />
            </label>
            <label>
              To (IST)
              <input
                type="date"
                value={end}
                onChange={(e) => Z(e.target.value)}
              />
            </label>
            <button disabled={busy}>
              {busy ? "Searching local memory…" : "Search stories"}
            </button>
          </div>
        </form>
        <p className="attribution">
          Similarity is a measure of related wording, not a forecast or
          probability. The archive includes only embedded, linked stories.
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {rows.map((r) => (
          <article className="news-item" key={r.article_id}>
            <span className="news-meta">
              {titleCase(r.source_key)} · {dateTime(r.published_at)} IST ·
              Similarity {pct(r.similarity)}
            </span>
            <h3>
              <Link href={`/news/${r.article_id}`}>{r.title}</Link>
            </h3>
            <p>{r.summary}</p>
            <div className="news-chips">
              {r.symbols.map((s) => (
                <span className="badge" key={s.symbol}>
                  {s.symbol}
                </span>
              ))}
              {r.sentiment.map((s, i) => (
                <span className="badge" key={i}>
                  {s.label} · {Number(s.score).toFixed(2)}
                </span>
              ))}
            </div>
          </article>
        ))}
        {searched && !busy && !error && !rows.length && (
          <p className="empty">No embedded stories match these filters.</p>
        )}
      </section>
    </div>
  );
}
