"""PR #3/#6 审查修复：采集公共层与 capture_sources 的针对性测试（全部离线，假 opener）。"""
import json, os, tempfile, time, unittest
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


ROUND = "2026-10-12/r1"
# 现行封锁规则（出处见 collect.py「封锁规则与来源健康状态」）：单次可疑 → 该主机本轮全部停止、被拒 URL 冷却 ≥24 小时。
# 旧测试里「主机被停用」的断言改为「该主机本轮因 401/403/429/厂商验证页停止」（HARD），语义上保留分类结果。
HARD = {"http_401", "http_403", "http_429", "challenge", "robots_http_401", "robots_http_403", "robots_http_429",
        "robots_challenge"}
ROBOTS_HARD = {"robots_http_401", "robots_http_403", "robots_http_429", "robots_challenge"}


def view(p):
    """{"hosts": {主机: 原因}, "sources": {sid: 原因}}：各轮因 HARD 原因停止的主机与对应源。"""
    d = {"hosts": {}, "sources": {}}
    for m in collect.SourceHealth(p).data["host_stops"].values():
        for h, rec in m.items():
            if rec["reason"] in HARD:
                d["hosts"][h] = rec["reason"]
                if rec["sid"]:
                    d["sources"][rec["sid"]] = rec["reason"]
    return d


def mk(routes, state=None, **kw):
    sleeps = []
    t = [0.0]

    def sleep(s):
        sleeps.append(s); t[0] += s
    kw.setdefault("resolver", PUBLIC_DNS)
    state = state if state is not None else collect.SourceHealth(None)
    if state.path:
        kw.setdefault("round_id", ROUND)
    f = collect.Fetcher(state, opener=FakeOpener(routes), sleep=sleep, clock=lambda: t[0], **kw)
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
            self.assertIn("https://", ua)                 # 联系方式用网址，代码里不写死邮箱
            self.assertNotIn("@", ua)
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

    def test_403_stops_host_this_round_and_url_cools_down(self):
        # 现行规则：403 → 该主机本轮全部停止（新进程也看得到）、被拒 URL 冷却 ≥24 小时；下一轮同主机别的 URL 可请求
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/x": Resp(403)}, state=collect.SourceHealth(p))
        self.assertEqual(f.get("https://a.org/x", sid="s1").error, "http_403")
        self.assertEqual(f.suspicious["s1"][0]["reason"], "http_403")
        st = collect.SourceHealth(p)                                   # 新进程也看得到
        self.assertEqual(view(p)["hosts"], {"a.org": "http_403"})
        f2, _ = mk({"https://a.org/y": Resp(200, b"ok"), "https://a.org/x": Resp(200, b"ok")}, state=st)
        self.assertEqual(f2.get("https://a.org/y", sid="s2").error, "host_stopped_this_round")   # 同主机本轮全停
        self.assertEqual(f2.opener.calls, [])
        f3, _ = mk({"https://a.org/x": Resp(200, b"ok"), "https://a.org/y": Resp(200, b"ok")},
                   state=collect.SourceHealth(p), round_id="2026-10-12/r2")
        self.assertEqual(f3.get("https://a.org/x", sid="s1").error, "url_cooldown")   # 被拒 URL 下一轮仍在冷却
        self.assertTrue(f3.get("https://a.org/y", sid="s1").ok)                      # 下一轮同主机别的 URL 照常

    def test_challenge_page_disables(self):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/x": Resp(200, b'<html><div class="cf-turnstile"></div></html>')},
                  state=collect.SourceHealth(p))
        self.assertEqual(f.get("https://a.org/x", sid="s").error, "challenge")   # r8：只有厂商标记才停用
        self.assertIn("s", view(p)["sources"])

    def test_no_retry_on_any_http_status_429_suspicious(self):
        # 429 立即停、计可疑、不重试；5xx 也不自动重发；只有没收到响应的网络错误才重试
        f, sleeps = mk({"https://a.org/x": [Resp(429, headers={"Retry-After": "7"}), Resp(200, b"ok")]})
        r = f.get("https://a.org/x", sid="s")
        self.assertEqual(r.error, "http_429")
        self.assertTrue(collect.is_suspicious(r.error))
        self.assertEqual(sum(1 for u, _ in f.opener.calls if u.endswith("/x")), 1)
        self.assertEqual(f.suspicious["s"][0]["reason"], "http_429")
        self.assertEqual(f.get("https://a.org/z").error, "host_stopped_this_round")
        f, _ = mk({"https://a.org/y": [Resp(503), Resp(200, b"ok")]})
        self.assertEqual(f.get("https://a.org/y").error, "http_503")
        self.assertEqual(sum(1 for u, _ in f.opener.calls if u.endswith("/y")), 1)
        f, sleeps = mk({"https://a.org/n": [OSError("reset"), Resp(200, b"ok")]})
        self.assertTrue(f.get("https://a.org/n").ok)                 # 网络错误（无 HTTP 响应）可重试
        self.assertIn(collect.BACKOFF_BASE, sleeps)

    def test_no_retry_on_404(self):
        f, _ = mk({"https://a.org/x": Resp(404)})
        self.assertEqual(f.get("https://a.org/x").error, "http_404")
        self.assertEqual(sum(1 for u, _ in f.opener.calls if u.endswith("/x")), 1)

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
        st = collect.SourceHealth(None)
        st.set_status("s", "disabled", "manual")
        f, _ = mk({"http://a.org/robots.txt": Resp(301, headers={"Location": "https://a.org/robots.txt"})}, state=st)
        f.robots("http://a.org/x", sid="s")              # 已停用的源：robots() 入口直接禁止
        self.assertEqual([u for u, _ in f.opener.calls], [])

    def test_robots_same_host_redirect_ok(self):
        f, _ = mk({"http://a.org/robots.txt": Resp(301, headers={"Location": "https://a.org/robots.txt"}),
                   "https://a.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /p\n")})
        rp = f.robots("http://a.org/x")
        self.assertTrue(rp.can_fetch("markjin-collector", "http://a.org/x"))
        self.assertFalse(rp.can_fetch("markjin-collector", "http://a.org/p"))

    def _robots_disables(self, resp):
        p = Path(tempfile.mkdtemp()) / "state.json"
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/x": Resp(200, b"body")},
                  state=collect.SourceHealth(p))
        r = f.get("https://a.org/x", sid="s1")
        self.assertIn(r.error, ROBOTS_HARD)                         # robots.txt 可疑 → 该主机本轮停止
        self.assertNotIn("https://a.org/x", [u for u, _ in f.opener.calls])
        d = view(p)
        self.assertIn("a.org", d["hosts"])
        self.assertIn("s1", d["sources"])

    def test_robots_403_disables(self):
        self._robots_disables(Resp(403))

    def test_robots_200_challenge_disables(self):
        self._robots_disables(Resp(200, b'<html><div class="g-recaptcha"></div></html>'))

    def test_robots_503_challenge_disables(self):
        self._robots_disables(Resp(503, b"<script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>"))

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
                   "https://a.org/p": Resp(200, b"ok")}, state=collect.SourceHealth(p))
        r = f.get("https://a.org/p", sid="s")
        self.assertIn(r.error, ROBOTS_HARD)
        self.assertNotIn("https://a.org/p", [u for u, _ in f.opener.calls])
        self.assertIn("a.org", view(p)["hosts"])

    def test_robots_generic_captcha_div_disables(self):
        self._robots_html(b'<html><div class="g-recaptcha">verify</div></html>')   # r9：id=captcha 不再算组件

    def test_robots_any_html_disallowed_not_disabled(self):
        # r8：robots 返回 HTML 但没有厂商标记 = 格式不对 → 本轮按禁止，不算可疑
        for body, ct in ((b"<!DOCTYPE html><html><body>Welcome</body></html>", "text/html"),
                         (b"<html><body>no ctype</body></html>", "text/plain")):
            p = Path(tempfile.mkdtemp()) / "state.json"
            f, _ = mk({"https://a.org/robots.txt": Resp(200, body, {"Content-Type": ct}),
                       "https://a.org/p": Resp(200, b"ok")}, state=collect.SourceHealth(p))
            self.assertEqual(f.get("https://a.org/p", sid="s").error, "robots_disallow")
            self.assertNotIn("https://a.org/p", [u for u, _ in f.opener.calls])
            self.assertEqual(view(p)["hosts"], {})

    def test_robots_plain_text_still_parsed(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(200, b"User-agent: *\nDisallow: /x\n", {"Content-Type": "text/plain"}),
                   "https://a.org/p": Resp(200, b"ok")})
        self.assertTrue(f.get("https://a.org/p").ok)

    def test_robots_404_html_is_not_challenge(self):
        f, _ = mk({"https://a.org/robots.txt": Resp(404, b"<html>not found</html>", {"Content-Type": "text/html"}),
                   "https://a.org/p": Resp(200, b"ok")})
        self.assertTrue(f.get("https://a.org/p").ok)

    def test_challenge_regex_variants(self):
        for b in (b'<div class="g-recaptcha" data-sitekey=x>', b"<div class=g-recaptcha>",
                  b'<script src="https://hcaptcha.com/1/api.js">', b'<script src="https://www.google.com/recaptcha/api.js">'):
            self.assertTrue(collect.CHALLENGE.search(b), b)
        for b in (b'<div id="captcha">', b"<div id=captcha>", b'<div class="hcaptcha">'):
            self.assertIsNone(collect.CHALLENGE.search(b), b)                    # r9：只认真正的组件
        for b in (b"<html><title>Just a moment...</title></html>", b"<html><TITLE>Access Denied</TITLE></html>"):
            self.assertIsNone(collect.CHALLENGE.search(b), b)                    # r8：泛用短语不是厂商标记
            self.assertEqual(collect.classify_page("text/html", b), "phrase", b)
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
                  b"<script src='https://challenges.cloudflare.com/turnstile/v0/api.js'>",
                  b"<script src='/_Incapsula_Resource?x'>", b'<div id="px-captcha">'):       # r10 加回
            self.assertTrue(collect.CHALLENGE.search(b), b)
        for b in (b'<div class="geetest_panel">',):
            self.assertIsNone(collect.CHALLENGE.search(b), b)                    # 清单外不算
        for b in (b"<html><title>Verify you are human</title></html>", b"<html><title>Robot Check</title></html>"):
            self.assertEqual(collect.classify_page("text/html", b), "phrase", b)
        self.assertFalse(collect.CHALLENGE.search(b"<p>How to verify you are human: a survey</p>"))

    def test_content_page_with_new_markers_disables(self):
        for b in (b'<div class="cf-turnstile"></div>',
                  b'<form id="challenge-form"></form>'):
            p = Path(tempfile.mkdtemp()) / "st.json"
            f, _ = mk({"https://a.org/p": Resp(200, b)}, state=collect.SourceHealth(p))   # robots 404
            r = f.get("https://a.org/p", sid="s")
            self.assertEqual(r.error, "challenge", b)
            self.assertFalse(r.ok)
            self.assertIn("a.org", view(p)["hosts"])

    def _robots(self, resp):
        p = Path(tempfile.mkdtemp()) / "st.json"
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/p": Resp(200, b"ok")}, state=collect.SourceHealth(p))
        r = f.get("https://a.org/p", sid="s")
        return r, f, view(p)

    def test_robots_401_429_5xx_html_suspected_challenge_no_retry(self):
        for st in (401, 429, 500, 503):
            r, f, d = self._robots(Resp(st, b"<html><body>please wait</body></html>", {"Content-Type": "text/html"}))
            if st in (401, 429):                                    # 401、429 同 403，按状态码判可疑（429 不重试）
                self.assertEqual(r.error, f"robots_http_{st}", st)
                self.assertIn("a.org", d["hosts"])
            else:
                self.assertEqual(r.error, "robots_disallow", st)    # 本轮禁止，不停用
                self.assertEqual(d["hosts"], {}, st)
            calls = [u for u, _ in f.opener.calls]
            self.assertEqual(calls.count("https://a.org/robots.txt"), 1, st)       # 不重复请求
            self.assertNotIn("https://a.org/p", calls)

    def test_robots_5xx_plain_not_retried_disallowed_not_suspicious(self):
        r, f, d = self._robots(Resp(503, b"busy", {"Content-Type": "text/plain"}))
        self.assertEqual(r.error, "robots_disallow")
        self.assertEqual(d["hosts"], {})
        self.assertEqual([u for u, _ in f.opener.calls].count("https://a.org/robots.txt"), 1)   # 任何 HTTP 状态都不重发

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
        f, _ = mk({"https://a.org/robots.txt": resp, "https://a.org/p": Resp(200, b"ok")}, state=collect.SourceHealth(p))
        r = f.get("https://a.org/p", sid="s")
        return r, [u for u, _ in f.opener.calls], view(p)

    def test_robots_text_plain_html_fragment_200_and_429_disable(self):
        for st in (200, 429):
            r, calls, d = self._robots(Resp(st, b"<div>Check your browser</div>", {"Content-Type": "text/plain"}))
            if st == 200:
                self.assertEqual(r.error, "robots_suspected_challenge", st)   # text/plain 标签+短语 → 可疑（不算 HARD）
                self.assertEqual(d["hosts"], {}, st)
            else:
                self.assertEqual(r.error, "robots_http_429", st)              # 先按状态码
                self.assertIn("a.org", d["hosts"])
            self.assertNotIn("https://a.org/p", calls)
            self.assertEqual(calls.count("https://a.org/robots.txt"), 1, st)          # 429 也不重试

    def test_robots_302_with_challenge_body_disables_before_location(self):
        r, calls, d = self._robots(Resp(302, b'<form id="challenge-form"></form>',
                                        {"Location": "https://a.org/robots2.txt"}))
        self.assertEqual(r.error, "robots_challenge")
        self.assertIn("a.org", d["hosts"])
        self.assertNotIn("https://a.org/robots2.txt", calls)
        self.assertNotIn("https://a.org/p", calls)

    def test_content_302_with_challenge_body_disables_before_location(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/x": Resp(302, b'<form id="challenge-form"></form>', {"Location": "https://a.org/y"}),
                   "https://a.org/y": Resp(200, b"ok")}, state=collect.SourceHealth(p))
        r = f.get("https://a.org/x", sid="s")
        self.assertEqual(r.error, "challenge")
        self.assertNotIn("https://a.org/y", [u for u, _ in f.opener.calls])
        self.assertIn("a.org", view(p)["hosts"])

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


