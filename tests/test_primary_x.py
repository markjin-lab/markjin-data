"""PR #6 审查修复：scraper 原件存档、fetch_primary 许可分流/线索身份/脱敏、x_capture 预算与翻页的针对性测试（离线）。"""
import json, os, tempfile, time, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import collect, strictjson
import capture_sources as CS
import fetch_primary as FP
import x_capture as XC
from test_collect import Resp, FakeOpener, mk


def tmp():
    return Path(tempfile.mkdtemp())


class ScraperCapture(unittest.TestCase):
    def test_sitemap_raw_archived_and_subsitemap_robots(self):
        import yaml
        base = tmp(); out, priv = base / "pub", base / "priv"; out.mkdir()
        idx = b"<?xml version='1.0'?><sitemapindex><sitemap><loc>https://www.anthropic.com/s1.xml</loc></sitemap>" \
              b"<sitemap><loc>https://other.org/s2.xml</loc></sitemap></sitemapindex>"
        s1 = b"<urlset><url><loc>https://www.anthropic.com/news/foo</loc><lastmod>2026-10-10</lastmod></url></urlset>"
        routes = {"https://www.anthropic.com/sitemap.xml": Resp(200, idx), "https://www.anthropic.com/s1.xml": Resp(200, s1),
                  "https://other.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /\n"),
                  "https://other.org/s2.xml": Resp(200, b"<urlset/>")}
        src = base / "s.yaml"
        src.write_text(yaml.safe_dump({"sources": [{"id": "anthropic-news", "method": "scraper", "scraper": "anthropic_sitemap",
                       "url": "https://www.anthropic.com/sitemap.xml", "enabled": True, "approval_status": "approved",
                       "approval_basis": "b", "license": "url+hash-only"}]}), encoding="utf-8")
        orig = collect.Fetcher.__init__
        op = FakeOpener(routes)

        def init(s, *a, **k):
            k["opener"] = op; k["sleep"] = lambda x: None; orig(s, *a, **k)
        collect.Fetcher.__init__ = init
        try:
            rc = CS.main(["--sources", str(src), "--date", "2026-10-12", "--round", "1", "--out-root", str(out),
                          "--private-root", str(priv)])
        finally:
            collect.Fetcher.__init__ = orig
        self.assertEqual(rc, 0)
        self.assertNotIn("https://other.org/s2.xml", [u for u, _ in op.calls])     # 子 sitemap 也查 robots
        day = priv / "raw/2026-10-12"
        man = (day / "MANIFEST.sha256").read_text()
        raws = sorted(p.read_bytes() for p in (day / "anthropic-news").glob("*.xml"))
        self.assertEqual(raws, sorted([idx, s1]))                                   # 每个原始响应都存档
        self.assertEqual(man.count("anthropic-news/"), 2)
        der = list((day / "anthropic-news/derived").glob("*items-*.json"))
        self.assertEqual(len(der), 1)
        self.assertIn("news/foo", der[0].read_text())
        self.assertNotIn("derived", man)


