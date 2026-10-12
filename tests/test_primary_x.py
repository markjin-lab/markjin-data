"""PR #6 审查修复：scraper 原件存档、fetch_primary 许可分流/线索身份/脱敏、x_capture 预算与翻页的针对性测试（离线）。"""
import hashlib, json, os, tempfile, time, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import collect, strictjson
import capture_sources as CS
import fetch_primary as FP
import x_capture as XC
from test_collect import Resp, FakeOpener, mk, PUBLIC_DNS


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
            k["opener"] = op; k["sleep"] = lambda x: None; k.setdefault("resolver", PUBLIC_DNS); orig(s, *a, **k)
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
    DNS = {}

    def resolve(self, host):
        return self.DNS.get(host, {"93.184.216.34"})

    def setUp(self):
        self.base = tmp(); self.out = self.base / "pub"; self.priv = self.base / "priv"; self.out.mkdir()

    def run_fp(self, leads, routes, evidence=None, state=None, max_bytes=collect.MAX_BYTES):
        lp = self.base / "leads.json"
        lp.write_text(json.dumps({"items": leads}), encoding="utf-8")
        f, _ = mk(routes, state=state, max_bytes=max_bytes)
        f.addr_policy = collect.AddressPolicy(resolver=self.resolve)
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
              "verified_by": "jw", "verified_at": "2026-10-12",
              "sha256": hashlib.sha256(b"<html><p>open article</p>").hexdigest()}
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
              "verified_by": "x", "verified_at": "x", "sha256": hashlib.sha256(b"<p>x</p>").hexdigest()}
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
        _, h = self.x("reserve", "--state", str(self.st), "--tool", "get_posts_by_ids", "--batch", "0")
        rc, _ = self.x("ingest-hydrate", "--state", str(self.st), "--call-id", h["call_id"], "--file", self.result(["9"]))
        self.assertEqual(rc, 0)
        _, b = self.x("budget", "--state", str(self.st))
        self.assertEqual(b["used_today_utc"], 2)
        _, leads = self.x("leads", "--state", str(self.st))
        self.assertTrue(all(i["source_role"] == "lead" and i["label"] == "线索" for i in leads["items"]))

    def test_minute_and_daily_caps_utc(self):
        self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "1")
        s = XC.load_state(self.st)
        now = time.time()
        for _ in range(XC.MIN_CAP):
            self.assertTrue(XC.reserve(s, "search_posts_all", "ai", 1, now=now)["allowed"])
            s["calls"][-1]["cancelled"] = True                       # 同页重复预留须先取消
        r = XC.reserve(s, "search_posts_all", "accounts-01", 1, now=now)
        self.assertFalse(r["allowed"]); self.assertGreater(r["wait_s"], 0)
        # 每日窗口按 UTC：前一 UTC 日 23:59Z 的调用不计入今天
        s = XC.load_state(self.st)
        import datetime as dt
        today0 = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        s["calls"] = [{"id": str(i), "t": today0 - 60 - i, "tool": "search_posts_all", "ingested": True} for i in range(XC.DAY_CAP)]
        self.assertEqual(XC.used_today(s, now=today0 + 3600), 0)
        s["calls"] = [{"id": str(i), "t": today0 + i, "tool": "search_posts_all", "ingested": True} for i in range(XC.DAY_CAP)]
        self.assertFalse(XC.reserve(s, "search_posts_all", "ai", 1, now=today0 + 7200)["allowed"])

    def test_result_strict_json(self):
        with self.assertRaises(strictjson.DuplicateKeyError):
            XC.parse_result(self.result(["1"], dup=True))


