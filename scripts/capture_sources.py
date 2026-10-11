#!/usr/bin/env python3
"""markjin P0 source capture.

Usage:
  capture_sources.py --sources sources.yaml --date YYYY-MM-DD --round 1|2 \
      [--out-root REPO_ROOT] [--private-root /workspace/markjin/private] \
      [--internal-root $MARKJIN_INTERNAL_DIR] [--only id1,id2] [--delay 1.0]

For every source with enabled: true and method rss/api:
  license full-text-ok          -> bytes saved to OUT/raw/DATE[/round2]/<id>/  (+ meta.json)
  license url+hash-only /
          market-data-restricted -> bytes saved ONLY to PRIVATE/raw/DATE[/round2]/<id>/;
                                    OUT/raw/DATE[/round2]/<id>/index.json holds url+sha256+fetched_at
  internal_only: true            -> everything (bytes, index, logs) under INTERNAL/raw/DATE[/round2]/<id>/;
                                    nothing is written to OUT.
Logs: <round dir>/query-log.jsonl (one line per fetch) and <round dir>/failures.json.
Free endpoints only: no credentials, no cookies, no login/paywall handling.
Exit code: 0 = all ok, 1 = at least one failure, 2 = bad arguments.
"""
import argparse, gzip, datetime as dt, hashlib, json, os, re, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path
import urllib.request, urllib.error
import yaml

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36 markjin-capture/1.0"
USER_KEYS = {"user", "users", "username", "screen_name", "author_id", "user_id", "profile_image_url",
             "avatar", "email", "commenter", "commenters"}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch(url, timeout, retries=1):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if body[:2] == b"\x1f\x8b":  # some CDNs (deepmind.google) send gzip unasked
                    body = gzip.decompress(body)
                return r.status, r.headers.get("Content-Type", ""), body, None
        except urllib.error.HTTPError as e:
            last = (e.code, "", b"", f"HTTP {e.code}")
            if e.code < 500:
                break
        except Exception as e:  # network / TLS / timeout
            last = (0, "", b"", f"{type(e).__name__}: {str(e)[:160]}")
        time.sleep(2 * (i + 1))
    return last


def parse_ok(method, body):
    try:
        b = body.lstrip(b"\xef\xbb\xbf \r\n\t")  # tolerate UTF-8 BOM (federalreserve.gov feeds)
        s = b[:1]
        if s in (b"{", b"["):
            json.loads(b); return "json"
        if s == b"<":
            ET.fromstring(b); return "xml"
    except Exception:
        return None
    return None


def strip_users(o):
    """Remove user-identifying fields (comment rule) from JSON before public storage."""
    if isinstance(o, dict):
        return {k: strip_users(v) for k, v in o.items() if k.lower() not in USER_KEYS}
    if isinstance(o, list):
        return [strip_users(x) for x in o]
    return o


def expand_url(url, date):
    """Placeholders: {date} = target date, {date-N} = target date minus N days (YYYY-MM-DD)."""
    d0 = dt.date.fromisoformat(date)
    def rep(m):
        n = int(m.group(1) or 0)
        return (d0 - dt.timedelta(days=n)).isoformat()
    return re.sub(r"\{date(?:-(\d+))?\}", rep, url)


def round_dir(root, date, rnd):
    d = Path(root) / "raw" / date
    return d / "round2" if rnd == 2 else d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--round", type=int, choices=(1, 2), required=True)
    ap.add_argument("--out-root", default=".")
    ap.add_argument("--private-root", default="/workspace/markjin/private")
    ap.add_argument("--internal-root", default=os.environ.get("MARKJIN_INTERNAL_DIR", "/workspace/markjin-internal"))
    ap.add_argument("--only", default="")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=30)
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print("bad --date", file=sys.stderr); return 2
    srcs = (yaml.safe_load(open(a.sources)) or {}).get("sources", [])
    only = {x for x in a.only.split(",") if x}
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fails = {}
    n_ok = 0
    for s in srcs:
        sid = s["id"]
        if only and sid not in only:
            continue
        if not s.get("enabled") or s.get("method") not in ("rss", "api"):
            continue
        lic = s.get("license", "url+hash-only")
        internal = bool(s.get("internal_only"))
        pub_rd = round_dir(a.internal_root if internal else a.out_root, a.date, a.round)
        priv_rd = round_dir(a.internal_root if internal else a.private_root, a.date, a.round)
        url = expand_url(s["url"], a.date)
        t0 = now(); st, ctype, body, err = fetch(url, a.timeout)
        sha = hashlib.sha256(body).hexdigest() if body else None
        kind = parse_ok(s["method"], body) if st == 200 else None
        rec = {"id": sid, "theme": s.get("theme"), "url": url, "round": a.round, "fetched_at": t0,
               "http_status": st, "bytes": len(body), "sha256": sha, "license": lic, "content_type": ctype}
        ok = st == 200 and kind is not None
        if ok:
            ext = {"json": "json", "xml": "xml"}[kind]
            fname = f"{stamp}.{ext}"
            if lic == "full-text-ok" or internal:
                d = pub_rd / sid; d.mkdir(parents=True, exist_ok=True)
                data = body
                if kind == "json" and lic == "full-text-ok" and not internal:
                    stripped = strip_users(json.loads(body))
                    if stripped != json.loads(body):
                        data = json.dumps(stripped, ensure_ascii=False).encode()
                        rec["stored_sha256"] = hashlib.sha256(data).hexdigest(); rec["user_fields_stripped"] = True
                (d / fname).write_bytes(data)
                rec["stored"] = str(d / fname)
            else:
                pd = priv_rd / sid; pd.mkdir(parents=True, exist_ok=True)
                (pd / fname).write_bytes(body)
                d = pub_rd / sid; d.mkdir(parents=True, exist_ok=True)
                idx_p = d / "index.json"
                idx = json.loads(idx_p.read_text()) if idx_p.exists() else []
                idx.append({"id": sid, "url": url, "sha256": sha, "fetched_at": t0, "bytes": len(body),
                            "license": lic, "round": a.round})
                idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n")
                rec["stored"] = "private"  # bytes never written to public tree
            n_ok += 1
        else:
            rec["error"] = err or ("unparseable" if st == 200 else f"HTTP {st}")
            fails.setdefault(pub_rd, []).append({k: rec[k] for k in ("id", "url", "fetched_at", "http_status", "error")})
        pub_rd.mkdir(parents=True, exist_ok=True)
        with open(pub_rd / "query-log.jsonl", "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"{'OK ' if ok else 'ERR'} {sid} {st} {len(body)}B", file=sys.stderr)
        time.sleep(a.delay)
    for rd in {round_dir(a.out_root, a.date, a.round), round_dir(a.internal_root, a.date, a.round)} | set(fails):
        if rd in fails or (rd / "query-log.jsonl").exists():
            p = rd / "failures.json"
            old = json.loads(p.read_text()) if p.exists() else []
            p.write_text(json.dumps(old + fails.get(rd, []), ensure_ascii=False, indent=1) + "\n")
    tot = sum(len(v) for v in fails.values())
    print(f"done: ok={n_ok} failed={tot}", file=sys.stderr)
    return 1 if tot else 0


if __name__ == "__main__":
    sys.exit(main())
