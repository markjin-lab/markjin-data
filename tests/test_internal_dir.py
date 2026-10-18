"""内部目录不再写死本机默认路径（Grok Bot 10-18 15:02 安排的清理）：只认 $MARKJIN_INTERNAL_DIR，未设置时用仓库根的同级相对目录。
守卫测试不重建任何具体旧路径，只用通用形状断言跟踪文件里没有本机绝对路径（r15 MEDIUM）。"""
import hashlib, os, re, subprocess, unittest
from collections import Counter
from pathlib import Path
from unittest import mock
import helpers  # noqa: F401
from markjin import internal

REPO = Path(__file__).resolve().parents[1]
# 本机绝对路径的通用形状（不针对任何具体目录）：根目录为 LOCAL_ROOTS 之一的绝对路径，或指向它们的 file: URI。
# 裸路径：前一个字符不能是字母、数字、点、冒号、斜杠等——网址里的同名路径段（见 test_pattern_shape）不算。
# file: URI：判法同 scripts/check-public.py 的 FILE_URI_RE——scheme 不分大小写，可带 //主机（含 localhost），
# 即 file:/、file:///、file://localhost/、FILE:/// 都算（r16 MEDIUM）。
LOCAL_ROOTS = ("workspace", "home")
LOCAL_ABS = re.compile(
    r"(?<![A-Za-z0-9_.:/\\-])/(?:%s)/"
    r"|(?i:(?<![A-Za-z0-9+.\-])file:(?://[^/\s\"'<>]*)?/+(?:%s)/)" % (("|".join(LOCAL_ROOTS),) * 2))
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
})
# 守卫本身的规则说明和测试样例：不整份豁免，只豁免下面逐条列出的现有行（r16 MEDIUM）。
# 键是行内容去掉首尾空白后的 sha256 前 16 位，值是该行允许出现的次数；行改了、或新增任何命中的行，都会被报出来。
LOCAL_PATH_LINE_EXCEPTIONS = {
    "scripts/check-public.py": {
        "14b9a51e17d92cb4": 1,  # 模块说明：规则 4) 新增 raw/ 文件不得含本机绝对路径
        "333de3c29a3423ea": 1,  # 注释：2026-10-12 合规撤回的规则来由
    },
    "tests/test_retract.py": {
        "5bd65b48608301f9": 1,  # test_home_path_flagged 样例
        "a7d12c2268342b50": 1,  # test_file_uri_flagged 样例
        "00c01c8c125fa416": 1,  # test_escaped_host_url_and_fragment_not_flagged 样例
        "e91f26dd5766065e": 1,  # test_quoted_workspace_path_flagged 样例
        "e75670c667012bd6": 1,  # test_file_uri_variants_flagged 样例（第 1 行）
        "a953a34ce116f107": 1,  # test_file_uri_variants_flagged 样例（第 2 行）
        "2ac2d11c8ad3fa24": 1,  # test_file_uri_variants_flagged 样例（第 3 行）
        "b1e93011243fa829": 1,  # test_file_uri_variants_flagged 样例（第 4 行）
        "8acda77aa959f891": 1,  # test_json_decoded_bare_path_flagged 样例（第 1 行）
        "57001971df4ba2a2": 1,  # test_json_decoded_bare_path_flagged 样例（第 2 行）
        "97c279433506fbb1": 1,  # test_http_query_and_fragment_not_flagged 样例（第 1 行）
        "0edf7d2398dcc320": 1,  # test_http_query_and_fragment_not_flagged 样例（第 2 行）
    },
}


def _line_key(line):
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()[:16]


def local_path_hits(path, text):
    """返回 text 里命中 LOCAL_ABS、且不在 path 的逐行例外里的行号列表（整份例外的历史文件不在这里处理）。"""
    allowed = Counter(LOCAL_PATH_LINE_EXCEPTIONS.get(path, {}))
    hits = []
    for no, line in enumerate(text.split("\n"), 1):
        if not LOCAL_ABS.search(line):
            continue
        key = _line_key(line)
        if allowed[key] > 0:
            allowed[key] -= 1
        else:
            hits.append(no)
    return hits


def _tracked_text(path):
    return (REPO / path).read_bytes().decode("utf-8", "replace")


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
        """跟踪文件里没有根目录为 LOCAL_ROOTS 的本机绝对路径；只豁免上面逐个列出的历史文件，和逐条列出的守卫说明/样例行。"""
        files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout.split(b"\0")
        hits = []
        for f in filter(None, (x.decode("utf-8") for x in files)):
            p = REPO / f
            if f in LOCAL_PATH_EXCEPTIONS or not p.is_file():
                continue
            lines = local_path_hits(f, p.read_bytes().decode("utf-8", "replace"))
            if lines:
                hits.append((f, lines))
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

    def test_file_uri_localhost_and_uppercase(self):
        """file: URI 判法同 check-public：file://localhost/ 和大写 FILE:/// 都算本机路径。"""
        for root in LOCAL_ROOTS:
            for uri in (f"file://localhost/{root}/x", f"FILE:///{root}/x", f"File://LocalHost/{root}/x",
                        f"FILE:/{root}/x", f"FILE://LOCALHOST/{root.upper()}/x"):
                with self.subTest(uri=uri):
                    self.assertRegex(f'{{"p": "{uri}"}}', LOCAL_ABS)
            self.assertNotRegex(f"file:///etc/{root}x", LOCAL_ABS)            # 其他根目录不算
            self.assertNotRegex(f"profile:///{root}/x", LOCAL_ABS)            # 别的 scheme 结尾含 file 不算

    def test_line_exceptions_are_exact(self):
        """逐行例外只用于两个守卫文件，不与整份例外重叠，且每一条都恰好对应现有的一行（没有多余条目）。"""
        self.assertEqual(set(LOCAL_PATH_LINE_EXCEPTIONS), {"scripts/check-public.py", "tests/test_retract.py"})
        self.assertFalse(set(LOCAL_PATH_LINE_EXCEPTIONS) & LOCAL_PATH_EXCEPTIONS)
        for f, allowed in LOCAL_PATH_LINE_EXCEPTIONS.items():
            found = Counter(_line_key(l) for l in _tracked_text(f).split("\n") if LOCAL_ABS.search(l))
            self.assertEqual(dict(found), allowed, f)

    def test_new_local_path_in_guard_files_is_caught(self):
        """在两个守卫文件里模拟新增一行本机路径（通用示例路径），检查会报出来；原样内容不报。"""
        for f in LOCAL_PATH_LINE_EXCEPTIONS:
            text = _tracked_text(f)
            self.assertEqual(local_path_hits(f, text), [], f)
            n = len(text.split("\n"))
            for root in LOCAL_ROOTS:
                for added in (f"# see /{root}/example/new.txt", f'x = "file://localhost/{root}/example"',
                              f'x = "FILE:///{root}/example"'):
                    with self.subTest(f=f, added=added):
                        self.assertEqual(local_path_hits(f, text + added + "\n"), [n])            # 文件末尾新增
                        self.assertEqual(local_path_hits(f, added + "\n" + text), [1])            # 文件开头新增
            # 把已豁免的某一行再复制一份，也会被报出来（豁免按次数，不按模式）
            dup = next(l for l in text.split("\n") if LOCAL_ABS.search(l))
            self.assertEqual(len(local_path_hits(f, text + dup + "\n")), 1, f)

if __name__ == "__main__":
    unittest.main()
