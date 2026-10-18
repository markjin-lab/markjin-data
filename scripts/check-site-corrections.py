#!/usr/bin/env python3
"""站点 PR 的更正规则检查（Grok Bot 2026-10-18）。只读，不写文件。

用法：
  scripts/check-site-corrections.py --site-repo DIR --pr N          # fetch origin main 与 PR head，检查 main...PR
  scripts/check-site-corrections.py --site-repo DIR --head REF [--base REF]   # 本地范围（默认 base origin/main）

检查 merge-base(base, head)..head 中改动的 content/posts/<section>/<name>[.en].md 与 content/cards/<name>[.en].md：
改已发布页面必须是更正（corrects + corrected_at），更正日期合法且出现在标题行可见文字里；删除已发布页面判失败。
规则与错误码见 docs/approvals.md「站点 PR 页面检查」。输出 JSON；退出码 0 = 通过，1 = 有页面不合规或输入无效。"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import sitecheck as S  # noqa: E402
from markjin.deps import DependencyError  # noqa: E402

ap = argparse.ArgumentParser()
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
except (S.SiteInputError, DependencyError) as e:
    print(json.dumps({"ok": False, "codes": [str(e).split(":")[0]], "detail": str(e)}, ensure_ascii=False))
    sys.exit(1)
if a.pr is not None:
    out["pr"] = a.pr
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(0 if out["ok"] else 1)
