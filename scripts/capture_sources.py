#!/usr/bin/env python3
"""markjin P0 source capture（审查 REJECTED 修复版，规则见 scripts/markjin/collect.py）。

Usage:
  capture_sources.py --sources improve/sources.yaml --date YYYY-MM-DD --round 1|2 \
      --private-root DIR (或环境变量 MARKJIN_PRIVATE_DIR) [--out-root REPO_ROOT] \
      [--internal-root DIR (或 MARKJIN_INTERNAL_DIR)] [--only id1,id2] [--interval 2.0]

只采集 approval_gate 通过的源（enabled + approval_status: approved + approval_basis），method rss/api。
未通过审批的源一律拒绝（--only 点名未审批源 → 退出码 1）。
每次响应：
  原字节（不解压、不脱敏）→ PRIVATE/raw/DATE/[round2/]<id>/<sha256>.<ext>，独占创建，追加 PRIVATE/raw/DATE/MANIFEST.sha256；
  gzip 原件的解压结果只作派生物（derived/，登记 DERIVED.sha256）；
  公开目录 OUT/raw/DATE/[round2/]：本次运行独占创建 <id>/index-<run>.json（url+sha256+fetched_at+license）、
  query-log-<run>.jsonl、failures-<run>.json，并追加 OUT/raw/DATE/MANIFEST.sha256。整份 RSS/API 响应是多条目聚合，
  不做逐条许可核验，因此全文永不进公开目录（逐条全文见 fetch_primary.py 的 license evidence）。
  internal_only 源：原件与记录全部写入内部目录，公开目录不写任何东西。
公开与私有记录都不含本机路径，URL 不带查询值（只记参数个数 query_param_count，不记参数名）；某源确需公开的参数值须在
sources.yaml 里按源声明 public_params: [name, ...]。URL 默认只写 scheme://主机/#sha256=<完整 URL 的 sha256>；
逐源确认路径不含凭证后，声明 public_path: true 才写出路径。stored 只写 private/internal。
地址策略强制生效（每一跳）：拒绝本机/内网/链路本地/保留地址；经透明代理时用 --proxy-fakeip-cidr 或
$MARKJIN_PROXY_FAKEIP_CIDR 声明代理假 IP 网段（只接受 198.18.0.0/15 内）。
需要免费密钥的 API：auth_env（环境变量名）+ auth_param（查询参数名），密钥只在请求时拼接，不进任何记录。
封锁规则（出处与细则见 scripts/markjin/collect.py「封锁规则与来源健康状态」；状态在 PRIVATE/state/source-health.json）：
  单次可疑（401/403、429、验证页、登录墙、rss/api 格式校验不通过）→ 该主机本轮全部停止、被拒 URL（含跳转起点）冷却 ≥24 小时，
  不重试；同一源最近 5 轮有 3 轮可疑 → pending-disable：当轮写 source-health-<run>.json（flag: grok-bot-review）与
  GROK-BOT-REVIEW-<run>.md，stderr 打 PENDING-DISABLE 和「待 Grok Bot 复核」一行（写进当天 capture-failures.md）；
  下一轮起不再请求，直到人工 confirm-disable 或 enable（scripts/source_health.py）。
  未公布限速的站点每站每分钟最多 1 次（跨进程）；sources.yaml 顶层 site_rate_limits 写明公布限额和依据的站点按其限额。
  旧 PRIVATE/state/collector-hosts.json 存在且未迁移 → 拒绝运行（退出码 2），先 source_health.py migrate；
  迁移后其中主机全部保持停用（host_disabled），不请求、不计数、不自动恢复。不绕过付费墙、登录或验证。
Exit code: 0 = all ok, 1 = 有失败或拒绝, 2 = 参数/配置错误.
"""
import argparse, datetime as dt, gzip, json, os, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import collect, strictjson  # noqa: E402

NO_REQUEST = ("source_blocked", "host_disabled", "host_stopped_this_round", "url_cooldown")   # 没发请求的拦截
METHODS = ("rss", "api")


