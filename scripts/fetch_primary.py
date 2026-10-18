#!/usr/bin/env python3
"""markjin primary-source fetcher for X leads（PR #6 审查 REJECTED 修复版，公共规则见 markjin/collect.py）。

Usage:
  fetch_primary.py --leads LEADS.json --date YYYY-MM-DD --round 1|2 --out-root REPO_ROOT
                   --private-root DIR (或 MARKJIN_PRIVATE_DIR) [--license-evidence EVIDENCE.jsonl]
                   [--interval 2.0] [--max 50]

对每条线索的 unwound_url / expanded_url（x.com、t.co、pic 链接忽略；t.co 永不解析）抓一次一手 URL：
  - 经 collect.Fetcher：如实 UA、不自动重定向、每一跳查 robots/源状态/主机停用与本轮停止/URL 冷却/站点限速、
    收到任何 HTTP 状态都不重发（只有网络错误有限重试）、超过 25 MiB 明确失败（不存半截）。
  - 封锁规则（现行版，出处与细则见 markjin/collect.py「封锁规则与来源健康状态」）：401/403、429、验证页、登录墙
    → 该主机本轮全部停止、被拒 URL 冷却 ≥24 小时；未公布限速的站点每站每分钟最多 1 次（OUT/improve/sources.yaml 的
    site_rate_limits 写明依据的除外）。文章按返回可疑响应那一跳的主机归入伪源 primary:<主机> 计数（r14 ⑩）；
    同一伪源最近 5 轮 3 轮可疑 → pending-disable（下一轮起），写公开 primary/source-health-<run>.json 与
    primary/GROK-BOT-REVIEW-<run>.md（当天汇报照抄），stderr 打 PENDING-DISABLE，交 Grok Bot 复核。
    旧 collector-hosts.json 有未迁移条目 → 拒绝运行（先 source_health.py migrate）；已迁移的停用主机不请求（host_disabled）。
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
Exit code: 0 = ok, 1 = 来源健康状态更新失败（StateError/OSError；上层须停下）, 2 = 参数/配置错误或拒绝运行.
"""
import argparse, hashlib, html, json, os, re, subprocess, sys, tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml  # noqa: E402

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


def primary_sid(url):
    """文章抓取的伪源 id：primary:<主机>（与 sources.yaml 的源 id 分开计数）。"""
    return f"primary:{collect.host_of(url) or 'unknown'}"


PUBLIC_LEAD_FIELDS = ("id", "url", "text_sha256", "primary_url", "sha256", "fetch_status", "fetched_at", "license",
                      "label", "source_role", "primary_verification")


GENERATED_FIELDS = ("primary_url", "sha256", "fetch_status", "fetched_at", "license", "label", "source_role",
                    "primary_verification")


def public_lead(lead, gen):
    """公开 leads-primary 只用本轮生成的字段构造，不从输入复制任何字段：
    id / url 由校验过的帖子 id 生成，text_sha256 由帖文计算，其余只取本轮生成的 gen（一手 URL 的
    public_url 形式与其 sha256、fetch_status、线索身份字段）。帖文原文、作者、互动数、原始 URL 只进私有档案。"""
    pid = lead.get("id")
    out = {}
    if isinstance(pid, (str, int)) and re.fullmatch(r"[1-9][0-9]{0,19}", str(pid)):   # 只有规范正整数 id 才写 id / url
        out["id"] = str(pid)
        out["url"] = f"https://x.com/i/status/{pid}"
    if isinstance(lead.get("text"), str):
        out["text_sha256"] = hashlib.sha256(lead["text"].encode("utf-8")).hexdigest()
    for k in GENERATED_FIELDS:
        if k in gen:
            out[k] = gen[k]
    return out


