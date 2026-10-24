"""Collect approved recipe pages in an isolated, script-free browser context."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
import yaml
from playwright.sync_api import sync_playwright
from shared.db import get_client
from shared.logbook import log_event
from guard import Blocked, Guard, PageBudget, allowed_url
from extract import html_text
from recipes.releases import links

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",str(ROOT/"browser-agent/.venv/browsers"))


def document(site,url,text,partial=False):
    return {"url":url,"domain":site["domain"],"title":text[:180],"text":text,
            "text_hash":hashlib.sha256(text.encode()).hexdigest(),"content_type":"text/html",
            "extraction_method":"recipe","trust_level":"untrusted",
            "status":"partial" if partial else "ok","meta":{"site_key":site["key"]},
            "job_id":int(os.environ["JOB_ID"]) if os.environ.get("JOB_ID") else None}


def collect(site,defaults,guard,save):
    if site.get("mode")!="recipe" or site.get("recipe")!="releases":
        raise Blocked("No reviewed recipe for this site")
    count=0
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            context=browser.new_context(java_script_enabled=False,accept_downloads=False,
                                        service_workers="block",user_agent=defaults["user_agent"])
            context.route("**/*",guard.route)
            context.route_web_socket("**/*",lambda websocket:websocket.close())
            page=context.new_page()
            page.set_default_navigation_timeout(defaults["page_timeout_seconds"]*1000)
            def visit(url):
                guard.check_time()
                try:
                    page.goto(url,wait_until="domcontentloaded")
                except Exception:
                    raise Blocked(getattr(guard,"blocked_reason","Browser navigation failed; stopped")) from None
                return page.content()
            listing=visit(site["start_url"])
            candidates=links(listing,page.url,site["listing_selector"])
            candidates=[url for url in candidates if allowed_url(url,site) and url!=page.url]
            if not candidates:
                raise Blocked("Recipe found no links within approved paths")
            for url in candidates[:max(0,defaults["max_pages_per_job"]-1)]:
                body=visit(url)
                text,partial=html_text(body,site["content_selector"],defaults["max_text_chars"])
                save(document(site,page.url,text,partial))
                count+=1
        finally:
            browser.close()
    return count


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["list","run"])
    parser.add_argument("--site")
    args=parser.parse_args()
    config=yaml.safe_load((ROOT/"config/browser_allowlist.yaml").read_text())
    if args.command=="list":
        print(json.dumps(config["sites"],indent=2)); return 0
    selected=[s for s in config["sites"] if s["key"]==args.site]
    if len(selected)!=1:
        parser.error("Choose a configured site with --site")
    site=selected[0]
    run_id=str(uuid4())
    budget=PageBudget(ROOT/".cache/browser/page-budget.sqlite")
    try:
        guard=Guard(site,config["defaults"],budget)
        client=get_client()
        count=collect(site,config["defaults"],guard,
            lambda row:client.table("documents").upsert(row,on_conflict="url,text_hash",ignore_duplicates=True).execute())
        log_event(run_id,"browser-agent","collect","success",output_summary=f"Collected {count} untrusted documents")
        print(json.dumps({"documents":count})); return 0
    except Blocked as exc:
        log_event(run_id,"browser-agent","collect","failed",error=str(exc))
        print(json.dumps({"blocked":str(exc)})); return 2
    except Exception:
        log_event(run_id,"browser-agent","collect","failed",error="Collection failed; inspect source configuration and browser installation")
        print('{"failed":"Collection failed"}'); return 1
    finally:
        budget.db.close()


if __name__=="__main__":
    raise SystemExit(main())
