"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { LoginRequired, useLogin } from "./auth";

type ProcessId = "alerts" | "news" | "backup";
type ManagedProcess = {
  id: ProcessId;
  label: string;
  schedule: string;
  description: string;
  available: boolean;
  enabled: boolean;
  state: string;
  lastRun: string | null;
  lastResult: number | null;
};

type NewsSource = {
  key: string;
  name: string;
  description: string;
  allowed: boolean;
  enabled: boolean;
  consecutiveFailures: number;
};

type CredentialId =
  | "gemini"
  | "telegramToken"
  | "telegramChatId"
  | "supabaseServiceKey"
  | "supabasePublicKey"
  | "backupDatabaseUrl";

type RoomSettings = {
  newsProcessing: Record<string, boolean>;
  technicalAreas: Record<string, boolean>;
  technicalConfigRevision: number;
  telegramNotifications: boolean;
};

type CredentialStatus = Record<CredentialId, boolean>;

async function controlRoomRequest(
  method: "GET" | "POST",
  body?: Record<string, unknown>,
) {
  const client = getBrowserClient();
  if (!client) throw new Error("Dashboard connection is unavailable.");
  const { data } = await client.auth.getSession();
  if (!data.session) throw new Error("Sign in to manage these settings.");
  const response = await fetch("/api/control-room", {
    method,
    headers: {
      Authorization: "Bearer " + data.session.access_token,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || "The change could not be saved.");
  return result;
}

function lastRunLabel(value: string | null) {
  if (!value) return "No previous run recorded";
  return new Date(value).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
  });
}

function Toggle({
  checked,
  label,
  disabled,
  onClick,
}: {
  checked: boolean;
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={"control-toggle" + (checked ? " is-on" : "")}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
    >
      <span />
    </button>
  );
}

const newsStages = [
  { key: "dedupe", name: "Duplicate detection", description: "Groups repeated headlines so copies do not dominate the news list." },
  { key: "link", name: "Company matching", description: "Links stories to NSE symbols using the reviewed company aliases." },
  { key: "classify", name: "Event classification", description: "Labels company news with configured event types." },
  { key: "sentiment", name: "Sentiment scoring", description: "Scores English titles and snippets with the local FinBERT model." },
  { key: "embed", name: "Similarity search indexing", description: "Builds local text embeddings for linked, nonduplicate stories." },
] as const;

const technicalAreas = [
  { key: "trend", name: "Trend and breakout signals", description: "SMA crossovers and new 20-session highs or lows." },
  { key: "momentum", name: "Momentum signals", description: "RSI threshold crossings and MACD signal-line crossings." },
  { key: "volatility", name: "Volatility signals", description: "Bollinger band crossings." },
  { key: "volume", name: "Volume signals", description: "Unusual volume compared with the 20-session average." },
  { key: "patterns", name: "Candlestick patterns", description: "The configured candlestick pattern detections." },
  { key: "levels", name: "Swing levels", description: "Confirmed swing highs and lows used as support/resistance references." },
] as const;

const credentials: {
  id: CredentialId;
  title: string;
  label: string;
  placeholder: string;
  description: string;
  multiline?: boolean;
}[] = [
  {
    id: "gemini",
    title: "Google AI Studio · Gemini",
    label: "Gemini API key",
    placeholder: "Paste a replacement key",
    description: "Used by evidence-based research discussions. The key stays in this PC’s ignored local settings file.",
  },
  {
    id: "telegramToken",
    title: "Telegram bot",
    label: "Bot token",
    placeholder: "Paste a replacement bot token",
    description: "Used for private alert delivery. The token is never displayed after saving.",
  },
  {
    id: "telegramChatId",
    title: "Telegram private chat",
    label: "Private chat ID",
    placeholder: "Enter the numeric private chat ID",
    description: "The numeric chat identifier for your private bot conversation.",
  },
  {
    id: "supabaseServiceKey",
    title: "Supabase server access",
    label: "Server key",
    placeholder: "Paste a replacement server key",
    description: "The replacement is checked against your signed-in owner account before it is saved.",
  },
  {
    id: "supabasePublicKey",
    title: "Supabase dashboard connection",
    label: "Public anon key",
    placeholder: "Paste a replacement public key",
    description: "This public client key is bundled into the dashboard; after changing it, rebuild and restart the app.",
  },
  {
    id: "backupDatabaseUrl",
    title: "Database backup connection",
    label: "PostgreSQL connection URI",
    placeholder: "postgresql://…",
    description: "Used by database backups. It is stored locally and never shown after saving.",
  },
];

