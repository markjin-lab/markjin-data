"""#10 路由反例测试。每个用例同时断言 路由状态、low_risk（重新计算值）与错误码。"""
import copy, datetime as dt, hashlib, json, os, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from helpers import make_repo, arxiv_line, quote_line, fred_line, DUMMY_INTERNAL, DATE
from markjin import route as R
from markjin import approvals as _A
from markjin.selfcheck import check_text, compute_low_risk

SGT = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 1, 5, 3, 25, tzinfo=SGT)
EOD = dt.datetime(2026, 1, 5, 7, 0, tzinfo=SGT)
SESSION = "01a125bd-02b5-7df2-9964-827ba9708316"
REPO = make_repo()
TITLE = f"# 日报 {DATE}\n"
DISC = "\n本文不含投资建议。\n"
CLEAN = TITLE + quote_line()   # 低风险结构白名单：标题 + 原文直引
INFER = TITLE + arxiv_line("作者声称 MMLU 90%。")


def sc_of(text, card_type="daily"):
    return check_text(text, REPO, DATE, card_type, link_checker=lambda u: True)


def decide_(sc, draft, *a, **k):
    """测试便利：未显式给出时，把自检结果绑定到该稿件（r12 decide() 核对 content_sha256）。"""
    if isinstance(sc, dict) and isinstance(draft, dict) and "content_sha256" not in sc:
        sc = dict(sc, content_sha256=draft.get("content_sha256"))
    from helpers import evaluate_for_tests
    return evaluate_for_tests(sc, draft, *a, **k)   # 测试专用组合；生产发布入口只有 route_pr


def draft_of(text, did="2026-01-05-d1"):
    return {"draft_id": did, "date": DATE, "content_sha256": hashlib.sha256(text.encode()).hexdigest()}


def state(**kw):
    s = {"version": 1, "updated_at": (NOW - dt.timedelta(minutes=5)).isoformat(), "mac_online": True,
         "wang_present": True, "codex_in_production": False, "drafts": {}}
    s.update(kw); return s


def codex(draft, **kw):
    r = {"content_sha256": draft["content_sha256"], "draft_id": draft["draft_id"], "codex_session": SESSION, "verdict": "APPROVED",
         "log_path": "review/codex/2026-01-05-d1.log", "reviewed_at": "2026-01-05T02:25:00+08:00"}
    r.update(kw); return r


def wang(draft, **kw):
    r = {"content_sha256": draft["content_sha256"], "recorded_at": (NOW - dt.timedelta(minutes=30)).isoformat(),
         "channel": "via-grok-bot", "quote": "同意发布",
         "schema_version": 2, "draft_id": draft["draft_id"], "quote_ref": "grok-bot:t200u"}   # r12：需王总批准的稿件只收 v2
    r.update(kw); return r


def wang_v1(draft, **kw):
    r = wang(draft, **kw)
    for k in ("schema_version", "draft_id", "quote_ref"):
        r.pop(k, None)
    return r


def recs(draft=None, c=True, w=True, **kw):
    out = {"codex": [codex(draft)] if (c and draft) else [], "wang": [wang(draft)] if (w and draft) else [],
           "error": None}
    out.update(kw); return out


class T(unittest.TestCase):
    def run_(self, text=INFER, st="default", rc="default", now=NOW, card_type="daily", sc=None, draft=None):
        sc = sc if sc is not None else sc_of(text, card_type)
        draft = draft or draft_of(text)
        sc = dict(sc, content_sha256=draft.get("content_sha256")) if isinstance(sc, dict) and isinstance(draft, dict) and "content_sha256" not in sc else sc
        rc = recs(draft, c=False, w=False) if rc == "default" else rc
        return sc, decide_(sc, draft, state() if st == "default" else st, rc, now)

    def run_s(self, text=INFER, **kw):
        """严格路径（需王总批准）的稿件：标为中医/佛学内容（flags.medical）。王总记录与在岗规则只对这类稿件生效。"""
        sc = kw.pop("sc", None) or sc_of(text, kw.get("card_type", "daily"))
        sc = copy.deepcopy(sc); sc["flags"]["medical"] = True
        return self.run_(text, sc=sc, **kw)

    def run_w(self, text=INFER, **kw):
        """需要王总批准的稿件（自检识别为宏观，按 needs_wang）：用于验证心跳、离线、在场规则。"""
        sc = kw.pop("sc", None) or sc_of(text, kw.get("card_type", "daily"))
        sc = dict(sc, flags=dict(sc["flags"], macro=True))
        return self.run_(text, sc=sc, **kw)

    def expect(self, res, st, low_risk, code=None):
        sc, d = res
        self.assertEqual(d.state, st, d.codes)
        self.assertIs(compute_low_risk(sc), low_risk)
        if code:
            self.assertIn(code, d.codes)
        self.assertEqual(d.publishable, st in ("AUTO_APPROVED", "APPROVED"))