class R6Fixes(unittest.TestCase):
    """PR #3 审查 r6：按采集方式校验内容；无厂商标记的验证片段（200 / 3xx）。"""

    def tmpdir(self):
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    FRAG = b"<div>Check your browser</div>"

    def test_is_challenge_short_body_or_title_only(self):
        cp = collect.classify_page
        self.assertEqual(cp("text/html", self.FRAG), "phrase")
        self.assertIsNone(cp("text/plain", b"Checking your browser before accessing"))     # 非 HTML 不查短语
        self.assertEqual(cp("text/html", b"<title>Checking your browser</title>" + b"x" * 5000), "phrase")
        self.assertIsNone(cp("text/html", b"<p>" + b"long article " * 400 + b"check your browser settings</p>"))
        self.assertFalse(collect.is_challenge(self.FRAG))                                 # 短语不算高置信

    def test_content_suspect_rules(self):
        cs = collect.content_suspect
        self.assertIsNone(cs("rss", {}, b"\xef\xbb\xbf<?xml version='1.0'?><rss><channel/></rss>"))
        self.assertIsNone(cs("rss", {}, b"<feed xmlns='http://www.w3.org/2005/Atom'/>"))
        self.assertIsNone(cs("rss", {}, b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'/>"))
        self.assertEqual(cs("rss", {"Content-Type": "text/plain"}, b"<div>hello</div>"), "html")
        self.assertEqual(cs("rss", {}, b"<?xml version='1.0'?><error>x</error>"), "xml_root:error")
        self.assertEqual(cs("rss", {}, b"garbage"), "xml_unparseable")
        self.assertEqual(cs("rss", {"Content-Type": "text/html"}, b"<rss/>"), "html")
        self.assertIsNone(cs("api", {}, b'{"a": 1}'))
        self.assertEqual(cs("api", {}, b"<error/>"), "json_unparseable")
        self.assertEqual(cs("api", {}, b"oops"), "json_unparseable")
        self.assertEqual(cs("api", {"Content-Type": "text/plain"}, b"<span>wait</span>"), "html")
        self.assertIsNone(cs("api", {}, b"<eSearchResult/>", "xml", ["eSearchResult"]))
        self.assertEqual(cs("api", {}, b"<other/>", "xml", ["eSearchResult"]), "xml_root:other")

    def test_get_200_and_302_vendorless_fragment_disable(self):
        for resp in (Resp(200, self.FRAG, {"Content-Type": "text/plain"}),
                     Resp(302, self.FRAG, {"Location": "https://a.org/y", "Content-Type": "text/plain"})):
            p = self.tmpdir() / "st.json"
            f, _ = mk({"https://a.org/x": resp, "https://a.org/y": Resp(200, b"ok")}, state=collect.SourceHealth(p))
            r = f.get("https://a.org/x", sid="s")
            self.assertEqual(r.error, "suspected_challenge", resp.status)   # r9：本轮可疑，不停用
            self.assertNotIn("https://a.org/y", [u for u, _ in f.opener.calls])
            self.assertEqual(view(p)["hosts"], {})

    def _cs(self, src, resp):
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        rc = t.run_cs([src], {src["url"]: resp})
        day = t.out / "raw/2026-10-12"
        idx = list(day.rglob("index-*.json")) if day.exists() else []
        return rc, idx, t

    def test_capture_rss_api_suspect_fails_round_not_disabled(self):
        cases = [(dict(CaptureT.S, url="https://f.org/rss"), Resp(200, b"<div>please wait</div>", {"Content-Type": "text/plain"})),
                 (dict(CaptureT.S, url="https://f.org/rss"), Resp(200, b"<?xml version='1.0'?><error/>")),
                 (dict(CaptureT.S, method="api", url="https://f.org/a.json"), Resp(200, b"<root/>")),
                 (dict(CaptureT.S, method="api", url="https://f.org/a.json"), Resp(200, b"not json"))]
        for src, resp in cases:
            import io, contextlib
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc, idx, t = self._cs(src, resp)
            self.assertEqual(rc, 1, src)
            self.assertEqual(idx, [], src)
            hs = collect.SourceHealth(t.priv / "state/source-health.json")   # 新规则：只记本轮一次可疑，不停用
            self.assertEqual(hs.data["sources"]["feed"]["status"], "ok", src)
            self.assertTrue(hs.data["sources"]["feed"]["rounds"][ROUND]["suspicious"], src)
            self.assertIn("ERR", err.getvalue())
            fl = next((t.out / "raw/2026-10-12").glob("failures-*.json")).read_text()
            self.assertTrue("suspected_challenge" in fl or "challenge" in fl, fl)
            self.assertTrue(list((t.priv / "raw/2026-10-12").rglob("feed/*")))      # 原字节仍私有存档

    def test_capture_rss_302_vendorless_fragment_fails_not_disabled(self):
        src = dict(CaptureT.S, url="https://f.org/rss")
        t = CaptureT("test_auth_key_never_logged"); t.setUp()
        rc = t.run_cs([src], {"https://f.org/rss": Resp(302, self.FRAG, {"Location": "https://f.org/rss2"}),
                              "https://f.org/rss2": Resp(200, b"<rss/>")})
        self.assertEqual(rc, 1)
        self.assertFalse(list((t.out / "raw/2026-10-12").rglob("index-*.json")))
        hs = collect.SourceHealth(t.priv / "state/source-health.json")
        self.assertEqual(hs.data["sources"]["feed"]["status"], "ok")
        self.assertEqual(hs.data["sources"]["feed"]["rounds"][ROUND]["reasons"], ["suspected_challenge"])


class R7Fixes(unittest.TestCase):
    """PR #3 审查 r7：3xx 先验正文；title/可见文本前 2KB 短语；text/plain 标签；QName；逐跳原字节存档；
    JSON 顶层；DOCTYPE/ENTITY；SEC UA 与全局限速。"""

    def tmpdir(self):
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    LONG = (b"<html><head><title>One moment</title><style>" + b"x{}" * 300 + b"</style></head><body>"
            b"<div>Checking your browser before accessing the site.</div>" + b"<p>pad</p>" * 400 + b"</body></html>")

    LONGV = LONG.replace(b"</body>", b"<script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script></body>")   # 长页 + 厂商标记

    def test_long_page_phrase_in_visible_window(self):
        # r8：长页面里的短语（title 不是短语为主）不算；短页且短语为主才算 phrase（只可疑，不停用）
        self.assertIsNone(collect.classify_page("text/html", self.LONG))
        for b in (b"<div>Please verify that you are human to continue</div>",
                  b"<p>Please enable JavaScript and cookies to continue</p>",
                  b"<title>Just a moment...</title>"):
            self.assertEqual(collect.classify_page("text/html", b), "phrase", b)
        late = b"<p>" + b"long article text " * 200 + b"check your browser settings</p>"
        self.assertIsNone(collect.classify_page("text/html", late))
        self.assertFalse(collect.is_challenge(b"<p>We study CAPTCHA systems</p>"))

    def _get(self, routes, url="https://a.org/x"):
        p = self.tmpdir() / "st.json"
        f, _ = mk(routes, state=collect.SourceHealth(p))
        sink = []
        r = f.get(url, sid="s", raw_sink=lambda b, st, ct: sink.append((st, b)))
        return r, [u for u, _ in f.opener.calls], view(p), sink

    def test_302_long_challenge_not_followed_and_raw_sunk(self):
        r, calls, d, sink = self._get({"https://a.org/x": Resp(302, self.LONGV, {"Location": "https://a.org/y"}),
                                       "https://a.org/y": Resp(200, b"ok")})
        self.assertEqual(r.error, "challenge")
        self.assertNotIn("https://a.org/y", calls)
        self.assertIn("a.org", d["hosts"])
        self.assertEqual(sink, [(302, self.LONGV)])                   # 丢弃前已交给私有存档

    def test_robots_302_long_challenge_disables(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/robots.txt": Resp(302, self.LONGV, {"Location": "https://a.org/r2"}),
                   "https://a.org/x": Resp(200, b"ok")}, state=collect.SourceHealth(p))
        self.assertEqual(f.get("https://a.org/x", sid="s").error, "robots_challenge")
        self.assertIn("a.org", view(p)["hosts"])

    def test_text_plain_tag_start_alone_not_disabled(self):
        r, calls, d, sink = self._get({"https://a.org/x": Resp(200, b"<div>hello</div>", {"Content-Type": "text/plain"})})
        self.assertTrue(r.ok)                                         # r8：plain_html 只是辅助证据
        self.assertEqual(d["hosts"], {})
        r, calls, d, sink = self._get({"https://a.org/x": Resp(200, b"<div>Check your browser</div>",
                                                               {"Content-Type": "text/plain"})})
        self.assertEqual(r.error, "suspected_challenge")              # r9：辅助证据 + 短语 → 本轮可疑，不停用
        self.assertEqual(d["hosts"], {})
        r, *_ = self._get({"https://a.org/x": Resp(200, b"<?xml version='1.0'?><rss/>", {"Content-Type": "text/plain"})})
        self.assertTrue(r.ok)

    def test_every_hop_raw_sunk(self):
        r, calls, d, sink = self._get({"https://a.org/x": Resp(301, b"moved", {"Location": "https://a.org/y"}),
                                       "https://a.org/y": Resp(200, b"{}")})
        self.assertTrue(r.ok)
        self.assertEqual(sink, [(301, b"moved"), (200, b"{}")])

    def test_qname_roots_and_dtd_and_json_top(self):
        cs = collect.content_suspect
        self.assertIsNone(cs("rss", {}, b"<feed xmlns='http://www.w3.org/2005/Atom'/>"))
        self.assertEqual(cs("rss", {}, b"<feed xmlns='http://www.w3.org/1999/xhtml'/>"),
                         "xml_root:{http://www.w3.org/1999/xhtml}feed")
        self.assertIsNotNone(cs("rss", {}, b"<feed/>"))
        self.assertIsNotNone(cs("rss", {}, b"<rdf:RDF xmlns:rdf='urn:x'/>"))
        self.assertIsNone(cs("api", {}, b"<eSearchResult/>", "xml", ["eSearchResult"]))
        self.assertIsNotNone(cs("api", {}, b"<e:eSearchResult xmlns:e='urn:x'/>", "xml", ["eSearchResult"]))
        self.assertEqual(cs("rss", {}, b"<?xml version='1.0'?><!DOCTYPE x [<!ENTITY a 'b'>]><rss>&a;</rss>"),
                         "xml_internal_subset_or_entity")
        self.assertIsNone(cs("rss", {}, b"<!DOCTYPE rss><rss/>"))              # r8：外部/无子集 DOCTYPE 放行
        for b in (b"null", b'"Just a moment"', b"1", b"true"):
            self.assertEqual(cs("api", {}, b), "json_unparseable", b)
        self.assertIsNone(cs("api", {}, b"[]"))
        self.assertIsNone(CS.parse_ok(b"null"))
        self.assertEqual(CS.parse_ok(b"<!DOCTYPE x><rss/>"), "xml")
        self.assertIsNone(CS.parse_ok(b"<!DOCTYPE x [<!ENTITY a 'b'>]><rss/>"))

    def test_sec_unconfigured_skipped_no_request_no_disable(self):
        import os
        old = os.environ.pop(collect.SEC_UA_ENV, None)
        try:
            p = self.tmpdir() / "st.json"
            f, _ = mk({"https://data.sec.gov/robots.txt": Resp(200, b""), "https://data.sec.gov/a.json": Resp(200, b"{}")},
                      state=collect.SourceHealth(p))
            r = f.get("https://data.sec.gov/a.json", sid="sec-edgar-aapl")
            self.assertEqual(r.error, "not_configured")
            self.assertEqual(f.opener.calls, [])
            self.assertEqual(view(p)["hosts"], {})
            os.environ[collect.SEC_UA_ENV] = "no contact here"
            self.assertIsNone(collect.sec_user_agent())
        finally:
            os.environ.pop(collect.SEC_UA_ENV, None)
            if old is not None:
                os.environ[collect.SEC_UA_ENV] = old

    def test_sec_capture_skipped_not_failure(self):
        import os, io, contextlib
        old = os.environ.pop(collect.SEC_UA_ENV, None)
        try:
            t = CaptureT("test_auth_key_never_logged"); t.setUp()
            src = dict(CaptureT.S, id="sec-edgar-aapl", method="api", url="https://data.sec.gov/submissions/C.json")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc = t.run_cs([src], {"https://data.sec.gov/submissions/C.json": Resp(200, b"{}")})
            self.assertEqual(rc, 0)
            self.assertIn("not_configured", err.getvalue())
            day = t.out / "raw/2026-10-12"
            self.assertIn("not_configured", next(day.glob("skipped-*.json")).read_text())
            self.assertFalse(list(day.rglob("index-*.json")))
        finally:
            if old is not None:
                os.environ[collect.SEC_UA_ENV] = old

    def test_sec_ua_from_env_and_global_rate(self):
        import os
        old = os.environ.get(collect.SEC_UA_ENV)
        os.environ[collect.SEC_UA_ENV] = "markjin research (+https://example.org/contact)"
        try:
            t = [100.0]
            slept = []
            f, waits = mk({"https://data.sec.gov/robots.txt": Resp(200, b""), "https://www.sec.gov/robots.txt": Resp(200, b""),
                           "https://data.sec.gov/a": Resp(200, b"{}"), "https://www.sec.gov/b": Resp(200, b"{}")})
            r = f.get("https://data.sec.gov/a")
            self.assertEqual(r.error, "not_configured")                   # r10：没有 lock_dir → 不发请求
            self.assertEqual(f.opener.calls, [])
            from unittest import mock
            d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup)
            f.lock_dir = Path(d.name)
            self.assertTrue(f.get("https://data.sec.gov/a").ok)
            self.assertTrue(f.get("https://www.sec.gov/b").ok)
            self.assertIn(0.2, [round(w, 6) for w in waits])              # sec.gov 站内 5 次/秒（不是 60 秒）
            self.assertLessEqual(max(waits), collect.HOST_INTERVAL)
            self.assertTrue(all(ua == os.environ[collect.SEC_UA_ENV] for _, ua in f.opener.calls))
            self.assertTrue(waits)                                        # 间隔在锁内按锁文件时间执行
            self.assertEqual(collect.RATE_GROUPS["sec.gov"], 0.2)
            self.assertLessEqual(1 / collect.RATE_GROUPS["sec.gov"], 10)
        finally:
            if old is None:
                os.environ.pop(collect.SEC_UA_ENV, None)
            else:
                os.environ[collect.SEC_UA_ENV] = old

    def test_no_email_hardcoded_in_code(self):
        import re as _re
        root = Path(__file__).resolve().parents[1] / "scripts"
        for p in root.rglob("*.py"):
            self.assertIsNone(_re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", p.read_text(encoding="utf-8")), p)


class R8Fixes(unittest.TestCase):
    """PR #3 审查 r8：只有 403 和厂商标记才持久停用；外部 DOCTYPE 放行；短语只在 HTML；标签边界；逐响应存档；SEC 跨进程锁。"""

    def tmpdir(self):
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    PUBMED = (b'<?xml version="1.0" encoding="UTF-8" ?>\n<!DOCTYPE eSearchResult PUBLIC "-//NLM//DTD esearch 20060628//EN" '
              b'"https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20060628/esearch.dtd">\n<eSearchResult><Count>2</Count><RetMax>2</RetMax>'
              b'<RetStart>0</RetStart><IdList>\n<Id>41000001</Id>\n<Id>41000002</Id>\n</IdList><TranslationSet/>'
              b'<QueryTranslation>"gene editing"[All Fields]</QueryTranslation></eSearchResult>\n')
    RSS091 = (b'<?xml version="1.0" encoding="ISO-8859-1"?>\n<!DOCTYPE rss PUBLIC "-//Netscape Communications//DTD RSS 0.91//EN" '
              b'"http://my.netscape.com/publish/formats/rss-0.91.dtd">\n<rss version="0.91"><channel><title>T</title>'
              b'<link>https://example.org/</link><description>d</description><language>en</language>'
              b'<item><title>x</title><link>https://example.org/1</link></item></channel></rss>')
    ARXIV = (b'<?xml version="1.0" encoding="UTF-8"?>\n<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0"><channel>'
             b'<title>cs.AI updates on arXiv.org</title><item><title>Are You a Robot? Detecting Autonomous Agents</title>'
             b'<link>https://arxiv.org/abs/2610.00001</link><description>Just a moment... verify you are human</description>'
             b'</item></channel></rss>')

    def _fetch(self, resp, url="https://a.org/p", extra=None, src="s"):
        p = self.tmpdir() / "st.json"
        routes = {url: resp}; routes.update(extra or {})
        f, _ = mk(routes, state=collect.SourceHealth(p))
        sunk = []
        r = f.get(url, sid=src, raw_sink=lambda b, st, ct: sunk.append((st, b)))
        return r, view(p), sunk, f

    def test_external_doctype_accepted_internal_subset_refused(self):
        cs = collect.content_suspect
        self.assertIsNone(cs("api", {"Content-Type": "text/xml; charset=UTF-8"}, self.PUBMED, "xml", ["eSearchResult"]))
        self.assertIsNone(cs("rss", {"Content-Type": "application/rss+xml"}, self.RSS091))
        self.assertEqual(CS.parse_ok(self.PUBMED), "xml")
        for bad in (b"<!DOCTYPE x [<!ENTITY a 'b'>]><rss>&a;</rss>", b"<!DOCTYPE rss [ ]><rss/>",
                    b"<?xml version='1.0'?><!ENTITY a 'b'><rss/>"):
            self.assertIn(cs("rss", {}, bad), ("xml_internal_subset_or_entity", "xml_unparseable"), bad)
        self.assertEqual(cs("rss", {}, b"<rss>&ext;</rss>"), "xml_unparseable")       # 未声明实体不加载

    def test_real_formats_pass_fetcher_without_disable(self):
        for body, ct in ((self.PUBMED, "text/xml; charset=UTF-8"), (self.RSS091, "application/rss+xml"),
                         (self.ARXIV, "application/rss+xml"),
                         (b'{"items": [{"title": "Robot check list for factory"}, {"title": "Just a moment..."}]}',
                          "application/json"),
                         (b'{"title": "Just a moment..."}', "text/plain")):
            r, d, sunk, _ = self._fetch(Resp(200, body, {"Content-Type": ct}))
            self.assertTrue(r.ok, body[:60])
            self.assertEqual(d["hosts"], {}, body[:60])
            self.assertIsNone(collect.content_suspect("rss" if b"<rss" in body else "api", {"Content-Type": ct}, body,
                                                      "xml" if b"eSearch" in body else None, ["eSearchResult"]), body[:60])

    def test_normal_html_mentioning_phrases_not_disabled(self):
        for b in (b"<html><body><h1>Why sites ask: are you a robot?</h1></body></html>",
                  b"<html><body><p>This app requires you to enable JavaScript to continue.</p></body></html>",
                  b"<html><head><title>Robot check list for factory</title></head><body><p>steps</p></body></html>",
                  b"<html><body><noscript>enable javascript and cookies</noscript><p>ok</p></body></html>",
                  b"<html><head><title>Docs</title></head><body><p>" + b"word " * 200 +
                  b"Please enable JavaScript and cookies to continue.</p></body></html>"):
            r, d, *_ = self._fetch(Resp(200, b, {"Content-Type": "text/html"}))
            self.assertTrue(r.ok, b[:70])
            self.assertEqual(d["hosts"], {})

    def test_phrase_only_html_suspect_round_fail_no_disable(self):
        r, d, *_ = self._fetch(Resp(200, b"<html><title>Just a moment...</title></html>", {"Content-Type": "text/html"}))
        self.assertEqual(r.error, "suspected_challenge")
        self.assertEqual(d["hosts"], {})
        r, d, *_ = self._fetch(Resp(302, b"<html><title>Just a moment...</title></html>",
                                    {"Content-Type": "text/html", "Location": "https://a.org/q"}),
                               extra={"https://a.org/q": Resp(200, b"ok")})
        self.assertEqual(r.error, "suspected_challenge")                                 # 不跟随
        self.assertEqual(d["hosts"], {})

    def test_vendor_marker_disables(self):
        r, d, *_ = self._fetch(Resp(200, b'<html><body><div class="cf-turnstile"></div></body></html>'))
        self.assertEqual(r.error, "challenge")
        self.assertIn("a.org", d["hosts"])
        r, d, *_ = self._fetch(Resp(200, b'{"note": "g-recaptcha in a JSON string"}', {"Content-Type": "application/json"}))
        self.assertTrue(r.ok)                                                             # JSON 只做格式校验

    def test_tag_boundary_and_plain_html_aux_only(self):
        P = "text/plain"
        for b in (b"<a.b@lists.example.org> wrote:\n> hi\n", b"<https://example.org/x>\nFrom: a", b"<<< begin >>>",
                  b"<3 robots", b"<-- arrow"):
            self.assertFalse(collect.plain_html(P, b), b)
        for b in (b"<p>quoted html in mail</p>", b"<html> tag discussion in plain text", b"<br/>\nmail", b"<br>\nmail"):
            self.assertTrue(collect.plain_html(P, b), b)
        for b in (b"<a.b@lists.example.org> wrote:\n> hi\n", b"<p>quoted html in mail</p>",
                  b"<html> tag discussion in plain text"):
            r, d, *_ = self._fetch(Resp(200, b, {"Content-Type": P}))
            self.assertTrue(r.ok, b)                                                      # 只有标签外形：不停用
            self.assertEqual(d["hosts"], {})
        r, d, *_ = self._fetch(Resp(200, b"<div>Please verify that you are human to continue</div>", {"Content-Type": P}))
        self.assertEqual(r.error, "suspected_challenge")                                  # r9：只记本轮可疑
        self.assertEqual(d["hosts"], {})

    def test_raw_sink_every_response_incl_robots_and_redirects(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/robots.txt": Resp(200, b"User-agent: *\nAllow: /\n"),
                   "https://a.org/p": Resp(302, b"moved", {"Location": "https://a.org/q"}),
                   "https://a.org/q": Resp(200, b'{"ok": 1}')},
                  state=collect.SourceHealth(p))
        sunk = []
        r = f.get("https://a.org/p", sid="s", raw_sink=lambda b, st, ct: sunk.append((st, b)))
        self.assertTrue(r.ok)
        self.assertEqual(sunk, [(200, b"User-agent: *\nAllow: /\n"), (302, b"moved"), (200, b'{"ok": 1}')])
        r = mk({"https://b.org/x": Resp(503, b"busy")})[0].get("https://b.org/x", raw_sink=lambda b, st, ct: sunk.append((st, b)))
        self.assertEqual((r.error, sunk[-1]), ("http_503", (503, b"busy")))     # 5xx 也先存档；不重发

    def test_sec_cross_process_lock_serialises(self):
        import os, threading
        old = os.environ.get(collect.SEC_UA_ENV)
        os.environ[collect.SEC_UA_ENV] = "markjin research (+https://example.org/contact)"
        try:
            lock = self.tmpdir()
            state = {"cur": 0, "max": 0, "times": []}
            mu = threading.Lock()

            class SlowOpener:
                def __init__(self): self.calls = []
                def open(self, req, timeout=None):
                    with mu:
                        state["cur"] += 1; state["max"] = max(state["max"], state["cur"]); state["times"].append(time.time())
                    time.sleep(0.05)
                    with mu:
                        state["cur"] -= 1
                    self.calls.append(req.full_url)
                    return Resp(200, b"" if req.full_url.endswith("robots.txt") else b"{}")

            def run(host):
                f = collect.Fetcher(opener=SlowOpener(), lock_dir=lock, resolver=lambda h: {"93.184.216.34"},
                                    sleep=time.sleep)          # 真实等待：间隔在锁内按锁文件的墙钟时间执行
                f.get(f"https://{host}/x")

            ts = [threading.Thread(target=run, args=(h,)) for h in ("data.sec.gov", "www.sec.gov", "efts.sec.gov")]
            [t.start() for t in ts]; [t.join() for t in ts]
            self.assertEqual(state["max"], 1)                                             # 同一时间只有一个请求
            gaps = [b - a for a, b in zip(state["times"], state["times"][1:])]
            self.assertTrue(all(g >= collect.RATE_GROUPS["sec.gov"] - 0.02 for g in gaps), gaps)
            self.assertEqual(len(state["times"]), 6)                                      # robots + 正文 × 3
            self.assertTrue((lock / "rate-site-sec.gov.lock").exists())
        finally:
            if old is None:
                os.environ.pop(collect.SEC_UA_ENV, None)
            else:
                os.environ[collect.SEC_UA_ENV] = old


