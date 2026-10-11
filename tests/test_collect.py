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


def mk(routes, state=None, **kw):
    sleeps = []
    t = [0.0]

    def sleep(s):
        sleeps.append(s); t[0] += s
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
        u = collect.public_url("https://user:pw@Example.org/a?api_key=SEKRIT&x=1&utm_source=t&token=T&s=20#f")
        self.assertEqual(u, "https://example.org/a?x=1")
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
            k["opener"] = FakeOpener(routes); k["sleep"] = lambda x: None
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


if __name__ == "__main__":
    unittest.main()
