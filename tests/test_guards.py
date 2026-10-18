"""#11 守卫反例测试：check-internal / check-public / pre-push 都检查 git 对象。
每个用例同时断言 status（退出码 → 通过/失败）、low_risk（守卫不产生低风险放行：恒 False 的 publishable 语义以退出码表示）与错误码。"""
import os, shutil, subprocess, tempfile, unittest
from pathlib import Path
import helpers  # noqa: F401
from helpers import DUMMY_INTERNAL

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ZERO = "0" * 40


def sh(*a, cwd, env=None, inp=None):
    return subprocess.run(list(a), cwd=cwd, env=env, input=inp, capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp()) / "pub"
        self.repo.mkdir()
        shutil.copytree(SCRIPTS, self.repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / "review/ledger").mkdir(parents=True)
        (self.repo / "review/ledger/.gitkeep").write_text("")
        self.idir = Path(tempfile.mkdtemp()) / "markjin-internal"
        self.idir.mkdir(mode=0o700)
        (self.idir / "topics-private.md").write_text(
            "| 名称 | 识别条件 | 来源 |\n|---|---|---|\n" + "".join(f"| {t} | 条件{n} | 来源{n} |\n" for n, t in enumerate(DUMMY_INTERNAL)),
            encoding="utf-8")
        self.env = dict(os.environ, MARKJIN_INTERNAL_DIR=str(self.idir),
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@e")
        sh("git", "init", "-q", cwd=self.repo)
        (self.repo / "a.md").write_text("公开内容\n", encoding="utf-8")
        self.commit("init")

    def commit(self, msg, add="-A"):
        sh("git", "add", add, cwd=self.repo)
        r = sh("git", "commit", "-qm", msg, cwd=self.repo, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.head()

    def head(self):
        return sh("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()

    def internal(self, *args, env=None, inp=None):
        if "--pre-push" in args and getattr(self, "PUSH_URL", None) and "--remote-url" not in args:
            args = (*args, "--remote", "origin", "--remote-url", self.PUSH_URL)
        return sh("python3", "scripts/check-internal.py", *args, cwd=self.repo, env=env or self.env, inp=inp)

    def public(self, *args, env=None, inp=None):
        if "--pre-push" in args and getattr(self, "PUSH_URL", None) and "--remote-url" not in args:
            args = (*args, "--remote", "origin", "--remote-url", self.PUSH_URL)
        return sh("python3", "scripts/check-public.py", *args, cwd=self.repo, env=env or self.env, inp=inp)

    def hook(self, inp, env=None, remote="origin", url=None):
        return sh("sh", "scripts/hooks/pre-push", remote, url or getattr(self, "PUSH_URL", None) or "u", cwd=self.repo, env=env or self.env, inp=inp)

    def push_line(self, sha=None, remote=ZERO):
        return f"refs/heads/x {sha or self.head()} refs/heads/x {remote}\n"

    def expect(self, r, ok, code=None, low_risk=False):
        # 断言系统的实际输出：退出码、最后一行的结论、错误码出现在 FAIL 行中；守卫输出从不含低风险结论
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0 if ok else 1, out)
        last = (r.stdout.strip().splitlines() or [""])[-1]
        if ok:
            self.assertNotIn("FAIL", r.stdout, out); self.assertRegex(last, "通过", out)
        else:
            self.assertRegex(r.stdout, r"(?m)^FAIL ", out)
        self.assertNotIn("low_risk", out); self.assertNotIn("AUTO_APPROVED", out)
        if code:
            self.assertRegex(r.stdout, r"(?m)^FAIL .*" + code, out)


class CheckInternal(Base):
    def test_clean_passes(self):
        self.expect(self.internal("--rev", "HEAD"), True)

    def test_content_hit_redacted(self):
        (self.repo / "secret-name.md").write_text("第一行\n关于样例内部词乙的段落\n", encoding="utf-8")
        c = self.commit("add b")
        r = self.internal("--rev", "HEAD")
        self.expect(r, False, "E-BLOCK-INTERNAL")
        self.assertIn(f"{c[:12]}:#", r.stdout); self.assertIn(":L2", r.stdout)
        self.assertNotIn("secret-name", r.stdout); self.assertNotIn(DUMMY_INTERNAL[1], r.stdout)

    def test_review_records_scanned(self):
        # review/ 下无法做字段校验的记录：内部清单扫描覆盖（日审 md 与 Codex 日志）
        (self.repo / "review/codex").mkdir(parents=True, exist_ok=True)
        for p, t in (("review/2026-10-12.md", f"# 日审 2026-10-12\n{DUMMY_INTERNAL[0]}\n"),
                     ("review/codex/x.log", f"OpenAI Codex v1\n{DUMMY_INTERNAL[1]}\n")):
            (self.repo / p).write_text(t, encoding="utf-8"); self.commit("r " + p)
            r = self.internal("--rev", "HEAD")
            self.expect(r, False, "E-BLOCK-INTERNAL"); self.assertNotIn(DUMMY_INTERNAL[0], r.stdout); self.assertNotIn(DUMMY_INTERNAL[1], r.stdout)
            (self.repo / p).unlink(); self.commit("rm")

    def test_path_hit(self):
        (self.repo / f"{DUMMY_INTERNAL[0]}.md").write_text("ok\n", encoding="utf-8"); self.commit("p")
        r = self.internal("--rev", "HEAD")
        self.expect(r, False, "E-BLOCK-INTERNAL"); self.assertIn(":path", r.stdout)
        self.assertNotIn(DUMMY_INTERNAL[0], r.stdout)

    def test_other_columns_protected(self):
        (self.repo / "c.md").write_text("来源1\n", encoding="utf-8"); self.commit("c")
        self.expect(self.internal("--rev", "HEAD"), False, "E-BLOCK-INTERNAL")

    def test_normalized_and_cross_line(self):
        for body in ("样例\u200b内部词甲\n", "样例内部\n词甲\n", "样 例 内 部 词 甲\n"):
            (self.repo / "n.md").write_text(body, encoding="utf-8"); self.commit("n")
            self.expect(self.internal("--rev", "HEAD"), False, "E-BLOCK-INTERNAL")

    def test_message_hit(self):
        (self.repo / "m.md").write_text("x\n", encoding="utf-8"); c = self.commit("关于样例内部词甲")
        r = self.internal("--rev", "HEAD"); self.expect(r, False, "E-BLOCK-INTERNAL")
        self.assertIn(f"{c[:12]}:msg", r.stdout)

    def test_hit_in_middle_commit_removed_later(self):
        (self.repo / "b.md").write_text("样例内部词甲\n", encoding="utf-8"); bad = self.commit("b")
        (self.repo / "b.md").unlink(); self.commit("rm")
        r = self.internal("--pre-push", inp=self.push_line())
        self.expect(r, False, "E-BLOCK-INTERNAL"); self.assertIn(bad[:12], r.stdout)

    def test_new_branch_not_excluded_by_remotes(self):
        (self.repo / "b.md").write_text("样例内部词甲\n", encoding="utf-8"); bad = self.commit("b")
        sh("git", "update-ref", "refs/remotes/origin/fake", bad, cwd=self.repo)   # 伪造/过期的远端引用
        (self.repo / "b.md").unlink(); self.commit("rm")
        self.expect(self.internal("--pre-push", inp=self.push_line()), False, "E-BLOCK-INTERNAL")

    def test_existing_branch_range(self):
        base = self.head()
        (self.repo / "b.md").write_text("样例内部词甲\n", encoding="utf-8"); self.commit("b")
        self.expect(self.internal("--pre-push", inp=self.push_line(remote=base)), False, "E-BLOCK-INTERNAL")

    def test_worktree_not_used(self):
        (self.repo / "dirty.md").write_text("样例内部词甲\n", encoding="utf-8")   # 未提交
        self.expect(self.internal("--pre-push", inp=self.push_line()), True)

    def test_decode_failure_rejected(self):
        (self.repo / "bin.dat").write_bytes(b"\xff\xfe\x00\x01"); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")

    def test_stdin_empty_or_malformed(self):
        for inp in ("", "\n", "garbage\n", f"refs/heads/x {self.head()} refs/heads/x\n",
                    f"refs/heads/x {'z' * 40} refs/heads/x {ZERO}\n"):
            self.expect(self.internal("--pre-push", inp=inp), False, "E-CHECK-STDIN")
        self.expect(self.internal(), False, "E-CHECK-STDIN")

    def test_list_missing_or_invalid_fail_closed(self):
        p = self.idir / "topics-private.md"
        for setup in ("missing", "empty", "no-table", "two-cols", "empty-cell", "dup"):
            if setup == "missing":
                p.unlink(missing_ok=True)
            else:
                p.write_text({"empty": "", "no-table": "说明\n",
                              "two-cols": "| 名称 | 来源 |\n|---|---|\n| a | b |\n",
                              "empty-cell": "| 名称 | 识别条件 | 来源 |\n|---|---|---|\n| a |  | b |\n",
                              "dup": "| 名称 | 识别条件 | 来源 |\n|---|---|---|\n| a | b | c |\n| a | d | e |\n"}[setup],
                             encoding="utf-8")
            self.expect(self.internal("--rev", "HEAD"), False, "E-INTERNAL-LIST-MISSING")

    def test_bad_rev(self):
        self.expect(self.internal("--rev", "deadbeef"), False, "E-CHECK-GIT")

    def test_pre_push_hook(self):
        self.expect(self.hook(self.push_line()), True)
        (self.repo / "b.md").write_text("样例内部词甲\n", encoding="utf-8"); self.commit("b")
        self.expect(self.hook(self.push_line()), False, "E-BLOCK-INTERNAL")

    def test_pre_push_hook_empty_stdin(self):
        r = self.hook("")
        self.assertEqual(r.returncode, 1); self.assertIn("E-CHECK-STDIN", r.stderr)

    def test_pre_push_hook_list_missing(self):
        (self.idir / "topics-private.md").unlink()
        self.expect(self.hook(self.push_line()), False, "E-INTERNAL-LIST-MISSING")


class CheckPublic(Base):
    def test_ci_without_internal_list_passes(self):
        env = dict(self.env, MARKJIN_INTERNAL_DIR=str(self.idir / "nope"))
        self.expect(self.public(env=env), True)

    def test_lifted_words_pass(self):
        # 2026-10-11 解禁（王总确认，quote_ref grok-bot:t90u）：两个原禁词出现在内容、路径、提交说明中都不再拦
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        for w in ("中医", "佛学"):
            (self.repo / "b.md").write_text("x\n" + w + "\n", encoding="utf-8"); self.commit("b")
            (self.repo / f"{w}.md").write_text("x\n", encoding="utf-8"); self.commit(f"msg {w}")
            r = self.public(); self.expect(r, True); self.assertNotIn("E-PUBLIC-BANNED", r.stdout)
            (self.repo / f"{w}.md").unlink(); self.commit("rm")

    def test_checks_objects_not_worktree(self):
        (self.repo / "review/notes.md").write_text("x\n", encoding="utf-8")   # 未提交
        self.expect(self.public("--pre-push", inp=self.push_line()), True)
        self.commit("b"); (self.repo / "review/notes.md").unlink()           # 已提交、工作树已删
        self.expect(self.public("--pre-push", inp=self.push_line()), False, "E-REVIEW-PATH")

    def test_internal_path_tracked(self):
        (self.repo / "topics-private.md").write_text("x\n", encoding="utf-8")
        sh("git", "add", "-f", "topics-private.md", cwd=self.repo); self.commit("oops", add="a.md")
        self.expect(self.public(), False, "E-PUBLIC-INTERNAL-PATH")

    def test_decode_failure(self):
        (self.repo / "bin.dat").write_bytes(b"\xff\x00"); self.commit("bin")
        self.expect(self.public(), False, "E-CHECK-DECODE")

    def test_stdin_bad(self):
        for inp in ("", "x y z\n"):
            self.expect(self.public("--pre-push", inp=inp), False, "E-CHECK-STDIN")

    def test_ledger_bad(self):
        d = self.repo / "review/ledger"
        cases = {"2026-10-12.jsonl": '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"note":"x"}\n',
                 "2026-02-30.jsonl": '{"date":"2026-02-30","error_code":"E-REPLAY-001","count":1}\n',
                 "2026-10-13.jsonl": '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1}\n'}
        codes = {"2026-10-12.jsonl": "E-LEDGER-FIELD", "2026-02-30.jsonl": "E-LEDGER-DATE", "2026-10-13.jsonl": "E-LEDGER-DATE"}
        for name, body in cases.items():
            for f in d.glob("*.jsonl"):
                f.unlink()
            (d / name).write_text(body); self.commit(name)
            self.expect(self.public(), False, codes[name])

    def test_ledger_r3(self):
        d = self.repo / "review/ledger"
        (self.repo / ".gitignore").write_text("__pycache__/\n")   # 运行脚本产生的 .pyc 不进测试仓库
        cases = [("notes.md", "任意自由文本\n", "E-LEDGER-FILE"),
                 ("2026-10-12.jsonl", "", "E-LEDGER-EMPTY"),
                 ("2026-10-12.jsonl", '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"自由","card_id":"c1"}\n', "E-LEDGER-VALUE"),
                 ("2026-10-12.jsonl", '{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c9"}\n', "E-LEDGER-CARD")]
        for name, body, code in cases:
            for f in d.iterdir():
                if f.name != ".gitkeep": f.unlink()
            (d / name).write_text(body, encoding="utf-8"); self.commit(name)
            self.expect(self.public(), False, code)
        for f in d.iterdir():
            if f.name != ".gitkeep": f.unlink()
        (self.repo / "cards").mkdir(); (self.repo / "cards/2026-10-12.md").write_text("## 卡 {#c9}\n", encoding="utf-8")
        (d / "2026-10-12.jsonl").write_text('{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c9"}\n')
        self.commit("ok")
        self.expect(self.public("--range", "HEAD~1..HEAD"), True)   # 只看修好后的提交（历史中的坏提交仍会被全量扫描拒绝）
        self.expect(self.public("--rev", "HEAD"), False, "E-LEDGER-CARD")   # r12：全史审计须显式 --rev
        self.expect(self.public(), True)                                    # 不带参数只查 HEAD 提交对象

    def test_review_path_whitelist(self):
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        (self.repo / "review/notes.md").write_text('{"topic":"任意自由文本"}\n', encoding="utf-8"); self.commit("notes")
        self.expect(self.public("--range", "HEAD~1..HEAD"), False, "E-REVIEW-PATH")

    def test_review_record_format(self):
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        (self.repo / "review/codex").mkdir(parents=True, exist_ok=True)
        (self.repo / "review/2026-10-12-r1").mkdir(parents=True, exist_ok=True)
        good = {"review/2026-10-12.md": "# 日审 2026-10-12\n\n内容\n",
                "review/codex/2026-10-12-d01.log": "OpenAI Codex v0.155.1\n--------\n",
                "review/2026-10-12-r1/result-r1.txt": "结论如下\n\nVERDICT: REJECTED\n",
                "review/2026-10-12-r1/review-prompt.md": "# 审查任务\n"}
        for p, t in good.items():
            (self.repo / p).write_text(t, encoding="utf-8")
        self.commit("good")
        self.expect(self.public("--range", "HEAD~1..HEAD"), True)
        bad = {"review/2026-10-12.md": '{"topic":"任意自由文本"}\n',               # 首行不是带日期的标题
               "review/codex/2026-10-12-d01.log": "随便写的内部审查描述\n",         # 不是 Codex 日志
               "review/2026-10-12-r1/result-r1.txt": "VERDICT: `APPROVED`\n",       # 不是纯文本 VERDICT 行
               "review/2026-10-12-r1/review-prompt.md": "# x\n见 ../markjin-internal/a\n"}
        for p, t in bad.items():
            (self.repo / p).write_text(t, encoding="utf-8"); self.commit("bad " + p)
            self.expect(self.public("--range", "HEAD~1..HEAD"), False, "E-REVIEW-FORMAT")
            (self.repo / p).write_text(good[p], encoding="utf-8"); self.commit("fix")

    def test_empty_range_rejected(self):
        self.expect(self.public("--range", "HEAD..HEAD"), False, "E-CHECK-EMPTY")
        self.expect(self.internal("--range", "HEAD..HEAD"), False, "E-CHECK-EMPTY")

    def test_ledger_dir_missing(self):
        shutil.rmtree(self.repo / "review"); self.commit("rm ledger")
        self.expect(self.public("--rev", "HEAD", "--range", "HEAD~1..HEAD"), False, "E-LEDGER-DIR")

    def test_hook_runs_public(self):
        (self.repo / "review/notes.md").write_text("x\n", encoding="utf-8"); self.commit("b")
        self.expect(self.hook(self.push_line()), False, "E-REVIEW-PATH")


if __name__ == "__main__":
    unittest.main()


class R8Guards(Base):
    def test_ref_name_scanned(self):
        w = DUMMY_INTERNAL[0]
        line = f"refs/heads/{w} {self.head()} refs/heads/{w} {ZERO}\n"
        r = self.internal("--pre-push", inp=line); self.expect(r, False, "E-BLOCK-INTERNAL")
        self.assertIn("push:#1:ref", r.stdout); self.assertNotIn(w, r.stdout)
        self.expect(self.hook(line), False, "E-BLOCK-INTERNAL")
        self.expect(self.internal("--pre-push", inp=self.push_line()), True)     # 正常分支名照常通过

    def test_annotated_tag_message_scanned(self):
        sh("git", "tag", "-a", "v1", "-m", "说明 " + DUMMY_INTERNAL[1], cwd=self.repo, env=self.env)
        tag = sh("git", "rev-parse", "v1", cwd=self.repo).stdout.strip()
        line = f"refs/tags/v1 {tag} refs/tags/v1 {ZERO}\n"
        r = self.internal("--pre-push", inp=line); self.expect(r, False, "E-BLOCK-INTERNAL")
        self.assertIn("push:#1:tag", r.stdout)
        sh("git", "tag", "-a", "v2", "-m", "普通说明", cwd=self.repo, env=self.env)
        t2 = sh("git", "rev-parse", "v2", cwd=self.repo).stdout.strip()
        self.expect(self.internal("--pre-push", inp=f"refs/tags/v2 {t2} refs/tags/v2 {ZERO}\n"), True)

    def test_empty_range_always_errors(self):
        for args in (("--range", "HEAD..HEAD"), ("--rev", "HEAD", "--range", "HEAD..HEAD"),
                     ("--range", "HEAD~0..HEAD", "--range", "HEAD..HEAD")):
            self.expect(self.public(*args), False, "E-CHECK-EMPTY")
            self.expect(self.internal(*args), False, "E-CHECK-EMPTY")


class R7ReviewGuards(Base):
    """第 7 轮审查意见：强推倒退零提交报错；附注标签嵌套不设深度上限。"""
    def test_force_push_rewind_zero_commits_errors(self):
        old = self.head()
        (self.repo / "README.md").write_text("more\n", encoding="utf-8"); self.commit("c2")
        new = self.head()
        # 远端在 new，本地推 old（倒退）：remote..local 为空 → 拒绝，而不是“通过”
        line = f"refs/heads/main {old} refs/heads/main {new}\n"
        self.expect(self.internal("--pre-push", inp=line), False, "E-CHECK-EMPTY")
        self.expect(self.hook(line), False, "E-CHECK-EMPTY")
        # 对照：正常前进推送照常通过
        self.expect(self.internal("--pre-push", inp=f"refs/heads/main {new} refs/heads/main {old}\n"), True)

    def test_deeply_nested_tag_scanned(self):
        prev = "HEAD"
        for k in range(12):                     # 12 层嵌套，命中词只放在最内层标签说明
            msg = ("说明 " + DUMMY_INTERNAL[1]) if k == 0 else f"层 {k}"
            sh("git", "tag", "-a", f"n{k}", prev, "-m", msg, cwd=self.repo, env=self.env)
            prev = f"n{k}"
        tag = sh("git", "rev-parse", "n11", cwd=self.repo).stdout.strip()
        r = self.internal("--pre-push", inp=f"refs/tags/n11 {tag} refs/tags/n11 {ZERO}\n")
        self.expect(r, False, "E-BLOCK-INTERNAL"); self.assertIn("push:#1:tag", r.stdout)


class R8ReviewGuards(Base):
    """第 8 轮审查意见：提交头 / 标签头扫描、标签目标的台账目录、显式空 --rev、bare 仓库。"""
    def test_commit_author_committer_scanned(self):
        for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME", "GIT_AUTHOR_EMAIL"):
            (self.repo / "a.md").write_text(f"干净 {var}\n", encoding="utf-8")
            env = dict(self.env, **{var: DUMMY_INTERNAL[1] + ("@e" if "EMAIL" in var else "")})
            sh("git", "add", "-A", cwd=self.repo)
            self.assertEqual(sh("git", "commit", "-qm", "clean", cwd=self.repo, env=env).returncode, 0)
            r = self.internal("--pre-push", inp=self.push_line())
            self.expect(r, False, "E-BLOCK-INTERNAL")
            sh("git", "reset", "-q", "--hard", "HEAD~1", cwd=self.repo)
        self.expect(self.internal("--rev", "HEAD"), True)

    def test_tagger_scanned(self):
        env = dict(self.env, GIT_COMMITTER_NAME=DUMMY_INTERNAL[1])     # tagger 取 committer 身份
        sh("git", "tag", "-a", "v1", "-m", "clean", cwd=self.repo, env=env)
        tag = sh("git", "rev-parse", "v1", cwd=self.repo).stdout.strip()
        r = self.internal("--pre-push", inp=f"refs/tags/v1 {tag} refs/tags/v1 {ZERO}\n")
        self.expect(r, False, "E-BLOCK-INTERNAL"); self.assertIn("push:#1:tag", r.stdout)
        sh("git", "tag", "-a", "v2", "-m", "clean", cwd=self.repo, env=self.env)
        t2 = sh("git", "rev-parse", "v2", cwd=self.repo).stdout.strip()
        self.expect(self.internal("--pre-push", inp=f"refs/tags/v2 {t2} refs/tags/v2 {ZERO}\n"), True)

    def test_tag_target_ledger_dir_checked(self):
        shutil.rmtree(self.repo / "review"); self.commit("rm ledger")
        sh("git", "tag", "-a", "old", "-m", "clean", cwd=self.repo, env=self.env)
        tag = sh("git", "rev-parse", "old", cwd=self.repo).stdout.strip()
        self.expect(self.public("--pre-push", inp=f"refs/tags/old {tag} refs/tags/old {ZERO}\n"), False, "E-LEDGER-DIR")

    def test_empty_rev_not_masked(self):
        self.expect(self.public("--rev", "HEAD..HEAD", "--rev", "HEAD"), False, "E-CHECK-EMPTY")
        self.expect(self.internal("--rev", "HEAD..HEAD", "--rev", "HEAD"), False, "E-CHECK-EMPTY")
        self.expect(self.public("--rev", "HEAD"), True)

    def test_bare_repo_internal_dir_rejected(self):
        from markjin.internal import _in_git_repo
        bare = Path(tempfile.mkdtemp()) / "b.git"
        sh("git", "init", "-q", "--bare", str(bare), cwd=self.repo)
        self.assertTrue(_in_git_repo(bare / "internal"))
        self.assertFalse(_in_git_repo(Path(tempfile.mkdtemp()) / "x"))
        env = dict(self.env, MARKJIN_INTERNAL_DIR=str(bare / "internal"))
        r = self.internal("--rev", "HEAD", env=env)
        self.expect(r, False, "E-INTERNAL-LIST-MISSING")


class FinalR1Binary(Base):
    """整体验收 r1 HIGH 1：main 上已登记的二进制原件（raw/<日期>/MANIFEST.sha256 有同字节的 ./相对路径 一行）不判 E-CHECK-DECODE；
    未登记、字节不符、扩展名不在白名单、不在 raw/<日期>/ 下的仍判失败。"""
    PDF = b"%PDF-1.4\n\xff\xfe\x00\x01binary\n"

    def put(self, rel, data, manifest=None):
        import hashlib
        p = self.repo / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        if manifest is not None:
            m = self.repo / "raw/2026-10-11/MANIFEST.sha256"
            h = hashlib.sha256(manifest).hexdigest()
            m.write_text((m.read_text() if m.exists() else "") + f"{h}  ./{rel.split('/', 2)[2]}\n", encoding="utf-8")

    def test_registered_binary_passes(self):
        self.put("raw/2026-10-11/fulltext/a.pdf", self.PDF, manifest=self.PDF); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), True)
        self.expect(self.public(), True)

    def test_registered_binary_in_merge_range_passes(self):
        base = self.head()
        sh("git", "checkout", "-q", "-b", "side", cwd=self.repo)
        self.put("raw/2026-10-11/nbs/x.jpg", self.PDF, manifest=self.PDF); self.commit("side")
        sh("git", "checkout", "-q", "-", cwd=self.repo)
        (self.repo / "c.md").write_text("c\n", encoding="utf-8"); self.commit("c")
        sh("git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "merge", "-q", "--no-edit", "side", cwd=self.repo)
        self.expect(self.internal("--range", f"{base}..HEAD"), True)

    def test_unregistered_or_mismatched_binary_fails(self):
        for rel, man in (("raw/2026-10-11/u.pdf", None), ("raw/2026-10-11/w.pdf", b"other"),
                         ("raw/2026-10-11/e.bin", self.PDF), ("docs/x.pdf", self.PDF)):
            with self.subTest(rel=rel):
                self.setUp()
                self.put(rel, self.PDF, manifest=man if rel.startswith("raw/") else None)
                if not rel.startswith("raw/"):
                    m = self.repo / "raw/2026-10-11/MANIFEST.sha256"; m.parent.mkdir(parents=True, exist_ok=True)
                    import hashlib; m.write_text(f"{hashlib.sha256(self.PDF).hexdigest()}  ./../../docs/x.pdf\n", encoding="utf-8")
                self.commit("bin")
                self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")


class FinalR1ReviewVerdict(unittest.TestCase):
    def test_review_result_accepts_followups(self):
        from markjin.ledger import review_record_errors
        ok = "## 结果\nVERDICT: APPROVED_WITH_FOLLOWUPS\n"
        self.assertEqual(review_record_errors("review/2026-10-11-r1/result-r1.txt", ok), [])
        self.assertEqual(review_record_errors("review/2026-10-11-r1/result-r1.txt", "x\nVERDICT: MAYBE\n"), ["E-REVIEW-FORMAT"])
        from markjin.ledger import REVIEW_ALLOWED
        self.assertTrue(any(r.match("review/2026-10-11-r1/result-r1.txt") for r in REVIEW_ALLOWED))   # 整体验收 r3：测试用的文件名须在白名单内


class FinalR4AsciiBinary(FinalR1Binary):
    """整体验收 r4 HIGH：字节全是 ASCII、能按 UTF-8 解码的 PDF/图片也必须先做登记校验。"""
    APDF = b"%PDF-1.4\n1 0 obj << >> endobj\ntrailer\n%%EOF\n"

    def test_ascii_registered_passes(self):
        self.put("raw/2026-10-11/fulltext/a.pdf", self.APDF, manifest=self.APDF); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), True); self.expect(self.public(), True)

    def test_ascii_unregistered_fails(self):
        self.put("raw/2026-10-11/fulltext/a.pdf", self.APDF); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")

    def test_ascii_hash_mismatch_fails(self):
        self.put("raw/2026-10-11/fulltext/a.pdf", self.APDF, manifest=self.APDF + b"x"); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")

    def test_ascii_outside_raw_fails(self):
        p = self.repo / "docs/x.pdf"; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(self.APDF); self.commit("bin")
        self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")


