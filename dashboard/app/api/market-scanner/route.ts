import { authorizeOwner } from "@/lib/ops-server";
import { scanNseMarket } from "@/lib/nse-market";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  try {
    await authorizeOwner(request);
    const url = new URL(request.url);
    const includeSme = url.searchParams.get("includeSme") === "true";
    const minTurnoverCr = Number(url.searchParams.get("minTurnoverCr") || "1");
    if (![0, 0.5, 1, 5, 10].includes(minTurnoverCr)) {
      return Response.json({ error: "Choose a supported liquidity filter." }, { status: 400 });
    }
    const result = await scanNseMarket({ includeSme, minTurnoverCr });
    return Response.json(result, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    const status =
      message === "Unauthorized" ? 401 : message === "Forbidden" ? 403 : 503;
    return Response.json(
      {
        error:
          status === 503
            ? "NSE market data is temporarily unavailable. Try refreshing in a few minutes."
            : message,
      },
      { status, headers: { "Cache-Control": "private, no-store" } },
    );
  }
}
