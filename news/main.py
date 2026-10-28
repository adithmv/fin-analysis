"""Manual, free, local news research pipeline. Text is data, never executable instructions."""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
import yaml
from shared.db import get_client
from shared.logbook import log_event, sanitize

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))
from news.storage import read, execute, upsert, store_articles  # noqa: E402


def settings():
    return tuple(
        yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8"))
        for name in ("news.yaml", "aliases.yaml", "news_events.yaml", "feeds.yaml")
    )


def sources(client, feeds):
    existing = {r["source_key"]: r for r in read(client, "news_sources")}
    for entry in feeds["sources"]:
        row = dict(
            source_key=entry["key"],
            name=entry["name"],
            source_type=entry["type"],
            url=entry.get("url"),
            enabled=entry["enabled"],
            poll_interval_minutes=feeds["default_poll_interval_minutes"],
            notes=entry.get("notes"),
        )
        if entry["key"] not in existing:
            upsert(client, "news_sources", [row], "source_key", True)
        elif not entry["enabled"] and existing[entry["key"]]["enabled"]:
            execute(client.table("news_sources").update({"enabled":False,"notes":entry.get("notes")}).eq("source_key",entry["key"]))
    allowed={entry["key"] for entry in feeds["sources"]}
    return {r["source_key"]: r for r in read(client, "news_sources") if r["source_key"] in allowed}


