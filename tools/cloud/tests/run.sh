#!/usr/bin/env bash
# 云端脚本单元测试运行器（030 T001）：纯 bash，无额外依赖。
# 用法：tools/cloud/tests/run.sh [测试文件...]（默认全部 test_*.sh）
#   CTX_KCOV=1：在 kcov 下运行，合并结果输出到 coverage/bash/cobertura.xml（宪法 I 覆盖率门禁，R17a）
set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)

run_file() {  # 运行单个测试文件中的全部 test_ 函数
  local file=$1 failed=0 name output
  # shellcheck disable=SC1090
  mapfile -t names < <(bash -c "source '$HERE/lib.sh'; source '$file'; declare -F" | awk '$3 ~ /^test_/ {print $3}')
  for name in "${names[@]}"; do
    if output=$( (set -euo pipefail; source "$HERE/lib.sh"; source "$file"; "$name") 2>&1 ); then
      printf '  ✔ %s %s\n' "$(basename "$file")" "$name"
    else
      printf '  ✘ %s %s\n%s\n' "$(basename "$file")" "$name" "$(sed 's/^/      /' <<< "$output")"
      failed=1
    fi
  done
  return $failed
}

if [[ ${1:-} == --single ]]; then run_file "$2"; exit $?; fi

files=("$@")
[[ ${#files[@]} -gt 0 ]] || mapfile -t files < <(find "$HERE" -maxdepth 1 -name 'test_*.sh' | sort)

status=0
if [[ -n ${CTX_KCOV:-} ]]; then
  command -v kcov >/dev/null || { echo "CTX_KCOV 需要 kcov（在工具箱镜像或 CI 中运行）"; exit 2; }
  out="$ROOT/coverage/bash"; rm -rf "$out"; mkdir -p "$out"
  for file in "${files[@]}"; do
    kcov --include-path="$ROOT/tools/cloud" --exclude-path="$ROOT/tools/cloud/tests" \
      "$out/$(basename "$file" .sh)" bash "$HERE/run.sh" --single "$file" || status=1
  done
  kcov --merge "$out/merged" "$out"/test_* >/dev/null
  cp "$out/merged/kcov-merged/cobertura.xml" "$out/cobertura.xml"
  echo "bash 覆盖率报告：coverage/bash/cobertura.xml"
else
  for file in "${files[@]}"; do run_file "$file" || status=1; done
fi
[[ $status == 0 ]] && echo "全部通过" || echo "有测试失败"
exit $status