class LowRisk(T):
    def test_auto(self):
        # t161u：低风险自动批准已取消；low_risk 只作参考
        self.expect(self.run_(CLEAN), "NEEDS_REVIEW", True, "E-ROUTE-NO-CODEX")
        d = draft_of(CLEAN)
        self.expect(self.run_(CLEAN, rc=recs(d)), "APPROVED", True)

    def test_auto_even_mac_offline_wang_absent(self):
        self.expect(self.run_(CLEAN, st=state(mac_online=False, wang_present=False)), "ARCHIVED", True, "A-MAC-OFFLINE")

    def test_forged_low_risk_not_trusted(self):
        sc = sc_of(INFER); sc["low_risk"] = True
        self.expect(self.run_(INFER, sc=sc), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")

    def test_forged_flags_still_blocked_by_codes(self):
        sc = sc_of(INFER); sc["low_risk"] = True; sc["flags"]["has_inference"] = False
        self.expect(self.run_(INFER, sc=sc), "NEEDS_REVIEW", False)

    def test_signal_macro_paragraph_need_review(self):
        for text, ct in ((CLEAN, "signal"), (TITLE + fred_line(), "daily")):
            self.expect(self.run_(text, card_type=ct), "NEEDS_REVIEW", False, "I-NEEDS-REVIEW")
        # 不命中词表、也没有来源的事实段落：无来源块规则 → UNCLEAR，拿到批准记录也不发布
        t0 = TITLE + "这是一段说明。\n" + arxiv_line()
        self.expect(self.run_(t0), "HOLD", False, "E-ROUTE-UNCLEAR")
        self.expect(self.run_(t0, rc=recs(draft_of(t0))), "HOLD", False, "E-ROUTE-UNCLEAR")
        # 无来源的判断段落：自检 FAIL → HOLD，拿到批准记录也不发布
        t = TITLE + "这意味着变化。\n" + arxiv_line()
        self.expect(self.run_(t), "HOLD", False, "E-ROUTE-SELFCHECK-FAIL")
        self.expect(self.run_(t, rc=recs(draft_of(t))), "HOLD", False, "E-REPLAY-001")


class InputSchema(T):
    def test_missing_or_none_fields(self):
        base = sc_of(INFER)
        for k in ("status", "flags", "counts", "error_codes", "card_type", "date", "low_risk", "errors"):
            for v in ("DEL", None):
                sc = copy.deepcopy(base)
                if v == "DEL": sc.pop(k)
                else: sc[k] = None
                self.expect(self.run_(INFER, sc=sc), "HOLD", False, "E-ROUTE-INPUT")

    def test_flag_none(self):
        sc = sc_of(INFER); sc["flags"]["internal"] = None
        self.expect(self.run_(INFER, sc=sc), "HOLD", False, "E-ROUTE-INPUT")

    def test_bad_draft_and_now(self):
        d = draft_of(INFER)
        for bad in ({**d, "content_sha256": None}, {**d, "draft_id": "含 空格"}, {**d, "date": "2026-02-30"},
                    {k: v for k, v in d.items() if k != "content_sha256"}, {**d, "extra": 1}, {**d, "date": "2026-01-06"}):
            self.expect(self.run_(INFER, draft=bad), "HOLD", False, "E-ROUTE-INPUT")
        self.expect(self.run_(INFER, now=dt.datetime(2026, 1, 5, 10)), "HOLD", False, "E-ROUTE-INPUT")
        self.expect(self.run_(CLEAN, now=None), "HOLD", True, "E-ROUTE-INPUT")


class StateFile(T):
    def test_state_missing_or_bad(self):
        bads = [None, {}, state(mac_online=None), state(wang_present="yes"), state(codex_in_production=None),
                state(updated_at="2026-01-05T02:25"), state(updated_at=(NOW + dt.timedelta(hours=1)).isoformat()),
                {**state(), "extra": 1}, state(version=2), state(drafts=None),
                state(drafts={"2026-01-05-d1": {"status": "archived", "reason": "随便", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}})]
        for b in bads:
            self.expect(self.run_(CLEAN, st=b), "HOLD", True, "E-ROUTE-STATE")

    def test_stale_heartbeat_holds_not_archives(self):
        # 心跳过期（>30 分钟）：一律 HOLD（可重试），无论 mac_online 写的是什么，也不归档
        # 只对需要 Codex 审查的稿件生效（反例：需审查稿 + 过期心跳 → HOLD）
        for mac in (True, False):
            st = state(updated_at=(NOW - dt.timedelta(minutes=31)).isoformat(), mac_online=mac)
            sc, d = self.run_w(INFER, st=st, rc=recs(draft_of(INFER)))
            self.expect((sc, d), "HOLD", False, "E-ROUTE-MAC-STALE")
            self.assertIsNone(d.state_change)

    def test_low_risk_ignores_heartbeat(self):
        # t161u：低风险自动批准取消后，低风险稿与其他稿一样看心跳：过期 HOLD、新鲜离线归档、新鲜在线待审
        for minutes in (1, 31, 600):
            for mac in (True, False):
                st = state(updated_at=(NOW - dt.timedelta(minutes=minutes)).isoformat(), mac_online=mac)
                sc, d = self.run_(CLEAN, st=st)
                exp = ("HOLD", "E-ROUTE-MAC-STALE") if minutes > 30 else (("NEEDS_REVIEW", "E-ROUTE-NO-CODEX") if mac else ("ARCHIVED", "A-MAC-OFFLINE"))
                self.expect((sc, d), exp[0], True, exp[1])

    def test_low_risk_heartbeat_not_a_bypass(self):
        # 反例：低风险豁免不放宽其他检查——状态文件坏仍 HOLD；已归档仍 ARCHIVED；已顺延的低风险稿走审查路径，心跳过期 → HOLD
        stale = (NOW - dt.timedelta(minutes=31)).isoformat()
        self.expect(self.run_(CLEAN, st=state(updated_at=stale, mac_online=None)), "HOLD", True, "E-ROUTE-STATE")
        ar = {"status": "archived", "reason": "A-MAC-OFFLINE", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}
        self.expect(self.run_(CLEAN, st=state(updated_at=stale, drafts={"2026-01-05-d1": ar})),
                    "ARCHIVED", True, "E-ROUTE-ARCHIVED-REUSE")
        df = {"status": "deferred", "reason": "I-DEFERRED", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(CLEAN)["content_sha256"]}
        n2 = NOW + dt.timedelta(days=1); stale2 = (n2 - dt.timedelta(minutes=31)).isoformat()
        # t161u：顺延的低风险稿也看心跳，过期 → HOLD
        self.expect(self.run_(CLEAN, now=n2, st=state(updated_at=stale2, mac_online=False, drafts={"2026-01-05-d1": df})),
                    "HOLD", True, "E-ROUTE-MAC-STALE")
        dfi = df | {"content_sha256": draft_of(INFER)["content_sha256"]}
        sc, d = self.run_(INFER, now=n2, st=state(updated_at=stale2, mac_online=False, drafts={"2026-01-05-d1": dfi}))
        self.expect((sc, d), "HOLD", False, "E-ROUTE-MAC-STALE"); self.assertIsNone(d.state_change)

    def test_fresh_heartbeat_boundary(self):
        st = state(updated_at=(NOW - dt.timedelta(minutes=30)).isoformat(), mac_online=False)
        sc, d = self.run_(INFER, st=st)
        self.expect((sc, d), "ARCHIVED", False, "A-MAC-OFFLINE")
        self.assertEqual(d.state_change["status"], "archived"); self.assertEqual(d.state_change["reason"], "A-MAC-OFFLINE")

    def test_fresh_online_not_archived(self):
        st = state(updated_at=(NOW - dt.timedelta(minutes=1)).isoformat(), mac_online=True)
        sc, d = self.run_(INFER, st=st)
        self.expect((sc, d), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX"); self.assertIsNone(d.state_change)

    def test_archived_final(self):
        ar = {"status": "archived", "reason": "A-MAC-OFFLINE", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}
        d = draft_of(INFER)
        for text in (CLEAN, INFER):
            self.expect(self.run_(text, st=state(drafts={"2026-01-05-d1": ar}), rc=recs(draft_of(text))),
                        "ARCHIVED", text == CLEAN, "E-ROUTE-ARCHIVED-REUSE")

    def test_codex_in_production(self):
        d = draft_of(INFER)
        self.expect(self.run_w(INFER, st=state(codex_in_production=True), rc=recs(d)), "ARCHIVED", False, "A-NO-REVIEW-PATH")

    def test_mac_offline(self):
        d = draft_of(INFER)
        self.expect(self.run_w(INFER, st=state(mac_online=False), rc=recs(d)), "ARCHIVED", False, "A-MAC-OFFLINE")

    def test_deferred_once(self):
        self.expect(self.run_s(INFER, st=state(wang_present=False)), "DEFERRED", False, "I-DEFERRED")
        df = {"status": "deferred", "reason": "I-DEFERRED", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}
        n2, e2 = NOW + dt.timedelta(days=1), EOD + dt.timedelta(days=1)
        self.expect(self.run_s(INFER, now=n2, st=state(updated_at=(n2 - dt.timedelta(minutes=5)).isoformat(), wang_present=False,
                                                      drafts={"2026-01-05-d1": df})), "ARCHIVED", False, "A-NOT-APPROVED")
        self.expect(self.run_s(INFER, now=e2, st=state(updated_at=(e2 - dt.timedelta(minutes=1)).isoformat(),
                                                      drafts={"2026-01-05-d1": df})), "ARCHIVED", False, "A-NOT-APPROVED")


class Records(T):
    def test_approved(self):
        self.expect(self.run_(INFER, rc=recs(draft_of(INFER))), "APPROVED", False)

    def test_no_records(self):
        self.expect(self.run_s(INFER), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")
        d = draft_of(INFER)
        self.expect(self.run_s(INFER, rc=recs(d, w=False)), "NEEDS_REVIEW", False, "E-ROUTE-NO-WANG")
        self.expect(self.run_s(INFER, rc=recs(d, c=False)), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")

    def test_codex_rejected(self):
        d = draft_of(INFER)
        rc = recs(d) | {"codex": [codex(d, verdict="REJECTED")]}
        self.expect(self.run_(INFER, rc=rc), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")

    def test_bound_by_sha(self):
        d = draft_of(INFER); other = draft_of(INFER + "x")
        self.expect(self.run_s(INFER, rc=recs(other)), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")
        self.expect(self.run_s(INFER, rc=recs(d) | {"wang": [wang(other)]}), "NEEDS_REVIEW", False, "E-ROUTE-NO-WANG")

    def test_edited_draft_after_approval(self):
        self.expect(self.run_(INFER + "\n", rc=recs(draft_of(INFER))), "NEEDS_REVIEW", False, "E-ROUTE-NO-CODEX")

    def test_invalid_file_not_trusted(self):
        d = draft_of(INFER)
        self.expect(self.run_(INFER, rc=recs(d) | {"error": "E-ROUTE-RECORD-INVALID"}), "HOLD", False, "E-ROUTE-RECORD-INVALID")
        self.expect(self.run_(INFER, rc=recs(d) | {"error": "E-ROUTE-APPROVALS-REWRITTEN"}), "HOLD", False, "E-ROUTE-APPROVALS-REWRITTEN")
        for bad in ({"codex": None}, {"wang": None}, {"codex": "x"}):
            self.expect(self.run_(INFER, rc=recs(d) | bad), "HOLD", False, "E-ROUTE-STATE")

    def test_same_sgt_day_only(self):
        d = draft_of(INFER)
        bad = [(NOW - dt.timedelta(days=1)).isoformat(), (NOW + dt.timedelta(hours=1)).isoformat(),
               dt.datetime(2026, 1, 4, 23, 59, tzinfo=SGT).isoformat(),
               dt.datetime(2026, 1, 4, 15, 59, tzinfo=dt.timezone.utc).isoformat()]   # = SGT 01-04 23:59
        for t in bad:
            self.expect(self.run_s(INFER, rc=recs(d) | {"wang": [wang(d, recorded_at=t)]}), "NEEDS_REVIEW", False, "E-ROUTE-RECORD-EXPIRED")
        good = [dt.datetime(2026, 1, 5, 0, 0, tzinfo=SGT).isoformat(),
                dt.datetime(2026, 1, 4, 16, 0, tzinfo=dt.timezone.utc).isoformat()]   # = SGT 01-05 00:00
        for t in good:
            rc = {"codex": [codex(d, reviewed_at="2026-01-05T00:00:00+08:00")], "wang": [wang(d, recorded_at=t)], "error": None}
            self.expect(self.run_s(INFER, rc=rc), "APPROVED", False)

    def test_signal_requires_v2_and_direct(self):
        d = draft_of(CLEAN)
        v2 = dict(wang(d, channel="direct"), schema_version=2, draft_id=d["draft_id"], quote_ref="coord-bot:msg/12345")
        self.expect(self.run_(CLEAN, card_type="signal", rc=recs(d) | {"wang": [wang_v1(d)]}), "NEEDS_REVIEW", False, "E-ROUTE-RECORD-V2-REQUIRED")
        self.expect(self.run_(CLEAN, card_type="signal", rc=recs(d) | {"wang": [wang_v1(d, channel="direct")]}),
                    "NEEDS_REVIEW", False, "E-ROUTE-RECORD-V2-REQUIRED")
        self.expect(self.run_(CLEAN, card_type="signal", rc=recs(d) | {"wang": [dict(v2, channel="via-grok-bot")]}),
                    "NEEDS_REVIEW", False, "E-ROUTE-RECORD-MISMATCH")
        self.expect(self.run_(CLEAN, card_type="signal", rc=recs(d) | {"wang": [v2]}), "APPROVED", False)

    def test_v2_schema(self):
        from markjin.approvals import valid_wang
        d = draft_of(INFER)
        v2 = dict(wang(d), schema_version=2, draft_id=d["draft_id"], quote_ref="coord-bot:msg/12345")
        self.assertTrue(valid_wang(v2))
        for bad in (dict(v2, quote_ref=""), dict(v2, quote_ref=None), dict(v2, quote_ref="有 空格"),
                    dict(v2, schema_version=3), {k: v for k, v in v2.items() if k != "quote_ref"},
                    dict(wang_v1(d), quote_ref="x")):
            self.assertFalse(valid_wang(bad))
        self.expect(self.run_(INFER, rc=recs(d) | {"wang": [v2]}), "APPROVED", False)


class Schema(unittest.TestCase):
    """approvals/ 严格 schema。断言 status（拒绝）、low_risk（不适用，恒 False）与错误码。"""
    def rej(self, name, text, v):
        from markjin.approvals import parse_record, ApprovalsError
        with self.assertRaises(ApprovalsError) as cm:
            parse_record(name, text, v)
        self.assertEqual(cm.exception.code, "E-ROUTE-RECORD-INVALID")

    def test_codex_schema(self):
        from markjin.approvals import valid_codex, parse_record
        d = draft_of(INFER); n = d["content_sha256"] + ".json"
        self.assertEqual(parse_record(n, json.dumps(codex(d)), valid_codex)["verdict"], "APPROVED")
        for bad in (codex(d, codex_session="x"), codex(d, codex_session=None), codex(d, verdict="OK"),
                    codex(d, log_path="/abs"), codex(d, log_path="a/../x"), codex(d, content_sha256="0" * 64),
                    {**codex(d), "approver": "wang"}, {k: v for k, v in codex(d).items() if k != "log_path"}):
            self.rej(n, json.dumps(bad), valid_codex)
        self.rej(n, "{oops", valid_codex); self.rej(n, "[]", valid_codex)
        self.rej("x.json", json.dumps(codex(d)), valid_codex)

    def test_wang_schema(self):
        from markjin.approvals import valid_wang
        d = draft_of(INFER); n = d["content_sha256"] + ".json"
        for bad in (wang(d, quote=""), wang(d, quote=None), wang(d, channel="bot"), wang(d, recorded_at="2026-01-05T03:25"),
                    {**wang(d), "head_sha": "a" * 40}, {k: v for k, v in wang(d).items() if k != "quote"}):
            self.rej(n, json.dumps(bad), valid_wang)


class HoldReject(T):
    def test_selfcheck_fail(self):
        self.expect(self.run_(TITLE + "- 作者声称方法优于所有基线。"), "HOLD", False, "E-REPLAY-001")

    def test_unclear(self):
        sc = sc_of(INFER); sc["status"] = "UNCLEAR"
        self.expect(self.run_(INFER, sc=sc), "HOLD", False, "E-ROUTE-UNCLEAR")
        self.expect(self.run_(INFER, sc=sc, st=state(mac_online=False)), "ARCHIVED", False, "A-MAC-OFFLINE")

    def test_internal_hard_reject(self):
        d = draft_of(TITLE + arxiv_line("样例内部词甲 MMLU 90%"))
        self.expect(self.run_(TITLE + arxiv_line("样例内部词甲 MMLU 90%"), rc=recs(d)), "REJECTED", False, "E-ROUTE-HARD-REJECT")

    def test_route_does_not_read_ledger(self):
        src = Path(R.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
        self.assertNotIn("ledger", src.lower())


class FromMain(unittest.TestCase):
    """从 git 仓库的 main 分支对象读取（不读工作树）。"""
    def setUp(self):
        import subprocess
        self.sp = subprocess
        self.repo = make_repo()
        import shutil; shutil.rmtree(self.repo / ".git")
        self.env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e")
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A"); self.git("commit", "-qm", "base", "--allow-empty"); self.git("tag", "base")
        (self.repo / "daily").mkdir(); self.draft = self.repo / "daily" / "2026-01-05-d1.md"
        self.draft.write_text(INFER + DISC, encoding="utf-8")   # r12：日报须带固定免责声明
        self.dr = {"content_sha256": hashlib.sha256((INFER + DISC).encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.cp = f"approvals/codex/{self.dr['content_sha256']}.json"
        self.wp = f"approvals/wang/{self.dr['content_sha256']}.json"
        self.commit("init")

    def git(self, *a):
        r = self.sp.run(["git", *a], cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); return r.stdout

    def write(self, rel, text):
        p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")

    def commit(self, msg):
        self.git("add", "-A"); self.git("commit", "-qm", msg, "--allow-empty")

    def route(self, now=NOW):
        # r11：发布入口一律走 route_pr（按 PR 文件清单配对）
        return self.route_pr_out(now)["daily/" + self.draft.name]

    def gh_meta(self, files=None, state="OPEN"):
        if self.infra_on_base:
            self.split_infra()
        base = self.git("rev-parse", "base").strip(); head = self.git("rev-parse", "HEAD").strip()
        if files is None:
            files = [{"path": p} for p in self.git("diff", "--name-only", f"{base}...{head}").split()]
        return {"baseRefOid": base, "headRefOid": head, "state": state, "files": files}

    infra_on_base = True    # r7 B4：批准记录、状态等非稿件文件放到 base（main 上已有），PR 只含稿件与 raw/

    def split_infra(self):
        """把 base...HEAD 中稿件与 raw/<日期>/ 以外的改动挪进一个新的 base 提交，HEAD 改为其上的同树提交。
        模拟真实情形：approvals/、state/ 等由各自的 PR 先合并进 main，稿件 PR 只改稿件和数据证据。"""
        base = self.git("rev-parse", "base").strip(); head = self.git("rev-parse", "HEAD").strip()
        changed = self.git("diff", "--name-only", "--no-renames", f"{base}...{head}").split()
        infra = [p for p in changed if not (R.PR_DATA_RE.fullmatch(p) or (len(p.split("/")) == 2 and p.endswith(".md")
                                                                      and p.split("/")[0] not in R.RESERVED_DIRS))]
        if not infra:
            return
        env = dict(self.env, GIT_INDEX_FILE=str(self.repo / ".git" / "tmp-index"))
        run = lambda *a: self.sp.run(["git", *a], cwd=self.repo, env=env, capture_output=True, text=True, check=True).stdout
        drafty = [p for p in changed if p not in infra]
        prev = base
        # 逐个重放 base..HEAD 的提交（保留批准记录的增删改历史），只把稿件与 raw/ 的路径还原为 base 版本
        for c in run("rev-list", "--reverse", "--first-parent", f"{base}..{head}").split():
            run("read-tree", c)
            for p in drafty:
                ls = run("ls-tree", base, "--", p).split()
                if ls:
                    run("update-index", "--add", "--cacheinfo", f"{ls[0]},{ls[2]},{p}")
                else:
                    run("update-index", "--force-remove", "--", p)
            prev = run("commit-tree", run("write-tree").strip(), "-p", prev, "-m", "infra on main").strip()
        nh = run("commit-tree", head + "^{tree}", "-p", prev, "-m", "draft PR").strip()
        self.git("update-ref", "HEAD", nh); self.git("tag", "-f", "base", prev)
        (self.repo / ".git" / "tmp-index").unlink(missing_ok=True)

    def route_pr_out(self, now=NOW, meta=None):
        if self.infra_on_base and meta is None:
            self.split_infra()
        o1, o2 = R._gh_pr, R.APPROVALS_REF
        o3 = R._real_now
        R._gh_pr = lambda repo, n: meta or self.gh_meta(); R.APPROVALS_REF = "main"   # 测试仓库没有 origin
        o4 = R._http_probe
        R._real_now = lambda: now                                                    # 整体验收 r2：时间只能 monkeypatch 真实时钟
        R._http_probe = lambda u, timeout=10: (True, None)                          # 链接只能 monkeypatch 内置检查
        try:
            return R.route_pr(self.repo, 21, DATE, "daily")
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    def one(self, rel, data=None, ct="daily", ref="main", now=NOW, date=DATE):
        data = data if data is not None else (self.repo / rel).read_bytes()
        o = R.APPROVALS_REF; R.APPROVALS_REF = ref
        try:
            return R._route_one(rel, data, self.repo, date, ct, now, link_checker=lambda u: True)
        finally:
            R.APPROVALS_REF = o

    def setup_ok(self):
        self.write("state/publish-state.json", json.dumps(state()))
        self.write(self.cp, json.dumps(codex(self.dr)))
        self.write(self.wp, json.dumps(wang(self.dr)))
        self.commit("ok")

    def expect(self, res, st, code=None):
        sc, d = res
        self.assertEqual(d.state, st, d.codes); self.assertFalse(compute_low_risk(sc))
        if code: self.assertIn(code, d.codes)

    def test_state_missing(self):
        self.expect(self.route(), "HOLD", "E-ROUTE-STATE")

    def test_state_corrupt(self):
        self.write("state/publish-state.json", "{oops"); self.commit("bad")
        self.expect(self.route(), "HOLD", "E-ROUTE-STATE")

    def test_bad_ref(self):
        self.setup_ok()
        sc, d = self.one("daily/" + self.draft.name, ref="nope")
        self.assertEqual(d.state, "HOLD"); self.assertIn("E-ROUTE-STATE", d.codes); self.assertFalse(compute_low_risk(sc))

    def test_approved_from_main(self):
        self.setup_ok(); self.expect(self.route(), "APPROVED")

    def test_worktree_ignored(self):
        self.write("state/publish-state.json", json.dumps(state()))
        self.commit("state")
        self.write(self.cp, json.dumps(codex(self.dr)))   # 未提交
        self.write(self.wp, json.dumps(wang(self.dr)))
        self.expect(self.route(), "NEEDS_REVIEW", "E-ROUTE-NO-CODEX")

    def test_other_branch_ignored(self):
        self.write("state/publish-state.json", json.dumps(state())); self.commit("state")
        self.git("checkout", "-q", "-b", "feature")
        self.write(self.cp, json.dumps(codex(self.dr)))
        self.write(self.wp, json.dumps(wang(self.dr))); self.commit("forge")
        self.expect(self.route(), "NEEDS_REVIEW", "E-ROUTE-NO-CODEX")

    def test_invalid_line(self):
        self.setup_ok()
        self.write("approvals/wang/" + "0" * 64 + ".json", '{"content_sha256": "x"}'); self.commit("bad")
        self.expect(self.route(), "HOLD", "E-ROUTE-RECORD-INVALID")

    def test_rewrite_rejected(self):
        self.setup_ok()
        self.write(self.cp, json.dumps(codex(self.dr, log_path="x.log"))); self.commit("modify")
        self.expect(self.route(), "HOLD", "E-ROUTE-APPROVALS-REWRITTEN")

    def test_delete_then_readd_rejected(self):
        self.setup_ok()
        (self.repo / self.wp).unlink(); self.commit("delete")
        self.write(self.wp, json.dumps(wang(self.dr))); self.commit("readd")
        self.expect(self.route(), "HOLD", "E-ROUTE-APPROVALS-REWRITTEN")

    def test_audit_script(self):
        self.setup_ok()
        aud = Path(R.__file__).resolve().parents[1] / "audit-approvals.py"
        r = self.sp.run(["python3", str(aud), "--repo", str(self.repo), "--ref", "main"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.write(self.cp, json.dumps(codex(self.dr, verdict="REJECTED"))); self.commit("modify")
        r = self.sp.run(["python3", str(aud), "--repo", str(self.repo), "--ref", "main"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("E-ROUTE-APPROVALS-REWRITTEN", r.stdout)
        self.assertFalse(compute_low_risk(sc_of(INFER)))

    def test_archive_irreversible(self):
        ar = {"status": "archived", "reason": "A-MAC-OFFLINE", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}
        self.write("state/publish-state.json", json.dumps(state(drafts={"daily-2026-01-05-d1": ar}))); self.commit("ar")
        self.expect(self.route(), "ARCHIVED", "E-ROUTE-ARCHIVED-REUSE")
        self.write("state/publish-state.json", json.dumps(state())); self.commit("revert")
        self.expect(self.route(), "HOLD", "E-ROUTE-STATE")

    def test_mac_offline_archives_not_defers(self):
        self.write("state/publish-state.json", json.dumps(state(mac_online=False, wang_present=False))); self.commit("off")
        sc, d = self.route()
        self.expect((sc, d), "ARCHIVED", "A-MAC-OFFLINE"); self.assertEqual(d.state_change["kind"], "draft")
        self.expect(self.route(now=EOD), "DEFERRED", "E-ROUTE-PUBLISH-LATE")   # 07:00 首次逾期：一律顺延

    def test_cli_has_no_self_reported_approval(self):
        cli = (Path(R.__file__).resolve().parents[1] / "route.py").read_text(encoding="utf-8")
        for f in ("--approver", "--codex-reviewed", "--mac-offline", "--archived", "--deferred"):
            self.assertNotIn(f, cli)


class DraftId(unittest.TestCase):
    def test_rule(self):
        repo = Path(tempfile.mkdtemp())
        ok = {"daily/2026-10-11.md": "daily-2026-10-11", "digest/2026-10-10.md": "digest-2026-10-10",
              "cards/2026-10-11-c03.md": "cards-2026-10-11-c03"}
        for rel, did in ok.items():
            self.assertEqual(R.draft_id_for(repo, repo / rel), did)
        for rel in ("2026-10-11.md", "daily/sub/2026-10-11.md", "Daily/2026-10-11.md", "daily/2026_10_11.md",
                    "daily/2026-10-11.txt", "daily/-x.md", "daily/" + "a" * 70 + ".md", "../daily/x.md"):
            self.assertIsNone(R.draft_id_for(repo, repo / rel), rel)
        self.assertIsNone(R.draft_id_for(repo, "/etc/daily/x.md"))

    def test_bad_path_holds(self):
        p = Path(tempfile.mkdtemp()) / "x.md"; p.write_text(INFER, encoding="utf-8")
        sc, d = R._route_one("x.md", INFER.encode(), REPO, DATE, "daily", NOW, link_checker=lambda u: True)
        self.assertEqual((d.state, d.codes), ("HOLD", ["E-ROUTE-DRAFT-PATH"])); self.assertIsNone(sc)
        self.assertFalse(d.publishable)


class StateChange(unittest.TestCase):
    """写回接口。断言 status（接受/拒绝）、low_risk（不适用，恒 False）与错误码。"""
    def setUp(self):
        from markjin import statechange as S
        self.S = S

    def rej(self, st, ch, code):
        with self.assertRaises(self.S.StateChangeError) as cm:
            self.S.apply_change(st, ch)
        self.assertEqual(cm.exception.code, code)

    def test_decision_emits_change_and_apply(self):
        sc, d = T.run_(T(), INFER, st=state(mac_online=False))
        self.assertEqual(d.state, "ARCHIVED"); self.assertFalse(compute_low_risk(sc))
        new = self.S.apply_change(state(), d.state_change)
        self.assertEqual(new["drafts"]["2026-01-05-d1"]["status"], "archived")
        self.assertEqual({k: new[k] for k in ("mac_online", "updated_at")}, {k: state()[k] for k in ("mac_online", "updated_at")})
        # 已归档再写任何变更 → 拒绝
        self.rej(new, self.S.draft_change(draft_of(INFER), "deferred", "I-DEFERRED", NOW), "E-ROUTE-ARCHIVED-REUSE")
        sc, d2 = T.run_(T(), INFER, st=new)
        self.assertEqual(d2.state, "ARCHIVED"); self.assertIsNone(d2.state_change)

    def test_defer_once(self):
        ch = self.S.draft_change(draft_of(INFER), "deferred", "I-DEFERRED", NOW)
        new = self.S.apply_change(state(), ch)
        self.rej(new, ch, "E-STATE-CHANGE-INVALID")

    def test_no_change_for_publishable_or_hold(self):
        for text, st in ((CLEAN, state()), (INFER, state(updated_at=(NOW - dt.timedelta(hours=1)).isoformat()))):
            sc, d = T.run_(T(), text, st=st)
            self.assertIsNone(d.state_change); self.assertIn(d.state, ("NEEDS_REVIEW", "HOLD"))

    def test_heartbeat_only_two_fields(self):
        st = state(drafts={"x": {"status": "deferred", "reason": "I-DEFERRED", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}})
        hb = self.S.heartbeat(False, NOW)
        new = self.S.apply_change(st, hb)
        self.assertEqual(new["mac_online"], False); self.assertEqual(new["updated_at"], NOW.isoformat())
        self.assertEqual({k: v for k, v in new.items() if k not in ("mac_online", "updated_at")},
                         {k: v for k, v in st.items() if k not in ("mac_online", "updated_at")})
        self.rej(new, self.S.heartbeat(True, NOW - dt.timedelta(minutes=1)), "E-STATE-CHANGE-STALE")

    def test_invalid_changes(self):
        hb = self.S.heartbeat(True, NOW)
        dc = self.S.draft_change(draft_of(INFER), "archived", "A-MAC-OFFLINE", NOW)
        for bad in ({**hb, "mac_online": None}, {**hb, "mac_online": "true"}, {**hb, "updated_at": "2026-01-05T03:25"},
                    {**hb, "wang_present": True}, {**hb, "schema": "v0"}, {**dc, "reason": "I-DEFERRED"},
                    {**dc, "status": "published"}, {**dc, "draft_id": "含 空格"}, {k: v for k, v in dc.items() if k != "at"},
                    {**dc, "kind": "other"}, None):
            self.rej(state(), bad, "E-STATE-CHANGE-INVALID")

    def test_cli_heartbeat(self):
        import subprocess
        d = Path(tempfile.mkdtemp()); p = d / "publish-state.json"
        p.write_text(json.dumps(state()), encoding="utf-8")
        cli = Path(R.__file__).resolve().parents[1] / "state-change.py"
        r = subprocess.run(["python3", str(cli), "heartbeat", "--state", str(p), "--mac-online", "false",
                            "--now", NOW.isoformat()], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        new = json.loads(p.read_text()); self.assertFalse(new["mac_online"]); self.assertEqual(new["updated_at"], NOW.isoformat())
        r = subprocess.run(["python3", str(cli), "heartbeat", "--state", str(p), "--mac-online", "true",
                            "--now", (NOW - dt.timedelta(hours=1)).isoformat()], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("E-STATE-CHANGE-STALE", r.stdout)
        self.assertFalse(json.loads(p.read_text())["mac_online"])


if __name__ == "__main__":
    unittest.main()


class R3Fixes(T):
    """r3 审查意见的反例（每例同时断言 状态、low_risk、错误码）。"""
    def wang_at(self, hh, mm, **kw):
        d = draft_of(INFER)
        return {"codex": [codex(d)], "wang": [wang(d, recorded_at=dt.datetime(2026, 1, 5, hh, mm, tzinfo=SGT).isoformat(), **kw)],
                "error": None}

    def test_wang_after_0655_not_accepted(self):
        now = dt.datetime(2026, 1, 5, 6, 57, 30, tzinfo=SGT)
        st = state(updated_at=(now - dt.timedelta(minutes=1)).isoformat())
        self.expect(self.run_s(INFER, rc=self.wang_at(6, 56), now=now, st=st), "DEFERRED", False, "E-ROUTE-RECORD-LATE")
        self.expect(self.run_s(INFER, rc=self.wang_at(6, 54), now=now, st=st), "APPROVED", False)

    def test_publish_deadline_0700(self):
        for hh, mm, exp in ((6, 59, "APPROVED"), (7, 1, "DEFERRED")):
            now = dt.datetime(2026, 1, 5, hh, mm, tzinfo=SGT)
            st = state(updated_at=(now - dt.timedelta(minutes=1)).isoformat())
            sc, d = self.run_(INFER, rc=self.wang_at(6, 25), now=now, st=st)
            self.expect((sc, d), exp, False, None if exp == "APPROVED" else "E-ROUTE-PUBLISH-LATE")
            self.assertEqual(d.publishable, exp == "APPROVED")

    def test_deferred_same_day_hold(self):
        df = {"status": "deferred", "reason": "I-DEFERRED", "at": NOW.isoformat(), "date": DATE, "content_sha256": draft_of(INFER)["content_sha256"]}
        sc, d = self.run_(INFER, st=state(wang_present=False, drafts={"2026-01-05-d1": df}))
        self.expect((sc, d), "HOLD", False, "E-ROUTE-DEFERRED-SAMEDAY"); self.assertIsNone(d.state_change)

    def test_strict_int_versions(self):
        self.expect(self.run_(CLEAN, st=state(version=True)), "HOLD", True, "E-ROUTE-STATE")
        self.expect(self.run_(CLEAN, st=state(version=1.0)), "HOLD", True, "E-ROUTE-STATE")
        from markjin.approvals import valid_wang
        d = draft_of(INFER)
        v2 = {**wang(d), "schema_version": 2, "draft_id": d["draft_id"], "quote_ref": "x:1"}
        self.assertTrue(valid_wang(v2))
        self.assertFalse(valid_wang({**v2, "schema_version": 2.0}))
        self.assertFalse(valid_wang({**v2, "schema_version": True}))

    def test_duplicate_keys_rejected(self):
        from markjin.approvals import parse_record, valid_codex, ApprovalsError
        d = draft_of(INFER); sha = d["content_sha256"]
        good = json.dumps(codex(d))
        self.assertEqual(parse_record(f"{sha}.json", good, valid_codex)["verdict"], "APPROVED")
        dup = good.replace('"verdict": "APPROVED"', '"verdict": "REJECTED", "verdict": "APPROVED"')
        with self.assertRaises(ApprovalsError) as e:
            parse_record(f"{sha}.json", dup, valid_codex)
        self.assertEqual(e.exception.code, "E-ROUTE-RECORD-INVALID")

    def test_non_main_ref_refused(self):
        from markjin.approvals import load_from_ref
        for ref in ("feature", "origin/feature", "HEAD", "main~1"):
            st, rc = load_from_ref(REPO, ref)
            self.assertIsNone(st)
            self.expect(self.run_(INFER, st=st, rc=rc), "HOLD", False, "E-ROUTE-STATE")

    def test_cli_ref_choices(self):
        import subprocess, sys
        cli = Path(__file__).resolve().parents[1] / "scripts" / "route.py"
        # r13：不再接受 --ref（记录只读 origin/main），也不接受稿件路径；只收 --pr 编号
        for extra in (["--pr", "1", "--ref", "main"], ["x.md", "--pr", "1"], ["--pr", "abc"], []):
            r = subprocess.run([sys.executable, str(cli), "--repo", ".", "--date", DATE, "--card-type", "daily", *extra],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, extra)

    def test_git_failure_not_skipped(self):
        from markjin import approvals as AP
        real = AP._git
        class Fail:
            returncode, stdout, stderr = 1, b"", b""
        def fake(repo, *args):
            if args[:2] == ("rev-list", "--parents"):
                return Fail()
            if args[0] == "rev-list":
                class OK: returncode, stdout = 0, b"abc\n"
                return OK()
            return real(repo, *args)
        AP._git = fake
        try:
            with self.assertRaises(AP.ApprovalsError) as e:
                AP.check_history(REPO, "main")
            self.assertEqual(e.exception.code, "E-ROUTE-STATE")
        finally:
            AP._git = real

    def test_apply_change_rejects_invalid_old_state(self):
        from markjin.statechange import apply_change, heartbeat, StateChangeError
        hb = heartbeat(True, NOW)
        self.assertEqual(apply_change(state(), hb)["updated_at"], NOW.isoformat())
        for bad in ({k: v for k, v in state().items() if k != "updated_at"}, state(updated_at="bad"), state(version=True)):
            with self.assertRaises(StateChangeError) as e:
                apply_change(bad, hb)
            self.assertEqual(e.exception.code, "E-ROUTE-STATE")


class R4Binding(T):
    """r4：draft_id 绑定、改名不复活、quote 内部清单扫描、卡片 cards- 前缀。"""
    def test_cross_path_replay_rejected(self):
        d = draft_of(INFER)                       # 批准记录绑定 2026-01-05-d1
        other = draft_of(INFER, did="daily-2026-01-05-copy")
        self.expect(self.run_(INFER, draft=other, rc=recs(d)), "NEEDS_REVIEW", False, "E-ROUTE-RECORD-MISMATCH")
        self.expect(self.run_(INFER, rc=recs(d)), "APPROVED", False)

    def test_v2_draft_id_must_match(self):
        d = draft_of(INFER)
        v2 = dict(wang(d, channel="direct"), schema_version=2, draft_id="daily-other", quote_ref="coord-bot:msg/1")
        self.expect(self.run_s(INFER, rc=recs(d) | {"wang": [v2]}), "NEEDS_REVIEW", False, "E-ROUTE-RECORD-MISMATCH")
        from markjin.approvals import valid_wang, valid_codex
        self.assertFalse(valid_wang({k: v for k, v in v2.items() if k != "draft_id"}))
        self.assertFalse(valid_codex({k: v for k, v in codex(d).items() if k != "draft_id"}))
        self.assertFalse(valid_codex(dict(codex(d), draft_id="含 空格")))

    def test_archived_renamed_not_revived(self):
        d = draft_of(INFER)
        ar = {"status": "archived", "reason": "A-MAC-OFFLINE", "at": NOW.isoformat(), "date": DATE,
              "content_sha256": d["content_sha256"]}
        renamed = draft_of(INFER, did="daily-2026-01-05-renamed")
        sc, res = self.run_(INFER, draft=renamed, st=state(drafts={"2026-01-05-d1": ar}),
                            rc=recs(renamed))
        self.expect((sc, res), "ARCHIVED", False, "E-ROUTE-ARCHIVED-REUSE"); self.assertIsNone(res.state_change)

    def test_state_entry_requires_sha(self):
        ar = {"status": "archived", "reason": "A-MAC-OFFLINE", "at": NOW.isoformat(), "date": DATE}
        self.expect(self.run_(CLEAN, st=state(drafts={"2026-01-05-d1": ar})), "HOLD", True, "E-ROUTE-STATE")

    def test_state_change_carries_sha(self):
        from markjin.statechange import apply_change
        sc, d = self.run_(INFER, st=state(mac_online=False))
        new = apply_change(state(), d.state_change)
        self.assertEqual(new["drafts"]["2026-01-05-d1"]["content_sha256"], draft_of(INFER)["content_sha256"])

    def test_quote_internal_scan(self):
        from markjin.approvals import scan_internal, ApprovalsError
        d = draft_of(INFER)
        scan_internal([codex(d), wang(d)], DUMMY_INTERNAL)
        for bad in (wang(d, quote="同意，" + DUMMY_INTERNAL[0]), codex(d, log_path="review/" + "x" + DUMMY_INTERNAL[1])):
            with self.assertRaises(ApprovalsError) as e:
                scan_internal([bad], DUMMY_INTERNAL)
            self.assertEqual(e.exception.code, "E-ROUTE-RECORD-INTERNAL")
        with self.assertRaises(ApprovalsError) as e:
            scan_internal([wang(d)], None)
        self.assertEqual(e.exception.code, "E-INTERNAL-LIST-MISSING")
        rc = {"codex": [], "wang": [], "error": "E-ROUTE-RECORD-INTERNAL"}
        self.expect(self.run_(INFER, rc=rc), "HOLD", False, "E-ROUTE-RECORD-INTERNAL")


class R4Cards(FromMain):
    def test_cards_prefix(self):
        self.setup_ok()
        for rel, ct, ok in (("cards/2026-01-05-c1.md", "signal", True), ("signal/2026-01-05-c1.md", "signal", False),
                            ("cards/2026-01-05-c1.md", "daily", False), ("daily/2026-01-05-c1.md", "signal", False)):
            p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(CLEAN, encoding="utf-8")
            sc, d = self.one(rel, ct=ct)
            if ok:
                self.assertNotIn("E-ROUTE-DRAFT-PATH", d.codes)
            else:
                self.assertEqual((d.state, d.codes, d.publishable), ("HOLD", ["E-ROUTE-DRAFT-PATH"], False))


class R5(T):
    """协调决定 (2)：07:00 首次逾期一律顺延（含低风险）；顺延稿次日按次日计算截止；Codex 完成时间；channel 类型；目录读取失败。"""
    D2 = dt.datetime(2026, 1, 6, 3, 25, tzinfo=SGT)

    def deferred(self, text=INFER):
        return {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE,
                "content_sha256": draft_of(text)["content_sha256"]}

    def st2(self, text=INFER, at=None, **kw):
        return state(updated_at=(at or self.D2).isoformat(), drafts={"2026-01-05-d1": self.deferred(text)}, **kw)

    def test_low_risk_overdue_defers(self):
        sc, d = self.run_(CLEAN, now=EOD)
        self.expect((sc, d), "DEFERRED", True, "E-ROUTE-PUBLISH-LATE")
        self.assertEqual(d.state_change["to"]["status"] if "to" in d.state_change else d.state_change["status"], "deferred")
        sc, d = self.run_(CLEAN, now=EOD - dt.timedelta(minutes=1))
        self.assertFalse(d.publishable); self.assertNotEqual(d.state, "AUTO_APPROVED")
        # t161u：顺延的低风险稿次日也须 Codex 批准；无批准二次逾期 → A-NOT-APPROVED
        sc, d = self.run_(CLEAN, st=self.st2(CLEAN), now=self.D2)
        self.assertFalse(d.publishable); self.assertNotEqual(d.state, "AUTO_APPROVED")
        r = self.run_(CLEAN, st=self.st2(CLEAN), now=EOD + dt.timedelta(days=1))
        self.expect(r, "ARCHIVED", True, "A-NOT-APPROVED")

    def test_deferred_next_day_approval_dates(self):
        d = draft_of(INFER)
        # r7 HIGH：顺延到第二天后，前一天的 Codex 记录作废 → 不可发布（须按可发布日重新审查）
        old = codex(d, reviewed_at="2026-01-05T06:25:00+08:00")
        w2 = dict(wang(d, recorded_at="2026-01-06T02:55:00+08:00"), _for_date="2026-01-06")   # r13：<sha>.<D>.json
        r = self.run_s(INFER, st=self.st2(), rc={"codex": [old], "wang": [w2], "error": None}, now=self.D2)
        self.assertFalse(r[1].publishable); self.assertIn("E-ROUTE-NO-CODEX", r[1].codes)   # r12：D 日只认 <sha>.<D>.json
        cx = dict(codex(d, reviewed_at="2026-01-06T02:25:00+08:00"), _for_date="2026-01-06")   # r12：<sha>.2026-01-06.json
        rc = {"codex": [old, cx], "wang": [w2], "error": None}
        self.expect(self.run_s(INFER, st=self.st2(), rc=rc, now=self.D2), "APPROVED", False)
        # 次日 06:55 后的王总记录 → 不采信；次日 07:00 后 → 归档（不再按稿件日期算截止）
        late = rc | {"wang": [dict(wang(d, recorded_at="2026-01-06T06:55:10+08:00"), _for_date="2026-01-06")]}
        t = dt.datetime(2026, 1, 6, 6, 56, 40, tzinfo=SGT)
        self.expect(self.run_s(INFER, st=self.st2(at=t), rc=late, now=t),
                    "ARCHIVED", False, "E-ROUTE-RECORD-LATE")
        self.expect(self.run_s(INFER, st=self.st2(), rc=rc, now=EOD + dt.timedelta(days=1)), "ARCHIVED", False, "E-ROUTE-PUBLISH-LATE")
        # r8：需审查顺延稿，次日 07:00 时已有有效批准但未发布 → A-OVERDUE-TWICE；无批准 → A-NOT-APPROVED
        t14 = dt.datetime(2026, 1, 6, 7, 1, tzinfo=SGT)
        ok = self.run_s(INFER, st=self.st2(at=t14), rc=rc, now=t14)
        self.expect(ok, "ARCHIVED", False, "A-OVERDUE-TWICE"); self.assertNotIn("A-NOT-APPROVED", ok[1].codes)
        no = self.run_s(INFER, st=self.st2(at=t14), rc=recs(d, c=False, w=False), now=t14)
        self.expect(no, "ARCHIVED", False, "A-NOT-APPROVED"); self.assertNotIn("A-OVERDUE-TWICE", no[1].codes)
        self.assertEqual(no[1].state_change["to"]["reason"] if "to" in no[1].state_change else no[1].state_change["reason"], "A-NOT-APPROVED")
        self.assertEqual(ok[1].state_change["to"]["reason"] if "to" in ok[1].state_change else ok[1].state_change["reason"], "A-OVERDUE-TWICE")
        # 前一天（顺延当天）的王总记录不能在次日复用
        old = rc | {"wang": [wang(d, recorded_at="2026-01-05T02:55:00+08:00")]}
        self.expect(self.run_s(INFER, st=self.st2(), rc=old, now=self.D2), "NEEDS_REVIEW", False, "E-ROUTE-NO-WANG")   # r13：D 日只认 <sha>.<D>.json

    def test_codex_reviewed_at(self):
        d = draft_of(INFER)
        for ts, code in (("2026-01-05T03:55:00+08:00", "E-ROUTE-RECORD-EXPIRED"),   # 晚于当前时间
                         ("2026-01-04T23:00:00+08:00", "E-ROUTE-RECORD-EXPIRED"),   # 早于稿件日期
                         ("2026-01-05T06:55:10+08:00", "E-ROUTE-RECORD-LATE")):
            now = NOW if code.endswith("EXPIRED") else dt.datetime(2026, 1, 5, 6, 57, 30, tzinfo=SGT)
            rc = {"codex": [codex(d, reviewed_at=ts)], "wang": [wang(d)], "error": None}
            r = self.run_(INFER, rc=rc, now=now, st=state(updated_at=now.isoformat()))
            self.assertIn(code, r[1].codes, ts); self.assertFalse(r[1].publishable)
        from markjin.approvals import valid_codex
        for bad in ("2026-01-05T02:25:00", "x", 1, None):
            self.assertFalse(valid_codex(codex(d, reviewed_at=bad)), bad)
        self.assertFalse(valid_codex({k: v for k, v in codex(d).items() if k != "reviewed_at"}))
        self.assertFalse(valid_codex(codex(d, verdict=["APPROVED"])))

    def test_channel_type(self):
        from markjin.approvals import valid_wang
        d = draft_of(INFER)
        self.assertTrue(valid_wang(wang(d)))
        for bad in (["direct"], {"direct": 1}, 1, None, "DIRECT"):
            self.assertFalse(valid_wang(wang(d, channel=bad)), bad)   # 不可哈希类型也不抛异常

    def test_approvals_dir_read_failure_holds(self):
        from unittest import mock
        from markjin import approvals as A
        repo = make_repo()
        sp = __import__("subprocess")
        sp.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo, check=True)
        self.assertEqual(A.load_dir(repo, "main", A.CODEX_DIR, A.valid_codex), [])   # 目录确实不存在 → 空
        with self.assertRaises(A.ApprovalsError) as e:
            A.load_dir(repo, "nosuchref", A.CODEX_DIR, A.valid_codex)                # ref 读不出 → 报错
        self.assertEqual(e.exception.code, "E-ROUTE-STATE")
        real = A._git
        def flaky(r, *args):
            if args[:1] == ("ls-tree",):
                return sp.CompletedProcess(args, 128, b"", b"")
            return real(r, *args)
        with mock.patch.object(A, "_git", flaky):
            with self.assertRaises(A.ApprovalsError):
                A.load_dir(repo, "main", A.CODEX_DIR, A.valid_codex)                 # ls-tree 失败 → 不得返回空


class R6Route(T):
    def test_records_error_holds_before_auto(self):
        for e in ("E-ROUTE-RECORD-INVALID", "E-ROUTE-APPROVALS-REWRITTEN", "E-INTERNAL-LIST-MISSING"):
            self.expect(self.run_(CLEAN, rc={"codex": [], "wang": [], "error": e}), "HOLD", True, e)

    def test_wang_not_before_codex(self):
        d = draft_of(INFER)
        rc = {"codex": [codex(d, reviewed_at="2026-01-05T02:45:00+08:00")], "wang": [wang(d, recorded_at="2026-01-05T02:35:00+08:00")], "error": None}
        self.expect(self.run_s(INFER, rc=rc), "NEEDS_REVIEW", False, "E-ROUTE-RECORD-ORDER")
        eq = rc | {"wang": [wang(d, recorded_at="2026-01-05T02:45:00+08:00")]}
        self.expect(self.run_s(INFER, rc=eq), "APPROVED", False)

    def test_future_dated_not_early(self):
        early = NOW - dt.timedelta(days=1)
        self.expect(self.run_(CLEAN, now=early, st=state(updated_at=early.isoformat())), "HOLD", True, "E-ROUTE-NOT-YET")
        self.expect(self.run_(INFER, now=early, st=state(updated_at=early.isoformat())), "HOLD", False, "E-ROUTE-NOT-YET")

    def test_mac_offline_priority_over_0700(self):
        for now in (NOW, EOD, EOD + dt.timedelta(minutes=30)):
            st = state(updated_at=now.isoformat(), mac_online=False)
            self.expect(self.run_(INFER, now=now, st=st), "ARCHIVED", False, "A-MAC-OFFLINE")
            # t161u：低风险稿同样须 Codex，离线一律归档
            self.expect(self.run_(CLEAN, now=now, st=st), "ARCHIVED", True, "A-MAC-OFFLINE")
        # 心跳过期：07:00 前 HOLD（可重试），07:00 后按“其余情况一律顺延”顺延，均不归档；在线：07:00 后顺延
        stale = state(updated_at=(EOD - dt.timedelta(minutes=31)).isoformat(), mac_online=False)
        stale2 = state(updated_at=(EOD - dt.timedelta(minutes=40)).isoformat(), mac_online=False)
        self.expect(self.run_(INFER, now=EOD - dt.timedelta(minutes=1), st=stale2), "HOLD", False, "E-ROUTE-MAC-STALE")
        self.expect(self.run_(INFER, now=EOD, st=stale), "DEFERRED", False, "E-ROUTE-PUBLISH-LATE")
        self.expect(self.run_(INFER, now=EOD, st=state(updated_at=EOD.isoformat())), "DEFERRED", False, "E-ROUTE-PUBLISH-LATE")


class R8Route(T):
    N2 = NOW + dt.timedelta(days=1)

    def deferred(self, text, **kw):
        return dict({"status": "deferred", "reason": "I-DEFERRED", "at": NOW.isoformat(), "date": DATE,
                     "content_sha256": draft_of(text)["content_sha256"]}, **kw)

    def test_deferral_bound_to_sha_and_date(self):
        st = lambda ds: state(updated_at=(self.N2 - dt.timedelta(minutes=5)).isoformat(), drafts={"2026-01-05-d1": ds})
        # 顺延记录换了内容（sha 不同）→ HOLD，不得借用顺延日期
        self.expect(self.run_(CLEAN, now=self.N2, st=st(self.deferred(INFER))), "HOLD", True, "E-ROUTE-DEFER-MISMATCH")
        # 原日期不一致（例如把 1 月 4 日的顺延挪给 1 月 5 日稿）→ HOLD，不能借此绕过未来日期 HOLD
        self.expect(self.run_(CLEAN, now=NOW, st=state(drafts={"2026-01-05-d1": self.deferred(CLEAN, date="2026-01-04")})),
                    "HOLD", True, "E-ROUTE-DEFER-MISMATCH")
        # 正确绑定：次日照常
        sc, d = self.run_(CLEAN, now=self.N2, st=st(self.deferred(CLEAN)))
        self.assertNotIn("E-ROUTE-DEFER-MISMATCH", d.codes); self.assertFalse(d.publishable)   # t161u：仍须 Codex

    def tongyi_v2(self, d, **kw):
        return dict(wang(d, channel="direct"), schema_version=2, draft_id=d["draft_id"], quote_ref="coord-bot:msg/777", **kw)

    def test_tongyi_never_low_risk_and_v2_direct(self):
        d = draft_of(CLEAN, did="tongyi-01")
        # 结构白名单通过的纯直引稿：tongyi 仍不得自动批准
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d, c=False, w=False)), "NEEDS_REVIEW", True, "E-ROUTE-NO-CODEX")
        # v1 记录、v2 via-grok-bot 都不接受
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d) | {"wang": [wang_v1(d)]}), "NEEDS_REVIEW", True, "E-ROUTE-RECORD-V2-REQUIRED")
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d) | {"wang": [self.tongyi_v2(d, channel="via-grok-bot")]}),
                    "NEEDS_REVIEW", True, "E-ROUTE-RECORD-MISMATCH")
        # 逐篇：另一篇的 v2 批准不能用（sha/draft_id 都要对上）
        d2 = draft_of(CLEAN + "\n", did="tongyi-02")
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d) | {"wang": [self.tongyi_v2(d2)]}), "NEEDS_REVIEW", True, "E-ROUTE-NO-WANG")
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d) | {"wang": [dict(self.tongyi_v2(d), draft_id="tongyi-02")]}),
                    "NEEDS_REVIEW", True, "E-ROUTE-RECORD-MISMATCH")
        self.expect(self.run_(CLEAN, draft=d, rc=recs(d) | {"wang": [self.tongyi_v2(d)]}), "APPROVED", True)

    def test_tongyi_path(self):
        self.assertEqual(R.draft_id_for(REPO, Path(REPO) / "tongyi" / "01-intro.md"), "tongyi-01-intro")