def collect(client, args, aliases, feeds, run_id):
    from news.collect import rss, announcements, corporate_actions

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    since = args.since or (now.date() - timedelta(days=7))
    configured = sources(client, feeds)
    active_symbols = {
        row["symbol"]
        for row in read(
            client,
            "watchlist",
            {"active": True, "exchange": "NSE", "kind": "equity"},
        )
    }
    symbols = (
        list(dict.fromkeys(s.strip().upper() for s in args.symbols.split(",")))
        if args.symbols
        else sorted(active_symbols)
    )
    if any(symbol not in active_symbols for symbol in symbols):
        raise ValueError("Select active NSE equities from the watchlist")
    failures = 0
    total = 0
    for key, source in configured.items():
        if args.command == "fetch" and source["source_type"] != "rss":
            continue
        if args.source and args.source != key:
            continue
        if args.command == "announcements" and source["source_type"] != "exchange_api":
            continue
        if args.command == "corporate-actions" and key != "nse_announcements":
            continue
        action = "fetch_feed" if source["source_type"] == "rss" else "fetch_announcements"
        if args.command == "corporate-actions":
            action = "fetch_corporate_actions"
        if not source["enabled"] or (args.command == "fetch" and not rss.due(source)):
            log_event(
                run_id,
                "news",
                action,
                "skipped",
                tool=key,
                output_summary="Disabled or polling interval not reached",
            )
            continue
        execute(
            client.table("news_sources").update({"last_fetched_at": now.isoformat()}).eq("source_key", key)
        )
        try:
            metadata = {}
            if source["source_type"] == "rss":
                rows, metadata, unchanged = rss.fetch(
                    source,
                    feeds,
                    on_retry=lambda attempt, wait: log_event(
                        run_id,
                        "news",
                        action,
                        "retried",
                        tool=key,
                        output_summary=f"Attempt {attempt}; wait {wait}s",
                    ),
                )
                count = store_articles(client, rows)
                log_event(
                    run_id,
                    "news",
                    "parse_items",
                    "warning" if any(r["published_at_assumed"] for r in rows) else "success",
                    tool=key,
                    output_summary=f"{len(rows)} items; {sum(r['published_at_assumed'] for r in rows)} assumed times",
                )
                log_event(
                    run_id,
                    "news",
                    action,
                    "skipped" if unchanged else "success",
                    tool=key,
                    output_summary="Not modified" if unchanged else f"{count} new of {len(rows)} items",
                )
                total += count
            else:
                source_errors = []
                for symbol in symbols:
                    try:
                        if args.command == "corporate-actions":
                            rows = corporate_actions.fetch(symbol, since, now.date())
                            upsert(client, "corporate_actions", rows, "identity_key")
                            earliest = min((r["ex_date"] for r in rows if r["ex_date"]), default="none")
                            count = len(rows)
                        else:
                            rows = announcements.fetch(
                                symbol, "NSE" if key.startswith("nse") else "BSE", since, now.date(), aliases
                            )
                            count = store_articles(client, rows)
                            earliest = min((r["published_at"] for r in rows), default="none")
                        total += count
                        log_event(
                            run_id,
                            "news",
                            action,
                            "success",
                            tool=key,
                            symbol=symbol,
                            output_summary=f"{count} stored; earliest returned {earliest}; requested since {since}",
                        )
                    except Exception as exc:
                        log_event(run_id, "news", action, "failed", tool=key, symbol=symbol, error=str(exc))
                        print(f"{key}/{symbol}: {sanitize(exc)}", file=sys.stderr)
                        source_errors.append(symbol)
                if source_errors:
                    raise ValueError(f"Failed symbols: {', '.join(source_errors)}; other symbols completed")
            execute(
                client.table("news_sources")
                .update({"last_success_at": now.isoformat(), "consecutive_failures": 0, **metadata})
                .eq("source_key", key)
            )
        except Exception as exc:
            failures += 1
            count = source["consecutive_failures"] + 1
            enabled = count < feeds["max_consecutive_failures_before_disable"]
            execute(
                client.table("news_sources")
                .update(
                    {"consecutive_failures": count, "enabled": enabled, "notes": str(sanitize(exc))[:500]}
                )
                .eq("source_key", key)
            )
            log_event(run_id, "news", action, "failed", tool=key, error=str(exc))
            if not enabled:
                log_event(
                    run_id,
                    "news",
                    "disable_source",
                    "warning",
                    tool=key,
                    output_summary=f"Disabled after {count} failed polls; manual re-enable required",
                )
    return {"stored": total, "failed": failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "announcements", "corporate-actions"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--source")
        cmd.add_argument("--symbols")
        cmd.add_argument("--since", type=lambda s: datetime.fromisoformat(s).date())
    cmd = commands.add_parser("process")
    cmd.add_argument("--stage", choices=["dedupe", "link", "classify", "sentiment", "embed"])
    cmd = commands.add_parser("search")
    cmd.add_argument("query")
    cmd.add_argument("--symbol")
    cmd.add_argument("--k", type=int, default=10)
    commands.add_parser("health")
    commands.add_parser("download-models")
    cmd = commands.add_parser("gold-sample")
    cmd.add_argument("--n", type=int, default=100)
    commands.add_parser("gold-eval")
    commands.add_parser("serve")
    args = parser.parse_args(argv)
    run_id = str(uuid4())
    try:
        config, aliases, rules, feeds = settings()
        if args.command == "download-models":
            from news.scoring.sentiment import Sentiment
            from news.embeddings.embedder import Embedder

            log_event(run_id, "news", "download_models", "started")
            scorer = Sentiment(config["sentiment"], offline=False)
            scores = scorer.score(
                ["The company reports record profits.", "The company reports heavy losses."]
            )
            embedder = Embedder(config["embeddings"], offline=False)
            assert len(embedder.encode(["Financial research"])[0]) == 384
            log_event(
                run_id,
                "news",
                "download_models",
                "success",
                output_summary="Pinned models cached locally; CPU smoke test passed",
            )
            print(json.dumps(scores))
            return 0
        if args.command == "serve":
            import uvicorn

            uvicorn.run("news.server:app", host="127.0.0.1", port=8766)
            return 0
        client = get_client()
        log_event(run_id, "news", "run_start", "started", input_summary=args.command)
        if args.command in ("fetch", "announcements", "corporate-actions"):
            result = collect(client, args, aliases, feeds, run_id)
        elif args.command == "process":
            from news.pipeline import process

            result = process(client, config, aliases, rules, feeds, run_id, args.stage)
        elif args.command == "health":
            from news.health import report

            result = report(client)
        elif args.command == "search":
            from news.search import search

            result = search(client, config, args.query, symbol=args.symbol, k=args.k)
        else:
            from news.gold import sample, evaluate

            result = sample(client, args.n) if args.command == "gold-sample" else evaluate(client, config)
            log_event(
                run_id,
                "news",
                args.command.replace("-", "_"),
                "warning" if result.get("status") == "awaiting_human_labels" else "success",
                meta=result,
            )
        log_event(
            run_id,
            "news",
            "run_end",
            "warning" if isinstance(result, dict) and result.get("failed") else "success",
            output_summary=json.dumps(result, default=str)[:250],
        )
        print(json.dumps(result, default=str, ensure_ascii=True))
        return 1 if isinstance(result, dict) and result.get("failed") else 0
    except Exception as exc:
        log_event(run_id, "news", "run_end", "failed", error=str(exc))
        print(f"News failed: {sanitize(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
