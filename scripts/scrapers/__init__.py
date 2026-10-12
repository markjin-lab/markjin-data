"""Per-site list-page scrapers for markjin (method: scraper in sources.yaml).

Contract: scrape(fetch, url, date) -> list of {"title", "url", "date"} (newest first, <=50).
`fetch(url)` is provided by capture_sources.run_scraper -> (status, ctype, body, err). Every call
(list page, each sub-sitemap) goes through markjin.collect.Fetcher: honest UA, robots.txt and
host-disable state re-checked on every request and redirect hop, per-host rate limit, t.co refused,
and the raw response bytes are archived privately (MANIFEST) before the scraper sees them.
Scrapers never open network connections themselves. No cookies, no JS, no challenge handling: a challenge
page is detected by the Fetcher (host disabled persistently) and surfaces here as err -> ScrapeError.
"""
import importlib, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from markjin.collect import CHALLENGE  # noqa: E402,F401  验证页识别只维护 collect.CHALLENGE 这一份


class ScrapeError(Exception):
    pass




def check_body(st, body, err):
    if err or st != 200:
        raise ScrapeError(err or f"HTTP {st}")
    if CHALLENGE.search(body[:20000]):
        raise ScrapeError("bot-challenge/interstitial page (not bypassed)")
    return body


def get(name):
    return importlib.import_module(f"{__name__}.{name}")
