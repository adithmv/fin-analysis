# News

Collection of RSS titles/snippets, NSE/BSE announcements, corporate actions,
precision-first company links, rule-based events, CPU FinBERT sentiment and local
MiniLM semantic memory. No full article/document downloads or cloud model calls.

## Setup and use

Use Python 3.12 and a dedicated environment. Apply migrations 004–006 after the
Phase 1/2 migrations. Root `.env` supplies the server-only database credentials.

```powershell
python -m venv news/.venv
news/.venv/Scripts/python.exe -m pip install -r news/requirements-lock.txt -e ./shared
news/.venv/Scripts/python.exe news/main.py download-models
news/.venv/Scripts/python.exe news/main.py fetch
news/.venv/Scripts/python.exe news/main.py announcements --symbols TCS,RELIANCE --since 2026-07-01
news/.venv/Scripts/python.exe news/main.py corporate-actions --since 2023-10-24
news/.venv/Scripts/python.exe news/main.py process
news/.venv/Scripts/python.exe news/main.py search "quarterly profit" --symbol TCS --k 5
news/.venv/Scripts/python.exe news/main.py health
news/.venv/Scripts/python.exe news/main.py serve
```

`serve` exposes only read operations on loopback port 8766. Keep it running for
dashboard semantic search and similar-event panels. The Next.js route forwards
only a fixed set of search parameters to that fixed local address. No service key
enters browser code. The dashboard still needs its public Supabase connection.

The first model download requires internet. Processing then loads pinned cached
models with `local_files_only=True`, CPU execution, and remote code disabled.
Database reads/writes still need internet because this installation uses hosted
Supabase. Fully disconnected end-to-end processing is not supported; pure stage
tests run without a model download or network. Missing cache fails clearly.

NSE announcement and corporate-action collection defaults to active NSE equity
watchlist symbols. A manual `--symbols` selection is also restricted to those
active equities; remove a stock from the dashboard to exclude it from future
targeted collection jobs.

## Collection and data contracts

- `feeds.yaml`: two enabled personal RSS feeds; other feeds and exchange
  announcement sources remain disabled. Conditional headers are saved where supplied. Polling
  defaults to 30 minutes; HTTP 429/server errors retry with bounded backoff; 403 stops immediately.
  Five failed polls disable a source for manual review. A failing symbol or feed
  does not prevent other symbols/sources from completing.
- NSE uses Dalal's public session endpoint with 90-day date windows. BSE uses the
  `bse` package's paginated announcement interface. Attachment links are stored,
  never downloaded. Invalid NSE attachment links fall back to its listing page.
- Published dissemination times are preferred. Date-less items retain a marked
  assumption and are excluded from studies. Naive exchange timestamps use IST,
  explicitly recorded in provenance. UTC storage; IST display.
- URL hashes prevent repeated inserts. Conservative near-duplicate matching
  preserves numeric/quarter/negation differences; the earliest publication is
  canonical within 48 hours. Duplicate groups are not evidence of independent events.
- `article_symbols` records matched text, method, confidence and linker version.
  `MARKET` is macro scope, not a company. Ambiguous aliases need context.
- Events enter at the first **stored session open strictly after publication**.
  No known future session means pending, not a guessed calendar date. Reprocessing
  after candle ingestion fills it. Articles with assumed times stay excluded.
- Atomic `replace_article_analysis` replaces links/events with processing markers.
  Version/hash checks reject changed aliases/rules without a version bump. Scoring
  is keyed by article, scope, model and revision; embeddings by pinned model key.
- Retention clears raw payloads after 90 days while retaining compact provenance,
  text, scores, events and corporate actions. No full text is stored.

## Models and limits

Pinned revisions live in `config/news.yaml`. FinBERT maps probability indices from
the model's label configuration and truncates at 512 tokens. Its current model
card declares **CC-BY-NC-SA-4.0**: this installation is personal/noncommercial.
MiniLM-L6-v2 uses 384-dimensional normalized vectors and Apache-2.0 licensing.
Do not mix embedding model versions in this vector column; the database checks
the exact pinned model key. A model migration requires deliberate re-embedding.

Sources: [FinBERT model card](https://huggingface.co/ProsusAI/finbert),
[MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
[NSE market timings](https://www.nseindia.com/static/market-data/market-timings),
[Supabase database size](https://supabase.com/docs/guides/platform/database-size).

Supabase Free database allowance is 500 MB; measured database size after initial
Phase 3 processing was 51 MB. Each vector alone is about 1.5 KB, plus row/index
overhead. Only linked canonical articles are embedded. Monitor database growth;
automatic RSS collection now runs every 30 minutes as described below.

## Automatic RSS updates on this laptop

Windows task `Fin Analysis News Updates` runs `ops/news.ps1` every 30 minutes:
fetch enabled RSS feeds, then deduplicate, link, classify, score sentiment and embed
locally. It processes healthy results even if another feed fails. Overlaps are
skipped; missed starts catch up; failures get one retry after five minutes. Keep
the laptop awake, signed in and online. Market/research pipelines in
`config/schedule.yaml` remain disabled independently. Do not also enable news_poll
without removing this task, or two schedulers will own news collection.

Use `ops/install-news-task.ps1` to register/update the task. Start it immediately
with `Start-ScheduledTask -TaskName 'Fin Analysis News Updates'`. Inspect
`.cache/news-task/fetch.log`, `process.log` and the completed task result. A skipped
overlapping trigger may show an ignored-start result while the original run remains
active; inspect task state as well.

The news environment uses host-accessible Python 3.12.14 at
`C:/dev/tools/python-3.12.14` because Windows Task Scheduler cannot access the
agent-managed runtime path. Rebuild against a host-installed Python 3.12 with the
news lockfile and editable shared package. The task sets `HF_HOME` to
`.cache/huggingface`, which contains the cached pinned models; set this same
variable when running `download-models` during a fresh setup.

The enabled feeds are Mint and Economic Times. Other sources remain disabled
pending review or permission. RSS fetch never invokes exchange APIs and HTTP 403
is not retried. Only publisher-supplied headlines/snippets and links are fetched
for private noncommercial use; no full articles, republication or model training.
Source decisions are in `docs/SOURCES_TERMS.md`. Fresh news does not refresh price
data; event outcomes may stay pending until price collection is commissioned.

## Research and evaluation

```powershell
backtest/.venv/Scripts/python.exe backtest/main.py events --source news --all
backtest/.venv/Scripts/python.exe backtest/main.py events --source sentiment --all
news/.venv/Scripts/python.exe news/main.py gold-sample --n 100
news/.venv/Scripts/python.exe news/main.py gold-eval
news/.venv/Scripts/python.exe -m pytest news/tests -q
```

The initial gold file has 100 blind, unlabelled items. The user explicitly left
human review pending. Accuracy is **unverified**, not reported as a fabricated
score. See [review instructions](tests/gold/README.md). The real archive and labels
are not committed or redistributed; synthetic fixtures are used in tests.

Known limitations: recent RSS history; approximate rules; English only; one tone
score for a whole article, even with multiple companies; conservative deduplication
can miss cross-exchange paraphrases; unofficial exchange APIs can break; shallow
news samples make most results insufficient. Similar-event outcomes are anecdotal,
before costs, and not causal evidence. Neither sentiment nor similarity predicts
prices. Phase 4 must retain the pending-accuracy caveat if it consumes this data.
