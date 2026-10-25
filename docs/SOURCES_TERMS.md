# Source access review

Review date: 2026-10-25. This records engineering enablement decisions, not legal
advice. Phase 5 requires sources that cannot be justified to stay disabled.

| Source | Access and rate | Finding and decision |
| --- | --- | --- |
| NSE (jugaad, OpenChart fallback, announcements and corporate actions) | Website-backed libraries; previously daily prices/hourly announcements | [Terms](https://www.nseindia.com/static/nse-terms-of-use) section 9 prohibits systematic/automated collection. Disable these collectors pending permission or a licensed alternative. Existing data retained. |
| Yahoo Finance | yfinance; daily sample | [Provider terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001), automated-collection restriction, verified 2026-10-25: express prior permission required. Disabled ingestion and independent-comparison fetches. Earlier comparison results remain historical evidence; no new requests. Existing raw NSE series cannot be silently mixed with Yahoo's split-adjusted history. |
| SEBI | Browser candidate | [Website policy](https://www.sebi.gov.in/website-policy.html) requires permission for reproduction; not enabled. |
| Reliance Industries | Browser candidate | [Legal notice](https://www.ril.com/legal-notice) permits personal-computer copies, but robots fetch returned a rejected-request page. Fail closed; not enabled. Cloud database/LLM storage rights also need clarification. |
| Infosys | Browser candidate | [Robots](https://www.infosys.com/robots.txt) allows most pages, but [terms](https://www.infosys.com/terms-of-use.html) restrict copying/reproduction. Not enabled for archival extraction. |
| CCI | Browser candidate | [Copyright policy](https://www.cci.gov.in/contents/copyright) requires permission; not enabled. |
| RBI | Browser candidate | [Disclaimer](https://www.rbi.org.in/Scripts/Disclaimer.aspx) limits caching; RSS already exists. Browser extraction not enabled. |
| Telegram | Owner-selected outbound alerts; one batch/10 minutes | [Bot FAQ](https://core.telegram.org/bots/faq#how-do-i-avoid-hitting-limits) permits free normal bot messaging within limits. Paid broadcasting disabled. Awaiting local credentials. |
| Gemini | Public market evidence only; 150 calls/day app cap | Phase 4 checked [pricing](https://ai.google.dev/gemini-api/docs/pricing) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). No billing upgrade. Source permission still applies to submitted material. |

Remaining review: The Hindu feed, BSE announcement access,
and a suitable browser source. No browser site is approved yet. The daily
pipeline remains disabled during commissioning. Official circulars were consulted
manually to verify calendar exceptions; this does not grant automated access to
the exchange website.

## RSS commissioning — 2026-10-25

Mint's [RSS page](https://www.livemint.com/rss) offers feeds for individual,
noncommercial newsreader use. Economic Times' [RSS terms](https://economictimes.indiatimes.com/rss.cms)
allow personal use and personal retained copies. These two feeds are enabled for
this owner's private reader: publisher-provided headlines/snippets and links, no
full article collection, public feed hosting, commercial redistribution or model
training. This is a limited engineering interpretation of the personal RSS
allowance, not a blanket licence for reuse or a public/commercial product.
Mint's [general terms](https://www.livemint.com/terms-of-use) also restrict scraping
and AI development; do not expand the personal RSS reader into those uses.

Business Standard is disabled: its [terms](https://www.business-standard.com/terms-conditions)
restrict automated collection, archives and AI use without written permission.
The Hindu access review could not be completed, so its collector is disabled.
BSE automation review remains pending and its collector is disabled. Existing
historical data is retained. RSS collection no longer invokes exchange APIs.
