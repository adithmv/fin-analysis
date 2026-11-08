import {
  getClientSettings,
  getCredentialStatus,
  getManagedProcesses,
  getNewsSourceControls,
  saveCredential,
  setControlFeature,
  setManagedProcess,
  setNewsSource,
} from "@/lib/control-room-server";
import { authorizeOwner, boundedBody, failure } from "@/lib/ops-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { client } = await authorizeOwner(request);
    const [processes, newsSources] = await Promise.all([
      getManagedProcesses(),
      getNewsSourceControls(client),
    ]);
    return Response.json({
      processes,
      newsSources,
      settings: getClientSettings(),
      credentials: getCredentialStatus(),
    });
  } catch (error) {
    return failure(error);
  }
}

export async function POST(request: Request) {
  try {
    const { client } = await authorizeOwner(request);
    const body = await boundedBody(request);
    if (body.action === "set-process") {
      if (typeof body.processId !== "string" || typeof body.enabled !== "boolean")
        throw new Error("Invalid request");
      const process = await setManagedProcess(body.processId, body.enabled);
      return Response.json({ changed: true, process });
    }
    if (body.action === "set-news-source") {
      if (typeof body.sourceKey !== "string" || typeof body.enabled !== "boolean")
        throw new Error("Invalid request");
      const source = await setNewsSource(client, body.sourceKey, body.enabled);
      return Response.json({ changed: true, source });
    }
    if (body.action === "set-feature") {
      if (
        typeof body.group !== "string" ||
        typeof body.key !== "string" ||
        typeof body.enabled !== "boolean"
      )
        throw new Error("Invalid request");
      const settings = setControlFeature(body.group, body.key, body.enabled);
      return Response.json({ changed: true, settings });
    }
    if (body.action === "save-credential") {
      if (typeof body.credentialId !== "string" || typeof body.value !== "string")
        throw new Error("Invalid request");
      const bearer = request.headers.get("authorization")?.slice(7) ?? "";
      await saveCredential(body.credentialId, body.value, bearer);
      return Response.json({ changed: true, credentials: getCredentialStatus() });
    }
    throw new Error("Invalid request");
  } catch (error) {
    return failure(error);
  }
}
