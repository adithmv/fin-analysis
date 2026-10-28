"use client";

import { useEffect, useMemo, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { LoginRequired, useLogin } from "./auth";

type Candidate = {
  symbol: string;
  segment: "CM" | "SME";
  series: string;
  price: number;
  changeToday: number;
  change30d: number;
  turnoverCr: number;
  volume: number;
  rangePosition: number;
  score: number;
};
type Scan = {
  source: string;
  asOf: string;
  scanned: number;
  validSnapshots: number;
  mainboardScanned: number;
  smeScanned: number;
  candidates: number;
  minTurnoverCr: number;
  items: Candidate[];
};

const PAGE_SIZE = 50;
const rupees = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});
const whole = new Intl.NumberFormat("en-IN");
const crores = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
function signed(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function MarketScanner() {
  const { ready, loggedIn } = useLogin();
  const [scan, setScan] = useState<Scan | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [includeSme, setIncludeSme] = useState(false);
  const [minTurnoverCr, setMinTurnoverCr] = useState("1");
  const [refreshKey, setRefreshKey] = useState(0);
  const [page, setPage] = useState(0);

  useEffect(() => {
    if (!ready || !loggedIn) return;
    let current = true;
    async function load() {
      setLoading(true);
      setError("");
      setScan(null);
      try {
        const client = getBrowserClient();
        if (!client) throw new Error("Dashboard database settings are missing.");
        const { data, error: sessionError } = await client.auth.getSession();
        if (sessionError || !data.session)
          throw new Error("Sign in again to run the market scan.");
        const params = new URLSearchParams({
          includeSme: String(includeSme),
          minTurnoverCr,
        });
        const response = await fetch(`/api/market-scanner?${params}`, {
          headers: { Authorization: `Bearer ${data.session.access_token}` },
          cache: "no-store",
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Market scan failed.");
        if (current) {
          setScan(result as Scan);
          setPage(0);
        }
      } catch (cause) {
        if (current)
          setError(cause instanceof Error ? cause.message : "Market scan failed.");
      } finally {
        if (current) setLoading(false);
      }
    }
    void load();
    return () => {
      current = false;
    };
  }, [ready, loggedIn, includeSme, minTurnoverCr, refreshKey]);

  const visible = useMemo(() => {
    if (!scan) return [];
    const start = page * PAGE_SIZE;
    return scan.items.slice(start, start + PAGE_SIZE);
  }, [scan, page]);

  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;

  return (
    <div className="page">
      <div className="eyebrow">INDIA / NSE MARKET-WIDE</div>
      <div className="scanner-title-row">
        <div>
          <h1>Potential stock screen</h1>
          <p className="subtitle">
            Rising momentum and active trading across NSE listings, beyond your watchlist.
          </p>
        </div>
        <button
          className="scanner-refresh"
          disabled={loading}
          onClick={() => setRefreshKey((value) => value + 1)}
        >
          {loading ? "Scanning NSE…" : "Refresh scan"}
        </button>
      </div>

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}

      <section className="scanner-controls panel">
        <label>
          Minimum traded value
          <select
            value={minTurnoverCr}
            disabled={loading}
            onChange={(event) => setMinTurnoverCr(event.target.value)}
          >
            <option value="0">Any traded value</option>
            <option value="0.5">₹0.5 crore</option>
            <option value="1">₹1 crore</option>
            <option value="5">₹5 crore</option>
            <option value="10">₹10 crore</option>
          </select>
        </label>
        <label className="scanner-check">
          <input
            type="checkbox"
            checked={includeSme}
            disabled={loading}
            onChange={(event) => setIncludeSme(event.target.checked)}
          />
          Include NSE SME listings
        </label>
        <span className="scanner-control-note">
          Candidates need positive change today and over 30 days.
        </span>
      </section>

      {loading && (
        <div className="panel scanner-loading" role="status">
          Checking NSE market listings and current snapshots…
        </div>
      )}

      {scan && (
        <>
          <div className="scanner-stats">
            <div className="panel">
              <span>Symbols scanned</span>
              <strong>{whole.format(scan.scanned)}</strong>
            </div>
            <div className="panel">
              <span>Momentum candidates</span>
              <strong>{whole.format(scan.candidates)}</strong>
            </div>
            <div className="panel">
              <span>Market snapshot (IST)</span>
              <strong>
                {new Date(scan.asOf).toLocaleTimeString("en-IN", {
                  timeZone: "Asia/Kolkata",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </strong>
            </div>
          </div>

          <p className="research-note">
            <strong>How the score works:</strong> 35% relative 30-day return, 25% daily move,
            20% position in the 52-week range, and 20% traded-value rank. Candidates must be up
            today and over 30 days and meet the selected traded-value floor. {whole.format(scan.validSnapshots)}
            of {whole.format(scan.scanned)} listings had complete, active price and volume data.
            The score is a relative ranking, not a probability or forecast.
          </p>

          <section className="panel scanner-results">
            <div className="panel-heading">
              <div>
                <h2>Momentum candidates</h2>
                <p>
                  Ranked by 30-day momentum, today’s move, 52-week position, and traded value.
                </p>
              </div>
              <span className="small-link">{scan.source}</span>
            </div>
            {!scan.items.length ? (
              <div className="empty scanner-empty">
                <h2>No matches with these filters</h2>
                <p>Lower the traded-value minimum or refresh after the next market update.</p>
              </div>
            ) : (
              <>
                <div className="scanner-table-wrap">
                  <table className="scanner-table">
                    <thead>
                      <tr>
                        <th>Symbol</th>
                        <th>Last price</th>
                        <th>Today</th>
                        <th>30 days</th>
                        <th>52-week range</th>
                        <th>Traded ₹ Cr</th>
                        <th>Screen score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visible.map((item) => (
                        <tr key={`${item.segment}:${item.symbol}`}>
                          <td>
                            <strong>{item.symbol}</strong>
                            {item.segment === "SME" && (
                              <span className="scanner-sme">SME</span>
                            )}
                          </td>
                          <td className="price">{rupees.format(item.price)}</td>
                          <td className="scanner-positive">{signed(item.changeToday)}</td>
                          <td className="scanner-positive">{signed(item.change30d)}</td>
                          <td>
                            <div className="scanner-range">
                              <span>{Math.round(item.rangePosition)}%</span>
                              <div>
                                <i style={{ width: `${item.rangePosition}%` }} />
                              </div>
                            </div>
                          </td>
                          <td>{crores.format(item.turnoverCr)}</td>
                          <td>
                            <span className="scanner-score">{item.score}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="pager scanner-pager">
                  <span>
                    Showing {page * PAGE_SIZE + 1}–
                    {Math.min((page + 1) * PAGE_SIZE, scan.items.length)} of {scan.items.length}
                  </span>
                  <div>
                    <button disabled={page === 0} onClick={() => setPage((value) => value - 1)}>
                      Previous
                    </button>
                    <button
                      disabled={(page + 1) * PAGE_SIZE >= scan.items.length}
                      onClick={() => setPage((value) => value + 1)}
                    >
                      Next
                    </button>
                  </div>
                </div>
              </>
            )}
          </section>

          <p className="attribution scanner-disclaimer">
            This is a momentum screen for research, not a buy/sell recommendation or forecast. NSE
            snapshots may be delayed by 1–3 minutes. The NSE equity segment can include ETFs and
            other listed instruments; BSE-only securities are outside this first scan. Data is
            provided by the <a href="https://www.nseindia.com/nse-mcp" target="_blank" rel="noreferrer">official NSE market interface</a> for personal informational use.
          </p>
        </>
      )}
    </div>
  );
}
