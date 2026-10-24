# Phase 3 verification — 24 October 2026 (IST)

Implementation is ready with one explicitly deferred acceptance item: the user
chose to leave the 100-item human-labelled accuracy review pending. Accuracy is
not claimed. Later phases must carry that caveat.

## Stored evidence

- Migrations 004, 005 and 006 applied. pgvector available; all seven new tables
  have RLS and no anonymous INSERT privilege. Security advisors returned no issues.
- NIFTY 50 Yahoo history: 738 stored daily candles, added as an index. Equities
  remain the default strategy universe.
- Initial archive: 764 articles, 66 duplicates, 670 company/macro links, 667
  classified events, 697 sentiment rows, 593 embeddings; 32 corporate actions.
- Three RSS sources collected successfully initially (Mint, ET, Hindu). Business
  Standard initially reset the connection and is visibly failing; retry behavior
  and source isolation are tested. Moneycontrol is deliberately disabled because
  its feed was stale. Both NSE and BSE announcements were collected. NSE malformed
  attachment links were handled with exchange listing links; affected symbols
  were retried successfully. No full articles or attachments were downloaded.
- News study run `9e3b3a4d-06ba-4250-91e8-80ba68a7f086`: 840 rows.
  Sentiment run `24486257-7972-449d-97e5-a6aa0a9f96dc`: 780 rows. Both include
  baseline, independent counts, chronological samples and NIFTY-adjusted rows.
- Repeat processing: zero changed duplicate groups, zero relinked/reclassified
  articles, zero new sentiment rows, zero new embeddings. No duplicate inserts.
- Database size after initial processing: 51 MB against Free's 500 MB allowance.

## Checks

25 news tests cover timestamps, publication-to-open timing, deduplication,
precision linking, every event rule, ambiguous corporate actions, conditional
feeds, malformed XML, 403/429 backoff, source failure isolation and circuit breaker,
model label order, long-input truncation, missing model handling, versioned
idempotence, and network-independent local linking. Nine backtest tests include
hand-calculated news returns, absolute moves, benchmark subtraction, missing-index
dates, exclusions, group counts and timing. Existing 31 root tests passed after
index-ingestion changes.

Production Next.js build and type check pass. Browser checks exercise filtering,
article detail, anecdotal outcomes, local semantic search, source health, stock
sentiment/actions, and adjusted news/sentiment studies. Desktop and 390px mobile
screenshots were inspected. Existing watchlist/logbook/research flows are retained.

CPU model smoke tests distinguish obvious profit/loss examples and return finite
384-dimensional embeddings. Semantic query “TCS quarterly earnings profit” with
TCS filtering returned matching stored stories. No model network calls occur
after caching. Hosted database connectivity remains necessary; complete offline
pipeline operation is not claimed.

## Practical limits

RSS history is shallow; the exchange backfill starts July 2026 for announcements.
Thus many IS samples are empty and independent OOS samples remain insufficient.
No positive performance conclusion is implied by populated result tables.
Paraphrased exchange announcements can escape conservative duplicate matching.
Macro stories are stored and searchable; the default five-stock study universe
does not pool MARKET/index events into company statistics. Corporate actions
provide context, not automatic adjustments to stored candles or quality flags.

Collected titles and the unlabelled gold CSV remain local/database-only, excluded
from Git. No secrets, paid service, cloud LLM, or trading function was added in Phase 3.
