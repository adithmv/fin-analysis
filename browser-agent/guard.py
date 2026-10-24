"""Fail-closed network guard, shared by recipes, PDF fetches and model browsing."""

from datetime import datetime
import ipaddress
from pathlib import Path
import socket
import sqlite3
import time
from urllib.parse import unquote, urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo
import httpx


class Blocked(RuntimeError):
    pass


def allowed_url(url, site):
    try:
        parsed=urlsplit(url)
        if parsed.scheme!="https" or parsed.hostname!=site["domain"] or parsed.port not in (None,443) or parsed.username or parsed.password:
            return False
        path=parsed.path or "/"
        for _ in range(4):
            decoded=unquote(path)
            if decoded==path:
                break
            path=decoded
        if "%" in path or "\\" in path or any(part in (".","..") for part in path.split("/")) or any(ord(c)<32 for c in url):
            return False
        return any(path==prefix.rstrip("/") or path.startswith(prefix.rstrip("/")+"/") for prefix in site["allowed_path_prefixes"])
    except (ValueError,KeyError):
        return False


def check_public_host(host):
    addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise Blocked("Destination is not a public network address")


def blocked_page(status, text):
    sample=text[:12000].lower()
    return status in (401,403,429) or any(phrase in sample for phrase in
        ("verify you are human","access denied","request rejected","captcha","unusual traffic","bot detection"))


class PageBudget:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path,timeout=10)
        self.db.execute("create table if not exists visits(domain text,day text,n integer,last real,primary key(domain,day))")
        self.db.commit()

    def reserve(self,domain,limit,delay,now=None):
        now=time.time() if now is None else now
        day=datetime.fromtimestamp(now,ZoneInfo("Asia/Kolkata")).date().isoformat()
        try:
            self.db.execute("begin immediate")
            row=self.db.execute("select n,last from visits where domain=? and day=?",(domain,day)).fetchone()
            if row and row[0]>=limit:
                raise Blocked("Daily page limit reached")
            wait=max(0,delay-(now-row[1])) if row else 0
            if wait:
                self.db.rollback()
                return wait
            self.db.execute("insert into visits values(?,?,1,?) on conflict(domain,day) do update set n=n+1,last=excluded.last",(domain,day,now))
            self.db.commit()
            return 0
        except BaseException:
            self.db.rollback()
            raise


class Guard:
    def __init__(self,site,defaults,budget,transport=None,resolve=check_public_host):
        if not site.get("enabled") or not site.get("terms_checked_on"):
            raise Blocked(site.get("disabled_reason","Site disabled or terms not reviewed"))
        self.site,self.config,self.budget=site,defaults,budget
        self.transport,self.resolve=transport,resolve
        self.robots=None
        self.pages=0
        self.started=time.monotonic()

    def check_time(self):
        if time.monotonic()-self.started>self.config["job_timeout_seconds"]:
            raise Blocked("Job runtime limit reached")

    def _request(self,url,maximum):
        self.check_time()
        self.resolve(urlsplit(url).hostname)
        # No browser cookies, credentials, redirects or user-controlled headers.
        with httpx.Client(timeout=self.config["page_timeout_seconds"],follow_redirects=False,
                          transport=self.transport,trust_env=False) as client:
            with client.stream("GET",url,headers={"User-Agent":self.config["user_agent"]}) as response:
                if response.status_code in (401,403,429):
                    raise Blocked(f"Source refused access ({response.status_code}); no retry")
                body=bytearray()
                for chunk in response.iter_bytes():
                    self.check_time()
                    body.extend(chunk)
                    if len(body)>maximum:
                        raise Blocked("Response exceeds byte limit")
                return response.status_code,dict(response.headers),bytes(body)

    def check_robots(self,url):
        if not allowed_url(url,self.site):
            raise Blocked("URL outside the approved domain or path")
        if self.robots is None:
            status,headers,body=self._request(f"https://{self.site['domain']}/robots.txt",200000)
            text=body.decode("utf-8",errors="replace")
            if status!=200 or "text/plain" not in headers.get("content-type","") or blocked_page(status,text):
                raise Blocked("robots.txt unavailable or refused; fail closed")
            parser=RobotFileParser()
            parser.parse(text.splitlines())
            self.robots=parser
        if not self.robots.can_fetch(self.config["user_agent"],url):
            raise Blocked("robots.txt disallows this path")

    def fetch(self,url,pdf=False):
        for _ in range(4):
            self.check_time()
            self.check_robots(url)
            if self.pages>=self.config["max_pages_per_job"]:
                raise Blocked("Job page cap reached")
            delay=max(4,self.config["min_seconds_between_pages"],self.robots.crawl_delay(self.config["user_agent"]) or 0)
            while wait:=self.budget.reserve(self.site["domain"],self.config["max_pages_per_day_per_domain"],delay):
                if wait>self.config["job_timeout_seconds"]-(time.monotonic()-self.started):
                    raise Blocked("Crawl delay exceeds remaining runtime")
                time.sleep(min(wait,30))
                self.check_time()
            self.pages+=1
            status,headers,body=self._request(url,self.config["max_pdf_bytes"] if pdf else self.config["max_html_bytes"])
            if status in (301,302,303,307,308):
                url=urljoin(url,headers.get("location",""))
                continue # Every redirect is checked again before any request.
            if status!=200:
                raise Blocked(f"Unexpected source status {status}; no retry")
            mime=headers.get("content-type","").split(";")[0]
            if pdf:
                if not self.site.get("pdf_allowed") or mime!="application/pdf" or not body.startswith(b"%PDF-"):
                    raise Blocked("Only explicitly allowed PDF downloads are accepted")
            elif mime not in ("text/html","text/plain") or blocked_page(status,body.decode("utf-8",errors="replace")):
                raise Blocked("Unexpected content or access challenge; stopped")
            return url,mime,body
        raise Blocked("Redirect limit reached")

    def route(self,route):
        request=route.request
        if request.method not in ("GET","HEAD") or request.resource_type!="document":
            route.abort()
            return
        try:
            final,mime,body=self.fetch(request.url)
            if final!=request.url:
                # Do not render content under a different origin/path from its real URL.
                route.fulfill(status=302,headers={"location":final},body="")
            else:
                route.fulfill(status=200,content_type=mime,body=body,
                    headers={"Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; frame-src 'none'"})
        except Blocked as exc:
            self.blocked_reason=str(exc)
            route.abort()
        except Exception:
            self.blocked_reason="Network request failed; stopped without retry"
            route.abort()
