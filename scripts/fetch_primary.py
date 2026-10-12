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
  - 目标地址：初始 URL、DNS 解析结果、每一跳都经 collect.AddressPolicy，拒绝本机/内网/链路本地/保留地址。
    出站经透明代理（DNS 返回 RFC 2544 基准网段 198.18.0.0/15 内的假 IP）时用 --proxy-fakeip-cidr / MARKJIN_PROXY_FAKEIP_CIDR 显式声明，
    只对主机名解析结果放行该网段；IP 字面量永远拒绝。
  - 许可：默认 url+hash-only。域名（arXiv、NASA、.gov/.mil 等）一律不构成许可。只有 --license-evidence 中
    针对*完整* URL（含全部查询参数）并绑定响应 sha256 的逐条目证据通过 collect.public_fulltext_ok——
    原 URL 与最终 URL 各自要有证据——原字节与带署名的 .txt 才写入公开目录；证据（URL 脱敏后）随条目进公开 index。
  - 公开目录 OUT/raw/DATE/primary/：本次运行独占创建 index-<run>.json、leads-primary-<run>.json，追加 MANIFEST。
    leads-primary 只含帖子 id/URL、帖文 sha256、一手 URL（脱敏）与 sha256、fetch_status、线索身份字段；
    帖文原文等完整线索只进私有 PRIVATE/raw/DATE/primary/leads-<run>.json。日志（含私有 fetch-log）只写脱敏 URL。
线索身份：每条线索保持 label: 线索、source_role: lead；抓取结果只写 fetch_status。HTTP 200 不等于核验：
  primary_verification 恒为 unverified，只有人工/独立核验（来源身份、页面内容、原断言一致）后另行改写。
