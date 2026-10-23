import type { Metadata } from "next";
import Link from "next/link";
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
            <Link href="/">
              ◉ <span>Live activity</span>
            </Link>
            <Link href="/stocks">
              ▥ <span>Watchlist</span>
            </Link>
            <Link href="/logbook">
              ≡ <span>Logbook</span>
            </Link>
          </nav>
          <div className="sidebar-note">
            <span className="dot" /> NSE · DAILY DATA
            <p>
              Evidence first.
              <br />
              Every action, accounted for.
            </p>
            <span className="phase">PHASE 01 / FOUNDATION</span>
          </div>
        </aside>
        <main className="workspace">
          <header className="topbar">
            <span>
              Personal research <span className="slash">/</span> Indian equities
            </span>
            <span className="readonly">◈ Read-only workspace</span>
          </header>
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
