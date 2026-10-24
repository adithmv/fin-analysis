import type { Metadata } from "next";
import Link from "next/link";
import { LoginLink } from "@/components/auth";
import { CriticalAlerts } from "@/components/operations";
import "./globals.css";

export const metadata: Metadata = {
  title: "Market Research | NSE",
  description: "Personal Indian market research logbook",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <aside className="sidebar">
          <Link href="/" className="brand">
            <span className="brand-mark">
              M<span>↗</span>
            </span>
            <span>
              Market<span className="brand-sub">RESEARCH WORKSPACE</span>
            </span>
          </Link>
          <div className="nav-label">WORKSPACE</div>
          <nav>
            <Link href="/ops">
              ⚙ <span>Operations</span>
            </Link>
            <Link href="/alerts">
              ! <span>Alerts</span>
            </Link>
            <Link href="/corporate-actions">
              ⇄ <span>Adjustment review</span>
            </Link>
            <Link href="/threads">
              ◈ <span>Discussions</span>
            </Link>
            <Link href="/track-record">
              ▧ <span>Track record</span>
            </Link>
            <Link href="/usage">
              ◴ <span>Model usage</span>
            </Link>
            <Link href="/news">
              ▤ <span>News archive</span>
            </Link>
            <Link href="/search">
              ⌕ <span>Search stories</span>
            </Link>
            <Link href="/sources">
              ◌ <span>Source health</span>
            </Link>
            <Link href="/">
              ◉ <span>Live activity</span>
            </Link>
            <Link href="/stocks">
              ▥ <span>Watchlist</span>
            </Link>
            <Link href="/logbook">
              ≡ <span>Logbook</span>
            </Link>
            <Link href="/lab">
              ◇ <span>Signal Lab</span>
            </Link>
            <Link href="/backtests">
              ↗ <span>Backtests</span>
            </Link>
          </nav>
          <div className="sidebar-note">
            <span className="dot" /> NSE · DAILY DATA
            <p>
              Evidence first.
              <br />
              Every action, accounted for.
            </p>
            <span className="phase">PHASE 05 / OPERATIONS</span>
          </div>
        </aside>
        <main className="workspace">
          <header className="topbar">
            <span>
              Personal research <span className="slash">/</span> Indian equities
            </span>
            <LoginLink />
          </header>
          <CriticalAlerts />
          {children}
          <footer>
            Analysis for research, not an investment recommendation.{" "}
            <span>All session dates use India Standard Time.</span>
          </footer>
        </main>
      </body>
    </html>
  );
}