class R2Primary(Primary):
    """PR #6 审查 r2 REJECTED 修复：许可按完整 URL+sha256、公开线索不含帖文、目标地址策略。"""

    def ev(self, url, body):
        return {"url": url, "license": "CC-BY-4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "evidence_url": "https://e.org/about", "attribution": "A", "verified_by": "jw",
                "verified_at": "2026-10-12", "sha256": hashlib.sha256(body).hexdigest()}

    def test_evidence_for_other_query_value_not_used(self):
        body = b"<p>private doc</p>"
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/d?code=PRIVATE"}],
                                {"https://e.org/d?code=PRIVATE": Resp(200, body)},
                                evidence=[self.ev("https://e.org/d?code=PUBLIC", body)])
        self.assertEqual(idx[0]["stored"], "private")
        self.assertFalse(list((self.out / "raw/2026-10-12/primary").glob("*.txt")))

    def test_evidence_sha_mismatch_stays_private(self):
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}],
                                {"https://e.org/a": Resp(200, b"<p>changed</p>")},
                                evidence=[self.ev("https://e.org/a", b"<p>original</p>")])
        self.assertEqual(idx[0]["stored"], "private")
        self.assertIn("sha256", idx[0]["license_decision"])

    def test_redirect_needs_evidence_for_both_urls(self):
        body = b"<p>open</p>"
        routes = {"https://e.org/a": Resp(302, headers={"Location": "https://e.org/b"}), "https://e.org/b": Resp(200, body)}
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}], routes,
                                evidence=[self.ev("https://e.org/a", body), self.ev("https://e.org/b", body)])
        self.assertEqual(idx[0]["stored"], "public")

    def test_public_leads_have_no_post_text(self):
        lead = {"id": "123", "text": "SECRET POST TEXT about things", "author_id": "9", "username": "someone",
                "public_metrics": {"like_count": 50}, "expanded_url": "https://e.org/a?token=SEKRIT"}
        items, _, _ = self.run_fp([lead, {"id": "124", "text": "UNFETCHED TEXT"}],
                                  {"https://e.org/a?token=SEKRIT": Resp(200, b"x")})
        pub_text = "".join(p.read_text(errors="replace") for p in self.out.rglob("*") if p.is_file())
        self.assertNotIn("SECRET POST TEXT", pub_text)
        self.assertNotIn("UNFETCHED TEXT", pub_text)
        self.assertNotIn("someone", pub_text)
        self.assertNotIn("SEKRIT", pub_text)
        for it in items:
            self.assertLessEqual(set(it), set(FP.PUBLIC_LEAD_FIELDS))
        self.assertEqual(items[0]["url"], "https://x.com/i/status/123")
        self.assertEqual(items[0]["text_sha256"], hashlib.sha256(lead["text"].encode()).hexdigest())
        priv = next((self.priv / "raw/2026-10-12/primary").glob("leads-*.json")).read_text()
        self.assertIn("SECRET POST TEXT", priv)                        # 原文进私有档案
        flog = next((self.priv / "raw/2026-10-12/primary").glob("fetch-log-*.jsonl")).read_text()
        self.assertNotIn("SEKRIT", flog)                               # 私有日志也不写凭证

    def _blocked(self, url, routes=None, dns=None):
        self.DNS = dns or {}
        items, idx, f = self.run_fp([{"id": "1", "expanded_url": url}], routes or {url: Resp(200, b"x")})
        return items[0]["fetch_status"], [u for u, _ in f.opener.calls]

    def test_loopback_private_linklocal_literals_rejected(self):
        for u in ("http://127.0.0.1:8080/x", "http://10.0.0.5/x", "http://192.168.1.1/", "http://169.254.169.254/latest",
                  "http://[::1]/x", "http://0.0.0.0/", "http://100.64.0.1/", "http://198.18.0.1/x", "http://240.0.0.1/"):
            st, calls = self._blocked(u)
            self.assertEqual(st, "blocked_address", u)
            self.assertEqual(calls, [], u)                             # 连 robots.txt 都不请求

    def test_hostname_resolving_to_private_rejected(self):
        st, calls = self._blocked("https://evil.example/x", dns={"evil.example": {"127.0.0.1"}})
        self.assertEqual((st, calls), ("blocked_address", []))
        st, _ = self._blocked("https://localhost/x")
        self.assertEqual(st, "blocked_address")

    def test_redirect_hop_to_private_rejected(self):
        routes = {"https://e.org/a": Resp(302, headers={"Location": "http://169.254.169.254/meta"}),
                  "http://169.254.169.254/meta": Resp(200, b"creds")}
        st, calls = self._blocked("https://e.org/a", routes)
        self.assertEqual(st, "blocked_address")
        self.assertFalse(any("169.254" in u for u in calls))
        routes = {"https://e.org/a": Resp(302, headers={"Location": "https://inner.example/x"}),
                  "https://inner.example/x": Resp(200, b"x")}
        st, calls = self._blocked("https://e.org/a", routes, dns={"inner.example": {"10.1.2.3"}})
        self.assertEqual(st, "blocked_address")
        self.assertFalse(any("inner.example" in u for u in calls))


