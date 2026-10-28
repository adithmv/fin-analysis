import "server-only";

const ENDPOINT = "https://mcp.nseindia.in/cmmkt/mcp";
const CACHE_MS = 90_000;
const PAGE_SIZE = 500;
const SYMBOL_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ&._-";
const ROOT_PREFIXES = [...SYMBOL_CHARS];

type Segment = "CM" | "SME";
type NseQuote = {
  type: string;
  symbol: string;
  series: string;
  lastTradedPrice: number;
  perChange: number;
  perChange30d: number;
  volume: number;
  value: number;
  fiftyTwoWeekHigh: number | null;
  fiftyTwoWeekLow: number | null;
};
type Snapshot = {
  quotes: NseQuote[];
  asOf: string;
};
type Candidate = {
  symbol: string;
  segment: Segment;
  series: string;
  price: number;
  changeToday: number;
  change30d: number;
  turnoverCr: number;
  volume: number;
  rangePosition: number;
  score: number;
};
type CacheEntry = { createdAt: number; value: Snapshot };

const cache = new Map<Segment, CacheEntry>();
const pending = new Map<Segment, Promise<Snapshot>>();

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function decodeResponse(response: Response) {
  const raw = await response.text();
  if (!response.ok) throw new Error("NSE market feed unavailable");
  const eventData = raw
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trim())
    .at(-1);
  const body = eventData || raw.trim();
  if (!body) throw new Error("NSE market feed returned no data");
  const parsed: unknown = JSON.parse(body);
  if (!isRecord(parsed) || parsed.error) {
    throw new Error("NSE market feed returned an invalid response");
  }
  return parsed;
}

class NseMcpSession {
  private id = 0;
  private sessionId = "";

  async open() {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: {
        Accept: "application/json, text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: this.id++,
        method: "initialize",
        params: {
          protocolVersion: "2025-03-26",
          capabilities: {},
          clientInfo: { name: "fin-analysis-private-scanner", version: "1.0" },
        },
      }),
      signal: AbortSignal.timeout(15_000),
      cache: "no-store",
    });
    await decodeResponse(response);
    this.sessionId = response.headers.get("mcp-session-id") || "";
    if (!this.sessionId) throw new Error("NSE market session unavailable");
    const initialized = await fetch(ENDPOINT, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
      signal: AbortSignal.timeout(15_000),
      cache: "no-store",
    });
    if (!initialized.ok) throw new Error("NSE market session unavailable");
  }

  private headers() {
    return {
      Accept: "application/json, text/event-stream",
      "Content-Type": "application/json",
      "Mcp-Session-Id": this.sessionId,
      "Mcp-Protocol-Version": "2025-03-26",
    };
  }

  async call<T>(name: string, args: Record<string, unknown>): Promise<T> {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: this.id++,
        method: "tools/call",
        params: { name, arguments: args },
      }),
      signal: AbortSignal.timeout(15_000),
      cache: "no-store",
    });
    const payload = await decodeResponse(response);
    const result = payload.result;
    if (!isRecord(result) || result.isError === true || !Array.isArray(result.content)) {
      throw new Error("NSE market feed could not complete the scan");
    }
    const content = result.content.find(
      (item) => isRecord(item) && item.type === "text" && typeof item.text === "string",
    );
    if (!isRecord(content) || typeof content.text !== "string") {
      throw new Error("NSE market feed returned no market snapshot");
    }
    const data: unknown = JSON.parse(content.text);
    if (!isRecord(data) || !Array.isArray(data.stocks)) {
      throw new Error("NSE market feed returned an invalid market snapshot");
    }
    return data as T;
  }

  async close() {
    if (!this.sessionId) return;
    try {
      await fetch(ENDPOINT, {
        method: "DELETE",
        headers: this.headers(),
        signal: AbortSignal.timeout(3_000),
        cache: "no-store",
      });
    } catch {
      // Closing a read-only source session is best effort.
    }
  }
}

function createLimiter(maximum: number) {
  let active = 0;
  const queue: Array<() => void> = [];
  return async function limit<T>(task: () => Promise<T>) {
    if (active >= maximum) await new Promise<void>((resolve) => queue.push(resolve));
    active += 1;
    try {
      return await task();
    } finally {
      active -= 1;
      queue.shift()?.();
    }
  };
}

function isQuote(value: unknown): value is NseQuote {
  if (!isRecord(value) || typeof value.symbol !== "string") return false;
  return /^[A-Z0-9&._-]{1,40}$/.test(value.symbol);
}

