"""2026-10-12 合规撤回：verify-raw.sh 的 RETRACTIONS.md 支持，以及 check-public 的本机绝对路径规则。"""
import hashlib, os, shutil, subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from test_guards import Base

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
LOCAL = "/work" + "space/"


def sha(b):
    return hashlib.sha256(b).hexdigest()


class VerifyRawRetractions(Base):
    def setUp(self):
        super().setUp()
        d = self.repo / "raw/2026-10-12"
        (d / "src").mkdir(parents=True)
        self.keep, self.gone = b"keep\n", b"gone\n"
        (d / "src/keep.txt").write_bytes(self.keep)
        (d / "src/gone.txt").write_bytes(self.gone)
        (d / "MANIFEST.sha256").write_text(f"{sha(self.keep)}  ./src/keep.txt\n{sha(self.gone)}  ./src/gone.txt\n")
        self.base = self.commit("raw")       # 基线 = raw 已提交之后
        self.d = d

    def verify(self):
        return subprocess.run(["bash", "scripts/verify-raw.sh", self.base], cwd=self.repo, capture_output=True, text=True)

    def retract(self, digest, path="raw/2026-10-12/src/gone.txt"):
        (self.d / "src/gone.txt").unlink()
        r = (f"| path | source_url | sha256 | removed_at | reason |\n|---|---|---|---|---|\n"
             f"| {path} | https://e.x/ | {digest} | 2026-10-12 07:17 SGT | test |\n").encode()
        (self.d / "RETRACTIONS.md").write_bytes(r)
        with open(self.d / "MANIFEST.sha256", "a") as f:
            f.write(f"{sha(r)}  ./RETRACTIONS.md\n")
        self.commit("retract")

    def test_baseline_passes(self):
        self.assertEqual(self.verify().returncode, 0)

    def test_listed_retraction_passes(self):
        self.retract(sha(self.gone))
        r = self.verify(); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("RETRACTED raw/2026-10-12/src/gone.txt", r.stdout)

    def test_unlisted_deletion_fails(self):
        (self.d / "src/gone.txt").unlink(); self.commit("rm")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("被删除", r.stdout)

    def test_sha_mismatch_fails(self):
        self.retract("0" * 64)
        r = self.verify(); self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL raw/2026-10-12/MANIFEST.sha256", r.stdout); self.assertIn("被删除", r.stdout)

    def test_other_path_listed_fails(self):
        self.retract(sha(self.gone), path="raw/2026-10-12/src/other.txt")
        self.assertEqual(self.verify().returncode, 1)


    def test_row_without_sha_fails(self):
        self.retract("")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("被删除", r.stdout)

    def test_row_malformed_sha_fails(self):
        self.retract(sha(self.gone)[:63] + "z")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("被删除", r.stdout)

    def test_retractions_rewritten_fails(self):
        self.retract(sha(self.gone)); self.base = self.head()
        f = self.d / "RETRACTIONS.md"
        f.write_bytes(f.read_bytes().replace(b"| test |", b"| edited |"))
        self.commit("edit")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("非追加式修改", r.stdout)

    def test_retractions_deleted_fails(self):
        self.retract(sha(self.gone)); self.base = self.head()
        (self.d / "RETRACTIONS.md").unlink(); self.commit("rm")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("RETRACTIONS.md 被删除", r.stdout)

    def test_retractions_appended_passes(self):
        self.retract(sha(self.gone)); self.base = self.head()
        with open(self.d / "RETRACTIONS.md", "ab") as f:
            f.write("\n补充说明：追加行。\n".encode())
        with open(self.d / "MANIFEST.sha256", "a") as f:   # 追加后按只追加原则重新登记新 sha256
            f.write(f"{sha((self.d / 'RETRACTIONS.md').read_bytes())}  ./RETRACTIONS.md\n")
        self.commit("append")
        r = self.verify(); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PublicLocalPath(Base):
    def test_new_raw_file_with_local_path_rejected(self):
        (self.repo / "raw").mkdir(); (self.repo / "raw/a.json").write_text(f'{{"stored": "{LOCAL}x"}}\n')
        self.commit("add")
        self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_previously_committed_file_exempt(self):
        (self.repo / "raw").mkdir(); (self.repo / "raw/a.json").write_text(f'{{"stored": "{LOCAL}x"}}\n')
        self.commit("old")
        (self.repo / "raw/b.txt").write_text("clean\n"); self.commit("next")
        self.expect(self.public(), True)

    def test_non_raw_not_affected(self):
        (self.repo / "notes.md").write_text(f"{LOCAL}x\n"); self.commit("n")
        self.expect(self.public(), True)


if __name__ == "__main__":
    unittest.main()
