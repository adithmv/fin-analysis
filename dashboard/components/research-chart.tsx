"use client";
import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type Time,
  type SeriesMarker,
} from "lightweight-charts";
import type { ChartEvent } from "./stock-news";
import { getBrowserClient } from "@/lib/supabase";
import { type Candle, sessionDate } from "@/lib/types";

type Indicator = { ts: string; series_key: string; value: number | null };
type Signal = {
  ts: string;
  signal_key: string;
  signal_type: string;
  direction: string;
  description: string;
  details: Record<string, unknown>;
  logic_version: string;
};

export function ResearchChart({
  candles,
  symbol,
  events,
}: {
  candles: Candle[];
  symbol: string;
  events: ChartEvent[];
}) {
  const [range, setRange] = useState("252");
  const [focusDate, setFocusDate] = useState("");
  useEffect(() => {
    const date = new URLSearchParams(window.location.search).get("date");
    if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
      setFocusDate(date);
      setRange("all");
    }
  }, []);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [overlays, setOverlays] = useState(["sma_50", "sma_200"]);
  const [type, setType] = useState("");
  const [direction, setDirection] = useState("");
  const [hover, setHover] = useState("");
  const priceRef = useRef<HTMLDivElement>(null),
    rsiRef = useRef<HTMLDivElement>(null),
    macdRef = useRef<HTMLDivElement>(null),
    volumeRef = useRef<HTMLDivElement>(null);
  const visible = range === "all" ? candles : candles.slice(-Number(range));
  const first = visible[0]?.ts,
    last = visible.at(-1)?.ts;
  useEffect(() => {
    let active = true;
    const client = getBrowserClient();
    if (!client || !first || !last) return;
    setBusy(true);
    setError("");
    setIndicators([]);
    setSignals([]);
    async function read<T>(table: string, sort: string): Promise<T[]> {
      const all: T[] = [];
      for (let offset = 0; ; offset += 500) {
        const { data, error } = await client!
          .from(table)
          .select("*")
          .eq("symbol", symbol)
          .eq("exchange", "NSE")
          .eq("timeframe", "1d")
          .gte("ts", first!)
          .lte("ts", last!)
          .order("ts")
          .order(sort)
          .range(offset, offset + 499);
        if (error) throw new Error(error.message);
        all.push(...(data as T[]));
        if (data.length < 500) return all;
      }
    }
    void Promise.all([
      read<Indicator>("indicator_values", "series_key"),
      read<Signal>("signals", "signal_key"),
    ])
      .then(([i, s]) => {
        if (active) {
          setIndicators(i);
          setSignals(s);
        }
      })
      .catch((e) => {
        if (active) setError(String(e));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [symbol, first, last]);
  useEffect(() => {
    if (
      !priceRef.current ||
      !rsiRef.current ||
      !macdRef.current ||
      !volumeRef.current
    )
      return;
    const options = {
      autoSize: true,
      layout: { background: { color: "#ffffff" }, textColor: "#687d75" },
      grid: {
        vertLines: { color: "#f5f7f6" },
        horzLines: { color: "#edf1ef" },
      },
      timeScale: { timeVisible: false },
    };
    const charts = [priceRef, rsiRef, macdRef, volumeRef].map((ref) =>
      createChart(ref.current!, options),
    );
    const price = charts[0].addSeries(CandlestickSeries, {
      upColor: "#229779",
      downColor: "#d66a6e",
      wickUpColor: "#229779",
      wickDownColor: "#d66a6e",
      borderVisible: false,
    });
    price.setData(
      visible.map((c) => ({
        time: sessionDate(c.ts) as Time,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      })),
    );
    const points = (key: string) =>
      indicators
        .filter((r) => r.series_key === key)
        .map((r) =>
          r.value === null
            ? { time: sessionDate(r.ts) as Time }
            : { time: sessionDate(r.ts) as Time, value: Number(r.value) },
        );
    const colors = [
      "#d7a12d",
      "#506cbd",
      "#9c62ac",
      "#2f958d",
      "#d77a44",
      "#8a9d9a",
    ];
    overlays.forEach((key, i) =>
      charts[0]
        .addSeries(LineSeries, {
          color: colors[i % colors.length],
          lineWidth: 1,
          title: key,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        .setData(points(key)),
    );
    const patterns = signals.filter((s) => s.signal_type === "pattern");
    const eventMarkers = events.filter((e) =>
      visible.some((c) => sessionDate(c.ts) === e.date),
    );
    const markers: SeriesMarker<Time>[] = patterns.map((s) => ({
      time: sessionDate(s.ts) as Time,
      position: s.direction === "bearish" ? "aboveBar" : "belowBar",
      color: s.direction === "bearish" ? "#be535c" : "#22856a",
      shape: s.direction === "bearish" ? "arrowDown" : "arrowUp",
      text: "",
      size: 0.5,
    }));
    markers.push(
      ...eventMarkers.map((e) => ({
        time: e.date as Time,
        position: "aboveBar" as const,
        color: e.kind === "action" ? "#ca8b25" : "#5666b5",
        shape: "circle" as const,
        text: e.kind === "action" ? "CA" : "N",
        size: 0.6,
      })),
    );
    markers.sort((a, b) => String(a.time).localeCompare(String(b.time)));
    createSeriesMarkers(price, markers);
    charts[0].subscribeCrosshairMove((param) => {
      const found = patterns.filter((s) => sessionDate(s.ts) === param.time);
      setHover(
        found
          .map(
            (s) =>
              `${s.description} · Trend: ${String(s.details.trend_state ?? "unknown")}`,
          )
          .concat(
            eventMarkers
              .filter((e) => e.date === param.time)
              .map((e) => e.text),
          )
          .join(" | "),
      );
    });
    const rsi = charts[1].addSeries(LineSeries, {
      color: "#8a62ac",
      lineWidth: 2,
      title: "RSI 14",
    });
    rsi.setData(points("rsi_14"));
    [30, 70].forEach((value) =>
      rsi.createPriceLine({
        price: value,
        color: "#b3bdb9",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: String(value),
      }),
    );
    charts[2]
      .addSeries(HistogramSeries, { color: "#bedacc", title: "Histogram" })
      .setData(points("macd_hist_12_26_9"));
    ["line", "signal"].forEach((key, i) =>
      charts[2]
        .addSeries(LineSeries, {
          color: colors[i],
          lineWidth: 1,
          title: `MACD ${key}`,
        })
        .setData(points(`macd_${key}_12_26_9`)),
    );
    charts[3]
      .addSeries(HistogramSeries, {
        color: "#bedacc",
        priceFormat: { type: "volume" },
      })
      .setData(
        visible
          .filter((c) => c.volume !== null)
          .map((c) => ({
            time: sessionDate(c.ts) as Time,
            value: Number(c.volume),
          })),
      );
    charts[3]
      .addSeries(LineSeries, {
        color: "#d7a12d",
        lineWidth: 1,
        title: "Volume avg 20",
        priceFormat: { type: "volume" },
      })
      .setData(points("volume_avg_20"));
    charts.forEach((c) => c.timeScale().fitContent());
    if (focusDate) {
      const index = visible.findIndex((c) => sessionDate(c.ts) >= focusDate);
      if (index >= 0)
        charts.forEach((c) =>
          c.timeScale().setVisibleLogicalRange({
            from: Math.max(0, index - 15),
            to: Math.min(visible.length - 1, index + 15),
          }),
        );
    }
    let syncing = false;
    charts.forEach((source) =>
      source.timeScale().subscribeVisibleLogicalRangeChange((next) => {
        if (syncing || !next) return;
        syncing = true;
        charts
          .filter((c) => c !== source)
          .forEach((c) => c.timeScale().setVisibleLogicalRange(next));
        syncing = false;
      }),
    );
    return () => charts.forEach((c) => c.remove());
    // The selected date range controls all on-demand database reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, range, indicators, signals, overlays, events, focusDate]);
  const trend = signals.filter((s) => s.signal_key === "trend_state").at(-1);
  const flags = [
    ...new Set(
      signals
        .filter((s) => s.signal_type === "data_flag")
        .map((s) => s.signal_key),
    ),
  ];
  const recent = signals
    .filter(
      (s) =>
        (!type || s.signal_type === type) &&
        (!direction || s.direction === direction),
    )
    .slice()
    .reverse();
  return (
    <>
      <div className="filters">
        <label>
          Visible history
          <select value={range} onChange={(e) => setRange(e.target.value)}>
            <option value="63">3 months</option>
            <option value="252">1 year</option>
            <option value="all">All history</option>
          </select>
        </label>
        <span className="connection" title={JSON.stringify(trend?.details)}>
          {trend?.description ?? "Trend unavailable"}
        </span>
      </div>
      <div className="overlay-controls">
        {[
          "sma_20",
          "sma_50",
          "sma_200",
          "ema_12",
          "ema_26",
          "bb_upper_20_2",
          "bb_middle_20_2",
          "bb_lower_20_2",
        ].map((key) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={overlays.includes(key)}
              onChange={() =>
                setOverlays((old) =>
                  old.includes(key)
                    ? old.filter((k) => k !== key)
                    : [...old, key],
                )
              }
            />
            {key.replaceAll("_", " ").toUpperCase()}
          </label>
        ))}
      </div>
      {busy && <p role="status">Loading indicators for the selected dates…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {flags.length > 0 && (
        <p className="research-note">
          Data checks in this range: {flags.join(", ")}. Suspected splits and
          short history are excluded from research outcomes.
        </p>
      )}
      <div
        ref={priceRef}
        className="chart"
        role="img"
        aria-label={`${visible.length} daily candlesticks with indicator overlays and pattern markers`}
      />
      <p className="marker-tooltip" role="status">
        {hover ||
          "Hover a marker: arrows are patterns, CA corporate actions, N high-importance news."}
      </p>
      <div className="indicator-title">RSI · 30 / 70 reference levels</div>
      <div
        ref={rsiRef}
        className="indicator-chart"
        role="img"
        aria-label="RSI indicator"
      />
      <div className="indicator-title">MACD · line, signal & histogram</div>
      <div
        ref={macdRef}
        className="indicator-chart"
        role="img"
        aria-label="MACD indicator"
      />
      <div className="indicator-title">Volume · 20-session average</div>
      <div
        ref={volumeRef}
        className="indicator-chart"
        role="img"
        aria-label="Volume and average"
      />
      <h2>Recent signals</h2>
      <div className="filters">
        <label>
          Signal type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All types</option>
            {[...new Set(signals.map((s) => s.signal_type))].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Direction
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
          >
            <option value="">All directions</option>
            {["bullish", "bearish", "neutral"].map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="research-scroll">
        <table aria-label="Recent technical signals">
          <thead>
            <tr>
              <th>Date</th>
              <th>Signal</th>
              <th>Direction</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {recent.slice(0, 100).map((s) => (
              <tr key={`${s.ts}-${s.signal_key}`}>
                <td>{sessionDate(s.ts)}</td>
                <td>{s.signal_key}</td>
                <td>{s.direction}</td>
                <td>
                  {s.description}
                  <details>
                    <summary>Rule details · v{s.logic_version}</summary>
                    <pre>{JSON.stringify(s.details, null, 2)}</pre>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="attribution">
        Showing {Math.min(recent.length, 100)} of {recent.length} matching
        signals in the selected date range.
      </p>
    </>
  );
}
