import { getBrowserClient } from "./supabase";
export async function readResearch<T>(
  table: string,
  filter?: [string, string],
  columns = "*",
): Promise<T[]> {
  const client = getBrowserClient();
  if (!client) throw new Error("Configure the dashboard database connection.");
  const rows: T[] = [];
  for (let offset = 0; ; offset += 500) {
    let query = client.from(table).select(columns);
    if (filter) query = query.eq(...filter);
    query =
      table === "backtest_results"
        ? query.order("symbol").order("sample")
        : query.order("id");
    const { data, error } = await query.range(offset, offset + 499);
    if (error) throw new Error(error.message);
    rows.push(...(data as unknown as T[]));
    if (data.length < 500) return rows;
  }
}
export const pct = (value: number | null | undefined) =>
  value == null ? "—" : `${(Number(value) * 100).toFixed(2)}%`;