export function ControlRoom() {
  const { ready, loggedIn } = useLogin();
  const [processes, setProcesses] = useState<ManagedProcess[]>([]);
  const [newsSources, setNewsSources] = useState<NewsSource[]>([]);
  const [settings, setSettings] = useState<RoomSettings | null>(null);
  const [credentialStatus, setCredentialStatus] = useState<CredentialStatus | null>(null);
  const [credentialValues, setCredentialValues] = useState<Record<CredentialId, string>>({
    gemini: "",
    telegramToken: "",
    telegramChatId: "",
    supabaseServiceKey: "",
    supabasePublicKey: "",
    backupDatabaseUrl: "",
  });
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await controlRoomRequest("GET");
      setProcesses(result.processes as ManagedProcess[]);
      setNewsSources(result.newsSources as NewsSource[]);
      setSettings(result.settings as RoomSettings);
      setCredentialStatus(result.credentials as CredentialStatus);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (loggedIn) void load();
  }, [loggedIn, load]);

  async function toggleProcess(process: ManagedProcess) {
    setBusy(process.id);
    setError("");
    setNotice("");
    try {
      const result = await controlRoomRequest("POST", {
        action: "set-process",
        processId: process.id,
        enabled: !process.enabled,
      });
      setProcesses((current) =>
        current.map((item) => item.id === process.id ? result.process as ManagedProcess : item),
      );
      setNotice(
        (result.process as ManagedProcess).enabled
          ? process.label + " is on. It will run at its next scheduled time."
          : process.label + " is paused.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function toggleNewsSource(source: NewsSource) {
    const next = !source.enabled;
    setBusy("source:" + source.key);
    setError("");
    setNotice("");
    try {
      await controlRoomRequest("POST", {
        action: "set-news-source",
        sourceKey: source.key,
        enabled: next,
      });
      setNewsSources((current) => current.map((item) => item.key === source.key ? { ...item, enabled: next, consecutiveFailures: next ? 0 : item.consecutiveFailures } : item));
      setNotice(source.name + (next ? " is enabled for the next news collection." : " is paused."));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function toggleFeature(group: string, key: string, enabled: boolean, label: string) {
    setBusy(group + ":" + key);
    setError("");
    setNotice("");
    try {
      const result = await controlRoomRequest("POST", {
        action: "set-feature",
        group,
        key,
        enabled,
      });
      setSettings((current) => {
        if (!current) return current;
        if (group === "news-processing")
          return { ...current, newsProcessing: result.settings as Record<string, boolean> };
        if (group === "technical-area")
          return { ...current, technicalAreas: result.settings as Record<string, boolean> };
        return { ...current, telegramNotifications: Boolean((result.settings as { delivery: boolean }).delivery) };
      });
      setNotice(
        enabled
          ? label + " is on and will apply on the next run."
          : label + " is paused; existing records remain available.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  async function saveCredential(event: FormEvent<HTMLFormElement>, id: CredentialId) {
    event.preventDefault();
    setBusy("credential:" + id);
    setError("");
    setNotice("");
    try {
      const result = await controlRoomRequest("POST", {
        action: "save-credential",
        credentialId: id,
        value: credentialValues[id],
      });
      setCredentialStatus(result.credentials as CredentialStatus);
      setCredentialValues((current) => ({ ...current, [id]: "" }));
      setNotice(id === "supabasePublicKey"
        ? "The public key was saved locally. Rebuild and restart the app to apply it."
        : "The credential was saved locally. Its value is hidden after saving.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }

  if (!ready) return <div className="page">Checking account…</div>;
  if (!loggedIn) return <LoginRequired />;

  return (
    <div className="page control-room-page">
      <div className="eyebrow">WORKSPACE / OWNER CONTROLS</div>
      <div className="control-room-heading">
        <div>
          <h1>Control Room</h1>
          <p className="subtitle">
            Choose which local research, news, alert and technical-analysis features are active.
          </p>
        </div>
        <button disabled={loading || Boolean(busy)} onClick={() => void load()}>
          {loading ? "Refreshing…" : "Refresh status"}
        </button>
      </div>

      {error && <p role="alert" className="error">{error}</p>}
      {notice && <p role="status" className="control-notice">{notice}</p>}

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>Background processes</h2>
            <p>These switches pause or resume the Windows scheduled task itself.</p>
          </div>
          <span className="control-local-badge">THIS PC</span>
        </div>
        {loading && processes.length === 0 ? (
          <div className="panel control-empty">Reading Task Scheduler…</div>
        ) : (
          <div className="control-grid">
            {processes.map((process) => (
              <section className="panel control-card" key={process.id}>
                <div className="control-card-heading">
                  <div>
                    <h3>{process.label}</h3>
                    <span className="control-schedule">{process.schedule}</span>
                  </div>
                  <Toggle
                    checked={process.enabled}
                    label={(process.enabled ? "Pause " : "Resume ") + process.label}
                    disabled={!process.available || loading || Boolean(busy)}
                    onClick={() => void toggleProcess(process)}
                  />
                </div>
                <p>{process.description}</p>
                <div className="control-state-line">
                  <span className={"control-state-dot" + (process.enabled ? " is-on" : "")} />
                  <strong>
                    {!process.available ? "Not installed" : process.enabled ? process.state === "Running" ? "Running" : "On" : "Paused"}
                  </strong>
                </div>
                {process.available && (
                  <div className="control-run-detail">
                    <span>Last run: {lastRunLabel(process.lastRun)}</span>
                    {process.lastResult !== null && <span>Last result: {process.lastResult === 0 ? "Succeeded" : "Code " + process.lastResult}</span>}
                  </div>
                )}
              </section>
            ))}
            {processes.length === 0 && !loading && <div className="panel control-empty">No managed scheduled tasks were found.</div>}
          </div>
        )}
        <p className="control-footnote">Price collection and the main research pipeline remain unavailable until a permitted market-data source and schedule are commissioned.</p>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>News sources</h2>
            <p>Each approved RSS feed can be paused on its own. Restricted or unreviewed feeds stay locked.</p>
          </div>
          <span className="control-local-badge">FEED BY FEED</span>
        </div>
        <div className="control-grid">
          {newsSources.map((source) => (
            <section className={"panel control-card" + (!source.allowed ? " is-locked" : "")} key={source.key}>
              <div className="control-card-heading">
                <div>
                  <h3>{source.name}</h3>
                  <span className="control-schedule">{source.allowed ? "Personal RSS source" : "Locked pending review"}</span>
                </div>
                <Toggle
                  checked={source.enabled}
                  label={(source.enabled ? "Pause " : "Enable ") + source.name}
                  disabled={!source.allowed || loading || Boolean(busy)}
                  onClick={() => void toggleNewsSource(source)}
                />
              </div>
              <p>{source.description}</p>
              <div className="control-state-line">
                <span className={"control-state-dot" + (source.enabled ? " is-on" : "")} />
                <strong>{source.allowed ? source.enabled ? "On" : "Paused" : "Unavailable"}</strong>
                {source.consecutiveFailures > 0 && <span className="control-failure-count">{source.consecutiveFailures} recent failures</span>}
              </div>
            </section>
          ))}
          {newsSources.length === 0 && <div className="panel control-empty">{loading ? "Loading feed status…" : "Feed status is unavailable."}</div>}
        </div>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>News processing</h2>
            <p>Control the individual steps applied to collected headlines. Pausing a step keeps existing analysis.</p>
          </div>
          <span className="control-local-badge">PER STEP</span>
        </div>
        <div className="control-grid">
          {newsStages.map((feature) => {
            const checked = settings?.newsProcessing[feature.key] ?? true;
            const id = "news-processing:" + feature.key;
            return (
              <section className="panel control-card" key={feature.key}>
                <div className="control-card-heading">
                  <h3>{feature.name}</h3>
                  <Toggle checked={checked} label={(checked ? "Pause " : "Enable ") + feature.name} disabled={!settings || Boolean(busy)} onClick={() => void toggleFeature("news-processing", feature.key, !checked, feature.name)} />
                </div>
                <p>{feature.description}</p>
                <div className="control-state-line"><span className={"control-state-dot" + (checked ? " is-on" : "")} /><strong>{busy === id ? "Saving…" : checked ? "On" : "Paused"}</strong></div>
              </section>
            );
          })}
        </div>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>Technical signal areas</h2>
            <p>These switches affect generated signal markers. Chart indicator values and data-quality checks stay available.</p>
          </div>
          <span className="control-local-badge">NEXT SIGNAL RUN</span>
        </div>
        <div className="control-grid">
          {technicalAreas.map((feature) => {
            const checked = settings?.technicalAreas[feature.key] ?? true;
            const id = "technical-area:" + feature.key;
            return (
              <section className="panel control-card" key={feature.key}>
                <div className="control-card-heading">
                  <h3>{feature.name}</h3>
                  <Toggle checked={checked} label={(checked ? "Pause " : "Enable ") + feature.name} disabled={!settings || Boolean(busy)} onClick={() => void toggleFeature("technical-area", feature.key, !checked, feature.name)} />
                </div>
                <p>{feature.description}</p>
                <div className="control-state-line"><span className={"control-state-dot" + (checked ? " is-on" : "")} /><strong>{busy === id ? "Saving…" : checked ? "On" : "Paused"}</strong></div>
              </section>
            );
          })}
        </div>
        <p className="control-footnote">A technical-area change refreshes signal history the next time signal calculations run; it does not fetch new prices.</p>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>Alert delivery</h2>
            <p>Health checks can keep running while Telegram messages are paused.</p>
          </div>
          <span className="control-local-badge">TELEGRAM</span>
        </div>
        <section className="panel control-card control-single-card">
          <div className="control-card-heading">
            <div><h3>Private Telegram notifications</h3><span className="control-schedule">Critical alerts bypass quiet hours when enabled</span></div>
            <Toggle checked={settings?.telegramNotifications ?? true} label={(settings?.telegramNotifications ? "Pause" : "Enable") + " Telegram notifications"} disabled={!settings || Boolean(busy)} onClick={() => void toggleFeature("telegram-notifications", "delivery", !settings?.telegramNotifications, "Telegram notifications")} />
          </div>
          <p>When paused, incidents remain in the dashboard and alert log. No alert or daily digest messages are sent.</p>
          <div className="control-state-line"><span className={"control-state-dot" + (settings?.telegramNotifications ? " is-on" : "")} /><strong>{settings?.telegramNotifications ? "On" : "Paused"}</strong></div>
        </section>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>API keys and connections</h2>
            <p>Enter a replacement value to change a saved credential. Saved values are never shown in the dashboard.</p>
          </div>
          <span className="control-local-badge">LOCAL ONLY</span>
        </div>
        <div className="control-grid">
          {credentials.map((credential) => {
            const saved = credentialStatus?.[credential.id] ?? false;
            return (
              <section className="panel control-key-panel" key={credential.id}>
                <div className="control-key-heading">
                  <div><h3>{credential.title}</h3><p>{credential.description}</p></div>
                  <span className={"control-key-status" + (saved ? " is-ready" : "")}>{saved ? "SAVED" : "NOT SET"}</span>
                </div>
                <form onSubmit={(event) => void saveCredential(event, credential.id)} className="control-key-form">
                  <label className="search-label" htmlFor={"credential-" + credential.id}>
                    {saved ? "Replacement " : ""}{credential.label}
                    <input
                      id={"credential-" + credential.id}
                      type="password"
                      autoComplete="new-password"
                      autoCapitalize="none"
                      spellCheck={false}
                      required
                      maxLength={3072}
                      value={credentialValues[credential.id]}
                      onChange={(event) => setCredentialValues((current) => ({ ...current, [credential.id]: event.target.value }))}
                      placeholder={saved ? "Enter a new value to replace the saved one" : credential.placeholder}
                    />
                  </label>
                  <button disabled={!credentialValues[credential.id].trim() || Boolean(busy)}>
                    {busy === "credential:" + credential.id ? "Checking and saving…" : "Save"}
                  </button>
                </form>
              </section>
            );
          })}
        </div>
        <p className="control-footnote">Google Drive backup uses the configured Google Drive Desktop sync folder; it does not need a separate Drive API key. All secret credentials stay in local ignored environment files, not Supabase.</p>
      </section>
    </div>
  );
}
