"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { createWorkspaceGuidePages } from "@/lib/handbook-workspaces";

type HandbookElement =
  | { type: "heading" | "paragraph" | "bullet"; level: number; text: string }
  | { type: "table"; rows: string[][] };
type HandbookPage = { number: number; title: string; part: string; workspaceHref?: string; elements: HandbookElement[] };
type HandbookData = { title: string; updated: string; pages: HandbookPage[] };

export default function HandbookApp() {
  const [book, setBook] = useState<HandbookData | null>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let alive = true;
    fetch("/handbook-content.json")
      .then((response) => {
        if (!response.ok) throw new Error("The handbook could not be loaded.");
        return response.json() as Promise<HandbookData>;
      })
      .then((data) => {
        if (!alive) return;
        setBook({
          ...data,
          pages: [...data.pages, ...createWorkspaceGuidePages(data.pages.length)],
        });
        const saved = Number(window.localStorage.getItem("fin-handbook-page"));
        if (Number.isInteger(saved) && saved >= 0 && saved < data.pages.length) setActive(saved);
      })
      .catch((error: unknown) => {
        if (alive) setLoadError(error instanceof Error ? error.message : "The handbook could not be loaded.");
      });
    return () => { alive = false; };
  }, []);

  const pages = book?.pages ?? [];
  const selectedPage = pages[active];
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return pages.map((page, index) => ({ page, index }));
    return pages.flatMap((page, index) => {
      const content = [page.title, page.part, ...page.elements.flatMap((element) =>
        element.type === "table" ? element.rows.flat() : [element.text],
      )].join(" ").toLocaleLowerCase();
      return content.includes(needle) ? [{ page, index }] : [];
    });
  }, [pages, query]);

  function choose(index: number) {
    setActive(index);
    window.localStorage.setItem("fin-handbook-page", String(index));
  }

  return (
    <div className="handbook-app">
      <aside className="handbook-index" aria-label="Handbook table of contents">
        <div className="handbook-index-top">
          <div className="handbook-kicker">FIN ANALYSIS</div>
          <h1>Project handbook</h1>
          <p>Technical guide · operations manual · scenarios</p>
          <label className="handbook-search-label" htmlFor="handbook-search">Search the handbook</label>
          <input id="handbook-search" className="handbook-search" type="search"
            placeholder="Try ‘backup’, ‘403’, or ‘signals’" value={query}
            onChange={(event) => setQuery(event.target.value)} />
          <div className="handbook-result-count" aria-live="polite">
            {query.trim() ? `${filtered.length} matching sections` : `${pages.length} sections`}
          </div>
        </div>
        <nav className="handbook-results" aria-label="Handbook sections">
          {filtered.map(({ page, index }) => (
            <button key={`${page.number}-${index}`}
              className={`handbook-result${active === index ? " selected" : ""}`}
              onClick={() => choose(index)} aria-current={active === index ? "page" : undefined}>
              <span className="handbook-result-part">{page.part.replace(/^Part \d+\s*/, "")}</span>
              <span className="handbook-result-title">{page.title}</span>
              <span className="handbook-result-page">Section {page.number}</span>
            </button>
          ))}
          {filtered.length === 0 && <p className="handbook-no-results">No matching sections. Try another term.</p>}
        </nav>
        <div className="handbook-index-foot">Personal market research · no trade execution</div>
      </aside>

      <main className="handbook-reader">
        {!book && !loadError && <div className="handbook-loading">Opening the handbook…</div>}
        {loadError && <div className="handbook-error" role="alert">{loadError} Refresh the page to try again.</div>}
        {selectedPage && (
          <>
            <header className="handbook-reader-head">
              <div>
                <div className="handbook-breadcrumb">PROJECT HANDBOOK <span>/</span> {selectedPage.part}</div>
                <div className="handbook-page-number">Section {selectedPage.number} of {pages.length}</div>
              </div>
              <div className="handbook-controls">
                <button onClick={() => choose(Math.max(0, active - 1))} disabled={active === 0}>Previous</button>
                <button onClick={() => choose(Math.min(pages.length - 1, active + 1))} disabled={active === pages.length - 1}>Next</button>
              </div>
            </header>
            <article className="handbook-article">
              <div className="handbook-article-part">{selectedPage.part}</div>
              <h2>{selectedPage.title}</h2>
              {selectedPage.workspaceHref && (
                <Link className="handbook-open-workspace" href={selectedPage.workspaceHref}>
                  Open this workspace →
                </Link>
              )}
              {selectedPage.elements.map((element, index) => {
                if (element.type === "table") return (
                  <div className="handbook-table-wrap" key={index}>
                    <table className="handbook-table"><tbody>
                      {element.rows.map((row, rowIndex) => (
                        <tr key={rowIndex}>{row.map((cell, cellIndex) => (
                          <td className={cellIndex === 0 ? "handbook-table-label" : undefined} key={cellIndex}>{cell}</td>
                        ))}</tr>
                      ))}
                    </tbody></table>
                  </div>
                );
                if (element.type === "heading") return <h3 className="handbook-subheading" key={index}>{element.text}</h3>;
                if (element.type === "bullet") return <p className="handbook-bullet" key={index}><span aria-hidden="true">•</span>{element.text}</p>;
                return <p className="handbook-paragraph" key={index}>{element.text}</p>;
              })}
            </article>
            <footer className="handbook-reader-foot">
              <span>Current-state edition · {book?.updated}</span>
              <span>Analysis for research, not investment advice.</span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
