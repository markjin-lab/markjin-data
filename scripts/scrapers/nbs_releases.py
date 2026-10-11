"""stats.gov.cn 最新发布 list page (https://www.stats.gov.cn/sj/zxfb/), static HTML.
Article href like ./202610/t20261008_1965465.html -> date from the t-stamp."""
import re
from urllib.parse import urljoin
from . import check_body, ScrapeError


def scrape(fetch, url, date):
    st, ct, body, err = fetch(url)
    s = check_body(st, body, err).decode("utf-8", "replace")
    seen, out = set(), []
    for href, _, title in re.findall(r'<a[^>]+href="(\./\d{6}/t(\d{8})_\d+\.html)"[^>]*title=\'([^\']+)\'', s):
        u = urljoin(url, href)
        if u in seen:
            continue
        seen.add(u)
        d = re.search(r"/t(\d{4})(\d{2})(\d{2})_", u)
        out.append({"title": title.strip(), "url": u, "date": "-".join(d.groups()) if d else ""})
    if not out:
        raise ScrapeError("no release links found (layout changed?)")
    return out[:50]
