"use client";
import { useEffect, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { changeOperation } from "@/lib/ops";
import { useLogin, LoginRequired } from "./auth";

type Factor = {
  symbol: string;
  exchange: string;
  ex_date: string;
  factor: number;
  status: string;
  corporate_action_id: number;
  note: string;
};
type Action = {
  id: number;
  symbol: string;
  ratio_text: string;
  source_ref: string;
  ex_date: string;
  parse_status: string;
};
type Price = { ts: string; close: number; adjusted: boolean };
const session = (ts: string) =>
  new Date(ts).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

function Preview({ factor }: { factor: Factor }) {
  const [prices, P] = useState<Price[]>([]),
    [error, E] = useState("");
  useEffect(() => {
    let active = true;
    const c = getBrowserClient();
    if (!c) return;
    const date = new Date(factor.ex_date);
    const start = new Date(date.getTime() - 15 * 86400000).toISOString(),
      end = new Date(date.getTime() + 15 * 86400000).toISOString();
    void c
      .from("candles")
      .select("ts,close,adjusted")
      .eq("symbol", factor.symbol)
      .eq("exchange", "NSE")
      .eq("timeframe", "1d")
      .gte("ts", start)
      .lte("ts", end)
      .order("ts")
      .then(({ data, error }) => {
        if (active) {
          if (error) E("Chart unavailable");
          else P(data as Price[]);
        }
      });
    return () => {
      active = false;
    };
  }, [factor.symbol, factor.ex_date]);
  if (error) return <p>{error}</p>;
  if (prices.length < 2) return <p>Loading price comparison…</p>;
  const raw = prices.map((p) => Number(p.close)),
    adjusted = prices.map(
      (p) =>
        Number(p.close) *
        (session(p.ts) < factor.ex_date && !p.adjusted
          ? Number(factor.factor)
          : 1),
    );
  const min = Math.min(...raw, ...adjusted),
    max = Math.max(...raw, ...adjusted),
    span = max - min || 1;
  const path = (values: number[]) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${30 + (i * 640) / (values.length - 1)},${190 - ((v - min) / span) * 160}`,
      )
      .join(" ");
  return (
    <>
      <svg
        role="img"
        aria-label={`${factor.symbol} raw and proposed adjusted close prices`}
        viewBox="0 0 700 225"
        style={{ width: "100%", maxWidth: 800 }}
      >
        <path d={path(raw)} fill="none" stroke="#64748b" strokeWidth="2" />
        <path d={path(adjusted)} fill="none" stroke="#0d9488" strokeWidth="3" />
        <text x="30" y="215" fontSize="12">
          {session(prices[0].ts)}
        </text>
        <text x="570" y="215" fontSize="12">
          {session(prices.at(-1)!.ts)}
        </text>
        <text x="30" y="18" fontSize="12">
          ₹{max.toFixed(2)}
        </text>
      </svg>
      <p>
        Grey: stored close · Green: this factor’s preview. Prices before{" "}
        {factor.ex_date} × {factor.factor}; volume ÷ {factor.factor}.
        Already-adjusted source rows pass through unchanged.
      </p>
    </>
  );
}

export function AdjustmentReview() {
  const { ready, loggedIn } = useLogin();
  const [factors, F] = useState<Factor[]>([]),
    [actions, A] = useState<Action[]>([]),
    [checks, C] = useState<Record<string, string>>({}),
    [notes, N] = useState<Record<string, string>>({}),
    [error, E] = useState(""),
    [busy, B] = useState(false);
  async function load() {
    const c = getBrowserClient();
    if (!c) return;
    const [f, a, h] = await Promise.all([
      c
        .from("adjustment_factors")
        .select("*")
        .order("ex_date", { ascending: false }),
      c
        .from("corporate_actions")
        .select("id,symbol,ratio_text,source_ref,ex_date,parse_status")
        .in("action_type", ["split", "bonus"]),
      c
        .from("health_checks")
        .select("subject,status")
        .eq("check_key", "adjustment_crosscheck")
        .order("ts", { ascending: false })
        .limit(100),
    ]);
    if (f.error || a.error || h.error)
      throw new Error("Could not load adjustment review");
    F(f.data as Factor[]);
    A(a.data as Action[]);
    const latest: Record<string, string> = {};
    for (const row of h.data || [])
      if (!(row.subject in latest)) latest[row.subject] = row.status;
    C(latest);
  }
  useEffect(() => {
    if (loggedIn) void load().catch((e) => E(e.message));
  }, [loggedIn]);
  async function decide(f: Factor, status: string) {
    B(true);
    E("");
    try {
      await changeOperation("/api/adjustments", {
        symbol: f.symbol,
        ex_date: f.ex_date,
        status,
        note: notes[f.symbol + f.ex_date] || "",
      });
      await load();
    } catch (e) {
      E((e as Error).message);
    } finally {
      B(false);
    }
  }
  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;
  return (
    <div className="page">
      <div className="eyebrow">HUMAN REVIEW / PRICE HISTORY</div>
      <h1>Corporate-action review</h1>
      <p className="subtitle">
        Review the source, factor and price continuity before approving. Raw
        candles are preserved.
      </p>
      <p className="research-note">
        Defaults remain raw until review and recomputation finish. Approved
        factors change the adjusted view; existing reports stay frozen. Cash
        dividends are excluded.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {factors.map((f) => {
        const a = actions.find((a) => a.id === f.corporate_action_id),
          key = f.symbol + f.ex_date;
        return (
          <section
            className="panel news-section"
            key={key}
            style={{ marginBottom: 20 }}
          >
            <h2>
              {f.symbol} · {f.ex_date}
            </h2>
            <p>
              <strong>{f.status}</strong> · Price factor {f.factor}
            </p>
            <blockquote>
              {a?.ratio_text || "Source text unavailable"}
            </blockquote>
            {a?.source_ref && /^https:\/\//.test(a.source_ref) && (
              <a href={a.source_ref} target="_blank" rel="noopener noreferrer">
                Exchange source
              </a>
            )}
            <Preview factor={f} />
            <p>
              Independent price comparison:{" "}
              {checks[f.symbol + ":" + f.ex_date] === "ok"
                ? "Passed within 0.5% tolerance"
                : checks[f.symbol + ":" + f.ex_date]
                  ? "Needs investigation"
                  : "Pending"}
            </p>
            <p>{f.note}</p>
            <label className="search-label">
              Your review note
              <input
                value={notes[key] || ""}
                maxLength={1000}
                onChange={(e) => N({ ...notes, [key]: e.target.value })}
              />
            </label>
            <button
              disabled={
                busy ||
                (notes[key] || "").trim().length < 3 ||
                f.status === "approved"
              }
              onClick={() => void decide(f, "approved")}
            >
              Approve factor
            </button>{" "}
            <button
              disabled={
                busy ||
                (notes[key] || "").trim().length < 3 ||
                f.status === "rejected"
              }
              onClick={() => void decide(f, "rejected")}
            >
              Reject factor
            </button>
          </section>
        );
      })}
      <h2>Unparsed or ambiguous actions</h2>
      {actions
        .filter((a) => !factors.some((f) => f.corporate_action_id === a.id))
        .map((a) => (
          <p key={a.id}>
            {a.symbol} · {a.ex_date} · {a.ratio_text} — requires manual
            interpretation
          </p>
        ))}
      {!factors.length && <p>No factor proposals yet.</p>}
    </div>
  );
}
