"""PR #3/#6 审查修复：采集公共层与 capture_sources 的针对性测试（全部离线，假 opener）。"""
import json, os, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import collect, strictjson
import capture_sources as CS


class Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status, self._b, self.headers = status, body, dict(headers or {})

    def getcode(self):
        return self.status

    def read(self, n=-1):
        return self._b if n < 0 else self._b[:n]

    def close(self):
        pass


class FakeOpener:
    """routes: url -> Resp 或 [Resp, ...]（依次返回）；未登记的 robots.txt → 404。"""

    def __init__(self, routes):
        self.routes, self.calls = dict(routes), []

    def open(self, req, timeout=None):
        u = req.full_url
        self.calls.append((u, req.get_header("User-agent")))
        r = self.routes.get(u)
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        if r is None:
            r = Resp(404) if u.endswith("/robots.txt") else Resp(404)
        if isinstance(r, Exception):
            raise r
        return r


def PUBLIC_DNS(host):
    """离线测试用解析器：所有主机名都解析到公网示例地址（不访问真实 DNS）。"""
    return {"93.184.216.34"}


def mk(routes, state=None, **kw):
    sleeps = []
    t = [0.0]

    def sleep(s):
        sleeps.append(s); t[0] += s
    kw.setdefault("resolver", PUBLIC_DNS)
    f = collect.Fetcher(state or collect.HostState(None), opener=FakeOpener(routes), sleep=sleep,
                        clock=lambda: t[0], **kw)
    return f, sleeps


class Gate(unittest.TestCase):
    def test_requires_approved_and_basis(self):
        self.assertFalse(collect.approval_gate({"enabled": True})[0])
        self.assertFalse(collect.approval_gate({"enabled": True, "approval_status": "pending",
                                                "approval_basis": "x"})[0])
        self.assertFalse(collect.approval_gate({"enabled": True, "approval_status": "approved"})[0])
        self.assertFalse(collect.approval_gate({"enabled": False, "approval_status": "approved",
                                                "approval_basis": "x"})[0])
        self.assertTrue(collect.approval_gate({"enabled": True, "approval_status": "approved",
                                               "approval_basis": "x"})[0])

    def test_repo_sources_yaml_consistent(self):
        import yaml
        p = Path(__file__).resolve().parents[1] / "improve" / "sources.yaml"
        for s in yaml.safe_load(p.read_text(encoding="utf-8"))["sources"]:
            self.assertIn(s.get("approval_status"), ("approved", "pending"), s["id"])
            if s.get("enabled"):
                self.assertEqual(s["approval_status"], "approved", s["id"])
                self.assertTrue(s.get("approval_basis"), s["id"])
            self.assertNotEqual(s.get("license"), "full-text-ok", s["id"])   # 不再整源全文许可
            self.assertNotIn("198.18.", json.dumps(s), s["id"])               # 不写代理/内网地址


class Paths(unittest.TestCase):
    def test_private_root_required_and_disjoint(self):
        env = os.environ.pop("MARKJIN_PRIVATE_DIR", None)
        try:
            with self.assertRaises(collect.ConfigError):
                collect.resolve_private_root(None, "/tmp/pubx")
            with self.assertRaises(collect.ConfigError):
                collect.resolve_private_root("/tmp/pubx/private", "/tmp/pubx")
            with self.assertRaises(collect.ConfigError):
                collect.resolve_private_root("/tmp/a", "/tmp/a/repo")
            self.assertEqual(collect.resolve_private_root("/tmp/privy", "/tmp/pubx"), Path("/tmp/privy").resolve())
        finally:
            if env is not None:
                os.environ["MARKJIN_PRIVATE_DIR"] = env

    def test_no_default_local_paths_in_scripts(self):
        root = Path(__file__).resolve().parents[1] / "scripts"
        for f in list(root.glob("*.py")) + list(root.glob("markjin/*.py")) + list(root.glob("scrapers/*.py")):
            if f.name in ("capture_sources.py", "fetch_primary.py", "x_capture.py", "collect.py") or \
               f.parent.name == "scrapers":
                self.assertNotIn("/workspace", f.read_text(encoding="utf-8"), f.name)


class Redact(unittest.TestCase):
    def test_public_url_strips_secrets_and_tracking(self):
        u = collect.public_url("https://user:pw@Example.org/a?api_key=SEKRIT&page=1&utm_source=t&token=T&s=20#f",
                               public_path=True)
        self.assertEqual(u, "https://example.org/a")
        self.assertNotIn("SEKRIT", collect.public_url("https://e.org/?apiKey=SEKRIT"))
        self.assertNotIn("SEKRIT", collect.public_url("https://e.org/?X-Amz-Signature=SEKRIT"))