class Schedule0700(unittest.TestCase):
    """王总 08:37 定（t130u）：07:00 发布；审查/批准上限 06:55。时间只在 route.CUTOFF / PUBLISH_DEADLINE 定义。"""
    def test_schedule_constants(self):
        from markjin import route
        self.assertEqual(route.CUTOFF, dt.time(6, 55))
        self.assertEqual(route.PUBLISH_DEADLINE, dt.time(7, 0))
        src = Path(route.__file__).read_text(encoding="utf-8")
        self.assertEqual(src.count("dt.time("), 2)          # 只在这两个常量里出现，其他地方不写死


class R10Bilingual(T):
    """t141u / t145u（经 Grok Bot 转达）：*.en.md 永不低风险；同一 PR 可放同 section、同 name 的中英两版，
    Codex 记录两条、reviewed_at 相同、pair_sha256 互相引用；任一不成立两版都不发布，且必须一起发布。"""
    ZH = CLEAN
    EN = CLEAN + "\n"

    def drafts(self):
        z = draft_of(self.ZH, "daily-2026-01-05"); e = draft_of(self.EN, "daily-2026-01-05-en")
        return z, e

    def pair_recs(self, z, e, zkw=None, ekw=None, w=True):
        cz = codex(z, **({"pair_sha256": e["content_sha256"]} | (zkw or {})))
        ce = codex(e, **({"pair_sha256": z["content_sha256"]} | (ekw or {})))
        return {"codex": [cz, ce], "wang": [wang(z), wang(e)] if w else [], "error": None}

    def dec(self, text, d, rc, pair):
        sc = sc_of(text)
        return sc, decide_(sc, d, state(), rc, NOW, pair)

    def test_draft_id(self):
        repo = Path(tempfile.mkdtemp())
        (repo / "daily").mkdir()
        for name, want in (("2026-10-11.md", "daily-2026-10-11"), ("2026-10-11.en.md", "daily-2026-10-11-en"),
                           ("2026-10-11-en.md", None), ("x.en.en.md", None)):
            p = repo / "daily" / name; p.write_text("x")
            self.assertEqual(R.draft_id_for(repo, p), want, name)

    def test_en_never_low_risk(self):
        z, e = self.drafts()
        sc, d = self.dec(self.EN, e, recs(), None)
        self.assertTrue(compute_low_risk(sc))           # 内容本身低风险
        self.assertEqual(d.state, "NEEDS_REVIEW"); self.assertIn("E-ROUTE-NO-CODEX", d.codes)
        self.assertFalse(d.publishable)

    def test_normal_pair_approved(self):
        z, e = self.drafts(); rc = self.pair_recs(z, e)
        for text, d, other in ((self.ZH, z, e), (self.EN, e, z)):
            sc, dd = self.dec(text, d, rc, other["content_sha256"])
            self.assertEqual(dd.state, "APPROVED", dd.codes); self.assertTrue(dd.publishable)

    def test_pair_zh_not_auto_approved(self):
        z, e = self.drafts()
        sc, d = self.dec(self.ZH, z, recs(), e["content_sha256"])
        self.assertEqual(d.state, "NEEDS_REVIEW"); self.assertFalse(d.publishable)

    def test_missing_half(self):
        z, e = self.drafts(); rc = self.pair_recs(z, e)
        rc["codex"] = [rc["codex"][0]]                  # 英文版 Codex 记录缺失
        _, d = self.dec(self.ZH, z, rc, e["content_sha256"])
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-PAIR-INCOMPLETE", d.codes)
        _, d = self.dec(self.EN, e, rc, z["content_sha256"])
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)
        rc = self.pair_recs(z, e, ekw={"verdict": "REJECTED"})
        _, d = self.dec(self.ZH, z, rc, e["content_sha256"])
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-PAIR-INCOMPLETE", d.codes)

    def test_pair_mismatch(self):
        z, e = self.drafts()
        rc = self.pair_recs(z, e, zkw={"pair_sha256": "0" * 64})
        for text, d, o in ((self.ZH, z, e), (self.EN, e, z)):
            _, dd = self.dec(text, d, rc, o["content_sha256"])
            self.assertFalse(dd.publishable); self.assertIn("E-ROUTE-PAIR-MISMATCH", dd.codes)
        # 单篇稿不得使用配对记录；配对稿不得使用无 pair_sha256 的记录
        zi = draft_of(INFER, "daily-2026-01-05")
        _, dd = self.dec(INFER, zi, self.pair_recs(zi, e), None)
        self.assertIn("E-ROUTE-PAIR-MISMATCH", dd.codes); self.assertFalse(dd.publishable)
        _, dd = self.dec(self.ZH, z, recs(z), e["content_sha256"])
        self.assertIn("E-ROUTE-PAIR-MISMATCH", dd.codes); self.assertFalse(dd.publishable)

    def test_reviewed_at_differs(self):
        z, e = self.drafts()
        rc = self.pair_recs(z, e, ekw={"reviewed_at": "2026-01-05T02:26:00+08:00"})
        for text, d, o in ((self.ZH, z, e), (self.EN, e, z)):
            _, dd = self.dec(text, d, rc, o["content_sha256"])
            self.assertFalse(dd.publishable); self.assertIn("E-ROUTE-PAIR-MISMATCH", dd.codes)

    def test_pair_sha_schema(self):
        from markjin.approvals import valid_codex
        z, e = self.drafts()
        self.assertTrue(valid_codex(codex(z, pair_sha256=e["content_sha256"])))
        self.assertFalse(valid_codex(codex(z, pair_sha256=z["content_sha256"])))   # 不得指向自身
        self.assertFalse(valid_codex(codex(z, pair_sha256="ABC")))

    def test_pr_file_combinations(self):
        self.assertEqual(R.pair_of(["daily/a.md"]), [("daily/a.md", None)])
        self.assertEqual(R.pair_of(["daily/a.en.md"]), "E-ROUTE-PAIR-MISSING")          # 缺一半
        self.assertEqual(len(R.pair_of(["daily/a.md", "daily/a.en.md"])), 2)            # 正常配对
        for bad in (["daily/a.md", "daily/b.en.md"],                                     # name 不同
                    ["daily/a.md", "cards/a.en.md"],                                     # section 不同
                    ["daily/a.md", "daily/b.md"], ["daily/a.en.md", "daily/b.en.md"],
                    ["daily/a.md", "daily/a.en.md", "daily/c.md"]):
            self.assertEqual(R.pair_of(bad), "E-ROUTE-PR-FILES", bad)

class R11Route(FromMain):
    """r11：一律走 route_pr；route_draft 直接调用不得自动批准/发布；section 不含 '-'，无 draft_id 碰撞。"""
    def test_no_public_route_draft(self):
        # r12 B-1：没有接收调用方文件列表的公开入口；route_pr 自己从 git diff 取清单
        self.assertFalse(hasattr(R, "route_draft"))
        import inspect
        self.assertNotIn("paths", inspect.signature(R.route_pr).parameters)
        self.setup_ok(); sc, d = self.route(); self.assertTrue(d.publishable, d.codes)

    def test_pr_files_from_git(self):
        self.setup_ok()
        en = self.draft.with_name(self.draft.name[:-3] + ".en.md"); en.write_text(CLEAN.replace(DISC, "\nThis article does not constitute investment advice.\n"), encoding="utf-8")
        self.write("docs/x.md", "doc"); self.commit("en")
        self.assertEqual(R.pr_draft_files(self.repo, "base", "HEAD")[0], ["daily/" + en.name, "daily/" + self.draft.name])
        out = self.route_pr_out()
        self.assertEqual(set(out), {"daily/" + en.name, "daily/" + self.draft.name})
        self.assertTrue(all(not d.publishable for _, d in out.values()))      # 无配对 Codex 记录 → 两版都不发布

    def test_daily_disclaimer_required(self):
        # r12 H-2：日报缺固定免责声明即拦；中英文各用自己的写法，互换或改写都不算
        self.setup_ok()
        EN = "\nThis article does not constitute investment advice.\n"
        for rel, text, ok in (("daily/x.md", INFER + DISC, True), ("daily/x.md", INFER, False),
                              ("daily/x.md", INFER + "\n本文不构成投资建议。\n", False), ("daily/x.md", INFER + EN, False),
                              ("daily/x.en.md", INFER + EN, True), ("daily/x.en.md", INFER + DISC, False),
                              ("daily/x.en.md", INFER + "\nThis is not investment advice.\n", False)):
            sc, d = self.one(rel, (text).encode(), date="2026-10-12")
            if ok:
                self.assertNotIn("E-ROUTE-DISCLAIMER-MISSING", d.codes, rel)
            else:
                self.assertEqual((d.state, d.codes, d.publishable), ("HOLD", ["E-ROUTE-DISCLAIMER-MISSING"], False), (rel, text))
        # r13：digest/ 同样要查；注释或代码块里的句子不算；2026-10-12 之前的历史稿不追溯
        EN = "\nThis article does not constitute investment advice.\n"
        for rel, text, date, ok in (("digest/x.md", INFER, "2026-10-12", False), ("digest/x.md", INFER + DISC, "2026-10-12", True),
                                    ("digest/x.md", INFER, "2026-10-11", True), ("daily/x.md", INFER, "2026-10-10", True),
                                    ("daily/x.md", INFER + "\n<!--\n本文不含投资建议。\n-->\n", "2026-10-12", False),
                                    ("daily/x.md", INFER + "\n<!-- 本文不含投资建议。", "2026-10-12", False),
                                    ("daily/x.md", INFER + "\n```\n本文不含投资建议。\n```\n", "2026-10-12", False),
                                    ("daily/x.en.md", INFER + "\n<!--" + EN + "-->\n", "2026-10-12", False),
                                    ("cards/x.md", INFER, "2026-10-12", True)):
            sc, d = self.one(rel, text.encode(), date=date, ct="signal" if rel.startswith("cards/") else "daily")
            self.assertEqual("E-ROUTE-DISCLAIMER-MISSING" in d.codes, not ok, (rel, date, text[-40:]))

    def test_daily_footer_only_from_2026_10_13(self):
        # 2026-10-16 王总／Grok Bot：2026-10-13 起日报只用站点页脚免责声明，正文没有固定免责声明不再拦
        self.setup_ok()
        EN = "\nThis article does not constitute investment advice.\n"
        for rel, text, date in (("daily/x.md", INFER, "2026-10-13"), ("daily/x.en.md", INFER, "2026-10-16"),
                                ("digest/x.md", INFER, "2026-10-13"), ("daily/x.md", INFER + DISC, "2026-10-16"),
                                ("daily/x.en.md", INFER + EN, "2026-10-13")):
            sc, d = self.one(rel, text.encode(), date=date)
            self.assertNotIn("E-ROUTE-DISCLAIMER-MISSING", d.codes, (rel, date))
        sc, d = self.one("daily/x.md", INFER.encode(), date="2026-10-12")      # 2026-10-12 仍按正文规则
        self.assertIn("E-ROUTE-DISCLAIMER-MISSING", d.codes)

    def test_disclaimer_required_matrix(self):
        corr = {"corrects": "daily-x"}
        for did, date, c, want in (("daily-x", "2026-10-11", None, False), ("daily-x", "2026-10-12", None, True),
                                   ("daily-x", "2026-10-13", None, False), ("digest-x", "2026-10-16", None, False),
                                   ("daily-x", "2026-01-05", corr, True), ("daily-x", "2026-10-12", corr, True),
                                   ("daily-x", "2026-10-13", corr, False), ("daily-x.en", "2026-10-16", corr, False),
                                   ("cards-x", "2026-10-12", corr, False), ("cards-x", "2026-10-12", None, False)):
            self.assertEqual(R.disclaimer_required(did, date, c), want, (did, date, c))

    def test_route_pr_requires_pr_number_and_open(self):
        self.setup_ok()
        for bad in ("21", None, 0, -1, True):
            with self.assertRaises(ValueError):
                R.route_pr(self.repo, bad, DATE, "daily")
        with self.assertRaises(ValueError):
            self.route_pr_out(meta=self.gh_meta(state="CLOSED"))
        with self.assertRaises(ValueError):
            self.route_pr_out(meta=dict(self.gh_meta(), headRefOid="HEAD"))
        with self.assertRaises(RuntimeError):                        # head 本地不存在（未 fetch / 伪造）
            self.route_pr_out(meta=dict(self.gh_meta(), headRefOid="1" * 40))

    def test_route_pr_gh_files_must_match_git(self):
        self.setup_ok()
        m = self.gh_meta()
        with self.assertRaises(ValueError):                          # gh 少列一个文件
            self.route_pr_out(meta=dict(m, files=m["files"][1:]))
        with self.assertRaises(ValueError):                          # gh 多列一个文件
            self.route_pr_out(meta=dict(m, files=m["files"] + [{"path": "daily/zz.en.md"}]))

    def test_route_pr_delete_or_rename_fails(self):
        self.infra_on_base = False                  # 本例就是要让删除/改名留在 PR 里
        self.setup_ok()
        self.write("docs/old.md", "x"); self.commit("x"); self.git("tag", "-f", "base")
        self.git("rm", "-q", "docs/old.md"); self.commit("del")
        with self.assertRaises(ValueError):
            self.route_pr_out()
        self.git("reset", "-q", "--hard", "base")
        self.git("mv", "docs/old.md", "docs/new.md"); self.commit("mv")
        with self.assertRaises(ValueError):
            self.route_pr_out()

    def test_route_pr_empty_raises(self):
        self.setup_ok(); self.git("tag", "-f", "base"); self.write("docs/x.md", "doc"); self.commit("doc")
        with self.assertRaises(ValueError):
            self.route_pr_out()

    def test_route_pr_pair_incomplete(self):
        self.setup_ok()
        en = self.draft.with_name(self.draft.name[:-3] + ".en.md"); en.write_text(INFER, encoding="utf-8"); self.commit("en")
        ok, no = R.Decision("APPROVED", [], publishable=True), R.Decision("NEEDS_REVIEW", ["E-ROUTE-NO-CODEX"])
        o = R._route_one
        try:
            R._route_one = lambda p, *a, **k: ({"flags": {}}, no if p.endswith(".en.md") else ok)
            out = self.route_pr_out()
            self.assertTrue(all(not d.publishable for _, d in out.values()))
            self.assertIn("E-ROUTE-PAIR-INCOMPLETE", out["daily/" + self.draft.name][1].codes)
        finally:
            R._route_one = o

    def test_raw_read_from_head_not_worktree(self):
        # 稿件引用的 raw 在 head 提交里与 MANIFEST 不符、工作树里却是好的 → 以 head 为准，不得通过自检
        self.setup_ok()
        import shutil
        raw = self.repo / "raw" / DATE / "arxiv" / "cs.AI.xml"
        rel = raw.relative_to(self.repo).as_posix()
        keep = raw.read_bytes()
        raw.write_bytes(keep + b"<!-- tampered -->"); self.git("add", rel); self.git("commit", "-qm", "corrupt raw in head")
        raw.write_bytes(keep)                                          # 工作树恢复为与 MANIFEST 一致的原件
        sc, d = self.route()
        self.assertFalse(d.publishable); self.assertEqual(sc["status"], "FAIL", sc["error_codes"])

    def test_pr_files_uncommitted_ignored(self):
        # 工作树里未提交的改动不算（字节取自 head 的 git 对象）
        self.setup_ok(); self.draft.write_text(INFER + "宏观经济好。\n", encoding="utf-8")
        sc, d = self.route(); self.assertTrue(d.publishable, d.codes)

    def test_no_draft_id_collision(self):
        repo = Path(tempfile.mkdtemp())
        a = R.draft_id_for(repo, repo / "a-b" / "c.md"); b = R.draft_id_for(repo, repo / "a" / "b-c.md")
        self.assertIsNone(a); self.assertEqual(b, "a-b-c"); self.assertNotEqual(a, b)
        for sec in ("daily-x", "x-", "-x"):
            self.assertIsNone(R.draft_id_for(repo, repo / sec / "n.md"), sec)
        self.assertEqual(R.draft_id_for(repo, repo / "daily" / "2026-10-11.md"), "daily-2026-10-11")