class Primary(unittest.TestCase):
    def setUp(self):
        self.base = tmp(); self.out = self.base / "pub"; self.priv = self.base / "priv"; self.out.mkdir()

    def run_fp(self, leads, routes, evidence=None, state=None, max_bytes=collect.MAX_BYTES):
        lp = self.base / "leads.json"
        lp.write_text(json.dumps({"items": leads}), encoding="utf-8")
        f, _ = mk(routes, state=state, max_bytes=max_bytes)
        args = ["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(self.out), "--private-root", str(self.priv)]
        if evidence is not None:
            ep = self.base / "ev.jsonl"
            ep.write_text("".join(json.dumps(e) + "\n" for e in evidence), encoding="utf-8")
            args += ["--license-evidence", str(ep)]
        self.assertEqual(FP.main(args, fetcher=f), 0)
        pday = self.out / "raw/2026-10-12/primary"
        doc = strictjson.loads(next(pday.glob("leads-primary-*.json")).read_text())
        idx = strictjson.loads(next(pday.glob("index-*.json")).read_text())
        return doc["items"], idx, f

    def test_gov_domain_is_not_a_license_and_200_is_not_verification(self):
        items, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://www.nasa.gov/a?token=SEKRIT&utm_source=x"}],
                                    {"https://www.nasa.gov/a?token=SEKRIT&utm_source=x": Resp(200, b"<html><title>T</title><p>body text</p>", {"Content-Type": "text/html"})})
        self.assertEqual(items[0]["label"], "线索")
        self.assertEqual(items[0]["source_role"], "lead")
        self.assertEqual(items[0]["fetch_status"], "fetched")
        self.assertEqual(items[0]["primary_verification"], "unverified")
        self.assertEqual(idx[0]["stored"], "private")
        self.assertEqual(idx[0]["license"], "url+hash-only")
        pub_text = "".join(p.read_text(errors="replace") for p in self.out.rglob("*") if p.is_file())
        self.assertNotIn("body text", pub_text)
        self.assertNotIn("SEKRIT", pub_text)
        self.assertNotIn(str(self.base), pub_text)
        self.assertTrue(list((self.priv / "raw/2026-10-12/primary").glob("*.html")))
        self.assertTrue(list((self.priv / "raw/2026-10-12/primary/derived").glob("*.txt")))

    def test_per_item_evidence_allows_public_with_attribution(self):
        u = "https://journals.aps.org/prxquantum/abstract/10.1103/X"
        ev = {"url": u, "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
              "evidence_url": "https://journals.aps.org/prxquantum/about", "attribution": "A. Author et al., PRX Quantum",
              "verified_by": "jw", "verified_at": "2026-10-12"}
        items, idx, _ = self.run_fp([{"id": "1", "expanded_url": u}],
                                    {u: Resp(200, b"<html><p>open article</p>", {"Content-Type": "text/html"})}, evidence=[ev])
        self.assertEqual(idx[0]["stored"], "public")
        self.assertEqual(idx[0]["license_evidence"]["attribution"], ev["attribution"])
        txt = next((self.out / "raw/2026-10-12/primary").glob("*.txt")).read_text()
        self.assertIn("Attribution: A. Author", txt)
        self.assertEqual(items[0]["label"], "线索")
        man = (self.out / "raw/2026-10-12/MANIFEST.sha256").read_text()
        for p in (self.out / "raw/2026-10-12").rglob("*"):
            if p.is_file() and p.name != "MANIFEST.sha256":
                self.assertIn("./" + str(p.relative_to(self.out / "raw/2026-10-12")), man)

    def test_redirect_to_unlicensed_url_stays_private(self):
        u = "https://journals.aps.org/a"
        ev = {"url": u, "license": "CC-BY-4.0", "license_url": "x", "evidence_url": "x", "attribution": "x",
              "verified_by": "x", "verified_at": "x"}
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": u}],
                                {u: Resp(302, headers={"Location": "https://journals.aps.org/b"}),
                                 "https://journals.aps.org/b": Resp(200, b"<p>x</p>")}, evidence=[ev])
        self.assertEqual(idx[0]["stored"], "private")

    def test_tco_never_fetched_and_403_disables_host(self):
        st = collect.HostState(self.base / "st.json")
        items, idx, f = self.run_fp([{"id": "1", "expanded_url": "https://t.co/x"},
                                     {"id": "2", "expanded_url": "https://bad.org/a"},
                                     {"id": "3", "expanded_url": "https://bad.org/b"}],
                                    {"https://bad.org/a": Resp(403), "https://bad.org/b": Resp(200, b"x")}, state=st)
        self.assertEqual(items[0]["fetch_status"], "no_primary_link")
        self.assertEqual(items[1]["fetch_status"], "http_403")
        self.assertEqual(items[2]["fetch_status"], "disabled")
        self.assertNotIn("https://bad.org/b", [u for u, _ in f.opener.calls])
        self.assertFalse(any("t.co" in u for u, _ in f.opener.calls))

    def test_oversize_is_failure_not_truncated(self):
        items, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/big"}],
                                    {"https://e.org/big": Resp(200, b"x" * 100)}, max_bytes=10)
        self.assertEqual(items[0]["fetch_status"], "too_large")
        self.assertIsNone(items[0]["sha256"])

    def test_outputs_never_overwritten(self):
        self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}], {"https://e.org/a": Resp(200, b"a")})
        before = {p: p.read_bytes() for p in self.out.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256"}
        self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}], {"https://e.org/a": Resp(200, b"a")})
        for p, b in before.items():
            self.assertEqual(p.read_bytes(), b)

    def test_leads_strict_json(self):
        lp = self.base / "leads.json"
        lp.write_text('{"items": [], "items": []}', encoding="utf-8")
        with self.assertRaises(strictjson.DuplicateKeyError):
            FP.main(["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(self.out),
                     "--private-root", str(self.priv)], fetcher=mk({})[0])


