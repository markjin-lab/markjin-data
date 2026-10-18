"""Generic official-sitemap lister (robots.txt-declared sitemaps only).
scraper_args: {pattern: <regex on loc>, index: true|false}. Root must be sitemaps.org-namespaced urlset/sitemapindex
(no DOCTYPE/ENTITY); a nested index beyond one level is an error. Follows one sitemap-index level; each sub-sitemap is a separate fetch (robots re-checked). Only robots-disallowed
or 404/410 sub-sitemaps are skipped; challenge / 401/403 / source blocked / URL already failed this round / blocked address
abort the whole run (marked failed).
Returns entries matching pattern, newest lastmod first (entries without lastmod keep sitemap order)."""
import re
import xml.etree.ElementTree as ET
from . import check_body, ScrapeError
from markjin.collect import xml_root  # noqa: E402  含 DOCTYPE/ENTITY 的 XML 一律拒收

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
URLSET, INDEX = NS + "urlset", NS + "sitemapindex"     # 只认 sitemaps.org 命名空间下的完整 QName
SKIPPABLE = {"robots_disallow", "http_404", "http_410"}
MAX_DEPTH = 1                                           # 只跟一层 sitemap index


def _parse(body):
    """200 的 sitemap 必须是合法 XML（不含 DOCTYPE/ENTITY），根元素为 sitemaps.org 命名空间的 urlset 或
    sitemapindex；否则 ScrapeError（本轮失败）。"""
    b = body.lstrip(b"\xef\xbb\xbf \r\n\t")
    try:
        xml_root(b)
        root = ET.fromstring(b)
    except ValueError:
        raise ScrapeError("not a sitemap (DOCTYPE/ENTITY refused)")
    except ET.ParseError:
        raise ScrapeError("not a sitemap (XML unparseable)")
    if root.tag not in (URLSET, INDEX):
        raise ScrapeError(f"not a sitemap (root {root.tag[:80]})")
    return root


def _entries(fetch, url, depth=0):
    st, ct, body, err = fetch(url)
    root = _parse(check_body(st, body, err))
    if root.tag == INDEX:
        if depth >= MAX_DEPTH:              # 嵌套超限：报错，不当成 0 条
            raise ScrapeError(f"sitemap index nested deeper than {MAX_DEPTH}")
        out = []
        for sm in root.findall(NS + "sitemap")[:5]:
            loc = (sm.findtext(NS + "loc") or "").strip()
            if not loc:
                raise ScrapeError("sitemap index entry without loc")
            try:   # 每个子 sitemap 都经 fetch（逐个查 robots/源状态/本轮失败 URL/限速）
                out += _entries(fetch, loc, depth + 1)
            except ScrapeError as e:
                if str(e) in SKIPPABLE:      # 只有明确允许跳过的错误才跳过（robots 不允许、子 sitemap 不存在）
                    continue
                raise                        # challenge / 401/403 / 源被拦 / 地址被拒 / 非法 sitemap → 本轮整体失败
        return out
    out = []
    for u in root.findall(NS + "url"):
        loc = (u.findtext(NS + "loc") or "").strip()
        if loc:
            out.append((loc, (u.findtext(NS + "lastmod") or "").strip()[:10]))
    return out


def scrape(fetch, url, date, pattern=".*", **_):
    rx = re.compile(pattern)
    out = [{"title": u.rstrip("/").rsplit("/", 1)[-1].replace("-", " "), "url": u, "date": d}
           for u, d in _entries(fetch, url) if rx.search(u)]
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:50]