async function fetchSegment(segment: Segment): Promise<Snapshot> {
  const session = new NseMcpSession();
  const tool = segment === "CM" ? "cm_get_equity_stocks" : "cm_get_sme_stocks";
  const limit = createLimiter(2);
  const timestamps: string[] = [];
  try {
    await session.open();
    async function fetchPrefix(prefix: string, depth: number): Promise<NseQuote[]> {
      const page = await limit(() =>
        session.call<{ updatedAt?: string; returned?: number; stocks: unknown[] }>(tool, {
          limit: PAGE_SIZE,
          symbolFilter: prefix,
        }),
      );
      if (page.updatedAt && Number.isFinite(Date.parse(page.updatedAt))) {
        timestamps.push(page.updatedAt);
      }
      const rows = page.stocks.filter(isQuote);
      if (Number(page.returned ?? rows.length) < PAGE_SIZE) return rows;
      if (depth >= 5) throw new Error("NSE symbol prefix exceeded scan depth");
      const children = await Promise.all(
        [...SYMBOL_CHARS].map((character) => fetchPrefix(prefix + character, depth + 1)),
      );
      return children.flat();
    }
    const pages = await Promise.all(
      ROOT_PREFIXES.map((prefix) => fetchPrefix(prefix, 1)),
    );
    const unique = new Map<string, NseQuote>();
    for (const quote of pages.flat()) {
      if (quote.type === segment) unique.set(`${quote.type}:${quote.symbol}`, quote);
    }
    const asOf = timestamps.sort((a, b) => Date.parse(a) - Date.parse(b))[0];
    if (!unique.size || !asOf) throw new Error("NSE market snapshot was empty");
    return { quotes: [...unique.values()], asOf };
  } finally {
    await session.close();
  }
}

async function getSegment(segment: Segment): Promise<Snapshot> {
  const cached = cache.get(segment);
  if (cached && Date.now() - cached.createdAt < CACHE_MS) return cached.value;
  const inflight = pending.get(segment);
  if (inflight) return inflight;
  const promise = fetchSegment(segment)
    .then((value) => {
      cache.set(segment, { createdAt: Date.now(), value });
      return value;
    })
    .finally(() => pending.delete(segment));
  pending.set(segment, promise);
  return promise;
}

function numeric(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function percentileRanks<T>(rows: T[], metric: (row: T) => number) {
  const sorted = rows
    .map((row) => ({ row, value: metric(row) }))
    .sort((a, b) => a.value - b.value);
  const ranks = new Map<T, number>();
  for (let start = 0; start < sorted.length; ) {
    let end = start + 1;
    while (end < sorted.length && sorted[end].value === sorted[start].value) end += 1;
    const rank =
      sorted.length < 2 ? 50 : ((start + end - 1) / 2 / (sorted.length - 1)) * 100;
    for (let index = start; index < end; index += 1) ranks.set(sorted[index].row, rank);
    start = end;
  }
  return ranks;
}

export async function scanNseMarket(options: {
  includeSme: boolean;
  minTurnoverCr: number;
}) {
  const snapshots = await Promise.all([
    getSegment("CM"),
    ...(options.includeSme ? [getSegment("SME")] : []),
  ]);
  const quotes = snapshots.flatMap((snapshot) => snapshot.quotes);
  const asOf = snapshots
    .map((snapshot) => snapshot.asOf)
    .sort((a, b) => Date.parse(a) - Date.parse(b))[0];
  const observed = quotes.filter(
    (quote) =>
      numeric(quote.lastTradedPrice) &&
      quote.lastTradedPrice > 0 &&
      numeric(quote.perChange) &&
      numeric(quote.perChange30d) &&
      numeric(quote.volume) &&
      quote.volume > 0 &&
      numeric(quote.value) &&
      quote.value > 0 &&
      numeric(quote.fiftyTwoWeekHigh) &&
      numeric(quote.fiftyTwoWeekLow) &&
      quote.fiftyTwoWeekHigh >= quote.fiftyTwoWeekLow &&
      quote.fiftyTwoWeekLow > 0,
  );
  const dayRanks = percentileRanks(observed, (quote) => quote.perChange);
  const monthRanks = percentileRanks(observed, (quote) => quote.perChange30d);
  const turnoverRanks = percentileRanks(observed, (quote) => Math.log1p(quote.value));
  const candidates: Candidate[] = observed
    .filter(
      (quote) =>
        quote.perChange > 0 &&
        quote.perChange30d > 0 &&
        quote.value >= options.minTurnoverCr,
    )
    .map((quote) => {
      const rangePosition = Math.max(
        0,
        Math.min(
          100,
          ((quote.lastTradedPrice - quote.fiftyTwoWeekLow!) /
            (quote.fiftyTwoWeekHigh! - quote.fiftyTwoWeekLow! || 1)) *
            100,
        ),
      );
      const score =
        monthRanks.get(quote)! * 0.35 +
        dayRanks.get(quote)! * 0.25 +
        rangePosition * 0.2 +
        turnoverRanks.get(quote)! * 0.2;
      return {
        symbol: quote.symbol,
        segment: quote.type as Segment,
        series: quote.series,
        price: quote.lastTradedPrice,
        changeToday: quote.perChange,
        change30d: quote.perChange30d,
        turnoverCr: quote.value,
        volume: quote.volume,
        rangePosition,
        score: Math.round(score),
      };
    })
    .sort((a, b) => b.score - a.score || b.turnoverCr - a.turnoverCr);

  return {
    source: "NSE CM Market Live",
    asOf,
    scanned: quotes.length,
    validSnapshots: observed.length,
    mainboardScanned: quotes.filter((quote) => quote.type === "CM").length,
    smeScanned: quotes.filter((quote) => quote.type === "SME").length,
    candidates: candidates.length,
    minTurnoverCr: options.minTurnoverCr,
    items: candidates,
  };
}
