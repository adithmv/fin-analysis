import "server-only";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { execFile } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { parseEnv, promisify } from "node:util";
import { resolve } from "node:path";

const execFileAsync = promisify(execFile);
const projectRoot = resolve(process.cwd(), "..");
const envPath = resolve(projectRoot, ".env");
const dashboardEnvPath = resolve(projectRoot, "dashboard", ".env.local");
const controlDirectory = resolve(projectRoot, ".cache", "control-room");
const controlSettingsPath = resolve(controlDirectory, "settings.json");
const taskControlPath = resolve(projectRoot, "ops", "control-room.ps1");
const processIds = new Set(["alerts", "news", "backup"]);

const approvedNewsSources = {
  livemint_markets: {
    name: "Livemint",
    description: "Personal RSS reading; titles and feed snippets only.",
  },
  economic_times_markets: {
    name: "Economic Times",
    description: "Personal RSS reading; titles and feed snippets only.",
  },
} as const;

const lockedNewsSources = [
  {
    key: "moneycontrol_markets",
    name: "Moneycontrol",
    description: "Paused because the feed is stale.",
  },
  {
    key: "business_standard_markets",
    name: "Business Standard",
    description: "Requires written permission for automated collection and AI use.",
  },
  {
    key: "thehindu_markets",
    name: "The Hindu",
    description: "Source access review is pending.",
  },
  {
    key: "nse_announcements",
    name: "NSE announcements",
    description: "Automated access requires permission or a licensed source.",
  },
  {
    key: "bse_announcements",
    name: "BSE announcements",
    description: "Automated source access review is pending.",
  },
] as const;

const newsProcessingDefaults = {
  dedupe: true,
  link: true,
  classify: true,
  sentiment: true,
  embed: true,
};

const technicalAreaDefaults = {
  trend: true,
  momentum: true,
  volatility: true,
  volume: true,
  patterns: true,
  levels: true,
};

type ControlSettings = {
  newsSources: Record<keyof typeof approvedNewsSources, boolean>;
  newsProcessing: typeof newsProcessingDefaults;
  technicalAreas: typeof technicalAreaDefaults;
  technicalConfigRevision: number;
  telegramNotifications: boolean;
};

const controlDefaults: ControlSettings = {
  newsSources: { livemint_markets: true, economic_times_markets: true },
  newsProcessing: { ...newsProcessingDefaults },
  technicalAreas: { ...technicalAreaDefaults },
  technicalConfigRevision: 0,
  telegramNotifications: true,
};

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

function readEnvFile(path: string): Record<string, string | undefined> {
  try {
    return parseEnv(readFileSync(path, "utf8"));
  } catch {
    return {};
  }
}

function isBooleanRecord<T extends Record<string, boolean>>(
  input: unknown,
  defaults: T,
): T {
  const source = input && typeof input === "object" ? input as Record<string, unknown> : {};
  return Object.fromEntries(
    Object.entries(defaults).map(([key, fallback]) => [
      key,
      typeof source[key] === "boolean" ? source[key] : fallback,
    ]),
  ) as T;
}

export function getControlSettings(): ControlSettings {
  let saved: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(readFileSync(controlSettingsPath, "utf8"));
    if (parsed && typeof parsed === "object") saved = parsed as Record<string, unknown>;
  } catch {
    // The first run uses the reviewed, conservative defaults below.
  }
  return {
    newsSources: isBooleanRecord(saved.newsSources, controlDefaults.newsSources),
    newsProcessing: isBooleanRecord(saved.newsProcessing, newsProcessingDefaults),
    technicalAreas: isBooleanRecord(saved.technicalAreas, technicalAreaDefaults),
    technicalConfigRevision:
      Number.isSafeInteger(saved.technicalConfigRevision) &&
      Number(saved.technicalConfigRevision) >= 0
        ? Number(saved.technicalConfigRevision)
        : 0,
    telegramNotifications:
      typeof saved.telegramNotifications === "boolean"
        ? saved.telegramNotifications
        : true,
  };
}

function saveControlSettings(settings: ControlSettings) {
  mkdirSync(controlDirectory, { recursive: true });
  const temporary = resolve(controlDirectory, "settings.tmp");
  writeFileSync(temporary, JSON.stringify(settings, null, 2) + "\n", {
    encoding: "utf8",
    mode: 0o600,
  });
  renameSync(temporary, controlSettingsPath);
}

