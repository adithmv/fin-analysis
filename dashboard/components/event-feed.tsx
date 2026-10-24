"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
import { dateTime, type EventRow } from "@/lib/types";

const modules = [
  "ingest",
  "signals",
  "backtest",
  "news",
  "analysis-agents",
  "browser-agent",
];
const labels: Record<string, string> = {
  ingest: "Price ingestion",
  signals: "Technical signals",
  backtest: "Historical testing",
  news: "News & sentiment",
  "analysis-agents": "Research agents",
  "browser-agent": "Web research",
};
const statuses = [
  "started",
  "success",
  "failed",
  "retried",
  "skipped",
  "warning",
];

export function EventFeed({
  full = false,
  runId,
  symbol,
}: {
  full?: boolean;
  runId?: string;
  symbol?: string;
}) {
  const [rows, setRows] = useState<EventRow[]>([]);
  const [tiles, setTiles] = useState<Record<string, EventRow | null>>({});
  const [module, setModule] = useState("");
  const [status, setStatus] = useState("");
  const [filterSymbol, setSymbol] = useState(symbol || "");
  const [hours, setHours] = useState(runId ? "" : "24");
  const [page, setPage] = useState(0);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [connection, setConnection] = useState("Connecting");
  const [connectionEpoch, setConnectionEpoch] = useState(0);
  const revision = useRef(0);
  const size = full ? 50 : 25;
  const load = useCallback(async () => {
    const version = ++revision.current;
    const client = getBrowserClient();
    if (!client) {
      setError(
        "Connect Supabase using dashboard/.env.local to see your research activity.",
      );
      setLoading(false);
      setConnection("Not configured");
      return;
    }
    let query = client.from("agent_events").select("*", { count: "exact" });
    if (module) query = query.eq("module", module);
    if (status) query = query.eq("status", status);
    if (filterSymbol) query = query.eq("symbol", filterSymbol.toUpperCase());
    if (hours)
      query = query.gte(
        "ts",
        new Date(Date.now() - Number(hours) * 3600000).toISOString(),
      );
    if (runId) query = query.eq("run_id", runId);
    const result = await query
      .order("ts", { ascending: !!runId })
      .order("id", { ascending: !!runId })
      .range(page * size, (page + 1) * size - 1);
    if (version !== revision.current) return;
    if (result.error) setError(result.error.message);
    else {
      setRows(result.data as EventRow[]);
      setCount(result.count || 0);
      setError("");
    }
    setLoading(false);
    if (!full && !symbol) {
      const latest = await Promise.all(
        modules.map(async (name) => {
          const { data } = await client
            .from("agent_events")
            .select("*")
            .eq("module", name)
            .in("action", ["run_start", "run_end"])
            .order("ts", { ascending: false })
            .order("id", { ascending: false })
            .limit(1);
          return [name, data?.[0] || null] as const;
        }),
      );
      if (version === revision.current) setTiles(Object.fromEntries(latest));
    }
  }, [module, status, filterSymbol, hours, page, size, runId, full, symbol]);

  useEffect(() => {
    let active = true;
    void load();
    const client = getBrowserClient();
    if (!client) return;
    const channel = client
      .channel(`events-${runId || symbol || "feed"}`)
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "agent_events" },
        () => {
          if (active) void load();
        },
      )
      .subscribe((state) => {
        if (!active) return;
        setConnection(state === "SUBSCRIBED" ? "Live" : "Reconnecting");
        if (state === "SUBSCRIBED") void load();
      });
    // Refetch after reconnect and poll as insurance against missed socket messages.
    const timer = setInterval(() => {
      if (active) void load();
    }, 15000);
    const offline = () => setConnection("Reconnecting");
    const online = () => {
      // A stale socket can still look connected after a brief network outage.
      // Recreate the subscription and refetch instead of trusting that socket.
      setConnectionEpoch((value) => value + 1);
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    return () => {
      active = false;
      revision.current++;
      clearInterval(timer);
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
      void client.removeChannel(channel);
    };
  }, [load, runId, symbol, connectionEpoch]);

  const filters = (
    <div className="filters">
      <label>
        Module
        <select
          aria-label="Module"
          value={module}
          onChange={(e) => {
            setModule(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All modules</option>
          {modules.map((x) => (
            <option key={x}>{x}</option>
          ))}
          <option>setup</option>
        </select>
      </label>
      <label>
        Status
        <select
          aria-label="Status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All statuses</option>
          {statuses.map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </label>
      {!symbol && (
        <label>
          Symbol
          <input
            aria-label="Symbol"
            placeholder="e.g. RELIANCE"
            value={filterSymbol}
            onChange={(e) => {
              setSymbol(e.target.value.toUpperCase());
              setPage(0);
            }}
          />
        </label>
      )}
      <label>
        Period
        <select
          aria-label="Period"
          value={hours}
          onChange={(e) => {
            setHours(e.target.value);
            setPage(0);
          }}
        >
          <option value="24">Last 24 hours</option>
          <option value="168">Last 7 days</option>
          <option value="720">Last 30 days</option>
          <option value="">All time</option>
        </select>
      </label>
    </div>
  );
  const content = (
    <>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              {runId
                ? "Run timeline"
                : symbol
                  ? "Recent stock activity"
                  : full
                    ? "Action logbook"
                    : "Activity stream"}
            </h2>
            <p>
              {runId
                ? runId
                : `${count.toLocaleString()} recorded actions · ${runId ? "Oldest" : "Newest"} first`}
            </p>
          </div>
          {!full && !symbol && (
            <Link className="small-link" href="/logbook">
              View full logbook ↗
            </Link>
          )}
        </div>
        {filters}
        {loading ? (
          <div className="skeleton">Loading recorded activity…</div>
        ) : rows.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">◎</div>
            <h2>No matching activity yet</h2>
            <p>
              Run price ingestion or adjust your filters. Real actions will
              appear here.
            </p>
          </div>
        ) : (
          rows.map((row) => <Event key={row.id} row={row} />)
        )}
        {full && (
          <div className="pager">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>
              ← Previous
            </button>
            <span>
              Page {page + 1} of {Math.max(1, Math.ceil(count / size))}
            </span>
            <button
              disabled={(page + 1) * size >= count}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </section>
    </>
  );
  if (symbol) return content;
  return (
    <div className="page">
      {runId && (
        <Link className="back" href="/logbook">
          ← Back to logbook
        </Link>
      )}
      <div className="heading">
        <div>
          <div className="eyebrow">OBSERVE / UNDERSTAND / VERIFY</div>
          <h1>
            {runId
              ? "Follow the evidence"
              : full
                ? "Every action, on record"
                : "Your research, in motion"}
          </h1>
          <p className="subtitle">
            {full
              ? "Explore the exact steps behind your market data."
              : "A clear view of your data pipeline. From source to stored candle."}
          </p>
        </div>
        <span
          className={`connection ${connection === "Live" ? "" : "offline"}`}
        >
          <span className="dot" />
          {connection}
        </span>
      </div>
      {!full && (
        <div className="status-grid">
          {modules.map((name) => (
            <div className="status-tile" key={name}>
              <div className="tile-label">
                <span>
                  {["ingest", "signals", "backtest", "news"].includes(name)
                    ? "ACTIVE MODULE"
                    : "COMING LATER"}
                </span>
                <span>↗</span>
              </div>
              <div className="tile-name">{labels[name]}</div>
              <span className={`badge ${tiles[name]?.status || "never"}`}>
                {tiles[name]?.status || "Never run"}
              </span>
              <p className="tile-time">
                {tiles[name]
                  ? dateTime(tiles[name]!.ts)
                  : "Awaiting a future phase"}
              </p>
            </div>
          ))}
        </div>
      )}
      {content}
    </div>
  );
}

function Event({ row }: { row: EventRow }) {
  const safeUrls = (row.source_urls || []).filter((url) =>
    /^https?:\/\//i.test(url),
  );
  return (
    <details className="event">
      <summary>
        <span className="event-time">{dateTime(row.ts)}</span>
        <span className={`badge ${row.status}`}>{row.status}</span>
        <div>
          <div className="event-title">
            {row.action.replaceAll("_", " ")}{" "}
            <span style={{ fontWeight: 400, color: "#8b979e" }}>
              {" "}
              / {row.module}
            </span>
          </div>
          <div className="event-desc">
            {row.output_summary ||
              row.input_summary ||
              row.error ||
              "Action recorded"}
          </div>
        </div>
        <span className="symbol">{row.symbol || "SYSTEM"}</span>
      </summary>
      <div className="event-body">
        <p>
          <strong>Run:</strong>{" "}
          <Link href={`/logbook/run/${row.run_id}`}>{row.run_id}</Link>
        </p>
        {row.tool && (
          <p>
            <strong>Source/tool:</strong> {row.tool}
          </p>
        )}
        {row.input_summary && (
          <p>
            <strong>Input:</strong> {row.input_summary}
          </p>
        )}
        {row.output_summary && (
          <p>
            <strong>Output:</strong> {row.output_summary}
          </p>
        )}
        {row.error && <p className="error">{row.error}</p>}
        <p>
          Duration: {row.duration_ms === null ? "—" : `${row.duration_ms} ms`} ·
          Fetch operations: {row.api_calls ?? "—"}
        </p>
        {safeUrls.map((url) => (
          <p key={url}>
            <a href={url} target="_blank" rel="noreferrer">
              {url} ↗
            </a>
          </p>
        ))}
        {Object.keys(row.meta || {}).length > 0 && (
          <pre>{JSON.stringify(row.meta, null, 2)}</pre>
        )}
      </div>
    </details>
  );
}
