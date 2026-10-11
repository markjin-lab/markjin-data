#!/usr/bin/env bash
# 校验 raw/ 存档：1) 每天 MANIFEST.sha256 与文件一致；2) 自基线提交起，已提交 raw 文件未被修改/删除（MANIFEST 只能追加行）。
# 用法：scripts/verify-raw.sh [BASE_COMMIT]   默认基线 = 引入本脚本的提交
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
fail=0
# 合规撤回（2026-10-12 起）：raw/<日期>/RETRACTIONS.md 表格行 "| raw/<路径> | url | sha256 | ... |" 登记的文件视为已撤回。
# 只有路径与 sha256 都匹配时才生效：存在性校验跳过该 MANIFEST 行；历史校验只允许删除登记过的文件（基线内容 sha256 须一致）。
retracted() {  # 输出 "sha256  repo相对路径"
  local r=raw/$1/RETRACTIONS.md
  [ -f "$r" ] || return 0
  awk -F'|' '$2 ~ /^ *raw\// { p=$2; h=$4; gsub(/ /,"",p); gsub(/ /,"",h); if (h ~ /^[0-9a-f]{64}$/) print h "  " p }' "$r"
}
is_retracted() {  # $1=repo 相对路径 $2=sha256
  local day=${1#raw/}; day=${day%%/*}
  retracted "$day" | grep -qxF "$2  $1"
}
for m in raw/*/MANIFEST.sha256; do
  [ -e "$m" ] || continue
  d=$(dirname "$m")
  day=${d#raw/}
  RET=$(retracted "$day"); export RET
  # 去掉已撤回（路径 + sha256 匹配 RETRACTIONS.md）的行后再校验
  if (cd "$d" && awk -v day="$day" '
        BEGIN { n = split(ENVIRON["RET"], a, "\n"); for (i = 1; i <= n; i++) if (a[i] != "") skip[a[i]] = 1 }
        { h = $1; p = substr($0, 67); sub(/^\.\//, "", p)
          if (p == "RETRACTIONS.md") { lastr = $0; next }   # RETRACTIONS.md 追加后重新登记：只校验最后一条登记
          if (!(((h "  raw/" day "/" p)) in skip)) print }
        END { if (lastr != "") print lastr }
      ' MANIFEST.sha256 | sha256sum --quiet -c -); then echo "OK   $m"; else echo "FAIL $m"; fail=1; fi
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
    M) if [[ "$path" == */RETRACTIONS.md ]]; then
         # RETRACTIONS.md 只能追加：基线内容必须是新内容的字节前缀
         n=$(git show "$base:$path" | wc -c)
         if [ "$(head -c "$n" "$path" | sha256sum)" != "$(git show "$base:$path" | sha256sum)" ]; then
           echo "FAIL RETRACTIONS.md 非追加式修改: $path"; fail=1; fi
       elif [[ "$path" == */MANIFEST.sha256 ]]; then
         # 只追加：基线中的每一行都必须仍存在
         if ! diff <(git show "$base:$path" | sort) <(git show "$base:$path" | sort | comm -12 - <(sort "$path")) >/dev/null; then
           echo "FAIL MANIFEST 删改了旧行: $path"; fail=1; fi
       else echo "FAIL 已提交 raw 文件被修改: $path"; fail=1; fi ;;
    D) if [[ "$path" == */RETRACTIONS.md ]]; then echo "FAIL RETRACTIONS.md 被删除: $path"; fail=1
       elif is_retracted "$path" "$(git show "$base:$path" | sha256sum | cut -d' ' -f1)"; then
         echo "RETRACTED $path（见 RETRACTIONS.md）"
       else echo "FAIL 已提交 raw 文件被删除/改名($st): $path"; fail=1; fi ;;
    *) echo "FAIL 已提交 raw 文件被删除/改名($st): $path"; fail=1 ;;
  esac
done < <(git diff --name-status --no-renames "$base" -- raw ":(exclude)raw/README.md")
[ $fail -eq 0 ] && echo "verify-raw: 全部通过（基线 ${base:0:7}）" || { echo "verify-raw: 失败"; exit 1; }
