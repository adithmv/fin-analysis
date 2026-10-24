import { authorizeOwner, boundedBody, failure } from "@/lib/ops-server";
export const runtime = "nodejs";
export async function POST(request: Request) {
  try {
    const { client, user } = await authorizeOwner(request);
    const body = await boundedBody(request);
    if (
      !Number.isSafeInteger(body.id) ||
      Number(body.id) < 1 ||
      !["retry", "cancel", "acknowledge", "resolve"].includes(
        String(body.action),
      )
    )
      throw new Error("Invalid request");
    const { data, error } = await client.rpc("owner_ops_action", {
      p_actor: user.id,
      p_action: body.action,
      p_id: body.id,
    });
    if (error) throw new Error("Invalid request");
    return Response.json({ changed: data });
  } catch (error) {
    return failure(error);
  }
}