class R12V2Only(T):
    """r12 H-1：宏观、医疗、宗教、tongyi、信号卡只接受绑定 draft_id 的 v2 王总记录。"""
    def test_v1_rejected_for_wang_required(self):
        d = draft_of(INFER)
        for flag in ("macro", "medical", "religion"):
            sc = dict(sc_of(INFER), flags=dict(sc_of(INFER)["flags"], **{flag: True}))
            self.expect(self.run_(INFER, sc=sc, rc=recs(d) | {"wang": [wang_v1(d)]}), "NEEDS_REVIEW", False,
                        "E-ROUTE-RECORD-V2-REQUIRED")
            self.expect(self.run_(INFER, sc=sc, rc=recs(d)), "APPROVED", False)
        for did in ("tongyi-2026-01-05-x", "macro-2026-01-05"):
            d = draft_of(INFER, did)
            self.expect(self.run_(INFER, draft=d, rc=recs(d) | {"wang": [wang_v1(d)]}), "NEEDS_REVIEW", False,
                        "E-ROUTE-RECORD-V2-REQUIRED")

    def test_v2_bound_to_other_draft_rejected(self):
        d = draft_of(INFER)
        sc = dict(sc_of(INFER), flags=dict(sc_of(INFER)["flags"], macro=True))
        sc_, r = self.run_(INFER, sc=sc, rc=recs(d) | {"wang": [wang(d, draft_id="daily-other")]})
        self.assertFalse(r.publishable)

    def test_daily_needs_no_wang(self):
        d = draft_of(INFER)
        self.expect(self.run_(INFER, rc=recs(d, w=False)), "APPROVED", False)


class R13Records(T):
    """r13：Codex/王总记录字段缺一个即失败；_decide 私有，没有公开 decide。"""
    def test_no_public_decide(self):
        self.assertFalse(hasattr(R, "decide"))

    def test_record_missing_field_fails(self):
        d = draft_of(INFER)
        for k in ("codex_session", "log_path", "reviewed_at", "verdict", "draft_id"):
            c = codex(d); c.pop(k)
            sc, r = self.run_(INFER, rc={"codex": [c], "wang": [], "error": None})
            self.assertEqual((r.state, r.codes, r.publishable), ("HOLD", ["E-ROUTE-RECORD-INVALID"], False), k)
        for k in ("quote_ref", "channel", "recorded_at"):
            w = wang(d); w.pop(k)
            sc, r = self.run_s(INFER, rc={"codex": [codex(d)], "wang": [w], "error": None})
            self.assertFalse(r.publishable, k); self.assertIn("E-ROUTE-RECORD-INVALID", r.codes)


class R12Binding(T):
    """r12：decide() 核对自检结果属于这篇稿件；codex_in_production 先于日报快通道。"""
    def test_selfcheck_sha_mismatch(self):
        d = draft_of(INFER); sc = dict(sc_of(INFER), content_sha256="0" * 64)
        r = decide_(sc, d, state(), recs(d), NOW)
        self.assertEqual((r.state, r.codes, r.publishable), ("HOLD", ["E-ROUTE-INPUT"], False))
        r = R._diagnose(sc_of(INFER), d, state(), recs(d), NOW)   # 缺 content_sha256
        self.assertEqual(r.codes, ["E-ROUTE-INPUT"])

    def test_codex_in_production_before_fast_path(self):
        d = draft_of(INFER)
        for st in (state(codex_in_production=True), state(codex_in_production=True, mac_online=False, wang_present=False)):
            sc, r = self.run_(INFER, st=st, rc=recs(d, w=False))
            self.assertFalse(r.publishable); self.assertIn("A-NO-REVIEW-PATH", r.codes)


class R11NoAuto(T):
    """t161u：AUTO_APPROVED 永久关闭。任何稿件没有有效 Codex APPROVED（+ 王总批准）记录就不得发布。"""
    def test_never_auto_approved(self):
        for text in (CLEAN, INFER, TITLE + fred_line()):
            for st in (state(), state(wang_present=False)):
                for now in (NOW, EOD - dt.timedelta(minutes=1)):
                    sc, d = self.run_(text, st=st, now=now)
                    self.assertNotEqual(d.state, "AUTO_APPROVED"); self.assertFalse(d.publishable)
                    self.assertNotIn("I-AUTO-APPROVED", d.codes)

    def test_forged_low_risk_cannot_publish(self):
        sc = sc_of(CLEAN); sc["low_risk"] = True
        sc2, d = self.run_(CLEAN, sc=sc)
        self.assertFalse(d.publishable)

    def test_wang_without_codex_not_publishable(self):
        d0 = draft_of(CLEAN)
        sc, d = self.run_(CLEAN, rc=recs(d0, c=False))
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)
        sc, d = self.run_(CLEAN, rc={"codex": [codex(d0, verdict="REJECTED")], "wang": [wang(d0)], "error": None})
        self.assertFalse(d.publishable)
        sc, d = self.run_(CLEAN, rc=recs(d0))
        self.assertEqual(d.state, "APPROVED"); self.assertTrue(d.publishable)


class R12DailyCodexOnly(T):
    """用户决定：日报（含中英配对）只需 Codex APPROVED，不依赖王总在场；王总在场检查只对需要王总批准的稿件生效
    （宏观、tongyi、信号卡 cards-*，以及标为中医/佛学的稿件）。"""

    def st_absent(self):
        return state(wang_present=False)

    def test_daily_presence_missing_routes_on_codex(self):
        d = draft_of(INFER, did="daily-2026-01-05")
        sc, r = self.run_(INFER, draft=d, st=self.st_absent(), rc=recs(d, w=False))
        self.assertEqual(r.state, "APPROVED", r.codes); self.assertTrue(r.publishable)
        # 无 Codex 时：06:55 前仍等待审查（NEEDS_REVIEW），不因王总缺席顺延
        sc, r = self.run_(INFER, draft=d, st=self.st_absent(), rc=recs(d, c=False, w=False))
        self.assertEqual(r.state, "NEEDS_REVIEW", r.codes); self.assertIn("E-ROUTE-NO-CODEX", r.codes)

    def test_daily_pair_presence_missing_routes_on_codex(self):
        zh, en = draft_of(INFER, did="daily-2026-01-05"), draft_of(INFER + "\n", did="daily-2026-01-05-en")
        rc = {"codex": [codex(zh, pair_sha256=en["content_sha256"]), codex(en, pair_sha256=zh["content_sha256"])],
              "wang": [], "error": None}
        for a, b in ((zh, en), (en, zh)):
            r = decide_(sc_of(INFER), a, self.st_absent(), rc, NOW, pair=b["content_sha256"])
            self.assertEqual(r.state, "APPROVED", r.codes); self.assertTrue(r.publishable)

    def strict_cases(self):
        sc = sc_of(INFER)
        card = copy.deepcopy(sc); card["card_type"] = "signal"
        med = copy.deepcopy(sc); med["flags"]["medical"] = True
        rel = copy.deepcopy(sc); rel["flags"]["religion"] = True
        return (("macro", sc, draft_of(INFER, did="macro-2026-01-05")),
                ("tongyi", sc, draft_of(INFER, did="tongyi-intro")),
                ("card", card, draft_of(INFER, did="cards-2026-01-05")),
                ("中医", med, draft_of(INFER, did="daily-2026-01-05")),
                ("佛学", rel, draft_of(INFER, did="daily-2026-01-05")))

    def test_strict_presence_missing_not_routed_on_codex_only(self):
        for name, sc, d in self.strict_cases():
            r = decide_(sc, d, self.st_absent(), recs(d, w=False), NOW)
            self.assertFalse(r.publishable, name); self.assertEqual(r.state, "DEFERRED", (name, r.codes))
            self.assertIn("E-ROUTE-NO-WANG", r.codes, name)
            # 王总在场时则等待批准，而不是凭 Codex 发布
            r = decide_(sc, d, state(), recs(d, w=False), NOW)
            self.assertEqual(r.state, "NEEDS_REVIEW", (name, r.codes)); self.assertFalse(r.publishable)

    def test_needs_wang_classification(self):
        for name, sc, d in self.strict_cases():
            self.assertTrue(R.needs_wang(d, sc["card_type"], sc["flags"]), name)
        sc = sc_of(INFER)
        for did in ("daily-2026-01-05", "daily-2026-01-05-en", "2026-01-05-d1"):
            self.assertFalse(R.needs_wang(draft_of(INFER, did=did), "daily", sc["flags"]), did)


class R12Rollover(T):
    """路线图 v1.8：顺延只用两个截止（06:55 批准、07:00 发布）；'06:25 仍无 PR' 不再触发顺延。"""
    def test_no_pr_at_0625_no_rollover(self):
        t = dt.datetime(2026, 1, 5, 6, 25, tzinfo=SGT)
        st = state(updated_at=(t - dt.timedelta(minutes=1)).isoformat())
        for strict in (False, True):
            sc, r = (self.run_s if strict else self.run_)(INFER, now=t, st=st)
            self.assertEqual(r.state, "NEEDS_REVIEW", r.codes); self.assertIsNone(r.state_change)
            self.assertNotIn("I-DEFERRED", r.codes)
        # 同理 06:26–06:54 也不顺延；07:00 才首次顺延
        t2 = dt.datetime(2026, 1, 5, 6, 54, tzinfo=SGT)
        sc, r = self.run_(INFER, now=t2, st=state(updated_at=t2.isoformat()))
        self.assertEqual(r.state, "NEEDS_REVIEW", r.codes)
        sc, r = self.run_(INFER, now=EOD, st=state(updated_at=EOD.isoformat()))
        self.assertEqual(r.state, "DEFERRED", r.codes)

    def test_only_two_deadlines(self):
        times = sorted(v for v in vars(R).values() if isinstance(v, dt.time))
        self.assertEqual(times, [dt.time(6, 55), dt.time(7, 0)])


class R12bCodexFastPath(T):
    """用户决定（2026-10-11）：日报已有有效 Codex APPROVED → 不因 Mac 离线、心跳过期、王总不在场而 HOLD/归档；需王总批准的稿件照旧。"""
    def cx_only(self, d):
        return recs(d, w=False)

    def test_daily_approved_despite_mac_and_wang(self):
        d = draft_of(INFER)
        stale = (NOW - dt.timedelta(hours=3)).isoformat()
        for st in (state(mac_online=False), state(updated_at=stale), state(wang_present=False),
                   state(mac_online=False, wang_present=False, updated_at=stale)):
            self.expect(self.run_(INFER, st=st, rc=self.cx_only(d)), "APPROVED", False)

    def test_daily_without_codex_keeps_mac_rules(self):
        self.expect(self.run_(INFER, st=state(mac_online=False)), "ARCHIVED", False, "A-MAC-OFFLINE")
        self.expect(self.run_(INFER, st=state(updated_at=(NOW - dt.timedelta(hours=3)).isoformat())), "HOLD", False, "E-ROUTE-MAC-STALE")

    def test_daily_codex_rejected_not_approved(self):
        d = draft_of(INFER)
        rc = recs(d, w=False) | {"codex": [codex(d, verdict="REJECTED")]}
        self.expect(self.run_(INFER, st=state(mac_online=False), rc=rc), "ARCHIVED", False, "A-MAC-OFFLINE")

    def test_daily_after_0700_still_deferred(self):
        d = draft_of(INFER)
        now = dt.datetime.combine(dt.date.fromisoformat(DATE), dt.time(7, 1), SGT)
        st = state(updated_at=(now - dt.timedelta(minutes=1)).isoformat())
        self.expect(self.run_(INFER, now=now, st=st, rc=self.cx_only(d)), "DEFERRED", False, "E-ROUTE-PUBLISH-LATE")

    def test_wang_drafts_keep_rules(self):
        d = draft_of(INFER)
        self.expect(self.run_w(INFER, st=state(mac_online=False), rc=recs(d)), "ARCHIVED", False, "A-MAC-OFFLINE")
        self.expect(self.run_w(INFER, rc=self.cx_only(d)), "NEEDS_REVIEW", False, "E-ROUTE-NO-WANG")
        self.expect(self.run_w(INFER, st=state(updated_at=(NOW - dt.timedelta(hours=3)).isoformat()), rc=recs(d)), "HOLD", False, "E-ROUTE-MAC-STALE")


class R13GhPr(unittest.TestCase):
    def test_gh_pr_maps_api_fields_and_fails_closed(self):
        import json as _j, subprocess as _sp
        from unittest import mock
        def fake(args, **kw):
            out = {"api": _j.dumps({"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}, "state": "open"}),
                   "pr": _j.dumps({"files": [{"path": "daily/x.md"}]})}[args[1]]
            return _sp.CompletedProcess(args, 0, out, "")
        with mock.patch("subprocess.run", fake):
            m = R._gh_pr(".", 7)
        self.assertEqual((m["baseRefOid"], m["headRefOid"], m["state"]), ("a" * 40, "b" * 40, "OPEN"))
        with mock.patch("subprocess.run", lambda a, **k: _sp.CompletedProcess(a, 1, "", "x")):
            with self.assertRaises(RuntimeError):
                R._gh_pr(".", 7)
        with mock.patch("subprocess.run", lambda a, **k: _sp.CompletedProcess(a, 0, "{}", "")):
            with self.assertRaises(RuntimeError):
                R._gh_pr(".", 7)


class Correction(FromMain):
    """更正稿 correction（Grok Bot 定，2026-10-11；r15 王总定“已发布”凭据＝站点仓库 origin/main 上确实有这篇）。"""
    LATER = dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT)      # 次日 10:00，已过原稿日 07:00

    def setUp(self):
        super().setUp()
        import tempfile as _t
        self.site = Path(_t.mkdtemp())
        self.sgit("init", "-q", "-b", "main")
        self.publish("daily", "2026-01-05-d1", "---\ntitle: 日报\ndate: 2026-01-05T07:00:00+08:00\n---\n" + INFER + DISC)
        self._o = R.SITE_REF; R.SITE_REF = "main"           # 测试站点仓库没有 origin

    def tearDown(self):
        R.SITE_REF = self._o

    def sgit(self, *a):
        r = self.sp.run(["git", *a], cwd=self.site, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); return r.stdout

    def publish(self, sec, name, text):
        p = self.site / "content" / "posts" / sec / (name + ".md"); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8"); self.sgit("add", "-A"); self.sgit("commit", "-qm", "pub")

    def ctext(self, corrects="daily-2026-01-05-d1", at="2026-01-06", note=True, body=None, disc=True):
        fm = "---\n" + (f"corrects: {corrects}\n" if corrects is not None else "") + (f"corrected_at: {at}\n" if at is not None else "") + "---\n"
        b = body if body is not None else INFER
        return fm + b + (f"\n## 更正 {at}\n" if note and at else "") + (DISC if disc else "")

    def rec(self, text, wang_rec=False, did="daily-2026-01-05-d1", **kw):
        d = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": did}
        self.write("state/publish-state.json", json.dumps(state(**kw.pop("st", {}))))
        self.write(f"approvals/codex/{d['content_sha256']}.json",
                   json.dumps(codex(d, reviewed_at=kw.pop("reviewed_at", "2026-01-06T09:30:00+08:00"))))
        if wang_rec:
            self.write(f"approvals/wang/{d['content_sha256']}.json",
                       json.dumps(wang(d, recorded_at="2026-01-06T09:40:00+08:00")))
        self.commit("rec")

    def go(self, text, now=None, rel="daily/2026-01-05-d1.md", site=True, date=DATE):
        o = R.APPROVALS_REF; R.APPROVALS_REF = "main"
        try:
            sc, d = R._route_one(rel, text.encode(), self.repo, date, "daily", now or self.LATER,
                                 link_checker=lambda u: True, site_repo=self.site if site else None)
            d.publishable = d.state == "APPROVED"          # r17：生产里由 route_pr 设置；这里模拟 route_pr 的同一步
            return sc, d
        finally:
            R.APPROVALS_REF = o

    def test_correction_published_after_0700(self):
        t = self.ctext(); self.rec(t)
        sc, d = self.go(t)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
        self.assertIn("I-CORRECTION", d.codes); self.assertIsNone(d.state_change)

    def test_without_codex_needs_review_not_deferred(self):
        t = self.ctext(); self.rec(INFER + "x")
        sc, d = self.go(t)
        self.assertEqual((d.state, d.publishable), ("NEEDS_REVIEW", False)); self.assertIn("E-ROUTE-NO-CODEX", d.codes)

    def test_frontmatter_fields_required(self):
        for t in (self.ctext(at=None), self.ctext(corrects=None), self.ctext(corrects="")):
            self.rec(t)
            self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-INVALID"], t[:60])

    def test_published_proof_is_site_main(self):
        t = self.ctext(corrects="daily-2026-01-04-d1"); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-TARGET"])       # corrects 与本稿不一致
        t = self.ctext(corrects="daily-2026-01-05-d2"); self.rec(t, did="daily-2026-01-05-d2")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-d2.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])  # 站点 main 上没有
        t = self.ctext(); self.rec(t)
        self.assertEqual(self.go(t, site=False)[1].codes, ["E-ROUTE-CORRECTION-TARGET"])  # 没给站点仓库
        # 数据仓库 main 上有、站点 main 上没有：仍判失败（不认数据仓库或发布状态）
        self.write("daily/2026-01-05-d3.md", INFER + DISC); self.commit("data only")
        t = self.ctext(corrects="daily-2026-01-05-d3"); self.rec(t, did="daily-2026-01-05-d3")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-d3.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])
        # 站点原稿只在未合并分支上：不算
        self.sgit("checkout", "-q", "-b", "draft"); self.publish("daily", "2026-01-05-d4", "---\ndate: 2026-01-05\n---\nx\n")
        self.sgit("checkout", "-q", "main")
        t = self.ctext(corrects="daily-2026-01-05-d4"); self.rec(t, did="daily-2026-01-05-d4")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-d4.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])

    def test_original_date_from_site_front_matter(self):
        self.publish("daily", "2026-01-05-nd", "---\ntitle: x\n---\n" + INFER)         # 原稿无日期
        t = self.ctext(corrects="daily-2026-01-05-nd"); self.rec(t, did="daily-2026-01-05-nd")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-nd.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])
        self.publish("daily", "2026-01-05-od", "---\ndate: 2026-01-04\n---\n" + INFER)  # 原稿日期与 --date 不一致
        t = self.ctext(corrects="daily-2026-01-05-od"); self.rec(t, did="daily-2026-01-05-od")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-od.md")[1].codes, ["E-ROUTE-CORRECTION-DATE"])

    def test_corrected_at_bounds(self):
        for at in ("2026-01-04", "2026-01-07", "2026-1-6", "x"):
            t = self.ctext(at=at); self.rec(t)
            self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-DATE"], at)
        t = self.ctext(at="2026-01-05"); self.rec(t, reviewed_at="2026-01-05T08:00:00+08:00")
        self.assertTrue(self.go(t)[1].publishable)

    def test_codex_review_not_before_corrected_at(self):
        t = self.ctext(); self.rec(t, reviewed_at="2026-01-05T06:00:00+08:00")
        self.assertIn("E-ROUTE-RECORD-EXPIRED", self.go(t)[1].codes)

    def test_page_must_note_date(self):
        t = self.ctext(note=False); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-NOTE"])
        t = self.ctext(note=False).replace("---\n" + INFER, "---\n" + INFER + "<!-- 更正 2026-01-06 -->\n"); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-NOTE"])

    def test_disclaimer_still_required_even_for_old_date(self):
        t = self.ctext(disc=False); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-DISCLAIMER-MISSING"])
        t = self.ctext(disc=False).replace("---\n", "---\ndescription: 本文不含投资建议。\n", 1); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-DISCLAIMER-MISSING"])

    def test_codex_in_production_and_selfcheck(self):
        t = self.ctext(); self.rec(t, st={"codex_in_production": True})
        sc, d = self.go(t)
        self.assertEqual((d.state, d.publishable), ("HOLD", False)); self.assertIn("A-NO-REVIEW-PATH", d.codes)
        self.assertIsNone(d.state_change)
        bad = self.ctext(body=TITLE + "宏观经济将会衰退。\n"); self.rec(bad)
        self.assertFalse(self.go(bad)[1].publishable)

    def test_category_from_site_original_needs_wang(self):
        self.publish("daily", "2026-01-05-m1", "---\ndate: 2026-01-05\ncategories: [宏观]\n---\n" + INFER + DISC)
        t = ("---\ncorrects: daily-2026-01-05-m1\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n## 更正 2026-01-06\n" + DISC)
        self.rec(t, did="daily-2026-01-05-m1")
        sc, d = self.go(t, rel="daily/2026-01-05-m1.md")
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)    # 类别沿用站点原稿（宏观）
        self.rec(t, wang_rec=True, did="daily-2026-01-05-m1")
        self.assertTrue(self.go(t, rel="daily/2026-01-05-m1.md")[1].publishable)

    def test_not_a_correction_still_deferred(self):
        t = INFER + "\n改了一处。\n" + DISC; self.rec(t, reviewed_at="2026-01-05T02:25:00+08:00")
        self.assertEqual(self.go(t)[1].state, "DEFERRED")


