import json, os, stat, subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import ledger, internal
from markjin.ledger import LedgerError


class Ledger(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        (self.repo / "review/ledger").mkdir(parents=True)

    def test_append_ok(self):
        p = ledger.append(self.repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 2, "ratio": 0.5})
        self.assertEqual(json.loads(p.read_text()), {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 2, "ratio": 0.5})

    def test_reject_extra_field(self):
        for extra in ({"note": "x"}, {"topic": "x"}, {"slug": "a"}, {"source": "u"}):
            with self.assertRaises(LedgerError) as cm:
                ledger.append(self.repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, **extra})
            self.assertEqual(cm.exception.code, "E-LEDGER-FIELD")
        self.assertFalse((self.repo / "review/ledger/2026-10-12.jsonl").exists())

    def test_reject_bad_values(self):
        bad = [{"date": "10/12", "error_code": "E-REPLAY-001", "count": 1},
               {"date": "2026-10-12", "error_code": "随便写", "count": 1},
               {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": -1},
               {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": "3"},
               {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "ratio": 1.5}]
        for b in bad:
            with self.assertRaises(LedgerError):
                ledger.append(self.repo, b)

    def test_card_id_ok(self):
        (self.repo / "cards").mkdir(exist_ok=True)
        (self.repo / "cards/2026-10-12.md").write_text('## 卡 {#2026-10-10-c03}\n<a id="c1"></a>\n### x {#a}\n', encoding="utf-8")
        for cid in ("2026-10-10-c03", "c1", "a"):
            p = ledger.append(self.repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": cid})
        self.assertEqual(ledger.verify_all(self.repo), [])
        self.assertIn('"card_id": "a"', p.read_text().splitlines()[-1])

    def test_card_id_rejects_free_text(self):
        for cid in ("含中文", "has space", "UPPER", "-lead", "trail-", "a/b", "a_b", "", "x" * 65, 3, None, ["a"]):
            with self.assertRaises(LedgerError, msg=repr(cid)) as cm:
                ledger.append(self.repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": cid})
            self.assertEqual(cm.exception.code, "E-LEDGER-VALUE")
        self.assertFalse((self.repo / "review/ledger/2026-10-12.jsonl").exists())

    def test_verify_rejects_bad_json(self):
        d = self.repo / "review/ledger"
        (d / "2026-10-12.jsonl").write_text('{"date": "2026-10-12", \n[1]\n')
        self.assertEqual([c for _, _, c in ledger.verify_all(self.repo)], ["E-LEDGER-VALUE", "E-LEDGER-VALUE"])

    def test_record_selfcheck_and_verify(self):
        res = {"errors": [{"code": "E-REPLAY-001", "line": 3}, {"code": "E-REPLAY-001", "line": 4},
                          {"code": "E-BLOCK-INTERNAL", "line": 5}]}
        ledger.record_selfcheck(self.repo, "2026-10-12", res)
        lines = (self.repo / "review/ledger/2026-10-12.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 2); self.assertEqual(ledger.verify_all(self.repo), [])
        with (self.repo / "review/ledger/2026-10-12.jsonl").open("a") as fh:
            fh.write('{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"memo":"x"}\n')
        self.assertEqual(ledger.verify_all(self.repo)[0][2], "E-LEDGER-FIELD")


class LedgerR2(unittest.TestCase):
    """第 2 轮反例：真实日历日期、文件名一致、目录缺失。断言 status（拒绝）、low_risk（不适用，恒 False）与错误码。"""
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp()); (self.repo / "review/ledger").mkdir(parents=True)

    def rej(self, rec, code):
        with self.assertRaises(LedgerError) as cm:
            ledger.append(self.repo, rec)
        self.assertEqual(cm.exception.code, code)

    def test_calendar_date(self):
        for d in ("2026-02-30", "2026-13-01", "2026-00-10", "0000-01-01"):
            self.rej({"date": d, "error_code": "E-REPLAY-001", "count": 1}, "E-LEDGER-DATE")

    def test_filename_mismatch(self):
        self.assertEqual(ledger.verify_text("2026-10-13.jsonl", '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1}'),
                         [(1, "E-LEDGER-DATE")])
        self.assertEqual(ledger.verify_text("notes.jsonl", ""), [(0, "E-LEDGER-FILE")])
        self.assertEqual(ledger.verify_text("2026-02-30.jsonl", ""), [(0, "E-LEDGER-DATE")])

    def test_dir_missing(self):
        repo = Path(tempfile.mkdtemp())
        with self.assertRaises(LedgerError) as cm:
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1})
        self.assertEqual(cm.exception.code, "E-LEDGER-DIR")
        self.assertEqual(ledger.verify_all(repo), [(0, 0, "E-LEDGER-DIR")])

    def test_auto_approved_is_only_a_count(self):
        from markjin.codes import ERROR_CODES
        self.assertIn("已停用", ERROR_CODES["I-AUTO-APPROVED"])          # t161u：不再有自动批准
        self.assertIn("不是批准凭证", Path(ledger.__file__).read_text(encoding="utf-8"))


class R12Fullmatch(unittest.TestCase):
    """r12：路径与字段白名单用 fullmatch，末尾换行的文件名或值不得通过。"""
    def test_trailing_newline_rejected(self):
        self.assertFalse(ledger.review_path_ok("review/2026-10-11.md\n")); self.assertFalse(ledger.is_public_draft("daily/2026-10-11.md\n"))
        self.assertIsNone(ledger.FILE_RE.fullmatch("2026-10-11.jsonl\n"))
        self.assertIsNone(ledger.DATE_RE.fullmatch("2026-10-11\n"))


class InternalDir(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()) / "markjin-internal"
        os.environ["MARKJIN_INTERNAL_DIR"] = str(self.d)

    def tearDown(self):
        os.environ.pop("MARKJIN_INTERNAL_DIR", None)

    def test_create_not_in_git_0700(self):
        d = internal.ensure_internal_dir()
        self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700)
        r = subprocess.run(["git", "-C", str(d), "rev-parse"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    def test_refuse_inside_git(self):
        root = Path(tempfile.mkdtemp()); (root / ".git").mkdir()
        os.environ["MARKJIN_INTERNAL_DIR"] = str(root / "markjin-internal")
        with self.assertRaises(internal.InternalError):
            internal.ensure_internal_dir()

    def test_actor_is_not_authorization(self):
        # actor 自报值不影响结果：任何 actor 都由操作系统权限决定
        for actor in ("governance", "wang", "producer", ""):
            p = internal.write_internal("review/a.md", "x", actor)
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        self.assertNotIn("actor", p.read_text())

    def test_loose_permissions_rejected(self):
        internal.ensure_internal_dir(); self.d.chmod(0o755)
        with self.assertRaises(internal.InternalError):
            internal.write_internal("review/a.md", "x", "governance")

    def test_symlink_dir_rejected(self):
        real = Path(tempfile.mkdtemp()); real.chmod(0o700)
        self.d.parent.mkdir(exist_ok=True); self.d.symlink_to(real)
        with self.assertRaises(internal.InternalError):
            internal.write_internal("review/a.md", "x", "governance")

    def test_escape_rejected(self):
        with self.assertRaises(internal.InternalError):
            internal.write_internal("../escape.md", "x", "governance")


if __name__ == "__main__":
    unittest.main()


class LedgerR3(unittest.TestCase):
    """r3 审查反例：文件名白名单、空台账、重复键、card_id 锚点。"""
    REC = '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1}'

    def test_filename_whitelist(self):
        for name in ("notes.md", "2026-10-12.json", "2026-10-12.jsonl.bak", "README", "x.jsonl"):
            self.assertEqual(ledger.verify_text(name, self.REC + "\n"), [(0, "E-LEDGER-FILE")], name)
        self.assertEqual(ledger.verify_text(".gitkeep", ""), [])
        self.assertEqual(ledger.verify_text(".gitkeep", "自由文本"), [(0, "E-LEDGER-FILE")])

    def test_empty_jsonl_fails(self):
        for body in ("", "\n", "  \n\n"):
            self.assertEqual(ledger.verify_text("2026-10-12.jsonl", body), [(0, "E-LEDGER-EMPTY")])

    def test_duplicate_keys_rejected(self):
        dup = '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"任意自由文本","card_id":"c1"}'
        self.assertEqual(ledger.verify_text("2026-10-12.jsonl", dup, {"c1"}), [(1, "E-LEDGER-VALUE")])

    def test_card_id_must_be_anchor(self):
        rec = '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c1"}'
        self.assertEqual(ledger.verify_text("2026-10-12.jsonl", rec, set()), [(1, "E-LEDGER-CARD")])
        self.assertEqual(ledger.verify_text("2026-10-12.jsonl", rec, {"c1"}), [])
        repo = Path(tempfile.mkdtemp()); (repo / "review/ledger").mkdir(parents=True)
        with self.assertRaises(LedgerError) as cm:
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})
        self.assertEqual(cm.exception.code, "E-LEDGER-CARD")
        (repo / "raw").mkdir(); (repo / "raw/x.md").write_text("{#c1}")        # raw/ 不是公开稿件
        with self.assertRaises(LedgerError):
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})
        (repo / "cards").mkdir(); (repo / "cards/2026-10-12.md").write_text("## 卡 {#c1}\n")
        ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})


