import "server-only";
import { createClient } from "@supabase/supabase-js";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

export async function authorizeOwner(request: Request) {
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin)
    throw new Error("Forbidden");
  const bearer = request.headers.get("authorization");
  if (!bearer?.startsWith("Bearer ")) throw new Error("Unauthorized");
  // This module is server-only. Local configuration never becomes component props.
  let local: Record<string, string | undefined> = {};
  try {
    local = parseEnv(readFileSync(resolve(process.cwd(), "../.env"), "utf8"));
  } catch {}
  const url = process.env.SUPABASE_URL || local.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY || local.SUPABASE_SERVICE_KEY;
  if (!url || !key) throw new Error("Service unavailable");
  const client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await client.auth.getUser(bearer.slice(7));
  if (error || !data.user) throw new Error("Unauthorized");
  const owner = await client.rpc("is_research_owner", { p_user: data.user.id });
  if (owner.error || owner.data !== true) throw new Error("Forbidden");
  return { client, user: data.user };
}

export async function boundedBody(request: Request) {
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    throw new Error("Invalid request");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("Invalid request");
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > 4096) {
      await reader.cancel();
      throw new Error("Invalid request");
    }
    chunks.push(value);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<
    string,
    unknown
  >;
}

export function failure(error: unknown) {
  const message = error instanceof Error ? error.message : "Invalid request";
  const status =
    message === "Unauthorized"
      ? 401
      : message === "Forbidden"
        ? 403
        : message === "Service unavailable"
          ? 503
          : 400;
  return Response.json(
    {
      error:
        status === 400
          ? "Request could not be completed. Check the values and current state."
          : message,
    },
    { status },
  );
}
