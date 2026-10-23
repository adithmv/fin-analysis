# Independent human review

The local `headlines.csv` contains 100 randomly sampled canonical stories. Predictions are hidden. The user chose to leave human review pending on 24 October 2026. No accuracy or acceptance claim is made until that review is complete.

Fill `symbols` with NSE symbols or MARKET, `sentiment` with positive/negative/neutral, `event_types` with keys from config/news_events.yaml, and `reviewer` with your name. Use semicolons for multiple symbols/types and NONE for no match. Keep IDs unchanged. Judge titles only; do not consult model predictions during labelling. The scorer uses title plus source snippet, so report this input difference when interpreting agreement.

Run `news/.venv/Scripts/python.exe news/main.py gold-eval` from the repository root. It records precision/recall, sentiment agreement/confusion, and event exact-set agreement/confusion in the logbook. At least 100 labelled items are required. Review linking precision against the initial 0.90 target and inspect errors before using downstream results.

Actual source headlines and human labels stay local and are ignored by Git to avoid redistributing the collected archive. Tests use synthetic fixtures. Never replace independent human labels with model predictions and call them ground truth.
