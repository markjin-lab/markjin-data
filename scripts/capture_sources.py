#!/usr/bin/env python3
"""markjin P0 source capture（审查 REJECTED 修复版，规则见 scripts/markjin/collect.py）。

Usage:
  capture_sources.py --sources improve/sources.yaml --date YYYY-MM-DD --round 1|2 \
      --private-root DIR (或环境变量 MARKJIN_PRIVATE_DIR) [--out-root REPO_ROOT] \
      [--internal-root DIR (或 MARKJIN_INTERNAL_DIR)] [--only id1,id2] [--interval 2.0]

只采集 approval_gate 通过的源（enabled + approval_status: approved + approval_basis），method rss/api/scraper。
scraper（`scraper: <module>` → scripts/scrapers/<module>.py）：scraper 内每个请求（列表页、子 sitemap）都经同一个
Fetcher（逐跳 robots、限速、停用），每个原始响应先按字节私有存档并登记 MANIFEST；条目 JSON 只作派生物
（derived/，带 derived_from 原件 sha256），公开 index 只记列表页 URL 与原件 sha256。
未通过审批的源一律拒绝（--only 点名未审批源 → 退出码 1）。
每次响应：
  原字节（不解压、不脱敏）→ PRIVATE/raw/DATE/[round2/]<id>/<sha256>.<ext>，独占创建，追加 PRIVATE/raw/DATE/MANIFEST.sha256；
  gzip 原件的解压结果只作派生物（derived/，登记 DERIVED.sha256）；
  公开目录 OUT/raw/DATE/[round2/]：本次运行独占创建 <id>/index-<run>.json（url+sha256+fetched_at+license）、
  query-log-<run>.jsonl、failures-<run>.json，并追加 OUT/raw/DATE/MANIFEST.sha256。整份 RSS/API 响应是多条目聚合，
  不做逐条许可核验，因此全文永不进公开目录（逐条全文见 fetch_primary.py 的 license evidence）。
  internal_only 源：原件与记录全部写入内部目录，公开目录不写任何东西。
公开记录不含本机路径与凭证型 URL 参数（stored 只写 private/internal）。
需要免费密钥的 API：auth_env（环境变量名）+ auth_param（查询参数名），密钥只在请求时拼接，不进任何记录。
403 / 验证页 → 持久停用（PRIVATE/state/collector-hosts.json），人工复核后删除条目才恢复。
Exit code: 0 = all ok, 1 = 有失败或拒绝, 2 = 参数/配置错误.
"""
import argparse, datetime as dt, gzip, json, os, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect, strictjson  # noqa: E402

METHODS = ("rss", "api", "scraper")


def parse_ok(body):
    """严格解析：JSON 用 strictjson（重复键判失败），XML 用 ElementTree。返回 json / xml / None。"""
    b = body
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except OSError:
            return None
    b = b.lstrip(b"\xef\xbb\xbf \r\n\t")
    try:
        if b[:1] in (b"{", b"["):
            strictjson.loads(b.decode("utf-8"))
            return "json"
        if b[:1] == b"<":
            ET.fromstring(b)
            return "xml"
    except (ValueError, ET.ParseError, UnicodeDecodeError):
        return None
    return None


def expand_url(url, date):
    """Placeholders: {date} = target date, {date-N} = target date minus N days (YYYY-MM-DD)."""
    d0 = dt.date.fromisoformat(date)
    return re.sub(r"\{date(?:-(\d+))?\}", lambda m: (d0 - dt.timedelta(days=int(m.group(1) or 0))).isoformat(), url)


def day_dir(root, date):
    root = Path(root)
    if root.name != "raw":
        root = root / "raw"
    return root / date


def request_url(s, url):
    env, param = s.get("auth_env"), s.get("auth_param")
    if not env:
        return url, None
    key = os.environ.get(env)
    if not key or not param:
        return None, "missing_credential"
    return url + ("&" if "?" in url else "?") + urlencode({param: key}), None


