#!/usr/bin/env python3
"""markjin X capture helper: 计划 / 额度预留 / 结果入账 / 补全批次 / 线索导出（PR #6 审查 REJECTED 修复版）。

X 调用由 agent 经动态 `x` 命名空间发起（CallDynamicTool, write_to_file=true）；本脚本不直接访问 X。
**每一次实际工具调用（首页、翻页、get_posts_by_ids 补全）之前都必须先 `reserve`**：
脚本检查每日上限与每分钟上限，通过才登记并返回 call_id；`ingest` / `ingest-hydrate` 只接受已预留、未入账的 call_id。

Commands:
  plan    --queries Q.json --state S.json --date YYYY-MM-DD --round 1|2
          按 improve/x-queries.md 自动计算窗口（round1: 当日 05:00 SGT − 48h = D−3 21:00Z；round2: D−1 21:00Z），
          把每个查询的完整参数写入状态，输出首页调用清单（不消耗额度）。
  reserve --state S.json --tool search_posts_all --slug SLUG --page N   （N 必须恰为该 slug 的下一页且 ≤ 页数上限）
  reserve --state S.json --tool get_posts_by_ids --batch K               （K = hydrate 输出的批次号）
          [--args JSON] 可选核对实际参数
          -> {"allowed": true, "call_id", "args"（本次必须使用的完整参数）, "args_digest"} 或
             {"allowed": false, "reason", "wait_s"}（退出码 3）；未计划 slug、错页码、超页数、错批次 → 退出码 2
  ingest  --state S.json --call-id ID --file RESULT.txt
          -> {"next": {...完整参数（从状态恢复）+ next_token...}} 或 {"next": null, "reason"}
  hydrate --state S.json                       -> get_posts_by_ids 批次（≤100 id/批，带批次号；每批调用前 reserve --batch）
  ingest-hydrate --state S.json --call-id ID --file RESULT.txt
  leads   --state S.json                       -> 线索 JSON（按 like≥20 / RT≥5 / 白名单作者过滤；含帖文，只写私有目录），
                                                  每条固定 label: 线索, source_role: lead
  budget  --state S.json                       -> 今日（UTC 日，00:00Z 重置）已用 / 剩余 / 需等待秒数
预算：≤400 次 / UTC 日（X 额度 00:00Z 重置，05:00 与 06:00 SGT 两轮在同一额度日），≤25 次 / 滚动 60 秒。
页数上限（x-queries.md「翻页」节）：账号批次 4 页、主题 2 页（两轮相同）。

Verified 2026-10-12 06:2x SGT: search_posts_all max_results ≤25；翻页参数 next_token；search 不返回 entities，
需 get_posts_by_ids（≤100 id）补全 entities.urls[].expanded_url/unwound_url；t.co 永不自行解析。
"""
import argparse, datetime as dt, hashlib, json, re, sys, time, uuid
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