class AddressPolicyT(unittest.TestCase):
    def test_fakeip_exception_is_narrow(self):
        fake = lambda h: {"198.18.0.1"}
        self.assertIsNotNone(collect.AddressPolicy(resolver=fake)("https://www.nasa.gov/x"))      # 默认不放行
        p = collect.AddressPolicy("198.18.0.0/15", resolver=fake)
        self.assertIsNone(p("https://www.nasa.gov/x"))                                          # 显式声明代理假 IP
        self.assertIsNotNone(p("http://198.18.0.1/x"))                                          # IP 字面量仍拒绝
        self.assertIsNotNone(collect.AddressPolicy("198.18.0.0/15", resolver=lambda h: {"198.18.0.1", "10.0.0.1"})(
            "https://mixed.example/"))                                                          # 混入内网仍拒绝
        self.assertIsNotNone(collect.AddressPolicy("198.18.0.0/15", resolver=lambda h: {"127.0.0.1"})(
            "https://evil.example/"))
        for bad in ("10.0.0.0/8", "0.0.0.0/0", "127.0.0.0/8", "198.16.0.0/14"):
            with self.assertRaises(collect.ConfigError):
                collect.AddressPolicy(bad)
        self.assertIsNone(collect.AddressPolicy(resolver=lambda h: {"93.184.216.34"})("https://e.org/"))

    def test_fetch_primary_forces_policy_and_interval_floor(self):
        base = tmp(); (base / "pub").mkdir()
        lp = base / "l.json"; lp.write_text(json.dumps({"items": [{"id": "1", "expanded_url": "http://127.0.0.1/x"}]}))
        f, _ = mk({"http://127.0.0.1/x": Resp(200, b"x")})
        self.assertIsNone(f.addr_policy)
        args = ["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(base / "pub"), "--private-root", str(base / "priv")]
        self.assertEqual(FP.main(args, fetcher=f), 0)
        self.assertEqual(f.opener.calls, [])                    # 传入的 Fetcher 也被套上地址策略
        self.assertEqual(FP.main(args + ["--interval", "0"], fetcher=mk({})[0]), 2)
        self.assertEqual(FP.main(args + ["--proxy-fakeip-cidr", "10.0.0.0/8"], fetcher=mk({})[0]), 2)


class R2XCapture(XCapture):
    def plan(self, rnd="1"):
        self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", rnd)

    def res(self, *extra):
        return self.x("reserve", "--state", str(self.st), "--tool", *extra)

    def test_reserve_validates_slug_and_page(self):
        self.plan()
        self.assertEqual(self.res("search_posts_all", "--slug", "nope", "--page", "1")[0], 2)
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "99")[0], 2)
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "2")[0], 2)   # 跳页
        self.assertEqual(self.res("search_posts_all", "--slug", "ai")[0], 2)                  # 缺页码
        rc, r = self.res("search_posts_all", "--slug", "ai", "--page", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(r["args_digest"], XC.args_digest(r["args"]))
        self.assertEqual(XC.load_state(self.st)["calls"][-1]["args_digest"], r["args_digest"])
        self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["1"], "TOK"))
        rc, r2 = self.res("search_posts_all", "--slug", "ai", "--page", "2")
        self.assertEqual(r2["args"]["next_token"], "TOK")                                    # 参数摘要绑定下一页 token
        self.x("ingest", "--state", str(self.st), "--call-id", r2["call_id"], "--file", self.result(["2"], "TOK2"))
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "3")[0], 2)  # 主题页数上限 2

    def test_reserve_args_must_match(self):
        self.plan()
        bad = json.dumps({"query": "something else"})
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "1", "--args", bad)[0], 2)
        st = XC.load_state(self.st)
        good = json.dumps(XC.expected_call(st, "search_posts_all", "ai", 1)[0])
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "1", "--args", good)[0], 0)

    def test_hydrate_bound_to_batch(self):
        self.plan()
        _, r = self.res("search_posts_all", "--slug", "ai", "--page", "1")
        self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["9"]))
        self.assertEqual(self.res("get_posts_by_ids")[0], 2)
        self.assertEqual(self.res("get_posts_by_ids", "--batch", "5")[0], 2)
        _, h = self.res("get_posts_by_ids", "--batch", "0")
        self.assertEqual(h["args"]["ids"], "9")
        rc, _ = self.x("ingest-hydrate", "--state", str(self.st), "--call-id", h["call_id"], "--file", self.result(["9", "77"]))
        self.assertEqual(rc, 2)                                                              # 批次外 id 拒绝

    def test_leads_filtered_by_engagement_and_whitelist(self):
        self.plan()
        s = XC.load_state(self.st)
        s["posts"] = {"1": {"id": "1", "text": "a", "public_metrics": {"like_count": 20, "retweet_count": 0}},
                      "2": {"id": "2", "text": "b", "public_metrics": {"like_count": 3, "retweet_count": 5}},
                      "3": {"id": "3", "text": "c", "public_metrics": {"like_count": 1}, "username": "A"},
                      "4": {"id": "4", "text": "d", "public_metrics": {"like_count": 19, "retweet_count": 4},
                            "username": "nobody"},
                      "5": {"id": "5", "text": "e"}}
        XC.save_state(self.st, s)
        _, out = self.x("leads", "--state", str(self.st))
        got = {i["id"]: i["lead_reason"] for i in out["items"]}
        self.assertEqual(got, {"1": "like_count>=20", "2": "retweet_count>=5", "3": "whitelisted_author"})
        self.assertEqual(out["filtered_out"], 2)
        self.assertTrue(all(i["source_role"] == "lead" and i["label"] == "线索" for i in out["items"]))

    def test_ingest_records_username_from_includes(self):
        self.plan()
        _, r = self.res("search_posts_all", "--slug", "accounts-01", "--page", "1")
        p = self.d / "u.txt"
        p.write_text("x\n" + json.dumps({"data": [{"id": "5", "text": "t", "author_id": "u1"}],
                                          "includes": {"users": [{"id": "u1", "username": "a"}]}, "meta": {}}))
        self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", str(p))
        self.assertEqual(XC.load_state(self.st)["posts"]["5"]["username"], "a")
        _, out = self.x("leads", "--state", str(self.st))
        self.assertEqual([i["id"] for i in out["items"]], ["5"])