class License(unittest.TestCase):
    EV = {"url": "https://journals.aps.org/prxquantum/abstract/10.1103/X", "license": "CC-BY-4.0",
          "license_url": "https://creativecommons.org/licenses/by/4.0/", "evidence_url": "https://journals.aps.org/x",
          "attribution": "A. Author, PRX Quantum 7, 1 (2026), DOI 10.1103/X", "verified_by": "jw",
          "verified_at": "2026-10-12"}

    def test_default_private(self):
        self.assertFalse(collect.public_fulltext_ok(None, "https://www.nasa.gov/x")[0])
        self.assertFalse(collect.public_fulltext_ok(None, "https://www.bls.gov/x")[0])

    def test_per_item_evidence(self):
        self.assertTrue(collect.public_fulltext_ok(self.EV, self.EV["url"])[0])
        self.assertFalse(collect.public_fulltext_ok(self.EV, "https://journals.aps.org/other")[0])
        self.assertFalse(collect.public_fulltext_ok(dict(self.EV, attribution=""), self.EV["url"])[0])
        self.assertFalse(collect.public_fulltext_ok(dict(self.EV, license="CC-BY-NC-4.0"), self.EV["url"])[0])
        pd = dict(self.EV, license="US-Gov-PD")
        self.assertFalse(collect.public_fulltext_ok(pd, self.EV["url"])[0])
        self.assertTrue(collect.public_fulltext_ok(dict(pd, third_party_excluded=True), self.EV["url"])[0])

    def test_evidence_file_strict(self):
        p = Path(tempfile.mkdtemp()) / "ev.jsonl"
        p.write_text('{"url": "https://a.org/x", "url": "https://b.org/y"}\n', encoding="utf-8")
        with self.assertRaises(strictjson.DuplicateKeyError):
            collect.load_license_evidence(p)


class ArchiveT(unittest.TestCase):
    def test_exclusive_and_manifest(self):
        d = Path(tempfile.mkdtemp())
        ar = collect.Archive(d)
        rel, sha = ar.put_raw("", "src", b"\x1f\x8b raw bytes", "gz")
        self.assertEqual((d / rel).read_bytes(), b"\x1f\x8b raw bytes")
        m = (d / "MANIFEST.sha256").read_text()
        self.assertEqual(m, f"{sha}  ./{rel}\n")
        ar.put_raw("", "src", b"\x1f\x8b raw bytes", "gz")          # 相同字节：去重，不重复登记
        self.assertEqual((d / "MANIFEST.sha256").read_text(), m)
        ar.put("x/log.json", b"1")
        with self.assertRaises(collect.ArchiveError):
            ar.put("x/log.json", b"2")                               # 拒绝改写
        self.assertEqual((d / "x/log.json").read_bytes(), b"1")
        drel, _ = ar.put_derived("", "src", sha, "json", b"{}")
        self.assertIn("/derived/", drel)
        self.assertNotIn(drel, (d / "MANIFEST.sha256").read_text())  # 派生物不冒充原件
        self.assertIn(drel, (d / "DERIVED.sha256").read_text())


class FetchT(unittest.TestCase):
    def test_honest_ua_and_robots_for_api(self):
        f, _ = mk({"https://api.e.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /private\n"),
                   "https://api.e.org/data": Resp(200, b"{}")})
        self.assertTrue(f.get("https://api.e.org/data").ok)
        self.assertFalse(f.get("https://api.e.org/private/x").ok)
        self.assertEqual(f.get("https://api.e.org/private/x").error, "robots_disallow")
        for _, ua in f.opener.calls:
            self.assertIn("markjin-collector", ua)
            self.assertIn("@", ua)
            self.assertNotIn("Mozilla", ua)

    def test_redirect_rechecks_robots(self):
        f, _ = mk({"https://a.org/x": Resp(302, headers={"Location": "https://b.org/secret"}),
                   "https://b.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /\n"),
                   "https://b.org/secret": Resp(200, b"data")})
        r = f.get("https://a.org/x")
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "robots_disallow")
        self.assertNotIn("https://b.org/secret", [u for u, _ in f.opener.calls])

    def test_refuses_tco_even_via_redirect(self):
        f, _ = mk({"https://a.org/x": Resp(301, headers={"Location": "https://t.co/abc"})})
        self.assertEqual(f.get("https://t.co/abc").error, "refused_host")
        self.assertEqual(f.get("https://a.org/x").error, "refused_host")

    def test_403_persistently_disables(self):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/x": Resp(403)}, state=collect.HostState(p))
        self.assertEqual(f.get("https://a.org/x", sid="s1").error, "http_403")
        st = collect.HostState(p)                                   # 新进程也看得到
        self.assertIn("a.org", st.data["hosts"])
        f2, _ = mk({"https://a.org/y": Resp(200, b"ok")}, state=st)
        r = f2.get("https://a.org/y")
        self.assertEqual(r.error, "disabled")
        self.assertEqual([u for u, _ in f2.opener.calls], [])

    def test_challenge_page_disables(self):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/x": Resp(200, b"<html><title>Just a moment...</title>")},
                  state=collect.HostState(p))
        self.assertEqual(f.get("https://a.org/x", sid="s").error, "challenge")
        self.assertIn("s", collect.HostState(p).data["sources"])

    def test_retry_backoff_and_retry_after(self):
        f, sleeps = mk({"https://a.org/x": [Resp(503), Resp(429, headers={"Retry-After": "7"}), Resp(200, b"ok")]})
        r = f.get("https://a.org/x")
        self.assertTrue(r.ok)
        self.assertIn(collect.BACKOFF_BASE, sleeps)
        self.assertIn(7.0, sleeps)

    def test_no_retry_on_404_and_bounded(self):
        f, _ = mk({"https://a.org/x": Resp(404)})
        self.assertEqual(f.get("https://a.org/x").error, "http_404")
        self.assertEqual(sum(1 for u, _ in f.opener.calls if u.endswith("/x")), 1)
        f, _ = mk({"https://a.org/y": Resp(500)})
        f.get("https://a.org/y")
        self.assertEqual(sum(1 for u, _ in f.opener.calls if u.endswith("/y")), collect.MAX_RETRIES + 1)

    def test_too_large_fails(self):
        f, _ = mk({"https://a.org/x": Resp(200, b"x" * 50)}, max_bytes=10)
        r = f.get("https://a.org/x")
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "too_large")

    def test_per_host_rate_limit_and_crawl_delay(self):
        f, sleeps = mk({"https://a.org/robots.txt": Resp(200, b"User-agent: *\nCrawl-delay: 5\n"),
                        "https://a.org/1": Resp(200, b"1"), "https://a.org/2": Resp(200, b"2")}, interval=2.0)
        f.get("https://a.org/1"); f.get("https://a.org/2")
        ts = [t for h, t in f.requests if h == "a.org"]
        self.assertEqual(len(ts), 3)                                  # robots + 2
        self.assertGreaterEqual(ts[1] - ts[0], 2.0)
        self.assertGreaterEqual(ts[2] - ts[1], 5.0)                   # 更严的 Crawl-delay 生效


