"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
import { type Candle, money, sessionDate } from "@/lib/types";

type Stock = { symbol: string; exchange: string; candle: Candle | null };
function health(candle: Candle | null) {
  if (!candle) return { text: "No data", status: "never" };
  const last = sessionDate(candle.ts);
  const today = sessionDate(new Date().toISOString());
  let days = 0;
  const cursor = new Date(`${last}T12:00:00Z`);
  while (cursor.toISOString().slice(0, 10) < today) {
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    if (cursor.getUTCDay() !== 0 && cursor.getUTCDay() !== 6) days++;
  }
  return days >= 3
    ? { text: `${days} weekdays old`, status: "warning" }
    : { text: "Up to date", status: "success" };
}
export function Watchlist() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    const client = getBrowserClient();
    if (!client) {
      setError("Configure dashboard/.env.local to connect Supabase.");
      setLoading(false);
      return;
    }
    async function load() {
      const { data, error } = await client!
        .from("watchlist")
        .select("symbol,exchange")
        .eq("active", true)
        .order("symbol");
      if (error) {
        if (active) {
          setError(error.message);
          setLoading(false);
        }
        return;
      }
      const result = await Promise.all(
        (data || []).map(async (stock) => {
          const latest = await client!
            .from("candles")
            .select("*")
            .eq("symbol", stock.symbol)
            .eq("exchange", stock.exchange)
            .eq("timeframe", "1d")
            .order("ts", { ascending: false })
            .limit(1);
          if (latest.error) throw new Error(latest.error.message);
          return { ...stock, candle: (latest.data?.[0] as Candle) || null };
        }),
      );
      if (active) {
        setStocks(result);
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
      .channel("watchlist-candles")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "candles" },
        refresh,
      )
      .subscribe();
    return () => {
      active = false;
      clearInterval(timer);
      void client.removeChannel(channel);
    };
  }, []);
  return (
    <div className="page">
      <div className="heading">
        <div>
          <div className="eyebrow">YOUR RESEARCH UNIVERSE</div>
          <h1>A focused view of the market</h1>
          <p className="subtitle">
            Daily candles, source provenance, and data health for your
            watchlist.
          </p>
        </div>
        <span className="connection">NSE · {stocks.length} stocks</span>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Watchlist</h2>
            <p>Stored market data · Daily timeframe</p>
          </div>
          <span className="small-link">INR</span>
        </div>
        {loading ? (
          <div className="skeleton">Loading your watchlist…</div>
        ) : !stocks.length ? (
          <div className="empty">
            <h2>Your watchlist is ready for data</h2>
            <p>Run ingestion to sync the configured stocks.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Company / symbol</th>
                  <th>Latest close</th>
                  <th>Session date</th>
                  <th>Source</th>
                  <th>Data health</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map((stock) => {
                  const state = health(stock.candle);
                  return (
                    <tr key={`${stock.exchange}:${stock.symbol}`}>
                      <td>
                        <Link
                          className="stock-symbol"
                          href={`/stocks/${encodeURIComponent(stock.symbol)}`}
                        >
                          {stock.symbol} ↗<small>{stock.exchange} equity</small>
                        </Link>
                      </td>
                      <td className="price">
                        {stock.candle ? money(Number(stock.candle.close)) : "—"}
                      </td>
                      <td>
                        {stock.candle ? sessionDate(stock.candle.ts) : "—"}
                      </td>
                      <td>{stock.candle?.source || "—"}</td>
                      <td>
                        <span className={`badge ${state.status}`}>
                          {state.text}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <p className="attribution">
        Health uses weekdays as an approximation; exchange holidays may make
        data appear older.
      </p>
    </div>
  );
}
