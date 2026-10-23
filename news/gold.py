"""Blind human evaluation export. Unlabelled data is never reported as accuracy."""

from collections import Counter
import csv
from pathlib import Path
import random
from .storage import read

FOLDER = Path(__file__).resolve().parent / "tests/gold"


def sample(client, n=100):
    rows = [r for r in read(client, "articles") if not r["is_duplicate"]]
    rows.sort(key=lambda r: r["published_at"], reverse=True)
    chosen = random.Random(2026).sample(rows[:1000], min(n, len(rows[:1000])))
    FOLDER.mkdir(exist_ok=True)
    path = FOLDER / "headlines.csv"
    if path.exists():
        raise ValueError("Existing gold labels will not be overwritten; move the file before a fresh export")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["article_id", "title", "source", "symbols", "sentiment", "event_types", "reviewer"],
        )
        writer.writeheader()
        for r in chosen:
            writer.writerow({"article_id": r["id"], "title": r["title"], "source": r["source_key"]})
    return {
        "exported": len(chosen),
        "file": str(path),
        "status": "Human review required; predictions hidden. Use NONE for empty symbols and semicolons for multiple values.",
    }


def evaluate(client, config):
    with (FOLDER / "headlines.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    labelled = [
        r
        for r in rows
        if r["reviewer"].strip()
        and r["symbols"].strip()
        and r["sentiment"] in ("positive", "negative", "neutral")
        and r["event_types"].strip()
    ]
    if not labelled:
        return {
            "status": "awaiting_human_labels",
            "labelled": 0,
            "exported": len(rows),
            "accuracy": None,
            "message": "No accuracy claimed before independent human review",
        }
    links = read(client, "article_symbols")
    scores = read(
        client,
        "article_sentiment",
        {
            "model_key": config["sentiment"]["model"],
            "model_revision": config["sentiment"]["revision"],
            "scope": config["sentiment"]["scope"],
        },
    )
    events = read(client, "news_events")
    tp = Counter()
    fp = Counter()
    fn = Counter()
    sentiment = Counter()
    confusion = Counter()
    event_hits = 0
    for row in labelled:
        expected = set(row["symbols"].split(";")) - {"NONE"}
        predicted = {r["symbol"] for r in links if r["article_id"] == row["article_id"]}
        tp.update(expected & predicted)
        fp.update(predicted - expected)
        fn.update(expected - predicted)
        actual = next((r["label"] for r in scores if r["article_id"] == row["article_id"]), "unscored")
        sentiment[(row["sentiment"], actual)] += 1
        expected_events = set(row["event_types"].split(";")) - {"NONE"}
        actual_events = {r["event_type"] for r in events if r["article_id"] == row["article_id"]}
        event_hits += expected_events == actual_events
        confusion[(";".join(sorted(expected_events)), ";".join(sorted(actual_events)))] += 1

    def metrics(a, b, c):
        return {
            "precision": a / (a + b) if a + b else None,
            "recall": a / (a + c) if a + c else None,
            "tp": a,
            "fp": b,
            "fn": c,
        }

    return {
        "labelled": len(labelled),
        "minimum_met": len(labelled) >= 100,
        "linking": metrics(sum(tp.values()), sum(fp.values()), sum(fn.values())),
        "per_symbol": {s: metrics(tp[s], fp[s], fn[s]) for s in tp.keys() | fp.keys() | fn.keys()},
        "sentiment_accuracy": sum(n for (a, b), n in sentiment.items() if a == b) / len(labelled),
        "sentiment_confusion": {f"{a} -> {b}": n for (a, b), n in sentiment.items()},
        "event_exact_set_accuracy": event_hits / len(labelled),
        "event_confusion": {f"{a} -> {b}": n for (a, b), n in confusion.items()},
    }