class CaptureT(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.out, self.priv = self.base / "pub", self.base / "priv"
        self.out.mkdir()
        self.src = self.base / "s.yaml"

    def run_cs(self, sources, routes, extra=()):
        import yaml
        self.src.write_text(yaml.safe_dump({"sources": sources}), encoding="utf-8")
        orig = collect.Fetcher.__init__

        def init(s, *a, **k):
            k["opener"] = FakeOpener(routes); k["sleep"] = lambda x: None; k.setdefault("resolver", PUBLIC_DNS)
            orig(s, *a, **k)
        collect.Fetcher.__init__ = init
        try:
            return CS.main(["--sources", str(self.src), "--date", "2026-10-12", "--round", "1",
                            "--out-root", str(self.out), "--private-root", str(self.priv), *extra])
        finally:
            collect.Fetcher.__init__ = orig

    S = {"id": "feed", "theme": "ai", "method": "rss", "url": "https://f.org/rss?token=SEKRIT",
         "enabled": True, "approval_status": "approved", "approval_basis": "b", "license": "url+hash-only"}

    def test_refuses_unapproved(self):
        rc = self.run_cs([dict(self.S, approval_status="pending")], {"https://f.org/rss?token=SEKRIT": Resp(200, b"<rss/>")})
        self.assertEqual(rc, 1)
        self.assertFalse((self.out / "raw").exists())

    def test_raw_private_public_index_only(self):
        body = b"\xef\xbb\xbf<rss><channel/></rss>"
        rc = self.run_cs([self.S], {"https://f.org/rss?token=SEKRIT": Resp(200, body, {"Content-Type": "application/rss+xml"})})
        self.assertEqual(rc, 0)
        pday, oday = self.priv / "raw/2026-10-12", self.out / "raw/2026-10-12"
        raws = list((pday / "feed").glob("*.xml"))
        self.assertEqual(len(raws), 1)
        self.assertEqual(raws[0].read_bytes(), body)                  # 原字节，未改动
        self.assertIn(raws[0].name, (pday / "MANIFEST.sha256").read_text())
        pub_files = [p for p in oday.rglob("*") if p.is_file()]
        man = (oday / "MANIFEST.sha256").read_text()
        for p in pub_files:
            txt = p.read_text(encoding="utf-8")
            self.assertNotIn("<rss>", txt)                            # 全文不进公开目录
            self.assertNotIn("SEKRIT", txt)                           # 凭证参数不进公开记录
            self.assertNotIn(str(self.base), txt)                     # 不写本机路径
            if p.name != "MANIFEST.sha256":
                self.assertIn("./" + str(p.relative_to(oday)), man)   # 公开文件全部登记
        # 第二次运行：不覆盖，只新增
        before = {p: p.read_bytes() for p in pub_files if p.name != "MANIFEST.sha256"}
        self.run_cs([self.S], {"https://f.org/rss?token=SEKRIT": Resp(200, body)})
        for p, b in before.items():
            self.assertEqual(p.read_bytes(), b)
        self.assertTrue((self.out / "raw/2026-10-12/MANIFEST.sha256").read_text().startswith(man))

    def test_duplicate_key_json_is_unparseable(self):
        s = dict(self.S, id="api", method="api", url="https://f.org/a.json")
        rc = self.run_cs([s], {"https://f.org/a.json": Resp(200, b'{"a": 1, "a": 2}')})
        self.assertEqual(rc, 1)
        self.assertIsNone(CS.parse_ok(b'{"a": 1, "a": 2}'))
        self.assertEqual(CS.parse_ok(b'{"a": 1}'), "json")

    def test_auth_key_never_logged(self):
        s = dict(self.S, id="fred", method="api", url="https://api.f.org/obs?series_id=X",
                 auth_env="TEST_KEY_ENV", auth_param="api_key")
        os.environ["TEST_KEY_ENV"] = "SEKRITKEY"
        try:
            rc = self.run_cs([s], {"https://api.f.org/obs?series_id=X&api_key=SEKRITKEY": Resp(200, b'{"o": []}')})
        finally:
            del os.environ["TEST_KEY_ENV"]
        self.assertEqual(rc, 0)
        for root in (self.out, self.priv):
            for p in root.rglob("*"):
                if p.is_file() and p.suffix in (".json", ".jsonl", ".sha256"):
                    self.assertNotIn("SEKRITKEY", p.read_text(encoding="utf-8"))

    def test_missing_private_root_is_config_error(self):
        env = os.environ.pop("MARKJIN_PRIVATE_DIR", None)
        try:
            self.src.write_text("sources: []\n", encoding="utf-8")
            self.assertEqual(CS.main(["--sources", str(self.src), "--date", "2026-10-12", "--round", "1",
                                      "--out-root", str(self.out)]), 2)
        finally:
            if env is not None:
                os.environ["MARKJIN_PRIVATE_DIR"] = env


class R2Fixes(unittest.TestCase):
    """PR #3 审查 r2 REJECTED 修复的针对性测试。"""

    def test_robots_redirect_to_tco_refused(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(302, headers={"Location": "https://t.co/r"}),
                   "https://t.co/r": Resp(200, b""), "https://a.org/x": Resp(200, b"body")})
        r = f.get("https://a.org/x")
        self.assertEqual(r.error, "robots_disallow")
        urls = [u for u, _ in f.opener.calls]
        self.assertNotIn("https://t.co/r", urls)
        self.assertNotIn("https://a.org/x", urls)

    def test_robots_cross_host_redirect_is_disallow(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(301, headers={"Location": "https://cdn.b.org/robots.txt"}),
                   "https://cdn.b.org/robots.txt": Resp(200, b"User-agent: *\nAllow: /\n"),
                   "https://a.org/x": Resp(200, b"body")})
        self.assertEqual(f.get("https://a.org/x").error, "robots_disallow")
        self.assertNotIn("https://cdn.b.org/robots.txt", [u for u, _ in f.opener.calls])

    def test_robots_redirect_bad_scheme_and_disabled_host(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(302, headers={"Location": "ftp://a.org/robots.txt"}),
                   "https://a.org/x": Resp(200, b"body")})
        self.assertEqual(f.get("https://a.org/x").error, "robots_disallow")
        st = collect.HostState(None)
        st.disable("a.org", None, "manual")
        f, _ = mk({"http://a.org/robots.txt": Resp(301, headers={"Location": "https://a.org/robots.txt"})}, state=st)
        f.robots("http://a.org/x")                       # 同主机跳转，但目标主机已停用
        self.assertEqual([u for u, _ in f.opener.calls], ["http://a.org/robots.txt"])

    def test_robots_same_host_redirect_ok(self):
        f, _ = mk({"http://a.org/robots.txt": Resp(301, headers={"Location": "https://a.org/robots.txt"}),
                   "https://a.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /p\n")})
        rp = f.robots("http://a.org/x")
        self.assertTrue(rp.can_fetch("markjin-collector", "http://a.org/x"))
        self.assertFalse(rp.can_fetch("markjin-collector", "http://a.org/p"))

    def _robots_disables(self, resp):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/x": Resp(200, b"body")},
                  state=collect.HostState(p))
        r = f.get("https://a.org/x", sid="s1")
        self.assertEqual(r.error, "disabled")
        self.assertNotIn("https://a.org/x", [u for u, _ in f.opener.calls])
        d = collect.HostState(p).data
        self.assertIn("a.org", d["hosts"])
        self.assertIn("s1", d["sources"])

    def test_robots_403_disables(self):
        self._robots_disables(Resp(403))

    def test_robots_200_challenge_disables(self):
        self._robots_disables(Resp(200, b"<html><title>Just a moment...</title></html>"))

    def test_robots_503_challenge_disables(self):
        self._robots_disables(Resp(503, b"<script src='/cdn-cgi/challenge-platform/x'></script>"))

    def test_hops_redacted_after_302_no_api_key_anywhere(self):
        f, _ = mk({"https://api.f.org/obs?series_id=X&api_key=SEKRITKEY":
                   Resp(302, headers={"Location": "https://api.f.org/v2/obs?series_id=X&api_key=SEKRITKEY"}),
                   "https://api.f.org/v2/obs?series_id=X&api_key=SEKRITKEY": Resp(200, b"{}")})
        r = f.get("https://api.f.org/obs?series_id=X&api_key=SEKRITKEY")
        self.assertTrue(r.ok)
        self.assertNotIn("SEKRITKEY", json.dumps(r.hops))
        self.assertEqual(r.hops[0]["from"], "https://api.f.org/#sha256=" +
                         collect.url_sha256("https://api.f.org/obs?series_id=X&api_key=SEKRITKEY"))
        self.assertEqual(r.hops[0]["query_param_count"], 2)
        self.assertNotIn("api_key", json.dumps(r.hops))

    def test_capture_after_302_no_api_key_in_any_log(self):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        s = dict(CaptureT.S, id="fred", method="api", url="https://api.f.org/obs?series_id=X",
                 auth_env="TEST_KEY_ENV", auth_param="api_key")
        os.environ["TEST_KEY_ENV"] = "SEKRITKEY"
        import io, contextlib
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                rc = t.run_cs([s], {
                    "https://api.f.org/obs?series_id=X&api_key=SEKRITKEY":
                        Resp(302, headers={"Location": "/v2/obs?series_id=X&api_key=SEKRITKEY"}),
                    "https://api.f.org/v2/obs?series_id=X&api_key=SEKRITKEY": Resp(200, b'{"o": []}')})
        finally:
            del os.environ["TEST_KEY_ENV"]
        self.assertEqual(rc, 0)
        self.assertNotIn("SEKRITKEY", err.getvalue())
        logs = [p for root in (t.out, t.priv) for p in root.rglob("*") if p.is_file()
                and p.suffix in (".json", ".jsonl", ".sha256", ".tsv")]
        self.assertTrue(any("fetch-log" in p.name for p in logs))
        for p in logs:
            self.assertNotIn("SEKRITKEY", p.read_text(encoding="utf-8"), p.name)
        fl = next(p for p in logs if "fetch-log" in p.name).read_text(encoding="utf-8")
        self.assertIn('"hops": [{"from": "https://api.f.org/#sha256=', fl)

    def test_public_url_allowlist(self):
        u = collect.public_url("https://s3.a.org/o?AWSAccessKeyId=AKIA123&Expires=1&Signature=S&series_id=X"
                               "&X-Goog-Credential=G&whatever=W&page=2")
        self.assertTrue(u.startswith("https://s3.a.org/#sha256="))
        self.assertEqual(collect.public_url("https://a.org/o?series_id=X&page=TOK", ["series_id"], True),
                         "https://a.org/o?series_id=X")

    def test_interval_floor(self):
        f, _ = mk({}, interval=0)
        self.assertEqual(f.interval, collect.HOST_INTERVAL)
        d = Path(tempfile.mkdtemp())
        (d / "s.yaml").write_text("sources: []\n", encoding="utf-8")
        (d / "pub").mkdir()
        self.assertEqual(CS.main(["--sources", str(d / "s.yaml"), "--date", "2026-10-12", "--round", "1",
                                  "--out-root", str(d / "pub"), "--private-root", str(d / "priv"),
                                  "--interval", "0.5"]), 2)


