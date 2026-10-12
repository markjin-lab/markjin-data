"""anthropic.com: no official RSS; robots.txt allows all and declares sitemap.xml.
Thin wrapper over sitemap_filter for /news/ and /research/ posts."""
from .sitemap_filter import scrape as _s


def scrape(fetch, url, date, **kw):
    return _s(fetch, url, date, pattern=r"^https://www\.anthropic\.com/(news|research)/[^/]+$")