class FinalR5(Base):
    """整体验收 r5 + r6 协调方决定：pre-push 在可信上游 main 核验通过后只扫新引入的提交；
    check-public 不把未闭合注释里的 card_id 当锚点。"""
    UPSTREAM = "https://github.com/markjin-lab/markjin-data.git"
    PUSH_URL = UPSTREAM          # r7：模拟 pre-push 的 $2 = 实际推送 URL（测试里经 insteadOf 改写到本地 bare）
    BAD = b"%PDF-1.4 unregistered\n"

    def _upstream(self, url=None):
        import tempfile as _t
        self.bare = Path(_t.mkdtemp()) / "up.git"
        sh("git", "init", "-q", "--bare", str(self.bare), cwd=self.repo)
        sh("git", "config", f"url.{self.bare}.insteadOf", url or self.UPSTREAM, cwd=self.repo)   # 测试：规范 URL 改写到本地 bare 仓库
        sh("git", "remote", "add", "origin", url or self.UPSTREAM, cwd=self.repo)
        # main 历史里放一个旧坏提交（未登记的二进制），模拟 #34 的 b5cfa0a / c289cb3
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        p = self.repo / "raw/2026-10-11/fulltext/old.pdf"; p.parent.mkdir(parents=True); p.write_bytes(self.BAD)
        self.commit("old bad")
        p.unlink(); self.commit("cleanup")
        sh("git", "branch", "-M", "main", cwd=self.repo)
        self.assertEqual(sh("git", "push", "-q", "origin", "main", cwd=self.repo, env=self.env).returncode, 0)
        sh("git", "fetch", "-q", "origin", cwd=self.repo, env=self.env)
        sh("git", "checkout", "-q", "-b", "feat/new", cwd=self.repo)
        (self.repo / "b.md").write_text("新内容\n", encoding="utf-8")
        return self.commit("new work")

    def line(self, sha):
        return f"refs/heads/feat/new {sha} refs/heads/feat/new {ZERO}\n"

    def test_new_branch_skips_verified_upstream_history(self):
        tip = self._upstream()
        self.expect(self.public("--rev", "HEAD"), False, "E-CHECK-DECODE")    # 全量历史扫描仍报旧坏提交（不改历史）
        self.expect(self.public("--pre-push", inp=self.line(tip)), True)
        self.expect(self.internal("--pre-push", inp=self.line(tip)), True)
        self.expect(self.hook(self.line(tip)), True)

    def test_new_bad_commit_still_blocked(self):
        self._upstream()
        p = self.repo / "raw/2026-10-11/fulltext/new.pdf"; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(self.BAD)
        tip = self.commit("new bad")
        self.expect(self.public("--pre-push", inp=self.line(tip)), False, "E-CHECK-DECODE")
        self.expect(self.hook(self.line(tip)), False, "E-CHECK-DECODE")

    def test_untrusted_or_stale_upstream_falls_back_to_full_scan(self):
        # 1) origin URL 不是 markjin-lab/markjin-data → 不信任 → 全量扫描 → 旧坏提交照旧拦
        self.setUp()
        tip = self._upstream(url="https://example.invalid/other.git")
        self.expect(self.public("--pre-push", inp=self.line(tip)), False, "E-CHECK-DECODE")
        # 2) 本地 origin/main 与远端 main 不一致（过期）→ 全量扫描
        self.setUp()
        tip = self._upstream()
        sh("git", "update-ref", "refs/remotes/origin/main", tip, cwd=self.repo)
        self.expect(self.public("--pre-push", inp=self.line(tip)), False, "E-CHECK-DECODE")

    def test_trusted_upstream_helper(self):
        from markjin import gitscan
        self.assertIsNone(gitscan.trusted_upstream_main(str(self.repo)))       # 没有 origin
        for ok in ("https://github.com/markjin-lab/markjin-data.git", "git@github.com:markjin-lab/markjin-data.git",
                   "https://github.com/markjin-lab/markjin-data"):
            self.assertTrue(gitscan.TRUSTED_UPSTREAM_RE.fullmatch(ok), ok)
        for bad in ("https://github.com/markjin-lab/markjin-data.git.evil", "https://github.com/evil/markjin-data.git",
                    "https://github.com/markjin-lab/markjin-data.git\n"):
            self.assertIsNone(gitscan.TRUSTED_UPSTREAM_RE.fullmatch(bad), bad)

    def test_unclosed_comment_anchor_check_public(self):
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        (self.repo / "cards").mkdir(); (self.repo / "cards/2026-10-12.md").write_text("<!--\n## 卡 {#c1}\n", encoding="utf-8")
        (self.repo / "review/ledger/2026-10-12.jsonl").write_text('{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c1"}\n')
        self.commit("c")
        self.expect(self.public("--range", "HEAD~1..HEAD"), False, "E-LEDGER-CARD")