class R9Fixes(unittest.TestCase):
    """PR #3 审查 r9 REJECTED 修复的针对性测试。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    BODIES = [(b"<html><head><title>Access Denied</title></head><body></body></html>", "text/html"),
              (b"<html><body>Just a moment...</body></html>", "text/html"),
              (b"plain forbidden", "text/plain"),
              (b'{"error": "forbidden"}', "application/json"),
              (b"", "text/html"),
              (b"<html><body>" + b"<p>long normal page</p>" * 300 + b"</body></html>", "text/html")]

    def test_content_403_401_disable_first_regardless_of_body(self):
        for st in (401, 403):
            for b, ct in self.BODIES:
                p = self.tmpdir() / "st.json"
                f, _ = mk({"https://a.org/p": Resp(st, b, {"Content-Type": ct})}, state=collect.SourceHealth(p))
                r = f.get("https://a.org/p", sid="s")
                self.assertEqual(r.error, f"http_{st}", (st, b[:30]))
                self.assertIn("a.org", view(p)["hosts"], (st, b[:30]))
                self.assertEqual([u for u, _ in f.opener.calls].count("https://a.org/p"), 1)   # 不重试

    def test_redirect_hop_403_401_disable(self):
        for st in (401, 403):
            p = self.tmpdir() / "st.json"
            f, _ = mk({"https://a.org/p": Resp(302, b"", {"Location": "https://a.org/q"}),
                       "https://a.org/q": Resp(st, b"<html><title>Just a moment...</title></html>")},
                      state=collect.SourceHealth(p))
            r = f.get("https://a.org/p", sid="s")
            self.assertEqual(r.error, f"http_{st}")
            self.assertIn("a.org", view(p)["hosts"])

    def test_robots_403_401_disable_first_regardless_of_body(self):
        for st in (401, 403):
            for b, ct in self.BODIES:
                p = self.tmpdir() / "st.json"
                f, _ = mk({"https://a.org/robots.txt": Resp(st, b, {"Content-Type": ct}), "https://a.org/p": Resp(200, b"ok")},
                          state=collect.SourceHealth(p))
                r = f.get("https://a.org/p", sid="s")
                self.assertEqual(r.error, f"robots_http_{st}", (st, b[:30]))
                self.assertIn("a.org", view(p)["hosts"])
                self.assertNotIn("https://a.org/p", [u for u, _ in f.opener.calls])

    def test_vendor_markers_only_real_components(self):
        real = [b"<script src='https://challenges.cloudflare.com/turnstile/v0/api.js' async></script>",
                b'<script src="https://js.hcaptcha.com/1/api.js"></script>',
                b'<script src="https://www.recaptcha.net/recaptcha/api.js"></script>',
                b'<form id="challenge-form" action="/x"></form>',
                b'<div class="foo cf-turnstile" data-sitekey="x"></div>', b'<div class="g-recaptcha"></div>']
        for b in real:
            self.assertEqual(collect.classify_page("text/html", b"<html><body>" + b + b"</body></html>"), "vendor", b)
        fake = [b"<p>Use the g-recaptcha class and cf-turnstile widget.</p>",
                b'<textarea><div class="g-recaptcha"></div></textarea>', b'<xmp><form id="challenge-form"></xmp>',
                b'<pre>&lt;div class="g-recaptcha"&gt;</pre>', b'<!-- <div class="cf-turnstile"></div> -->',
                b"<p>see https://challenges.cloudflare.com/turnstile/v0/api.js</p>",
                b'<script src="/static/recaptcha-helper.min.js"></script>']
        for b in fake:
            self.assertNotEqual(collect.classify_page("text/html", b"<html><body>" + b + b"</body></html>"), "vendor", b)

    def test_tutorial_and_plain_access_denied_not_disabled(self):
        art = (b"<html><body><article><h1>How to add reCAPTCHA</h1><pre>&lt;div class=\"g-recaptcha\"&gt;</pre>"
               b"<p>Use g-recaptcha class.</p>" + b"<p>text</p>" * 100 + b"</article></body></html>")
        for b, ct in ((art, "text/html"), (b"<p>Access denied</p>", "text/plain")):
            p = self.tmpdir() / "st.json"
            f, _ = mk({"https://a.org/p": Resp(200, b, {"Content-Type": ct})}, state=collect.SourceHealth(p))
            f.get("https://a.org/p", sid="s")
            self.assertEqual(view(p)["hosts"], {}, b[:40])

    def test_xml_expat_internal_subset_entity_utf16_quoted_gt(self):
        X = b"<?xml version='1.0'?>"
        for b in (X + b"<!DOCTYPE r [<!ATTLIST r a CDATA 'x'>]><r/>",
                  X + b"<!DOCTYPE r SYSTEM 'a>b' [<!ATTLIST r a CDATA 'x'>]><r/>",
                  X + b'<!DOCTYPE r PUBLIC "-//x>y//EN" "u>v" [<!ENTITY a "b">]><r>&a;</r>',
                  "<?xml version='1.0' encoding='UTF-16'?><!DOCTYPE rss [<!ENTITY a 'aaaa'>]><rss>&a;</rss>".encode("utf-16"),
                  "<?xml version='1.0' encoding='UTF-16'?><!DOCTYPE rss [<!ATTLIST rss a CDATA 'x'>]><rss/>".encode("utf-16-le")):
            with self.assertRaises(Exception, msg=b[:60]):
                collect.xml_root(b)
            self.assertTrue(collect.content_suspect("rss", {"Content-Type": "application/xml"}, b), b[:60])
        ok = [(X + b"<!DOCTYPE eSearchResult PUBLIC '-//NLM//DTD esearch 20060628//EN' 'https://e.example.org/a>b.dtd'><eSearchResult/>",
               "eSearchResult"),
              ("<?xml version='1.0' encoding='UTF-16'?><rss version='2.0'><channel/></rss>".encode("utf-16"), "rss"),
              (X + b"<feed xmlns='http://www.w3.org/2005/Atom'/>", "{http://www.w3.org/2005/Atom}feed")]
        for b, root in ok:
            self.assertEqual(collect.xml_root(b), root)
        with self.assertRaises(Exception):          # 外部 DTD 不加载 → 未声明实体解析失败
            collect.xml_root(X + b"<!DOCTYPE rss SYSTEM 'file:///etc/passwd'><rss>&x;</rss>")

    def test_sec_lock_records_per_host_and_enforces_host_interval_across_fetchers(self):
        import os
        from unittest import mock
        old = os.environ.get(collect.SEC_UA_ENV)
        os.environ[collect.SEC_UA_ENV] = "markjin research (+https://example.org/contact)"
        try:
            lock = self.tmpdir()

            class O:
                def __init__(self): self.calls = []
                def open(self, req, timeout=None):
                    self.calls.append(req.full_url)
                    return Resp(200, b"" if req.full_url.endswith("robots.txt") else b"{}")
            waits = []
            mk_f = lambda: collect.Fetcher(opener=O(), lock_dir=lock, resolver=lambda h: {"93.184.216.34"},
                                           sleep=waits.append)
            mk_f().get("https://data.sec.gov/x")            # 进程 A
            rec = json.loads((lock / "rate-site-sec.gov.lock").read_text())
            self.assertIn("data.sec.gov", rec["hosts"])
            self.assertIn("site", rec)
            waits.clear()
            mk_f().get("https://data.sec.gov/y")            # 进程 B：内存里没有 _last，靠锁文件里的单主机时间戳
            self.assertTrue(waits and max(waits) >= collect.HOST_INTERVAL - 0.5, waits)
        finally:
            if old is None:
                os.environ.pop(collect.SEC_UA_ENV, None)
            else:
                os.environ[collect.SEC_UA_ENV] = old


def _hs_disable_proc(path, host):          # 子进程：独立 SourceHealth 实例各记一次可疑（URL 冷却 + 主机本轮停止）
    hs = collect.SourceHealth(path)
    time.sleep(0.2)                         # 两个进程都先读到空状态，再各自写回
    hs.stop([f"https://{host}/x"], ROUND, None, "http_403")


class R10Fixes(unittest.TestCase):
    """PR #3 审查 r10 REJECTED 修复的针对性测试。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    CF = (b"<!DOCTYPE html><html lang='en-US'><head><title>Just a moment...</title><meta http-equiv='refresh' content='390'>"
          b"</head><body><div class='main-wrapper' role='main'><div class='main-content'><h1 class='zone-name-title h1'>a.org</h1>"
          b"<h2 class='h2'>Checking if the site connection is secure</h2><noscript><div class='h2'>Enable JavaScript and cookies to "
          b"continue</div></noscript></div></div><script>(function(){window._cf_chl_opt={cvId:'3',cZone:'a.org',cType:'managed',"
          b"cRay:'8',cH:'x'};var a=document.createElement('script');a.src='/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1"
          b"?ray=8';document.getElementsByTagName('head')[0].appendChild(a);}());</script></body></html>")
    INCAP = (b'<html style="height:100%"><head><META NAME="ROBOTS" CONTENT="NOINDEX, NOFOLLOW"><meta name="format-detection" '
             b'content="telephone=no"><meta name="viewport" content="initial-scale=1.0"><meta http-equiv="X-UA-Compatible" '
             b'content="IE=edge,chrome=1"><script type="text/javascript" src="/_Incapsula_Resource?SWJIYLWA=719d34d31c8e3a6e6fffd425f7e032f3">'
             b'</script></head><body style="margin:0px;height:100%"><iframe id="main-iframe" src="/_Incapsula_Resource?CWUDNSAI=9&xinfo=1" '
             b'frameborder=0 width="100%" height="100%">Request unsuccessful. Incapsula incident ID: 0-0</iframe></body></html>')
    PX = (b'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Access to this page has been denied</title>'
          b'<script>window._pxAppId="PXabc";window._pxJsClientSrc="/abc/init.js";window._pxHostUrl="/abc/xhr";</script></head>'
          b'<body><div class="px-container"><div class="page-title-wrapper"><h1>Please verify you are a human</h1></div>'
          b'<div class="content-wrapper"><p>Press &amp; Hold to confirm you are a human (and not a bot).</p><div id="px-captcha">'
          b'</div></div></div><script src="/abc/captcha/captcha.js?a=c&m=0"></script></body></html>')

    def test_real_vendor_pages_disable_content_and_robots_at_200_429_503(self):
        for lab, body in (("cloudflare", self.CF), ("incapsula", self.INCAP), ("perimeterx", self.PX)):
            self.assertEqual(collect.classify_page("text/html", body), "vendor", lab)
            for st in (200, 429, 503):
                for where in ("content", "robots", "hop"):
                    p = self.tmpdir() / "st.json"
                    routes = {"https://a.org/p": Resp(200, b"ok")}
                    if where == "robots":
                        routes["https://a.org/robots.txt"] = Resp(st, body)
                    elif where == "content":
                        routes["https://a.org/p"] = Resp(st, body)
                    else:
                        routes["https://a.org/p"] = Resp(302, b"", {"Location": "https://a.org/q"})
                        routes["https://a.org/q"] = Resp(st, body)
                    f, _ = mk(routes, state=collect.SourceHealth(p))
                    r = f.get("https://a.org/p", sid="s")
                    self.assertFalse(r.ok)
                    exp = "http_429" if st == 429 else "challenge"                    # 429 先按状态码
                    self.assertEqual(r.error, ("robots_" + exp) if where == "robots" else exp, (lab, st, where))
                    self.assertIn("a.org", view(p)["hosts"], (lab, st, where))
                    calls = [u for u, _ in f.opener.calls]
                    self.assertEqual(len(calls), len(set(calls)), (lab, st, where))     # 不重试

    def test_cf_mitigated_header_is_vendor(self):
        for st in (200, 403, 503):
            self.assertEqual(collect.classify_page("text/plain", b"", {"cf-mitigated": "challenge"}), "vendor")
        for where in ("content", "robots"):
            p = self.tmpdir() / "st.json"
            resp = Resp(200, b"<html><body>wait</body></html>", {"Content-Type": "text/html", "CF-Mitigated": "challenge"})
            routes = {"https://a.org/p": Resp(200, b"ok")}
            routes["https://a.org/robots.txt" if where == "robots" else "https://a.org/p"] = resp
            f, _ = mk(routes, state=collect.SourceHealth(p))
            f.get("https://a.org/p", sid="s")
            self.assertIn("a.org", view(p)["hosts"], where)
        self.assertNotEqual(collect.classify_page("text/html", b"<p>x</p>", {"cf-mitigated": "none"}), "vendor")

    def test_parser_only_exact_attributes_and_skips_script_text(self):
        fake = [b'<div data-class="cf-turnstile">x</div>', b'<img data-src="https://www.google.com/recaptcha/api.js">',
                b"<script>var t='<div class=\"g-recaptcha\"></div>';</script>",
                b"<script>var t='<div id=\"px-captcha\"></div>';</script>",
                b'<div data-id="px-captcha"></div>', b'<div class="not-cf-turnstile-x"></div>',
                b'<script src="https://evil.example.org/recaptcha/api.js"></script>',
                b'<script src="https://www.google.com/search?q=/recaptcha/api.js"></script>',
                b'<a href="/cdn-cgi/challenge-platform/x">doc</a>', b"<p>window._cf_chl_opt = {}</p>",
                b'<textarea><div class="g-recaptcha"></div></textarea>', b'<title><div id="px-captcha"></div></title>',
                b"<!-- <div class='cf-turnstile'></div> -->", b'<p>/_Incapsula_Resource?x in a support article</p>']
        for b in fake:
            body = b"<html><body>" + b + b"<p>a</p>" * 100 + b"</body></html>"
            self.assertNotEqual(collect.classify_page("text/html", body), "vendor", b)
        real = [b'<div class="x cf-turnstile y"></div>', b'<div class="g-recaptcha"></div>', b'<div id="px-captcha"></div>',
                b'<form id="challenge-form"></form>', b'<script src="//challenges.cloudflare.com/turnstile/v0/api.js"></script>',
                b'<script src="https://www.recaptcha.net/recaptcha/api.js"></script>',
                b'<script src="https://js.hcaptcha.com/1/api.js"></script>',
                b'<script src="/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"></script>',
                b'<script src="/_Incapsula_Resource?SWJIYLWA=1"></script>',          # r11：只认 script src
                b"<script>window._cf_chl_opt={cType:'managed'}</script>",
                b"<script>var a=document.createElement('script');a.src = '/cdn-cgi/challenge-platform/h/g/orchestrate/x';</script>"]
        for b in real:
            self.assertEqual(collect.classify_page("text/html", b"<html><body>" + b + b"</body></html>"), "vendor", b)

    def test_two_processes_fail_different_urls_both_kept(self):
        import multiprocessing as mp
        d = self.tmpdir() / "state"
        p = d / "source-health.json"
        ctx = mp.get_context("fork")
        ps = [ctx.Process(target=_hs_disable_proc, args=(str(p), h)) for h in ("a.org", "b.org")]
        [x.start() for x in ps]; [x.join() for x in ps]
        self.assertEqual([x.exitcode for x in ps], [0, 0])
        self.assertEqual(sorted(view(p)["hosts"]), ["a.org", "b.org"])
        self.assertTrue((d / "locks" / "source-health.json.lock").exists())
        self.assertEqual([x.name for x in d.iterdir() if x.suffix == ".tmp"], [])          # 临时文件不残留

    def test_disabled_rereads_file_before_each_request(self):
        p = self.tmpdir() / "st.json"
        hs = collect.SourceHealth(p)
        f, _ = mk({"https://a.org/p": Resp(200, b"ok"), "https://a.org/q": Resp(200, b"ok")}, state=hs)
        self.assertTrue(f.get("https://a.org/p").ok)
        collect.SourceHealth(p).set_status("s", "disabled", "confirmed by reviewer")            # 另一个“进程”人工停用该源
        r = f.get("https://a.org/q", sid="s")
        self.assertEqual(r.error, "source_blocked")
        self.assertTrue(f.get("https://a.org/q", sid="other").ok)                              # 只影响该源

    def test_sec_without_lock_dir_not_configured_no_request(self):
        import os
        old = os.environ.get(collect.SEC_UA_ENV)
        os.environ[collect.SEC_UA_ENV] = "markjin research (+https://example.org/contact)"
        try:
            f, _ = mk({"https://data.sec.gov/robots.txt": Resp(200, b""), "https://data.sec.gov/a": Resp(200, b"{}")})
            r = f.get("https://data.sec.gov/a")
            self.assertEqual(r.error, "not_configured")
            self.assertEqual(f.opener.calls, [])
            self.assertEqual((f.contacted, f.suspicious), (set(), {}))                          # 不算可疑
        finally:
            if old is None:
                os.environ.pop(collect.SEC_UA_ENV, None)
            else:
                os.environ[collect.SEC_UA_ENV] = old


