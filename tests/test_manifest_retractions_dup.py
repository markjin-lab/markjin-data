"""MANIFEST 中 RETRACTIONS.md 重复登记（raw/README.md：每次追加 RETRACTIONS.md 后在 MANIFEST 末尾重登记新 sha256）。
守卫（gitscan）与 selfcheck 只对 RETRACTIONS.md 放宽重复、以最后一条为准；其他路径重复仍判整份 MANIFEST 无效。"""
import hashlib, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from test_guards import Base

REPO = Path(__file__).resolve().parents[1]


def sha(b):
    return hashlib.sha256(b).hexdigest()


class GuardManifestRetractionsDup(Base):
    PDF = b"%PDF-1.4\n\xff\xfe\x00\x01binary\n"
    JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00binary\n"

    def build(self, extra_dup=None):
        d = self.repo / "raw/2026-10-11"
        (d / "fulltext").mkdir(parents=True); (d / "nbs").mkdir()
        (d / "fulltext/a.pdf").write_bytes(self.PDF); (d / "nbs/b.jpg").write_bytes(self.JPG)
        r1 = b"| path | source_url | sha256 | removed_at | reason |\n|---|---|---|---|---|\n"
        r2 = r1 + b"| raw/2026-10-11/x.txt | https://e.x/ | " + b"1" * 64 + b" | t | r |\n"
        (d / "RETRACTIONS.md").write_bytes(r2)
        lines = [f"{sha(self.PDF)}  ./fulltext/a.pdf", f"{sha(r1)}  ./RETRACTIONS.md",
                 f"{sha(self.JPG)}  ./nbs/b.jpg", f"{sha(r2)}  ./RETRACTIONS.md"]
        if extra_dup:
            lines.append(extra_dup)
        (d / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.commit("dup")
        return r1, r2

    def test_retractions_dup_last_wins_and_binaries_registered(self):
        r1, r2 = self.build()
        self.expect(self.public(), True)
        self.expect(self.internal("--rev", "HEAD"), True)
        from markjin import gitscan
        m = gitscan._manifest_lines((self.repo / "raw/2026-10-11/MANIFEST.sha256").read_text())
        self.assertIn((sha(r2), "RETRACTIONS.md"), m); self.assertNotIn((sha(r1), "RETRACTIONS.md"), m)
        self.assertIn((sha(self.PDF), "fulltext/a.pdf"), m); self.assertIn((sha(self.JPG), "nbs/b.jpg"), m)

    def test_other_path_dup_still_invalid(self):
        self.build(extra_dup=f"{sha(self.PDF)}  ./fulltext/a.pdf")
        self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")
        self.expect(self.public(), False, "E-CHECK-DECODE")
        from markjin import gitscan
        self.assertEqual(gitscan._manifest_lines(f"{'a' * 64}  ./x.txt\n{'b' * 64}  ./x.txt\n"), set())
        self.assertEqual(gitscan._manifest_lines(f"{'a' * 64}  ./x.txt\n{'b' * 64}  ./sub/RETRACTIONS.md\n{'c' * 64}  ./sub/RETRACTIONS.md\n"), set())


class SelfcheckManifestRetractionsDup(unittest.TestCase):
    DATE = "2026-10-12"
    XML = ('<feed><entry><id>http://arxiv.org/abs/2610.00001v1</id>'
           '<summary>The model reaches 90% accuracy on MMLU.</summary></entry></feed>')

    def repo(self, extra=""):
        """按 #83 中 raw/2026-10-12/MANIFEST.sha256 的形态：普通登记行、首次 ./RETRACTIONS.md、被撤回文件的原登记行（文件已删）、
        round2 嵌套路径，末尾再追加一次 ./RETRACTIONS.md 新 sha256。"""
        d = Path(tempfile.mkdtemp()); day = d / "raw" / self.DATE; (day / "arxiv").mkdir(parents=True)
        (day / "arxiv/cs.AI.xml").write_text(self.XML, encoding="utf-8")
        old, new = b"| path |\n", b"| path |\n| raw/2026-10-12/fred/UNRATE.json | u | " + b"2" * 64 + b" | t | r |\n"
        (day / "RETRACTIONS.md").write_bytes(new)
        (day / "MANIFEST.sha256").write_text(
            f"{sha(self.XML.encode())}  ./arxiv/cs.AI.xml\n{sha(old)}  ./RETRACTIONS.md\n{'2' * 64}  ./fred/UNRATE.json\n"
            f"{'3' * 64}  ./round2/MANIFEST.sha256\n{sha(new)}  ./RETRACTIONS.md\n" + extra, encoding="utf-8")
        return d

    LOC = "The model reaches 90% accuracy on MMLU."   # 存档摘要原文，作为结构化断言的〔原文：…〕位置

    def run_check(self, d, locator=None):
        from markjin.selfcheck import check_text
        txt = f"- 模型在 MMLU 上达到 90% 准确率。 — `raw/{self.DATE}/arxiv/cs.AI.xml` · https://arxiv.org/abs/2610.00001v1"
        txt += (f" 〔原文：{locator}〕" if locator else "") + "\n"
        return check_text(txt, repo=d, date=self.DATE, card_type="daily", link_checker=lambda u: True, internal_terms="load")

    def test_draft_citing_2026_10_12_no_manifest_parse_error(self):
        # #79：结构化断言必须带〔原文：…〕位置，故此处带位置；意图不变：引用 10-12 不报 MANIFEST 解析错误、结果不是 FAIL
        out = self.run_check(self.repo(), locator=self.LOC)
        self.assertNotIn("E-MANIFEST-PARSE", out["error_codes"]); self.assertNotEqual(out["status"], "FAIL", out["error_codes"])

    def test_draft_citing_2026_10_12_without_locator_is_locator_missing(self):
        # #79 与 #87 的规则交界：同一断言去掉〔原文：…〕→ E-SUPPORT-LOCATOR-MISSING（不是 MANIFEST 解析错误）
        out = self.run_check(self.repo())
        self.assertNotIn("E-MANIFEST-PARSE", out["error_codes"])
        self.assertIn("E-SUPPORT-LOCATOR-MISSING", out["error_codes"]); self.assertEqual(out["status"], "FAIL")

    def test_other_dup_still_manifest_parse_error(self):
        out = self.run_check(self.repo(extra=f"{sha(self.XML.encode())}  ./arxiv/cs.AI.xml\n"))
        self.assertIn("E-MANIFEST-PARSE", out["error_codes"])

    def test_real_2026_10_12_manifest_parses(self):
        """回归：仓库中真实的 raw/2026-10-12/MANIFEST.sha256（#83 后含两行 ./RETRACTIONS.md）。"""
        day = REPO / "raw" / self.DATE
        if not (day / "MANIFEST.sha256").exists():
            self.skipTest("仓库中没有 raw/2026-10-12")
        from markjin.selfcheck import _Ctx
        entries, err = _Ctx(REPO, self.DATE).manifest(day)
        self.assertIsNone(err)
        self.assertEqual(entries["RETRACTIONS.md"], sha((day / "RETRACTIONS.md").read_bytes()))


if __name__ == "__main__":
    unittest.main()