def run_scraper(fetcher, raw_ar, sub, sid, s, url):
    """返回 (Result, raw_records)。Result.body = 条目 JSON（派生物），raw_records = 每个原始响应的存档记录。"""
    import scrapers
    raws = []

    def fetch(u):
        r = fetcher.get(u, sid=sid)
        if r.ok:
            rel, sha = raw_ar.put_raw(sub, sid, r.body, collect.ext_for(r.ctype, r.body))
            raws.append({"url": collect.public_url(u), "raw": rel, "sha256": sha})
        return r.status, r.ctype, r.body, (None if r.ok else (r.error or f"http_{r.status}"))
    try:
        items = scrapers.get(s["scraper"]).scrape(fetch, url, None, **(s.get("scraper_args") or {}))
    except Exception as e:
        return collect.Result(False, error=f"scraper:{type(e).__name__}", detail=str(e)[:160]), raws
    if not items:
        return collect.Result(False, error="scraper:no_items"), raws
    return collect.Result(True, 200, "application/json",
                          json.dumps(items, ensure_ascii=False).encode()), raws


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--round", type=int, choices=(1, 2), required=True)
    ap.add_argument("--out-root", default=".")
    ap.add_argument("--private-root")
    ap.add_argument("--internal-root")
    ap.add_argument("--only", default="")
    ap.add_argument("--interval", type=float, default=collect.HOST_INTERVAL,
                    help=f"每主机最小间隔秒数，下限 {collect.HOST_INTERVAL}")
    ap.add_argument("--timeout", type=float, default=30)
    a = ap.parse_args(argv)
    if a.interval < collect.HOST_INTERVAL:
        print(f"--interval must be >= {collect.HOST_INTERVAL}", file=sys.stderr); return 2
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print("bad --date", file=sys.stderr); return 2
    try:
        priv_root = collect.resolve_private_root(a.private_root, a.out_root)
        int_root = collect.resolve_internal_root(a.internal_root, a.out_root)
    except collect.ConfigError as e:
        print(f"config: {e}", file=sys.stderr); return 2
    srcs = (yaml.safe_load(open(a.sources, encoding="utf-8")) or {}).get("sources", [])
    only = {x for x in a.only.split(",") if x}
    run = collect.stamp()
    sub = "round2/" if a.round == 2 else ""
    fetcher = collect.Fetcher(collect.HostState(priv_root / "state" / "collector-hosts.json"),
                              interval=a.interval, timeout=a.timeout)
    pub_ar = collect.Archive(day_dir(a.out_root, a.date))
    priv_ar = collect.Archive(day_dir(priv_root, a.date))
    int_ar = collect.Archive(day_dir(int_root, a.date)) if int_root else None
    logs = {"public": [], "internal": []}
    fails = {"public": [], "internal": []}
    raw_logs = {"public": [], "internal": []}
    n_ok = n_bad = 0
    for s in srcs:
        sid = s["id"]
        if only and sid not in only:
            continue
        if s.get("method") not in METHODS:
            if sid in only:
                print(f"REFUSED {sid}: method {s.get('method')} not capturable here", file=sys.stderr); n_bad += 1
            continue
        ok, why = collect.approval_gate(s)
        if not ok:
            if sid in only or s.get("enabled"):
                print(f"REFUSED {sid}: {why}", file=sys.stderr); n_bad += 1
            continue
        internal = bool(s.get("internal_only"))
        if internal and int_ar is None:
            print(f"REFUSED {sid}: internal_only source needs --internal-root / MARKJIN_INTERNAL_DIR", file=sys.stderr)
            n_bad += 1; continue
        raw_ar = int_ar if internal else priv_ar
        where = "internal" if internal else "public"
        url = expand_url(s["url"], a.date)
        lic = s.get("license", "url+hash-only")
        t0 = collect.now()
        raws = []
        if s["method"] == "scraper":
            r, raws = run_scraper(fetcher, raw_ar, sub, sid, s, url)
            kind = "json" if r.ok else None
            sha = raws[0]["sha256"] if raws else None
            rec = {"id": sid, "theme": s.get("theme"), "url": collect.public_url(url), "round": a.round,
                   "fetched_at": t0, "http_status": r.status, "bytes": None, "raw_count": len(raws), "sha256": sha,
                   "license": lic, "content_type": "scraper", "raw_responses": [x["sha256"] for x in raws]}
            if raws:
                rec["stored"] = "internal" if internal else "private"
                raw_logs[where].append({"id": sid, "run": run, "raws": raws, "url": collect.public_url(url)})
            if r.ok:
                raw_ar.put_derived(sub, sid, sha, f"items-{run}.json", r.body)
        else:
            req_url, cred_err = request_url(s, url)
            r = collect.Result(False, error=cred_err) if cred_err else fetcher.get(req_url, sid=sid)
            rec = {"id": sid, "theme": s.get("theme"), "url": collect.public_url(url), "round": a.round,
                   "fetched_at": t0, "http_status": r.status, "bytes": len(r.body), "sha256": r.sha256,
                   "license": lic, "content_type": r.ctype, "redirects": len(r.hops)}
            kind = parse_ok(r.body) if r.ok else None
            if r.ok:   # 每个成功响应的原字节都先私有存档（不论能否解析）
                ext = collect.ext_for(r.ctype, r.body)
                rel, sha = raw_ar.put_raw(sub, sid, r.body, ext)
                if ext == "gz" and kind:
                    raw_ar.put_derived(sub, sid, sha, kind, gzip.decompress(r.body))
                rec["stored"] = "internal" if internal else "private"
                raw_logs[where].append({"id": sid, "run": run, "raw": rel, "url": collect.public_url(url), "parsed": kind,
                                        "final_url": collect.public_url(r.final_url or url), "hops": r.hops})
        if r.ok and kind:
            (int_ar if internal else pub_ar).put_json(
                f"{sub}{sid}/index-{run}.json",
                [{"id": sid, "url": rec["url"], "sha256": sha, "fetched_at": t0, "bytes": rec["bytes"],
                  "license": lic, "round": a.round, "stored": rec["stored"], "method": s["method"]}])
            n_ok += 1
            print(f"OK  {sid} {r.status} {len(r.body)}B", file=sys.stderr)
        else:
            rec["error"] = r.error or "unparseable"
            fails[where].append({k: rec[k] for k in ("id", "url", "fetched_at", "http_status", "error")})
            n_bad += 1
            print(f"ERR {sid} {r.status} {rec['error']}", file=sys.stderr)
        logs[where].append(rec)
    for where, ar in (("public", pub_ar), ("internal", int_ar)):
        if ar is None or not (logs[where] or fails[where]):
            continue
        ar.put(f"{sub}query-log-{run}.jsonl",
               "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logs[where]).encode())
        ar.put_json(f"{sub}failures-{run}.json", fails[where])
    for where, ar in (("public", priv_ar), ("internal", int_ar)):
        if raw_logs[where]:
            ar.put(f"{sub}fetch-log-{run}.jsonl",
                   "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in raw_logs[where]).encode())
    print(f"done: ok={n_ok} failed_or_refused={n_bad}", file=sys.stderr)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