function updateControlSettings(
  update: (current: ControlSettings) => ControlSettings,
) {
  const next = update(getControlSettings());
  saveControlSettings(next);
  return next;
}

async function runTaskControl(
  operation: "status" | "enable" | "disable",
  processId?: string,
) {
  if (process.platform !== "win32")
    throw new Error("Task controls are available on the Windows app.");
  const powershell = process.env.SystemRoot
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
  const output = await runTaskControl(enabled ? "enable" : "disable", processId);
  return JSON.parse(output) as ManagedProcess;
}

export async function getNewsSourceControls(client: SupabaseClient) {
  const keys = Object.keys(approvedNewsSources);
  const { data, error } = await client
    .from("news_sources")
    .select("source_key,enabled,consecutive_failures")
    .in("source_key", keys);
  if (error) throw new Error("Could not read news-source status.");
  const database = new Map((data ?? []).map((row) => [row.source_key, row]));
  const settings = getControlSettings();
  return [
    ...Object.entries(approvedNewsSources).map(([key, source]) => {
      const row = database.get(key);
      return {
        key,
        name: source.name,
        description: source.description,
        allowed: true,
        enabled: row ? Boolean(row.enabled) : settings.newsSources[key as keyof typeof approvedNewsSources],
        consecutiveFailures: row?.consecutive_failures ?? 0,
      };
    }),
    ...lockedNewsSources.map((source) => ({
      ...source,
      allowed: false,
      enabled: false,
      consecutiveFailures: 0,
    })),
  ];
}

export async function setNewsSource(
  client: SupabaseClient,
  key: string,
  enabled: boolean,
) {
  if (!Object.hasOwn(approvedNewsSources, key))
    throw new Error("This news source is not approved for automated collection.");
  const update: Record<string, unknown> = { enabled };
  if (enabled) update.consecutive_failures = 0;
  const { error } = await client.from("news_sources").update(update).eq("source_key", key);
  if (error) throw new Error("Could not update the news-source setting.");
  updateControlSettings((current) => ({
    ...current,
    newsSources: { ...current.newsSources, [key]: enabled },
  }));
  return { key, enabled };
}

export function setControlFeature(
  group: string,
  key: string,
  enabled: boolean,
) {
  if (group === "news-processing" && Object.hasOwn(newsProcessingDefaults, key)) {
    const settings = updateControlSettings((current) => ({
      ...current,
      newsProcessing: { ...current.newsProcessing, [key]: enabled },
    }));
    return settings.newsProcessing;
  }
  if (group === "technical-area" && Object.hasOwn(technicalAreaDefaults, key)) {
    const settings = updateControlSettings((current) => {
      if (current.technicalAreas[key as keyof typeof technicalAreaDefaults] === enabled)
        return current;
      return {
        ...current,
        technicalAreas: { ...current.technicalAreas, [key]: enabled },
        technicalConfigRevision: current.technicalConfigRevision + 1,
      };
    });
    return settings.technicalAreas;
  }
  if (group === "telegram-notifications" && key === "delivery") {
    const settings = updateControlSettings((current) => ({
      ...current,
      telegramNotifications: enabled,
    }));
    return { delivery: settings.telegramNotifications };
  }
  throw new Error("Select a supported feature.");
}

function configured(name: string, path: string) {
  const local = readEnvFile(path);
  return Boolean(process.env[name]?.trim() || local[name]?.trim());
}

export function getCredentialStatus() {
  return {
    gemini: configured("GEMINI_API_KEY", envPath),
    telegramToken: configured("TELEGRAM_BOT_TOKEN", envPath),
    telegramChatId: configured("TELEGRAM_CHAT_ID", envPath),
    supabaseServiceKey: configured("SUPABASE_SERVICE_KEY", envPath),
    supabasePublicKey: configured("NEXT_PUBLIC_SUPABASE_ANON_KEY", dashboardEnvPath),
    backupDatabaseUrl: configured("DATABASE_URL", envPath),
  };
}