class XCapture(unittest.TestCase):
    def setUp(self):
        self.d = tmp(); self.st = self.d / "state.json"
        (self.d / "q.json").write_text(json.dumps([{"slug": "accounts-01", "kind": "account", "query": "from:a"},
                                                   {"slug": "ai", "kind": "topic", "query": "LLM"}]))

    def x(self, *a):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = XC.main(list(a))
        return rc, (json.loads(buf.getvalue()) if buf.getvalue().strip() else None)

    def result(self, ids, tok=None, dup=False):
        p = self.d / f"r{len(list(self.d.iterdir()))}.txt"
        body = json.dumps({"data": [{"id": i, "text": "t"} for i in ids], "meta": {"next_token": tok} if tok else {}})
        if dup:
            body = body[:-1] + ', "meta": {}}'
        p.write_text("tool result:\n" + body + "\nX reads left: 20 of 25 this minute, 300 of 400 today\n")
        return str(p)

    def test_window_by_round(self):
        self.assertEqual(XC.window_start("2026-10-12", 2), "2026-10-11T21:00:00Z")
        self.assertEqual(XC.window_start("2026-10-12", 1), "2026-10-09T21:00:00Z")
        rc, plan = self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "2")
        self.assertEqual(rc, 0)
        self.assertEqual(plan[0]["args"]["start_time"], "2026-10-11T21:00:00Z")
        with self.assertRaises(SystemExit):
            XC.main(["plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12"])

    def test_ingest_requires_reservation_and_restores_args(self):
        self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "1")
        rc, _ = self.x("ingest", "--state", str(self.st), "--call-id", "nope", "--file", self.result(["1"], "T"))
        self.assertEqual(rc, 2)                                               # 未预留的调用不能入账
        rc, r = self.x("reserve", "--state", str(self.st), "--tool", "search_posts_all", "--slug", "accounts-01", "--page", "1")
        self.assertTrue(r["allowed"])
        rc, n = self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["1", "2"], "TOK"))
        self.assertEqual(n["next"]["args"]["query"], "from:a")                # 完整参数从状态恢复
        self.assertEqual(n["next"]["args"]["start_time"], "2026-10-09T21:00:00Z")
        self.assertEqual(n["next"]["args"]["next_token"], "TOK")
        rc, _ = self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["3"], "T"))
        self.assertEqual(rc, 2)                                               # 同一调用不能入账两次

    def test_page_caps_by_round(self):
        self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "1")
        for page, ids in ((1, ["8"]), (2, ["9"])):
            _, r = self.x("reserve", "--state", str(self.st), "--tool", "search_posts_all", "--slug", "ai", "--page", str(page))
            _, n = self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(ids, "TOK"))
        self.assertIsNone(n["next"])
        self.assertIn("page cap 2", n["reason"])

    def test_hydrate_calls_need_reservation(self):
        self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "1")
        _, r = self.x("reserve", "--state", str(self.st), "--tool", "search_posts_all", "--slug", "ai", "--page", "1")
        self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["9"]))
        _, b = self.x("hydrate", "--state", str(self.st))
        self.assertEqual(b[0]["args"]["ids"], "9")
        rc, _ = self.x("ingest-hydrate", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["9"]))
        self.assertEqual(rc, 2)                                               # 搜索预留不能冒充补全
        _, h = self.x("reserve", "--state", str(self.st), "--tool", "get_posts_by_ids")
        rc, _ = self.x("ingest-hydrate", "--state", str(self.st), "--call-id", h["call_id"], "--file", self.result(["9"]))
        self.assertEqual(rc, 0)
        _, b = self.x("budget", "--state", str(self.st))
        self.assertEqual(b["used_today_utc"], 2)
        _, leads = self.x("leads", "--state", str(self.st))
        self.assertTrue(all(i["source_role"] == "lead" and i["label"] == "线索" for i in leads["items"]))

    def test_minute_and_daily_caps_utc(self):
        s = XC.load_state(self.st)
        now = time.time()
        for _ in range(XC.MIN_CAP):
            self.assertTrue(XC.reserve(s, "search_posts_all", now=now)["allowed"])
        r = XC.reserve(s, "get_posts_by_ids", now=now)
        self.assertFalse(r["allowed"]); self.assertGreater(r["wait_s"], 0)
        # 每日窗口按 UTC：前一 UTC 日 23:59Z 的调用不计入今天
        s = XC.load_state(self.d / "none.json")
        import datetime as dt
        today0 = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        s["calls"] = [{"id": str(i), "t": today0 - 60 - i, "tool": "search_posts_all", "ingested": True} for i in range(XC.DAY_CAP)]
        self.assertEqual(XC.used_today(s, now=today0 + 3600), 0)
        s["calls"] = [{"id": str(i), "t": today0 + i, "tool": "search_posts_all", "ingested": True} for i in range(XC.DAY_CAP)]
        self.assertFalse(XC.reserve(s, "search_posts_all", now=today0 + 7200)["allowed"])

    def test_result_strict_json(self):
        with self.assertRaises(strictjson.DuplicateKeyError):
            XC.parse_result(self.result(["1"], dup=True))


if __name__ == "__main__":
    unittest.main()