class R3Fixes(unittest.TestCase):
    """PR #3 审查 r3 REJECTED 修复的针对性测试。"""

    def test_fetcher_forces_address_policy_on_redirect(self):
        f, _ = mk({"https://src.org/feed": Resp(302, headers={"Location": "http://127.0.0.1/admin"}),
                   "http://127.0.0.1/admin": Resp(200, b"{}")})
        r = f.get("https://src.org/feed", sid="s")
        self.assertEqual(r.error, "blocked_address")
        self.assertFalse(any("127.0.0.1" in u for u, _ in f.opener.calls))

    def test_forced_policy_cannot_be_disabled_by_extra_policy(self):
        f, _ = mk({"http://10.0.0.5/x": Resp(200, b"x")}, addr_policy=lambda u: None)
        f.addr_policy = lambda u: None
        self.assertEqual(f.get("http://10.0.0.5/x").error, "blocked_address")
        self.assertEqual(f.opener.calls, [])

    def test_extra_policy_is_conjunctive(self):
        f, _ = mk({"https://a.org/x": Resp(200, b"x")}, addr_policy=lambda u: "extra says no")
        r = f.get("https://a.org/x")
        self.assertEqual((r.error, r.detail), ("blocked_address", "extra says no"))

    def test_hostname_resolving_private_blocked_by_default(self):
        f, _ = mk({"https://in.example/x": Resp(200, b"x")}, resolver=lambda h: {"192.168.0.10"})
        self.assertEqual(f.get("https://in.example/x").error, "blocked_address")
        self.assertEqual(f.opener.calls, [])

    def test_fakeip_only_when_configured(self):
        fake = lambda h: {"198.18.0.7"}
        f, _ = mk({"https://a.org/x": Resp(200, b"x")}, resolver=fake, fakeip_cidr="")
        self.assertEqual(f.get("https://a.org/x").error, "blocked_address")
        f, _ = mk({"https://a.org/x": Resp(200, b"x")}, resolver=fake, fakeip_cidr="198.18.0.0/15")
        self.assertTrue(f.get("https://a.org/x").ok)
        f, _ = mk({"http://198.18.0.7/x": Resp(200, b"x")}, resolver=fake, fakeip_cidr="198.18.0.0/15")
        self.assertEqual(f.get("http://198.18.0.7/x").error, "blocked_address")    # IP 字面量永远拒绝
        with self.assertRaises(collect.ConfigError):
            mk({}, fakeip_cidr="10.0.0.0/8")

    def test_mapped_and_odd_ip_forms_blocked(self):
        p = collect.AddressPolicy(resolver=lambda h: {"127.0.0.1"} if h in ("2130706433", "0x7f.1", "0") else {"93.184.216.34"})
        for u in ("http://[::ffff:127.0.0.1]/", "http://[::ffff:198.18.0.1]/", "http://2130706433/", "http://0x7f.1/",
                  "http://0/", "http://localhost./"):
            self.assertIsNotNone(p(u), u)
        self.assertIsNotNone(collect.AddressPolicy(resolver=lambda h: {"::ffff:10.0.0.1"})("http://m.example/"))

    def test_capture_sources_redirect_to_loopback_not_requested(self):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        routes = {"https://f.org/rss": Resp(302, headers={"Location": "http://127.0.0.1/admin"}),
                  "http://127.0.0.1/admin": Resp(200, b"<rss/>")}
        import yaml
        t.src.write_text(yaml.safe_dump({"sources": [dict(CaptureT.S, url="https://f.org/rss")]}), encoding="utf-8")
        op = FakeOpener(routes)
        orig = collect.Fetcher.__init__

        def init(s, *a, **k):
            k["opener"] = op; k["sleep"] = lambda x: None; k["resolver"] = PUBLIC_DNS
            orig(s, *a, **k)
        collect.Fetcher.__init__ = init
        try:
            rc = CS.main(["--sources", str(t.src), "--date", "2026-10-12", "--round", "1",
                          "--out-root", str(t.out), "--private-root", str(t.priv)])
        finally:
            collect.Fetcher.__init__ = orig
        self.assertEqual(rc, 1)
        self.assertFalse(any("127.0.0.1" in u for u, _ in op.calls))
        fails = next((t.out / "raw/2026-10-12").glob("failures-*.json")).read_text()
        self.assertIn("blocked_address", fails)

    def test_capture_sources_rejects_bad_fakeip_cidr(self):
        d = Path(tempfile.mkdtemp()); (d / "s.yaml").write_text("sources: []\n"); (d / "pub").mkdir()
        self.assertEqual(CS.main(["--sources", str(d / "s.yaml"), "--date", "2026-10-12", "--round", "1",
                                  "--out-root", str(d / "pub"), "--private-root", str(d / "priv"),
                                  "--proxy-fakeip-cidr", "10.0.0.0/8"]), 2)

    def _robots_html(self, body, ctype="text/html"):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/robots.txt": Resp(200, body, {"Content-Type": ctype}),
                   "https://a.org/p": Resp(200, b"ok")}, state=collect.HostState(p))
        r = f.get("https://a.org/p", sid="s")
        self.assertEqual(r.error, "disabled")
        self.assertNotIn("https://a.org/p", [u for u, _ in f.opener.calls])
        self.assertIn("a.org", collect.HostState(p).data["hosts"])

    def test_robots_generic_captcha_div_disables(self):
        self._robots_html(b'<html><div id="captcha">verify</div></html>')

    def test_robots_any_html_disables(self):
        self._robots_html(b"<!DOCTYPE html><html><body>Welcome</body></html>")
        self._robots_html(b"<html><body>no ctype</body></html>", ctype="text/plain")

    def test_robots_plain_text_still_parsed(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /x\n", {"Content-Type": "text/plain"}),
                   "https://a.org/p": Resp(200, b"ok")})
        self.assertTrue(f.get("https://a.org/p").ok)

    def test_robots_404_html_is_not_challenge(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(404, b"<html>not found</html>", {"Content-Type": "text/html"}),
                   "https://a.org/p": Resp(200, b"ok")})
        self.assertTrue(f.get("https://a.org/p").ok)

    def test_challenge_regex_variants(self):
        for b in (b'<div id="captcha">', b"<div id=captcha>", b'<div class="g-recaptcha" data-sitekey=x>',
                  b'<script src="https://hcaptcha.com/1/api.js">', b'<div class="h-captcha">'.replace(b"h-", b"h"),
                  b"<title>Security captcha</title>", b"Just a moment...", b"<TITLE>Access Denied</TITLE>"):
            self.assertTrue(collect.CHALLENGE.search(b), b)
        self.assertFalse(collect.CHALLENGE.search(b"<p>We discuss CAPTCHA research in this paper.</p>"))

    def test_logs_have_no_query_values(self):
        self.assertEqual(collect.public_url("https://a.org/?page=TOKENVALUE&q=api_key%3DTOKENVALUE", public_path=True),
                         "https://a.org/")
        self.assertNotIn("TOKENVALUE", collect.public_url("https://a.org/?page=TOKENVALUE"))
        self.assertEqual(collect.query_count("https://a.org/?page=TOKENVALUE&q=x&page=2"), 3)

    def test_capture_public_params_declared_per_source(self):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        s = dict(CaptureT.S, id="api", method="api", url="https://f.org/a.json?series_id=S1&page=TOKENVALUE",
                 public_params=["series_id"], public_path=True)
        rc = t.run_cs([s], {"https://f.org/a.json?series_id=S1&page=TOKENVALUE": Resp(200, b'{"o": 1}')})
        self.assertEqual(rc, 0)
        txt = "".join(p.read_text() for root in (t.out, t.priv) for p in root.rglob("*")
                      if p.is_file() and p.suffix in (".json", ".jsonl"))
        self.assertNotIn("TOKENVALUE", txt)
        self.assertIn("a.json?series_id=S1", txt)
        self.assertIn('"query_param_count": 2', txt)

    def test_interval_nan_inf_rejected(self):
        for bad in ("nan", "inf", "-inf", "1.9"):
            d = Path(tempfile.mkdtemp()); (d / "s.yaml").write_text("sources: []\n"); (d / "pub").mkdir()
            self.assertEqual(CS.main(["--sources", str(d / "s.yaml"), "--date", "2026-10-12", "--round", "1",
                                      "--out-root", str(d / "pub"), "--private-root", str(d / "priv"),
                                      f"--interval={bad}"]), 2, bad)
        with self.assertRaises(collect.ConfigError):
            mk({}, interval=float("nan"))
        with self.assertRaises(collect.ConfigError):
            collect.check_interval(float("inf"))
        self.assertEqual(collect.check_interval(2), 2.0)


