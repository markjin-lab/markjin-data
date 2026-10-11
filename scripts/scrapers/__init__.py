"""Per-site list-page scrapers for markjin (method: scraper in sources.yaml).

Contract: scrape(fetch, url, date) -> list of {"title", "url", "date"} (newest first, <=50).
`fetch(url)` is capture_sources.fetch bound with timeout -> (status, ctype, body, err).
Rules: plain HTTP GET with a declared UA, robots.txt checked by the caller, no cookies,
no JS execution, no challenge/captcha handling. A challenge/interstitial page is a failure
(raise ScrapeError), never something to work around.
"""
import importlib, re


class ScrapeError(Exception):
    pass


CHALLENGE = re.compile(rb"Just a moment\.\.\.|challenges\.cloudflare\.com|Access Denied</TITLE>|captcha", re.I)


def check_body(st, body, err):
    if st != 200:
        raise ScrapeError(err or f"HTTP {st}")
    if CHALLENGE.search(body[:20000]):
        raise ScrapeError("bot-challenge/interstitial page (not bypassed)")
    return body


def get(name):
    return importlib.import_module(f"{__name__}.{name}")
