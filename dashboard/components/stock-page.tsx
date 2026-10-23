"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ResearchChart } from "./research-chart";
import { getBrowserClient } from "@/lib/supabase";
import { type Candle, money, sessionDate } from "@/lib/types";
import { EventFeed } from "./event-feed";

export function StockPage({ symbol }: { symbol: string }) {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true,
      sequence = 0;
    const client = getBrowserClient();
    if (!client) {
      setError("Configure dashboard/.env.local to connect Supabase.");
      setLoading(false);
      return;
    }
    async function load() {
      const version = ++sequence;
      const all: Candle[] = [];
      for (let offset = 0; ; offset += 500) {
        const { data, error } = await client!
          .from("candles")
          .select("*")
          .eq("symbol", symbol)
          .eq("exchange", "NSE")
          .eq("timeframe", "1d")
          .order("ts")
          .range(offset, offset + 499);
        if (error) throw new Error(error.message);
        all.push(...(data as Candle[]));
        if (data.length < 500) break;
      }
      if (active && version === sequence) {
        setCandles(all);
        setError("");
        setLoading(false);
      }
    }
    const refresh = () =>
      void load().catch((e) => {
        if (active) {
          setError(String(e));
          setLoading(false);
        }
      });
    refresh();
    const timer = setInterval(refresh, 15000);
    const channel = client
      .channel(`stock-${symbol}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "candles",
          filter: `symbol=eq.${symbol}`,
        },
        refresh,
      )
      .subscribe();
    return () => {
      active = false;
      sequence++;
      clearInterval(timer);
      void client.removeChannel(channel);
    };
  }, [symbol]);
  const last = candles.at(-1);
  return (
    <div className="page">
      <Link className="back" href="/stocks">
        ← Back to watchlist
      </Link>
      <div className="heading">
        <div>
          <div className="eyebrow">NSE / EQUITY / DAILY</div>
          <h1>{symbol}</h1>
          <p className="subtitle">
            Price history with a clear record of where it came from.
          </p>
        </div>
        <span className="connection">1D · {candles.length} sessions</span>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <section className="panel" style={{ marginBottom: 28 }}>
        <div className="panel-heading">
          <h2>Daily price & volume</h2>
          <span className="small-link">INR</span>
        </div>
        <div className="chart-wrap">
          {loading ? (
            <div className="skeleton">Loading stored candles…</div>
          ) : !last ? (
            <div className="empty">
              <h2>No candles stored for {symbol}</h2>
              <p>Fetch this symbol to begin its price history.</p>
            </div>
          ) : (
            <>
              <div className="stats">
                <div>
                  <label>LATEST CLOSE</label>
                  <strong>{money(Number(last.close))}</strong>
                </div>
                <div>
                  <label>SESSION DATE</label>
                  <strong>{sessionDate(last.ts)}</strong>
                </div>
                <div>
                  <label>SOURCE</label>
                  <strong>{last.source}</strong>
                </div>
              </div>
              <ResearchChart candles={candles} symbol={symbol} />
              <p className="attribution">
                {last.adjusted
                  ? "Split-adjusted source data."
                  : "Unadjusted source data; corporate actions can cause price jumps."}{" "}
                Stored session dates shown in IST.
              </p>
            </>
          )}
          <p className="attribution">
            TradingView Lightweight Charts™ · Copyright (c) 2026 TradingView,
            Inc.{" "}
            <a
              href="https://www.tradingview.com/"
              target="_blank"
              rel="noreferrer"
            >
              Charting technology by TradingView
            </a>
            .
          </p>
        </div>
      </section>
      <EventFeed symbol={symbol} />
    </div>
  );
}