class LedgerR4(unittest.TestCase):
    def test_review_whitelist(self):
        ok = ["review/README.md", "review/error-codes.md", "review/ledger/.gitkeep", "review/ledger/2026-10-12.jsonl",
              "review/2026-10-10.md", "review/2026-10-10-r3/digest.md", "review/2026-10-10-r3/result-r3b.txt",
              "review/2026-10-10-r4/review-prompt.md", "review/codex/2026-10-10-d01.log"]
        bad = ["review/notes.md", "review/ledger/notes.md", "review/x/y.md", "review/2026-10-10-r3/notes.md",
               "review/codex/../x.log", "review/2026-10-10.txt", "review/README.md.bak"]
        for p in ok: self.assertTrue(ledger.review_path_ok(p), p)
        for p in bad: self.assertFalse(ledger.review_path_ok(p), p)

    def test_anchor_only_cards_unique_not_in_code(self):
        self.assertTrue(ledger.is_public_draft("cards/2026-10-12-c1.md"))
        for p in ("digest/2026-10-12.md", "README.md", "cards/sub/x.md", "cards/X.md", "content/cards/x.md"):
            self.assertFalse(ledger.is_public_draft(p), p)
        self.assertEqual(ledger.unique_anchors(["## a {#c1}\n", "```\n{#c2}\n```\n<!-- {#c3} -->\n"]), {"c1"})
        self.assertEqual(ledger.unique_anchors(["{#c1}", "{#c1}"]), set())   # 重复锚点不认


