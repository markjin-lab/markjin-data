#!/usr/bin/env python3
"""markjin primary-source fetcher for X leads.

Usage:
  fetch_primary.py --leads raw/DATE/x/leads.json --out-root OUT [--private-root /workspace/markjin/private]
                   [--out leads-primary.json] [--delay 2.0] [--max 50]

For each lead with expanded_url/unwound_url (x.com / t.co / pic links ignored), fetch the
primary URL once (dedup by canonical URL, utm_* stripped), honouring robots.txt, one request
per host every --delay seconds, no cookies/credentials.
License rule:
  full-text-ok  : arxiv.org abs/pdf, *.nasa.gov, other US federal *.gov / *.mil
                  -> bytes + extracted .txt under OUT/primary/<sha12>.*
  url+hash-only : everything else -> bytes (+txt) under PRIVATE/primary/<sha12>.*;
                  OUT/primary/index.json carries url, sha256, fetched_at, license only.
Writes leads-primary.json (default OUT/leads-primary.json): each lead gets primary_url,
primary_status ('可用' | '失败' | 'robots禁止' | '无一手链接'), license, sha256, fetched_at.
t.co is never resolved (its robots.txt disallows all agents).
"""
import argparse, datetime as dt, hashlib, html, json, re, subprocess, sys, time
import urllib.request, urllib.error, urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

UA = "Mozilla/5.0 (X11; Linux x86_64) markjin-capture/1.0 (+primary-source fetch)"
SKIP_HOSTS = ("x.com", "twitter.com", "t.co", "pic.x.com", "pic.twitter.com")
MAX_BYTES = 25 * 1024 * 1024


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canon(u):
    p = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k not in ("linkId", "s", "ref_src")]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(q), ""))


def license_for(u):
    p = urlsplit(u); h = p.netloc.lower().split(":")[0]
    if h in ("arxiv.org", "www.arxiv.org", "export.arxiv.org") and re.match(r"^/(abs|pdf)/", p.path):
        return "full-text-ok"
    if h == "nasa.gov" or h.endswith(".nasa.gov"):
        return "full-text-ok"
    if h.endswith(".gov") or h.endswith(".mil"):
        return "full-text-ok"  # US federal works (17 USC 105); third-party material excluded
    return "url+hash-only"


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self):
        super().__init__(); self.out = []; self.depth = 0; self.title = ""; self._t = False

    def handle_starttag(self, tag, a):
        if tag in self.SKIP: self.depth += 1
        if tag == "title": self._t = True
        if tag in self.BLOCK: self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth: self.depth -= 1
        if tag == "title": self._t = False

    def handle_data(self, d):
        if self._t: self.title += d
        elif not self.depth: self.out.append(d)


def extract_text(body, ctype, tmp):
    if "pdf" in ctype or body[:5] == b"%PDF-":
        tmp.write_bytes(body)
        r = subprocess.run(["pdftotext", "-layout", str(tmp), "-"], capture_output=True, timeout=120)
        tmp.unlink(missing_ok=True)
        return "", r.stdout.decode("utf-8", "replace")
    if "html" in ctype or body.lstrip()[:1] == b"<":
        m = re.search(rb'charset=["\']?([\w-]+)', body[:2048])
        enc = (m.group(1).decode() if m else None) or "utf-8"
        try: s = body.decode(enc, "replace")
        except LookupError: s = body.decode("utf-8", "replace")
        p = _Text(); p.feed(s)
        t = re.sub(r"[ \t\r\f\v]+", " ", html.unescape("".join(p.out)))
        t = "\n".join(l.strip() for l in t.splitlines() if l.strip())
        return p.title.strip(), t
    if ctype.startswith("text/"):
        return "", body.decode("utf-8", "replace")
    return "", ""


_robots = {}


def allowed(u):
    p = urlsplit(u); base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            rp.allow_all = e.code in (404, 410)   # missing robots = allowed; 401/403/5xx = treat as disallow
            rp.disallow_all = not rp.allow_all
        except Exception:
            rp.disallow_all = True
        _robots[base] = rp
    return _robots[base].can_fetch(UA, u)


_last = {}


