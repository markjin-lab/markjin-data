#!/usr/bin/env python3
"""markjin primary-source fetcher for X leads（PR #6 审查 REJECTED 修复版，公共规则见 markjin/collect.py）。

Usage:
  fetch_primary.py --leads LEADS.json --date YYYY-MM-DD --out-root REPO_ROOT
                   --private-root DIR (或 MARKJIN_PRIVATE_DIR) [--license-evidence EVIDENCE.jsonl]
                   [--interval 2.0] [--max 50]

对每条线索的 unwound_url / expanded_url（x.com、t.co、pic 链接忽略；t.co 永不解析）抓一次一手 URL：
  - 经 collect.Fetcher：如实 UA、不自动重定向、每一跳查 robots/停用状态/限速、403 与验证页持久停用、
    429/5xx 有上限退避、超过 25 MiB 明确失败（不存半截）。
  - 原字节 → PRIVATE/raw/DATE/primary/<sha256>.<ext>（独占创建 + MANIFEST.sha256）；提取文本 → 私有派生物。
  - 许可：默认 url+hash-only。域名（arXiv、NASA、.gov/.mil 等）一律不构成许可。只有 --license-evidence 中
    针对该 URL（及最终 URL）的逐条目证据通过 collect.public_fulltext_ok，原字节与带署名的 .txt 才写入公开目录；
    证据随条目记录进公开 index。
  - 公开目录 OUT/raw/DATE/primary/：本次运行独占创建 index-<run>.json、leads-primary-<run>.json，追加 MANIFEST。
    公开记录只含脱敏 URL（去凭证型/跟踪参数）与错误类别；原 URL 只在私有 fetch-log。
线索身份：每条线索保持 label: 线索、source_role: lead；抓取结果只写 fetch_status。HTTP 200 不等于核验：
  primary_verification 恒为 unverified，只有人工/独立核验（来源身份、页面内容、原断言一致）后另行改写。
"""
import argparse, html, json, re, subprocess, sys, tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect, strictjson  # noqa: E402

SKIP_HOSTS = ("x.com", "twitter.com", "t.co", "pic.x.com", "pic.twitter.com", "mobile.twitter.com", "www.x.com")


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


def extract_text(body, ctype):
    if "pdf" in ctype or body[:5] == b"%PDF-":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
            t.write(body); t.flush()
            r = subprocess.run(["pdftotext", "-layout", t.name, "-"], capture_output=True, timeout=120)
        return "", r.stdout.decode("utf-8", "replace")
    if "html" in ctype or body.lstrip()[:1] == b"<":
        m = re.search(rb'charset=["\']?([\w-]+)', body[:2048])
        enc = (m.group(1).decode() if m else None) or "utf-8"
        try: s = body.decode(enc, "replace")
        except LookupError: s = body.decode("utf-8", "replace")
        p = _Text(); p.feed(s)
        t = re.sub(r"[ \t\r\f\v]+", " ", html.unescape("".join(p.out)))
        return p.title.strip(), "\n".join(l.strip() for l in t.splitlines() if l.strip())
    if ctype.startswith("text/"):
        return "", body.decode("utf-8", "replace")
    return "", ""


def primary_urls(lead):
    out = []
    for k in ("unwound_url", "expanded_url"):
        v = lead.get(k)
        for u in (v if isinstance(v, list) else [v] if v else []):
            if isinstance(u, str) and (urlsplit(u).hostname or "").lower() not in SKIP_HOSTS:
                out.append(u)
    for u in lead.get("urls", []) or []:   # optional list of {expanded_url, unwound_url}
        if isinstance(u, dict): out += primary_urls(u)
    return list(dict.fromkeys(out))[:1]   # unwound preferred, one primary per lead


