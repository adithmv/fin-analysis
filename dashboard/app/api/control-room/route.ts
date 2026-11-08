import {
  getManagedProcesses,
  hasGeminiApiKey,
  setManagedProcess,
  saveGeminiApiKey,
} from "@/lib/control-room-server";
import { authorizeOwner, boundedBody, failure } from "@/lib/ops-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    await authorizeOwner(request);
    const processes = await getManagedProcesses();
    return Response.json({
      processes,
      geminiApiKeyConfigured: hasGeminiApiKey(),
    });
  } catch (error) {
    return failure(error);
  }
}

export async function POST(request: Request) {
  try {
    await authorizeOwner(request);
    const body = await boundedBody(request);
    if (body.action === "set-process") {
      if (
        typeof body.processId !== "string" ||
        typeof body.enabled !== "boolean"
      )
        throw new Error("Invalid request");
      const process = await setManagedProcess(body.processId, body.enabled);
      return Response.json({ changed: true, process });
    }
    if (body.action === "save-gemini-key") {
      if (typeof body.apiKey !== "string") throw new Error("Invalid request");
      saveGeminiApiKey(body.apiKey);
      return Response.json({ changed: true, geminiApiKeyConfigured: true });
    }
    throw new Error("Invalid request");
  } catch (error) {
    return failure(error);
  }
}
