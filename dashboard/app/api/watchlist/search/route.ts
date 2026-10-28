import { authorizeOwner } from "@/lib/ops-server";
import { searchNseEquities } from "@/lib/nse-equity-catalog";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(request: Request) {
  try {
    await authorizeOwner(request);
    const query = new URL(request.url).searchParams.get("q")?.trim() || "";
    if (query.length < 2 || query.length > 80) {
      return Response.json({ items: [], retrievedAt: null });
    }
    const result = await searchNseEquities(query);
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
            ? "The NSE stock list is temporarily unavailable. Try again shortly."
            : message,
      },
      { status, headers: { "Cache-Control": "private, no-store" } },
    );
  }
}
