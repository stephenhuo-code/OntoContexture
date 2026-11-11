#!/usr/bin/env bash
# 云端脚本单元测试的断言与桩函数（030）。由 run.sh 在每个测试函数的子 shell 中加载。
# shellcheck disable=SC2317

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
export REPO_ROOT

fail() { printf '断言失败：%s\n' "$*" >&2; exit 1; }

assert_eq() {  # assert_eq <期望> <实际> [说明]
  [[ $1 == "$2" ]] || fail "${3:-值不相等}：期望 [$1]，实际 [$2]"
}

assert_contains() {  # assert_contains <文本> <子串> [说明]
  [[ $1 == *"$2"* ]] || fail "${3:-缺少内容}：未找到 [$2]，文本为 [$1]"
}

assert_not_contains() {  # assert_not_contains <文本> <子串> [说明]
  [[ $1 != *"$2"* ]] || fail "${3:-出现不应出现的内容}：[$2]"
}

# assert_status <期望退出码> <命令...>：在子 shell 中运行命令，输出存入 $OUTPUT
assert_status() {
  local expected=$1; shift
  local status=0
  OUTPUT=$("$@" 2>&1) || status=$?
  [[ $status == "$expected" ]] || fail "退出码期望 $expected，实际 $status；输出：$OUTPUT"
}

# 记录桩命令的调用：桩函数把参数追加到 $STUB_LOG，供断言检查
stub_log_init() { STUB_LOG=$(mktemp); export STUB_LOG; }
stub_record() { printf '%s\n' "$*" >> "$STUB_LOG"; }
stub_calls() { cat "$STUB_LOG"; }

# 临时目录：测试结束由子 shell 退出后清理
tmpdir() { local d; d=$(mktemp -d); printf '%s' "$d"; }
