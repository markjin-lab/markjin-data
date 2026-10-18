"""内部目录不再写死本机默认路径（Grok Bot 10-18 15:02 安排的清理）：只认 $MARKJIN_INTERNAL_DIR，未设置时用仓库根的同级相对目录。"""
import os, subprocess, unittest
from pathlib import Path
from unittest import mock
import helpers  # noqa: F401
from markjin import internal

REPO = Path(__file__).resolve().parents[1]
LOCAL_DEFAULT = "/" + "workspace/" + "markjin-internal"     # 拼出来，避免本测试文件自己命中


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

    def test_no_local_default_path_in_public_files(self):
        """全仓（raw/ 存档除外：只追加、不改写）不再出现本机默认路径。"""
        out = subprocess.run(["git", "grep", "-l", "-F", LOCAL_DEFAULT, "--", ".", ":!raw"], cwd=REPO,
                             capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "", out.stdout)
        src = (REPO / "scripts/markjin/internal.py").read_text(encoding="utf-8")
        self.assertNotIn("/workspace", src)


if __name__ == "__main__":
    unittest.main()
