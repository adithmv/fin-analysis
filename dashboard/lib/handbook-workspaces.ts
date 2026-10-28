type GuideElement =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; level: number; text: string }
  | { type: "bullet"; level: number; text: string };

export type WorkspaceGuidePage = {
  number: number;
  title: string;
  part: string;
  workspaceHref?: string;
  elements: GuideElement[];
};

type WorkspaceGuide = {
  title: string;
  path: string;
  purpose: string;
  operation: string;
  use: string[];
  read: string[];
  limits: string[];
};

const guides: WorkspaceGuide[] = [
  {
    title: "Choose a workspace",
    path: "/",
    purpose: "A short map of the dashboard: where to look first, what each area answers, and how the views fit together.",
    operation: "The dashboard is a read-and-review interface over the project’s stored market candles, collected news, research runs, and operations records. The views answer different questions and refresh at different intervals; one page is not a substitute for the evidence shown in another.",
    use: [
      "To see what the system just did, open Live activity, then follow an event into the Logbook for its full record.",
      "To inspect a stock, start at Watchlist and open its symbol page. Use the News archive for related headlines and the Logbook for pipeline activity.",
      "To choose the stocks you want monitored, open Watchlist and search by company name or symbol.",
      "To inspect news, use News archive for filters and original sources, then Search stories to find similar items from the stored archive.",
      "To assess evidence, use Signal Lab for historical event studies, Backtests for saved strategy runs, and Track record for outcomes of research reports.",
      "To investigate a failed or delayed process, use Operations for jobs and Alerts for incidents; check Source health when news collection is stale or quiet.",
      "Use Project handbook for the longer product, technical, and operating reference. This guide is the day-to-day tour of the dashboard pages.",
    ],
    read: [
      "Check the displayed time window and update time before concluding that a page is current.",
      "A blank view can mean no matching records, a filter that is too narrow, an offline service, or missing database configuration. Read the page’s status and error message first.",
      "The dashboard is for personal market research. It does not place orders or provide a guaranteed prediction.",
    ],
    limits: [
      "Changing a filter changes only what is shown; it does not collect new data or launch a research job.",
      "Some pages require you to sign in before they display or change stored research and operations records.",
      "Prices, headlines, model analysis, and research summaries can be incomplete or wrong. Open source evidence and data-quality notes before relying on a result.",
    ],
  },
  {
    title: "Live activity",
    path: "/",
    purpose: "A quick status board for recent pipeline activity, with a small card for each tracked module and a recent event stream.",
    operation: "The page reads recorded agent events from the database. A live database subscription refreshes new events as they arrive; a 15-second poll is the fallback. The module cards show the latest recorded start/end activity, not a promise that a process is running now.",
    use: [
      "Start here when you want to know whether the pipeline has recorded recent work.",
      "Use the module, status, symbol, and time-period filters to narrow the activity stream.",
      "Expand an event row to inspect its details, source references, run ID, and any error information.",
      "Choose the full Logbook link to see more records and page through older entries.",
    ],
    read: [
      "Live means the database event subscription is connected. Reconnecting or Not configured describes the dashboard connection, not whether every worker is healthy.",
      "A Never run tile means no matching start/end event has been recorded for that module.",
      "A green success event describes that recorded step; it does not certify the accuracy of every output it produced.",
    ],
    limits: [
      "Only actions that emit an event appear here. A quiet stream can mean no scheduled work occurred.",
      "Use Operations for job queue state and Alerts for active incidents. This page is an activity summary, not the incident ledger.",
    ],
  },
  {
    title: "Watchlist and stock pages",
    path: "/stocks",
    purpose: "A searchable NSE EQ-series stock catalogue and the set of equities selected for the project's future technical and research checks.",
    operation: "Searches the official NSE EQ-series company and symbol list. Owner-only actions add an equity to the active watchlist or mark it inactive; existing candles and research history remain stored. The dashboard reads active symbols from Supabase and fetches each latest daily candle. Ingestion YAML is used only to seed the list when the database has no NSE watchlist rows. Technical signal generation and freshness checks select active NSE equities. The daily schedule and automated price sources are currently disabled, and the evidence pack does not yet provide recurring fundamental checks.",
    use: [
      "Type at least two characters of a company name or NSE symbol in Find NSE stocks, then select Add. Sign in with the owner account to search and change the list.",
      "Choose Remove to stop future checks for an equity. Its historical candles and research reports remain available.",
      "Scan the company/symbol, latest close, session date, source, and data-health columns.",
      "Select a symbol to open its detail page. Follow its news or activity links when you need supporting context.",
      "Check Operations, Source health, and the Logbook before assuming scheduled checks or fresh prices are running.",
    ],
    read: [
      "Prices are stored daily candles in INR. The displayed date is the candle’s session date.",
      "The freshness badge estimates age using weekdays. It does not account for exchange holidays or special sessions, so verify the session calendar when timing matters.",
      "A missing close is shown as a dash and means no candle was returned for that symbol; it is not a zero price.",
    ],
    limits: [
      "The finder covers NSE listings in the EQ series. It does not include BSE-only securities, NSE SME listings, indexes, ETFs, or other NSE series.",
      "Adding a stock selects it for future jobs; it does not enable a disabled source or schedule. At present, price collection and daily scheduling are disabled, and periodic fundamental checks are not implemented.",
      "The stock detail page may contain historical material. Check the date, source, and adjusted/raw price basis before comparing values.",
    ],
  },
  {
    title: "Logbook",
    path: "/logbook",
    purpose: "The searchable, filterable record of pipeline actions, used to trace a result from a source or job to its stored output.",
    operation: "The page queries the agent event ledger, applies module/status/symbol/time filters, and subscribes to new database events. It shows 50 records per page in the full logbook and provides run-specific timelines when you open a run ID.",
    use: [
      "Choose a time window first, then narrow by module, status, or stock symbol.",
      "Open an event row to read its payload, source links, run ID, and error details.",
      "Open a run ID to see the events for that run in chronological order. Use this to follow its beginning, retries, warnings, and completion.",
      "Use Previous and Next at the bottom to move through older records.",
    ],
    read: [
      "Each row represents a recorded action. It is an audit trail of emitted events, not a complete operating-system log.",
      "An empty result after applying filters means no rows match those filters in the selected period; reset filters before assuming the system has no history.",
    ],
    limits: [
      "The logbook cannot show events that a worker never wrote to the database.",
      "For queued job state and retry/cancel controls, go to Operations. For active health incidents, go to Alerts.",
    ],
  },
  {
    title: "Pipeline operations and jobs",
    path: "/ops",
    purpose: "A signed-in control and status view for queued pipeline jobs, retryable failures, and worker heartbeat information.",
    operation: "The page reads recent job records and scheduler heartbeat data from the database, refreshes periodically, and sends retry/cancel requests through the protected operations API. Jobs progress according to the local scheduler and worker configuration.",
    use: [
      "Sign in, then scan the job module, kind, status, attempts, scheduled time, run ID, and last error.",
      "Filter by a word such as a status, source, or module to find a particular job.",
      "Use Retry only for a failed, dead, cancelled, or skipped job after checking its error and the relevant Logbook run.",
      "Use Cancel only for a queued or running job you intend to stop. Recheck the row and logbook after the request.",
      "Use the run link to inspect the event timeline. Use the heartbeat timestamp to assess whether the scheduler has reported in recently.",
    ],
    read: [
      "A recent heartbeat shows that the scheduler wrote a heartbeat; it does not prove all individual tasks succeeded.",
      "A retry creates another attempt. Check whether the original cause is fixed before retrying repeatedly.",
      "The page labels scheduling as being commissioned; treat the live machine’s configured schedule as the source of truth.",
    ],
    limits: [
      "Do not cancel a job merely because it has been running longer than expected; inspect the run and current status first.",
      "A successful request means the control request was accepted, not necessarily that the job finished successfully.",
      "This interface does not expose every worker log or a way to edit pipeline configuration.",
    ],
  },
  {
    title: "Alerts",
    path: "/alerts",
    purpose: "A signed-in incident list for actionable health-check failures that remain visible even if Telegram delivery is unavailable.",
    operation: "The page reads alert records maintained by the health-check and operations pipeline. Acknowledgement records that you have seen an open alert; resolution closes it. If its health check continues failing, a later check may create another incident.",
    use: [
      "Open the alert, read its severity, rule, subject, message, and the time/context shown.",
      "Follow the related pipeline/job/source record to identify the cause before taking action.",
      "Choose Acknowledge to mark an open alert as seen while work remains.",
      "Choose Mark resolved only after checking that the underlying issue has recovered; revisit the page to see whether a new incident appears.",
    ],
    read: [
      "Acknowledged means reviewed, not fixed. Resolved means the record is closed; continued failure can open another record.",
      "The app database is the durable alert history. Telegram is a notification channel and can fail independently.",
    ],
    limits: [
      "Acknowledging or resolving an incident changes its stored state; it does not repair the worker, source, or database.",
      "A missing Telegram message does not prove there was no alert. Check this page and the Operations record.",
    ],
  },
  {
    title: "Corporate-action review",
    path: "/corporate-actions",
    purpose: "A signed-in human review page for proposed split or bonus-share price adjustment factors.",
    operation: "The page compares the source’s action text with the proposed factor and previews stored prices around the ex-date. An independent cross-check status is displayed. Approving or rejecting submits your note and decision through a protected API; approved factors affect future adjusted views after recomputation, while raw candles remain preserved.",
    use: [
      "Read the symbol, ex-date, factor, original ratio text, and exchange-source link.",
      "Inspect the before/after price preview and independent cross-check. Investigate any mismatch or pending check.",
      "Enter a short, specific review note explaining what you verified; the decision buttons remain disabled without a note.",
      "Choose Approve factor only when the evidence supports it, or Reject factor when it does not. Then check the record again and verify recomputation before using adjusted outputs.",
      "Review the Unparsed or ambiguous actions list separately; it needs manual interpretation before it can be treated as a factor proposal.",
    ],
    read: [
      "An approved factor changes the adjusted-price view used by later analysis; original raw candles are preserved.",
      "A passed cross-check is evidence within its stated tolerance, not proof that the source or interpretation is infallible.",
    ],
    limits: [
      "Cash dividends are excluded from this split/bonus factor workflow.",
      "Existing research reports remain frozen. Do not assume a prior report was recomputed just because a factor was approved.",
      "Treat this as a financial-data review decision: inspect the underlying exchange evidence before approving.",
    ],
  },
  {
    title: "Research discussions",
    path: "/threads",
    purpose: "A signed-in workspace for requesting a stock analysis and reviewing its debate, evidence, verification, and final report.",
    operation: "A request is added to the analysis queue. A local worker gathers the permitted market evidence, requests model contributions, verifies stored facts and references, and records the thread and report. The page refreshes the list periodically; it does not itself run the analysis in the browser.",
    use: [
      "Choose one of the available stock symbols, then select Run analysis now once.",
      "Wait for the queued request to appear, and track its queued, running, completed, failed, or budget-exhausted status.",
      "Use the Symbol, Status, Stance, Evidence strength, and Research date filters to find a thread or report.",
      "Open a discussion to read the role-by-role case, claims, evidence links, verification notes, risks, invalidation points, and final report.",
      "Open Model usage if the request did not complete or if you want to check the remaining call budget.",
    ],
    read: [
      "The verifier checks stored facts and references; it does not prove that the reasoning is sound or that all source coverage is complete.",
      "Evidence strength and confidence should be read alongside sample size, source quality, and data-quality notes.",
      "The human-labelled news-accuracy review is pending, so news-derived conclusions have that known limitation.",
    ],
    limits: [
      "Each request consumes a limited model-call budget. Failed or interrupted attempts may count against the cap.",
      "A completed discussion is research material, not personalized investment advice or an instruction to trade.",
    ],
  },
  {
    title: "Report track record",
    path: "/track-record",
    purpose: "A retrospective scorecard for frozen research reports, compared with later stock and NIFTY 50 price outcomes.",
    operation: "The page joins saved reports to mature report-outcome rows, chooses either live reports or historical replays, then calculates directional-hit summaries for the selected trading-session horizon. Severe verification failures are excluded from the clean score; pending reports remain visible in the ledger.",
    use: [
      "Choose Live reports for reports created in normal operation or Historical replays for replay-generated reports.",
      "Select a horizon in trading sessions, then read the number of reports, mature outcomes, pending outcomes, and exclusions.",
      "Compare the score by stance, confidence, and evidence strength; inspect the outcome ledger for the report, verification status, entry/exit dates, stock return, index return, excess return, and hit.",
      "Open a ledger report to inspect the original discussion and its frozen evidence before interpreting the score.",
    ],
    read: [
      "Entry uses the first stored session opening after report creation; exit uses the close at the selected horizon. Index and stock dates must align.",
      "Neutral and mixed calls do not have a directional hit score. Reported intervals describe raw observations and can overstate precision when outcomes overlap.",
      "Fewer than 30 independent outcomes cannot establish reliability; even a larger score is historical evidence, not a promise of future performance.",
    ],
    limits: [
      "Returns are gross price changes and do not include trading costs.",
      "Reports with incomplete price sessions remain pending; severe verification failures are excluded from the clean summary but remain in the ledger.",
    ],
  },
  {
    title: "Model usage",
    path: "/usage",
    purpose: "A record of model-call reservations and usage against the application’s daily free-tier limit.",
    operation: "The page reads reserved call rows and their recorded role, model, status, timestamps, and token counts. It groups them by a Pacific-time budget day and refreshes periodically. Calls that fail or stop partway are still counted as attempts.",
    use: [
      "Check Calls today / cap and input/output token totals before requesting another analysis.",
      "Choose an earlier Usage day to inspect prior reservations.",
      "Review role, discussion link, model, status, and tokens for each row. Open the linked discussion to see what the call contributed.",
      "If the daily warning appears, wait for the next budget day or review the provider account’s limits before requesting more work.",
    ],
    read: [
      "The budget day runs midnight to midnight Pacific time, while displayed event timestamps are shown in IST.",
      "The application cap is a local guardrail; the provider’s account quota can be lower.",
      "Token totals for failed calls may be unavailable because the provider did not return usage data.",
    ],
    limits: [
      "This page reports recorded reservations; it does not change the provider’s quota or automatically enable billing.",
      "Do not treat a low token count as proof that a request was successful; inspect its status.",
    ],
  },
  {
    title: "News archive",
    path: "/news",
    purpose: "A filtered archive of canonical collected headlines, with source links, linked symbols, event labels, sentiment tags, and related historical events.",
    operation: "The archive loads stored articles and their classifications, groups likely duplicate copies, refreshes every 30 seconds, and applies the selected filters locally. Each item links to its original publisher and a detail view with related past events.",
    use: [
      "Filter by symbol, source, event type, sentiment, publication-date range in IST, or minimum importance.",
      "Read the headline and timestamp, then open the original source to verify the full story and context.",
      "Use the linked symbol badge to open that stock page. Choose Details & past events to see the stored detail and similar historical items.",
      "Choose Show more stories to reveal more matching results; reset filters if no story appears.",
    ],
    read: [
      "A time marked approximate indicates the collector inferred a publication time.",
      "Sentiment describes English-language tone; it does not measure expected share-price impact.",
      "Duplicate labels indicate copies grouped as the same likely story; grouping can be imperfect.",
    ],
    limits: [
      "The archive begins when collection began unless a source-specific backfill was run; it is not a complete exchange history.",
      "Classification is approximate and human accuracy review is pending. Always open the original article before relying on its interpretation.",
    ],
  },
  {
    title: "Search stories by meaning",
    path: "/search",
    purpose: "A meaning-based search over previously embedded and linked stories, useful for finding related events even when the wording differs.",
    operation: "The browser sends the search question and filters to the local news-memory service running on this computer. That service compares the query with vectors stored for archived stories and returns the closest matches. The route does not fetch general web search results.",
    use: [
      "Enter a concrete research question, for example “What happened after the RBI raised rates?”",
      "Optionally narrow by symbol and an IST date range, then choose Search stories.",
      "Sort through the matching headlines and summaries. Open the article detail and original source before drawing a conclusion.",
      "If the local service is offline, start the news memory service on this computer and retry; the page reports a specific offline message.",
    ],
    read: [
      "Similarity is related wording or subject matter, not a probability, forecast, or claim that two events had the same effect.",
      "Only stories that were embedded and linked are searchable. An absent match may not have been collected or embedded.",
    ],
    limits: [
      "This is a search of project memory, not live internet search.",
      "The local memory service must be running and its stored vectors must be available.",
    ],
  },
  {
    title: "News source health",
    path: "/sources",
    purpose: "A monitoring table for the configured news feeds, showing recent successful collection, failure streaks, duplicate rate, stock-link coverage, and timestamp quality.",
    operation: "The page reads the source-health summary maintained by collection jobs and refreshes every 15 seconds. Its status label combines whether the feed is enabled, recent failures, newest publication time, and recent item count.",
    use: [
      "Check the health label and last-success time first.",
      "Compare New items over 24 hours and 7 days with the source’s normal cadence.",
      "Review consecutive failures, duplicate rate, stock-link coverage, and assumed-time rate when a feed’s results look wrong.",
      "If a source is failing or disabled, inspect Operations, Alerts, and the Logbook for its collection error before changing configuration.",
    ],
    read: [
      "Quiet means no recent new items; it does not by itself mean the feed is broken.",
      "Counts include newly stored articles, including historical backfills, not necessarily articles published in that period.",
      "A source disables after five failed polls and requires manual review.",
    ],
    limits: [
      "This is a monitor, not a feed editor. It does not enable, disable, or repair a source.",
      "A healthy poll does not guarantee that the publisher provided all stories or that classification is correct.",
    ],
  },
  {
    title: "Project handbook workspace",
    path: "/handbook",
    purpose: "This searchable manual: project orientation, system details, operational procedures, edge cases, and the new page-by-page dashboard guide.",
    operation: "The handbook loads its text from a bundled content file, filters the section list in the browser as you type, and remembers the selected section in this browser. The workspace guides are appended to the project manual and can be searched with the same search field.",
    use: [
      "Search for the page name or task, such as “alerts”, “retry”, “backup”, or “Signal Lab”.",
      "Select a result in the left contents list, or use Previous and Next in the reading pane.",
      "Use the workspace guide pages for the purpose, how it works, exact steps, how to read results, and known limits of each dashboard area.",
      "Use the broader technical and scenario sections when you need architecture, failure handling, data rules, or release procedures.",
    ],
    read: [
      "Section numbers are the handbook app’s navigable sections, not Word print-page numbers.",
      "The current guide describes the interface and behavior present in this project edition; it may need updating when a page or pipeline changes.",
    ],
    limits: [
      "The handbook is documentation; its steps do not execute jobs or change your database.",
      "Check the page itself for the latest status and the Logbook for actual execution evidence.",
    ],
  },
  {
    title: "Signal Lab",
    path: "/lab",
    purpose: "A comparison table for stored event-study statistics: whether technical signals, news events, or sentiment buckets historically differed from a matched baseline.",
    operation: "The page loads the newest completed statistics run for the selected study source, then filters the stored rows by signal, scope, horizon, sample, and market adjustment. Technical rows use unadjusted returns; news and sentiment may be compared with raw or NIFTY-adjusted abnormal returns.",
    use: [
      "Choose Technical signals, News events, or Sentiment buckets.",
      "For news or sentiment, select unadjusted return or abnormal return minus NIFTY 50.",
      "Narrow the table by signal, scope, holding horizon, and All dates, In-sample, or Out-of-sample.",
      "Compare the event count and independent count, mean return, win rate, baseline, edge, and the separate in-sample/out-of-sample edge.",
      "Open Run provenance to inspect the stored configuration used for the visible statistics.",
    ],
    read: [
      "A positive edge is a historical difference from the selected baseline; it is not evidence by itself of a durable trading advantage.",
      "Rows marked Insufficient sample should be treated as descriptive only. Independent event count matters because events can overlap or cluster.",
      "Many signals and horizons create multiple-testing risk; a best-looking row can appear by chance.",
    ],
    limits: [
      "This workspace reads saved statistics; it does not launch a study run from the page.",
      "Use the out-of-sample row and the configuration together. Do not treat in-sample performance as validation.",
    ],
  },
  {
    title: "Backtests",
    path: "/backtests",
    purpose: "A read-only catalogue and drill-down for saved historical strategy tests, their buy-and-hold comparison, sample splits, and simulated trades.",
    operation: "The list reads stored backtest run metadata. Opening a run loads its per-symbol results, equity curves, metrics, and trades. The result view separates in-sample and out-of-sample periods and displays the saved run configuration and code version.",
    use: [
      "Choose a saved run from the list and inspect its symbols, date range, creation time, strategy key, and code version.",
      "On the run detail page, select a symbol and sample. Compare the strategy curve and metrics with buy-and-hold for the same period.",
      "Review the in-sample versus out-of-sample table, trade ledger, cost assumptions, and saved parameters.",
      "Open the run configuration when reproducing or comparing results; use the code version to distinguish implementations.",
    ],
    read: [
      "The simulator uses next-open execution and includes illustrative fee and slippage assumptions. They may not match broker charges.",
      "A parameter sweep tries multiple combinations; the best historical result can overstate evidence.",
      "Exclusion boundaries are retrospective data filters. Inspect them and the sample dates when judging generalization.",
    ],
    limits: [
      "This dashboard is a viewer for saved runs; it does not create or execute a backtest from this page.",
      "Backtests are historical simulations, not live orders or forecasts. Check for survivorship, data, and selection bias before using a result.",
    ],
  },
  {
    title: "Collected documents",
    path: "/documents",
    purpose: "A signed-in view of text documents collected by the browser research pipeline, with their source URL, extraction method, trust label, and processing status.",
    operation: "The page reads document records collected by the browser worker. Each record can expand to reveal extracted source text. The page deliberately labels extracted text untrusted because a web page can contain misleading statements or instructions.",
    use: [
      "Open Operations and choose Documents, then filter by status, source, or module.",
      "Inspect the title/domain, status, trust level, and extraction method first.",
      "Open Original source to view the page from which the text came; compare the extracted text with that source.",
      "Expand Read untrusted extracted text only when you need to inspect the captured material.",
    ],
    read: [
      "Collected text is source material, not an instruction for operating the project and not verified fact.",
      "Extraction status and trust level describe how the pipeline captured the page; they do not certify the author or claim.",
    ],
    limits: [
      "This page does not browse or collect a new document on demand.",
      "Follow the original URL and verify date, author, and context before using a claim in research.",
    ],
  },
];

function section(title: string, texts: string[], type: "paragraph" | "bullet" = "bullet"): GuideElement[] {
  return [
    { type: "heading", level: 2, text: title },
    ...texts.map((text) => ({ type, level: 0, text }) as GuideElement),
  ];
}

export function createWorkspaceGuidePages(startNumber: number): WorkspaceGuidePage[] {
  return guides.map((guide, index) => ({
    number: startNumber + index + 1,
    title: guide.title,
    part: "Workspace guide",
    workspaceHref: guide.path,
    elements: [
      { type: "paragraph", level: 0, text: guide.purpose },
      ...section("How it works", [guide.operation], "paragraph"),
      ...section("How to use it", guide.use),
      ...section("How to read the results", guide.read),
      ...section("Limits and good practice", guide.limits),
    ],
  }));
}
