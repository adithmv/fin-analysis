export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const mode = incoming.searchParams.get("mode");
  const id = incoming.searchParams.get("id");
  if (mode === "similar" && !/^[0-9a-f-]{36}$/i.test(id || ""))
    return Response.json({ error: "Invalid article ID" }, { status: 400 });
  const url = new URL(
    mode === "similar"
      ? `http://127.0.0.1:8766/similar/${id}`
      : "http://127.0.0.1:8766/search",
  );
  for (const key of ["q", "symbol", "start", "end", "event"]) {
    const value = incoming.searchParams.get(key);
    if (value) url.searchParams.set(key, value);
  }
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok)
      return Response.json(
        {
          error:
            "Local memory could not complete this request. Check the news logbook and model setup.",
        },
        { status: 503 },
      );
    return Response.json(await response.json());
  } catch {
    return Response.json(
      {
        error:
          "Local memory is offline. Start the news memory service on this computer to search.",
      },
      { status: 503 },
    );
  }
}
