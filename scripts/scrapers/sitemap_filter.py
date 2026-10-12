"""Generic official-sitemap lister (robots.txt-declared sitemaps only).
scraper_args: {pattern: <regex on loc>, index: true|false}. Follows one sitemap-index level; each sub-sitemap is a separate fetch (robots re-checked, disallowed ones skipped).
Returns entries matching pattern, newest lastmod first (entries without lastmod keep sitemap order)."""
import re
from . import check_body, ScrapeError


def _entries(fetch, url, depth=0):
    st, ct, body, err = fetch(url)
    s = check_body(st, body, err).decode("utf-8", "replace")
    if "<sitemapindex" in s[:500] and depth == 0:
        out = []
        for loc in re.findall(r"<sitemap>\s*<loc>([^<]+)</loc>", s)[:5]:
            try:   # 每个子 sitemap 都经 fetch（逐个查 robots/停用/限速）；被拒的子 sitemap 跳过，不绕过
                out += _entries(fetch, loc.strip(), 1)
            except ScrapeError:
                continue
        return out
    return [(loc.strip(), (lm or "")[:10]) for loc, lm in
            re.findall(r"<url>\s*<loc>([^<]+)</loc>(?:(?:(?!</url>).)*?<lastmod>([^<]+)</lastmod>)?", s, re.S)]


def scrape(fetch, url, date, pattern=".*", **_):
    rx = re.compile(pattern)
    out = [{"title": u.rstrip("/").rsplit("/", 1)[-1].replace("-", " "), "url": u, "date": d}
           for u, d in _entries(fetch, url) if rx.search(u)]
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:50]
