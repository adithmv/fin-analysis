"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getBrowserClient } from "@/lib/supabase";
export function useLogin() {
  const [loggedIn, S] = useState(false),
    [ready, R] = useState(false);
  useEffect(() => {
    const c = getBrowserClient();
    if (!c) {
      R(true);
      return;
    }
    let active = true;
    void c.auth.getUser().then(({ data }) => {
      if (active) {
        S(Boolean(data.user));
        R(true);
      }
    });
    const { data } = c.auth.onAuthStateChange((_e, session) => {
      S(Boolean(session?.user));
      R(true);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);
  return { loggedIn, ready };
}
export function LoginLink() {
  const { loggedIn } = useLogin();
  return (
    <Link className="readonly" href="/login">
      {loggedIn ? "Account · signed in" : "Sign in for discussions"}
    </Link>
  );
}
export function Login() {
  const { loggedIn, ready } = useLogin();
  const [email, E] = useState(""),
    [password, P] = useState(""),
    [error, F] = useState(""),
    [busy, B] = useState(false);
  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    B(true);
    F("");
    try {
      const c = getBrowserClient();
      if (!c) throw new Error("Database connection unavailable");
      const { error } = await c.auth.signInWithPassword({ email, password });
      if (error) throw error;
      P("");
    } catch {
      F("Sign-in failed. Check the configured email and password.");
    } finally {
      B(false);
    }
  }
  return (
    <div className="page">
      <div className="eyebrow">YOUR RESEARCH ACCOUNT</div>
      <h1>{loggedIn ? "You’re signed in" : "Sign in"}</h1>
      <p className="subtitle">
        Discussions and questions are private to the configured account. Market
        data remains read-only.
      </p>
      <section className="panel news-section" style={{ maxWidth: 540 }}>
        {!ready ? (
          <p>Checking account…</p>
        ) : loggedIn ? (
          <>
            <Link className="small-link" href="/threads">
              Open discussions →
            </Link>
            <p>
              <button onClick={() => void getBrowserClient()?.auth.signOut()}>
                Sign out
              </button>
            </p>
          </>
        ) : (
          <form onSubmit={signIn}>
            <label className="search-label">
              Email
              <input
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => E(e.target.value)}
              />
            </label>
            <label className="search-label">
              Password
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => P(e.target.value)}
              />
            </label>
            <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
            <p className="attribution">
              Use the account configured for this workspace.
            </p>
          </form>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
export function LoginRequired() {
  return (
    <div className="page">
      <h1>Sign in to continue</h1>
      <p>
        Discussions, questions and model usage are private to your research
        account.
      </p>
      <Link className="small-link" href="/login">
        Sign in →
      </Link>
    </div>
  );
}
