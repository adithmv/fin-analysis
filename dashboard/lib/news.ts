import { readResearch } from "./research";
export type NewsLink = {
  symbol: string;
  confidence: number;
  matched_text: string;
  match_type: string;
};
export type Sentiment = {
  label: string;
  score: number;
  p_positive: number;
  p_negative: number;
  p_neutral: number;
  model_key: string;
  model_revision: string;
  computed_at: string;
};
export type NewsEvent = {
  event_type: string;
  importance: number;
  symbol: string;
  effective_trading_date: string | null;
  matched_rule: string;
};
export type Article = {
  id: string;
  title: string;
  summary: string;
  url: string;
  source_key: string;
  published_at: string;
  published_at_assumed: boolean;
  is_duplicate: boolean;
  dedupe_group_id: string | null;
  article_symbols: NewsLink[];
  article_sentiment: Sentiment[];
  news_events: NewsEvent[];
};
export type CorporateAction = {
  id: number;
  symbol: string;
  action_type: string;
  ex_date: string | null;
  record_date: string | null;
  parsed: Record<string, unknown>;
  ratio_text: string;
  parse_status: string;
  source: string;
};
export const articles = () =>
  readResearch<Article>(
    "articles",
    undefined,
    "id,title,summary,url,source_key,published_at,published_at_assumed,is_duplicate,dedupe_group_id,article_symbols(*),article_sentiment(*),news_events(*)",
  );
export const score = (a: Article) =>
  [...a.article_sentiment].sort((x, y) =>
    y.computed_at.localeCompare(x.computed_at),
  )[0];
export const bucket = (s: number) =>
  s <= -0.6
    ? "very_negative"
    : s < -0.2
      ? "negative"
      : s >= 0.6
        ? "very_positive"
        : s > 0.2
          ? "positive"
          : "neutral";
export const titleCase = (s: string) => s.replaceAll("_", " ");
export function externalUrl(value: string) {
  try {
    const u = new URL(value);
    return ["http:", "https:"].includes(u.protocol) ? u.href : "#";
  } catch {
    return "#";
  }
}