class R15Fixes(FromMain):
    def test_unknown_section_fails(self):
        self.setup_ok()
        for rel in ("essay/intro.md", "notes/2026-01-05.md"):
            sc, d = self.one(rel, (INFER + DISC).encode())
            self.assertEqual((d.state, d.codes, d.publishable), ("HOLD", ["E-ROUTE-DRAFT-PATH"], False), rel)

    def test_route_pr_now_cannot_rewind_past_0700(self):
        self.setup_ok(); self.git("tag", "-f", "base")
        self.write("daily/2026-01-05-d1.md", INFER + "\n补一句。\n" + DISC); self.commit("edit")
        sha = hashlib.sha256((INFER + "\n补一句。\n" + DISC).encode()).hexdigest()
        self.write(f"approvals/codex/{sha}.json", json.dumps(codex({"content_sha256": sha, "draft_id": "daily-2026-01-05-d1"})))
        self.commit("rec"); self.git("tag", "-f", "base")
        self.write("daily/2026-01-05-d1.md", INFER + "\n补一句。\n" + DISC + "\n"); self.commit("x")
        o1, o2, o3 = R._gh_pr, R.APPROVALS_REF, R._real_now
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"
        R._real_now = lambda: dt.datetime(2026, 1, 5, 7, 3, tzinfo=SGT)                   # 实际 07:03
        try:
            out = R.route_pr(self.repo, 21, DATE, "daily")                                # 公开入口不收 now
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now = o1, o2, o3
        d = list(out.values())[0][1]
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-PUBLISH-LATE", d.codes)


def quote_line_macro():
    from helpers import fred_line
    return fred_line()


class R14Fixes(FromMain):
    def test_path_date_must_match_cli_date(self):
        self.setup_ok()
        sc, d = self.one("digest/2026-10-12.md", (INFER).encode(), date="2026-10-11")
        self.assertEqual((d.state, d.codes), ("HOLD", ["E-ROUTE-INPUT"]))

    def test_head_change_during_routing_fails(self):
        self.setup_ok(); self.git("tag", "-f", "base")
        self.write("daily/2026-01-05-d1.md", INFER + "\n补一句。\n" + DISC); self.commit("edit")
        m = self.gh_meta(); calls = []
        def gh(repo, n):
            calls.append(1)
            return m if len(calls) == 1 else dict(m, headRefOid="2" * 40)
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = gh; R.APPROVALS_REF = "main"; R._real_now = lambda: NOW; R._http_probe = lambda u, timeout=10: (True, None)
        try:
            with self.assertRaises(RuntimeError):
                R.route_pr(self.repo, 21, DATE, "daily")
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    def test_cli_now_cannot_rewind(self):
        import subprocess, sys as _s
        cli = Path(R.__file__).resolve().parents[1] / "route.py"
        r = subprocess.run([_s.executable, str(cli), "--pr", "1", "--repo", str(self.repo), "--date", DATE,
                            "--card-type", "daily", "--now", "2020-01-01T06:50:00+08:00"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("E-ROUTE-INPUT", r.stdout); self.assertIn("--dry-run", r.stdout)


class R15RecordSource(unittest.TestCase):
    def test_decide_full_takes_no_records(self):
        import inspect
        params = list(inspect.signature(R._diagnose_from_git).parameters)
        self.assertNotIn("records", params); self.assertNotIn("state", params)
        src = inspect.getsource(R._diagnose_from_git)
        self.assertIn("load_from_ref(repo, APPROVALS_REF)", src)
        self.assertFalse(hasattr(_A, "LoadedRecords"))


class R16Fixes(Correction):
    """r16（王总定）：front matter 用 YAML 解析；类别识别不出按最严；站点仓库只认规范 remote；_diagnose 不带 publishable。"""

    def _orig(self, fm_extra, name="2026-01-05-m1"):
        self.publish("daily", name, "---\ndate: 2026-01-05\n" + fm_extra + "---\n" + INFER + DISC)
        t = (f"---\ncorrects: daily-{name}\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n## 更正 2026-01-06\n" + DISC)
        self.rec(t, did=f"daily-{name}")
        return self.go(t, rel=f"daily/{name}.md")[1]

    def test_multiline_inline_scalar_categories_need_wang(self):
        for i, fm in enumerate(("categories:\n  - macro\n", "categories:\n- 宏观\n", "categories: [daily, macro]\n",
                                "categories: macro\n", "tags:\n  - 中医\n")):
            d = self._orig(fm, name=f"2026-01-05-m{i}")
            self.assertFalse(d.publishable, fm); self.assertIn("E-ROUTE-NO-WANG", d.codes, fm)

    def test_unrecognized_category_is_strictest(self):
        for i, fm in enumerate(("categories: [AI]\n", "tags: {a: 1}\n", "series: 统一\n", "categories: [[macro]]\n")):
            d = self._orig(fm, name=f"2026-01-05-u{i}")
            self.assertIn("E-ROUTE-NO-WANG", d.codes, fm)

    def test_daily_labels_do_not_need_wang(self):
        d = self._orig("categories:\n  - daily\ntags: [日报]\n", name="2026-01-05-ok")
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_bad_yaml_fails(self):
        self.publish("daily", "2026-01-05-b1", "---\ndate: 2026-01-05\ncategories: [macro\n---\n" + INFER + DISC)
        t = "---\ncorrects: daily-2026-01-05-b1\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n## 更正 2026-01-06\n" + DISC
        self.rec(t, did="daily-2026-01-05-b1")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-b1.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])   # 原稿解析失败
        t2 = "---\ncorrects: [x\n---\n" + INFER + DISC
        self.rec(t2)
        self.assertEqual(self.go(t2)[1].codes, ["E-ROUTE-FRONT-MATTER"])                                        # 本稿解析失败

    def test_site_remote_must_be_canonical(self):
        for u in ("https://github.com/markjin-lab/markjin-lab.github.io.git", "https://github.com/markjin-lab/markjin-lab.github.io",
                  "git@github.com:markjin-lab/markjin-lab.github.io.git"):
            self.assertTrue(R._site_remote_ok(u), u)
        for u in ("https://github.com/evil/markjin-lab.github.io.git", "/tmp/bare.git", "file:///tmp/x",
                  "https://github.com/markjin-lab/markjin-lab.github.io.git.evil", "https://example.com/markjin-lab/markjin-lab.github.io"):
            self.assertFalse(R._site_remote_ok(u), u)

    def test_self_made_site_repo_rejected(self):
        """自建仓库：origin 指向自建 bare 仓库，本地 origin/main 与其远端一致，仍须判失败。"""
        import tempfile as _t
        bare = Path(_t.mkdtemp()) / "b.git"
        self.sp.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        self.sgit("remote", "add", "origin", str(bare)); self.sgit("push", "-q", "origin", "main"); self.sgit("fetch", "-q", "origin")
        R.SITE_REF = "origin/main"
        t = self.ctext(); self.rec(t)
        self.assertEqual(self.go(t)[1].codes, ["E-ROUTE-CORRECTION-TARGET"])
        self.assertIsNone(R._site_main(self.site))

    def test_diagnose_has_no_publishable_and_no_evaluate(self):
        self.assertFalse(hasattr(R, "_evaluate"))
        import inspect
        src = inspect.getsource(R)
        self.assertEqual(src.count("publishable = "), 1)                 # r17：只在 route_pr 里设置
        self.assertNotIn("publishable=True", src)
        self.assertIn("d.publishable = publish and d.state == \"APPROVED\"", inspect.getsource(R._route_pr))
        self.assertFalse(hasattr(R, "_decide_full"))
        t = self.ctext(); self.rec(t)
        sc, d0 = self.go(t)
        self.assertTrue(d0.publishable)
        d = R._diagnose(sc, {"draft_id": "daily-2026-01-05-d1", "date": DATE, "content_sha256": sc["content_sha256"]},
                        state(), {"codex": [], "wang": [], "error": None}, self.LATER)
        self.assertFalse(d.publishable)

    def test_production_code_does_not_import_test_helpers(self):
        import pathlib
        for f in pathlib.Path(R.__file__).parent.glob("*.py"):
            self.assertNotIn("evaluate_for_tests", f.read_text(encoding="utf-8"), f.name)
        self.assertNotIn("evaluate_for_tests", (pathlib.Path(R.__file__).parents[1] / "route.py").read_text(encoding="utf-8"))


class R17Fixes(R16Fixes):
    """r17（王总定）：发布入口只有 route_pr；原稿类别 null / 空列表 / 无法解释一律须王总；YAML 重复键判失败。"""

    def test_null_or_empty_category_needs_wang(self):
        for i, fm in enumerate(("categories: null\n", "categories: []\n", "categories:\n", "tags: ''\n", "categories: [daily, '']\n")):
            d = self._orig(fm, name=f"2026-01-05-n{i}")
            self.assertIn("E-ROUTE-NO-WANG", d.codes, fm)

    def test_duplicate_keys_fail(self):
        with self.assertRaises(R.FrontMatterError):
            R.front_matter("---\ncategories: [daily]\ncategories: [macro]\n---\nx\n")
        self.publish("daily", "2026-01-05-k1", "---\ndate: 2026-01-05\ncategories: daily\ncategories: macro\n---\n" + INFER + DISC)
        t = "---\ncorrects: daily-2026-01-05-k1\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n## 更正 2026-01-06\n" + DISC
        self.rec(t, did="daily-2026-01-05-k1")
        self.assertEqual(self.go(t, rel="daily/2026-01-05-k1.md")[1].codes, ["E-ROUTE-CORRECTION-TARGET"])
        t2 = "---\ncorrects: daily-2026-01-05-d1\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + INFER + DISC
        self.rec(t2)
        self.assertEqual(self.go(t2)[1].codes, ["E-ROUTE-FRONT-MATTER"])

    def test_internal_functions_never_publishable(self):
        """直接调用 _route_one / _diagnose_from_git 得到的结果不带 publishable；只有 route_pr 会设置。"""
        t = self.ctext(); self.rec(t)
        o = R.APPROVALS_REF; R.APPROVALS_REF = "main"
        try:
            sc, d = R._route_one("daily/2026-01-05-d1.md", t.encode(), self.repo, DATE, "daily", self.LATER,
                                 link_checker=lambda u: True, site_repo=self.site)
        finally:
            R.APPROVALS_REF = o
        self.assertEqual((d.state, d.publishable), ("APPROVED", False))


class FinalR1(FromMain):
    """整体验收 r1（王总定）：route_pr 链接检查不能关闭、打不开/没检查一律 HOLD（网络问题重试一次）；
    信号卡站点路径；更正稿经 route_pr 的端到端；06:55 边界。"""
    T0658 = dt.datetime(2026, 1, 5, 6, 58, tzinfo=SGT)   # r7：去掉第三遍后恢复 06:58

    def setUp(self):
        super().setUp()
        self._sleep = R._LinkProbe.RETRY_SLEEP; R._LinkProbe.RETRY_SLEEP = 0

    def tearDown(self):
        R._LinkProbe.RETRY_SLEEP = self._sleep

    def run_pr(self, now=NOW, checker=lambda u: True, site=None, meta=None):
        """整体验收 r2：route_pr 不收 now / link_checker；测试 monkeypatch _real_now 与 _http_probe。checker=None → 不替换 _http_probe。"""
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = meta or (lambda repo, n: self.gh_meta()); R.APPROVALS_REF = "main"
        R._real_now = lambda: now
        if checker is not None:
            R._http_probe = lambda u, timeout=10: (True, None) if checker(u) is True else (False, "unreachable")
        try:
            return R.route_pr(self.repo, 21, DATE, "daily", site_repo=site)["daily/" + self.draft.name][1]
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    # —— 链接
    def test_unreachable_link_holds_with_reason(self):
        self.setup_ok()
        d = self.run_pr(checker=lambda u: False)
        self.assertEqual((d.state, d.codes, d.publishable), ("HOLD", ["E-ROUTE-LINK-UNREACHABLE"], False))
        self.assertIn("unreachable", d.detail)

    def test_network_error_retried_once(self):
        self.setup_ok()
        calls = []
        def flaky(u):
            calls.append(u)
            if len(calls) == 1:
                raise OSError("temporary")
            return True
        d = self.run_pr(checker=flaky)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
        self.assertEqual(len(calls), 2)

    def test_network_error_twice_holds(self):
        self.setup_ok()
        def down(u):
            raise TimeoutError("down")
        d = self.run_pr(checker=down)
        self.assertEqual((d.state, d.codes), ("HOLD", ["E-ROUTE-LINK-UNREACHABLE"]))
        self.assertIn("network: TimeoutError", d.detail); self.assertIn("已重试一次", d.detail)

    def test_none_checker_does_not_disable(self):
        """route_pr(link_checker=None) 不是“关掉检查”：用内置 HTTP 检查；这里让它失败，结果仍是 HOLD。"""
        self.setup_ok()
        o = R._http_probe; R._http_probe = lambda u, timeout=10: (False, "http 404")
        try:
            d = self.run_pr(checker=None)
        finally:
            R._http_probe = o
        self.assertEqual((d.state, d.codes), ("HOLD", ["E-ROUTE-LINK-UNREACHABLE"])); self.assertIn("http 404", d.detail)

    def test_cli_no_link_check_rejected(self):
        import subprocess, sys
        cli = Path(R.__file__).resolve().parents[1] / "route.py"
        r = subprocess.run([sys.executable, str(cli), "--pr", "1", "--repo", str(self.repo), "--date", DATE,
                            "--card-type", "daily", "--no-link-check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); out = json.loads(r.stdout)
        self.assertEqual((out["state"], out["codes"]), ("HOLD", ["E-ROUTE-INPUT"]))

    # —— 06:55 边界
    def _codex_at(self, ts):
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(self.cp, json.dumps(codex(self.dr, reviewed_at=ts)))
        self.commit("rec")

    def test_codex_exactly_0655_ok(self):
        self._codex_at("2026-01-05T06:55:00+08:00")
        d = self.run_pr(now=self.T0658)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_codex_after_0655_not_publishable(self):
        self._codex_at("2026-01-05T06:55:01+08:00")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-RECORD-LATE", d.codes)

    # —— 信号卡站点路径
    def test_card_site_path(self):
        self.assertEqual(R.site_path("cards-abc", False), "content/cards/abc.md")
        self.assertEqual(R.site_path("cards-abc-en", True), "content/cards/abc.en.md")
        self.assertEqual(R.site_path("daily-2026-01-05-d1", False), "content/posts/daily/2026-01-05-d1.md")

    # —— 更正稿经 route_pr 端到端
    def _site(self, publish=True):
        import tempfile as _t
        root = Path(_t.mkdtemp()); bare = root / "site.git"; site = root / "site"
        run = lambda *a, cwd=None: self.assertEqual(self.sp.run(["git", *a], cwd=cwd, env=self.env, capture_output=True).returncode, 0, a)
        run("init", "-q", "--bare", str(bare)); run("init", "-q", "-b", "main", str(site))
        p = site / "content/posts/daily/2026-01-05-d1.md"; p.parent.mkdir(parents=True)
        p.write_text("---\ntitle: 日报\ndate: 2026-01-05T07:00:00+08:00\n---\n" + INFER + DISC, encoding="utf-8")
        if not publish:
            p.unlink(); (site / "README.md").write_text("x\n", encoding="utf-8")
        run("add", "-A", cwd=site); run("commit", "-qm", "pub", cwd=site)
        run("remote", "add", "origin", str(bare), cwd=site); run("push", "-q", "origin", "main", cwd=site)
        run("fetch", "-q", "origin", cwd=site)
        return site

    def _correction_pr(self):
        t = "---\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n## 更正 2026-01-06\n" + DISC
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write("state/publish-state.json", json.dumps(state(updated_at="2026-01-06T09:50:00+08:00")))
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr, reviewed_at="2026-01-06T09:30:00+08:00")))
        self.commit("corr")

    def test_correction_end_to_end_via_route_pr(self):
        self._correction_pr()
        later = dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT)
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True      # 测试 remote 是本地 bare 仓库；规范 remote 另有单测
        try:
            d = self.run_pr(now=later, site=self._site())
            self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes); self.assertIn("I-CORRECTION", d.codes)
            d2 = self.run_pr(now=later, site=self._site(publish=False))
            self.assertFalse(d2.publishable); self.assertIn("E-ROUTE-CORRECTION-TARGET", d2.codes)
        finally:
            R._site_remote_ok = o
        d3 = self.run_pr(now=later, site=self._site())                  # 不是规范 remote → 失败
        self.assertFalse(d3.publishable); self.assertIn("E-ROUTE-CORRECTION-TARGET", d3.codes)

    def test_correction_of_deferred_then_published_original_via_route_pr(self):
        # r15 HIGH（协调方批准）：原稿先顺延（状态条目绑定旧稿 sha），次日获批并发布到站点 main；之后的更正稿应正常路由，
        # 不得因旧顺延条目报 E-ROUTE-DEFER-MISMATCH / E-ROUTE-CORRECTION-TARGET
        orig = "---\ntitle: 日报\ndate: 2026-01-05T07:00:00+08:00\n---\n" + INFER + DISC
        df = {"status": "deferred", "reason": "I-DEFERRED", "at": "2026-01-05T07:00:00+08:00", "date": "2026-01-05",
              "content_sha256": hashlib.sha256(orig.encode()).hexdigest()}
        self._correction_pr()
        self.write("state/publish-state.json",
                   json.dumps(state(updated_at="2026-01-07T09:50:00+08:00", drafts={"daily-2026-01-05-d1": df})))
        self.commit("deferred-state")
        later = dt.datetime(2026, 1, 7, 10, 0, tzinfo=SGT)
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True
        try:
            d = self.run_pr(now=later, site=self._site())
            self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
            self.assertIn("I-CORRECTION", d.codes); self.assertNotIn("E-ROUTE-DEFER-MISMATCH", d.codes)
            d2 = self.run_pr(now=later, site=self._site(publish=False))     # 原稿未发布（只有顺延条目）→ 仍不可更正
            self.assertFalse(d2.publishable); self.assertIn("E-ROUTE-CORRECTION-TARGET", d2.codes)
        finally:
            R._site_remote_ok = o


class FinalR2(FinalR1):
    """整体验收 r2（王总定）：route_pr 公开签名去掉 now / link_checker；dry-run 永不 publishable；
    免责声明逐字（含标点）；更正日期须在标题行；末次核对 PR 仍 OPEN；YAML 非字符串键 → 结构化 HOLD。"""
    def test_public_signature(self):
        import inspect
        ps = list(inspect.signature(R.route_pr).parameters)
        self.assertEqual(ps, ["repo", "pr_number", "date", "card_type", "site_repo"])
        with self.assertRaises(TypeError):
            R.route_pr(self.repo, 21, DATE, "daily", NOW)
        with self.assertRaises(TypeError):
            R.route_pr(self.repo, 21, DATE, "daily", link_checker=lambda u: True)

    def test_dry_run_never_publishable(self):
        self.setup_ok()
        o1, o2, o3 = R._gh_pr, R.APPROVALS_REF, R._http_probe
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"; R._http_probe = lambda u, timeout=10: (True, None)
        try:
            out = R.dry_run(self.repo, 21, DATE, "daily", NOW)
        finally:
            R._gh_pr, R.APPROVALS_REF, R._http_probe = o1, o2, o3
        d = list(out.values())[0][1]
        self.assertEqual(d.state, "APPROVED"); self.assertIs(d.publishable, False)

    def test_pr_closed_at_final_check(self):
        self.setup_ok()
        m = self.gh_meta(); calls = []
        def gh(repo, n):
            calls.append(1)
            return m if len(calls) == 1 else dict(m, state="CLOSED")
        with self.assertRaises(RuntimeError):
            self.run_pr(meta=gh)

    def test_disclaimer_needs_exact_punctuation(self):
        self.assertTrue(R.has_disclaimer("x\n本文不含投资建议。\n", False))
        self.assertFalse(R.has_disclaimer("x\n本文不含投资建议\n", False))
        self.assertTrue(R.has_disclaimer("x\nThis article does not constitute investment advice.\n", True))
        self.assertFalse(R.has_disclaimer("x\nThis article does not constitute investment advice\n", True))

    def test_yaml_non_string_key_is_front_matter_error(self):
        for fm in ("? [a, b]\n: 1\n", "1: x\n", "title: t\nmeta:\n  ? [x]\n  : y\n"):
            with self.assertRaises(R.FrontMatterError, msg=fm):
                R.front_matter("---\n" + fm + "---\nbody\n")

    def test_correction_date_must_be_in_heading(self):
        t = "---\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + INFER + "\n更正 2026-01-06\n[来源](https://x.test/2026-01-06)\n" + DISC
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write("state/publish-state.json", json.dumps(state(updated_at="2026-01-06T09:50:00+08:00")))
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr, reviewed_at="2026-01-06T09:30:00+08:00")))
        self.commit("corr")
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True
        try:
            d = self.run_pr(now=dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT), site=self._site())
        finally:
            R._site_remote_ok = o
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-CORRECTION-NOTE", d.codes)


class FinalR3(FinalR1):
    """整体验收 r3：路由跨时间边界 → HOLD 重跑；更正日期须在标题的可见文字里；dry-run 不输出 state_change。"""
    def test_crosses_boundary(self):
        S = lambda h, m, s=0, d=5: dt.datetime(2026, 1, d, h, m, s, tzinfo=SGT)
        self.assertTrue(R._crosses_boundary(S(6, 59, 55), S(7, 0, 5)))
        self.assertTrue(R._crosses_boundary(S(6, 54, 59), S(6, 55)))
        self.assertTrue(R._crosses_boundary(S(23, 59, 59), S(0, 0, 1, d=6)))
        self.assertTrue(R._crosses_boundary(S(7, 1), S(7, 0)))           # 时钟回拨
        self.assertFalse(R._crosses_boundary(S(6, 50), S(6, 54, 59)))
        self.assertFalse(R._crosses_boundary(S(7, 0), S(7, 5)))

    def test_route_pr_crossing_0700_holds(self):
        self.setup_ok()
        ticks = iter([dt.datetime(2026, 1, 5, 6, 59, 55, tzinfo=SGT), dt.datetime(2026, 1, 5, 7, 0, 5, tzinfo=SGT)])
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"
        R._real_now = lambda: next(ticks); R._http_probe = lambda u, timeout=10: (True, None)
        try:
            with self.assertRaises(RuntimeError) as cm:
                R.route_pr(self.repo, 21, DATE, "daily")
            self.assertIn("E-ROUTE-RETRY", str(cm.exception))
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    def test_heading_shown_text(self):
        self.assertNotIn("2026-01-06", R._heading_shown("## [更正说明](https://example.test/2026-01-06)"))
        self.assertNotIn("2026-01-06", R._heading_shown("## 更正 ![x](https://e.test/2026-01-06.png)"))
        self.assertNotIn("2026-01-06", R._heading_shown('## <span title="2026-01-06">更正</span>'))
        self.assertIn("2026-01-06", R._heading_shown("## [更正 2026-01-06](https://e.test/x)"))
        self.assertIn("2026-01-06", R._heading_shown("## 更正 2026-01-06"))

    def test_approval_regex_fullmatch(self):
        from markjin import approvals as A
        self.assertIsNone(A.QUOTE_REF_RE.fullmatch("grok-bot:t1\n"))
        self.assertIsNone(A.LOG_PATH_RE.fullmatch("review/x.log\n"))
        import inspect
        self.assertNotRegex(inspect.getsource(A), r"_RE\.match\(")

    def test_cli_dry_run_drops_state_change_before_print(self):
        src = (Path(R.__file__).resolve().parents[1] / "route.py").read_text(encoding="utf-8")
        i, j = src.index('r["state_change"] = None'), src.index("print(json.dumps(res[0]")
        self.assertLess(i, j); self.assertLess(src.index('r["dry_run"] = True'), j)