class R11Fixes(unittest.TestCase):
    """PR #3 审查 r11 REJECTED 修复的针对性测试。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    CFS = (b"<script>(function(){window._cf_chl_opt={cType:'managed'};var a=document.createElement('script');"
           b"a.src='/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1';}());</script>")

    def cls(self, b):
        return collect.classify_page("text/html", b"<html><body>" + b + b"</body></html>", {})

    def test_pre_code_checked_closed_unclosed_selfclosed(self):
        for wrap in (b"pre", b"code"):
            for comp in (self.CFS, b"<div class='cf-turnstile'></div>", b"<script src='/_Incapsula_Resource?SWJ=1'></script>"):
                for b in (b"<%s>x%s</%s>" % (wrap, comp, wrap),          # 闭合
                          b"<%s>x%s" % (wrap, comp),                     # 没闭合
                          b"<%s/>%s" % (wrap, comp)):                    # <pre/>
                    self.assertEqual(self.cls(b), "vendor", b)

    def test_only_textarea_xmp_plaintext_title_exempt(self):
        self.assertEqual(collect._LITERAL_TAGS, frozenset({"textarea", "xmp", "plaintext", "title"}))
        for tag in (b"textarea", b"xmp", b"title"):
            self.assertIsNone(self.cls(b"<%s>x<div class='cf-turnstile'></div></%s>" % (tag, tag)), tag)
        self.assertIsNone(self.cls(b"<plaintext>x<div class='g-recaptcha'></div>"))

    def test_tightened_markers_no_false_positive(self):
        fake = [b'<img src="/cdn-cgi/challenge-platform/x.png">', b'<img src="/img/_Incapsula_Resource_diagram.png">',
                b'<iframe src="/_Incapsula_Resource?CWUDNSAI=1"></iframe>',
                b"<script src='https://evil.example.org/cdn-cgi/challenge-platform/x'></script>",
                b'<h2 id="px-captcha">PerimeterX captcha explained</h2>', b'<a id="px-captcha">x</a>',
                b"<pre>window._cf_chl_opt = {}</pre>", b"<code>window._cf_chl_opt = {}</code>",
                b"<script>console.log('see window._cf_chl_opt = {} docs');</script>",
                b'<script>var s = "window._cf_chl_opt = {}";</script>',
                b"<script>// window._cf_chl_opt = {}\n/* window._cf_chl_opt={} */ var x = 1;</script>",
                b"<script>var t = 'a.src=\"/cdn-cgi/challenge-platform/x\"';</script>",
                b"<script>if (window._cf_chl_opt == null) {}</script>"]
        for b in fake:
            self.assertIsNone(self.cls(b + b"<p>a</p>" * 100), b)
        # px-captcha：div 且整页可见文本很短才算
        self.assertEqual(self.cls(b"<div id='px-captcha'></div><p>Press &amp; Hold to confirm you are a human</p>"), "vendor")
        self.assertIsNone(self.cls(b"<div id='px-captcha'></div>" + b"<p>long article text here</p>" * 100))
        for b in (b"<script>window._cf_chl_opt={cType:'managed'}</script>", b"<script>;window._cf_chl_opt = {a: 1};</script>",
                  b"<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script>",
                  b"<script>var a=document.createElement('script');a.src = \"/cdn-cgi/challenge-platform/h/g/orchestrate/x\";</script>"):
            self.assertEqual(self.cls(b + b"<p>a</p>" * 100), "vendor", b)

    def test_stale_process_does_not_rewrite_manually_enabled_source(self):
        p = self.tmpdir() / "state" / "source-health.json"
        old = collect.SourceHealth(p)                      # 已在跑的旧进程
        old.set_status("s1", "disabled", "confirmed")
        collect.SourceHealth(p).set_status("s1", "ok", "manual enable")   # 人工恢复，同一把锁
        self.assertIsNone(old.blocked("s1"))            # blocked() 每次以磁盘为准
        old.record_round(ROUND, {"s2": ["http_403"]})   # 旧进程再写别的源：只合并这一条
        d = collect.SourceHealth(p).data["sources"]
        self.assertEqual(d["s1"]["status"], "ok")
        self.assertEqual(d["s2"]["rounds"][ROUND], {"suspicious": True, "reasons": ["http_403"]})

    def test_stale_cache_without_refresh_still_not_written_back(self):
        p = self.tmpdir() / "state" / "source-health.json"
        old = collect.SourceHealth(p)
        old.set_status("s1", "disabled", "confirmed")
        collect.SourceHealth(p).set_status("s1", "ok", "manual enable")
        old.stop(["https://b.org/x"], ROUND, "s2", "http_403")   # 未调用 refresh() 也不写回 s1 的旧状态
        self.assertEqual(collect.SourceHealth(p).data["sources"]["s1"]["status"], "ok")
        self.assertEqual(sorted(view(p)["hosts"]), ["b.org"])

    def test_sec_gate_in_raw_covers_direct_robots(self):
        import os
        old = os.environ.get(collect.SEC_UA_ENV)
        try:
            for ua, lock in ((None, True), ("markjin research (+https://example.org/contact)", False)):
                if ua is None:
                    os.environ.pop(collect.SEC_UA_ENV, None)
                else:
                    os.environ[collect.SEC_UA_ENV] = ua
                f, _ = mk({"https://www.sec.gov/robots.txt": Resp(200, b"")},
                          lock_dir=(self.tmpdir() if lock else None))
                rp = f.robots("https://www.sec.gov/x")
                self.assertEqual(f.opener.calls, [], (ua, lock))           # 直接调用 robots() 也不发请求
                self.assertFalse(rp.can_fetch(collect.UA_TOKEN, "https://www.sec.gov/x"))
                self.assertEqual((f.contacted, f.suspicious), (set(), {}))  # 不算可疑
                self.assertEqual(f._raw("https://www.sec.gov/x", "*/*")[3], "not_configured")
        finally:
            if old is None:
                os.environ.pop(collect.SEC_UA_ENV, None)
            else:
                os.environ[collect.SEC_UA_ENV] = old


class R12Fixes(unittest.TestCase):
    """PR #3 审查 r12 REJECTED 修复的针对性测试。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    INCAP_IFRAME = (b"<html style='height:100%'><head><META NAME='ROBOTS' CONTENT='NOINDEX, NOFOLLOW'><meta name='format-detection' "
                    b"content='telephone=no'></head><body style='margin:0px;height:100%'><iframe id='main-iframe' "
                    b"src='/_Incapsula_Resource?CWUDNSAI=9&xinfo=6-1&incident_id=165-68&edet=12&cinfo=04000000' frameborder=0 "
                    b"width='100%' height='100%' marginheight='0px' marginwidth='0px'>Request unsuccessful. Incapsula incident ID: "
                    b"165001010055460724-68720833956480598</iframe></body></html>")
    PX_TEMPLATE = (Path(__file__).parent / "fixtures" / "px_blocking_template.html").read_bytes()   # PerimeterX 官方拦截模板

    def run_get(self, st, body, url="https://a.org/p"):
        p = self.tmpdir() / "st.json"
        f, _ = mk({url: Resp(st, body)}, state=collect.SourceHealth(p))
        return f.get(url, sid="s"), view(p)

    def cls(self, b, url="https://a.org/p"):
        return collect.classify_page("text/html", b"<html><body>" + b + b"</body></html>", {}, url)

    def test_incapsula_iframe_block_page_200_and_403(self):
        self.assertEqual(collect.classify_page("text/html", self.INCAP_IFRAME, {}, "https://a.org/p"), "vendor")
        r, d = self.run_get(200, self.INCAP_IFRAME)
        self.assertEqual(r.error, "challenge"); self.assertIn("a.org", d["hosts"])
        r, d = self.run_get(403, self.INCAP_IFRAME)
        self.assertEqual(r.error, "http_403"); self.assertIn("a.org", d["hosts"])
        # 组合证据：只有 iframe、没有 incident ID → 不算；别的主机的 iframe → 不算
        self.assertNotEqual(self.cls(b"<iframe src='/_Incapsula_Resource?CWUDNSAI=9'></iframe>"), "vendor")
        self.assertNotEqual(collect.classify_page("text/html", self.INCAP_IFRAME.replace(b"src='/_", b"src='https://b.org/_"),
                                                  {}, "https://a.org/p"), "vendor")

    def test_same_origin_resolution_via_response_url(self):
        CF = b"/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1"
        for src in (CF, b"https://a.org" + CF, b"//a.org" + CF):
            self.assertEqual(self.cls(b"<script src='" + src + b"'></script>"), "vendor", src)
            self.assertEqual(self.cls(b"<script>var a=document.createElement('script');a.src='" + src + b"';</script>"), "vendor", src)
        for src in (b"/_Incapsula_Resource?SWJIYLWA=7", b"https://a.org/_Incapsula_Resource?SWJIYLWA=7",
                    b"//a.org/_Incapsula_Resource?SWJIYLWA=7"):
            self.assertEqual(self.cls(b"<script src='" + src + b"'></script>"), "vendor", src)
        for src in (b"https://b.org" + CF, b"//b.org" + CF, b"http://a.org" + CF, b"https://a.org:8443" + CF,
                    b"https://b.org/_Incapsula_Resource?x=1", b"//evil.example.org/_Incapsula_Resource?x=1"):
            self.assertIsNone(self.cls(b"<script src='" + src + b"'></script>"), src)          # 其他主机/协议/端口不认
        r, d = self.run_get(200, b"<html><head><script src='//a.org" + CF + b"'></script></head></html>")
        self.assertEqual(r.error, "challenge"); self.assertIn("a.org", d["hosts"])

    def test_perimeterx_official_template_and_variants(self):
        self.assertEqual(collect.classify_page("text/html", self.PX_TEMPLATE, {}, "https://a.org/p"), "vendor")
        for st in (200, 403):
            r, d = self.run_get(st, self.PX_TEMPLATE)
            self.assertIn("a.org", d["hosts"], st)
        filler = b"<p>a</p>" * 300
        self.assertIsNone(self.cls(b"<script>window._pxAppId = 'PXabc';</script>" + filler))   # r13：正常页面 Sensor，不算
        self.assertEqual(self.cls(b"<script src='https://captcha.px-cdn.net/PXabc/captcha.js'></script>" + filler), "vendor")
        self.assertEqual(self.cls(b"<script>var s=document.createElement('script');s.src='//captcha.px-cloud.net/PXabc/captcha.js';"
                                  b"</script>" + filler), "vendor")
        meta = (b"<html><head><meta name='description' content='px-captcha'><title>Access to this page has been denied</title>"
                b"</head><body>" + filler + b"</body></html>")
        self.assertEqual(collect.classify_page("text/html", meta, {}, "https://a.org/p"), "vendor")
        # 反例：文档里展示的代码、单独的标题或 meta、字符串里的赋值
        for b in (b"<pre>window._pxAppId = &#x27;PXabc&#x27;;</pre>", b"<script>var doc = \"window._pxAppId = 'x'\";</script>",
                  b"<a href='https://captcha.px-cloud.net/x/captcha.js'>link</a>", b"<script>if (window._pxAppId == null) {}</script>"):
            self.assertIsNone(self.cls(b + filler), b)
        self.assertNotEqual(collect.classify_page("text/html", meta.replace(b"content='px-captcha'", b"content='news'"), {},
                                                  "https://a.org/p"), "vendor")
        self.assertNotEqual(collect.classify_page("text/html", meta.replace(b"Access to this page has been denied", b"PX docs"), {},
                                                  "https://a.org/p"), "vendor")

    def test_cf_only_orchestrate_path_not_jsd(self):
        filler = b"<p>news</p>" * 50
        for src in (b"/cdn-cgi/challenge-platform/scripts/jsd/main.js", b"/cdn-cgi/challenge-platform/scripts/jsd/api.js",
                    b"/cdn-cgi/challenge-platform/h/gg/orchestrate/x", b"/cdn-cgi/challenge-platform/x.js"):
            self.assertIsNone(self.cls(b"<script src='" + src + b"'></script>" + filler), src)
            self.assertIsNone(self.cls(b"<script>var a=document.createElement('script');a.src='" + src + b"';</script>" + filler), src)
        jsd = (b"<article>" + filler + b"</article><script>(function(){var d=b.createElement('script');d.innerHTML=\"window.__CF$cv$params="
               b"{r:'8'};var a=document.createElement('script');a.src='/cdn-cgi/challenge-platform/scripts/jsd/main.js';\";})();</script>")
        r, d = self.run_get(200, b"<html><body>" + jsd + b"</body></html>")
        self.assertTrue(r.ok); self.assertEqual(d["hosts"], {})                              # Cloudflare 注入正常页面的 JSD
        self.assertEqual(self.cls(b"<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'></script>"), "vendor")

    def test_unclosed_script_never_vendor(self):
        # r13：没闭合的 script 永不算高置信；混入 HTML 标签（<pre> 等）时不凭内部赋值判定
        one = b"<html><body><script>var x=1;\n<pre>\nwindow._cf_chl_opt = {}\n</pre>"
        self.assertIsNone(collect.classify_page("text/html", one, {}, "https://a.org/p"))
        r, d = self.run_get(200, one)
        self.assertTrue(r.ok)
        two = (b"<html><body><script>window._cf_chl_opt={cType:'managed'};var a=document.createElement('script');"
               b"a.src='/cdn-cgi/challenge-platform/h/g/orchestrate/chl_page/v1';")
        self.assertEqual(collect.classify_page("text/html", two, {}, "https://a.org/p"), "phrase")
        r, d = self.run_get(200, two)
        self.assertEqual(r.error, "suspected_challenge"); self.assertEqual(d["hosts"], {})
        closed = b"<html><body><script>window._cf_chl_opt={cType:'managed'};</script></body></html>"
        self.assertEqual(collect.classify_page("text/html", closed, {}, "https://a.org/p"), "vendor")

    VALID = {"version": 2, "sources": {"s": {"status": "ok", "rounds": {}}},
             "urls": {"2026-10-12/r1": {"a" * 64: {"reason": "http_403", "sid": "s", "host": "a.org", "at": 100.0,
                                                   "until": 100.0 + 86400}}},
             "host_stops": {"2026-10-12/r1": {"a.org": {"reason": "http_403", "sid": "s", "at": 100.0}}},
             "hosts": {}, "legacy_imports": {}}

    def bad_states(self):
        import copy
        V = self.VALID
        out = ["{bad", "", "[]", "{}", '{"hosts": {}, "sources": {}}', '{"version": 2, "sources": {}, "urls": {}}']

        def m(fn):
            d = copy.deepcopy(V); fn(d); out.append(json.dumps(d))
        m(lambda d: d.update(version=2.0))                                         # r14 ⑨：必须是整数 2
        m(lambda d: d.update(version=True))
        m(lambda d: d.update(version=3))
        m(lambda d: d.update(extra={}))                                            # 未知顶层键
        for k in ("sources", "urls", "host_stops", "hosts", "legacy_imports", "version"):
            m(lambda d, k=k: d.pop(k))                                             # 缺任一顶层键
        m(lambda d: d["sources"].update(s={}))
        m(lambda d: d["sources"].update(s={"status": "off", "rounds": {}}))
        m(lambda d: d["sources"].update(s={"status": "disabled", "rounds": {}}))   # 非 ok 缺 status_reason
        m(lambda d: d["sources"].update(s={"status": "pending-disable", "rounds": {}, "status_reason": "x"}))  # 缺 pending_round
        m(lambda d: d["sources"]["s"].update(extra=1))
        m(lambda d: d["sources"]["s"]["rounds"].update({"bad": {"suspicious": True, "reasons": []}}))
        m(lambda d: d["sources"]["s"]["rounds"].update({"2026-10-12/r1": {"suspicious": 1, "reasons": []}}))
        m(lambda d: d["urls"]["2026-10-12/r1"]["a" * 64].pop("sid"))              # r14 ⑨：sid 必填
        m(lambda d: d["urls"]["2026-10-12/r1"]["a" * 64].update(extra=1))
        m(lambda d: d["urls"]["2026-10-12/r1"]["a" * 64].update(until=200.0))     # 冷却不足 24 小时
        m(lambda d: d["urls"]["2026-10-12/r1"]["a" * 64].update(at=True))
        m(lambda d: d["urls"].update({"bad": {}}))
        m(lambda d: d["urls"]["2026-10-12/r1"].update({"x": {}}))
        m(lambda d: d["host_stops"]["2026-10-12/r1"]["a.org"].pop("sid"))
        m(lambda d: d["hosts"].update({"a.org": {"status": "ok", "reason": "r", "category": "other", "unrecoverable": False}}))
        m(lambda d: d["hosts"].update({"a.org": {"status": "disabled", "reason": "r", "category": "bot_check"}}))
        m(lambda d: d["legacy_imports"].update(x="t"))
        return out

    def test_state_file_strict_schema_refuses_requests(self):
        p0 = self.tmpdir() / "ok" / "source-health.json"; p0.parent.mkdir()
        p0.write_text(json.dumps(self.VALID))
        self.assertIsNone(collect.SourceHealth(p0).error)                         # 合法样例本身可读
        for txt in self.bad_states():
            p = self.tmpdir() / "state" / "source-health.json"; p.parent.mkdir()
            p.write_text(txt)
            hs = collect.SourceHealth(p)
            self.assertTrue(hs.error, txt)
            self.assertTrue(hs.blocked("t"), txt)                                            # 任何源都拒绝
            self.assertTrue(hs.blocked(None), txt)
            f, _ = mk({"https://b.org/robots.txt": Resp(200, b""), "https://b.org/x": Resp(200, b"ok")}, state=hs)
            r = f.get("https://b.org/x", sid="t")
            self.assertEqual(r.error, "source_blocked", txt)
            self.assertEqual(f.opener.calls, [], txt)                                         # 不发请求
            self.assertFalse(f.robots("https://b.org/x").can_fetch(collect.UA_TOKEN, "https://b.org/x"))
            with self.assertRaises(collect.StateError):
                hs.record_round(ROUND, {"t": []})                                             # 不改写损坏的文件
            with self.assertRaises(collect.StateError):
                hs.stop(["https://b.org/x"], ROUND, "t", "http_403")
            with self.assertRaises(collect.StateError):
                hs.report()                                                                   # r14 ⑨：report 读失败报错
            self.assertEqual(p.read_text(), txt)
        p = self.tmpdir() / "fresh" / "source-health.json"                                    # 文件不存在 = 首次运行
        self.assertIsNone(collect.SourceHealth(p).blocked("s"))
        collect.SourceHealth(p).record_round(ROUND, {"s": []})
        self.assertEqual(sorted(json.loads(p.read_text())),
                         ["host_stops", "hosts", "legacy_imports", "sources", "urls", "version"])

    def test_robots_checks_source_status_before_cache(self):
        p = self.tmpdir() / "state" / "h.json"
        hs = collect.SourceHealth(p)
        f, _ = mk({"https://a.org/robots.txt": Resp(200, b"User-agent: *\nAllow: /\n")}, state=hs)
        self.assertTrue(f.robots("https://a.org/x", sid="s").can_fetch(collect.UA_TOKEN, "https://a.org/x"))    # 已缓存
        collect.SourceHealth(p).set_status("s", "disabled", "confirmed")
        n = len(f.opener.calls)
        self.assertFalse(f.robots("https://a.org/x", sid="s").can_fetch(collect.UA_TOKEN, "https://a.org/x"))
        self.assertEqual(len(f.opener.calls), n)
        self.assertTrue(f.robots("https://a.org/x", sid="t").can_fetch(collect.UA_TOKEN, "https://a.org/x"))     # 别的源照常



