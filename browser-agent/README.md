# Browser agent

Read-only recipe collector with exact host/path allowlists, mandatory robots checks, shared daily page limits, bounded downloads and isolated Playwright contexts. JavaScript, cookies from existing sessions, subresources, forms, WebSockets and downloads are unavailable. Redirects pass the same checks. Access challenges stop the job without retry. Extracted source instructions remain untrusted text.

Install from the repository root using `uv venv browser-agent/.venv --python 3.12`, then `uv pip install --python browser-agent/.venv/Scripts/python.exe -r browser-agent/requirements.txt`. Set `PLAYWRIGHT_BROWSERS_PATH` to the absolute `browser-agent/.venv/browsers` directory and run that environment's Python with `-m playwright install chromium`. The collector selects that directory by default.

Run `browser-agent/.venv/Scripts/python.exe browser-agent/main.py list` to review configured sources; `run --site reliance_releases` attempts the configured recipe. All live sites are currently disabled: robots access and archival permissions remain unresolved. The selectors are candidates, not verified live recipes. See `docs/SOURCES_TERMS.md`. Disabled sources never launch a browser or request source pages.

Successful extraction writes owner-visible `documents` with untrusted status and URL/text-hash deduplication. Partial text is labelled. No model receives page content in this implementation. AI navigation, PDF collection integration, news ingestion and scheduler commissioning remain pending; the isolated PDF parser is a foundation only.

Run tests using the module environment with `-m pytest browser-agent/tests -q`. The browser integration test serves a synthetic source through an intercepted transport and verifies that external links and script requests never reach the network. No live source access is needed.
