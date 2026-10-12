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


    def test_delete_file_and_manifest_line_fails(self):
        (self.d / "src/gone.txt").unlink()
        (self.d / "MANIFEST.sha256").write_text(f"{sha(self.keep)}  ./src/keep.txt\n")
        self.commit("rm both")
        r = self.verify(); self.assertEqual(r.returncode, 1)
        self.assertIn("MANIFEST 删改了旧行", r.stdout); self.assertIn("被删除", r.stdout)

    def test_rewrite_reason_then_append_manifest_fails(self):
        self.retract(sha(self.gone)); self.base = self.head()
        f = self.d / "RETRACTIONS.md"
        f.write_bytes(f.read_bytes().replace(b"| test |", b"| edited |"))
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(f.read_bytes())}  ./RETRACTIONS.md\n")
        self.commit("rewrite")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("非追加式修改", r.stdout)

    def test_manifest_deleted_fails(self):
        (self.d / "MANIFEST.sha256").unlink(); self.commit("rm manifest")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("MANIFEST 被删除", r.stdout)

    def run_default(self, env_base=None):
        env = dict(os.environ); env.pop("VERIFY_RAW_BASE", None)
        if env_base is not None:
            env["VERIFY_RAW_BASE"] = env_base
        return subprocess.run(["bash", "scripts/verify-raw.sh"], cwd=self.repo, capture_output=True, text=True, env=env)

    def test_default_base_parent_catches_deletion(self):
        # 无 origin/main → 回退 HEAD^：最近一次提交里的删除必须被发现
        (self.d / "src/gone.txt").unlink(); self.commit("rm")
        r = self.run_default(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)

    def test_default_base_origin_main(self):
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", self.base], cwd=self.repo, check=True)
        (self.d / "src/gone.txt").unlink(); self.commit("rm")
        (self.repo / "other.txt").write_text("x\n"); self.commit("later")   # HEAD^ 已含删除，只有 origin/main 能发现
        r = self.run_default(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)

    def test_env_base_override(self):
        (self.d / "src/gone.txt").unlink(); self.commit("rm")
        r = self.run_default(env_base=self.head()); self.assertEqual(r.returncode, 1); self.assertIn("被删除", r.stdout)   # 基线=目标：仍检查目标提交对父提交
        r = self.run_default(env_base=self.base); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)

    def test_bad_base_fails(self):
        r = self.run_default(env_base="deadbeef" * 5); self.assertEqual(r.returncode, 1)


    # ---- r2（PR #9 审查）----
    def git(self, *a):
        r = subprocess.run(["git", *a], cwd=self.repo, capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr); return r.stdout.strip()

    def test_new_day_without_manifest_fails(self):
        (self.repo / "raw/2026-10-13").mkdir(); (self.repo / "raw/2026-10-13/a.txt").write_text("x\n")
        self.commit("day")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("缺少 MANIFEST.sha256: raw/2026-10-13/", r.stdout)

    def test_manifest_reorder_fails(self):
        (self.d / "MANIFEST.sha256").write_text(f"{sha(self.gone)}  ./src/gone.txt\n{sha(self.keep)}  ./src/keep.txt\n")
        self.commit("reorder")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("MANIFEST 删改了旧行", r.stdout)

    def test_manifest_prepend_fails(self):
        (self.d / "src/new.txt").write_bytes(b"new\n")
        m = self.d / "MANIFEST.sha256"
        m.write_text(f"{sha(b'new' + bytes([10]))}  ./src/new.txt\n" + m.read_text())
        self.commit("prepend")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("MANIFEST 删改了旧行", r.stdout)

    def test_manifest_append_passes(self):
        (self.d / "src/new.txt").write_bytes(b"new\n")
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(b'new' + bytes([10]))}  ./src/new.txt\n")
        self.commit("append")
        r = self.verify(); self.assertEqual(r.returncode, 0, r.stdout)

    def test_add_then_remove_within_range_fails(self):
        (self.d / "src/tmp.txt").write_bytes(b"tmp\n")
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(b'tmp' + bytes([10]))}  ./src/tmp.txt\n")
        self.commit("add")
        (self.d / "src/tmp.txt").unlink()
        (self.d / "MANIFEST.sha256").write_text(f"{sha(self.keep)}  ./src/keep.txt\n{sha(self.gone)}  ./src/gone.txt\n")
        self.commit("remove")          # 端点 diff 为空，但中间提交违规
        self.assertEqual(self.git("diff", self.base, "HEAD"), "")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)

    def test_reads_commit_not_worktree(self):
        orig = (self.d / "src/keep.txt").read_bytes(), (self.d / "MANIFEST.sha256").read_bytes()
        (self.d / "src/keep.txt").write_bytes(b"changed\n")
        (self.d / "MANIFEST.sha256").write_text(f"{sha(b'changed' + bytes([10]))}  ./src/keep.txt\n{sha(self.gone)}  ./src/gone.txt\n")
        self.commit("tamper")
        (self.d / "src/keep.txt").write_bytes(orig[0]); (self.d / "MANIFEST.sha256").write_bytes(orig[1])   # 工作树还原
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被修改", r.stdout)

    def test_target_other_than_head(self):
        self.git("checkout", "-q", "-b", "bad")
        (self.d / "src/gone.txt").unlink(); bad = self.commit("rm")
        self.git("checkout", "-q", "-")
        r = subprocess.run(["bash", "scripts/verify-raw.sh", self.base, "--target", bad], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)
        self.assertEqual(self.verify().returncode, 0)

    def test_non_ancestor_base_fails(self):
        self.git("checkout", "-q", "-b", "side")
        (self.repo / "s.txt").write_text("s\n"); side = self.commit("side")
        self.git("checkout", "-q", "-")
        (self.repo / "m.txt").write_text("m\n"); self.commit("main")
        r = subprocess.run(["bash", "scripts/verify-raw.sh", side], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("不是目标", r.stdout)

    def test_git_failure_fails_closed(self):
        fake = Path(tempfile.mkdtemp())
        real = shutil.which("git")
        (fake / "git").write_text(f'#!/bin/sh\n[ "$1" = diff ] && exit 128\nexec {real} "$@"\n'); (fake / "git").chmod(0o755)
        (self.repo / "x.txt").write_text("x\n"); self.commit("x")
        env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}")
        r = subprocess.run(["bash", "scripts/verify-raw.sh", self.base], cwd=self.repo, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("git 命令失败", r.stdout)

    def test_hook_checks_non_head_ref(self):
        self.git("checkout", "-q", "-b", "bad")
        (self.d / "src/gone.txt").unlink(); bad = self.commit("rm")
        self.git("checkout", "-q", "-")
        r = self.hook(f"refs/heads/bad {bad} refs/heads/bad {self.base}\n")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr); self.assertIn("verify-raw 未通过", r.stderr)

    def test_hook_passes_clean_non_head_ref(self):
        self.git("checkout", "-q", "-b", "ok")
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        self.git("checkout", "-q", "-")
        r = self.hook(f"refs/heads/ok {ok} refs/heads/ok {self.base}\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_hook_rejects_main_deletion(self):
        r = self.hook(f"(delete) {'0' * 40} refs/heads/main {self.base}\n")
        self.assertEqual(r.returncode, 1); self.assertIn("禁止删除不可变 ref", r.stderr)

    # ---- r3（PR #9 第二轮审查）----
    def add_listed(self, rel, data):
        f = self.d / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(data)
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(data)}  ./{rel}\n")

    def test_nested_manifest_unlisted_fails(self):
        (self.d / "src/MANIFEST.sha256").write_bytes(b"x\n"); self.commit("nested")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("未登记: raw/2026-10-12/src/MANIFEST.sha256", r.stdout)

    def test_nested_manifest_append_is_modification(self):
        self.add_listed("src/MANIFEST.sha256", b"a\n"); self.commit("nested"); self.base = self.head()
        f = self.d / "src/MANIFEST.sha256"; f.write_bytes(b"a\nb\n")
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(b'a' + bytes([10]) + b'b' + bytes([10]))}  ./src/MANIFEST.sha256\n")
        self.commit("append nested")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("已提交 raw 文件被修改: raw/2026-10-12/src/MANIFEST.sha256", r.stdout)

    def test_nested_manifest_deletion_needs_retraction(self):
        self.add_listed("src/MANIFEST.sha256", b"a\n"); self.commit("nested"); self.base = self.head()
        (self.d / "src/MANIFEST.sha256").unlink(); self.commit("rm nested")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("已提交 raw 文件被删除", r.stdout)

    def test_nested_retractions_does_not_excuse(self):
        (self.d / "src/gone.txt").unlink()
        row = f"| raw/2026-10-12/src/gone.txt | https://e.x/ | {sha(self.gone)} | t | r |\n".encode()
        self.add_listed("src/RETRACTIONS.md", row); self.commit("nested retract")
        r = self.verify(); self.assertEqual(r.returncode, 1); self.assertIn("被删除", r.stdout)

    def write_retractions(self, rows):
        r = ("| path | source_url | sha256 | removed_at | reason |\n|---|---|---|---|---|\n" +
             "".join(f"| {p} | https://e.x/ | {h} | t | r |\n" for p, h in rows)).encode()
        (self.d / "RETRACTIONS.md").write_bytes(r)
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(r)}  ./RETRACTIONS.md\n")

    def test_retraction_of_extant_file_with_fake_sha_fails(self):
        # 新文件配假 sha（全 0），并在 RETRACTIONS.md 里重复这个假 sha：文件仍存在 → 必须照常校验
        (self.d / "src/a.txt").write_bytes(b"real\n")
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{'0' * 64}  ./src/a.txt\n")
        self.write_retractions([("raw/2026-10-12/src/a.txt", "0" * 64)])
        self.commit("fake")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("raw/2026-10-12/src/a.txt: FAILED", r.stdout); self.assertIn("在父提交中不存在", r.stdout)

    def test_retraction_of_extant_old_file_fails(self):
        self.write_retractions([("raw/2026-10-12/src/keep.txt", sha(self.keep))]); self.commit("not deleted")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("在本提交中仍存在", r.stdout)

    def test_retraction_row_wrong_sha_for_deleted_file_fails(self):
        (self.d / "src/gone.txt").unlink()
        self.write_retractions([("raw/2026-10-12/src/gone.txt", sha(self.gone)), ("raw/2026-10-12/src/keep2.txt", "1" * 64)])
        self.commit("extra row")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("在父提交中不存在", r.stdout)

    def test_retraction_malformed_extra_row_fails(self):
        (self.d / "src/gone.txt").unlink()
        self.write_retractions([("raw/2026-10-12/src/gone.txt", sha(self.gone)), ("raw/2026-10-12/src/keep.txt", "zz")])
        self.commit("bad row")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("sha256 格式错误", r.stdout)

    def test_retraction_sha_compared_to_parent_blob(self):
        (self.d / "src/gone.txt").unlink()
        self.write_retractions([("raw/2026-10-12/src/gone.txt", sha(b"other\n"))]); self.commit("mismatch")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("与父提交中被删除文件不符", r.stdout)

    def test_intermediate_unregistered_file_still_caught(self):
        (self.d / "src/late.txt").write_bytes(b"late\n"); self.commit("unregistered")
        (self.repo / "o.txt").write_text("o\n"); self.commit("non-raw")          # raw 未变的中间提交
        with open(self.d / "MANIFEST.sha256", "a") as m:
            m.write(f"{sha(b'late' + bytes([10]))}  ./src/late.txt\n")
        self.commit("register later")
        r = self.verify(); self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("未登记: raw/2026-10-12/src/late.txt", r.stdout)

    def test_default_base_is_merge_base_for_new_branch(self):
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", self.base], cwd=self.repo, check=True)
        self.git("checkout", "-q", "-b", "feat")
        (self.d / "src/gone.txt").unlink(); self.commit("rm")
        (self.repo / "o.txt").write_text("o\n"); self.commit("later")
        self.git("checkout", "-q", "-")
        (self.repo / "m.txt").write_text("m\n"); main2 = self.commit("main moves")
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", main2], cwd=self.repo, check=True)
        env = dict(os.environ); env.pop("VERIFY_RAW_BASE", None)
        r = subprocess.run(["bash", "scripts/verify-raw.sh", "--target", "feat"], cwd=self.repo, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("被删除", r.stdout)
        r = self.hook(f"refs/heads/feat {self.git('rev-parse', 'feat')} refs/heads/feat {'0' * 40}\n")
        self.assertEqual(r.returncode, 1, r.stderr); self.assertIn("verify-raw 未通过", r.stderr)

    def test_hook_new_branch_merge_base_passes_clean(self):
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", self.base], cwd=self.repo, check=True)
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        r = self.hook(f"refs/heads/n {ok} refs/heads/n {'0' * 40}\n"); self.assertEqual(r.returncode, 0, r.stderr)

    # ---- pre-push：多 ref、git 失败、非提交目标、不可变 ref ----
    def bad_branch(self):
        self.git("checkout", "-q", "-b", "bad")
        (self.d / "src/gone.txt").unlink(); bad = self.commit("rm")
        self.git("checkout", "-q", "-"); return bad

    def test_hook_multi_ref_one_bad_fails(self):
        bad = self.bad_branch()
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        for inp in (f"refs/heads/ok {ok} refs/heads/ok {self.base}\nrefs/heads/bad {bad} refs/heads/bad {self.base}\n",
                    f"refs/heads/bad {bad} refs/heads/bad {self.base}\nrefs/heads/ok {ok} refs/heads/ok {self.base}\n"):
            r = self.hook(inp); self.assertEqual(r.returncode, 1, r.stderr); self.assertIn("verify-raw 未通过（refs/heads/bad", r.stderr)

    def test_hook_multi_ref_all_good_passes(self):
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        r = self.hook(f"refs/heads/a {ok} refs/heads/a {self.base}\nrefs/heads/b {ok} refs/heads/b {'0' * 40}\n"
                      f"refs/tags/v1 {ok} refs/tags/v1 {'0' * 40}\n(delete) {'0' * 40} refs/heads/tmp {self.base}\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_hook_multi_ref_with_tag_deletion_fails(self):
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        r = self.hook(f"refs/heads/a {ok} refs/heads/a {self.base}\n(delete) {'0' * 40} refs/tags/v1 {self.base}\n")
        self.assertEqual(r.returncode, 1); self.assertIn("禁止删除不可变 ref refs/tags/v1", r.stderr)

    def test_hook_other_branch_deletion_allowed(self):
        r = self.hook(f"(delete) {'0' * 40} refs/heads/tmp {self.base}\n"); self.assertEqual(r.returncode, 0, r.stderr)

    def test_hook_tag_retarget_fails(self):
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")   # 子孙提交，快进也不行
        r = self.hook(f"refs/tags/v1 {ok} refs/tags/v1 {self.base}\n")
        self.assertEqual(r.returncode, 1); self.assertIn("禁止改指已有 tag", r.stderr)

    def test_hook_non_commit_target_rejected(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        r = self.hook(f"refs/heads/t {tree} refs/heads/t {'0' * 40}\n")
        self.assertEqual(r.returncode, 1); self.assertIn("不是提交", r.stderr)

    def test_hook_unknown_object_rejected(self):
        r = self.hook(f"refs/heads/t {'1' * 40} refs/heads/t {'0' * 40}\n"); self.assertEqual(r.returncode, 1)

    def fake_git(self, cond):
        fake = Path(tempfile.mkdtemp()); real = shutil.which("git")
        (fake / "git").write_text(f'#!/bin/sh\n{cond} && exit 128\nexec {real} "$@"\n'); (fake / "git").chmod(0o755)
        return dict(self.env, PATH=f"{fake}:{os.environ['PATH']}")

    def test_hook_git_failures_fail_closed(self):
        (self.repo / "n.txt").write_text("n\n"); ok = self.commit("ok")
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", self.base], cwd=self.repo, check=True)
        for cond, inp in [
            ('[ "$1" = rev-parse ] && [ "$2" = -q ]', f"refs/heads/a {ok} refs/heads/a {self.base}\n"),
            ('[ "$1" = cat-file ] && [ "$2" = -t ]', f"refs/heads/a {ok} refs/heads/a {self.base}\n"),
            ('[ "$1" = merge-base ] && [ "$2" != --is-ancestor ]', f"refs/heads/a {ok} refs/heads/a {'0' * 40}\n"),
            ('[ "$1" = for-each-ref ]', f"refs/heads/a {ok} refs/heads/a {'0' * 40}\n"),
            ('[ "$1" = ls-tree ]', f"refs/heads/a {ok} refs/heads/a {self.base}\n"),
        ]:
            with self.subTest(cond=cond):
                r = self.hook(inp, env=self.fake_git(cond)); self.assertEqual(r.returncode, 1, cond + r.stderr)
        r = self.hook(f"refs/heads/a {ok} refs/heads/a {self.base}\n"); self.assertEqual(r.returncode, 0, r.stderr)

    def test_verify_merge_base_git_error_fails(self):
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", self.base], cwd=self.repo, check=True)
        env = self.fake_git('[ "$1" = merge-base ]'); env.pop("VERIFY_RAW_BASE", None)
        r = subprocess.run(["bash", "scripts/verify-raw.sh"], cwd=self.repo, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1); self.assertIn("git 命令失败", r.stdout)


class PublicLocalPath(Base):
    def setUp(self):
        super().setUp()
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"     # 多次提交时不把 __pycache__ 带进测试仓库

    def add_raw(self, body, name=None):
        self.n = getattr(self, "n", 0) + 1     # 每次用新文件名：父提交里已有的路径属于豁免
        (self.repo / "raw").mkdir(exist_ok=True); (self.repo / f"raw/{name or 'a%d.json' % self.n}").write_text(body)
        self.commit("add")

    def test_url_path_not_flagged(self):
        self.add_raw('{"url": "https://sam.gov/workspace/contract/1", "u2": "sam.gov/workspace/x", "u3": "https://x/home/y"}\n')
        self.expect(self.public(), True)

    def test_home_path_flagged(self):
        self.add_raw("stored at '/home/box/x'\n")
        self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_file_uri_flagged(self):
        self.add_raw('{"p": "file:///workspace/a"}\n')
        self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_json_escaped_flagged(self):
        self.add_raw('{"p": "\\/workspace\\/a"}\n')
        self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_escaped_host_url_and_fragment_not_flagged(self):
        self.add_raw('{"u": "https:\\/\\/sam.gov\\/workspace\\/x", "f": "https://x/#/workspace/a"}\n')
        self.expect(self.public(), True)

    def test_quoted_workspace_path_flagged(self):
        self.add_raw('{"p": "/workspace/a"}\n')
        self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

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

    # ---- r3：按 URI 判断 ----
    def test_file_uri_variants_flagged(self):
        for body in ['{"p": "file://localhost/workspace/a"}\n', '{"p": "file:/workspace/a"}\n',
                     '{"p": "FILE:///workspace/a"}\n', '{"p": "file:\\/\\/\\/workspace\\/a"}\n',
                     'see File:///home/x\n', '{"p": "file:///tmp/a"}\n', '{"p": "file:\\u002f\\u002f\\u002fworkspace"}\n',
                     'not json file:\\/\\/\\/workspace\\/a\n', '{"p": "x", "p": "file:/home/x"}\n', '{"a": 1}\n{"p": "file://localhost/home/b"}\n']:
            with self.subTest(body=body):
                self.add_raw(body); self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_json_decoded_bare_path_flagged(self):
        for body in ['{"p": "\\u002fworkspace\\u002fa"}\n', '{"/home/x": 1}\n', '{"p": "dir=/workspace/a"}\n',
                     'x=/workspace\n', '{"p": "ftp://h/x?q=/home/y"}\n']:
            with self.subTest(body=body):
                self.add_raw(body); self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")

    def test_http_query_and_fragment_not_flagged(self):
        for body in ['{"u": "https://x/?p=/workspace/a"}\n', '{"u": "http://x.org/a?p=/home/b&q=/workspace"}\n',
                     '{"u": "https:\\/\\/x\\/?p=\\/workspace\\/a"}\n', 'see https://x/#/workspace/a now\n',
                     '{"u": "HTTPS://Sam.gov/home/x"}\n', 'profile:/workspace-not\n']:
            with self.subTest(body=body):
                self.add_raw(body); self.expect(self.public(), True)

    def test_https_without_host_flagged(self):
        self.add_raw('{"u": "https:///workspace/a"}\n'); self.expect(self.public(), False, "E-PUBLIC-LOCAL-PATH")


if __name__ == "__main__":
    unittest.main()