class FinalR4(FinalR1):
    """整体验收 r4：结束时按真实时间重算全部判定，与开头不同 → E-ROUTE-RETRY；Python dry_run 也不带 state_change。"""
    def _with(self, fn, ticks=None):
        o1, o2, o3, o4, o5 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe, R._route_one
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"
        R._real_now = (lambda it=iter(ticks): next(it)) if ticks else (lambda: NOW)
        R._http_probe = lambda u, timeout=10: (True, None)
        try:
            return fn()
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe, R._route_one = o1, o2, o3, o4, o5

    def test_decision_change_between_passes_retries(self):
        self.setup_ok()
        real = R._route_one; calls = []
        def flip(*a, **k):
            sc, d = real(*a, **k); calls.append(1)
            if len(calls) == 2:
                d = R.Decision("HOLD", ["E-ROUTE-MAC-STALE"])     # 模拟心跳在路由期间过期
            return sc, d
        def go():
            R._route_one = flip
            return R.route_pr(self.repo, 21, DATE, "daily")
        with self.assertRaises(RuntimeError) as cm:
            self._with(go)
        self.assertIn("E-ROUTE-RETRY", str(cm.exception))

    def test_heartbeat_ttl_crossing_retries(self):
        self.setup_ok()
        upd = NOW - R.MAC_STATUS_TTL + dt.timedelta(seconds=1)
        self.write("state/publish-state.json", json.dumps(state(updated_at=upd.isoformat()))); self.commit("hb")
        self.git("tag", "-f", "base"); self.write("daily/2026-01-05-d1.md", INFER + "\n补一句。\n" + DISC); self.commit("e")
        ticks = [NOW, NOW + dt.timedelta(seconds=3), NOW + dt.timedelta(seconds=3)]
        try:
            out = self._with(lambda: R.route_pr(self.repo, 21, DATE, "daily"), ticks)
            for _, d in out.values():                              # 结论没变（如本稿不看心跳）也可以，但不能沿用过期判定
                self.assertNotIn("E-ROUTE-MAC-STALE", d.codes)
        except RuntimeError as e:
            self.assertIn("E-ROUTE-RETRY", str(e))

    def test_python_dry_run_has_no_state_change(self):
        self.setup_ok()
        out = self._with(lambda: R.dry_run(self.repo, 21, DATE, "daily", NOW + dt.timedelta(days=1)))
        for _, d in out.values():
            self.assertIsNone(d.state_change); self.assertFalse(d.publishable)

    def test_reference_image_alt_not_shown(self):
        self.assertNotIn("2026-01-06", R._heading_shown("## ![更正 2026-01-06][img]"))

    def test_approval_filename_fullmatch(self):
        import inspect
        from markjin import approvals as A
        self.assertNotIn('re.match(r"^([0-9a-f]{64})', inspect.getsource(A))


class FinalR5(FinalR1):
    """整体验收 r5 + r6 协调方决定：结论 60 秒有效（decided_at / valid_until / head_sha）；第二遍耗时与第二遍期间 PR 变化；
    更正稿原稿日期整体解析；算式后缀与仅 X 来源经 route_pr 不可发布；配对稿单版链接失败两版都不可发布。"""
    MACRO = TITLE + fred_line() + DISC

    def _macro(self, upd):
        self.write("state/publish-state.json", json.dumps(state(updated_at=upd.isoformat()))); self.commit("hb")
        self.git("tag", "-f", "base")
        self.draft.write_text(self.MACRO, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(self.MACRO.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr)))
        self.write(f"approvals/wang/{dr['content_sha256']}.json", json.dumps(wang(dr)))
        self.commit("macro")
        # 记录在 main 上（APPROVALS_REF=main），稿件变更须在 base..HEAD 内：把 base 设回记录之前
        return dr

    def _go(self, ticks, meta=None):
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = meta or (lambda repo, n: self.gh_meta()); R.APPROVALS_REF = "main"
        it = iter(ticks); R._real_now = lambda: next(it)
        R._http_probe = lambda u, timeout=10: (True, None)
        try:
            return R.route_pr(self.repo, 21, DATE, "daily")
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    def test_macro_baseline_publishable_with_validity(self):
        self._macro(NOW - dt.timedelta(minutes=5))
        out = self._go([NOW, NOW + dt.timedelta(seconds=1), NOW + dt.timedelta(seconds=2)])
        d = out["daily/" + self.draft.name][1]
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
        self.assertEqual(d.head_sha, self.git("rev-parse", "HEAD").strip())
        da, vu = dt.datetime.fromisoformat(d.decided_at), dt.datetime.fromisoformat(d.valid_until)
        self.assertEqual(da, NOW + dt.timedelta(seconds=1)); self.assertEqual(vu - da, dt.timedelta(seconds=60))
        self.assertTrue(R.still_valid(d, da + dt.timedelta(seconds=59)))
        self.assertFalse(R.still_valid(d, vu))
        self.assertFalse(R.still_valid(R.Decision("HOLD", ["x"]), da))

    def test_heartbeat_expires_during_second_pass_retries(self):
        # 需王总批准的宏观稿：心跳差 1 秒到 30 分钟，第二遍耗时 3 秒 → 不得返回可发布
        self._macro(NOW - R.MAC_STATUS_TTL + dt.timedelta(seconds=1))
        with self.assertRaises(RuntimeError) as cm:
            self._go([NOW, NOW + dt.timedelta(seconds=3)])
        self.assertIn("E-ROUTE-RETRY", str(cm.exception))

    def test_heartbeat_expiring_after_decided_at_is_68a_gap(self):
        # r7：心跳在 decided_at 之后才过期，属于判定到发布之间的空档（68A，FOLLOW-UP）；判定本身照常可发布
        self._macro(NOW - R.MAC_STATUS_TTL + dt.timedelta(seconds=30))
        d = self._go([NOW, NOW])["daily/" + self.draft.name][1]
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_no_third_pass_and_no_early_cutoff(self):
        # r7：不再按 end+120 秒做第三遍；06:58:30 开始、06:58:31 结束的路由照常可发布（截止仍是 07:00）
        self._macro(dt.datetime(2026, 1, 5, 6, 55, tzinfo=SGT))
        t = dt.datetime(2026, 1, 5, 6, 58, 30, tzinfo=SGT)
        calls = []
        real = R._route_one
        def spy(*a, **k):
            calls.append(a[5]); return real(*a, **k)
        R._route_one = spy
        try:
            d = self._go([t, t + dt.timedelta(seconds=1)])["daily/" + self.draft.name][1]
        finally:
            R._route_one = real
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
        self.assertEqual(calls, [t, t + dt.timedelta(seconds=1)])            # 只有两遍
        self.assertEqual(dt.datetime.fromisoformat(d.decided_at), t + dt.timedelta(seconds=1))
        self.assertEqual(dt.datetime.fromisoformat(d.valid_until), t + dt.timedelta(seconds=61))

    def test_routing_started_before_0655_follows_old_rules(self):
        # 06:55 前开始、跨过 06:55 结束 → 原规则：E-ROUTE-RETRY；06:55 前开始且结束也在 06:55 前 → 照常
        self._macro(dt.datetime(2026, 1, 5, 6, 50, tzinfo=SGT))
        t = dt.datetime(2026, 1, 5, 6, 54, 59, tzinfo=SGT)
        with self.assertRaises(RuntimeError) as cm:
            self._go([t, t + dt.timedelta(seconds=2)])
        self.assertIn("E-ROUTE-RETRY", str(cm.exception))
        d = self._go([t - dt.timedelta(seconds=5), t])["daily/" + self.draft.name][1]
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)
        t7 = dt.datetime(2026, 1, 5, 6, 59, 59, tzinfo=SGT)                  # 跨 07:00 同样重跑
        with self.assertRaises(RuntimeError):
            self._go([t7, t7 + dt.timedelta(seconds=2)])

    def test_decided_at_recorded_before_external_checks(self):
        # r7 BLOCKER 1：decided_at 先记，PR 与远端 main 的外部核对在其后
        self._macro(NOW - dt.timedelta(minutes=5))
        log = []
        ticks = iter([NOW, NOW + dt.timedelta(seconds=1)])
        def now_():
            v = next(ticks); log.append(("now", v)); return v
        def gh(repo, n):
            log.append(("gh",)); return self.gh_meta()
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr, R.APPROVALS_REF, R._real_now = gh, "main", now_
        R._http_probe = lambda u, timeout=10: (True, None)
        try:
            d = R.route_pr(self.repo, 21, DATE, "daily")["daily/" + self.draft.name][1]
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4
        self.assertEqual(dt.datetime.fromisoformat(d.decided_at), NOW + dt.timedelta(seconds=1))
        last_now = max(i for i, e in enumerate(log) if e[0] == "now")
        self.assertEqual(log[-1], ("gh",)); self.assertGreater(len(log) - 1, last_now)

    def _meta_changing(self, change):
        calls = []
        def gh(repo, n):
            calls.append(1); m = self.gh_meta()
            return change(m) if len(calls) >= 3 else m      # 第 1 次取 PR、第 2 次第一遍后核对；第 3 次是记下 decided_at 之后的外部核对
        return gh

    def test_pr_head_changes_during_second_pass(self):
        self._macro(NOW - dt.timedelta(minutes=5))
        with self.assertRaises(RuntimeError) as cm:
            self._go([NOW, NOW, NOW], meta=self._meta_changing(lambda m: dict(m, headRefOid="2" * 40)))
        self.assertIn("E-ROUTE-PR-FILES", str(cm.exception))

    def test_pr_closed_during_second_pass(self):
        self._macro(NOW - dt.timedelta(minutes=5))
        with self.assertRaises(RuntimeError) as cm:
            self._go([NOW, NOW, NOW], meta=self._meta_changing(lambda m: dict(m, state="CLOSED")))
        self.assertIn("no longer open", str(cm.exception))

    def test_orig_date_full_parse(self):
        f = R._orig_date_sgt
        self.assertEqual(f("2026-01-05"), "2026-01-05")
        self.assertEqual(f("2026-01-05T07:00:00+08:00"), "2026-01-05")
        self.assertEqual(f("2026-01-05T23:30:00-08:00"), "2026-01-06")     # 按 SGT 换算
        self.assertEqual(f("2026-01-04T17:00:00Z"), "2026-01-05")
        self.assertEqual(f("2026-01-05T10:00:00"), "2026-01-05")            # 不带时区按 SGT
        for bad in ("2026-01-05bogus", "2026-01-05 junk", "2026-02-30", "2026-01-05T25:00:00", None, 20260105, ""):
            self.assertIsNone(f(bad), bad)

    def _pub(self, date_line):
        import tempfile as _t
        root = Path(_t.mkdtemp()); bare = root / "site.git"; site = root / "site"
        run = lambda *a, cwd=None: self.assertEqual(self.sp.run(["git", *a], cwd=cwd, env=self.env, capture_output=True).returncode, 0, a)
        run("init", "-q", "--bare", str(bare)); run("init", "-q", "-b", "main", str(site))
        p = site / "content/posts/daily/2026-01-05-d1.md"; p.parent.mkdir(parents=True)
        p.write_text("---\ntitle: 日报\n" + date_line + "\n---\n" + INFER + DISC, encoding="utf-8")
        run("add", "-A", cwd=site); run("commit", "-qm", "pub", cwd=site)
        run("remote", "add", "origin", str(bare), cwd=site); run("push", "-q", "origin", "main", cwd=site)
        run("fetch", "-q", "origin", cwd=site)
        return site

    def test_correction_orig_date_bogus_suffix_fails(self):
        # 站点 main 原稿 date: 2026-01-05bogus → 失败；带时区换算到 SGT 后是 01-06 → 与更正稿日期不符
        self._correction_pr()
        later = dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT)
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True
        try:
            for line, want in (("date: 2026-01-05bogus", "E-ROUTE-CORRECTION-TARGET"),
                               ("date: '2026-01-05T23:30:00-08:00'", "E-ROUTE-CORRECTION-DATE")):
                d = self.run_pr(now=later, site=self._pub(line))
                self.assertFalse(d.publishable, line); self.assertIn(want, d.codes, line)
            d = self.run_pr(now=later, site=self._pub("date: 2026-01-05T07:00:00+08:00"))
            self.assertTrue(d.publishable, d.codes)
        finally:
            R._site_remote_ok = o

    def test_formula_suffix_not_publishable_via_route_pr(self):
        bad = TITLE + fred_line("UNRATE 差值 +0.2（由原始数据计算；算式：4.2-4.0=0.2x≈9.99）") + DISC
        self._macro(NOW - dt.timedelta(minutes=5))
        self.draft.write_text(bad, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(bad.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr)))
        self.write(f"approvals/wang/{dr['content_sha256']}.json", json.dumps(wang(dr))); self.commit("bad")
        sc, d = self._go([NOW, NOW, NOW])["daily/" + self.draft.name]
        self.assertFalse(d.publishable); self.assertIn("E-FORMULA-MISMATCH", sc["error_codes"])

    def test_x_only_daily_not_publishable_via_route_pr(self):
        from helpers import x_line
        t = TITLE + x_line() + DISC
        self.write("state/publish-state.json", json.dumps(state())); self.commit("st"); self.git("tag", "-f", "base")
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr))); self.commit("x")
        sc, d = self._go([NOW, NOW, NOW])["daily/" + self.draft.name]
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def _route_daily(self, t):
        self.write("state/publish-state.json", json.dumps(state())); self.commit("st"); self.git("tag", "-f", "base")
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr))); self.commit("d")
        return self._go([NOW, NOW, NOW])["daily/" + self.draft.name]

    def test_same_number_other_metric_not_publishable_via_route_pr(self):
        # #32 反例一：同一个数字（90%），但对象/指标不同（原文是 MMLU，断言写 GSM8K）；有效 Codex APPROVED 也不可发布
        from helpers import ARXIV_LOC
        sc, d = self._route_daily(TITLE + arxiv_line("模型在 GSM8K 上达到 90% 准确率。", locator=ARXIV_LOC) + DISC)
        self.assertFalse(d.publishable); self.assertIn("E-SUPPORT-LOCATOR-MISMATCH", sc["error_codes"])

    def test_locator_missing_not_publishable_via_route_pr(self):
        sc, d = self._route_daily(TITLE + arxiv_line(locator=None) + DISC)
        self.assertFalse(d.publishable); self.assertIn("E-SUPPORT-LOCATOR-MISSING", sc["error_codes"])

    def test_x_plus_unsupporting_nonx_not_publishable_via_route_pr(self):
        # #32 反例二（迁移自旧库 #51）：X 来源 + 一条并不支撑断言的非 X 来源；有效 Codex APPROVED 也不可发布
        from helpers import x_line, ARXIV_LOC, ARXIV_ID
        line = x_line() + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{ARXIV_LOC}〕"
        sc, d = self._route_daily(TITLE + line + DISC)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_paragraph_heading_without_locator_not_publishable_via_route_pr(self):
        # #32 r2：段落、标题里带来源但没写支持位置（或位置不支持断言）→ 有效 Codex APPROVED 也不可发布
        from helpers import ARXIV_LOC, ARXIV_ID, XPOST_ID
        asrc = f"`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        xsrc = f"`raw/{DATE}/x/01.json` · https://x.com/i/status/{XPOST_ID}"
        for body, want in ((f"模型在 GSM8K 上达到 90%。见 {asrc}\n", "E-SUPPORT-LOCATOR-MISSING"),
                           (f"## 模型在 GSM8K 上达到 90% {asrc} 〔原文：{ARXIV_LOC}〕\n", "E-SUPPORT-LOCATOR-MISMATCH"),
                           (f"该方法远超所有对手。见 {xsrc} 与 {asrc}\n", "E-X-ONLY")):
            sc, d = self._route_daily(TITLE + arxiv_line() + "\n" + body + DISC)
            self.assertFalse(d.publishable, body); self.assertIn(want, sc["error_codes"], body)

    def test_paragraph_with_locator_publishable_via_route_pr(self):
        from helpers import ARXIV_LOC, ARXIV_ID
        asrc = f"`raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1"
        sc, d = self._route_daily(TITLE + arxiv_line() + f"\n模型在 MMLU 上达到 90%。见 {asrc} 〔原文：{ARXIV_LOC}〕\n" + DISC)
        self.assertTrue(d.publishable, (sc["error_codes"], d.codes))

    def test_fred_unit_mismatch_not_publishable_via_route_pr(self):
        # #32 r3：FRED 序列单位为 Percent，断言写“4.2 倍”→ 有效 Codex 与王总批准也不可发布
        bad = TITLE + fred_line("UNRATE 为 4.2 倍。") + DISC
        self.write("state/publish-state.json", json.dumps(state())); self.commit("st"); self.git("tag", "-f", "base")
        self.draft.write_text(bad, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(bad.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr)))
        self.write(f"approvals/wang/{dr['content_sha256']}.json", json.dumps(wang(dr))); self.commit("bad")
        sc, d = self._go([NOW, NOW, NOW])["daily/" + self.draft.name]
        self.assertFalse(d.publishable); self.assertIn("E-SUPPORT-LOCATOR-MISMATCH", sc["error_codes"])

    def _route_daily_src(self, t, summary):
        # r5：替换存档 arXiv 摘要（同步改 MANIFEST），再走发布路由
        from helpers import ARXIV_ID, FILES, write_manifest
        files = dict(FILES)
        files["arxiv/cs.AI.xml"] = f"<feed><entry><id>http://arxiv.org/abs/{ARXIV_ID}v1</id><summary>{summary}</summary></entry></feed>"
        day = self.repo / "raw" / DATE
        (day / "arxiv" / "cs.AI.xml").write_text(files["arxiv/cs.AI.xml"], encoding="utf-8")
        write_manifest(day, files)
        self.commit("raw-b")
        return self._route_daily(t)

    def test_b1_wrong_object_negation_not_publishable_via_route_pr(self):
        # #32 r5（审查 r4 HIGH B1）：原文 A 未达到、B 达到；断言“B 未能达到”→ 有效 Codex APPROVED 也不可发布
        loc = "Model A does not reach 90%; on MMLU, Model B reaches 90%."
        sc, d = self._route_daily_src(TITLE + arxiv_line("Model B 在 MMLU 上未能达到 90%。", locator=loc) + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-SUPPORT-LOCATOR-MISMATCH", sc["error_codes"])

    def test_b2_right_object_publishable_via_route_pr(self):
        loc = "Model A does not reach 90%; on MMLU, Model B reaches 90%."
        sc, d = self._route_daily_src(TITLE + arxiv_line("Model B 在 MMLU 上达到 90%。", locator=loc) + DISC, loc)
        self.assertNotIn("E-SUPPORT-LOCATOR-MISMATCH", sc["error_codes"]); self.assertTrue(d.publishable, (sc["error_codes"], d.codes))

    def test_b1_with_x_still_x_only_via_route_pr(self):
        # B1 的错误非 X 支持不能解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "Model A does not reach 90%; on MMLU, Model B reaches 90%."
        line = x_line("Model B 在 MMLU 上未能达到 90%。") + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_keyless_swap_with_x_still_x_only_via_route_pr(self):
        # #32 r6（r5 审查 HIGH）：无数字、无代号的分句借用另一对象的否定（A 不可靠 → B 不可靠），非 X 来源不支撑，不能解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "Model A is not reliable; Model B is reliable."
        claim = "Model B is not reliable."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_keyless_right_pairing_with_x_publishable_via_route_pr(self):
        # 对照：断言与原文同一对象的否定状态一致 → 非 X 来源支撑，可发布
        from helpers import x_line, ARXIV_ID
        loc = "Model A is not reliable; Model B is reliable."
        claim = "Model B is reliable."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertNotIn("E-X-ONLY", sc["error_codes"]); self.assertTrue(d.publishable, (sc["error_codes"], d.codes))

    def test_keyless_negation_word_pairing_with_x_still_x_only_via_route_pr(self):
        # #32 r6 审查 HIGH：否定词不参与配对；“The baseline does not improve recall.” 不能借用 new method 的否定解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "The new method does not improve recall, and the baseline improves recall clearly."
        claim = "The baseline does not improve recall."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_keyless_predicate_overlap_with_x_still_x_only_via_route_pr(self):
        # #32 r7 审查 HIGH：baseline 的断言与 new method 分句共享谓语词更多，也不能借用其否定解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "The new method does not improve recall on long documents; the baseline improves recall."
        claim = "The baseline does not improve recall on long documents."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_keyless_tied_other_objects_with_x_still_x_only_via_route_pr(self):
        # #32 r7 审查：两个同状态的并列候选（first/second system）不能替 replacement 配对、解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "The first system processes audio quickly; The second system processes audio quickly; The replacement does not process audio."
        claim = "The replacement processes audio quickly."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_keyless_alias_with_x_still_x_only_via_route_pr(self):
        # #32 r8 审查 HIGH：异名对象（substitute 对 replacement）不能借用 baseline 分句的否定解除 E-X-ONLY
        from helpers import x_line, ARXIV_ID
        loc = "The baseline does not improve recall on long documents; the replacement improves recall."
        claim = "The substitute does not improve recall on long documents."
        line = x_line(claim) + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{loc}〕"
        sc, d = self._route_daily_src(TITLE + line + DISC, loc)
        self.assertFalse(d.publishable); self.assertIn("E-X-ONLY", sc["error_codes"])

    def test_x_plus_supporting_nonx_publishable_via_route_pr(self):
        # 对照：X + 经原文支持位置核对确实支撑的非 X 来源 → 可发布
        from helpers import x_line, ARXIV_LOC, ARXIV_ID
        line = x_line("模型在 MMLU 上达到 90% 准确率。") + f" ; `raw/{DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/{ARXIV_ID}v1 〔原文：{ARXIV_LOC}〕"
        sc, d = self._route_daily(TITLE + line + DISC)
        self.assertNotIn("E-X-ONLY", sc["error_codes"]); self.assertTrue(d.publishable, (sc["error_codes"], d.codes))

    def test_pair_one_link_fails_both_unpublishable(self):
        self.write("state/publish-state.json", json.dumps(state())); self.commit("st"); self.git("tag", "-f", "base")
        zh = INFER + "\n" + DISC
        en = TITLE + arxiv_line("The authors report MMLU 90%.") + "\nThis article does not constitute investment advice.\n"
        enp = self.draft.with_name(self.draft.name[:-3] + ".en.md")
        self.draft.write_text(zh, encoding="utf-8"); enp.write_text(en, encoding="utf-8")
        hz, he = hashlib.sha256(zh.encode()).hexdigest(), hashlib.sha256(en.encode()).hexdigest()
        self.write(f"approvals/codex/{hz}.json", json.dumps(codex({"content_sha256": hz, "draft_id": "daily-2026-01-05-d1"}, pair_sha256=he)))
        self.write(f"approvals/codex/{he}.json", json.dumps(codex({"content_sha256": he, "draft_id": "daily-2026-01-05-d1-en"}, pair_sha256=hz)))
        self.commit("pair")
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"; R._real_now = lambda: NOW
        try:
            R._http_probe = lambda u, timeout=10: (True, None)
            ok = R.route_pr(self.repo, 21, DATE, "daily")
            self.assertTrue(all(d.publishable for _, d in ok.values()), [d.codes for _, d in ok.values()])
            R._http_probe = lambda u, timeout=10: (False, "unreachable")
            out = R.route_pr(self.repo, 21, DATE, "daily")
            self.assertTrue(all(not d.publishable for _, d in out.values()))
            self.assertTrue(any("E-ROUTE-LINK-UNREACHABLE" in d.codes for _, d in out.values()))
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4


class FinalR6(FinalR5):
    """整体验收 r6：更正日期可见性；真实 origin/main（本地 bare remote）读取批准记录与最终外部核对的竞态。"""
    def test_hidden_correction_date_not_visible(self):
        for head in ("## 更正 <span hidden>2026-01-06</span>", '## 更正 <span style="display:none">2026-01-06</span>',
                     '## 更正 <span aria-hidden="true">2026-01-06</span>', "## 更正 <!-- 2026-01-06 -->",
                     '## 更正 <span class="sr-only">2026-01-06</span>', "## 更正 <template>2026-01-06</template>"):
            self.assertNotIn("2026-01-06", R._heading_shown(head), head)
        self.assertIn("2026-01-06", R._heading_shown("## 更正 <b>2026-01-06</b>"))
        self.assertIn("2026-01-06", R._heading_shown("## 更正 <span hidden>旧</span> 2026-01-06"))

    def test_hidden_correction_date_via_route_pr(self):
        t = ("---\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + INFER
             + "\n## 更正 <span hidden>2026-01-06</span>\n" + DISC)
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write("state/publish-state.json", json.dumps(state(updated_at="2026-01-06T09:50:00+08:00")))
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr, reviewed_at="2026-01-06T09:30:00+08:00")))
        self.commit("corr-hidden")
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True
        try:
            d = self.run_pr(now=dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT), site=self._site())
        finally:
            R._site_remote_ok = o
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-CORRECTION-NOTE", d.codes)

    # —— 真实 origin/main：APPROVALS_REF 不替换
    def _with_origin(self):
        import tempfile as _t
        self.bare = Path(_t.mkdtemp()) / "data.git"
        self.sp.run(["git", "init", "-q", "--bare", str(self.bare)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.bare))
        self._macro(NOW - dt.timedelta(minutes=5))
        self.git("push", "-q", "origin", "HEAD:refs/heads/main"); self.git("fetch", "-q", "origin")
        # 稿件改动只在 PR head 上：再加一个只改稿件的提交，不推到远端 main
        self.git("tag", "-f", "base")
        self.draft.write_text(self.MACRO + "\n", encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256((self.MACRO + "\n").encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.git("checkout", "-q", "-b", "pr")
        self.commit("draft")
        self.git("checkout", "-q", "main")
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr)))
        self.write(f"approvals/wang/{dr['content_sha256']}.json", json.dumps(wang(dr)))
        self.commit("records"); self.git("push", "-q", "origin", "HEAD:refs/heads/main"); self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "pr")

    def _go_origin(self, gh=None, ticks=(NOW, NOW)):
        o1, o3, o4 = R._gh_pr, R._real_now, R._http_probe
        R._gh_pr = gh or (lambda repo, n: self.gh_meta())
        it = iter(ticks); R._real_now = lambda: next(it)
        R._http_probe = lambda u, timeout=10: (True, None)
        try:
            self.assertEqual(R.APPROVALS_REF, "origin/main")
            return R.route_pr(self.repo, 21, DATE, "daily")["daily/" + self.draft.name][1]
        finally:
            R._gh_pr, R._real_now, R._http_probe = o1, o3, o4

    def test_real_origin_main_records(self):
        self._with_origin()
        d = self._go_origin()
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_remote_main_drift_after_decided_at_holds(self):
        self._with_origin()
        calls = []
        def gh(repo, n):
            calls.append(1)
            if len(calls) == 3:          # 记下 decided_at 之后的外部核对期间，远端 main 被推进
                c = self.git("commit-tree", "origin/main^{tree}", "-p", "origin/main", "-m", "drift").strip()
                self.git("push", "-q", "origin", c + ":refs/heads/main")
            return self.gh_meta()
        with self.assertRaises(RuntimeError) as cm:
            self._go_origin(gh)
        self.assertIn("E-ROUTE-RETRY", str(cm.exception))

    def test_pr_closed_during_final_check_holds(self):
        self._with_origin()
        calls = []
        def gh(repo, n):
            calls.append(1); m = self.gh_meta()
            return dict(m, state="CLOSED") if len(calls) == 3 else m
        with self.assertRaises(RuntimeError) as cm:
            self._go_origin(gh)
        self.assertIn("no longer open", str(cm.exception))

    def test_stale_local_origin_main_refused(self):
        self._with_origin()
        self.git("update-ref", "refs/remotes/origin/main", "base")
        with self.assertRaises(RuntimeError) as cm:
            self._go_origin()
        self.assertIn("E-ROUTE-STATE", str(cm.exception))

    def test_pair_hold_keeps_metadata(self):
        self.setup_ok()
        en = self.draft.with_name(self.draft.name[:-3] + ".en.md"); en.write_text(INFER, encoding="utf-8"); self.commit("en")
        ok, no = R.Decision("APPROVED", []), R.Decision("NEEDS_REVIEW", ["E-ROUTE-NO-CODEX"])
        o = R._route_one
        try:
            R._route_one = lambda p, *a, **k: ({"flags": {}}, no if p.endswith(".en.md") else ok)
            out = self._go([NOW, NOW])
        finally:
            R._route_one = o
        d = out["daily/" + self.draft.name][1]
        self.assertIn("E-ROUTE-PAIR-INCOMPLETE", d.codes); self.assertIsNotNone(d.head_sha); self.assertIsNotNone(d.decided_at)