def redact_lead_urls(o):
    """线索里的 URL 字段写出前脱敏（凭证型/跟踪参数），原 URL 只留私有 fetch-log。"""
    for k in ("unwound_url", "expanded_url", "url"):
        v = o.get(k)
        if isinstance(v, str):
            o[k] = collect.public_url(v)
        elif isinstance(v, list):
            o[k] = [collect.public_url(x) if isinstance(x, str) else x for x in v]
    for u in o.get("urls", []) or []:
        if isinstance(u, dict):
            redact_lead_urls(u)


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", required=True); ap.add_argument("--out-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--private-root"); ap.add_argument("--license-evidence")
    ap.add_argument("--interval", type=float, default=collect.HOST_INTERVAL)
    ap.add_argument("--max", type=int, default=50)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print("bad --date", file=sys.stderr); return 2
    try:
        priv_root = collect.resolve_private_root(a.private_root, a.out_root)
        evidence = collect.load_license_evidence(a.license_evidence)
    except (collect.ConfigError, ValueError) as e:
        print(f"config: {type(e).__name__}: {e}", file=sys.stderr); return 2
    doc = strictjson.loads(Path(a.leads).read_text(encoding="utf-8"))
    items = doc["items"] if isinstance(doc, dict) else doc
    run = collect.stamp()
    pub = collect.Archive(Path(a.out_root) / "raw" / a.date)
    priv = collect.Archive(priv_root / "raw" / a.date)
    f = fetcher or collect.Fetcher(collect.HostState(priv_root / "state" / "collector-hosts.json"), interval=a.interval)
    cache, index, plog, n = {}, [], [], 0
    for lead in items:
        lead["label"] = "线索"
        lead["source_role"] = "lead"
        lead["primary_verification"] = "unverified"
        urls = primary_urls(lead)
        if not urls:
            lead["fetch_status"] = "no_primary_link"; continue
        orig = urls[0]
        cu = collect.public_url(orig)
        lead["primary_url"] = cu
        if cu not in cache:
            if n >= a.max:
                lead["fetch_status"] = "not_fetched_cap"; continue
            n += 1
            t0 = collect.now()
            r = f.get(orig)
            rec = {"url": cu, "fetched_at": t0, "http_status": r.status, "license": "url+hash-only",
                   "stored": None, "fetch_status": "fetched" if r.ok else r.error}
            if r.ok:
                fu = collect.public_url(r.final_url or orig)
                ext = collect.ext_for(r.ctype, r.body)
                rel, sha = priv.put_raw("", "primary", r.body, ext)
                title, txt = extract_text(r.body, r.ctype)
                if txt:
                    priv.put_derived("", "primary", sha, "txt", (txt + "\n").encode())
                ev = evidence.get(cu) or evidence.get(fu)
                ok1, why = collect.public_fulltext_ok(ev, cu)
                ok2, why2 = collect.public_fulltext_ok(ev, fu) if fu != cu else (ok1, why)
                rec.update(final_url=fu, sha256=sha, bytes=len(r.body), title=title[:300], stored="private",
                           license_decision=why or why2 or "per-item evidence verified")
                if ok1 and ok2:
                    pub.put_raw("", "primary", r.body, ext)
                    if txt:
                        head = f"Source: {fu}\nLicense: {ev['license']} ({ev['license_url']})\nAttribution: {ev['attribution']}\n\n"
                        pub.put(f"primary/{sha}.txt", (head + txt + "\n").encode())
                    rec.update(stored="public", license=ev["license"],
                               license_evidence={k: ev.get(k) for k in collect.EVIDENCE_FIELDS + ("third_party_excluded",)})
                plog.append({"url": orig, "final_url": r.final_url, "hops": r.hops, "raw": rel})
            index.append(rec)
            print(f"{rec['fetch_status']} {r.status} {rec['stored'] or '-'} {cu}", file=sys.stderr)
            cache[cu] = rec
        rr = cache[cu]
        lead.update(fetch_status=rr["fetch_status"], license=rr["license"], sha256=rr.get("sha256"),
                    fetched_at=rr.get("fetched_at"))
    for lead in items:
        redact_lead_urls(lead)
    pub.put_json(f"primary/index-{run}.json", index)
    if isinstance(doc, dict): doc["items"] = items
    pub.put_json(f"primary/leads-primary-{run}.json", doc)
    if plog:
        priv.put(f"primary/fetch-log-{run}.jsonl", "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in plog).encode())
    c = {}
    for r in cache.values(): c[(r["fetch_status"], r["stored"])] = c.get((r["fetch_status"], r["stored"]), 0) + 1
    print("summary:", json.dumps({f"{s}/{l}": v for (s, l), v in c.items()}, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
