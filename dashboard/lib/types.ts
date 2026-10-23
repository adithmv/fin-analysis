export type EventRow = {
  id: number;
  ts: string;
  run_id: string;
  module: string;
  agent: string | null;
  action: string;
  tool: string | null;
  status: string;
  symbol: string | null;
  input_summary: string | null;
  output_summary: string | null;
  source_urls: string[] | null;
  duration_ms: number | null;
  api_calls: number | null;
  error: string | null;
  meta: Record<string, unknown>;
};
export type Candle = {
  symbol: string;
  exchange: string;
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  source: string;
  adjusted: boolean;
  fetched_at: string;
};
export function sessionDate(ts: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(ts));
}
export function dateTime(ts: string) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(ts));
}
export function money(value: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(value);
}