def main(argv=None, fetcher=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads", required=True); ap.add_argument("--out-root", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--round", type=int, choices=(1, 2), required=True)
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
    rid = collect.round_id(a.date, a.round)
    if fetcher is None:
        try:     # 旧 collector-hosts.json 有未迁移条目或损坏 → 拒绝运行（先 source_health.py migrate）
            st0 = collect.open_source_health(priv_root)
        except (collect.StateError, OSError) as e:
            print(f"source health: {e}; refusing to run", file=sys.stderr); return 2
        try:     # 只认 sources.yaml 里写明公布限额和依据的站点；其余每站每分钟 1 次
            cfg_p = Path(a.out_root) / "improve" / "sources.yaml"
            site_limits = collect.load_site_limits(
                (yaml.safe_load(cfg_p.read_text(encoding="utf-8")) or {}).get("site_rate_limits")) if cfg_p.exists() else collect.load_site_limits(None)
        except (collect.ConfigError, yaml.YAMLError, AttributeError) as e:
            print(f"config: site_rate_limits: {e}", file=sys.stderr); return 2
    f = fetcher or collect.Fetcher(st0,
                                   interval=a.interval, fakeip_cidr=a.proxy_fakeip_cidr or "",
                                   lock_dir=priv_root / "state" / "locks", round_id=rid,    # 站点/URL 跨进程锁
                                   site_limits=site_limits)
    health = f.state
    # 外部传入的 Fetcher：其自带策略与本次强制策略合取（两边都放行才放行），不能用宽松策略绕过
    # （强制策略沿用该 Fetcher 的解析器，保证检查的是它实际会连接的解析结果）
    policy = collect.AddressPolicy(a.proxy_fakeip_cidr, resolver=f.resolver)
    f.addr_policy = collect.AllOf(policy, f.addr_policy)
    cache, index, plog, n, gens = {}, [], [], 0, []
    for lead in items:
        g = {"label": "线索", "source_role": "lead", "primary_verification": "unverified"}   # 本轮生成的字段
        gens.append(g)
        for k in GENERATED_FIELDS:      # 输入里预填的同名字段不保留（私有档案里另存为 input_*）
            if k in lead:
                lead[f"input_{k}"] = lead.pop(k)
        lead.update(g)
        urls = primary_urls(lead)
        if not urls:
            g["fetch_status"] = lead["fetch_status"] = "no_primary_link"; continue
        orig = urls[0]
        key = collect.full_url_key(orig)          # 缓存/许可均按完整 URL，不按脱敏 URL
        cu = collect.public_url(orig)
        g["primary_url"] = lead["primary_url"] = cu
        if key not in cache:
            if n >= a.max:
                g["fetch_status"] = lead["fetch_status"] = "not_fetched_cap"; continue
            n += 1
            t0 = collect.now()
            hop_raws = []

            def sink(body, st, ctype, _acc=hop_raws):     # 每一跳原字节先私有存档，再决定丢弃/跳转
                rel_h, sha_h = priv.put_raw("", "primary", body, collect.ext_for(ctype, body))
                _acc.append({"raw": rel_h, "sha256": sha_h, "status": st})
            # r14 ⑩：按每一跳的主机给伪源 id，可疑记在返回可疑响应那一跳的主机上
            r = f.get(orig, sid=lambda host: f"primary:{host or 'unknown'}", raw_sink=sink)
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
                plog.append({"url": cu, "final_url": fu, "hops": r.hops, "raw": rel, "title": title[:300],
                             "hop_raws": hop_raws})
            elif hop_raws:
                plog.append({"url": cu, "error": r.error, "hops": r.hops, "hop_raws": hop_raws})
            index.append(rec)
            print(f"{rec['fetch_status']} {r.status} {rec['stored'] or '-'} {cu}", file=sys.stderr)
            cache[key] = rec
        rr = cache[key]
        g.update(fetch_status=rr["fetch_status"], license=rr["license"], sha256=rr.get("sha256"),
                 fetched_at=rr.get("fetched_at"))
        lead.update(g)
    # 本轮实际发出过请求（或有可疑事件）的伪源各记一轮；没发请求的（冷却、主机已停、停用）不记
    psids = {s for s in set(f.contacted) | set(f.suspicious) if isinstance(s, str) and s.startswith("primary:")}
    ran = {sid: sorted({e["reason"] for e in f.suspicious.get(sid, [])}) for sid in psids}
    health_failed = False
    try:
        newly = health.record_round(rid, ran) if ran else {}
        report = health.report(sids=set(ran) | {primary_sid(x["url"]) for x in index if x.get("fetch_status") == "source_blocked"})
    except (collect.StateError, OSError) as e:
        print(f"source health not updated: {type(e).__name__}: {e}", file=sys.stderr)
        newly, report = {}, []
        health_failed = True            # r15（#60）MEDIUM：健康状态没更新 → 退出码非 0，让上层停下
    if report:
        pub.put_json(f"primary/source-health-{run}.json", [dict(e, newly_flagged=bool(newly.get(e["id"]))) for e in report])
    pend = [e for e in report if e["status"] == "pending-disable"]
    if pend:            # 当天汇报显眼可见：单独一份 Markdown + stderr 一行，写 capture-failures.md 时照抄
        pub.put(f"primary/GROK-BOT-REVIEW-{run}.md", collect.review_md(a.date, a.round, pend, newly).encode())
    for e in pend:
        print(f"PENDING-DISABLE {e['id']}: {e['suspicious_rounds_in_window']} of the last {e['window']} rounds suspicious "
              f"— flag for Grok Bot review (confirm-disable or enable)", file=sys.stderr)
    if pend:
        print(f"=== 待 Grok Bot 复核（pending-disable）{len(pend)} 个源：{', '.join(e['id'] for e in pend)} "
              f"— 详见 primary/GROK-BOT-REVIEW-{run}.md，请写进当天 capture-failures.md ===", file=sys.stderr)
    priv.put_json(f"primary/leads-{run}.json", doc)              # 完整线索（含帖文）只进私有档案
    pub.put_json(f"primary/index-{run}.json", index)
    pub_doc = {"items": [public_lead(x, g) for x, g in zip(items, gens)]}
    pub.put_json(f"primary/leads-primary-{run}.json", pub_doc)
    if plog:
        priv.put(f"primary/fetch-log-{run}.jsonl", "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in plog).encode())
    c = {}
    for r in cache.values(): c[(r["fetch_status"], r["stored"])] = c.get((r["fetch_status"], r["stored"]), 0) + 1
    print("summary:", json.dumps({f"{s}/{l}": v for (s, l), v in c.items()}, ensure_ascii=False),
          f"pending_disable={len(pend)}", file=sys.stderr)
    if health_failed:
        print("source health update failed; exiting 1 so the caller stops", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