class LedgerR8(unittest.TestCase):
    def test_inline_code_and_escaped_not_anchor(self):
        from markjin.ledger import anchors_in
        self.assertEqual(anchors_in("说明 `{#c1}` 与 ``id=\"c2\"``"), set())
        self.assertEqual(anchors_in("转义 \\{#c3} 与 \\id=\"c4\""), set())
        self.assertEqual(anchors_in("## 卡 {#c5}\n<a id=\"c6\"></a>"), {"c5", "c6"})
        rec = '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c1"}'
        repo = Path(tempfile.mkdtemp()); (repo / "review/ledger").mkdir(parents=True)
        (repo / "cards").mkdir(); (repo / "cards/2026-10-12.md").write_text("只有行内代码 `{#c1}`\n")
        with self.assertRaises(LedgerError) as cm:
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})
        self.assertEqual(cm.exception.code, "E-LEDGER-CARD")


class LedgerR8b(unittest.TestCase):
    def test_data_id_and_indented_code_not_anchor(self):
        from markjin.ledger import anchors_in
        self.assertEqual(anchors_in('<div data-id="c1"></div>'), set())
        self.assertEqual(anchors_in("正文\n\n    {#c2}\n\tid=\"c3\"\n"), set())
        self.assertEqual(anchors_in('## 卡 {#c4}\n<a id="c5"></a>'), {"c4", "c5"})

    def test_unreadable_card_rejects(self):
        from markjin.ledger import repo_anchors, LedgerError
        repo = Path(tempfile.mkdtemp()); (repo / "cards").mkdir()
        (repo / "cards/a.md").write_text("## 卡 {#c1}\n", encoding="utf-8")
        (repo / "cards/b.md").write_bytes(b"\xff\xfe {#c1}")
        with self.assertRaises(LedgerError) as cm:
            repo_anchors(repo)
        self.assertEqual(cm.exception.code, "E-LEDGER-CARD")


