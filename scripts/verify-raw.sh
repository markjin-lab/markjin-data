#!/usr/bin/env bash
# 校验 raw/ 存档：1) 每天 MANIFEST.sha256 与文件一致；2) 自基线提交起，已提交 raw 文件未被修改/删除（MANIFEST 只能追加行）。
# 用法：scripts/verify-raw.sh [BASE_COMMIT]   默认基线 = 引入本脚本的提交
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
fail=0
for m in raw/*/MANIFEST.sha256; do
  [ -e "$m" ] || continue
  d=$(dirname "$m")
  if (cd "$d" && sha256sum --quiet -c MANIFEST.sha256); then echo "OK   $m"; else echo "FAIL $m"; fail=1; fi
  # 目录内每个文件（除 MANIFEST 本身）都必须登记
  while IFS= read -r f; do
    grep -qF "  ./$f" "$m" || grep -qF "  $f" "$m" || { echo "FAIL 未登记: $d/$f"; fail=1; }
  done < <(cd "$d" && find . -type f ! -name MANIFEST.sha256 | sed 's|^\./||' | sort)
done
base=${1:-$(git log --diff-filter=A --format=%H -- scripts/verify-raw.sh | tail -1)}
[ -n "$base" ] || base=HEAD
while IFS=$'\t' read -r st path rest; do
  [ -n "${st:-}" ] || continue
  case "$st" in
    A) ;;
    M) if [[ "$path" == */MANIFEST.sha256 ]]; then
         # 只追加：基线中的每一行都必须仍存在
         if ! diff <(git show "$base:$path" | sort) <(git show "$base:$path" | sort | comm -12 - <(sort "$path")) >/dev/null; then
           echo "FAIL MANIFEST 删改了旧行: $path"; fail=1; fi
       else echo "FAIL 已提交 raw 文件被修改: $path"; fail=1; fi ;;
    *) echo "FAIL 已提交 raw 文件被删除/改名($st): $path"; fail=1 ;;
  esac
done < <(git diff --name-status --no-renames "$base" -- raw ":(exclude)raw/README.md")
[ $fail -eq 0 ] && echo "verify-raw: 全部通过（基线 ${base:0:7}）" || { echo "verify-raw: 失败"; exit 1; }
