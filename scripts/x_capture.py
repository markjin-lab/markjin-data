#!/usr/bin/env python3
"""markjin X capture helper: 计划 / 额度预留 / 结果入账 / 补全批次 / 线索导出（PR #6 审查 REJECTED 修复版）。

X 调用由 agent 经动态 `x` 命名空间发起（CallDynamicTool, write_to_file=true）；本脚本不直接访问 X。
**每一次实际工具调用（首页、翻页、get_posts_by_ids 补全）之前都必须先 `reserve`**：
脚本检查每日上限与每分钟上限，通过才登记并返回 call_id；`ingest` / `ingest-hydrate` 只接受已预留、未入账的 call_id。

Commands:
  plan    --queries Q.json --state S.json --date YYYY-MM-DD --round 1|2
          按 improve/x-queries.md 自动计算窗口（round1: 当日 05:00 SGT − 48h = D−3 21:00Z；round2: D−1 21:00Z），
          把每个查询的完整参数写入状态，输出首页调用清单（不消耗额度）。
  reserve --state S.json --tool search_posts_all|get_posts_by_ids [--slug SLUG --page N]
          -> {"allowed": true, "call_id": ...} 或 {"allowed": false, "reason", "wait_s"}（退出码 3）
  ingest  --state S.json --call-id ID --file RESULT.txt
          -> {"next": {...完整参数（从状态恢复）+ next_token...}} 或 {"next": null, "reason"}
  hydrate --state S.json                       -> get_posts_by_ids 批次（≤100 id/批；每批调用前同样要 reserve）
  ingest-hydrate --state S.json --call-id ID --file RESULT.txt
  leads   --state S.json                       -> 线索 JSON，每条固定 label: 线索, source_role: lead
  budget  --state S.json                       -> 今日（UTC 日，00:00Z 重置）已用 / 剩余 / 需等待秒数
预算：≤400 次 / UTC 日（X 额度 00:00Z 重置，05:00 与 06:00 SGT 两轮在同一额度日），≤25 次 / 滚动 60 秒。
页数上限（x-queries.md「翻页」节）：账号批次 4 页、主题 2 页（两轮相同）。

Verified 2026-10-12 06:2x SGT: search_posts_all max_results ≤25；翻页参数 next_token；search 不返回 entities，
需 get_posts_by_ids（≤100 id）补全 entities.urls[].expanded_url/unwound_url；t.co 永不自行解析。
"""
import argparse, datetime as dt, json, re, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import strictjson  # noqa: E402

DAY_CAP, MIN_CAP = 400, 25
PAGE_CAP = {1: {"account": 4, "topic": 2}, 2: {"account": 4, "topic": 2}}
TOOLS = ("search_posts_all", "get_posts_by_ids")
HYDRATE_BATCH = 100
BASE_ARGS = {"max_results": 25, "post.fields": "created_at,author_id,public_metrics,entities,referenced_tweets",
             "expansions": "author_id", "user.fields": "username"}
UTC = dt.timezone.utc


class UsageError(Exception):
    pass


def window_start(date, rnd):
    d = dt.date.fromisoformat(date)
    five_sgt_utc = dt.datetime(d.year, d.month, d.day, tzinfo=UTC) - dt.timedelta(hours=3)   # 当日 05:00 SGT = D−1 21:00Z
    t = five_sgt_utc - dt.timedelta(hours=48) if rnd == 1 else five_sgt_utc
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state(p):
    p = Path(p)
    s = strictjson.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in (("calls", []), ("ids", []), ("queries", {}), ("posts", {})):
        s.setdefault(k, v)
    return s


def save_state(p, s):
    p = Path(p)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


def parse_result(path):
    """CallDynamicTool write_to_file 结果：取出 JSON 正文，严格解析（重复键判失败）。"""
    txt = Path(path).read_text(encoding="utf-8")
    i = txt.index("{")
    body = txt[i:].split("\nX reads left")[0]
    body = body[: body.rindex("}") + 1]
    j = strictjson.loads(body)
    quota = re.search(r"(\d+) of (\d+) this minute.*?(\d+) of (\d+) today", txt, re.S)
    return j, (tuple(map(int, quota.groups())) if quota else None)


def used_today(s, now=None):
    now = now or time.time()
    today = dt.datetime.fromtimestamp(now, UTC).date()
    return sum(1 for c in s["calls"] if dt.datetime.fromtimestamp(c["t"], UTC).date() == today)


def wait_needed(s, now=None):
    now = now or time.time()
    recent = [c["t"] for c in s["calls"] if now - c["t"] < 60]
    if len(recent) < MIN_CAP:
        return 0.0
    return round(60 - (now - sorted(recent)[-MIN_CAP]) + 0.5, 1)


def reserve(s, tool, slug=None, page=None, now=None):
    if tool not in TOOLS:
        raise UsageError(f"unknown tool {tool}")
    now = now or time.time()
    if used_today(s, now) >= DAY_CAP:
        return {"allowed": False, "reason": f"daily cap {DAY_CAP} (resets 00:00Z)"}
    w = wait_needed(s, now)
    if w > 0:
        return {"allowed": False, "reason": f"per-minute cap {MIN_CAP}", "wait_s": w}
    cid = uuid.uuid4().hex[:12]
    s["calls"].append({"id": cid, "t": now, "tool": tool, "slug": slug, "page": page, "ingested": False})
    return {"allowed": True, "call_id": cid}


def _take_call(s, cid, tool):
    for c in s["calls"]:
        if c.get("id") == cid:
            if c["tool"] != tool:
                raise UsageError(f"call {cid} was reserved for {c['tool']}")
            if c["ingested"]:
                raise UsageError(f"call {cid} already ingested")
            c["ingested"] = True
            return c
    raise UsageError(f"call {cid} was never reserved (every X call must be reserved first)")


