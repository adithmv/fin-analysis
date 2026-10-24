from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from zoneinfo import ZoneInfo
from shared.logbook import log_event, sanitize
from .storage import read, execute, upsert
from .normalize import deduplicate
from .linking.linker import link
from .events.classifier import classify


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def process(client, config, aliases, rules, feeds, run_id, stage=None):
    rows = read(client, "articles")
    if not rows:
        return {"articles": 0, "failed": 0}
    for r in rows:
        r["_has_raw"] = bool(r["raw"])
        r["raw"] = {**r.get("provenance", {}), **r["raw"]}
    failed = 0

    def log(action, status="success", **kw):
        log_event(run_id, "news", action, status, **kw)

    stages = [stage] if stage else ["dedupe", "link", "classify", "sentiment", "embed"]
    if "dedupe" in stages:
        original = {r["id"]: (r["dedupe_group_id"], r["is_duplicate"]) for r in rows}
        rows = deduplicate(rows, config["dedupe"])
        changed = 0
        for r in rows:
            if original[r["id"]] != (r["dedupe_group_id"], r["is_duplicate"]):
                execute(
                    client.table("articles")
                    .update({k: r[k] for k in ("dedupe_group_id", "is_duplicate")})
                    .eq("id", r["id"])
                )
                changed += 1
        log("dedupe", output_summary=f"{changed} changed; {sum(r['is_duplicate'] for r in rows)} duplicates")
    links = read(client, "article_symbols")
    linked = defaultdict(list)
    for row in links:
        linked[row["article_id"]].append(row)
    link_version = config["processing"]["linker_version"]
    link_hash = fingerprint({"aliases": aliases, "linking": config["linking"]})
    if "link" in stages:
        count = 0
        for r in rows:
            prior = r["processing"].get("link", {})
            if prior.get("version") == link_version and prior.get("hash") != link_hash:
                raise ValueError("Aliases or thresholds changed: bump linker_version")
            if prior == {"version": link_version, "hash": link_hash}:
                continue
            try:
                fresh = link(r, aliases, link_version, config["linking"]["min_confidence_to_store"])
                marker = {"link": {"version": link_version, "hash": link_hash}, "classify": None}
                execute(
                    client.rpc(
                        "replace_article_analysis",
                        {"p_article": r["id"], "p_links": fresh, "p_events": [], "p_processing": marker},
                    )
                )
                r["processing"].update(marker)
                linked[r["id"]] = fresh
                count += 1
            except Exception as exc:
                failed += 1
                log("link_entities", "failed", error=str(exc), input_summary=r["id"])
        coverage = sum(bool(linked[r["id"]]) for r in rows) / len(rows)
        log(
            "link_entities",
            "warning" if coverage < 0.2 else "success",
            output_summary=f"{count} processed; {coverage:.1%} linked",
        )
    if "classify" in stages:
        sessions = defaultdict(list)
        for c in read(client, "candles", {"exchange": "NSE", "timeframe": "1d"}, columns="symbol,ts"):
            sessions[c["symbol"]].append(
                datetime.fromisoformat(c["ts"]).astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()
            )
        sessions["MARKET"] = sessions.get(config["benchmark"], [])
        groups = Counter(r["dedupe_group_id"] for r in rows)
        tiers = {s["key"]: s["tier"] for s in feeds["sources"]}
        rules_hash = fingerprint(rules)
        count = 0
        for r in rows:
            marker = {
                "version": rules["logic_version"],
                "hash": rules_hash,
                "link": link_version,
                "group": r["dedupe_group_id"],
                "coverage": groups[r["dedupe_group_id"]],
                "last_session": max(
                    (max(sessions.get(linked_row["symbol"], []) or [""]) for linked_row in linked[r["id"]]),
                    default="",
                ),
            }
            prior = r["processing"].get("classify") or {}
            if prior.get("version") == rules["logic_version"] and prior.get("hash") != rules_hash:
                raise ValueError("Event rules changed: bump logic_version")
            if prior == marker:
                continue
            try:
                events = classify(
                    r,
                    linked[r["id"]],
                    rules,
                    sessions,
                    tiers.get(r["source_key"], 2),
                    groups[r["dedupe_group_id"]],
                    config["linking"]["min_confidence_for_events"],
                )
                execute(
                    client.rpc(
                        "replace_article_analysis",
                        {
                            "p_article": r["id"],
                            "p_links": None,
                            "p_events": events,
                            "p_processing": {"classify": marker},
                        },
                    )
                )
                r["processing"]["classify"] = marker
                count += 1
            except Exception as exc:
                failed += 1
                log("classify_events", "failed", error=str(exc), input_summary=r["id"])
        log(
            "classify_events",
            output_summary=f"{count} articles classified; future session dates remain pending",
        )
    if "sentiment" in stages:
        from .scoring.sentiment import Sentiment, english

        cfg = config["sentiment"]
        done = {
            r["article_id"]
            for r in read(
                client,
                "article_sentiment",
                {"model_key": cfg["model"], "model_revision": cfg["revision"], "scope": cfg["scope"]},
                columns="article_id,scope,model_key,model_revision",
            )
        }
        pending = [
            r
            for r in rows
            if not r["is_duplicate"]
            and r["id"] not in done
            and r["processing"].get("sentiment_skip") != cfg["revision"]
        ]
        valid = []
        for r in pending:
            if english(r):
                valid.append(r)
            else:
                execute(
                    client.table("articles")
                    .update({"processing": {**r["processing"], "sentiment_skip": cfg["revision"]}})
                    .eq("id", r["id"])
                )
        try:
            if valid:
                scorer = Sentiment(cfg)
                for start in range(0, len(valid), cfg["batch_size"]):
                    batch = valid[start : start + cfg["batch_size"]]
                    try:
                        scores = scorer.score(
                            [
                                r["title"]
                                + (" " + (r.get("summary") or "") if cfg["scope"] == "title_summary" else "")
                                for r in batch
                            ]
                        )
                        upsert(
                            client,
                            "article_sentiment",
                            [
                                dict(
                                    article_id=r["id"],
                                    scope=cfg["scope"],
                                    model_key=cfg["model"],
                                    model_revision=cfg["revision"],
                                    **score,
                                )
                                for r, score in zip(batch, scores)
                            ],
                            "article_id,scope,model_key,model_revision",
                        )
                    except Exception as exc:
                        failed += len(batch)
                        log("score_sentiment", "failed", error=str(exc))
            log(
                "score_sentiment",
                output_summary=f"{len(valid)} eligible; {len(pending) - len(valid)} skipped non-English/garbled",
            )
        except Exception as exc:
            failed += 1
            log(
                "score_sentiment",
                "failed",
                error=f"Local model unavailable; run download-models first. {sanitize(exc)}",
            )
    if "embed" in stages:
        from .embeddings.embedder import Embedder

        cfg = config["embeddings"]
        key = cfg["model"] + "@" + cfg["revision"]
        done = {
            r["article_id"]
            for r in read(client, "article_embeddings", {"model_key": key}, columns="article_id,model_key")
        }
        pending = [
            r
            for r in rows
            if not r["is_duplicate"]
            and r["id"] not in done
            and (linked[r["id"]] or not cfg["embed_only_if_linked"])
        ]
        try:
            if pending:
                embedder = Embedder(cfg)
                for start in range(0, len(pending), 16):
                    batch = pending[start : start + 16]
                    vectors = embedder.encode([r["title"] + " " + (r.get("summary") or "") for r in batch])
                    upsert(
                        client,
                        "article_embeddings",
                        [
                            dict(
                                article_id=r["id"],
                                model_key=key,
                                embedding=vector,
                                text_basis="title_summary",
                            )
                            for r, vector in zip(batch, vectors)
                        ],
                        "article_id,model_key",
                    )
            log("embed_articles", output_summary=f"{len(pending)} relevant canonical articles embedded")
        except Exception as exc:
            failed += 1
            log("embed_articles", "failed", error=f"Local embedding stage failed. {sanitize(exc)}")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config["retention"]["keep_raw_days"])).isoformat()
    # Preserve compact exchange tags/category/time provenance needed for future reprocessing.
    for r in rows:
        if r["fetched_at"] < cutoff and r["_has_raw"]:
            retained = {
                k: v
                for k, v in r["raw"].items()
                if k in ("exchange_symbol", "category", "origin_exchange", "time_assumption")
            }
            execute(client.table("articles").update({"raw": {}, "provenance": retained}).eq("id", r["id"]))
    return {"articles": len(rows), "failed": failed}