def parse_ok(body):
    """严格解析：JSON 用 strictjson（重复键判失败、顶层须为对象或数组），XML 用 ElementTree（含 DOCTYPE/ENTITY
    拒收）。返回 json / xml / None。"""
    b = body
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except OSError:
            return None
    b = b.lstrip(b"\xef\xbb\xbf \r\n\t")
    if b[:1] in (b"{", b"["):
        return "json" if collect.json_ok(b) else None
    if b[:1] == b"<":
        try:
            collect.xml_root(b)
            return "xml"
        except (ValueError, ET.ParseError):
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
    ap.add_argument("--proxy-fakeip-cidr", default=os.environ.get(collect.FAKEIP_ENV),
                    help="仅当出站经透明代理且 DNS 返回 RFC 2544 假 IP 时设置（必须在 198.18.0.0/15 内）")
    a = ap.parse_args(argv)
    try:
        collect.check_interval(a.interval)          # 先 isfinite（拒绝 nan/inf），再要求 >= 2s
    except collect.ConfigError as e:
        print(f"--interval: {e}", file=sys.stderr); return 2
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print("bad --date", file=sys.stderr); return 2
    try:
        priv_root = collect.resolve_private_root(a.private_root, a.out_root)
        int_root = collect.resolve_internal_root(a.internal_root, a.out_root)
        collect.AddressPolicy(a.proxy_fakeip_cidr)  # 校验代理假 IP 网段配置（错误 → 退出码 2）
    except (collect.ConfigError, ValueError) as e:
        print(f"config: {e}", file=sys.stderr); return 2
    cfg = yaml.safe_load(open(a.sources, encoding="utf-8")) or {}
    srcs = cfg.get("sources", [])
    try:
        site_limits = collect.load_site_limits(cfg.get("site_rate_limits"))   # 只认写明公布限额和依据的站点
    except collect.ConfigError as e:
        print(f"config: {e}", file=sys.stderr); return 2
    only = {x for x in a.only.split(",") if x}
    run = collect.stamp()
    sub = "round2/" if a.round == 2 else ""
    rid = collect.round_id(a.date, a.round)
    try:
        health = collect.open_source_health(priv_root)   # 旧 collector-hosts.json 未迁移 → 拒绝运行（先 source_health.py migrate）
    except (collect.StateError, OSError) as e:
        print(f"source health: {e}; refusing to run", file=sys.stderr)
        return 2
    fetcher = collect.Fetcher(health, interval=a.interval, timeout=a.timeout, fakeip_cidr=a.proxy_fakeip_cidr or "",
                              lock_dir=priv_root / "state" / "locks", round_id=rid,
                              site_limits=site_limits)   # SEC 等主机组的跨进程限速锁放在私有目录
    # 地址策略（addr_policy）由 Fetcher 强制安装：每一跳、scraper 的子 sitemap 都在请求前检查
    pub_ar = collect.Archive(day_dir(a.out_root, a.date))
    priv_ar = collect.Archive(day_dir(priv_root, a.date))
    int_ar = collect.Archive(day_dir(int_root, a.date)) if int_root else None
    logs = {"public": [], "internal": []}
    fails = {"public": [], "internal": []}
    raw_logs = {"public": [], "internal": []}
    skipped = {"public": [], "internal": []}
    n_ok = n_bad = 0
    where_of = {}                # 源 → public / internal
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
        where_of[sid] = where
        url = expand_url(s["url"], a.date)
        lic = s.get("license", "url+hash-only")
        pp = s.get("public_params") or ()
        ppath = s.get("public_path") is True       # 逐源确认路径不含凭证后才公开路径
        purl = collect.public_url(url, pp, ppath)
        t0 = collect.now()
        req_url, cred_err = request_url(s, url)
        if cred_err:
            r = collect.Result(False, error=cred_err)
        else:
            hop_raws = []

            def sink(body, st, ctype, _ar=raw_ar, _sid=sid, _acc=hop_raws):   # 每一跳原字节先私有存档
                rel_h, sha_h = _ar.put_raw(sub, _sid, body, collect.ext_for(ctype, body))
                _acc.append({"raw": rel_h, "sha256": sha_h, "status": st})
            def validate(ctype, body, _s=s):     # r15 ④：rss/api 格式校验与停止写入在 URL 锁（及站点限速锁）内完成
                return collect.content_suspect(_s["method"], {"Content-Type": ctype}, body, _s.get("format"),
                                               _s.get("xml_roots"))
            r = fetcher.get(req_url, sid=sid, raw_sink=sink, validate=validate)
        if r.error == "not_configured":   # 例如 SEC 未设 MARKJIN_SEC_USER_AGENT：不发请求、不停用，记为未配置
            skipped[where].append({"id": sid, "url": purl, "reason": "not_configured", "detail": r.detail})
            print(f"SKIP {sid} not_configured: {r.detail}", file=sys.stderr)
            continue
        if r.error in NO_REQUEST and not r.hops:
            # 源停用 / 状态损坏 / 旧表停用主机 / 本轮主机已停 / URL 冷却：没发请求，列入跳过，不计入可疑轮数
            skipped[where].append({"id": sid, "url": purl, "reason": r.error, "detail": r.detail})
            print(f"SKIP {sid} {r.error}: {r.detail}", file=sys.stderr)
            n_bad += 1
            continue
        rec = {"id": sid, "theme": s.get("theme"), "url": purl, "query_param_count": collect.query_count(url), "round": a.round,
               "fetched_at": t0, "http_status": r.status, "bytes": len(r.body), "sha256": r.sha256,
               "license": lic, "content_type": r.ctype, "redirects": len(r.hops)}
        # 格式校验不通过（suspected_challenge:<原因>）已在 fetcher.get 的锁内判定并写停止，这里 r.ok 为 False
        kind = parse_ok(r.body) if r.ok else None
        if r.ok:   # 每个成功响应的原字节都先私有存档（不论能否解析）
            ext = collect.ext_for(r.ctype, r.body)
            rel, sha = raw_ar.put_raw(sub, sid, r.body, ext)
            if ext == "gz" and kind:
                raw_ar.put_derived(sub, sid, sha, kind, gzip.decompress(r.body))
            rec["stored"] = "internal" if internal else "private"
            raw_logs[where].append({"id": sid, "run": run, "raw": rel, "url": purl, "parsed": kind,
                                    "final_url": collect.public_url(r.final_url or url, pp, ppath), "hops": r.hops,
                                    "hop_raws": hop_raws})
        elif not cred_err and hop_raws:   # 失败/验证页/跳转中途的响应原字节也已私有存档，登记到私有 fetch-log
            raw_logs[where].append({"id": sid, "run": run, "url": purl, "error": r.error, "hops": r.hops,
                                    "hop_raws": hop_raws})
        if r.ok and kind:
            (int_ar if internal else pub_ar).put_json(
                f"{sub}{sid}/index-{run}.json",
                [{"id": sid, "url": rec["url"], "sha256": sha, "fetched_at": t0, "bytes": len(r.body),
                  "license": lic, "round": a.round, "stored": rec["stored"]}])
            n_ok += 1
            print(f"OK  {sid} {r.status} {len(r.body)}B", file=sys.stderr)
        else:
            rec["error"] = r.error or "unparseable"
            fails[where].append({k: rec[k] for k in ("id", "url", "fetched_at", "http_status", "error")})
            n_bad += 1
            print(f"ERR {sid} {r.status} {rec['error']}", file=sys.stderr)
        logs[where].append(rec)
    for where, ar in (("public", pub_ar), ("internal", int_ar)):
        if ar is not None and skipped[where]:
            ar.put_json(f"{sub}skipped-{run}.json", skipped[where])
        if ar is None or not (logs[where] or fails[where]):
            continue
        ar.put(f"{sub}query-log-{run}.jsonl",
               "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logs[where]).encode())
        ar.put_json(f"{sub}failures-{run}.json", fails[where])
    for where, ar in (("public", priv_ar), ("internal", int_ar)):
        if raw_logs[where]:
            ar.put(f"{sub}fetch-log-{run}.jsonl",
                   "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in raw_logs[where]).encode())
    # 逐源可疑计数：本轮实际请求过的源各记一轮；最近 5 轮 3 轮可疑 → pending-disable 并写报告
    # 本轮实际发出过请求（或有可疑事件）的源各记一轮；没发请求的源（冷却、主机已停、停用）不记
    ran = {sid: sorted({e["reason"] for e in fetcher.suspicious.get(sid, [])})
           for sid in where_of if sid in fetcher.contacted or fetcher.suspicious.get(sid)}
    try:
        newly = health.record_round(rid, ran) if ran else {}
        report = health.report(sids=set(where_of))
    except (collect.StateError, OSError) as e:
        print(f"source health not updated: {type(e).__name__}: {e}", file=sys.stderr)
        newly, report = {}, []
        n_bad += 1
    for where, ar in (("public", pub_ar), ("internal", int_ar)):
        entries = [dict(e, newly_flagged=bool(newly.get(e["id"]))) for e in report if where_of.get(e["id"]) == where]
        if ar is not None and entries:
            ar.put_json(f"{sub}source-health-{run}.json", entries)
    pend = [e for e in report if e["status"] == "pending-disable"]
    for where, ar in (("public", pub_ar), ("internal", int_ar)):
        mine = [e for e in pend if where_of.get(e["id"]) == where]
        if ar is not None and mine:      # 当天汇报里显眼可见：单独一份 Markdown，写日报 capture-failures.md 时照抄
            ar.put(f"{sub}GROK-BOT-REVIEW-{run}.md", collect.review_md(a.date, a.round, mine, newly).encode())
    for e in pend:
        print(f"PENDING-DISABLE {e['id']}: {e['suspicious_rounds_in_window']} of the last {e['window']} rounds suspicious "
              f"— flag for Grok Bot review (confirm-disable or enable)", file=sys.stderr)
    if pend:
        print(f"=== 待 Grok Bot 复核（pending-disable）{len(pend)} 个源：{', '.join(e['id'] for e in pend)} "
              f"— 详见 {sub}GROK-BOT-REVIEW-{run}.md，请写进当天 capture-failures.md ===", file=sys.stderr)
    print(f"done: ok={n_ok} failed_or_refused={n_bad} pending_disable={len(pend)}", file=sys.stderr)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