class FinalR7(FromMain):
    """整体验收 r7：B4 稿件 PR 准入、医疗类兜底、顺延稿 Codex 记录作废（均走公开入口 route_pr）。"""
    T0658 = FinalR1.T0658
    def setUp(self):
        FromMain.setUp(self)
        self._sleep = R._LinkProbe.RETRY_SLEEP; R._LinkProbe.RETRY_SLEEP = 0

    def tearDown(self):
        R._LinkProbe.RETRY_SLEEP = self._sleep

    run_pr = FinalR1.run_pr
    _codex_at = FinalR1._codex_at

    def _ok(self):
        self._codex_at("2026-01-05T02:25:00+08:00")
        self.write(self.wp, json.dumps(wang(self.dr))); self.commit("wang")

    # —— 1) B4
    def test_draft_pr_touching_rules_code_roadmap_template_config_not_publishable(self):
        for extra in ("scripts/markjin/route.py", "docs/roadmap.md", "scripts/markjin/lexicon.json", "layouts/x.html",
                      "hugo.toml", "review/2026-01-05.md", ".github/workflows/x.yml", "tests/test_x.py",
                      "approvals/codex/" + "1" * 64 + ".json", "state/publish-state.json", "README.md"):
            with self.subTest(extra=extra):
                self.setUp(); self._ok()
                self.git("tag", "-f", "base")
                self.draft.write_text(INFER + DISC + "\n", encoding="utf-8")
                self.write(extra, "changed\n"); self.commit("mixed")
                self.infra_on_base = False
                d = self.run_pr(now=self.T0658)
                self.assertEqual((d.state, d.publishable), ("HOLD", False), d.codes)
                self.assertIn("E-ROUTE-PR-SCOPE", d.codes)

    def test_draft_with_raw_data_and_manifest_allowed(self):
        self._ok()
        self.assertEqual(R.pr_scope_violations(["daily/a.md"], ["daily/a.md", "raw/2026-01-05/MANIFEST.sha256",
                                                                "raw/2026-01-05/arxiv/x.xml"]), [])
        self.assertEqual(R.pr_scope_violations(["daily/a.md"], ["daily/a.md", "raw/x.json", "raw/2026-01-05"]),
                         ["raw/2026-01-05", "raw/x.json"])
        d = self.run_pr(now=self.T0658)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    # —— 2) 医疗
    def test_medical_section_path_needs_wang(self):
        dr = {"draft_id": "health-2026-01-05-x", "content_sha256": "a" * 64, "date": DATE}
        self.assertTrue(R.needs_wang(dr, "daily", {}))
        self.assertFalse(R.needs_wang(dict(dr, draft_id="daily-2026-01-05-x"), "daily", {}))

    def test_codex_category_medical_needs_wang_end_to_end(self):
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(self.cp, json.dumps(codex(self.dr, category="medical"))); self.commit("rec")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)
        self.write(self.wp, json.dumps(wang(self.dr))); self.commit("wang")
        d = self.run_pr(now=self.T0658)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_bad_codex_category_invalid(self):
        from markjin.approvals import valid_codex
        self.assertTrue(valid_codex(codex(self.dr, category="medical")))
        self.assertFalse(valid_codex(codex(self.dr, category="health")))

    def test_tcm_daily_without_wang_not_publishable(self):
        text = TITLE + arxiv_line("作者声称 MMLU 90%。") + "\nTCM is used in this protocol.\n" + DISC
        self.draft.write_text(text, encoding="utf-8")
        self.dr = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.cp = f"approvals/codex/{self.dr['content_sha256']}.json"; self.commit("tcm")
        self._codex_at("2026-01-05T02:25:00+08:00")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable)

    def test_front_matter_category_medical_needs_wang(self):
        text = "---\ncategories: [Health]\n---\n" + INFER + DISC
        self.draft.write_text(text, encoding="utf-8")
        self.dr = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.cp = f"approvals/codex/{self.dr['content_sha256']}.json"; self.commit("fm")
        self._codex_at("2026-01-05T02:25:00+08:00")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    # —— 4) 顺延
    def test_deferred_previous_day_codex_void_via_route_pr(self):
        d2 = dt.datetime(2026, 1, 6, 3, 25, tzinfo=SGT)
        ds = {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE,
              "content_sha256": self.dr["content_sha256"]}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(d2 - dt.timedelta(minutes=1)).isoformat(),
                                                                drafts={"daily-2026-01-05-d1": ds})))
        self.write(self.cp, json.dumps(codex(self.dr, reviewed_at="2026-01-05T06:25:00+08:00"))); self.commit("d")
        d = self.run_pr(now=d2)
        # r12：顺延到 D 日只认 <sha>.<D>.json；只有首日的 <sha>.json → 没有可用的 Codex 记录
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)

    def test_deferred_same_day_codex_publishable_via_route_pr(self):
        d2 = dt.datetime(2026, 1, 6, 3, 25, tzinfo=SGT)
        ds = {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE,
              "content_sha256": self.dr["content_sha256"]}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(d2 - dt.timedelta(minutes=1)).isoformat(),
                                                                drafts={"daily-2026-01-05-d1": ds})))
        self.write(self.cp.replace(".json", ".2026-01-06.json"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00")))
        self.commit("d")                                   # r12：顺延稿重审记录写 <sha>.<D>.json
        d = self.run_pr(now=d2)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)


class FinalR8(FinalR7):
    """整体验收 r8：中英配对稿取两版审批类型并集；front matter 别名 fail-closed（经 route_pr）；路由围栏长度。"""

    def _pair(self, zh_extra_fm="", en_extra_fm=""):
        en = self.repo / "daily" / "2026-01-05-d1.en.md"
        zh_text = (f"---\n{zh_extra_fm}\n---\n" if zh_extra_fm else "") + INFER + DISC
        en_text = (f"---\n{en_extra_fm}\n---\n" if en_extra_fm else "") + INFER + "\nThis article does not constitute investment advice.\n"
        self.draft.write_text(zh_text, encoding="utf-8"); en.write_text(en_text, encoding="utf-8")
        zs, es = (hashlib.sha256(t.encode()).hexdigest() for t in (zh_text, en_text))
        zd = {"content_sha256": zs, "draft_id": "daily-2026-01-05-d1"}
        ed = {"content_sha256": es, "draft_id": "daily-2026-01-05-d1-en"}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        ts = "2026-01-05T02:25:00+08:00"
        self.write(f"approvals/codex/{zs}.json", json.dumps(codex(zd, reviewed_at=ts, pair_sha256=es)))
        self.write(f"approvals/codex/{es}.json", json.dumps(codex(ed, reviewed_at=ts, pair_sha256=zs, log_path="review/codex/en.log")))
        self.commit("pair")
        return zd, ed, en

    def _route_pair(self):
        o1, o2, o3, o4 = R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe
        R._gh_pr = lambda repo, n: self.gh_meta(); R.APPROVALS_REF = "main"
        R._real_now = lambda: self.T0658; R._http_probe = lambda u, timeout=10: (True, None)
        try:
            return R.route_pr(self.repo, 21, DATE, "daily")
        finally:
            R._gh_pr, R.APPROVALS_REF, R._real_now, R._http_probe = o1, o2, o3, o4

    def test_pair_union_requires_wang_for_both(self):
        zd, ed, en = self._pair(zh_extra_fm="categories: [Health]")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})
        # 只有中文版有王总记录 → 两版都不可发布（英文版缺自己的王总记录）
        self.write(f"approvals/wang/{zd['content_sha256']}.json", json.dumps(wang(zd))); self.commit("wang zh")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        self.assertIn("E-ROUTE-NO-WANG", out["daily/2026-01-05-d1.en.md"][1].codes)
        # 两版各自都有 → 可发布
        self.write(f"approvals/wang/{ed['content_sha256']}.json", json.dumps(wang(ed))); self.commit("wang en")
        out = self._route_pair()
        self.assertTrue(all(d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})

    def test_pair_union_from_english_side(self):
        zd, ed, en = self._pair(en_extra_fm="tags: [TCM]")
        self.write(f"approvals/wang/{ed['content_sha256']}.json", json.dumps(wang(ed))); self.commit("wang en")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        self.assertIn("E-ROUTE-NO-WANG", out["daily/2026-01-05-d1.md"][1].codes)

    def test_plain_pair_needs_only_codex(self):
        self._pair()
        out = self._route_pair()
        self.assertTrue(all(d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})

    def test_yaml_alias_category_fail_closed_via_route_pr(self):
        text = "---\nnote: &topic Health\ncategories: *topic\n---\n" + INFER + DISC
        self.draft.write_text(text, encoding="utf-8")
        self.dr = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.cp = f"approvals/codex/{self.dr['content_sha256']}.json"; self.commit("alias")
        self._codex_at("2026-01-05T02:25:00+08:00")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertEqual(d.state, "HOLD")

    def test_longer_closing_fence_keeps_disclaimer_visible(self):
        for fence in (("```", "````"), ("````", "`````"), ("~~~", "~~~~")):
            t = f"正文\n{fence[0]}\ncode\n{fence[1]}\n本文不含投资建议。\n"
            self.assertTrue(R.has_disclaimer(t, False), fence)
        for t in ("正文\n````\ncode\n```\n本文不含投资建议。\n", "正文\n```\ncode\n~~~\n本文不含投资建议。\n", "```\n本文不含投资建议。\n"):
            self.assertFalse(R.has_disclaimer(t, False), t)


class FinalR9(FinalR8):
    """整体验收 r9：解析出的 categories 全部参与审批类型判定（路径、categories、正文词表取并集）；state-change 重复键判失败。"""

    def _single(self, fm):
        text = f"---\n{fm}\n---\n" + INFER + DISC
        self.draft.write_text(text, encoding="utf-8")
        self.dr = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.cp = f"approvals/codex/{self.dr['content_sha256']}.json"; self.commit("fm " + fm[:20])
        self._codex_at("2026-01-05T02:25:00+08:00")
        return self.run_pr(now=self.T0658)

    def test_wang_categories_need_wang_via_route_pr(self):
        for fm in ("categories: [religion]", "categories: [macro]", "categories: [Health]", "categories: [tongyi]",
                   "categories: [card]", "categories: [信号卡]", "categories:\n  - 宏观", "tags: [佛学]",
                   "categories:\n  main: macro", "category: tongyi", "topics: [cards]"):
            d = self._single(fm)
            self.assertFalse(d.publishable, fm)
            # 宏观类别还会让自检按宏观稿从严（可能先报 E-ROUTE-UNCLEAR）；其余都应停在缺王总批准
            self.assertTrue("E-ROUTE-NO-WANG" in d.codes or "E-ROUTE-UNCLEAR" in d.codes, (fm, d.codes))

    def test_unknown_category_needs_wang(self):
        for fm in ("categories: [AI]", "categories: [misc]", "categories: []", "categories: null"):
            d = self._single(fm)
            self.assertFalse(d.publishable, fm); self.assertIn("E-ROUTE-NO-WANG", d.codes, fm)

    def test_daily_category_codex_only(self):
        for fm in ("categories: [daily]", "categories: [日报]\ntags: [digest]", "title: 普通日报"):
            d = self._single(fm)
            self.assertTrue(d.publishable, (fm, d.codes))

    def test_religion_category_with_wang_publishable(self):
        d = self._single("categories: [religion]")
        self.assertFalse(d.publishable)
        self.write(f"approvals/wang/{self.dr['content_sha256']}.json", json.dumps(wang(self.dr))); self.commit("wang")
        d = self.run_pr(now=self.T0658)
        self.assertTrue(d.publishable, d.codes)

    def test_pair_union_with_category(self):
        zd, ed, en = self._pair(zh_extra_fm="categories: [religion]")
        self.write(f"approvals/wang/{zd['content_sha256']}.json", json.dumps(wang(zd))); self.commit("wang zh")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        self.assertIn("E-ROUTE-NO-WANG", out["daily/2026-01-05-d1.en.md"][1].codes)

    def test_labels_need_wang_shared_with_correction(self):
        self.assertTrue(R.labels_need_wang({"categories": ["daily", "macro"]}))
        self.assertTrue(R.labels_need_wang({"Categories": ["x"]}))
        self.assertFalse(R.labels_need_wang({"categories": ["daily"], "title": "宏观"}))

    def test_state_change_cli_duplicate_keys_fail(self):
        import subprocess, tempfile as _t
        d = Path(_t.mkdtemp()); p = d / "publish-state.json"
        good = json.dumps(state())
        dup = good[:-1] + ', "drafts": {}}'
        p.write_text(dup, encoding="utf-8"); before = p.read_bytes()
        cli = Path(R.__file__).resolve().parents[1] / "state-change.py"
        r = subprocess.run(["python3", str(cli), "heartbeat", "--state", str(p), "--mac-online", "true",
                            "--now", NOW.isoformat()], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("E-STATE-CHANGE-INVALID", r.stdout); self.assertEqual(p.read_bytes(), before)
        p.write_text(good, encoding="utf-8")
        r = subprocess.run(["python3", str(cli), "apply", "--state", str(p), "--change", '{"kind": "heartbeat", "kind": "x"}'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("E-STATE-CHANGE-INVALID", r.stdout)
        from markjin import statechange as SC
        with self.assertRaises(SC.StateChangeError):
            SC.loads_strict('{"a": 1, "a": 2}')


class FinalR10(FinalR9):
    """整体验收 r10：分类键与 selfcheck 共用（keywords 进入审批判定）；缺 PyYAML 结构化 HOLD。"""

    def test_shared_keys_object(self):
        from markjin import fmkeys, selfcheck
        self.assertIs(R.CAT_KEYS, fmkeys.FM_CATEGORY_KEYS); self.assertIs(selfcheck.FM_CATEGORY_KEYS, fmkeys.FM_CATEGORY_KEYS)
        self.assertTrue(R.labels_need_wang({"keywords": ["AI"]}))
        self.assertTrue(R.labels_need_wang({"Keywords": "macro"}))
        self.assertFalse(R.labels_need_wang({"keywords": ["daily"]}))

    def test_single_unknown_keywords_needs_wang(self):
        for fm in ("keywords: [AI]", "keywords: AI", "keyword: [misc]", "keywords: []"):
            d = self._single(fm)
            self.assertFalse(d.publishable, fm); self.assertIn("E-ROUTE-NO-WANG", d.codes, (fm, d.codes))
        d = self._single("keywords: [daily]")
        self.assertTrue(d.publishable, d.codes)

    def test_single_unknown_keywords_with_wang_publishable(self):
        d = self._single("keywords: [AI]")
        self.assertFalse(d.publishable)
        self.write(f"approvals/wang/{self.dr['content_sha256']}.json", json.dumps(wang(self.dr))); self.commit("wang")
        d = self.run_pr(now=self.T0658)
        self.assertTrue(d.publishable, d.codes)

    def test_pair_keywords_both_sides(self):
        zd, ed, en = self._pair(zh_extra_fm="keywords: [AI]", en_extra_fm="keywords: [AI]")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        for k, (_, d) in out.items():
            self.assertIn("E-ROUTE-NO-WANG", d.codes, k)
        self.write(f"approvals/wang/{zd['content_sha256']}.json", json.dumps(wang(zd))); self.commit("wang zh")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        self.assertIn("E-ROUTE-NO-WANG", out["daily/2026-01-05-d1.en.md"][1].codes)
        self.write(f"approvals/wang/{ed['content_sha256']}.json", json.dumps(wang(ed))); self.commit("wang en")
        out = self._route_pair()
        self.assertTrue(all(d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})

    def test_pair_keywords_one_side_union(self):
        zd, ed, en = self._pair(en_extra_fm="keywords: [AI]")
        self.write(f"approvals/wang/{ed['content_sha256']}.json", json.dumps(wang(ed))); self.commit("wang en")
        out = self._route_pair()
        self.assertTrue(all(not d.publishable for _, d in out.values()))
        self.assertIn("E-ROUTE-NO-WANG", out["daily/2026-01-05-d1.md"][1].codes)

    def test_missing_pyyaml_route_raises_structured(self):
        import sys
        from markjin import deps
        saved = sys.modules.get("yaml"); sys.modules["yaml"] = None
        try:
            with self.assertRaises(deps.DependencyError) as cm:
                R.route_pr(self.repo, 21, DATE, "daily")
            self.assertTrue(str(cm.exception).startswith("E-DEP-PYYAML"))
            self.assertIsInstance(cm.exception, RuntimeError)
        finally:
            if saved is None:
                sys.modules.pop("yaml", None)
            else:
                sys.modules["yaml"] = saved

    def test_missing_pyyaml_cli_hold(self):
        import subprocess, tempfile as _t, os
        fake = Path(_t.mkdtemp()); (fake / "yaml.py").write_text("raise ImportError('PyYAML not installed (test)')\n")
        cli = Path(R.__file__).resolve().parents[1] / "route.py"
        env = dict(os.environ, PYTHONPATH=str(fake))
        r = subprocess.run(["python3", str(cli), "--pr", "21", "--repo", str(self.repo), "--date", DATE, "--card-type", "daily"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1, r.stderr); self.assertNotIn("Traceback", r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["state"], "HOLD"); self.assertEqual(out["codes"], ["E-DEP-PYYAML"]); self.assertFalse(out["publishable"])


class FinalR11(unittest.TestCase):
    """整体验收 r11：所有 json.load/json.loads 入口都拒绝重复键；gh 输出重复键判失败；心跳注释与逻辑一致。"""

    def test_every_json_entry_rejects_duplicates(self):
        import re
        pkg = Path(R.__file__).resolve().parent
        found = []
        for f in sorted(list(pkg.glob("*.py")) + list(pkg.parent.glob("*.py"))):
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"(?<![A-Za-z_])_?json\.loads?\(", line):
                    found.append((f.name, n, line.strip()))
        self.assertTrue(found)
        for name, n, line in found:
            self.assertIn("object_pairs_hook", line, f"{name}:{n} {line}")   # 只剩带 hook 的底层调用

    def test_gh_duplicate_keys_runtime_error(self):
        import os, stat, tempfile
        d = Path(tempfile.mkdtemp()); gh = d / "gh"
        gh.write_text('#!/bin/sh\necho \'{"state": "open", "state": "closed"}\'\n'); gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        old = os.environ["PATH"]; os.environ["PATH"] = f"{d}:{old}"
        try:
            with self.assertRaises(RuntimeError) as cm:
                R._gh_pr(d, 1)
            self.assertTrue(str(cm.exception).startswith("E-ROUTE-PR-FILES"))
        finally:
            os.environ["PATH"] = old

    def test_heartbeat_comment_matches_logic(self):
        src = Path(R.__file__).read_text(encoding="utf-8")
        self.assertNotIn("未知 → 按离线处理", src); self.assertIn('_hold("E-ROUTE-MAC-STALE")', src)


class FinalR11Docs(unittest.TestCase):
    def test_macro_prediction_doc_current_rule(self):
        t = (Path(R.__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn("历史口径，已被下方", t); self.assertNotIn("由人工审查把关（按 09:07 决定不另加硬拦）。", t)


class FinalR12Hidden(FinalR6):
    """整体验收 r12 BLOCKER：隐藏范围按整篇正文追踪（HTML 解析器）；跨行 hidden / display:none / aria-hidden / template / 注释
    里的免责声明和更正标题都不算可见——日报与更正稿都经 route_pr。"""

    HIDERS = (("<div hidden>", "</div>"), ('<div style="display:none">', "</div>"), ('<section aria-hidden="true">', "</section>"),
              ("<template>", "</template>"), ("<!--", "-->"), ("<div hidden>", ""))   # 最后一项：未闭合 → 隐藏到文末

    def test_visible_text_cross_line(self):
        for o, c in self.HIDERS:
            t = f"正文\n{o}\n本文不含投资建议。\n{c}\n"
            self.assertFalse(R.has_disclaimer(t, False), o)
            t2 = f"正文\n{o}\n## 更正 2026-01-06\n{c}\n"
            self.assertNotIn("2026-01-06", R.visible_text(t2), o)
        self.assertTrue(R.has_disclaimer("正文\n<div>\n本文不含投资建议。\n</div>\n", False))
        self.assertTrue(R.has_disclaimer("<div hidden>\nx\n</div>\n本文不含投资建议。\n", False))
        self.assertTrue(R.has_disclaimer('<div hidden><div>x</div>\n</div>\n本文不含投资建议。\n', False))

    def _daily(self, body):
        t = INFER + body
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr, reviewed_at="2026-01-05T02:25:00+08:00")))
        self.commit("daily hidden")
        o = R.DISCLAIMER_FROM; R.DISCLAIMER_FROM = "2026-01-01"    # 把门禁起始日提前，使 2026-01-05 的日报受免责声明门禁约束
        try:
            return self.run_pr(now=self.T0658)
        finally:
            R.DISCLAIMER_FROM = o

    def test_daily_hidden_disclaimer_via_route_pr(self):
        for o, c in self.HIDERS:
            d = self._daily(f"\n{o}\n{DISC.strip()}\n{c}\n")
            self.assertFalse(d.publishable, o); self.assertIn("E-ROUTE-DISCLAIMER-MISSING", d.codes, (o, d.codes))
        d = self._daily("\n<div>\n" + DISC.strip() + "\n</div>\n")
        self.assertNotIn("E-ROUTE-DISCLAIMER-MISSING", d.codes, d.codes)

    def _corr(self, extra):
        t = "---\ncorrects: daily-2026-01-05-d1\ncorrected_at: 2026-01-06\n---\n" + INFER + extra
        self.draft.write_text(t, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(t.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write("state/publish-state.json", json.dumps(state(updated_at="2026-01-06T09:50:00+08:00")))
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr, reviewed_at="2026-01-06T09:30:00+08:00")))
        self.commit("corr")
        o = R._site_remote_ok; R._site_remote_ok = lambda u: True
        try:
            return self.run_pr(now=dt.datetime(2026, 1, 6, 10, 0, tzinfo=SGT), site=self._site())
        finally:
            R._site_remote_ok = o

    def test_correction_hidden_heading_via_route_pr(self):
        for o, c in self.HIDERS:
            d = self._corr(f"\n{o}\n## 更正 2026-01-06\n{c}\n" + DISC)
            self.assertFalse(d.publishable, o); self.assertIn("E-ROUTE-CORRECTION-NOTE", d.codes, (o, d.codes))

    def test_correction_hidden_disclaimer_via_route_pr(self):
        for o, c in self.HIDERS[:5]:
            d = self._corr(f"\n## 更正 2026-01-06\n{o}\n{DISC.strip()}\n{c}\n")
            self.assertFalse(d.publishable, o); self.assertIn("E-ROUTE-DISCLAIMER-MISSING", d.codes, (o, d.codes))


class FinalR12Deferred(FinalR7):
    """整体验收 r12 HIGH（王总定）：顺延稿重审记录 approvals/codex/<sha>.<D>.json；首日只认 <sha>.json，D 日只认 <sha>.<D>.json。"""

    D2 = dt.datetime(2026, 1, 6, 3, 25, tzinfo=SGT)

    def _defer_state(self, sha=None, did="daily-2026-01-05-d1", extra=None):
        ds = {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE,
              "content_sha256": sha or self.dr["content_sha256"]}
        drafts = {did: ds}
        drafts.update(extra or {})
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.D2 - dt.timedelta(minutes=1)).isoformat(), drafts=drafts)))

    def dp(self, day, sha=None):
        return f"approvals/codex/{sha or self.dr['content_sha256']}.{day}.json"

    def test_full_cycle_real_git(self):
        # D 日（首日）：<sha>.json 获批，但 07:00 未发布 → 顺延；D+1 日写 <sha>.<D+1>.json（原文件不动）→ 可发布
        self._codex_at("2026-01-05T06:25:00+08:00")
        d1 = self.run_pr(now=self.T0658)
        self.assertTrue(d1.publishable, d1.codes)
        self._defer_state(); self.commit("deferred")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00"))); self.commit("re-review")
        d = self.run_pr(now=self.D2)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_dated_file_not_used_on_first_day(self):
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(self.dp("2026-01-05"), json.dumps(codex(self.dr, reviewed_at="2026-01-05T02:25:00+08:00"))); self.commit("dated")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)

    def test_wrong_day_file_not_used(self):
        self._defer_state()
        self.write(self.dp("2026-01-07"), json.dumps(codex(self.dr, reviewed_at="2026-01-07T02:25:00+08:00"))); self.commit("d7")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)

    def test_filename_date_mismatch_reviewed_at_fails(self):
        self._defer_state()
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-05T22:25:00+08:00"))); self.commit("mismatch")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-RECORD-INVALID", d.codes)

    def test_bad_filename_dates_fail(self):
        from markjin import approvals as A
        rec = json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00"))
        sha = self.dr["content_sha256"]
        for name in (f"{sha}.2026-02-30.json", f"{sha}.20260106.json", f"{sha}.2026-01-06.json.bak", f"{sha}..json"):
            with self.assertRaises(A.ApprovalsError, msg=name):
                A.parse_record(name, rec, A.valid_codex, dated_ok=True)
        with self.assertRaises(A.ApprovalsError):
            A.parse_record(f"{sha}.2026-01-06.json", rec, A.valid_codex, dated_ok=False)   # 王总目录不收带日期文件
        r = A.parse_record(f"{sha}.2026-01-06.json", rec, A.valid_codex, dated_ok=True)
        self.assertEqual(r["_for_date"], "2026-01-06"); self.assertTrue(A.valid_codex(r))

    def test_wang_dated_mismatch_invalid(self):
        # r13：王总目录也允许 <sha>.<D>.json，但文件名日期须等于 recorded_at 的 SGT 日期
        self._defer_state()
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00")))
        self.write(f"approvals/wang/{self.dr['content_sha256']}.2026-01-06.json", json.dumps(wang(self.dr, recorded_at="2026-01-05T22:55:00+08:00")))
        self.commit("wang dated mismatch")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-RECORD-INVALID", d.codes)

    def test_duplicate_same_day_fails(self):
        from markjin import approvals as A
        r = dict(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00"), _for_date="2026-01-06")
        with self.assertRaises(A.ApprovalsError):
            A.check_unique([r, dict(r)])
        A.check_unique([r, dict(r, _for_date=None), dict(r, _for_date="2026-01-07")])

    def test_dated_file_append_only(self):
        self._defer_state()
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00"))); self.commit("a")
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:26:00+08:00"))); self.commit("rewrite")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-APPROVALS-REWRITTEN", d.codes)


