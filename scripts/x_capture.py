#!/usr/bin/env python3
"""markjin X capture helper: paging plan + page ingest + budget guard.

X calls are made by the agent through the dynamic `x` namespace (CallDynamicTool,
write_to_file=true); this script never talks to X itself. It (1) plans calls,
(2) ingests each saved tool-result file and says whether/how to fetch the next page,
(3) enforces the daily / per-minute budget, (4) emits id batches for entity hydration.

Verified 2026-10-12 06:2x SGT (one real 2-page call):
  * search_posts_all caps max_results at 25 per call.
  * Paging param name is `next_token` (value = meta.next_token of the previous page).
    The schema also lists `pagination_token`; use `next_token` (the tested one).
  * Page 2 returned 25 new ids, 0 overlap, all older than page 1 (recency order).
  * search_posts_all does NOT return `entities` even when post.fields=entities is set;
    hydrate with get_posts_by_ids (<=100 ids/call, post.fields=entities,created_at),
    which does return entities.urls[].expanded_url / unwound_url.
  * t.co robots.txt disallows `*`: never resolve t.co ourselves; use unwound_url/expanded_url.

Commands:
  plan    --queries queries.json --round 1|2           -> JSON list of first-page calls
  ingest  --state STATE.json --slug S --kind account|topic --page N --file RESULT.txt
          -> prints JSON {"next": {...args...}} or {"next": null, "reason": ...}
  hydrate --state STATE.json                          -> JSON list of id batches (<=100)
  budget  --state STATE.json                          -> calls used today / remaining
Budget: <=400 X calls per SGT capture day, <=25 per rolling minute (script sleeps if needed).
Page caps: account batches 4 pages, topic queries 2 pages.
"""
import argparse, json, re, sys, time, datetime as dt
from pathlib import Path

DAY_CAP, MIN_CAP = 400, 25
PAGE_CAP = {"account": 4, "topic": 2}
HYDRATE_BATCH = 100
BASE_ARGS = {"max_results": 25, "post.fields": "created_at,author_id,public_metrics,entities,referenced_tweets",
             "expansions": "author_id", "user.fields": "username"}


def load_state(p):
    p = Path(p)
    s = json.loads(p.read_text()) if p.exists() else {}
    s.setdefault("calls", []); s.setdefault("ids", []); s.setdefault("queries", {})
    return s


def save_state(p, s):
    Path(p).write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n")


def parse_result(path):
    """Extract the JSON payload from a CallDynamicTool write_to_file result."""
    txt = Path(path).read_text()
    i = txt.index("{")
    body = txt[i:].split("\nX reads left")[0]
    body = body[: body.rindex("}") + 1]
    j = json.loads(body)
    quota = re.search(r"(\d+) of (\d+) this minute.*?(\d+) of (\d+) today", txt, re.S)
    return j, (tuple(map(int, quota.groups())) if quota else None)


def record_call(s, slug, page):
    s["calls"].append({"t": time.time(), "slug": slug, "page": page})


def throttle(s):
    """Return seconds to wait so the next call stays <=25/min; 0 if fine."""
    now = time.time()
    recent = [c for c in s["calls"] if now - c["t"] < 60]
    if len(recent) < MIN_CAP:
        return 0
    return 60 - (now - min(c["t"] for c in recent)) + 0.5


def used_today(s):
    sgt = dt.timezone(dt.timedelta(hours=8))
    today = dt.datetime.now(sgt).date()
    return sum(1 for c in s["calls"] if dt.datetime.fromtimestamp(c["t"], sgt).date() == today)


def cmd_plan(a):
    q = json.loads(Path(a.queries).read_text())  # [{"slug","kind","query","sort_order"?}]
    out = []
    for e in q:
        args = dict(BASE_ARGS, query=e["query"], sort_order=e.get("sort_order",
                    "recency" if e["kind"] == "account" else "relevancy"))
        if a.start_time:
            args["start_time"] = a.start_time
        out.append({"slug": e["slug"], "kind": e["kind"], "page": 1, "args": args})
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_ingest(a):
    s = load_state(a.state)
    j, quota = parse_result(a.file)
    record_call(s, a.slug, a.page)
    data = j.get("data", []) or []
    new = [d["id"] for d in data if d["id"] not in set(s["ids"])]
    s["ids"].extend(new)
    qs = s["queries"].setdefault(a.slug, {"kind": a.kind, "pages": 0, "posts": 0})
    qs["pages"] = a.page; qs["posts"] += len(data)
    tok = (j.get("meta") or {}).get("next_token")
    reason = None
    if not tok:
        reason = "no next_token"
    elif a.page >= PAGE_CAP[a.kind]:
        reason = f"page cap {PAGE_CAP[a.kind]}"
    elif used_today(s) >= DAY_CAP:
        reason = f"daily cap {DAY_CAP}"
    elif quota and quota[0] <= 1:
        reason = "X per-minute quota exhausted; retry after reset"
    elif not new and data:
        reason = "page added no new ids"
    save_state(a.state, s)
    if reason:
        print(json.dumps({"next": None, "reason": reason, "new_ids": len(new)})); return 0
    wait = throttle(s)
    if a.prev_args:
        args = json.loads(Path(a.prev_args).read_text())
    else:
        args = {}
    args.pop("pagination_token", None); args["next_token"] = tok
    print(json.dumps({"next": {"slug": a.slug, "kind": a.kind, "page": a.page + 1, "args": args,
                               "sleep_s": round(wait, 1)}, "new_ids": len(new)}, ensure_ascii=False))
    return 0


def cmd_hydrate(a):
    s = load_state(a.state)
    ids = s["ids"]
    batches = [ids[i:i + HYDRATE_BATCH] for i in range(0, len(ids), HYDRATE_BATCH)]
    print(json.dumps([{"tool": "get_posts_by_ids", "args": {"ids": ",".join(b),
           "post.fields": "entities,created_at,note_tweet"}} for b in batches], indent=1))


def cmd_budget(a):
    s = load_state(a.state)
    u = used_today(s)
    print(json.dumps({"used_today": u, "remaining": DAY_CAP - u, "wait_s": round(throttle(s), 1)}))


def main(argv=None):
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--queries", required=True); p.add_argument("--start-time")
    p.set_defaults(f=cmd_plan)
    p = sp.add_parser("ingest"); p.add_argument("--state", required=True); p.add_argument("--slug", required=True)
    p.add_argument("--kind", choices=PAGE_CAP, required=True); p.add_argument("--page", type=int, required=True)
    p.add_argument("--file", required=True); p.add_argument("--prev-args", help="JSON file of previous call args")
    p.set_defaults(f=cmd_ingest)
    for n, f in (("hydrate", cmd_hydrate), ("budget", cmd_budget)):
        p = sp.add_parser(n); p.add_argument("--state", required=True); p.set_defaults(f=f)
    a = ap.parse_args(argv)
    return a.f(a) or 0


if __name__ == "__main__":
    sys.exit(main())
