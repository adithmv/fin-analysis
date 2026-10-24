"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Article,
  articles,
  score,
  bucket,
  titleCase,
  externalUrl,
} from "@/lib/news";
import { dateTime, sessionDate } from "@/lib/types";

export function NewsNote() {
  return (
    <p className="research-note">
      Titles and short snippets only · English sentiment measures tone, not
      price impact. Classification is approximate and human accuracy review is
      pending. Feed history starts with collection; exchange history may go
      further back.
    </p>
  );
}
export function NewsRows({
  rows,
  all = rows,
}: {
  rows: Article[];
  all?: Article[];
}) {
  return (
    <div className="news-list">
      {rows.map((a) => {
        const s = score(a);
        const copies = all.filter(
          (x) => x.id !== a.id && x.dedupe_group_id === a.dedupe_group_id,
        ).length;
        return (
          <article key={a.id} className="news-item">
            <div className="news-meta">
              {dateTime(a.published_at)} IST · {titleCase(a.source_key)}
              {a.published_at_assumed && (
                <span className="badge warning">Time approximate</span>
              )}
            </div>
            <h3>
              <a href={externalUrl(a.url)} target="_blank" rel="noreferrer">
                {a.title} ↗
              </a>
            </h3>
            <div className="news-chips">
              {a.article_symbols.map((l) => (
                <Link
                  className="badge"
                  key={l.symbol}
                  href={
                    l.symbol === "MARKET"
                      ? "/stocks/NIFTY50"
                      : `/stocks/${l.symbol}`
                  }
                >
                  {l.symbol}
                </Link>
              ))}
              {s && (
                <span
                  className={`badge ${s.label === "negative" ? "failed" : s.label === "positive" ? "success" : "skipped"}`}
                >
                  {titleCase(bucket(Number(s.score)))} ·{" "}
                  {Number(s.score).toFixed(2)}
                </span>
              )}
              {[...new Set(a.news_events.map((e) => e.event_type))].map((t) => (
                <span className="badge" key={t}>
                  {titleCase(t)}
                </span>
              ))}
              {copies > 0 && (
                <span className="badge">+{copies} same story</span>
              )}
              <Link href={`/news/${a.id}`} className="small-link">
                Details & past events →
              </Link>
            </div>
          </article>
        );
      })}
    </div>
  );
}

export function NewsFeed() {
  const [rows, setRows] = useState<Article[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [symbol, S] = useState(""),
    [source, F] = useState(""),
    [event, E] = useState(""),
    [sentiment, B] = useState(""),
    [start, A] = useState(""),
    [end, Z] = useState(""),
    [importance, I] = useState(""),
    [limit, L] = useState(40);
  useEffect(() => {
    let active = true;
    const refresh = () =>
      void articles()
        .then((r) => {
          if (active) {
            setRows(r);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(String(e.message));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  const filtered = rows
    .filter(
      (a) =>
        !a.is_duplicate &&
        (!symbol || a.article_symbols.some((l) => l.symbol === symbol)) &&
        (!source || a.source_key === source) &&
        (!event || a.news_events.some((e) => e.event_type === event)) &&
        (!sentiment ||
          (score(a) && bucket(Number(score(a).score)) === sentiment)) &&
        (!start || sessionDate(a.published_at) >= start) &&
        (!end || sessionDate(a.published_at) <= end) &&
        (!importance ||
          a.news_events.some((e) => e.importance >= Number(importance))),
    )
    .sort((a, b) => b.published_at.localeCompare(a.published_at));
  return (
    <div className="page">
      <div className="eyebrow">NEWS / EVENTS / MEMORY</div>
      <h1>News archive</h1>
      <p className="subtitle">
        Follow the story, its source, and the evidence that comes after.
      </p>
      <NewsNote />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <section className="panel">
        <div className="filters">
          {[
            {
              label: "Symbol",
              value: symbol,
              set: S,
              values: rows.flatMap((a) =>
                a.article_symbols.map((l) => l.symbol),
              ),
            },
            {
              label: "Source",
              value: source,
              set: F,
              values: rows.map((a) => a.source_key),
            },
            {
              label: "Event type",
              value: event,
              set: E,
              values: rows.flatMap((a) =>
                a.news_events.map((e) => e.event_type),
              ),
            },
            {
              label: "Sentiment",
              value: sentiment,
              set: B,
              values: [
                "very_negative",
                "negative",
                "neutral",
                "positive",
                "very_positive",
              ],
            },
          ].map((f) => (
            <label key={f.label}>
              {f.label}
              <select
                value={f.value}
                onChange={(e) => {
                  f.set(e.target.value);
                  L(40);
                }}
              >
                <option value="">All</option>
                {[...new Set(f.values)].sort().map((x) => (
                  <option key={x} value={x}>
                    {titleCase(x)}
                  </option>
                ))}
              </select>
            </label>
          ))}
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
          <label>
            Importance
            <select value={importance} onChange={(e) => I(e.target.value)}>
              <option value="">All</option>
              {[2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} or more
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="attribution">
          {loading
            ? "Loading news…"
            : `${filtered.length} canonical stories · duplicates grouped · refreshes every 30 seconds`}
        </p>
        <NewsRows rows={filtered.slice(0, limit)} all={rows} />
        {!loading && !filtered.length && (
          <p className="empty">No stories match these filters.</p>
        )}
        {filtered.length > limit && (
          <button onClick={() => L(limit + 40)}>Show more stories</button>
        )}
      </section>
    </div>
  );
}