def fetch(u, delay, timeout=30):
    h = urlsplit(u).netloc
    w = delay - (time.time() - _last.get(h, 0))
    if w > 0: time.sleep(w)
    _last[h] = time.time()
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "text/html,application/pdf,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read(MAX_BYTES), r.geturl(), None
    except urllib.error.HTTPError as e:
        return e.code, "", b"", u, f"HTTP {e.code}"
    except Exception as e:
        return 0, "", b"", u, f"{type(e).__name__}: {str(e)[:160]}"


def primary_urls(lead):
    out = []
    for k in ("unwound_url", "expanded_url"):
        v = lead.get(k)
        for u in (v if isinstance(v, list) else [v] if v else []):
            if urlsplit(u).netloc.lower().split(":")[0] not in SKIP_HOSTS:
                out.append(u)
    for u in lead.get("urls", []) or []:   # optional list of {expanded_url, unwound_url}
        if isinstance(u, dict): out += primary_urls(u)
    return list(dict.fromkeys(out))[:1]   # unwound preferred, one primary per lead


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", required=True); ap.add_argument("--out-root", required=True)
    ap.add_argument("--private-root", default="/workspace/markjin/private")
    ap.add_argument("--out"); ap.add_argument("--delay", type=float, default=2.0)
    ap.add_argument("--max", type=int, default=50)
    a = ap.parse_args(argv)
    doc = json.loads(Path(a.leads).read_text())
    items = doc["items"] if isinstance(doc, dict) else doc
    pub = Path(a.out_root) / "primary"; priv = Path(a.private_root) / "primary"
    pub.mkdir(parents=True, exist_ok=True)
    idx_p = pub / "index.json"
    index = json.loads(idx_p.read_text()) if idx_p.exists() else []
    cache, n = {}, 0
    for lead in items:
        urls = primary_urls(lead)
        if not urls:
            lead.setdefault("primary_status", "无一手链接"); continue
        cu = canon(urls[0]); lead["primary_url"] = cu
        if cu not in cache:
            if n >= a.max:
                lead["primary_status"] = "未抓取(超出上限)"; continue
            lic = license_for(cu); rec = {"url": cu, "license": lic}
            if not allowed(cu):
                rec.update(status="robots禁止", fetched_at=now())
            else:
                n += 1
                t0 = now(); st, ct, body, final, err = fetch(cu, a.delay)
                rec.update(fetched_at=t0, http_status=st, final_url=canon(final))
                if st == 200 and body:
                    sha = hashlib.sha256(body).hexdigest(); rec["sha256"] = sha; rec["bytes"] = len(body)
                    lic = rec["license"] = license_for(final) if license_for(cu) == "full-text-ok" else lic
                    d = pub if lic == "full-text-ok" else priv; d.mkdir(parents=True, exist_ok=True)
                    ext = ".pdf" if ("pdf" in ct or body[:5] == b"%PDF-") else ".html"
                    (d / (sha[:12] + ext)).write_bytes(body)
                    title, txt = extract_text(body, ct, d / (sha[:12] + ".tmp"))
                    if txt:
                        (d / (sha[:12] + ".txt")).write_text(txt + "\n")
                    rec.update(status="可用", title=title[:300], text_chars=len(txt),
                               stored="public" if d == pub else "private")
                    index.append({k: rec.get(k) for k in ("url", "final_url", "sha256", "fetched_at", "license", "bytes")})
                else:
                    rec.update(status="失败", error=err or f"HTTP {st}")
                print(f"{rec['status']} {rec.get('http_status','-')} {lic} {cu}", file=sys.stderr)
            cache[cu] = rec
        r = cache[cu]
        lead.update(primary_status=r["status"], license=r["license"], sha256=r.get("sha256"),
                    fetched_at=r.get("fetched_at"), primary_error=r.get("error"))
        if r["status"] == "可用":
            lead["label"] = "线索+一手来源"
    idx_p.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n")
    out = Path(a.out) if a.out else Path(a.out_root) / "leads-primary.json"
    if isinstance(doc, dict): doc["items"] = items
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    c = {}
    for r in cache.values(): c[(r["status"], r["license"])] = c.get((r["status"], r["license"]), 0) + 1
    print("summary:", json.dumps({f"{s}/{l}": v for (s, l), v in c.items()}, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