class FinalR6(FinalR5):
    """整体验收 r6：零新增提交的 ref 更新（标签指向上游旧提交）至少扫所指提交；MANIFEST 严格解析；未闭合围栏锚点。"""
    def test_tag_on_old_upstream_commit_scans_target(self):
        self._upstream()
        # 上游 main 历史里有一个缺 review/ledger/ 的旧提交：新附注标签指向它
        sh("git", "checkout", "-q", "main", cwd=self.repo)
        old = sh("git", "rev-parse", "main~1", cwd=self.repo).stdout.strip()
        sh("git", "tag", "-a", "t-old", old, "-m", "old", cwd=self.repo, env=self.env)
        tag = sh("git", "rev-parse", "t-old", cwd=self.repo).stdout.strip()
        line = f"refs/tags/t-old {tag} refs/tags/t-old {ZERO}\n"
        r = self.public("--pre-push", inp=line)
        self.assertEqual(r.returncode, 1, r.stdout)                  # 旧提交含未登记 PDF → 被扫描并拒绝
        self.assertIn("E-CHECK-DECODE", r.stdout)

    def test_tag_on_commit_without_ledger_dir(self):
        self._upstream()
        sh("git", "checkout", "-q", "main", cwd=self.repo)
        # 构造一个上游 main 上的提交，树里没有 review/ledger/
        tree = sh("git", "mktree", cwd=self.repo, inp="").stdout.strip()
        c = sh("git", "commit-tree", tree, "-p", "HEAD", "-m", "empty tree", cwd=self.repo, env=self.env).stdout.strip()
        sh("git", "update-ref", "refs/heads/main", c, cwd=self.repo)
        self.assertEqual(sh("git", "push", "-q", "origin", "main", cwd=self.repo, env=self.env).returncode, 0)
        sh("git", "fetch", "-q", "origin", cwd=self.repo, env=self.env)
        sh("git", "tag", "-a", "t-empty", c, "-m", "x", cwd=self.repo, env=self.env)
        tag = sh("git", "rev-parse", "t-empty", cwd=self.repo).stdout.strip()
        self.expect(self.public("--pre-push", inp=f"refs/tags/t-empty {tag} refs/tags/t-empty {ZERO}\n"), False, "E-LEDGER-DIR")

    def test_new_branch_equal_to_upstream_scans_tip(self):
        self._upstream()
        sh("git", "checkout", "-q", "main", cwd=self.repo)
        tip = sh("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        r = self.public("--pre-push", inp=f"refs/heads/same {tip} refs/heads/same {ZERO}\n")
        self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("1 个提交", r.stdout)

    def test_malformed_manifest_does_not_register_binary(self):
        import hashlib
        h = hashlib.sha256(self.PDF if hasattr(self, "PDF") else b"%PDF").hexdigest()
        data = b"%PDF-1.4\n\xff\xfe binary"
        h = hashlib.sha256(data).hexdigest()
        for manifest in (f"{h}  ./fulltext/a.pdf\ngarbage\n", f"{h}  ./fulltext/a.pdf\n{h}  ./fulltext/a.pdf\n",
                         f"{h}  ./fulltext/a.pdf\n{h}  ../x.pdf\n"):
            with self.subTest(manifest=manifest):
                self.setUp()
                p = self.repo / "raw/2026-10-11/fulltext/a.pdf"; p.parent.mkdir(parents=True); p.write_bytes(data)
                (self.repo / "raw/2026-10-11/MANIFEST.sha256").write_text(manifest, encoding="utf-8")
                self.commit("bin")
                self.expect(self.internal("--rev", "HEAD"), False, "E-CHECK-DECODE")
        self.setUp()
        p = self.repo / "raw/2026-10-11/fulltext/a.pdf"; p.parent.mkdir(parents=True); p.write_bytes(data)
        (self.repo / "raw/2026-10-11/MANIFEST.sha256").write_text(f"{h}  ./fulltext/a.pdf\n", encoding="utf-8")
        self.commit("bin ok")
        self.expect(self.internal("--rev", "HEAD"), True)

    def test_unclosed_fence_anchor_check_public(self):
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        (self.repo / "cards").mkdir(); (self.repo / "cards/2026-10-12.md").write_text("```\n## 卡 {#c1}\n", encoding="utf-8")
        (self.repo / "review/ledger/2026-10-12.jsonl").write_text('{"date":"2026-10-12","error_code":"E-REPLAY-001","count":1,"card_id":"c1"}\n')
        self.commit("c")
        self.expect(self.public("--range", "HEAD~1..HEAD"), False, "E-LEDGER-CARD")


class FinalR7(FinalR5):
    """整体验收 r7：pre-push 只在推往 markjin-lab/markjin-data 且远端 main 等于基线时才只扫新增提交；围栏长度；文档口径。"""

    def test_push_to_other_remote_full_scan(self):
        tip = self._upstream()
        import tempfile as _t
        other = Path(_t.mkdtemp()) / "other.git"
        sh("git", "init", "-q", "--bare", str(other), cwd=self.repo)
        sh("git", "remote", "add", "mirror", str(other), cwd=self.repo)
        # origin 可信，但实际推往另一个空远端 → 全量扫描 → 历史里的旧坏提交照旧拦
        self.expect(self.public("--pre-push", "--remote", "mirror", "--remote-url", str(other), inp=self.line(tip)),
                    False, "E-CHECK-DECODE")
        self.expect(self.internal("--pre-push", "--remote", "mirror", "--remote-url", str(other), inp=self.line(tip)),
                    False, "E-CHECK-DECODE")
        self.expect(self.hook(self.line(tip), remote="mirror", url=str(other)), False, "E-CHECK-DECODE")
        # 真实 git push 触发 hook：推往 mirror 被拒，推往 origin 通过
        sh("git", "config", "core.hooksPath", "scripts/hooks", cwd=self.repo)
        self.assertNotEqual(sh("git", "push", "-q", "mirror", "feat/new", cwd=self.repo, env=self.env).returncode, 0)

    def test_untrusted_name_or_missing_url_full_scan(self):
        tip = self._upstream()
        self.expect(self.public("--pre-push", "--remote-url", "", inp=self.line(tip)), False, "E-CHECK-DECODE")
        self.expect(self.public("--pre-push", "--remote", "mirror", "--remote-url", self.UPSTREAM, inp=self.line(tip)),
                    False, "E-CHECK-DECODE")
        self.expect(self.public("--pre-push", "--remote", "origin", "--remote-url", "https://github.com/evil/markjin-data.git",
                                inp=self.line(tip)), False, "E-CHECK-DECODE")

    def test_untrusted_pushurl_full_scan(self):
        tip = self._upstream()
        sh("git", "config", "remote.origin.pushurl", "https://example.invalid/x.git", cwd=self.repo)
        self.expect(self.public("--pre-push", inp=self.line(tip)), False, "E-CHECK-DECODE")

    def test_remote_main_moved_full_scan(self):
        tip = self._upstream()
        # 远端 main 前进（本地基线过期）→ 全量
        self.assertEqual(sh("git", "push", "-q", "--no-verify", "origin", f"{tip}:refs/heads/tmp", cwd=self.repo, env=self.env).returncode, 0)
        self.assertEqual(sh("git", "--git-dir", str(self.bare), "update-ref", "refs/heads/main", tip, cwd=self.repo).returncode, 0)
        self.assertNotEqual(sh("git", "rev-parse", "origin/main", cwd=self.repo).stdout.strip(), tip)   # 本地基线未变
        self.expect(self.public("--pre-push", inp=self.line(tip)), False, "E-CHECK-DECODE")

    def test_trusted_target_only_new_commits(self):
        tip = self._upstream()
        self.expect(self.public("--pre-push", inp=self.line(tip)), True)
        self.expect(self.hook(self.line(tip)), True)

    def test_longer_closing_fence(self):
        from markjin.ledger import anchors_list
        self.assertEqual(anchors_list("```\ncode {#x}\n````\n## 卡 {#c1}\n"), ["c1"])
        self.assertEqual(anchors_list("````\ncode {#x}\n`````\n## 卡 {#c1}\n"), ["c1"])
        self.assertEqual(anchors_list("~~~\n{#x}\n~~~~~\n{#c2}\n"), ["c2"])
        self.assertEqual(anchors_list("````\n{#x}\n```\n{#c3}\n"), [])          # 更短的闭围栏不算 → 延续到文末
        self.assertEqual(anchors_list("```\n{#x}\n~~~\n{#c4}\n"), [])           # 不同字符不算
        self.assertEqual(anchors_list("```\n{#x}\n"), [])

    def test_docs_match_code(self):
        import markjin.gitscan as G, markjin.ledger as L
        self.assertNotIn("无需扫描", G.__doc__)
        self.assertIn("停用", L.__doc__)
        self.assertIn("停用", (self.repo / "review/README.md").read_text(encoding="utf-8") if (self.repo / "review/README.md").exists()
                      else (Path(G.__file__).resolve().parents[2] / "review/README.md").read_text(encoding="utf-8"))


class FinalR8(FinalR5):
    """整体验收 r8：已有分支推往其他远端也全量扫描；只有可信目标且远端 main = 基线才只扫增量。"""

    def _existing(self):
        tip = self._upstream()
        # feat/new 已推到 origin（远端 SHA 本地存在），再加一个干净提交
        self.assertEqual(sh("git", "push", "-q", "--no-verify", "origin", "feat/new", cwd=self.repo, env=self.env).returncode, 0)
        (self.repo / "c.md").write_text("再加一段\n", encoding="utf-8")
        new = self.commit("more")
        return tip, new

    def line2(self, old, new):
        return f"refs/heads/feat/new {new} refs/heads/feat/new {old}\n"

    def test_existing_branch_to_other_remote_full_scan(self):
        old, new = self._existing()
        import tempfile as _t
        other = Path(_t.mkdtemp()) / "other.git"
        sh("git", "init", "-q", "--bare", str(other), cwd=self.repo)
        for fn in (self.public, self.internal):
            self.expect(fn("--pre-push", "--remote", "mirror", "--remote-url", str(other), inp=self.line2(old, new)),
                        False, "E-CHECK-DECODE")
        self.expect(self.hook(self.line2(old, new), remote="mirror", url=str(other)), False, "E-CHECK-DECODE")

    def test_existing_branch_without_url_full_scan(self):
        old, new = self._existing()
        self.expect(self.public("--pre-push", "--remote-url", "", inp=self.line2(old, new)), False, "E-CHECK-DECODE")

    def test_existing_branch_trusted_incremental(self):
        old, new = self._existing()
        r = self.public("--pre-push", inp=self.line2(old, new))
        self.expect(r, True); self.assertIn("1 个提交", r.stdout)
        self.expect(self.hook(self.line2(old, new)), True)

    def test_existing_branch_remote_main_moved_full_scan(self):
        old, new = self._existing()
        self.assertEqual(sh("git", "--git-dir", str(self.bare), "update-ref", "refs/heads/main", old, cwd=self.repo).returncode, 0)
        self.expect(self.public("--pre-push", inp=self.line2(old, new)), False, "E-CHECK-DECODE")

    def test_rewind_still_empty_any_target(self):
        old, new = self._existing()
        for extra in ((), ("--remote", "mirror", "--remote-url", "/tmp/x.git")):
            self.expect(self.public("--pre-push", *extra, inp=self.line2(new, old)), False, "E-CHECK-EMPTY")


class FinalR9Docs(unittest.TestCase):
    """整体验收 r9 MEDIUM：review/README.md 写明增量扫描的可信条件，不再有无条件的“已有分支扫描 remote_sha..local_sha”。"""

    def test_readme_states_trusted_condition(self):
        t = (SCRIPTS.parent / "review" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("，已有分支扫描 `remote_sha..local_sha` 的每个提交，", t)
        i = t.index("remote_sha..local_sha")
        self.assertIn("可信条件", t[max(0, i - 200):i])


class FinalR12HeadOnly(Base):
    """整体验收 r12 MEDIUM：check-public 不带参数只查 HEAD 提交对象（与说明一致），--rev 才扫全部可达提交。"""

    def test_default_head_only(self):
        (self.repo / "bin.dat").write_bytes(b"\xff\xfe\x00\x01"); self.commit("bad")
        (self.repo / "bin.dat").unlink(); self.commit("fix")
        self.expect(self.public(), True)
        self.expect(self.public("--rev", "HEAD"), False, "E-CHECK-DECODE")

    def test_default_head_bad_fails(self):
        (self.repo / "bin.dat").write_bytes(b"\xff\xfe\x00\x01"); self.commit("bad")
        self.expect(self.public(), False, "E-CHECK-DECODE")

    def test_docs(self):
        src = (self.repo / "scripts" / "check-public.py").read_text(encoding="utf-8")
        self.assertIn("只检查 HEAD 这一个提交对象", src)
        t = (SCRIPTS.parent / "review" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("第三种供规划文件使用", t); self.assertIn("第二种（`APPROVED_WITH_FOLLOWUPS`）供规划文件使用", t)