class R2Sources(unittest.TestCase):
    def test_borrowed_report_items_are_pending(self):
        import yaml
        p = Path(__file__).resolve().parents[1] / "improve" / "sources.yaml"
        by = {s["id"]: s for s in yaml.safe_load(p.read_text(encoding="utf-8"))["sources"]}
        for sid in ("qwen-blog-rss",):
            self.assertEqual(by[sid]["approval_status"], "pending", sid)
            self.assertFalse(by[sid]["enabled"], sid)
            self.assertFalse(collect.approval_gate(by[sid])[0], sid)


class R3Primary(Primary):
    """PR #6 审查 r3 修复：私有条目不公开 title、license_url 脱敏、注入 Fetcher 策略合取、子 sitemap 地址策略。"""

    def test_private_item_title_not_in_public_index(self):
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}],
                                {"https://e.org/a": Resp(200, b"<html><title>SECRET TITLE</title><p>x</p>", {"Content-Type": "text/html"})})
        self.assertEqual(idx[0]["stored"], "private")
        self.assertNotIn("title", idx[0])
        pub = "".join(p.read_text(errors="replace") for p in self.out.rglob("*") if p.is_file())
        self.assertNotIn("SECRET TITLE", pub)
        flog = next((self.priv / "raw/2026-10-12/primary").glob("fetch-log-*.jsonl")).read_text()
        self.assertIn("SECRET TITLE", flog)                                   # 标题留在私有日志

    def test_public_item_has_title_and_redacted_license_url(self):
        body = b"<html><title>Open T</title><p>open</p></html>"
        ev = {"url": "https://e.org/a", "license": "CC-BY-4.0",
              "license_url": "https://creativecommons.org/licenses/by/4.0/?tok=LICSECRET",
              "evidence_url": "https://e.org/about?k=EVSECRET", "attribution": "A", "verified_by": "jw",
              "verified_at": "2026-10-12", "sha256": hashlib.sha256(body).hexdigest()}
        _, idx, _ = self.run_fp([{"id": "1", "expanded_url": "https://e.org/a"}],
                                {"https://e.org/a": Resp(200, body, {"Content-Type": "text/html"})}, evidence=[ev])
        self.assertEqual(idx[0]["stored"], "public")
        self.assertEqual(idx[0]["title"], "Open T")
        self.assertEqual(idx[0]["license_evidence"]["license_url"], "https://creativecommons.org/licenses/by/4.0/")
        pub = "".join(p.read_text(errors="replace") for p in self.out.rglob("*") if p.is_file())
        self.assertNotIn("LICSECRET", pub)
        self.assertNotIn("EVSECRET", pub)

    def test_injected_permissive_policy_cannot_bypass(self):
        lp = self.base / "l.json"
        lp.write_text(json.dumps({"items": [{"id": "1", "expanded_url": "https://lo.example/x"},
                                            {"id": "2", "expanded_url": "http://127.0.0.1/y"}]}))
        f, _ = mk({"https://lo.example/x": Resp(200, b"x"), "http://127.0.0.1/y": Resp(200, b"y")},
                  resolver=lambda h: {"127.0.0.1"}, addr_policy=lambda u: None)
        rc = FP.main(["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(self.out),
                      "--private-root", str(self.priv)], fetcher=f)
        self.assertEqual(rc, 0)
        self.assertEqual(f.opener.calls, [])

    def test_injected_strict_policy_is_respected(self):
        lp = self.base / "l.json"
        lp.write_text(json.dumps({"items": [{"id": "1", "expanded_url": "https://e.org/x"}]}))
        f, _ = mk({"https://e.org/x": Resp(200, b"x")}, addr_policy=lambda u: "caller policy refuses")
        FP.main(["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(self.out),
                 "--private-root", str(self.priv)], fetcher=f)
        self.assertEqual(f.opener.calls, [])

    def test_interval_nan_rejected(self):
        lp = self.base / "l.json"; lp.write_text('{"items": []}')
        for bad in ("nan", "inf", "1"):
            self.assertEqual(FP.main(["--leads", str(lp), "--date", "2026-10-12", "--out-root", str(self.out),
                                      "--private-root", str(self.priv), f"--interval={bad}"], fetcher=mk({})[0]), 2)