"""
import argparse, hashlib, html, json, os, re, subprocess, sys, tempfile
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


PUBLIC_LEAD_FIELDS = ("id", "url", "text_sha256", "primary_url", "sha256", "fetch_status", "fetched_at", "license",
                      "label", "source_role", "primary_verification")


def public_lead(lead):
    """公开 leads-primary 只留：帖子 id、帖子 URL、帖文 hash、一手 URL（脱敏）与其 sha256、fetch_status、线索身份字段。
    帖文原文、作者、互动数、原始 URL 字段只进私有 leads 档案。"""
    pid = lead.get("id")
    out = {}
    if isinstance(pid, (str, int)) and re.fullmatch(r"[1-9][0-9]{0,19}", str(pid)):   # 只有合法帖子 id 才写 id / url
        out["id"] = str(pid)
        out["url"] = f"https://x.com/i/status/{pid}"
    if isinstance(lead.get("text"), str):
        out["text_sha256"] = hashlib.sha256(lead["text"].encode("utf-8")).hexdigest()
    for k in PUBLIC_LEAD_FIELDS:
        if k in ("id", "url"):        # 输入里的 id / url 不原样复制
            continue
        if k in lead and k not in out:
            out[k] = lead[k]
    # primary_url 在主循环里已是 public_url 形式（主机 + 完整 URL sha256），不再二次处理
    return out


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", required=True); ap.add_argument("--out-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--private-root"); ap.add_argument("--license-evidence")
    ap.add_argument("--interval", type=float, default=collect.HOST_INTERVAL)
    ap.add_argument("--proxy-fakeip-cidr", default=os.environ.get(collect.FAKEIP_ENV),
                    help="仅当出站经透明代理且 DNS 返回假 IP 时设置（必须在 198.18.0.0/15 内，见 README）")
    ap.add_argument("--max", type=int, default=50)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print("bad --date", file=sys.stderr); return 2
    try:
        collect.check_interval(a.interval)          # 先 isfinite（拒绝 nan/inf），再要求 >= 2s
    except collect.ConfigError as e:
        print(f"--interval: {e}", file=sys.stderr); return 2
    try:
        priv_root = collect.resolve_private_root(a.private_root, a.out_root)
        evidence = collect.load_license_evidence(a.license_evidence)
        policy = collect.AddressPolicy(a.proxy_fakeip_cidr)
    except (collect.ConfigError, ValueError) as e:
        print(f"config: {type(e).__name__}: {e}", file=sys.stderr); return 2
    doc = strictjson.loads(Path(a.leads).read_text(encoding="utf-8"))
    items = doc["items"] if isinstance(doc, dict) else doc
    run = collect.stamp()
    pub = collect.Archive(Path(a.out_root) / "raw" / a.date)
    priv = collect.Archive(priv_root / "raw" / a.date)
    f = fetcher or collect.Fetcher(collect.HostState(priv_root / "state" / "collector-hosts.json"),
                                   interval=a.interval, fakeip_cidr=a.proxy_fakeip_cidr or "")
    # 外部传入的 Fetcher：其自带策略与本次强制策略合取（两边都放行才放行），不能用宽松策略绕过
    # （强制策略沿用该 Fetcher 的解析器，保证检查的是它实际会连接的解析结果）
    policy = collect.AddressPolicy(a.proxy_fakeip_cidr, resolver=f.resolver)
    f.addr_policy = collect.AllOf(policy, f.addr_policy)
    cache, index, plog, n = {}, [], [], 0
    for lead in items:
        lead["label"] = "线索"
        lead["source_role"] = "lead"
        lead["primary_verification"] = "unverified"
        urls = primary_urls(lead)
        if not urls:
            lead["fetch_status"] = "no_primary_link"; continue
        orig = urls[0]
        key = collect.full_url_key(orig)          # 缓存/许可均按完整 URL，不按脱敏 URL
        cu = collect.public_url(orig)
        lead["primary_url"] = cu
        if key not in cache:
            if n >= a.max:
                lead["fetch_status"] = "not_fetched_cap"; continue
            n += 1
            t0 = collect.now()
            r = f.get(orig)
            rec = {"url": cu, "fetched_at": t0, "http_status": r.status, "license": "url+hash-only",
                   "stored": None, "fetch_status": "fetched" if r.ok else r.error}
            if r.error == "blocked_address":
                rec["detail"] = "non-public address"
            if r.ok:
                final = r.final_url or orig
                fu = collect.public_url(final)                  # 默认：主机 + 完整 URL sha256
                ext = collect.ext_for(r.ctype, r.body)
                rel, sha = priv.put_raw("", "primary", r.body, ext)
                title, txt = extract_text(r.body, r.ctype)
                if txt:
                    priv.put_derived("", "primary", sha, "txt", (txt + "\n").encode())
                ev_o = evidence.get(key)
                ev_f = evidence.get(collect.full_url_key(final))
                ok1, why = collect.public_fulltext_ok(ev_o, orig, sha)
                same = collect.full_url_key(final) == key
                ok2, why2 = (ok1, why) if same else collect.public_fulltext_ok(ev_f, final, sha)
                rec.update(final_url=fu, sha256=sha, bytes=len(r.body), stored="private",
                           license_decision=why or why2 or "per-item evidence verified (url + sha256)")
                if ok1 and ok2:
                    ev = ev_f if not same else ev_o
                    pub.put_raw("", "primary", r.body, ext)
                    if txt:
                        src = collect.public_url(final, public_path=True)   # 逐条许可证据已人工核实该 URL
                        head = f"Source: {src}\nLicense: {ev['license']} ({collect.public_url(ev['license_url'], public_path=True)})\nAttribution: {ev['attribution']}\n\n"
                        pub.put(f"primary/{sha}.txt", (head + txt + "\n").encode())
                    shown = {k: ev.get(k) for k in collect.EVIDENCE_FIELDS + ("third_party_excluded",)}
                    # 证据各 URL 经人工核实（逐条确认），才写出路径；查询值仍去掉
                    shown["url"] = collect.public_url(shown["url"], public_path=True)
                    shown["evidence_url"] = collect.public_url(shown["evidence_url"], public_path=True)
                    shown["license_url"] = collect.public_url(shown["license_url"], public_path=True)
                    rec["final_url"] = collect.public_url(final, public_path=True)
                    # 正文派生字段（title）只在逐条许可通过、stored=public 时才进公开 index
                    rec.update(stored="public", license=ev["license"], license_evidence=shown, title=title[:300])
                # 私有 fetch-log 也只写脱敏 URL；完整原 URL 只在私有 leads 原始档案里
                plog.append({"url": cu, "final_url": fu, "hops": r.hops, "raw": rel, "title": title[:300]})
            index.append(rec)
            print(f"{rec['fetch_status']} {r.status} {rec['stored'] or '-'} {cu}", file=sys.stderr)
            cache[key] = rec
        rr = cache[key]
        lead.update(fetch_status=rr["fetch_status"], license=rr["license"], sha256=rr.get("sha256"),
                    fetched_at=rr.get("fetched_at"))
    priv.put_json(f"primary/leads-{run}.json", doc)              # 完整线索（含帖文）只进私有档案
    pub.put_json(f"primary/index-{run}.json", index)
    pub_doc = {"items": [public_lead(x) for x in items]}
    pub.put_json(f"primary/leads-primary-{run}.json", pub_doc)
    if plog:
        priv.put(f"primary/fetch-log-{run}.jsonl", "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in plog).encode())
    c = {}
    for r in cache.values(): c[(r["fetch_status"], r["stored"])] = c.get((r["fetch_status"], r["stored"]), 0) + 1
    print("summary:", json.dumps({f"{s}/{l}": v for (s, l), v in c.items()}, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
