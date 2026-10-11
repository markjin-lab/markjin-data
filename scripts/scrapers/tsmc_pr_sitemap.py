"""pr.tsmc.com: no RSS; robots.txt allows / and lists a Google-News sitemap.
Intermittently answers with a Cloudflare challenge -> ScrapeError (not bypassed)."""
import re
from . import check_body


def scrape(fetch, url, date):
    st, ct, body, err = fetch(url)
    s = check_body(st, body, err).decode("utf-8", "replace")
    out = []
    for blk in re.findall(r"<url>(.*?)</url>", s, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", blk)
        if not loc or "/news/" not in loc.group(1):
            continue
        t = re.search(r"<news:title>([^<]*)</news:title>", blk)
        d = re.search(r"<news:publication_date>([^<]*)", blk)
        out.append({"title": (t.group(1) if t else "").strip(), "url": loc.group(1).strip(),
                    "date": (d.group(1) if d else "")[:10]})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:50]
