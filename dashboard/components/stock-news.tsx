"use client";
import { Article, CorporateAction, score, titleCase } from "@/lib/news";
import { sessionDate } from "@/lib/types";
import { NewsRows } from "./news-feed";
export type ChartEvent = {
  date: string;
  text: string;
  kind: "news" | "action";
};
export function StockNews({
  rows,
  actions,
  symbol,
}: {
  rows: Article[];
  actions: CorporateAction[];
  symbol: string;
}) {
  const linked = rows
    .filter(
      (a) =>
        !a.is_duplicate &&
        a.article_symbols.some(
          (l) => l.symbol === (symbol === "NIFTY50" ? "MARKET" : symbol),
        ),
    )
    .sort((a, b) => b.published_at.localeCompare(a.published_at));
  const days = new Map<string, number[]>();
  for (const a of linked) {
    const s = score(a);
    if (s && !a.published_at_assumed) {
      const day = sessionDate(a.published_at);
      days.set(day, [...(days.get(day) || []), Number(s.score)]);
    }
  }
  return (
    <>
      <section className="panel news-section">
        <h2>Daily news sentiment</h2>
        <p className="attribution">
          Average article tone by publication date in IST · Canonical stories
          only · Hover for score and article count · Last 60 news days
        </p>
        <div
          className="sentiment-timeline"
          aria-label="Daily average sentiment and article counts"
        >
          {[...days]
            .sort(([a], [b]) => a.localeCompare(b))
            .slice(-60)
            .map(([day, values]) => {
              const mean = values.reduce((a, b) => a + b, 0) / values.length;
              return (
                <div
                  className="sentiment-day"
                  key={day}
                  title={`${day}: ${mean.toFixed(3)} · ${values.length} articles`}
                >
                  <div
                    className="sentiment-stick"
                    style={{
                      height: Math.abs(mean) * 65 + 2,
                      background: mean < 0 ? "#d66a6e" : "#229779",
                    }}
                  />
                  <span>{values.length}</span>
                  <small>{day.slice(5)}</small>
                </div>
              );
            })}
          {!days.size && <p>No scored stories available.</p>}
        </div>
      </section>
      <section className="panel news-section">
        <h2>Corporate actions</h2>
        <p className="attribution">
          Compare ex-dates with possible split or bonus flags on the chart.
          These records provide context; they do not automatically change prices
          or remove quality flags.
        </p>
        <div className="research-scroll">
          <table>
            <thead>
              <tr>
                <th>Ex-date</th>
                <th>Action</th>
                <th>Published terms</th>
                <th>Parsing</th>
              </tr>
            </thead>
            <tbody>
              {[...actions]
                .sort((a, b) =>
                  (b.ex_date || "").localeCompare(a.ex_date || ""),
                )
                .map((a) => (
                  <tr key={a.id}>
                    <td>{a.ex_date || "Unknown"}</td>
                    <td>{titleCase(a.action_type)}</td>
                    <td>
                      {a.ratio_text}
                      <small>
                        {a.source} · Record date{" "}
                        {a.record_date || "unavailable"}
                      </small>
                    </td>
                    <td>
                      <span
                        className={`badge ${a.parse_status === "needs_review" ? "warning" : "success"}`}
                      >
                        {titleCase(a.parse_status)}
                      </span>
                      {a.parsed && <small>{JSON.stringify(a.parsed)}</small>}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!actions.length && <p>No corporate actions stored.</p>}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Recent company news</h2>
        </div>
        <NewsRows rows={linked.slice(0, 15)} all={rows} />
        {!linked.length && <p className="empty">No linked news stored.</p>}
      </section>
    </>
  );
}
