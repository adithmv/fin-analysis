"use client";
import { getBrowserClient } from "./supabase";
export async function changeOperation(
  path: string,
  body: Record<string, unknown>,
) {
  const client = getBrowserClient();
  if (!client) throw new Error("Database unavailable");
  const { data } = await client.auth.getSession();
  if (!data.session) throw new Error("Sign in first");
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${data.session.access_token}`,
    },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Change failed");
  if (!result.changed)
    throw new Error("Nothing changed; refresh to see the latest state.");
}