class FinalR12DeferredPair(FinalR8):
    """配对稿顺延：两版用同一个 D 的 <sha>.<D>.json，reviewed_at 相同且互相引用。"""

    D2 = dt.datetime(2026, 1, 6, 3, 25, tzinfo=SGT)

    def _deferred_pair(self, en_day="2026-01-06"):
        zd, ed, en = self._pair()
        zs, es = zd["content_sha256"], ed["content_sha256"]
        mk = lambda sha: {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE, "content_sha256": sha}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.D2 - dt.timedelta(minutes=1)).isoformat(),
                   drafts={"daily-2026-01-05-d1": mk(zs), "daily-2026-01-05-d1-en": mk(es)})))
        ts_z = "2026-01-06T02:25:00+08:00"; ts_e = ts_z if en_day == "2026-01-06" else f"{en_day}T02:25:00+08:00"
        self.write(f"approvals/codex/{zs}.2026-01-06.json", json.dumps(codex(zd, reviewed_at=ts_z, pair_sha256=es)))
        self.write(f"approvals/codex/{es}.{en_day}.json", json.dumps(codex(ed, reviewed_at=ts_e, pair_sha256=zs, log_path="review/codex/en.log")))
        self.commit("pair re-review")

    def _route_pair_at(self, now):
        o = self.T0658; self.T0658 = now
        try:
            return self._route_pair()
        finally:
            self.T0658 = o

    def test_pair_same_d_publishable(self):
        self._deferred_pair()
        out = self._route_pair_at(self.D2)
        self.assertTrue(all(d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})

    def test_pair_different_d_not_publishable(self):
        self._deferred_pair(en_day="2026-01-07")
        out = self._route_pair_at(self.D2)
        self.assertTrue(all(not d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})


class FinalR12ViaRoute(FinalR5):
    """整体验收 r12 MEDIUM：算式（第二段格式错误）与 FRED 重复键都经公开入口 route_pr 验证不可发布。"""

    def _approved(self, text):
        self._macro(NOW - dt.timedelta(minutes=5))
        self.draft.write_text(text, encoding="utf-8")
        dr = {"content_sha256": hashlib.sha256(text.encode()).hexdigest(), "draft_id": "daily-2026-01-05-d1"}
        self.write(f"approvals/codex/{dr['content_sha256']}.json", json.dumps(codex(dr)))
        self.write(f"approvals/wang/{dr['content_sha256']}.json", json.dumps(wang(dr))); self.commit("draft")
        return self._go([NOW, NOW, NOW])["daily/" + self.draft.name]

    def test_second_malformed_formula_via_route_pr(self):
        for f in ("算式：4.2-4.0=0.2；算式：4.2-4.0=未知", "算式：4.2-4.0=0.2；算式：4.2-4.1=0.2"):
            t = TITLE + fred_line("UNRATE 差值 +0.2（由原始数据计算；" + f + "）") + DISC
            sc, d = self._approved(t)
            self.assertFalse(d.publishable, f); self.assertIn("E-FORMULA-MISMATCH", sc["error_codes"], f)

    def test_two_good_formulas_via_route_pr_no_mismatch(self):
        t = TITLE + fred_line("UNRATE 差值 +0.2（由原始数据计算；算式：4.2-4.0=0.2；算式：4.0+0.2=4.2）") + DISC
        sc, d = self._approved(t)
        self.assertNotIn("E-FORMULA-MISMATCH", sc["error_codes"], sc["errors"])

    def test_fred_duplicate_key_via_route_pr(self):
        from helpers import FILES, write_manifest
        files = dict(FILES); files["fred/UNRATE.json"] = '{"series_id":"OTHER","series_id":"UNRATE","value":"4.2"}'
        day = self.repo / "raw" / DATE
        (day / "fred" / "UNRATE.json").write_text(files["fred/UNRATE.json"], encoding="utf-8")
        write_manifest(day, files)
        sc, d = self._approved(TITLE + fred_line() + DISC)
        self.assertFalse(d.publishable); self.assertIn("E-REPLAY-READ", sc["error_codes"], sc["error_codes"])


class FinalR13Deferred(FinalR12Deferred):
    """整体验收 r13（审查 bot 定）：王总记录与 Codex 对称——顺延到 D 日只认 approvals/wang/<sha>.<D>.json；
    审批类型取首日与当日 Codex 记录类别的并集（从严）。"""

    def wp_d(self, day):
        return f"approvals/wang/{self.dr['content_sha256']}.{day}.json"

    def _d2_medical(self):
        self._codex_at("2026-01-05T06:25:00+08:00")            # 首日 <sha>.json：无类别
        self._defer_state()
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00", category="medical")))

    def test_d2_medical_without_wang_not_publishable(self):
        self._d2_medical(); self.commit("d2 medical")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    def test_d2_medical_first_day_wang_not_reused(self):
        self._d2_medical()
        self.write(self.wp, json.dumps(wang(self.dr, recorded_at="2026-01-05T06:30:00+08:00"))); self.commit("d1 wang")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    def test_d2_medical_with_dated_wang_publishable(self):
        self._d2_medical()
        self.write(self.wp, json.dumps(wang(self.dr, recorded_at="2026-01-05T06:30:00+08:00")))
        self.write(self.wp_d("2026-01-06"), json.dumps(wang(self.dr, recorded_at="2026-01-06T03:00:00+08:00", channel="direct")))
        self.commit("d2 wang")
        d = self.run_pr(now=self.D2)
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_first_day_category_still_counts(self):
        # 首日 Codex 判医疗、当日重审没写类别 → 并集仍为医疗，缺当日王总批准不可发布
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(self.cp, json.dumps(codex(self.dr, reviewed_at="2026-01-05T06:25:00+08:00", category="religion")))
        self._defer_state()
        self.write(self.dp("2026-01-06"), json.dumps(codex(self.dr, reviewed_at="2026-01-06T02:25:00+08:00")))
        self.commit("d1 religion")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    def test_dated_wang_not_used_on_first_day(self):
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.T0658 - dt.timedelta(minutes=1)).isoformat())))
        self.write(self.cp, json.dumps(codex(self.dr, reviewed_at="2026-01-05T02:25:00+08:00", category="medical")))
        self.write(self.wp_d("2026-01-05"), json.dumps(wang(self.dr, recorded_at="2026-01-05T03:00:00+08:00"))); self.commit("dated wang d1")
        d = self.run_pr(now=self.T0658)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    def test_dated_wang_append_only(self):
        self._d2_medical()
        self.write(self.wp_d("2026-01-06"), json.dumps(wang(self.dr, recorded_at="2026-01-06T03:00:00+08:00"))); self.commit("w")
        self.write(self.wp_d("2026-01-06"), json.dumps(wang(self.dr, recorded_at="2026-01-06T03:01:00+08:00"))); self.commit("rw")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-APPROVALS-REWRITTEN", d.codes)

    def test_wang_dated_still_requires_v2(self):
        self._d2_medical()
        self.write(self.wp_d("2026-01-06"), json.dumps(wang_v1(self.dr, recorded_at="2026-01-06T03:00:00+08:00"))); self.commit("v1")
        d = self.run_pr(now=self.D2)
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-RECORD-V2-REQUIRED", d.codes)

    def test_wang_dup_check(self):
        from markjin import approvals as A
        sha = self.dr["content_sha256"]
        r = A.parse_record(f"{sha}.2026-01-06.json", json.dumps(wang(self.dr, recorded_at="2026-01-06T03:00:00+08:00")), A.valid_wang, dated_ok=True)
        self.assertEqual(r["_for_date"], "2026-01-06"); self.assertTrue(A.valid_wang(r)); self.assertTrue(A.is_v2(r))
        with self.assertRaises(A.ApprovalsError):
            A.check_unique([r, dict(r)])


class FinalR13DeferredPair(FinalR12DeferredPair):
    """配对稿顺延 + 医疗类：两版王总记录都用同一个 D 的 <sha>.<D>.json。"""

    def _pair_med(self, en_wang_day):
        zd, ed, en = self._pair()
        zs, es = zd["content_sha256"], ed["content_sha256"]
        mk = lambda sha: {"status": "deferred", "reason": "I-DEFERRED", "at": EOD.isoformat(), "date": DATE, "content_sha256": sha}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.D2 - dt.timedelta(minutes=1)).isoformat(),
                   drafts={"daily-2026-01-05-d1": mk(zs), "daily-2026-01-05-d1-en": mk(es)})))
        ts = "2026-01-06T02:25:00+08:00"
        self.write(f"approvals/codex/{zs}.2026-01-06.json", json.dumps(codex(zd, reviewed_at=ts, pair_sha256=es, category="medical")))
        self.write(f"approvals/codex/{es}.2026-01-06.json", json.dumps(codex(ed, reviewed_at=ts, pair_sha256=zs, log_path="review/codex/en.log", category="medical")))
        self.write(f"approvals/wang/{zs}.2026-01-06.json", json.dumps(wang(zd, recorded_at="2026-01-06T03:00:00+08:00")))
        self.write(f"approvals/wang/{es}.{en_wang_day}.json", json.dumps(wang(ed, recorded_at=f"{en_wang_day}T03:00:00+08:00")))
        self.commit("pair med")

    def test_pair_wang_same_d_publishable(self):
        self._pair_med("2026-01-06")
        out = self._route_pair_at(self.D2)
        self.assertTrue(all(d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})

    def test_pair_wang_other_d_not_publishable(self):
        self._pair_med("2026-01-05")
        out = self._route_pair_at(self.D2)
        self.assertTrue(all(not d.publishable for _, d in out.values()), {k: v[1].codes for k, v in out.items()})


class FinalR15LongForm(FinalR1):
    """整体验收 r15（审查 bot 定）：tongyi 长文更正稿经 route_pr——样本为合成 fixture（更正稿与原稿各一份，不含正文）。
    自检不再报日报断言句式码；缺王总 v2 direct 记录 → 不可发布；有记录 → 可发布。日报把 type 写成 tongyi → 失败。"""

    FIX = Path(__file__).resolve().parent / "fixtures" / "tongyi-sample"
    NAME = "sample-a"
    DID = "tongyi-sample-a"
    NOW2 = dt.datetime(2026, 10, 11, 20, 30, tzinfo=SGT)

    def _site_tongyi(self):
        import tempfile as _t
        root = Path(_t.mkdtemp()); bare = root / "site.git"; site = root / "site"
        run = lambda *a, cwd=None: self.assertEqual(self.sp.run(["git", *a], cwd=cwd, env=self.env, capture_output=True).returncode, 0, a)
        run("init", "-q", "--bare", str(bare)); run("init", "-q", "-b", "main", str(site))
        p = site / "content/posts/tongyi" / (self.NAME + ".md"); p.parent.mkdir(parents=True)
        p.write_bytes((self.FIX / "sample-a.original.md").read_bytes())
        run("add", "-A", cwd=site); run("commit", "-qm", "pub", cwd=site)
        run("remote", "add", "origin", str(bare), cwd=site); run("push", "-q", "origin", "main", cwd=site)
        run("fetch", "-q", "origin", cwd=site)
        return site

    def _pr(self, rel, data, codex_ok=True, wang_rec=None, wang_v1_rec=False):
        """r15 MEDIUM 3：走真实 origin/main 取证路径——批准记录与状态提交到 main 并推到本地 bare 仓库（模拟 origin），
        fetch 后 origin/main 与远端一致；PR 分支只含稿件。APPROVALS_REF 保持 "origin/main" 不替换。"""
        import tempfile as _t
        self.infra_on_base = False
        self.git("rm", "-q", "--cached", str(self.draft.relative_to(self.repo))); self.draft.unlink()
        sha = hashlib.sha256(data).hexdigest()
        did = rel.split("/")[0] + "-" + Path(rel).stem
        dr = {"content_sha256": sha, "draft_id": did}
        self.write("state/publish-state.json", json.dumps(state(updated_at=(self.NOW2 - dt.timedelta(minutes=2)).isoformat())))
        if codex_ok:
            self.write(f"approvals/codex/{sha}.json", json.dumps(codex(dr, reviewed_at="2026-10-11T20:10:00+08:00")))
        if wang_rec:
            mk = wang_v1 if wang_v1_rec else wang
            self.write(f"approvals/wang/{sha}.json", json.dumps(mk(dr, recorded_at="2026-10-11T20:20:00+08:00", **wang_rec)))
        self.commit("records on main"); self.git("tag", "-f", "base")
        self.bare = Path(_t.mkdtemp()) / "data.git"
        self.sp.run(["git", "init", "-q", "--bare", str(self.bare)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(self.bare))
        self.git("push", "-q", "origin", "HEAD:refs/heads/main"); self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", "pr")
        p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.commit("pr draft")
        return rel

    def _route(self, rel, site):
        # 不替换 APPROVALS_REF（真实 origin/main）；只替换无法在测试中真实访问的外部服务：gh（PR 元数据由本地 git 给出）、
        # HTTP 链接探测、站点规范 remote（规范 remote 校验另有单测 test_site_remote_*）
        o = (R._gh_pr, R._real_now, R._http_probe, R._site_remote_ok)
        R._gh_pr = lambda repo, n: self.gh_meta(); R._real_now = lambda: self.NOW2
        R._http_probe = lambda u, timeout=10: (True, None); R._site_remote_ok = lambda u: True
        try:
            self.assertEqual(R.APPROVALS_REF, "origin/main")
            return R.route_pr(self.repo, 28, "2026-10-11", "daily", site_repo=site)[rel]
        finally:
            R._gh_pr, R._real_now, R._http_probe, R._site_remote_ok = o

    def sample(self):
        return (self.FIX / (self.NAME + ".md")).read_bytes()

    def test_sample_sha(self):
        self.assertEqual(hashlib.sha256(self.sample()).hexdigest(),
                         "8b8a4b6338e6ea6c413cc1929373e859fcd45e28dbf5056068bb4bd14abf89fc")

    def test_sample_without_wang_holds(self):
        rel = self._pr(f"tongyi/{self.NAME}.md", self.sample())
        sc, d = self._route(rel, self._site_tongyi())
        self.assertEqual([c for c in sc["error_codes"] if c.startswith("E-")], [], sc["errors"])
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-WANG", d.codes)

    def test_sample_with_wang_via_bot_not_publishable(self):
        rel = self._pr(f"tongyi/{self.NAME}.md", self.sample(), wang_rec={"channel": "via-grok-bot"})
        sc, d = self._route(rel, self._site_tongyi())
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-RECORD-MISMATCH", d.codes)

    def test_sample_with_wang_v1_direct_not_publishable(self):
        # r16 MEDIUM 1：真正删掉 schema_version、draft_id、quote_ref 三个 v2 字段，得到格式合格的 v1 direct 记录
        rel = self._pr(f"tongyi/{self.NAME}.md", self.sample(), wang_rec={"channel": "direct"}, wang_v1_rec=True)
        sha = hashlib.sha256(self.sample()).hexdigest()
        r = json.loads(self.git("show", f"origin/main:approvals/wang/{sha}.json"))
        self.assertFalse({"schema_version", "draft_id", "quote_ref"} & set(r)); self.assertTrue(_A.valid_wang(r))
        sc, d = self._route(rel, self._site_tongyi())
        self.assertFalse(d.publishable, d.codes)
        self.assertIn("E-ROUTE-RECORD-V2-REQUIRED", d.codes)

    def test_front_matter_any_yaml_form_not_publishable_even_with_both_approvals(self):
        # r16 BLOCKER：多行 YAML 列表、flow 列表、块标量等写法的无来源数字，双批准有效也不能发布
        for v in ("score:\n  - 95", "score: [95]", "note: |\n  得分 95", "note: >\n  得分 95",
                  'note: "<!-- 95 -->"'):   # r17 BLOCKER：front matter 里的注释写法同样不可发布
            with self.subTest(v=v):
                self.setUp()
                data = self._variant("---\n", "---\n" + v + "\n")
                rel = self._pr(f"tongyi/{self.NAME}.md", data, wang_rec={"channel": "direct"})
                sc, d = self._route(rel, self._site_tongyi())
                self.assertIn("E-REPLAY-001", sc["error_codes"], v)
                self.assertFalse(d.publishable, v); self.assertIn("E-ROUTE-SELFCHECK-FAIL", d.codes)

    # —— r15 BLOCKER 修正的反例：两份批准都有效，仍不可发布
    def _variant(self, old, new):
        t = self.sample().decode("utf-8"); assert old in t
        return t.replace(old, new, 1).encode("utf-8")

    def test_front_matter_number_not_publishable_even_with_both_approvals(self):
        data = self._variant("---\n", "---\nscore: 95\n")
        rel = self._pr(f"tongyi/{self.NAME}.md", data, wang_rec={"channel": "direct"})
        sc, d = self._route(rel, self._site_tongyi())
        self.assertIn("E-REPLAY-001", sc["error_codes"])
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-SELFCHECK-FAIL", d.codes)

    def test_hard_blocks_not_publishable_even_with_both_approvals(self):
        for line, code in (("建议买入沪深300ETF。", "E-BLOCK-INVEST"), ("仓位加到八成。", "E-BLOCK-INVEST"),
                           ("样例内部词甲。", None), ("美联储议息，预计后续走势回落。", "E-BLOCK-MACRO-OPINION")):
            with self.subTest(line=line):
                self.setUp()
                data = self._variant("本文不含投资建议。", line + "\n\n本文不含投资建议。")
                rel = self._pr(f"tongyi/{self.NAME}.md", data, wang_rec={"channel": "direct"})
                sc, d = self._route(rel, self._site_tongyi())
                self.assertFalse(d.publishable, line)
                if code:
                    self.assertIn(code, sc["error_codes"], line)

    def test_hidden_content_not_publishable(self):
        data = self._variant("本文不含投资建议。", '<div hidden>\n建议买入。\n</div>\n\n本文不含投资建议。')
        rel = self._pr(f"tongyi/{self.NAME}.md", data, wang_rec={"channel": "direct"})
        sc, d = self._route(rel, self._site_tongyi())
        self.assertFalse(d.publishable, d.codes)
        self.assertIn("E-BLOCK-INVEST", sc["error_codes"])

    def test_sample_with_wang_direct_publishable(self):
        rel = self._pr(f"tongyi/{self.NAME}.md", self.sample(), wang_rec={"channel": "direct"})
        sc, d = self._route(rel, self._site_tongyi())
        self.assertEqual([c for c in sc["error_codes"] if c.startswith("E-")], [], sc["errors"])
        self.assertEqual((d.state, d.publishable), ("APPROVED", True), d.codes)

    def test_sample_without_codex_holds(self):
        rel = self._pr(f"tongyi/{self.NAME}.md", self.sample(), codex_ok=False, wang_rec={"channel": "direct"})
        sc, d = self._route(rel, self._site_tongyi())
        self.assertFalse(d.publishable); self.assertIn("E-ROUTE-NO-CODEX", d.codes)

    def test_daily_with_tongyi_type_fails(self):
        t = ("---\ntype: tongyi\n---\n" + INFER + "\n这一段没有来源，判断会上涨 10%。\n" + DISC).encode()
        rel = self._pr("daily/2026-10-11.md", t, wang_rec={"channel": "direct"})
        sc, d = self._route(rel, None)
        self.assertIn("E-TONGYI-MISMATCH", sc["error_codes"])
        self.assertFalse(d.publishable)
