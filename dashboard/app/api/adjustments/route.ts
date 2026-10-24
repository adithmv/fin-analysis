import { authorizeOwner, boundedBody, failure } from "@/lib/ops-server";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    const { client, user } = await authorizeOwner(request);
    const body = await boundedBody(request);
    if (
      typeof body.symbol !== "string" ||
      !/^[A-Z0-9&.-]{1,40}$/.test(body.symbol) ||
      typeof body.ex_date !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(body.ex_date) ||
      !["approved", "rejected"].includes(String(body.status)) ||
      typeof body.note !== "string" ||
      body.note.trim().length < 3 ||
      body.note.length > 1000
    )
      throw new Error("Invalid request");
    const { data, error } = await client.rpc("review_adjustment", {
      p_symbol: body.symbol,
      p_exchange: "NSE",
      p_date: body.ex_date,
      p_status: body.status,
      p_note: body.note,
      p_actor: user.id,
    });
    if (error) throw new Error("Invalid request");
    return Response.json({ changed: data });
  } catch (error) {
    return failure(error);
  }
}
