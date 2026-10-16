#!/usr/bin/env python3
"""写一条 Codex 审查记录到 approvals/codex/（只新建，不覆盖）。英文稿 draft_id 须以 -en 结尾（E-APPROVALS-EN-DRAFT-ID）。

用法：scripts/write-codex-record.py --sha <稿件sha256> --draft-id <draft_id> --session <uuid> --verdict APPROVED|REJECTED \\
        --log-path <相对路径> --reviewed-at <ISO 时间> (--draft <稿件路径> | --lang zh|en) [--for-date YYYY-MM-DD] [--repo .]
不提交、不推送；写完后照常跑 check-public / check-internal / audit-approvals 再推送。"""
import argparse, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markjin import approvals as A  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--sha", required=True); ap.add_argument("--draft-id", required=True)
ap.add_argument("--session", required=True); ap.add_argument("--verdict", required=True)
ap.add_argument("--log-path", required=True); ap.add_argument("--reviewed-at", required=True)
ap.add_argument("--draft"); ap.add_argument("--lang", choices=A.CODEX_LANGS)
ap.add_argument("--for-date"); ap.add_argument("--repo")
a = ap.parse_args()
repo = a.repo or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
rec = {"content_sha256": a.sha, "draft_id": a.draft_id, "codex_session": a.session, "verdict": a.verdict,
       "log_path": a.log_path, "reviewed_at": a.reviewed_at}
try:
    p = A.write_codex_record(repo, rec, draft_path=a.draft, lang=a.lang, for_date=a.for_date)
except A.ApprovalsError as e:
    print(f"FAIL {e.code}"); sys.exit(1)
print(f"OK {Path(p).relative_to(repo)}")
