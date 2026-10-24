"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Article, articles, score, titleCase, externalUrl } from "@/lib/news";
import { dateTime } from "@/lib/types";
import { pct } from "@/lib/research";
import { NewsNote, NewsRows } from "./news-feed";
type Similar = {
  article_id: string;
  title: string;
  published_at: string;
  similarity: number;
  outcomes: {
    symbol: string;
    entry_date: string;
    price_moves_before_costs: Record<string, number | null>;
  }[];
};
export function NewsDetail({ id }: { id: string }) {
  const [rows, R] = useState<Article[]>([]),
    [error, E] = useState(""),
    [loading, L] = useState(true),
    [similar, M] = useState<Similar[] | null>(null),
    [busy, B] = useState(false),
    [memoryError, F] = useState("");
  useEffect(() => {
    let active = true;
    void articles()
      .then((r) => {
        if (active) R(r);
      })
      .catch((e) => {
        if (active) E(String(e.message));
      })
      .finally(() => {
        if (active) L(false);
      });
    return () => {
      active = false;
    };
  }, [id]);
  const a = rows.find((r) => r.id === id);
  async function find() {
    B(true);
    F("");
    try {
      const res = await fetch(`/api/memory?mode=similar&id=${id}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      M(data.items);
    } catch (e) {
      F(String((e as Error).message));
    } finally {
      B(false);
    }
  }
  if (!a)
    return (
      <div className="page">
        <Link href="/news">← News archive</Link>
        <p role={error ? "alert" : "status"}>
          {error || (loading ? "Loading story…" : "Story not found.")}
        </p>
      </div>
    );
  const s = score(a);
  return (
    <div className="page">
      <Link className="back" href="/news">
        ← News archive
      </Link>
      <div className="eyebrow">
        {titleCase(a.source_key)} · {dateTime(a.published_at)} IST
      </div>
      <h1 className="article-title">{a.title}</h1>
      <p>
        <a
          className="small-link"
          href={externalUrl(a.url)}
          target="_blank"
          rel="noreferrer"
        >
          Read original source ↗
        </a>
        {a.published_at_assumed && " · Time approximate; excluded from studies"}
      </p>
      <NewsNote />
      <section className="panel news-section">
        <h2>Source snippet</h2>
        <p>{a.summary || "No summary supplied by this source."}</p>
        <h2>Company links</h2>
        {a.article_symbols.map((l) => (
          <p key={l.symbol}>
            <strong>{l.symbol}</strong> · {pct(l.confidence)} confidence ·{" "}
            {titleCase(l.match_type)} · “{l.matched_text}”
          </p>
        ))}
        {!a.article_symbols.length && <p>No watchlist company linked.</p>}
        <h2>Article sentiment</h2>
        {s ? (
          <>
            <p>
              {titleCase(s.label)} · Score {Number(s.score).toFixed(3)} · One
              score for the whole article
            </p>
            {(["positive", "neutral", "negative"] as const).map((k) => (
              <div key={k} className="probability">
                <label>{k}</label>
                <meter min={0} max={1} value={Number(s[`p_${k}`])} />
                <span>{pct(s[`p_${k}`])}</span>
              </div>
            ))}
            <small>
              {s.model_key} · {s.model_revision.slice(0, 8)}
            </small>
          </>
        ) : (
          <p>
            Unscored, pending processing, or skipped by the English-language
            check.
          </p>
        )}
        <h2>Classified events</h2>
        {a.news_events.map((e, i) => (
          <p key={i}>
            <strong>{titleCase(e.event_type)}</strong> · {e.symbol} · Importance{" "}
            {e.importance}/5 · Eligible open:{" "}
            {e.effective_trading_date ||
              "Pending available session / excluded timestamp"}
            <small>Matched rule: {e.matched_rule}</small>
          </p>
        ))}
        {!a.news_events.length && <p>No eligible event classified.</p>}
      </section>
      <section className="panel news-section">
        <h2>Same story across sources</h2>
        <NewsRows
          rows={rows.filter(
            (r) => r.id !== id && r.dedupe_group_id === a.dedupe_group_id,
          )}
          all={[]}
        />
      </section>
      <section className="panel news-section">
        <h2>Similar past events</h2>
        <p className="research-note">
          Anecdotal similarity, not statistical evidence. Only earlier published
          items are returned. Price moves are before costs; missing or excluded
          outcomes are blank.
        </p>
        <button onClick={() => void find()} disabled={busy}>
          {busy ? "Searching local memory…" : "Find similar past events"}
        </button>
        {memoryError && (
          <p role="alert" className="error">
            {memoryError}
          </p>
        )}
        {similar?.map((r) => (
          <article className="news-item" key={r.article_id}>
            <Link href={`/news/${r.article_id}`}>{r.title}</Link>
            <p>
              {dateTime(r.published_at)} IST · Similarity {pct(r.similarity)}
            </p>
            {r.outcomes.map((o) => (
              <p key={o.symbol}>
                {o.symbol} · Entry {o.entry_date} · 1 session:{" "}
                {pct(o.price_moves_before_costs["1"])} · 5:{" "}
                {pct(o.price_moves_before_costs["5"])} · 20:{" "}
                {pct(o.price_moves_before_costs["20"])}
              </p>
            ))}
          </article>
        ))}
        {similar?.length === 0 && <p>No earlier embedded stories found.</p>}
      </section>
    </div>
  );
}