class FinalR1ErrorCodes(unittest.TestCase):
    def test_error_codes_md_in_sync(self):
        import subprocess, sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        r = subprocess.run([sys.executable, str(root / "scripts/gen-error-codes.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


class FinalR5UnclosedComment(unittest.TestCase):
    """整体验收 r5 MEDIUM：未闭合 HTML 注释里的 card_id 不算锚点（注释视为延续到文件末尾）。"""
    def test_anchors_ignore_unclosed_comment(self):
        self.assertEqual(ledger.anchors_in("<!--\n## 卡 {#c1}\n"), set())
        self.assertEqual(ledger.anchors_in("## 卡 {#c0}\n<!--\n## 卡 {#c1}\n<a id=\"c2\"></a>\n"), {"c0"})
        self.assertEqual(ledger.anchors_in("<!-- x -->\n## 卡 {#c3}\n"), {"c3"})       # 闭合注释之后照常

    def test_append_rejects_anchor_in_unclosed_comment(self):
        repo = Path(tempfile.mkdtemp()); (repo / "review/ledger").mkdir(parents=True)
        (repo / "cards").mkdir(); (repo / "cards/2026-10-12.md").write_text("<!--\n## 卡 {#c1}\n", encoding="utf-8")
        with self.assertRaises(LedgerError) as cm:
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})
        self.assertEqual(cm.exception.code, "E-LEDGER-CARD")


class FinalR6UnclosedFence(unittest.TestCase):
    """整体验收 r6 MEDIUM：未闭合代码围栏延续到文末；闭围栏长度不少于开围栏。"""
    def test_fence_rules(self):
        self.assertEqual(ledger.anchors_in("```\n{#c1}\n"), set())
        self.assertEqual(ledger.anchors_in("## a {#c0}\n```\n{#c1}\n```\n{#c2}\n"), {"c0", "c2"})
        self.assertEqual(ledger.anchors_in("````\n```\n{#c1}\n````\n{#c3}"), {"c3"})
        self.assertEqual(ledger.anchors_in("~~~\n{#c1}\n```\n{#c2}"), set())

    def test_append_rejects_anchor_in_unclosed_fence(self):
        repo = Path(tempfile.mkdtemp()); (repo / "review/ledger").mkdir(parents=True)
        (repo / "cards").mkdir(); (repo / "cards/2026-10-12.md").write_text("```\n## 卡 {#c1}\n", encoding="utf-8")
        with self.assertRaises(LedgerError) as cm:
            ledger.append(repo, {"date": "2026-10-12", "error_code": "E-REPLAY-001", "count": 1, "card_id": "c1"})
        self.assertEqual(cm.exception.code, "E-LEDGER-CARD")


class FinalR9PlainTextId(unittest.TestCase):
    """整体验收 r9 MEDIUM：纯文本里的 id="c1" 不算锚点，只认 HTML 起始标签里的 id 属性。"""

    def test_plain_text_id_not_anchor(self):
        from markjin import ledger
        for t in ('说明 id="c1"', '[链接 id="c1"](https://x.example)', '正文 id="c1" 结尾', '> 引用 id="c1"'):
            self.assertEqual(ledger.anchors_in(t), set(), t)

    def test_real_tags_still_anchor(self):
        from markjin import ledger
        self.assertEqual(ledger.anchors_in('<a id="c1"></a>'), {"c1"})
        self.assertEqual(ledger.anchors_in('<span class="k" id="c2">x</span>'), {"c2"})
        self.assertEqual(ledger.anchors_in('<div\n  id="c3">'), {"c3"})
        self.assertEqual(ledger.anchors_in('<br id="c4"/>'), {"c4"})
        self.assertEqual(ledger.anchors_in('<a data-id="c5"></a>'), set())


class FinalR11Retired(unittest.TestCase):
    """整体验收 r11 MEDIUM：已停用的 I-AUTO-APPROVED 只许记 0；review/README 结论枚举与代码一致。"""

    def test_nonzero_rejected(self):
        for c in (1, 7):
            with self.assertRaises(LedgerError) as cm:
                ledger.validate({"date": "2026-10-12", "error_code": "I-AUTO-APPROVED", "count": c}, file_date="2026-10-12")
            self.assertEqual(cm.exception.code, "E-LEDGER-VALUE")
        self.assertEqual(ledger.verify_text("2026-10-12.jsonl", '{"date":"2026-10-12","error_code":"I-AUTO-APPROVED","count":1}\n'),
                         [(1, "E-LEDGER-VALUE")])

    def test_zero_allowed_and_others_unaffected(self):
        ledger.validate({"date": "2026-10-12", "error_code": "I-AUTO-APPROVED", "count": 0}, file_date="2026-10-12")
        ledger.validate({"date": "2026-10-12", "error_code": "E-FORMULA-MISMATCH", "count": 3}, file_date="2026-10-12")

    def test_readme_verdict_enum_consistent(self):
        t = (Path(ledger.__file__).resolve().parents[2] / "review" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("`VERDICT: APPROVED|REJECTED`", t); self.assertIn("VERDICT: APPROVED_WITH_FOLLOWUPS", t)
