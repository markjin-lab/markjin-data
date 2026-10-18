"""内部目录不再写死本机默认路径（Grok Bot 10-18 15:02 安排的清理）：只认 $MARKJIN_INTERNAL_DIR，未设置时用仓库根的同级相对目录。
守卫测试不重建任何具体旧路径，只用通用形状断言跟踪文件里没有本机绝对路径（r15 MEDIUM）。"""
import os, re, subprocess, unittest
from pathlib import Path
from unittest import mock
import helpers  # noqa: F401
from markjin import internal

REPO = Path(__file__).resolve().parents[1]
# 本机绝对路径的通用形状（不针对任何具体目录）：根目录为 LOCAL_ROOTS 之一的绝对路径，或指向它们的 file: URI。
# 前一个字符不能是字母、数字、点、冒号、斜杠等——网址里的同名路径段（见 test_pattern_shape）不算。
LOCAL_ROOTS = ("workspace", "home")
LOCAL_ABS = re.compile(r"(?<![A-Za-z0-9_.:/\\-])/(?:%s)/|file:/+(?:%s)/" % (("|".join(LOCAL_ROOTS),) * 2))
# 已定不改的历史文件（按 Grok Bot 10-18 决定：以前写进公开仓库的本机路径不改），逐个列出，不用通配：
LOCAL_PATH_EXCEPTIONS = frozenset({
    # 已发布日报（台账待登记文件位置）
    "digest/2026-10-15.md", "digest/2026-10-16.md", "digest/2026-10-17.md", "digest/2026-10-18.md",
    # 审批记录与审查记录（只追加，不改写）
    "docs/approvals.md", "review/2026-10-16.md",
    # raw/ 已入库历史存档（只追加、永不修改；新增 raw/ 文件另由 check-public E-PUBLIC-LOCAL-PATH 拦截）
    "raw/2026-10-10/x-queries.md", "raw/2026-10-10/x/PROVENANCE.md",
    "raw/2026-10-11/fulltext/MANIFEST.sha256", "raw/2026-10-11/fulltext/ORIGINALS.sha256",
    "raw/2026-10-11/fulltext/PROVENANCE.md", "raw/2026-10-11/round2/x/query-log.jsonl",
    "raw/2026-10-11/x-queries.md", "raw/2026-10-11/x/PROVENANCE.md", "raw/2026-10-11/x/query-log.jsonl",
    "raw/2026-10-12/dedup-evidence.json", "raw/2026-10-12/query-log.jsonl",
    # 守卫本身：check-public 的规则说明，以及它的测试样例（检查对象，不是配置）
    "scripts/check-public.py", "tests/test_retract.py",
})


class InternalDir(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"MARKJIN_INTERNAL_DIR": "some/where"}):
            self.assertEqual(internal.internal_dir(), Path("some/where"))

    def test_unset_or_empty_uses_repo_sibling(self):
        for env in ({}, {"MARKJIN_INTERNAL_DIR": ""}, {"MARKJIN_INTERNAL_DIR": "  "}):
            with mock.patch.dict(os.environ, env):
                if not env:
                    os.environ.pop("MARKJIN_INTERNAL_DIR", None)
                self.assertEqual(internal.internal_dir(), REPO.parent / "markjin-internal")

    def test_missing_dir_fails_closed(self):
        with mock.patch.dict(os.environ, {"MARKJIN_INTERNAL_DIR": str(REPO / "no-such-internal-dir")}):
            self.assertIsNone(internal.load_internal_terms())

    def test_no_local_absolute_paths_in_tracked_files(self):
        """跟踪文件里没有根目录为 LOCAL_ROOTS 的本机绝对路径；只豁免上面逐个列出的历史文件。"""
        files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout.split(b"\0")
        hits = []
        for f in filter(None, (x.decode("utf-8") for x in files)):
            p = REPO / f
            if f in LOCAL_PATH_EXCEPTIONS or not p.is_file():
                continue
            if LOCAL_ABS.search(p.read_bytes().decode("utf-8", "replace")):
                hits.append(f)
        self.assertEqual(hits, [], "local absolute paths in tracked files")

    def test_exceptions_are_explicit_files(self):
        for f in LOCAL_PATH_EXCEPTIONS:
            self.assertNotRegex(f, r"[*?\[]")                      # 不用通配
            self.assertTrue((REPO / f).is_file(), f)                  # 每个例外都是实际存在的单个文件

    def test_pattern_shape(self):
        for root in LOCAL_ROOTS:
            self.assertRegex(f"see /{root}/x/y", LOCAL_ABS)
            self.assertRegex(f"'/{root}/x'", LOCAL_ABS)
            self.assertRegex(f"file:///{root}/x", LOCAL_ABS)
            self.assertNotRegex(f"https://sam.gov/{root}/x", LOCAL_ABS)     # 网址路径段不算
            self.assertNotRegex(f"/{root}", LOCAL_ABS)
        src = (REPO / "scripts/markjin/internal.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, LOCAL_ABS)                           # 内部目录没有绝对默认值

if __name__ == "__main__":
    unittest.main()