class R3Scraper(unittest.TestCase):
    def test_subsitemap_to_private_address_blocked(self):
        import yaml
        base = tmp(); out, priv = base / "pub", base / "priv"; out.mkdir()
        idx = b"<?xml version='1.0'?><sitemapindex><sitemap><loc>http://10.0.0.8/s1.xml</loc></sitemap></sitemapindex>"
        routes = {"https://www.anthropic.com/sitemap.xml": Resp(200, idx), "http://10.0.0.8/s1.xml": Resp(200, b"<urlset/>")}
        src = base / "s.yaml"
        src.write_text(yaml.safe_dump({"sources": [{"id": "anthropic-news", "method": "scraper", "scraper": "anthropic_sitemap",
                       "url": "https://www.anthropic.com/sitemap.xml", "enabled": True, "approval_status": "approved",
                       "approval_basis": "b", "license": "url+hash-only"}]}), encoding="utf-8")
        orig = collect.Fetcher.__init__
        op = FakeOpener(routes)

        def init(s, *a, **k):
            k["opener"] = op; k["sleep"] = lambda x: None; k["resolver"] = PUBLIC_DNS; orig(s, *a, **k)
        collect.Fetcher.__init__ = init
        try:
            CS.main(["--sources", str(src), "--date", "2026-10-12", "--round", "1", "--out-root", str(out),
                     "--private-root", str(priv)])
        finally:
            collect.Fetcher.__init__ = orig
        self.assertFalse(any("10.0.0.8" in u for u, _ in op.calls))

    def test_scrapers_share_collector_challenge(self):
        import scrapers
        self.assertIs(scrapers.CHALLENGE, collect.CHALLENGE)
        with self.assertRaises(scrapers.ScrapeError):
            scrapers.check_body(200, b'<div class="g-recaptcha"></div>', None)


