"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
import { type Candle, money, sessionDate } from "@/lib/types";

type Stock = {
  symbol: string;
  exchange: string;
  kind: string;
  candle: Candle | null;
};
type SearchResult = { symbol: string; company: string; series: "EQ" };

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

async function ownerToken() {
  const client = getBrowserClient();
  if (!client) throw new Error("Dashboard Supabase connection is not configured.");
  const { data, error } = await client.auth.getSession();
  if (error || !data.session) {
    throw new Error("Sign in with your owner account to manage the watchlist.");
  }
  return data.session.access_token;
}

export function Watchlist() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searchMessage, setSearchMessage] = useState("");
  const [savingSymbol, setSavingSymbol] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const client = getBrowserClient();
    if (!client) {
      setError("Configure dashboard/.env.local to connect Supabase.");
      setLoading(false);
      return;
    }
    if (refreshVersion === 0) setLoading(true);
    async function load() {
      const { data, error } = await client!
        .from("watchlist")
        .select("symbol,exchange,kind")
        .eq("active", true)
        .order("symbol");
      if (error) throw new Error(error.message);
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
  }, [refreshVersion]);

  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      setSearchError("");
      return;
    }
    let active = true;
    const controller = new AbortController();
    setSearchLoading(true);
    setSearchError("");
    const timer = setTimeout(() => {
      void (async () => {
        const token = await ownerToken();
        const response = await fetch(
          `/api/watchlist/search?q=${encodeURIComponent(query)}`,
          {
            headers: { Authorization: `Bearer ${token}` },
            cache: "no-store",
            signal: controller.signal,
          },
        );
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(
            response.status === 401 || response.status === 403
              ? "Sign in with your owner account to search NSE stocks."
              : payload.error || "Stock search could not be completed.",
          );
        }
        if (active) setSearchResults(payload.items || []);
      })()
        .catch((e) => {
          if (active && !controller.signal.aborted) {
            setSearchResults([]);
            setSearchError(String(e instanceof Error ? e.message : e));
          }
        })
        .finally(() => {
          if (active) setSearchLoading(false);
        });
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [search]);

  async function changeWatchlist(action: "add" | "remove", symbol: string) {
    setSavingSymbol(symbol);
    setSearchError("");
    setSearchMessage("");
    try {
      const token = await ownerToken();
      const response = await fetch("/api/watchlist", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ action, symbol }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          response.status === 401 || response.status === 403
            ? "Sign in with your owner account to change the watchlist."
            : payload.error || "The watchlist could not be updated.",
        );
      }
      if (action === "add") {
        setStocks((current) => {
          if (current.some((stock) => stock.symbol === symbol && stock.exchange === "NSE")) {
            return current;
          }
          return [
            ...current,
            { symbol, exchange: "NSE", kind: "equity", candle: null },
          ].sort((left, right) => left.symbol.localeCompare(right.symbol));
        });
        setSearchMessage(`${symbol} added to your active watchlist.`);
      } else {
        setStocks((current) => current.filter((stock) => stock.symbol !== symbol));
        setSearchMessage(`${symbol} removed. Past research and price history are kept.`);
      }
      setRefreshVersion((version) => version + 1);
    } catch (e) {
      setSearchError(String(e instanceof Error ? e.message : e));
    } finally {
      setSavingSymbol("");
    }
  }

  const activeSymbols = new Set(
    stocks.filter((stock) => stock.kind === "equity").map((stock) => stock.symbol),
  );
  const equityCount = stocks.filter((stock) => stock.kind === "equity").length;

  return (
    <div className="page">
      <div className="heading">
        <div>
          <div className="eyebrow">YOUR RESEARCH UNIVERSE</div>
          <h1>Research the stocks you choose</h1>
          <p className="subtitle">
            Search NSE-listed companies, then keep technical checks focused on your active watchlist.
          </p>
        </div>
        <span className="connection">NSE · {equityCount} equities watched</span>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      <section className="panel watchlist-finder" id="find-stocks">
        <div className="panel-heading">
          <div>
            <h2>Find NSE stocks</h2>
            <p>Search by company name or symbol in NSE’s current EQ-series list.</p>
          </div>
          <span className="small-link">NSE · EQ</span>
        </div>
        <label className="watchlist-search-label" htmlFor="watchlist-stock-search">
          Company or symbol
        </label>
        <input
          id="watchlist-stock-search"
          className="watchlist-search-input"
          type="search"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setSearchMessage("");
          }}
          placeholder="For example, Tata Motors or TATAMOTORS"
          autoComplete="off"
        />
        <p className="watchlist-search-hint">
          Type at least 2 characters. Search results are matched against the official NSE company and symbol list.
        </p>
        {searchLoading && <div className="watchlist-search-status">Searching NSE listings…</div>}
        {searchError && (
          <div className="error watchlist-search-feedback" role="alert">
            {searchError}
          </div>
        )}
        {searchMessage && (
          <div className="watchlist-search-success" role="status">
            {searchMessage}
          </div>
        )}
        {search.trim().length >= 2 && !searchLoading && !searchError && !searchResults.length && (
          <div className="watchlist-search-status">No NSE EQ-series match found.</div>
        )}
        {!!searchResults.length && (
          <ul className="watchlist-search-results">
            {searchResults.map((result) => {
              const watched = activeSymbols.has(result.symbol);
              return (
                <li key={result.symbol}>
                  <span className="watchlist-company">
                    <strong>{result.company}</strong>
                    <small>{result.symbol} · NSE EQ</small>
                  </span>
                  <button
                    type="button"
                    className="watchlist-action"
                    disabled={watched || savingSymbol === result.symbol}
                    onClick={() => void changeWatchlist("add", result.symbol)}
                  >
                    {watched ? "Added" : savingSymbol === result.symbol ? "Adding…" : "Add"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Active watchlist</h2>
            <p>Daily candles · Technical signals · AI stock reviews use these active equities</p>
          </div>
          <span className="small-link">INR</span>
        </div>
        {loading ? (
          <div className="skeleton">Loading your watchlist…</div>
        ) : !stocks.length ? (
          <div className="empty">
            <h2>Your watchlist is ready</h2>
            <p>Search above and add the NSE stocks you want to follow.</p>
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
                  <th>Manage</th>
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
                          {stock.symbol} ↗
                          <small>
                            {stock.exchange} {stock.kind}
                          </small>
                        </Link>
                      </td>
                      <td className="price">
                        {stock.candle ? money(Number(stock.candle.close)) : "—"}
                      </td>
                      <td>{stock.candle ? sessionDate(stock.candle.ts) : "—"}</td>
                      <td>{stock.candle?.source || "—"}</td>
                      <td>
                        <span className={`badge ${state.status}`}>{state.text}</span>
                      </td>
                      <td>
                        {stock.kind === "equity" ? (
                          <button
                            type="button"
                            className="watchlist-remove"
                            disabled={savingSymbol === stock.symbol}
                            onClick={() => void changeWatchlist("remove", stock.symbol)}
                          >
                            {savingSymbol === stock.symbol ? "Removing…" : "Remove"}
                          </button>
                        ) : (
                          <span className="watchlist-baseline">Market baseline</span>
                        )}
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
        Adding or removing a stock changes future active-watchlist checks. Existing price history and past research are retained. Price feeds and the daily schedule are currently disabled, and periodic fundamental checks are not implemented yet. See Operations and Source health for status.
      </p>
    </div>
  );
}