def _url_race_proc(state, lock, log, go):      # 子进程：同一 URL 并发请求（r14 ④）
    import fcntl

    class O:
        def open(self, req, timeout=None):
            if req.full_url.endswith("robots.txt"):
                return Resp(404)
            with open(log, "a") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX); fh.write(req.full_url + "\n")
            time.sleep(0.3)
            return Resp(403)
    while not os.path.exists(go):
        time.sleep(0.01)
    f = collect.Fetcher(collect.SourceHealth(state), opener=O(), sleep=lambda w: None, resolver=PUBLIC_DNS,
                        lock_dir=lock, round_id=ROUND)
    f.robots("https://a.org/x", sid="s")
    f.get("https://a.org/x", sid="s")


class BlockRule1522(unittest.TestCase):
    """现行封锁规则（王总 10-18 13:50 决定切回正常模式、恢复 #3/#6（14:15 改为立即生效）；封锁细则由 Grok Bot 定，
    10-18 13:51 初版，15:22 按审查意见收紧为现行版，底线是王总 10-11 确认的『遇到拦截即停』），并覆盖审查 r14 ①–⑨。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    CF = b"<html><head><script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script></head></html>"

    # ---- 规则 1：单次可疑 → 该主机本轮全部停止；429 不重试
    def test_each_suspicious_kind_stops_host_this_round(self):
        for resp, err in ((Resp(401), "http_401"), (Resp(403), "http_403"), (Resp(429), "http_429"),
                          (Resp(200, self.CF), "challenge"),
                          (Resp(200, b"<html><title>Just a moment...</title></html>"), "suspected_challenge"),
                          (Resp(302, headers={"Location": "https://a.org/login?next=/x"}), "login_wall"),
                          (Resp(302, headers={"Location": "https://accounts.example.com/signin"}), "login_wall"),
                          (Resp(503, b"<html>wait</html>", {"cf-mitigated": "challenge"}), "challenge")):
            p = self.tmpdir() / "st.json"
            f, _ = mk({"https://a.org/x": resp, "https://a.org/y": Resp(200, b"ok"), "https://b.org/z": Resp(200, b"ok")},
                      state=collect.SourceHealth(p))
            r = f.get("https://a.org/x", sid="s")
            self.assertEqual(r.error, err)
            self.assertTrue(collect.is_suspicious(r.error), err)
            self.assertEqual(f.get("https://a.org/y", sid="s2").error, "host_stopped_this_round", err)   # 同主机别的源也停
            self.assertTrue(f.get("https://b.org/z", sid="s").ok, err)                               # 别的主机照常
            calls = [u for u, _ in f.opener.calls]
            self.assertEqual(calls.count("https://a.org/x"), 1, err)                                 # 不重试
            self.assertNotIn("https://a.org/y", calls, err)
            self.assertFalse([u for u in calls if "login" in u or "signin" in u], err)               # 不跟登录跳转
            self.assertEqual(collect.SourceHealth(p).data["sources"], {}, err)                       # 轮末才记源

    def test_robots_429_and_403_stop_host(self):
        for st in (403, 429):
            f, _ = mk({"https://a.org/robots.txt": Resp(st), "https://a.org/x": Resp(200, b"ok")})
            self.assertEqual(f.get("https://a.org/x", sid="s").error, f"robots_http_{st}")
            self.assertEqual(f.get("https://a.org/y", sid="t").error, "host_stopped_this_round")
            self.assertEqual([u for u, _ in f.opener.calls], ["https://a.org/robots.txt"])

    def test_no_bypass_on_challenge(self):
        f, _ = mk({"https://a.org/x": [Resp(403, self.CF), Resp(200, b"ok")]})
        self.assertEqual(f.get("https://a.org/x", sid="s").error, "http_403")
        self.assertEqual(f.get("https://a.org/x", sid="s").error, "host_stopped_this_round")
        reqs = [(u, ua) for u, ua in f.opener.calls if u.endswith("/x")]
        self.assertEqual(len(reqs), 1)                                          # 不重试、不换 UA 再试
        self.assertIn("markjin-collector", reqs[0][1])

    def test_host_stop_cross_process_and_next_round(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/x": Resp(403)}, state=collect.SourceHealth(p))
        f.get("https://a.org/x", sid="s")
        f2, _ = mk({"https://a.org/y": Resp(200, b"ok")}, state=collect.SourceHealth(p))     # 另一进程、同一轮
        self.assertEqual(f2.get("https://a.org/y", sid="t").error, "host_stopped_this_round")
        self.assertEqual(f2.opener.calls, [])
        f3, _ = mk({"https://a.org/y": Resp(200, b"ok")}, state=collect.SourceHealth(p), round_id="2026-10-12/r2")
        self.assertTrue(f3.get("https://a.org/y", sid="t").ok)                             # 下一轮主机恢复

    # ---- 规则 2：被拒 URL 冷却 ≥24 小时；按轮次分别保存（r14 ⑤）；起点持久（⑥）；规范化（⑧）
    def test_rejected_url_cooldown_24h(self):
        t = [1_000_000.0]
        p = self.tmpdir() / "st.json"
        hs = lambda: collect.SourceHealth(p, clock=lambda: t[0])
        f, _ = mk({"https://a.org/x": Resp(403)}, state=hs())
        f.get("https://a.org/x", sid="s")
        rec = next(iter(collect.SourceHealth(p).data["urls"][ROUND].values()))
        self.assertGreaterEqual(rec["until"] - rec["at"], 24 * 3600)
        for rid, dt_h, exp in (("2026-10-12/r2", 1, "url_cooldown"), ("2026-10-13/r1", 23.9, "url_cooldown"),
                               ("2026-10-13/r2", 24.1, None)):
            t[0] = 1_000_000.0 + dt_h * 3600
            f, _ = mk({"https://a.org/x": Resp(200, b"ok")}, state=hs(), round_id=rid)
            r = f.get("https://a.org/x", sid="s")
            self.assertEqual(r.error, exp, rid)

    def test_r14_5_backfill_r1_does_not_clear_r2_records(self):
        p = self.tmpdir() / "st.json"
        r2, r1 = "2026-10-12/r2", "2026-10-12/r1"
        mk({"https://a.org/A": Resp(403)}, state=collect.SourceHealth(p), round_id=r2)[0].get("https://a.org/A", sid="s")
        mk({"https://b.org/B": Resp(403)}, state=collect.SourceHealth(p), round_id=r1)[0].get("https://b.org/B", sid="s")
        d = collect.SourceHealth(p).data
        self.assertEqual(sorted(d["urls"]), [r1, r2])                                   # 两轮的记录都在
        self.assertIn("a.org", d["host_stops"][r2])
        self.assertIn(collect.url_key("https://a.org/A"), d["urls"][r2])
        f, _ = mk({"https://a.org/A": Resp(200, b"ok")}, state=collect.SourceHealth(p), round_id=r2)
        self.assertEqual(f.get("https://a.org/A", sid="s").error, "host_stopped_this_round")   # 另一 r2 进程不再请求 A
        self.assertEqual(f.opener.calls, [])

    def test_r14_6_redirect_origin_persisted(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/p": Resp(302, headers={"Location": "https://b.org/q"}), "https://b.org/q": Resp(403)},
                  state=collect.SourceHealth(p))
        self.assertEqual(f.get("https://a.org/p", sid="s").error, "http_403")
        d = collect.SourceHealth(p).data
        self.assertIn(collect.url_key("https://a.org/p"), d["urls"][ROUND])             # 起点也写进持久状态
        self.assertIn(collect.url_key("https://b.org/q"), d["urls"][ROUND])
        f2, _ = mk({"https://a.org/p": Resp(200, b"ok")}, state=collect.SourceHealth(p), round_id="2026-10-12/r2")
        self.assertEqual(f2.get("https://a.org/p", sid="s").error, "url_cooldown")      # 新进程、下一轮：起点直接不请求
        self.assertEqual(f2.opener.calls, [])

    def test_r14_8_url_normalization(self):
        n = collect.normalize_url
        self.assertEqual(n("HTTPS://A.Org:443/x#frag"), "https://a.org/x")
        self.assertEqual(n("http://a.org:80"), "http://a.org/")
        self.assertEqual(n("https://a.org:8443/X"), "https://a.org:8443/X")              # 非默认端口、路径大小写保留
        self.assertNotEqual(collect.url_key("https://a.org/x"), collect.url_key("https://a.org/x/"))
        self.assertNotEqual(collect.url_key("https://a.org/x"), collect.url_key("https://a.org/x?q=1"))
        p = self.tmpdir() / "st.json"
        mk({"https://a.org/x": Resp(403)}, state=collect.SourceHealth(p))[0].get("https://a.org/x", sid="s")
        f, _ = mk({"https://A.org:443/x": Resp(200, b"ok"), "https://a.org/x/": Resp(200, b"ok")},
                  state=collect.SourceHealth(p), round_id="2026-10-12/r2")
        self.assertEqual(f.get("https://A.org:443/x#top", sid="s").error, "url_cooldown")   # 等价写法同样冷却
        self.assertTrue(f.get("https://a.org/x/", sid="s").ok)                              # 尾斜杠是不同资源

    def test_r14_4_same_url_two_processes_one_request(self):
        import multiprocessing as mp
        d = self.tmpdir()
        state, lock, log, go = d / "state" / "sh.json", d / "locks", d / "log.txt", d / "go"
        ctx = mp.get_context("fork")
        ps = [ctx.Process(target=_url_race_proc, args=(str(state), str(lock), str(log), str(go))) for _ in range(2)]
        [x.start() for x in ps]
        time.sleep(0.2); go.write_text("1")
        [x.join() for x in ps]
        self.assertEqual([x.exitcode for x in ps], [0, 0])
        self.assertEqual(log.read_text().splitlines(), ["https://a.org/x"])          # 同一 URL 只请求一次

    # ---- 规则 4：每站每分钟最多 1 次（r14 ①）
    def test_r14_1_site_bucket_60s_shared_across_hosts_and_processes(self):
        t = [0.0]
        waits = []

        def sleep(w):
            waits.append(w); t[0] += w
        lock = self.tmpdir()
        routes = {"https://rss.arxiv.org/a": Resp(200, b"1"), "https://export.arxiv.org/b": Resp(200, b"2"),
                  "https://rss.arxiv.org/c": Resp(200, b"3")}
        mkf = lambda **kw: collect.Fetcher(opener=FakeOpener(routes), sleep=sleep, clock=lambda: t[0], resolver=PUBLIC_DNS,
                                           lock_dir=lock, **kw)
        f = mkf()
        f.get("https://rss.arxiv.org/a"); f.get("https://export.arxiv.org/b")
        g = mkf()                                                                  # 另一进程（共享锁文件）
        g.get("https://rss.arxiv.org/c")
        ts = sorted(x for _, x in f.requests + g.requests)
        self.assertEqual(len(ts), 6)                                               # 3 个 robots（新进程重取）+ 3 个正文
        self.assertTrue(all(b - a >= 60.0 - 1e-9 for a, b in zip(ts, ts[1:])), ts)
        self.assertEqual(collect.site_of("rss.arxiv.org"), collect.site_of("export.arxiv.org"))
        self.assertEqual(collect.site_of("a.b.co.uk"), "b.co.uk")

    def test_r14_1_published_limit_needs_basis_and_robots_stricter_wins(self):
        with self.assertRaises(collect.ConfigError):
            collect.load_site_limits({"example.org": {"min_interval_s": 1}})          # 没写依据
        with self.assertRaises(collect.ConfigError):
            collect.load_site_limits({"example.org": {"min_interval_s": 0, "basis": "x"}})
        lim = collect.load_site_limits({"example.org": {"min_interval_s": 10, "basis": "https://example.org/api-terms"}})
        f, sleeps = mk({"https://example.org/1": Resp(200, b"1"), "https://example.org/2": Resp(200, b"2"),
                        "https://example.org/robots.txt": Resp(404)}, site_limits=lim)
        f.get("https://example.org/1"); f.get("https://example.org/2")
        self.assertEqual(sleeps, [10.0, 10.0])
        f, sleeps = mk({"https://example.org/robots.txt": Resp(200, b"User-agent: *\nCrawl-delay: 120\n"),
                        "https://example.org/1": Resp(200, b"1"), "https://example.org/2": Resp(200, b"2")}, site_limits=lim)
        f.get("https://example.org/1"); f.get("https://example.org/2")
        self.assertEqual(sleeps, [120.0, 120.0])                                   # robots 更严则从严（robots 之后每次）
        f, sleeps = mk({"https://sec.gov/robots.txt": Resp(404)})
        self.assertEqual(f.site_gap("data.sec.gov"), 0.2)                          # SEC 维持 5 次/秒

    # ---- 规则 3：最近 5 轮 3 轮可疑 → pending-disable，下一轮起生效（r14 ⑦）
    def test_three_of_last_five_not_consecutive_then_next_round(self):
        hs = collect.SourceHealth(self.tmpdir() / "st.json")
        rounds = ["2026-10-12/r1", "2026-10-12/r2", "2026-10-13/r1", "2026-10-13/r2"]
        res = [["http_403"], [], ["http_429"], ["challenge"]]
        for i, (rid, r) in enumerate(zip(rounds, res)):
            ch = hs.record_round(rid, {"s": r})
            self.assertEqual(ch["s"], i == 3, rid)
        rec = hs.data["sources"]["s"]
        self.assertEqual((rec["status"], rec["pending_round"]), ("pending-disable", "2026-10-13/r2"))
        self.assertIsNone(hs.blocked("s", "2026-10-13/r2"))                         # 触发轮照常跑完
        self.assertTrue(hs.blocked("s", "2026-10-14/r1"))                           # 下一轮起不抓
        self.assertTrue(hs.blocked("s"))                                            # 没有轮次上下文 → 保守拒绝
        e = hs.report()[0]
        self.assertEqual((e["status"], e["flag"], e["suspicious_rounds_in_window"]), ("pending-disable", "grok-bot-review", 3))
        hs.set_status("s", "disabled", "confirmed by Grok Bot")
        self.assertTrue(hs.blocked("s", "2026-10-13/r2"))                           # 人工确认的 disabled 立即生效
        hs2 = collect.SourceHealth(self.tmpdir() / "st.json")
        pat = [["x"], [], [], ["x"], [], [], ["x"]]                                  # 窗口内最多 2 轮 → 不进 pending
        for i, r in enumerate(pat):
            hs2.record_round(f"2026-10-{12 + i // 2}/r{i % 2 + 1}", {"s": [x.replace("x", "http_403") for x in r]})
        self.assertEqual(hs2.data["sources"]["s"]["status"], "ok")
        self.assertEqual(hs2.report()[0]["status"], "watch")

    def test_cooldown_and_host_stop_skips_not_counted(self):
        p = self.tmpdir() / "st.json"
        f, _ = mk({"https://a.org/x": Resp(403)}, state=collect.SourceHealth(p))
        f.get("https://a.org/x", sid="s")
        f.get("https://a.org/y", sid="t")
        self.assertEqual(f.contacted, {"s"})                                         # t 没发请求
        self.assertEqual(list(f.suspicious), ["s"])
        self.assertFalse(collect.is_suspicious("host_stopped_this_round"))
        self.assertFalse(collect.is_suspicious("url_cooldown"))
        self.assertFalse(collect.is_suspicious("host_disabled"))

    def test_round_id_validation(self):
        self.assertEqual(collect.round_id("2026-10-12", 2), "2026-10-12/r2")
        for bad in (("2026-10-12", 3), ("x", 1)):
            with self.assertRaises(collect.ConfigError):
                collect.round_id(*bad)
        with self.assertRaises(collect.ConfigError):
            collect.Fetcher(collect.SourceHealth(self.tmpdir() / "s.json"), resolver=PUBLIC_DNS)   # 持久状态必须给轮次

    # ---- capture_sources 端到端
    S = {"id": "feed", "theme": "ai", "method": "rss", "url": "https://f.org/rss", "enabled": True,
         "approval_status": "approved", "approval_basis": "b", "license": "url+hash-only"}
    S2 = dict(S, id="feed2", url="https://g.org/rss2")
    S3 = dict(S, id="feed3", url="https://f.org/rss3")
    RSS = Resp(200, b"<rss><channel/></rss>", {"Content-Type": "application/rss+xml"})
    ROUNDS = [("2026-10-12", 1), ("2026-10-12", 2), ("2026-10-13", 1), ("2026-10-13", 2), ("2026-10-14", 1),
              ("2026-10-14", 2), ("2026-10-15", 1)]

    def run_round(self, base, date, rnd, routes, sources=None, t=None, cfg=None):
        import contextlib, io, yaml
        from unittest import mock
        src = base / "s.yaml"
        src.write_text(yaml.safe_dump(dict(cfg or {}, sources=sources or [self.S, self.S2])), encoding="utf-8")
        (base / "pub").mkdir(exist_ok=True)
        orig = collect.Fetcher.__init__
        opener = FakeOpener(routes)

        def init(s, *a, **k):
            k["opener"] = opener; k["sleep"] = lambda x: None; k.setdefault("resolver", PUBLIC_DNS)
            orig(s, *a, **k)
        collect.Fetcher.__init__ = init
        err = io.StringIO()
        # 墙钟：每个日期相隔 25 小时（URL 冷却 24 小时），同日两轮相隔 6 小时
        day = int(date[-2:]) - 12
        now = 2_000_000_000.0 + day * 25 * 3600 + (rnd - 1) * 6 * 3600 if t is None else t
        try:
            with contextlib.redirect_stderr(err), mock.patch("time.time", return_value=now):
                rc = CS.main(["--sources", str(src), "--date", date, "--round", str(rnd),
                              "--out-root", str(base / "pub"), "--private-root", str(base / "priv")])
        finally:
            collect.Fetcher.__init__ = orig
        return rc, err.getvalue(), [u for u, _ in opener.calls]

    def health_reports(self, base, date, rnd):
        d = base / "pub" / "raw" / date / ("round2" if rnd == 2 else "")
        return [json.loads(p.read_text()) for p in sorted(d.glob("source-health-*.json"))]

    def test_capture_three_of_five_pending_report_same_round_ok_next_round_skip(self):
        base = self.tmpdir()
        ok = {"https://f.org/rss": self.RSS, "https://g.org/rss2": self.RSS, "https://f.org/rss3": self.RSS}
        bad = dict(ok, **{"https://f.org/rss": Resp(403)})
        plan = [bad, ok, bad, ok, bad]                      # 可疑/正常/可疑/正常/可疑：不连续，5 轮里 3 轮
        for i, ((date, rnd), routes) in enumerate(zip(self.ROUNDS, plan)):
            rc, err, calls = self.run_round(base, date, rnd, routes)
            self.assertIn("https://g.org/rss2", calls)                                   # 别的主机照常
            if i < 4:
                self.assertNotIn("Grok Bot 复核", err)
                self.assertFalse(list((base / "pub" / "raw" / date).rglob("GROK-BOT-REVIEW-*.md")) and i < 2)
        rep = self.health_reports(base, "2026-10-14", 1)[-1]
        e = [x for x in rep if x["id"] == "feed"][0]
        self.assertEqual((e["status"], e["flag"], e["newly_flagged"], e["pending_round"]),
                         ("pending-disable", "grok-bot-review", True, "2026-10-14/r1"))
        self.assertIn("PENDING-DISABLE feed", err)
        self.assertIn("=== 待 Grok Bot 复核（pending-disable）1 个源：feed", err)          # 当天汇报显眼可见
        self.assertIn("pending_disable=1", err.strip().splitlines()[-1])
        md = list((base / "pub" / "raw" / "2026-10-14").glob("GROK-BOT-REVIEW-*.md"))
        self.assertEqual(len(md), 1)
        self.assertIn("| feed | 是 | 3 | 2026-10-14/r1 |", md[0].read_text())
        self.assertNotIn("f.org", md[0].read_text())                                    # 不含 URL
        self.assertIn("GROK-BOT-REVIEW-", (base / "pub/raw/2026-10-14/MANIFEST.sha256").read_text())
        # 同一轮补跑（r14 ⑦）：pending 从下一轮起才生效——但 f.org 本轮已因 403 停止，feed 仍不发请求
        rc, err, calls = self.run_round(base, "2026-10-14", 1, ok, sources=[self.S])
        self.assertNotIn("source_blocked", err)
        self.assertIn("host_stopped_this_round", err)
        # 下一轮：feed 跳过（source_blocked）、同主机的 feed3 照常
        rc, err, calls = self.run_round(base, "2026-10-14", 2, ok, sources=[self.S, self.S3])
        self.assertNotIn("https://f.org/rss", calls)
        self.assertIn("https://f.org/rss3", calls)
        self.assertIn("SKIP feed source_blocked", err)
        skipped = json.loads(next((base / "pub/raw/2026-10-14/round2").glob("skipped-*.json")).read_text())
        self.assertEqual([x["reason"] for x in skipped], ["source_blocked"])
        for p in (base / "pub").rglob("*.json"):
            self.assertNotIn(str(base), p.read_text())                                  # 不写本机路径

    def test_capture_pending_same_round_rerun_not_blocked(self):
        # r14 ⑦：触发 pending 的那一轮，补跑同源其他 URL（换主机）不会被 source_blocked
        base = self.tmpdir()
        hs = collect.SourceHealth(base / "priv" / "state" / "source-health.json")
        for rid in ("2026-10-12/r1", "2026-10-12/r2", "2026-10-13/r1"):
            hs.record_round(rid, {"feed": ["http_403"]})
        self.assertEqual(hs.data["sources"]["feed"]["pending_round"], "2026-10-13/r1")
        moved = dict(self.S, url="https://h.org/rss")
        rc, err, calls = self.run_round(base, "2026-10-13", 1, {"https://h.org/rss": self.RSS}, sources=[moved])
        self.assertIn("https://h.org/rss", calls)
        rc, err, calls = self.run_round(base, "2026-10-13", 2, {"https://h.org/rss": self.RSS}, sources=[moved])
        self.assertEqual(calls, [])
        self.assertIn("source_blocked", err)

    def test_capture_format_suspect_stops_host_and_persists_request_url(self):
        base = self.tmpdir()
        routes = {"https://f.org/rss": Resp(200, b"<html><body>hello</body></html>", {"Content-Type": "text/html"}),
                  "https://f.org/rss3": self.RSS, "https://g.org/rss2": self.RSS}
        rc, err, calls = self.run_round(base, "2026-10-12", 1, routes, sources=[self.S, self.S3, self.S2])
        self.assertIn("suspected_challenge:", err)
        self.assertNotIn("https://f.org/rss3", calls)                                   # 同主机本轮停止
        self.assertIn("SKIP feed3 host_stopped_this_round", err)
        self.assertIn("https://g.org/rss2", calls)
        hs = collect.SourceHealth(base / "priv" / "state" / "source-health.json")
        self.assertEqual(hs.data["sources"]["feed"]["rounds"]["2026-10-12/r1"]["suspicious"], True)
        self.assertNotIn("feed3", hs.data["sources"])                                   # 没发请求的源不记轮
        self.assertIn(collect.url_key("https://f.org/rss"), hs.data["urls"]["2026-10-12/r1"])

    def test_capture_site_rate_limits_from_sources_yaml(self):
        base = self.tmpdir()
        rc, err, _ = self.run_round(base, "2026-10-12", 1, {}, cfg={"site_rate_limits": {"f.org": {"min_interval_s": 5}}})
        self.assertEqual(rc, 2)
        self.assertIn("basis", err)

    def test_capture_internal_source_report_not_public(self):
        base = self.tmpdir()
        internal = dict(self.S, id="secretfeed", internal_only=True, url="https://g.org/rss")
        os.environ["MARKJIN_INTERNAL_DIR"] = str(base / "internal")
        try:
            self.run_round(base, "2026-10-12", 1, {"https://g.org/rss": Resp(403)}, sources=[internal])
        finally:
            del os.environ["MARKJIN_INTERNAL_DIR"]
        for p in (base / "pub").rglob("*"):
            if p.is_file():
                self.assertNotIn("secretfeed", p.read_text())
        self.assertTrue(list((base / "internal").rglob("source-health-*.json")))

    def test_source_health_cli_confirm_and_enable(self):
        import contextlib, io
        import source_health as SH
        base = self.tmpdir()
        st = base / "priv" / "state" / "source-health.json"
        hs = collect.SourceHealth(st)
        for rid in ("2026-10-12/r1", "2026-10-12/r2", "2026-10-13/r1"):
            hs.record_round(rid, {"feed": ["http_403"]})
        args = ["--private-root", str(base / "priv"), "--out-root", str(base / "pub")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(SH.main(["report", *args]), 0)
        self.assertEqual(json.loads(out.getvalue())["sources"][0]["status"], "pending-disable")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(SH.main(["confirm-disable", "--id", "feed", *args]), 2)        # 必须写明确认依据
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SH.main(["confirm-disable", "--id", "feed", "--reason", "Grok Bot confirmed", *args]), 0)
        self.assertEqual(collect.SourceHealth(st).data["sources"]["feed"]["status"], "disabled")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SH.main(["enable", "--id", "feed", *args]), 0)
        self.assertIsNone(collect.SourceHealth(st).blocked("feed"))
        st.write_text("{}")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(SH.main(["report", *args]), 2)                                 # 损坏文件 → 2，不改写
        self.assertEqual(st.read_text(), "{}")


class LegacyHosts(unittest.TestCase):
    """旧 collector-hosts.json（r14 ③、现行规则 6）：未迁移 → 拒绝运行；migrate 迁为「已停用（等人工复核）」；
    其中主机全部保持停用、不会被重新请求、不计入可疑轮数；机器人验证 / 登录停用的标 unrecoverable，enable 默认拒绝。"""

    def tmpdir(self):
        d = tempfile.TemporaryDirectory(dir="/workspace"); self.addCleanup(d.cleanup); return Path(d.name)

    LEGACY = {"hosts": {"a.org": {"reason": "HTTP 403", "at": "2026-10-12T05:01:00+08:00", "needs": "manual review"},
                        "B.org": {"reason": "bot challenge page: vendor marker (HTTP 503)", "at": "2026-10-12T05:02:00+08:00"},
                        "c.org": {"reason": "HTTP 401", "at": "2026-10-13T05:03:00+08:00"},
                        "d.org": {"reason": "robots.txt bot challenge page (HTTP 200)", "at": "2026-10-13T05:04:00+08:00"},
                        "f.org": {"reason": "robots.txt HTTP 403"}},
              "sources": {"feedx": {"reason": "HTTP 401", "at": "2026-10-13T05:03:00+08:00", "host": "c.org"}}}

    def priv(self, legacy=None):
        base = self.tmpdir()
        st = base / "priv" / "state"; st.mkdir(parents=True)
        (st / "collector-hosts.json").write_text(json.dumps(self.LEGACY if legacy is None else legacy))
        return base

    def migrate(self, base):
        import contextlib, io
        import source_health as SH
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = SH.main(["migrate", "--private-root", str(base / "priv"), "--out-root", str(base / "pub")])
        return rc, json.loads(out.getvalue() or "{}")

    def test_unmigrated_legacy_refuses_to_run(self):
        import contextlib, io
        import source_health as SH
        base = self.priv()
        B = BlockRule1522()
        rc, err, calls = B.run_round(base, "2026-10-14", 1, {"https://g.org/rss2": B.RSS})
        self.assertEqual((rc, calls), (2, []))
        self.assertIn("migrate", err)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(SH.main(["report", "--private-root", str(base / "priv"), "--out-root", str(base / "pub")]), 2)
        with self.assertRaises(collect.StateError):
            collect.open_source_health(base / "priv")

    def test_migrate_marks_disabled_pending_review_and_unrecoverable(self):
        base = self.priv()
        legacy = base / "priv" / "state" / "collector-hosts.json"
        before = legacy.read_bytes()
        rc, res = self.migrate(base)
        self.assertEqual((rc, res), (0, {"hosts": 5, "sources": 1, "skipped": False}))
        hs = collect.open_source_health(base / "priv")                      # 迁移后可以运行
        H = hs.data["hosts"]
        self.assertEqual({h: (r["category"], r["unrecoverable"]) for h, r in H.items()},
                         {"a.org": ("http_403", False), "b.org": ("bot_check", True), "c.org": ("login", True),
                          "d.org": ("bot_check", True), "f.org": ("http_403", False)})
        for r in H.values():
            self.assertEqual((r["status"], r["review"]), ("disabled", "pending-manual-review"))
        self.assertEqual(H["b.org"]["reason"], "bot challenge page: vendor marker (HTTP 503)")   # 原文
        self.assertEqual(H["a.org"]["since"], "2026-10-12T05:01:00+08:00")
        self.assertEqual((hs.data["sources"]["feedx"]["status"], hs.data["sources"]["feedx"]["unrecoverable"]),
                         ("disabled", True))
        self.assertEqual(legacy.read_bytes(), before)                       # 旧文件不改不删
        self.assertTrue(self.migrate(base)[1]["skipped"])                   # 幂等
        legacy.write_text(json.dumps(dict(self.LEGACY, hosts={"z.org": {"reason": "HTTP 403"}})))
        with self.assertRaises(collect.StateError):                          # 旧文件变了 → 再次拒绝运行，直到再迁移
            collect.open_source_health(base / "priv")

    def test_legacy_hosts_never_requested_over_rounds_not_counted(self):
        base = self.priv()
        self.migrate(base)
        B = BlockRule1522()
        S = dict(B.S, id="feed", url="https://f.org/rss")
        Sa = dict(B.S, id="feeda", url="https://a.org/rss")
        Sb = dict(B.S, id="feedb", url="https://ok.org/rss", )
        routes = {"https://f.org/rss": B.RSS, "https://a.org/rss": B.RSS, "https://ok.org/rss": B.RSS,
                  "https://ok.org/redir": Resp(302, headers={"Location": "https://b.org/x"})}
        for date, rnd in B.ROUNDS:
            rc, err, calls = B.run_round(base, date, rnd, routes, sources=[S, Sa, Sb])
            self.assertFalse([u for u in calls if any(h in u for h in ("a.org", "b.org", "c.org", "d.org", "f.org"))],
                             (date, rnd))                                   # 旧表主机一个都不请求（含 robots）
            self.assertIn("https://ok.org/rss", calls)
            self.assertIn("SKIP feed host_disabled", err)
            self.assertIn("SKIP feeda host_disabled", err)
            self.assertNotIn("PENDING-DISABLE", err)
        hs = collect.SourceHealth(base / "priv" / "state" / "source-health.json")
        self.assertNotIn("feed", hs.data["sources"])                        # 不计入可疑轮数
        self.assertEqual(hs.data["hosts"]["f.org"]["status"], "disabled")   # 没有自动恢复
        f, _ = mk({"https://ok.org/redir": Resp(302, headers={"Location": "https://B.org/x"})}, state=hs,
                  round_id="2026-10-16/r1")
        self.assertEqual(f.get("https://ok.org/redir", sid="s").error, "host_disabled")   # 经跳转也不请求
        self.assertFalse([u for u, _ in f.opener.calls if "b.org" in u.lower()])
        self.assertEqual(f._raw("https://a.org/x", "*/*")[3], "host_disabled")            # 最底层出站入口同样拒绝

    def test_corrupt_legacy_refuses(self):
        for bad in ("{bad", "[]", '{"hosts": {"a.org": {}}}', '{"hosts": []}'):
            base = self.tmpdir()
            st = base / "priv" / "state"; st.mkdir(parents=True)
            (st / "collector-hosts.json").write_text(bad)
            B = BlockRule1522()
            rc, err, calls = B.run_round(base, "2026-10-14", 1, {"https://g.org/rss2": B.RSS})
            self.assertEqual((rc, calls), (2, []), bad)
            import contextlib, io
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                import source_health as SH
                self.assertEqual(SH.main(["migrate", "--private-root", str(base / "priv"),
                                          "--out-root", str(base / "pub")]), 2)
            self.assertFalse((st / "source-health.json").exists())

    def test_enable_refuses_unrecoverable_by_default(self):
        import contextlib, io
        import source_health as SH
        base = self.priv()
        self.migrate(base)
        args = ["--private-root", str(base / "priv"), "--out-root", str(base / "pub")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(SH.main(["report", *args]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["disabled_hosts"]), 5)
        st = base / "priv" / "state" / "source-health.json"
        q = io.StringIO()
        with contextlib.redirect_stderr(q), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SH.main(["enable", "--host", "b.org", "--reason", "x", *args]), 2)   # bot_check
            self.assertEqual(SH.main(["enable", "--host", "c.org", "--reason", "x", *args]), 2)   # login
            self.assertEqual(SH.main(["enable", "--host", "c.org", "--allow-unrecoverable", *args]), 2)  # 无依据
            self.assertEqual(SH.main(["enable", "--id", "feedx", *args]), 2)                      # 旧表 login 源
            self.assertEqual(SH.main(["enable", "--host", "a.org", *args]), 2)                    # 403 也须写依据
        self.assertIn("unrecoverable", q.getvalue())
        self.assertEqual(len(collect.SourceHealth(st).data["hosts"]), 5)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(SH.main(["enable", "--host", "a.org", "--reason", "reviewed by Grok Bot", *args]), 0)
            self.assertEqual(SH.main(["enable", "--host", "b.org", "--allow-unrecoverable",
                                      "--reason", "vendor whitelisted us, confirmed by Grok Bot", *args]), 0)
            self.assertEqual(SH.main(["enable", "--id", "feedx", "--allow-unrecoverable",
                                      "--reason", "confirmed by Grok Bot", *args]), 0)
        hs = collect.open_source_health(base / "priv")                      # 旧文件还在，也不会再迁移回去
        self.assertEqual(sorted(hs.data["hosts"]), ["c.org", "d.org", "f.org"])
        self.assertIsNone(hs.host_blocked("a.org"))
        self.assertIsNone(hs.blocked("feedx"))

    def test_legacy_category_from_original_reason(self):
        for reason, cat in (("HTTP 403", "http_403"), ("HTTP 401", "login"), ("robots.txt HTTP 401", "login"),
                            ("robots.txt HTTP 403", "http_403"), ("bot challenge page: vendor marker (HTTP 403)", "bot_check"),
                            ("robots.txt bot challenge page (HTTP 503)", "bot_check"), ("login required", "login"),
                            ("network", "other")):
            self.assertEqual(collect.legacy_category(reason), cat, reason)



if __name__ == "__main__":
    unittest.main()