const credentialTargets = {
  gemini: { name: "GEMINI_API_KEY", path: envPath },
  telegramToken: { name: "TELEGRAM_BOT_TOKEN", path: envPath },
  telegramChatId: { name: "TELEGRAM_CHAT_ID", path: envPath },
  supabaseServiceKey: { name: "SUPABASE_SERVICE_KEY", path: envPath },
  supabasePublicKey: { name: "NEXT_PUBLIC_SUPABASE_ANON_KEY", path: dashboardEnvPath },
  backupDatabaseUrl: { name: "DATABASE_URL", path: envPath },
} as const;

type CredentialId = keyof typeof credentialTargets;

function validateCredential(id: CredentialId, value: string) {
  const clean = value.trim();
  if (!clean || clean.length > 3072 || /[\u0000-\u001f\u007f]/.test(clean))
    throw new Error("Enter a valid value.");
  if (id === "telegramToken" && !/^\d+:[A-Za-z0-9_-]+$/.test(clean))
    throw new Error("Enter a valid Telegram bot token.");
  if (id === "telegramChatId" && !/^-?\d+$/.test(clean))
    throw new Error("Enter the numeric ID for your private Telegram chat.");
  if (id === "backupDatabaseUrl") {
    try {
      const parsed = new URL(clean);
      if (!/^postgres(?:ql)?:$/.test(parsed.protocol) || !parsed.hostname || !parsed.username)
        throw new Error();
    } catch {
      throw new Error("Enter a PostgreSQL connection URI with a host and username.");
    }
  }
  return clean;
}

async function validateSupabaseKey(key: string, accessToken: string, ownerAccess: boolean) {
  const rootEnv = readEnvFile(envPath);
  const dashboardEnv = readEnvFile(dashboardEnvPath);
  const url = process.env.SUPABASE_URL || rootEnv.SUPABASE_URL || dashboardEnv.NEXT_PUBLIC_SUPABASE_URL;
  if (!url) throw new Error("Supabase project URL is not configured locally.");
  const candidate = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await candidate.auth.getUser(accessToken);
  if (error || !data.user) throw new Error("That Supabase key could not verify your signed-in account.");
  if (ownerAccess) {
    const owner = await candidate.rpc("is_research_owner", { p_user: data.user.id });
    if (owner.error || owner.data !== true)
      throw new Error("That Supabase key does not have owner access to this project.");
  }
}

export async function saveCredential(
  id: string,
  rawValue: string,
  accessToken: string,
) {
  if (!Object.hasOwn(credentialTargets, id)) throw new Error("Select a supported credential.");
  const credentialId = id as CredentialId;
  const value = validateCredential(credentialId, rawValue);
  if (credentialId === "supabaseServiceKey" || credentialId === "supabasePublicKey")
    await validateSupabaseKey(value, accessToken, credentialId === "supabaseServiceKey");

  const target = credentialTargets[credentialId];
  const previous = existsSync(target.path) ? readFileSync(target.path, "utf8") : "";
  const newline = previous.includes("\r\n") ? "\r\n" : "\n";
  const lines = previous
    ? previous.split(/\r?\n/).filter((line) => !new RegExp(`^\\s*(?:export\\s+)?${target.name}\\s*=`).test(line))
    : [];
  const envValue = /^[A-Za-z0-9._=-]+$/.test(value) ? value : JSON.stringify(value);
  const updated = [...lines, `${target.name}=${envValue}`].join(newline) + newline;
  mkdirSync(resolve(target.path, ".."), { recursive: true });
  const temporary = resolve(target.path + ".control-room.tmp");
  writeFileSync(temporary, updated, { encoding: "utf8", mode: 0o600 });
  renameSync(temporary, target.path);

  if (credentialId === "gemini") process.env.GEMINI_API_KEY = value;
  if (credentialId === "telegramToken") process.env.TELEGRAM_BOT_TOKEN = value;
  if (credentialId === "telegramChatId") process.env.TELEGRAM_CHAT_ID = value;
  if (credentialId === "supabaseServiceKey") process.env.SUPABASE_SERVICE_KEY = value;
  return { configured: true };
}

export function getClientSettings() {
  const settings = getControlSettings();
  return {
    newsProcessing: settings.newsProcessing,
    technicalAreas: settings.technicalAreas,
    technicalConfigRevision: settings.technicalConfigRevision,
    telegramNotifications: settings.telegramNotifications,
  };
}
