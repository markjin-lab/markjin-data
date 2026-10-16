import json, subprocess, sys, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from markjin import approvals as A

SHA = "a" * 64
SESS = "01a146a5-13a5-75f1-bacf-9330e357a0a8"


def rec(did, sha=SHA):
    return {"content_sha256": sha, "draft_id": did, "codex_session": SESS, "verdict": "REJECTED",
            "log_path": "review/codex/x.log", "reviewed_at": "2026-10-17T05:39:49+08:00"}


class EnDraftIdWrite(unittest.TestCase):
    """Grok Bot 2026-10-17：英文稿 Codex 记录的 draft_id 必须以 -en 结尾，否则拒绝写入。"""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())

    def code(self, *a, **k):
        with self.assertRaises(A.ApprovalsError) as cm:
            A.write_codex_record(self.repo, *a, **k)
        return cm.exception.code

    def test_en_requires_suffix(self):
        for kw in ({"lang": "en"}, {"draft_path": "content/posts/daily/2026-10-17.en.md"},
                   {"draft_path": "daily/2026-10-17.en.md", "lang": "en"}):
            self.assertEqual(self.code(rec("daily-2026-10-17"), **kw), "E-APPROVALS-EN-DRAFT-ID", kw)
        self.assertFalse((self.repo / A.CODEX_DIR).exists() and any((self.repo / A.CODEX_DIR).iterdir()))
        p = A.write_codex_record(self.repo, rec("daily-2026-10-17-en"), lang="en")
        self.assertEqual(json.loads(p.read_text())["draft_id"], "daily-2026-10-17-en")

    def test_zh_ok_and_lang_required(self):
        p = A.write_codex_record(self.repo, rec("daily-2026-10-17"), draft_path="content/posts/daily/2026-10-17.md")
        self.assertTrue(p.exists())
        self.assertEqual(self.code(rec("daily-2026-10-17", "b" * 64)), "E-APPROVALS-EN-DRAFT-ID")          # 语言缺失
        self.assertEqual(self.code(rec("daily-2026-10-17-en", "b" * 64), draft_path="x/2026-10-17.md", lang="en"),
                         "E-APPROVALS-EN-DRAFT-ID")                                                        # 路径与语言矛盾
        self.assertEqual(self.code(rec("daily-2026-10-17", "b" * 64), lang="fr"), "E-APPROVALS-EN-DRAFT-ID")

    def test_append_only_and_schema(self):
        A.write_codex_record(self.repo, rec("daily-x"), lang="zh")
        self.assertEqual(self.code(rec("daily-x"), lang="zh"), "E-ROUTE-APPROVALS-REWRITTEN")
        bad = rec("daily-x", "c" * 64); bad["extra"] = 1
        self.assertEqual(self.code(bad, lang="zh"), "E-ROUTE-RECORD-INVALID")

    def test_written_record_parses(self):
        p = A.write_codex_record(self.repo, rec("daily-2026-10-17-en"), lang="en", for_date="2026-10-18")
        self.assertEqual(p.name, SHA + ".2026-10-18.json")
        self.assertTrue(A.valid_codex(json.loads(p.read_text())))

    def test_historical_records_still_valid(self):
        # 已写错的 3 条历史记录（缺 -en）读取校验不变，audit 不追溯
        for did in ("daily-2026-10-16", "daily-2026-10-17"):
            self.assertTrue(A.valid_codex(rec(did)))

    def test_cli(self):
        cli = Path(__file__).resolve().parents[1] / "scripts" / "write-codex-record.py"
        base = [sys.executable, str(cli), "--repo", str(self.repo), "--sha", "d" * 64, "--session", SESS,
                "--verdict", "REJECTED", "--log-path", "review/codex/x.log", "--reviewed-at", "2026-10-17T05:39:49+08:00"]
        r = subprocess.run(base + ["--draft-id", "daily-2026-10-17", "--draft", "daily/2026-10-17.en.md"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "FAIL E-APPROVALS-EN-DRAFT-ID"))
        r = subprocess.run(base + ["--draft-id", "daily-2026-10-17-en", "--draft", "daily/2026-10-17.en.md"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