def args_digest(args):
    return hashlib.sha256(json.dumps(args, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def expected_call(s, tool, slug=None, page=None, batch=None):
    """预留前核对：search 必须是已计划的 slug、页码必须恰为下一页且不超页数上限、查询未结束；
    补全必须是当前 hydrate 批次之一。返回本次调用应使用的完整参数（预留时绑定其摘要）。"""
    if tool == "search_posts_all":
        if not slug or slug not in s["queries"]:
            raise UsageError(f"slug {slug!r} not planned")
        qs = s["queries"][slug]
        if qs.get("done"):
            raise UsageError(f"slug {slug} finished: {qs['done']}")
        want = qs["pages"] + 1
        if page != want:
            raise UsageError(f"page must be the next page {want} for {slug} (got {page})")
        cap = PAGE_CAP[qs["round"]][qs["kind"]]
        if page > cap:
            raise UsageError(f"page cap {cap} (round {qs['round']} {qs['kind']})")
        args = dict(qs["args"])
        if page > 1:
            if not qs.get("next_token"):
                raise UsageError(f"no next_token recorded for {slug}")
            args["next_token"] = qs["next_token"]
        return args, None
    batches = hydrate_batches(s)
    if batch is None or not (0 <= batch < len(batches)):
        raise UsageError(f"--batch must be 0..{len(batches) - 1} (current hydrate batches)")
    args = batches[batch]["args"]
    return args, args["ids"].split(",")


def reserve(s, tool, slug=None, page=None, now=None, batch=None, args=None):
    if tool not in TOOLS:
        raise UsageError(f"unknown tool {tool}")
    want, ids = expected_call(s, tool, slug, page, batch)
    dg = args_digest(want)
    if args is not None and args_digest(args) != dg:
        raise UsageError("args do not match the planned call for this slug/page/batch")
    now = now or time.time()
    if used_today(s, now) >= DAY_CAP:
        return {"allowed": False, "reason": f"daily cap {DAY_CAP} (resets 00:00Z)"}
    w = wait_needed(s, now)
    if w > 0:
        return {"allowed": False, "reason": f"per-minute cap {MIN_CAP}", "wait_s": w}
    cid = uuid.uuid4().hex[:12]
    s["calls"].append({"id": cid, "t": now, "tool": tool, "slug": slug, "page": page, "ingested": False,
                       "args_digest": dg, "ids": ids})
    return {"allowed": True, "call_id": cid, "args": want, "args_digest": dg}


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
    args = strictjson.loads(a.args) if a.args else None
    r = reserve(s, a.tool, a.slug, a.page, batch=a.batch, args=args)
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
    users = {u.get("id"): u.get("username") for u in ((j.get("includes") or {}).get("users") or [])}
    for d in data:
        s["posts"].setdefault(d["id"], {k: d.get(k) for k in ("id", "text", "author_id", "created_at", "public_metrics")})
        s["posts"][d["id"]]["query"] = slug
        if users.get(d.get("author_id")):
            s["posts"][d["id"]]["username"] = users[d.get("author_id")]
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
        qs["done"] = reason
        qs.pop("next_token", None)
        return {"next": None, "reason": reason, "new_ids": len(new)}
    qs["next_token"] = tok
    args = dict(qs["args"])          # 完整参数从状态恢复，不依赖人工传入
    args.pop("pagination_token", None)
    args["next_token"] = tok
    return {"next": {"slug": slug, "kind": qs["kind"], "page": qs["pages"] + 1, "tool": "search_posts_all",
                     "args": args, "wait_s": wait_needed(s)}, "new_ids": len(new)}


def hydrate_batches(s):
    ids = [i for i in s["ids"] if "urls" not in s["posts"].get(i, {})]
    return [{"batch": n, "tool": "get_posts_by_ids", "args": {"ids": ",".join(ids[i:i + HYDRATE_BATCH]),
             "post.fields": "entities,created_at,note_tweet"}}
            for n, i in enumerate(range(0, len(ids), HYDRATE_BATCH))]


def cmd_hydrate(a, s):
    return hydrate_batches(s)


def cmd_ingest_hydrate(a, s):
    c = _take_call(s, a.call_id, "get_posts_by_ids")
    allowed = set(c.get("ids") or [])
    j, _ = parse_result(a.file)
    data = j.get("data", []) or []
    extra = [d["id"] for d in data if d["id"] not in allowed]
    if extra:
        raise UsageError(f"{len(extra)} ids not in the reserved batch for call {a.call_id}")
    n = 0
    for d in data:
        p = s["posts"].setdefault(d["id"], {"id": d["id"]})
        p["urls"] = [{"expanded_url": u.get("expanded_url"), "unwound_url": u.get("unwound_url")}
                     for u in ((d.get("entities") or {}).get("urls") or [])]
        n += 1
    return {"hydrated": n}


LIKE_MIN, RT_MIN = 20, 5   # improve/x-queries.md：like_count ≥ 20 或 retweet_count ≥ 5 或作者在白名单


def whitelist(s):
    """白名单 = 状态中全部 account 类（from: 批次）查询里的账号（小写）。"""
    out = set()
    for q in s["queries"].values():
        if q.get("kind") == "account":
            out |= {m.lower() for m in re.findall(r"from:(\w+)", q["args"].get("query", ""))}
    return out


def lead_reason(p, wl):
    m = p.get("public_metrics") or {}
    if (m.get("like_count") or 0) >= LIKE_MIN:
        return f"like_count>={LIKE_MIN}"
    if (m.get("retweet_count") or 0) >= RT_MIN:
        return f"retweet_count>={RT_MIN}"
    if (p.get("username") or "").lower() in wl:
        return "whitelisted_author"
    return None


def cmd_leads(a, s):
    """按文档派生过滤规则导出；输出含帖文，只能写入私有目录（fetch_primary 的公开输出不含帖文）。"""
    wl, items, dropped = whitelist(s), [], 0
    for p in s["posts"].values():
        why = lead_reason(p, wl)
        if not why:
            dropped += 1; continue
        items.append(dict(p, label="线索", source_role="lead", lead_reason=why))
    return {"items": items, "filtered_out": dropped}


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
    p.add_argument("--batch", type=int); p.add_argument("--args", help="可选：本次实际调用参数 JSON，须与计划一致")
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