class R4Fixes(unittest.TestCase):
    """PR #3 审查 r4 REJECTED 修复的针对性测试。"""

    def test_challenge_new_markers(self):
        for b in (b'<div class="cf-turnstile" data-sitekey=x>', b'<form id="challenge-form" action=/x>',
                  b"<script src='/_Incapsula_Resource?x'>", b'<div id="px-captcha">', b'<div class="geetest_panel">',
                  b"<title>Verify you are human</title>", b"<title>Amazon.com - Robot Check</title>"):
            self.assertTrue(collect.CHALLENGE.search(b), b)
        self.assertFalse(collect.CHALLENGE.search(b"<p>How to verify you are human: a survey</p>"))

    def test_content_page_with_new_markers_disables(self):
        for b in (b"<html><title>Verify you are human</title></html>", b'<div class="cf-turnstile"></div>',
                  b'<form id="challenge-form"></form>', b'<div id="px-captcha"></div>', b"<div class=geetest_x>"):
            p = Path(tempfile.mkdtemp()) / "st.json"
            f, _ = mk({"https://a.org/p": Resp(200, b)}, state=collect.HostState(p))   # robots 404
            r = f.get("https://a.org/p", sid="s")
            self.assertEqual(r.error, "challenge", b)
            self.assertFalse(r.ok)
            self.assertIn("a.org", collect.HostState(p).data["hosts"])

    def _robots(self, resp):
        p = Path(tempfile.mkdtemp()) / "st.json"
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/p": Resp(200, b"ok")}, state=collect.HostState(p))
        r = f.get("https://a.org/p", sid="s")
        return r, f, collect.HostState(p).data

    def test_robots_401_429_5xx_html_suspected_challenge_no_retry(self):
        for st in (401, 429, 500, 503):
            r, f, d = self._robots(Resp(st, b"<html><body>please wait</body></html>", {"Content-Type": "text/html"}))
            self.assertEqual(r.error, "disabled", st)
            self.assertIn("pending manual review", d["hosts"]["a.org"]["reason"])
            calls = [u for u, _ in f.opener.calls]
            self.assertEqual(calls.count("https://a.org/robots.txt"), 1, st)       # 不重复请求
            self.assertNotIn("https://a.org/p", calls)

    def test_robots_5xx_plain_still_retried_and_disallowed_not_disabled(self):
        r, f, d = self._robots(Resp(503, b"busy", {"Content-Type": "text/plain"}))
        self.assertEqual(r.error, "robots_disallow")
        self.assertEqual(d["hosts"], {})
        self.assertEqual([u for u, _ in f.opener.calls].count("https://a.org/robots.txt"), collect.MAX_RETRIES + 1)

    def test_robots_404_410_html_is_no_robots(self):
        for st in (404, 410):
            r, _, d = self._robots(Resp(st, b"<html>nf</html>", {"Content-Type": "text/html"}))
            self.assertTrue(r.ok, st)
            self.assertEqual(d["hosts"], {})

    def test_robots_same_host_redirect_hops_checked_by_policies(self):
        seen = []

        def extra(u):
            seen.append(u)
            return "extra blocks hop" if u.startswith("https://a.org/robots") else None
        f, _ = mk({"http://a.org/robots.txt": Resp(301, headers={"Location": "https://a.org/robots.txt"}),
                   "https://a.org/robots.txt": Resp(200, b"User-agent: *\nAllow: /\n")}, addr_policy=extra)
        rp = f.robots("http://a.org/x")
        self.assertIn("https://a.org/robots.txt", seen)
        self.assertNotIn("https://a.org/robots.txt", [u for u, _ in f.opener.calls])
        self.assertFalse(rp.can_fetch("markjin-collector", "http://a.org/x"))
        # 强制策略：同主机跳转后主机重新解析到内网 → 不请求
        n = [0]

        def dns(h):
            n[0] += 1
            return {"93.184.216.34"} if n[0] == 1 else {"127.0.0.1"}
        f, _ = mk({"http://b.org/robots.txt": Resp(301, headers={"Location": "https://b.org/robots.txt"}),
                   "https://b.org/robots.txt": Resp(200, b"")}, resolver=dns)
        f.robots("http://b.org/x")
        self.assertEqual([u for u, _ in f.opener.calls], ["http://b.org/robots.txt"])

    def test_robots_direct_call_checks_policy(self):
        f, _ = mk({"http://127.0.0.1/robots.txt": Resp(200, b"")})
        rp = f.robots("http://127.0.0.1/x")
        self.assertEqual(f.opener.calls, [])
        self.assertFalse(rp.can_fetch("markjin-collector", "http://127.0.0.1/x"))

    def test_query_param_names_not_logged(self):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        s = dict(CaptureT.S, id="api", method="api", url="https://f.org/a.json?TOKENNAME=1&x=2")
        routes = {"https://f.org/a.json?TOKENNAME=1&x=2": Resp(302, headers={"Location": "/b.json?OTHERSECRET=1"}),
                  "https://f.org/b.json?OTHERSECRET=1": Resp(200, b'{"o": 1}')}
        self.assertEqual(t.run_cs([s], routes), 0)
        txt = "".join(p.read_text() for root in (t.out, t.priv) for p in root.rglob("*") if p.is_file()
                      and p.suffix in (".json", ".jsonl"))
        self.assertNotIn("TOKENNAME", txt)
        self.assertNotIn("OTHERSECRET", txt)
        self.assertIn('"query_param_count": 2', txt)