class R3XCapture(R2XCapture):
    def test_same_page_cannot_be_reserved_twice(self):
        self.plan()
        rc, r = self.res("search_posts_all", "--slug", "accounts-01", "--page", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(self.res("search_posts_all", "--slug", "accounts-01", "--page", "1")[0], 2)
        self.x("cancel", "--state", str(self.st), "--call-id", r["call_id"])
        rc, r2 = self.res("search_posts_all", "--slug", "accounts-01", "--page", "1")
        self.assertEqual(rc, 0)                                              # 取消后可重新预留
        self.assertEqual(self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"],
                                "--file", self.result(["1"]))[0], 2)        # 已取消的不能入账
        _, b = self.x("budget", "--state", str(self.st))
        self.assertEqual(b["used_today_utc"], 2)                             # 取消的仍计入额度

    def test_ingest_checks_page_and_digest(self):
        self.plan()
        _, r = self.res("search_posts_all", "--slug", "ai", "--page", "1")
        st = XC.load_state(self.st)
        st["calls"][-1]["args_digest"] = "0" * 64                            # 被改动的预留
        XC.save_state(self.st, st)
        self.assertEqual(self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"],
                                "--file", self.result(["1"], "T"))[0], 2)
        st = XC.load_state(self.st)
        self.assertFalse(st["calls"][-1]["ingested"])
        st["calls"][-1]["args_digest"] = r["args_digest"]; st["calls"][-1]["page"] = 2
        XC.save_state(self.st, st)
        self.assertEqual(self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"],
                                "--file", self.result(["1"], "T"))[0], 2)   # 页码不是下一页

    def test_replan_keeps_started_query_pages(self):
        self.plan()
        _, r = self.res("search_posts_all", "--slug", "ai", "--page", "1")
        self.x("ingest", "--state", str(self.st), "--call-id", r["call_id"], "--file", self.result(["1"], "TOK"))
        rc, plan = self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-12", "--round", "1")
        self.assertEqual(rc, 0)
        st = XC.load_state(self.st)
        self.assertEqual(st["queries"]["ai"]["pages"], 1)
        self.assertEqual(st["queries"]["ai"]["next_token"], "TOK")
        self.assertEqual({p["slug"]: p["page"] for p in plan}["ai"], 2)
        self.assertEqual(self.res("search_posts_all", "--slug", "ai", "--page", "1")[0], 2)
        rc, _ = self.x("plan", "--queries", str(self.d / "q.json"), "--state", str(self.st), "--date", "2026-10-13", "--round", "1")
        self.assertEqual(rc, 2)                                              # 已开始的查询换参数 → 拒绝


class R3Sources(unittest.TestCase):
    def test_nbs_releases_restored(self):
        import yaml
        p = Path(__file__).resolve().parents[1] / "improve" / "sources.yaml"
        by = {s["id"]: s for s in yaml.safe_load(p.read_text(encoding="utf-8"))["sources"]}
        self.assertTrue(collect.approval_gate(by["nbs-releases"])[0])
        self.assertFalse(collect.approval_gate(by["qwen-blog-rss"])[0])


if __name__ == "__main__":
    unittest.main()
