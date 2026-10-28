import { authorizeOwner, boundedBody, failure } from "@/lib/ops-server";
import { isNseEquity } from "@/lib/nse-equity-catalog";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const { client } = await authorizeOwner(request);
    const body = await boundedBody(request);
    const action = String(body.action);
    const symbol = String(body.symbol || "").trim().toUpperCase();
    if (!/^[A-Z0-9&._-]{1,40}$/.test(symbol) || !["add", "remove"].includes(action)) {
      throw new Error("Invalid request");
    }

    if (action === "add") {
      if (!(await isNseEquity(symbol))) throw new Error("Invalid request");
      const { error } = await client
        .from("watchlist")
        .upsert(
          { symbol, exchange: "NSE", active: true, kind: "equity" },
          { onConflict: "symbol,exchange" },
        );
      if (error) throw new Error("Service unavailable");
      return Response.json({ symbol, active: true });
    }

    const { error } = await client
      .from("watchlist")
      .update({ active: false })
      .eq("symbol", symbol)
      .eq("exchange", "NSE")
      .eq("kind", "equity");
    if (error) throw new Error("Service unavailable");
    return Response.json({ symbol, active: false });
  } catch (error) {
    return failure(error);
  }
}
