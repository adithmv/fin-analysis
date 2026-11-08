import "server-only";
import { execFile } from "node:child_process";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { parseEnv, promisify } from "node:util";
import { resolve } from "node:path";

const execFileAsync = promisify(execFile);
const projectRoot = resolve(process.cwd(), "..");
const envPath = resolve(projectRoot, ".env");
const taskControlPath = resolve(projectRoot, "ops", "control-room.ps1");
const processIds = new Set(["alerts", "news", "backup"]);

export type ManagedProcess = {
  id: "alerts" | "news" | "backup";
  label: string;
  schedule: string;
  description: string;
  available: boolean;
  enabled: boolean;
  state: string;
  lastRun: string | null;
  lastResult: number | null;
};

async function runTaskControl(
  operation: "status" | "enable" | "disable",
  processId?: string,
) {
  if (process.platform !== "win32")
    throw new Error("Task controls are available on the Windows app.");
  const powershell =
    process.env.SystemRoot
      ? resolve(process.env.SystemRoot, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
      : "powershell.exe";
  const args = [
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy",
    "RemoteSigned",
    "-File",
    taskControlPath,
    "-Operation",
    operation,
  ];
  if (processId) args.push("-ProcessName", processId);
  const { stdout } = await execFileAsync(powershell, args, {
    cwd: projectRoot,
    windowsHide: true,
    timeout: 15000,
    maxBuffer: 16 * 1024,
  });
  return stdout.trim();
}

export async function getManagedProcesses(): Promise<ManagedProcess[]> {
  const output = await runTaskControl("status");
  const value: unknown = JSON.parse(output);
  if (!Array.isArray(value)) throw new Error("Invalid task status response.");
  return value as ManagedProcess[];
}

export async function setManagedProcess(
  processId: string,
  enabled: boolean,
): Promise<ManagedProcess> {
  if (!processIds.has(processId)) throw new Error("Select a supported process.");
  const output = await runTaskControl(
    enabled ? "enable" : "disable",
    processId,
  );
  return JSON.parse(output) as ManagedProcess;
}

export function hasGeminiApiKey() {
  const fileValues = existsSync(envPath)
    ? parseEnv(readFileSync(envPath, "utf8"))
    : {};
  return Boolean(
    process.env.GEMINI_API_KEY?.trim() || fileValues.GEMINI_API_KEY?.trim(),
  );
}

export function saveGeminiApiKey(value: string) {
  const key = value.trim();
  if (!key || key.length > 2048 || /[\u0000-\u001f\u007f]/.test(key))
    throw new Error("Enter a valid API key.");

  const previous = existsSync(envPath) ? readFileSync(envPath, "utf8") : "";
  const newline = previous.includes("\r\n") ? "\r\n" : "\n";
  const lines = previous
    ? previous.split(/\r?\n/).filter((line) => !/^\s*(?:export\s+)?GEMINI_API_KEY\s*=/.test(line))
    : [];
  const envValue = /^[A-Za-z0-9._=-]+$/.test(key)
    ? key
    : JSON.stringify(key);
  const updated = [...lines, "GEMINI_API_KEY=" + envValue].join(newline) + newline;
  const temporary = resolve(projectRoot, ".env.control-room.tmp");
  writeFileSync(temporary, updated, { encoding: "utf8", mode: 0o600 });
  renameSync(temporary, envPath);
  process.env.GEMINI_API_KEY = key;
}
