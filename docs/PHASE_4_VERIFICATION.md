# Phase 4 verification — 24 October 2026

Implementation uses Gemini free tier, the existing Supabase project, and the local dashboard. Phase 3's independent human news-label review remains deferred at the user's request. This document distinguishes automated checks from assistant review of live output.

## Completed checks

- Migration `007_agents.sql` applied with RLS on every new research table. Realtime is enabled for threads and messages.
- Owner sign-in/sign-out worked in a real browser. A different authenticated UUID saw zero private threads. Anonymous callers cannot request analysis; authenticated callers can insert only the allowed request columns, cannot set status, cannot claim queue entries, and cannot write messages or edit reports. An actual owner public-client message insert was denied with permission error 42501.
- 31 root Python tests passed. 42 agent tests passed using fake providers only. 13 backtest tests passed, including report grading. All relevant Ruff checks passed.
- Nine browser checks passed: login, discussion/report viewing, evidence inspection, mobile width, usage, track record, and all previous market/news/backtest flows. The additional evidence-panel scroll and event-specific log links passed the focused browser check. Desktop and mobile screenshots were inspected.
- Next.js production build and TypeScript check passed. All six GitHub jobs passed for final implementation commit `493262f`: core Python, dashboard, news, signals, backtest and analysis agents. [Verified workflow run](https://github.com/adithmv/fin-analysis/actions/runs/40081099134).
- `db/tests/agent_budgets.sql` verified actual PostgreSQL run, daily, requests-per-minute, tokens-per-minute and prompt-size enforcement. The transaction was rolled back and made no provider calls.
- Failure tests cover invalid/truncated JSON, one repair then withholding, 429 backoff/exhaustion, partial transcripts, missing/wrong/future evidence, hostile source text and delimiters, opinion numbers, unsupported prose numbers, insufficient samples, mixed statistics runs, tool scope/cutoff/row limits, future replays and interrupted local-worker recovery.
- Gating tests cover technical events, material news, nearby corporate actions, ATR thresholds, elapsed review intervals, stale data and quiet cases.
- Grading checks enforce creation-time entry for live reports, historical cutoff for replays, exact benchmark sessions, missing/immature/flagged windows, neutral scores and duplicate-date rejection. Running the real grader saved zero outcomes because new reports have no subsequent complete market window yet. No performance is invented.
- Current local credential values were scanned against tracked files; no match was found. Root `.env` and browser test artifacts remain ignored.

## Live provider findings

The initial Pydantic JSON schema was rejected by Gemini. The adapter now expands references into the supported OpenAPI schema subset while retaining strict local validation. A subsequent news response reached the output cap and was withheld after its single repair. The cap was raised to 6,000 output tokens with concise-response instructions. The first complete thread used eight calls and retained all eight messages.

Prompt v2 explicitly names the indicator numeric field (`value`), requires exact stored event dates and distinguishes a stored historical edge sign from an agent's stance. This reduced, but did not eliminate, invalid numeric/event claims. Those claims remain visibly unverified and are withheld from final summaries. The model still produces generic narrative and can overstate the meaning of an observational pattern; the UI therefore labels interpretation partial and explains that reasoning is not verified.

Review also found news/technical role drift. Prompt v3 uses a smaller role-specific evidence subset, balanced technical/news statistics, core indicators and a compact verified transcript. All four v3 news analysts stayed focused on corporate events rather than repeating oscillator commentary. Full prompt snapshots and a Python source hash are now stored in new thread configurations, so later file edits cannot change their prompts. Earlier exploratory v1/v2 threads retain their original version label and output; they were not retroactively rewritten.

Narrative can still include unsupported interpretations, such as valuation claims without valuation data or interpreting a positive bearish-pattern edge as bullish. The structured checks do not prove these arguments. The UI now labels checks as **Claims: verified/partial/unverified** and explicitly excludes narrative interpretation from verification. New final summaries use accepted claim text rather than treating a paragraph as checked merely because its numeric claims passed. Existing reports remain immutable, with code-derived confidence badges clearly distinguished from stored narrative wording.

## Review of ten completed discussions

The assistant read the role transcripts and reports, then checked published text for forbidden instructions and report confidence against the code caps. This is an implementation quality review, not a human-labelled accuracy test. V/P/U below means stored-field verified / partial / rejected claims; these are verifier classifications, **not an accuracy percentage**.

| Thread ID | Stock / prompt | V/P/U | Final stance / strength | Main finding |
|---|---|---|---|---|
| ad74ef2d-a352-41f5-acd3-d4e69d2635c2 | TCS v1 | 20/5/10 | neutral / none | Wrong metric names and event dates were caught; motivated explicit field instructions. |
| 141f8cc0-3fe1-4115-bbd7-45d50da5ba35 | RELIANCE v2 | 16/18/7 | neutral / weak | News edges were overinterpreted in prose; code did not establish strong evidence. |
| 9b646514-454e-4e42-8f19-ef0a1855c8a5 | TCS v2 | 24/6/3 | neutral / weak | Numeric references improved; news role drifted into chart commentary. |
| acfb8819-fdb1-4fb7-bbb9-6d88914cb7f9 | INFY v2 | 11/11/9 | neutral / weak | Earnings narrative exceeded limited samples; rejected facts stayed out of summary. |
| 22e68733-8a72-4f26-8cf5-aed1fdb683e6 | HDFCBANK v2 | 24/10/1 | neutral / weak | Sparse company-specific evidence and a generic news role; low confidence retained. |
| d8d2a88d-0462-4a6f-a4f3-cb0e20122b23 | ICICIBANK v2 | 26/2/4 | neutral / weak | Checked numeric claims did not justify narrative certainty; prompted clearer UI wording. |
| fe8d6eae-eed1-4f3a-9de7-78b6d5b705a6 | RELIANCE v3 | 19/11/6 | neutral / weak | News role focused on events; counter-arguments visible; some unsupported numbers rejected. |
| f7ec33d8-dfcb-40fe-a64e-a6d54ad81de5 | TCS v3 | 20/3/5 | neutral / weak | Technical pattern statistics entered the debate; valuation language remains an unchecked interpretation. |
| 889a0021-2be2-4d48-ac73-3a7556bdf470 | INFY v3 | 1/19/12 | mixed / weak | Weakest factual coverage; one entirely unverified bear message was visible and excluded from subsequent accepted claims. |
| 0a9343ff-f97c-4c67-bce4-5875be234307 | HDFCBANK v3 | 25/9/2 | neutral / weak | News scope improved; positive edge for a bearish pattern still invited flawed bullish interpretation. |

All ten contain eight debate messages. Aggregate: **186 verified, 94 partial, 59 rejected** across 339 structured claims. All final reports have low confidence and no severe future-data event. Published debate text passed the trading-instruction lint. This does not imply that reasoning is reliable; the weak evidence ratings and findings above are material limits.

The direct trade question was rejected with zero model calls. A mixed question had its trade-advice part declined, then received an evidence-linked partial answer using one model call. Its tool/model events are 711 and 712 and open the correct question-run log. The authenticated client queued the requests; the worker produced the messages. Usage reconciliation found **90 reserved attempts, 90 logbook call events, zero attempts missing an event**, and matching recorded input-token totals of 1,728,999. Early probe token counts remain unknown rather than fabricated.

## Final live checks

- The real dashboard form queued a trade-advice question and showed the worker's deterministic refusal with no model call. Repeated smoke checks retain these private test messages.
- A Pacific-day rollover exposed an empty usage ledger for the new day. The page now includes an explicit empty state and a historical-day selector; the 90 earlier attempts remain inspectable. Current-day counters correctly reset to zero.
- The historical usage selector and dashboard question/refusal flow passed the focused browser check. The local queue worker was restarted on the final implementation; no request was running or left pending during restart.
- Final implementation commit `493262f` passed all GitHub checks. The following documentation-only commit records these results and the ten-thread review without changing the tested implementation.

## Practical limits

This is an assistant review of model output, not an independent human-labelled evaluation. No report has a mature live outcome yet. Several reports for the same stock on one date are acceptance samples, not independent performance observations. News-derived evidence cannot establish moderate/strong strength while human accuracy review remains pending.

The verifier checks frozen stored fields and structured claims, not truth outside the archive or the quality of reasoning. Unsupported nonnumeric prose may escape detection; its interpretation is not automatically reliable. The source archive has limited history and is not complete market coverage. Strict known-at timestamps make most pre-ingestion replays unavailable. Weekday staleness approximates the exchange calendar.

The free-tier account's exact quotas remain unconfirmed; conservative application limits and provider 429 handling are enforced. No paid upgrade was enabled. A crash between queue claiming and local journal creation can leave a running request needing inspection; multiple worker machines are outside this phase. Ollama is implemented as an optional adapter but was not live-tested.
