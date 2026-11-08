"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getBrowserClient } from "@/lib/supabase";
import { LoginRequired, useLogin } from "./auth";

type ManagedProcess = {
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

export function ControlRoom() {
  const { ready, loggedIn } = useLogin();
  const [processes, setProcesses] = useState<ManagedProcess[]>([]);
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [apiKey, setApiKey] = useState("");
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
      setKeyConfigured(Boolean(result.geminiApiKeyConfigured));
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
        current.map((item) =>
          item.id === process.id ? (result.process as ManagedProcess) : item,
        ),
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

  async function saveApiKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("gemini-key");
    setError("");
    setNotice("");
    try {
      await controlRoomRequest("POST", {
        action: "save-gemini-key",
        apiKey,
      });
      setApiKey("");
      setKeyConfigured(true);
      setNotice("The Google AI Studio key was saved on this PC.");
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
            Pause or resume the background tasks on this PC and update the AI
            research key.
          </p>
        </div>
        <button disabled={loading || Boolean(busy)} onClick={() => void load()}>
          {loading ? "Refreshing…" : "Refresh status"}
        </button>
      </div>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="control-notice">
          {notice}
        </p>
      )}

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>Background processes</h2>
            <p>
              On lets the task run on its normal schedule. Off pauses future
              scheduled runs.
            </p>
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
                  <button
                    type="button"
                    className={
                      "control-toggle" + (process.enabled ? " is-on" : "")
                    }
                    role="switch"
                    aria-checked={process.enabled}
                    aria-label={
                      (process.enabled ? "Pause " : "Resume ") + process.label
                    }
                    disabled={
                      !process.available || loading || Boolean(busy)
                    }
                    onClick={() => void toggleProcess(process)}
                  >
                    <span />
                  </button>
                </div>
                <p>{process.description}</p>
                <div className="control-state-line">
                  <span
                    className={
                      "control-state-dot" +
                      (process.enabled ? " is-on" : "")
                    }
                  />
                  <strong>
                    {!process.available
                      ? "Not installed"
                      : process.enabled
                        ? process.state === "Running"
                          ? "Running"
                          : "On"
                        : "Paused"}
                  </strong>
                </div>
                {process.available && (
                  <div className="control-run-detail">
                    <span>Last run: {lastRunLabel(process.lastRun)}</span>
                    {process.lastResult !== null && (
                      <span>
                        Last result:{" "}
                        {process.lastResult === 0
                          ? "Succeeded"
                          : "Code " + process.lastResult}
                      </span>
                    )}
                  </div>
                )}
              </section>
            ))}
            {processes.length === 0 && !loading && (
              <div className="panel control-empty">
                No managed scheduled tasks were found.
              </div>
            )}
          </div>
        )}
        <p className="control-footnote">
          Price collection and the main research pipeline remain unavailable
          until a permitted market data source and their schedules are
          commissioned.
        </p>
      </section>

      <section className="control-section">
        <div className="control-section-heading">
          <div>
            <h2>Google AI Studio key</h2>
            <p>Used by the Gemini research provider.</p>
          </div>
          <span
            className={
              "control-key-status" + (keyConfigured ? " is-ready" : "")
            }
          >
            {keyConfigured ? "KEY SAVED" : "NOT SET"}
          </span>
        </div>
        <div className="panel control-key-panel">
          <p>
            {keyConfigured
              ? "A key is saved. It is never shown here; paste a replacement below to change it."
              : "Paste your Google AI Studio API key below to enable Gemini research."}
          </p>
          <form onSubmit={saveApiKey} className="control-key-form">
            <label className="search-label" htmlFor="gemini-api-key">
              {keyConfigured ? "Replacement API key" : "API key"}
              <input
                id="gemini-api-key"
                type="password"
                autoComplete="new-password"
                autoCapitalize="none"
                spellCheck={false}
                required
                maxLength={2048}
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                placeholder={
                  keyConfigured
                    ? "Enter a new key to replace the saved one"
                    : "Paste the full key"
                }
              />
            </label>
            <button disabled={!apiKey.trim() || busy !== ""}>
              {busy === "gemini-key" ? "Saving…" : "Save key"}
            </button>
          </form>
          <p className="control-footnote">
            The key is stored only in this PC’s ignored local environment file.
            It is not returned to the browser or saved in Supabase. New research
            runs will use it after the process loads the updated settings.
          </p>
        </div>
      </section>
    </div>
  );
}
