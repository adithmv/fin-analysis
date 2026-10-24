import { getBrowserClient } from "./supabase";
export type Thread = {
  id: string;
  symbol: string;
  thread_date: string;
  status: string;
  kind: string;
  data_cutoff_ts: string;
  run_id: string;
  prompt_version: string;
  llm_model: string;
  config: Record<string, unknown>;
  failure_reason: string | null;
  created_at: string;
};
export type Claim = {
  id: string;
  text: string;
  kind: string;
  evidence_id: string | null;
  metric: string | null;
  value: number | null;
};
export type Verification = {
  claim_id?: string;
  status?: string;
  reasons?: string[];
  reason?: string;
  value?: number;
};
export type Message = {
  id: number;
  seq: number;
  author_role: string;
  author_type: string;
  round: number;
  content_md: string;
  stance: string;
  confidence: string;
  claims: Claim[];
  evidence: Record<string, unknown>[];
  verification_status: string;
  verification_notes: Verification[];
  event_ids: number[];
  llm_model: string;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
};
export type Point = {
  text: string;
  claim_ids: string[];
  evidence: Record<string, unknown>[];
};
export type Report = {
  id: string;
  thread_id: string;
  symbol: string;
  as_of_date: string;
  stance: string;
  confidence: string;
  horizon_days: number;
  summary_md: string;
  key_points: Point[];
  risks: Point[];
  invalidation: Point[];
  what_changed: Record<string, unknown>;
  evidence_strength: string;
  evidence_strength_why: string[];
  data_quality_notes: string[];
  verification_summary: Record<string, number | boolean>;
  disclaimer: string;
};
export type Pack = {
  symbol: string;
  cutoff: string;
  quality_notes: string[];
  items: {
    evidence_id: string;
    section: string;
    ref: Record<string, unknown>;
    row: Record<string, unknown>;
  }[];
};
export async function agentRows<T>(
  table: string,
  filter?: [string, string],
  order = "id",
): Promise<T[]> {
  const c = getBrowserClient();
  if (!c) throw new Error("Database connection unavailable");
  const rows: T[] = [];
  for (let n = 0; ; n += 500) {
    let q = c.from(table).select("*");
    if (filter) q = q.eq(...filter);
    const { data, error } = await q.order(order).range(n, n + 499);
    if (error) throw new Error(error.message);
    rows.push(...(data as T[]));
    if (data.length < 500) return rows;
  }
}
export async function requestAnalysis(value: {
  kind: "analysis" | "question";
  symbol?: string;
  thread_id?: string;
  question_text?: string;
}) {
  const c = getBrowserClient();
  if (!c) throw new Error("Database connection unavailable");
  const { error } = await c.from("analysis_requests").insert(value);
  if (error) throw new Error(error.message);
}
