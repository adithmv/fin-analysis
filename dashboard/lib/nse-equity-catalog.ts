import "server-only";

const CATALOG_URL =
  "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv";
const CATALOG_TTL_MS = 6 * 60 * 60 * 1000;
const SYMBOL_PATTERN = /^[A-Z0-9&._-]{1,40}$/;

export type NseEquity = {
  symbol: string;
  company: string;
  series: "EQ";
};

type Catalog = { loadedAt: number; entries: NseEquity[] };
let cachedCatalog: Catalog | null = null;
let pendingCatalog: Promise<Catalog> | null = null;

function csvRows(text: string) {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted && character === '"' && text[index + 1] === '"') {
      field += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (!quoted && character === ",") {
      row.push(field.trim());
      field = "";
    } else if (!quoted && (character === "\n" || character === "\r")) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(field.trim());
      if (row.some((value) => value.length)) rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }
  row.push(field.trim());
  if (row.some((value) => value.length)) rows.push(row);
  if (quoted) throw new Error("NSE equity list is incomplete");
  return rows;
}

async function loadCatalog(): Promise<Catalog> {
  if (cachedCatalog && Date.now() - cachedCatalog.loadedAt < CATALOG_TTL_MS) {
    return cachedCatalog;
  }
  if (pendingCatalog) return pendingCatalog;

  pendingCatalog = (async () => {
    const response = await fetch(CATALOG_URL, {
      cache: "no-store",
      headers: {
        Accept: "text/csv,*/*",
        "User-Agent": "Mozilla/5.0 FinAnalysis personal research dashboard",
      },
      signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) throw new Error("NSE equity catalogue is unavailable");
    const text = (await response.text()).replace(/^\uFEFF/, "");
    if (!text || text.length > 2_000_000) {
      throw new Error("NSE equity catalogue is invalid");
    }
    const rows = csvRows(text);
    const header = rows[0]?.map((value) => value.toUpperCase());
    const symbolIndex = header?.indexOf("SYMBOL") ?? -1;
    const companyIndex = header?.indexOf("NAME OF COMPANY") ?? -1;
    const seriesIndex = header?.indexOf("SERIES") ?? -1;
    if (symbolIndex < 0 || companyIndex < 0 || seriesIndex < 0) {
      throw new Error("NSE equity catalogue has an unknown format");
    }
    const entries = rows
      .slice(1)
      .map((values) => ({
        symbol: values[symbolIndex]?.toUpperCase() || "",
        company: values[companyIndex] || "",
        series: values[seriesIndex]?.toUpperCase() || "",
      }))
      .filter(
        (entry): entry is NseEquity =>
          entry.series === "EQ" &&
          SYMBOL_PATTERN.test(entry.symbol) &&
          entry.company.length > 0,
      );
    if (!entries.length) throw new Error("NSE equity catalogue is empty");
    const catalog: Catalog = { loadedAt: Date.now(), entries };
    cachedCatalog = catalog;
    return catalog;
  })().finally(() => {
    pendingCatalog = null;
  });
  return pendingCatalog;
}

export async function searchNseEquities(query: string) {
  const catalog = await loadCatalog();
  const normalized = query.trim().toLocaleLowerCase("en-IN");
  const matches = catalog.entries
    .map((entry) => {
      const symbol = entry.symbol.toLocaleLowerCase("en-IN");
      const company = entry.company.toLocaleLowerCase("en-IN");
      const rank =
        symbol === normalized
          ? 0
          : symbol.startsWith(normalized)
            ? 1
            : company.startsWith(normalized)
              ? 2
              : symbol.includes(normalized)
                ? 3
                : company.includes(normalized)
                  ? 4
                  : 99;
      return { entry, rank };
    })
    .filter(({ rank }) => rank < 99)
    .sort(
      (left, right) =>
        left.rank - right.rank || left.entry.company.localeCompare(right.entry.company),
    )
    .slice(0, 30)
    .map(({ entry }) => entry);
  return { items: matches, retrievedAt: new Date(catalog.loadedAt).toISOString() };
}

export async function isNseEquity(symbol: string) {
  if (!SYMBOL_PATTERN.test(symbol)) return false;
  const catalog = await loadCatalog();
  return catalog.entries.some((entry) => entry.symbol === symbol);
}