def cmd_plan(a, s):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        raise UsageError("--date must be YYYY-MM-DD")
    start = window_start(a.date, a.round)
    q = strictjson.loads(Path(a.queries).read_text(encoding="utf-8"))  # [{"slug","kind","query","sort_order"?}]
    out = []
    for e in q:
        if e["kind"] not in PAGE_CAP[1]:
            raise UsageError(f"bad kind {e['kind']}")
        args = dict(BASE_ARGS, query=e["query"], start_time=start, sort_order=e.get(
            "sort_order", "recency" if e["kind"] == "account" else "relevancy"))
        s["queries"][e["slug"]] = {"kind": e["kind"], "round": a.round, "date": a.date, "args": args,
                                   "pages": 0, "posts": 0}
        out.append({"slug": e["slug"], "kind": e["kind"], "page": 1, "tool": "search_posts_all", "args": args})
    return out


def cmd_reserve(a, s):
    r = reserve(s, a.tool, a.slug, a.page)
    return r, (0 if r["allowed"] else 3)


def cmd_ingest(a, s):
    c = _take_call(s, a.call_id, "search_posts_all")
    slug = c["slug"]
    if slug not in s["queries"]:
        raise UsageError(f"slug {slug} not planned")
    qs = s["queries"][slug]
    j, quota = parse_result(a.file)
    data = j.get("data", []) or []
    known = set(s["ids"])
    new = [d["id"] for d in data if d["id"] not in known]
    s["ids"].extend(new)
    for d in data:
        s["posts"].setdefault(d["id"], {k: d.get(k) for k in ("id", "text", "author_id", "created_at", "public_metrics")})
        s["posts"][d["id"]]["query"] = slug
    qs["pages"] = c["page"] or qs["pages"] + 1
    qs["posts"] += len(data)
    tok = (j.get("meta") or {}).get("next_token")
    cap = PAGE_CAP[qs["round"]][qs["kind"]]
    reason = None
    if not tok:
        reason = "no next_token"
    elif qs["pages"] >= cap:
        reason = f"page cap {cap} (round {qs['round']} {qs['kind']})"
    elif used_today(s) >= DAY_CAP:
        reason = f"daily cap {DAY_CAP}"
    elif quota and quota[0] <= 1:
        reason = "X per-minute quota exhausted; retry after reset"
    elif not new and data:
        reason = "page added no new ids"
    if reason:
        return {"next": None, "reason": reason, "new_ids": len(new)}
    args = dict(qs["args"])          # 完整参数从状态恢复，不依赖人工传入
    args.pop("pagination_token", None)
    args["next_token"] = tok
    return {"next": {"slug": slug, "kind": qs["kind"], "page": qs["pages"] + 1, "tool": "search_posts_all",
                     "args": args, "wait_s": wait_needed(s)}, "new_ids": len(new)}


def cmd_hydrate(a, s):
    ids = [i for i in s["ids"] if "urls" not in s["posts"].get(i, {})]
    return [{"tool": "get_posts_by_ids", "args": {"ids": ",".join(ids[i:i + HYDRATE_BATCH]),
             "post.fields": "entities,created_at,note_tweet"}} for i in range(0, len(ids), HYDRATE_BATCH)]


def cmd_ingest_hydrate(a, s):
    _take_call(s, a.call_id, "get_posts_by_ids")
    j, _ = parse_result(a.file)
    n = 0
    for d in j.get("data", []) or []:
        p = s["posts"].setdefault(d["id"], {"id": d["id"]})
        p["urls"] = [{"expanded_url": u.get("expanded_url"), "unwound_url": u.get("unwound_url")}
                     for u in ((d.get("entities") or {}).get("urls") or [])]
        n += 1
    return {"hydrated": n}


def cmd_leads(a, s):
    return {"items": [dict(p, label="线索", source_role="lead") for p in s["posts"].values()]}


def cmd_budget(a, s):
    u = used_today(s)
    return {"used_today_utc": u, "remaining": DAY_CAP - u, "wait_s": wait_needed(s)}


def main(argv=None):
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--queries", required=True); p.add_argument("--state", required=True)
    p.add_argument("--date", required=True); p.add_argument("--round", type=int, choices=(1, 2), required=True)
    p.set_defaults(f=cmd_plan, mut=True)
    p = sp.add_parser("reserve"); p.add_argument("--state", required=True)
    p.add_argument("--tool", choices=TOOLS, required=True); p.add_argument("--slug"); p.add_argument("--page", type=int)
    p.set_defaults(f=cmd_reserve, mut=True)
    for n, f in (("ingest", cmd_ingest), ("ingest-hydrate", cmd_ingest_hydrate)):
        p = sp.add_parser(n); p.add_argument("--state", required=True); p.add_argument("--call-id", required=True)
        p.add_argument("--file", required=True); p.set_defaults(f=f, mut=True)
    for n, f in (("hydrate", cmd_hydrate), ("budget", cmd_budget), ("leads", cmd_leads)):
        p = sp.add_parser(n); p.add_argument("--state", required=True); p.set_defaults(f=f, mut=False)
    a = ap.parse_args(argv)
    try:
        s = load_state(a.state)
        r = a.f(a, s)
    except (UsageError, ValueError, KeyError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr); return 2
    rc = 0
    if isinstance(r, tuple):
        r, rc = r
    if a.mut:
        save_state(a.state, s)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return rc


if __name__ == "__main__":
    sys.exit(main())