class R5Fixes(unittest.TestCase):
    """PR #3 审查 r5 REJECTED 修复的针对性测试（临时目录用 TemporaryDirectory）。"""

    def tmpdir(self):
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_looks_html_fragments(self):
        for b in (b"<div>Check your browser</div>", b"  \n<p>x", b"<!DOCTYPE html>", b"<span class=a>", b"<br/>",
                  b"\xef\xbb\xbf<div>x</div>"):
            self.assertTrue(collect.looks_html({"Content-Type": "text/plain"}, b), b)
        for b in (b"User-agent: *\nDisallow: /\n", b"# comment <div>\nUser-agent: *", b"< not a tag", b"<3 robots"):
            self.assertFalse(collect.looks_html({"Content-Type": "text/plain"}, b), b)

    def _robots(self, resp):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/p": Resp(200, b"ok")}, state=collect.HostState(p))
        r = f.get("https://a.org/p", sid="s")
        return r, [u for u, _ in f.opener.calls], collect.HostState(p).data

    def test_robots_text_plain_html_fragment_200_and_429_disable(self):
        for st in (200, 429):
            r, calls, d = self._robots(Resp(st, b"<div>Check your browser</div>", {"Content-Type": "text/plain"}))
            self.assertEqual(r.error, "disabled", st)
            self.assertIn("a.org", d["hosts"], st)
            self.assertNotIn("https://a.org/p", calls)
            self.assertEqual(calls.count("https://a.org/robots.txt"), 1, st)          # 429 也不重试

    def test_robots_302_with_challenge_body_disables_before_location(self):
        r, calls, d = self._robots(Resp(302, b'<form id="challenge-form"></form>',
                                        {"Location": "https://a.org/robots2.txt"}))
        self.assertEqual(r.error, "disabled")
        self.assertIn("a.org", d["hosts"])
        self.assertNotIn("https://a.org/robots2.txt", calls)
        self.assertNotIn("https://a.org/p", calls)

    def test_content_302_with_challenge_body_disables_before_location(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/x": Resp(302, b'<form id="challenge-form"></form>', {"Location": "https://a.org/y"}),
                   "https://a.org/y": Resp(200, b"ok")}, state=collect.HostState(p))
        r = f.get("https://a.org/x", sid="s")
        self.assertEqual(r.error, "challenge")
        self.assertNotIn("https://a.org/y", [u for u, _ in f.opener.calls])
        self.assertIn("a.org", collect.HostState(p).data["hosts"])

    def test_public_url_default_host_plus_hash(self):
        u = "https://docs.e.org/private/TOKENPATH/document?key=TOKENQUERY"
        pu = collect.public_url(u)
        self.assertEqual(pu, "https://docs.e.org/#sha256=" + collect.url_sha256(u))
        self.assertNotIn("TOKENPATH", pu)
        self.assertEqual(collect.public_url(u, public_path=True), "https://docs.e.org/private/TOKENPATH/document")

    def test_capture_index_path_only_when_source_confirms(self):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        s1 = dict(CaptureT.S, id="a1", method="api", url="https://f.org/TOKENPATH/a.json")
        s2 = dict(CaptureT.S, id="a2", method="api", url="https://f.org/public/b.json", public_path=True)
        import io, contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = t.run_cs([s1, s2], {"https://f.org/TOKENPATH/a.json": Resp(200, b'{"o": 1}'),
                                     "https://f.org/public/b.json": Resp(200, b'{"o": 2}')})
        self.assertEqual(rc, 0)
        pub = "".join(p.read_text() for p in t.out.rglob("*") if p.is_file())
        self.assertNotIn("TOKENPATH", pub + err.getvalue())
        self.assertIn("https://f.org/#sha256=", pub)
        self.assertIn("https://f.org/public/b.json", pub)


if __name__ == "__main__":
    unittest.main()
