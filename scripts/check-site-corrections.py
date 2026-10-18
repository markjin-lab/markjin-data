#!/usr/bin/env python3
"""站点 PR 的更正规则检查（Grok Bot 2026-10-18）。不改工作树；--pr 会 fetch 并更新本地 Git 对象和引用。

用法：
  scripts/check-site-corrections.py --site-repo DIR --pr N          # fetch origin main 与 PR head，检查 main...PR
  scripts/check-site-corrections.py --site-repo DIR --head REF [--base REF]   # 本地范围（默认 base origin/main）

检查 merge-base(base, head)..head 中改动的 content/posts/<section>/<name>[.en].md 与 content/cards/<name>[.en].md：
“已发布”按站点部署所用版本的 Hugo 实际构建判定（需本机 hugo，版本须与站点 .github/workflows/hugo.yml 一致）。
改已发布页面必须是更正（corrects + corrected_at），更正日期合法，更正区须有与 corrected_at 对应的新格式条目或过渡期旧格式标题，且本次日期的更正次数比 base 多（纯格式迁移例外）；删除已发布页面判失败。
规则与错误码见 docs/approvals.md「站点 PR 页面检查」。输出 JSON；退出码 0 = 通过，1 = 有页面不合规或输入无效（含参数错误）。"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import sitecheck as S  # noqa: E402
from markjin.deps import DependencyError  # noqa: E402

class JsonParser(argparse.ArgumentParser):
    """参数错误也输出 JSON、退出码 1（r1 LOW 7）。"""
    def error(self, message):
        print(json.dumps({"ok": False, "codes": ["E-SITE-INPUT"], "detail": message}, ensure_ascii=False))
        self.exit(1)


ap = JsonParser()
ap.add_argument("--site-repo", required=True, help="站点仓库本地克隆")
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--pr", type=int, help="站点 PR 编号（从 origin fetch refs/pull/N/head）")
g.add_argument("--head", help="要检查的提交或引用")
ap.add_argument("--base", help="基线引用（默认 origin/main；与 --pr 同用时忽略）")
a = ap.parse_args()
try:
    if a.pr is not None:
        base, head = S.fetch_pr(a.site_repo, a.pr)
    else:
        base, head = a.base or "origin/main", a.head
    out = S.check_range(a.site_repo, base, head)
except OSError as e:
    print(json.dumps({"ok": False, "codes": ["E-SITE-INPUT"], "detail": f"E-SITE-INPUT: 临时目录或构建 I/O 不可用：{e}"},
                     ensure_ascii=False))
    sys.exit(1)
except (S.SiteInputError, DependencyError) as e:
    print(json.dumps({"ok": False, "codes": [str(e).split(":")[0]], "detail": str(e)}, ensure_ascii=False))
    sys.exit(1)
if a.pr is not None:
    out["pr"] = a.pr
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if out["ok"] else 1)
