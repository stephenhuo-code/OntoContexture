sleep 10; kill -TERM -- "-$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true
grep -q "工具箱" "$TMPDIR_T/int.log" || true#!/usr/bin/env bash
# T065 云端验证：失败的测试使命令非 0 退出且不留残留 Pod；中断后 Pod 被删除（US3 场景 1、2、4；FR-016）
source "$(dirname "$0")/lib.sh"
TMPDIR_T=$(mktemp -d); trap 'rm -rf "$TMPDIR_T"; rm -f "$ROOT/tools/tests/test_zz_cloud_must_fail.py"' EXIT
printf 'def test_must_fail() -> None:\n    assert False, "030 故意失败"\n' > "$ROOT/tools/tests/test_zz_cloud_must_fail.py"
status=0; ( cd "$ROOT" && make cloud-test ) > "$TMPDIR_T/out.log" 2>&1 || status=$?
[[ $status != 0 ]] && pass "失败的测试使 cloud-test 非 0 退出（$status）" || fail "cloud-test 应失败"
grep -q "030 故意失败" "$TMPDIR_T/out.log" && pass "终端显示失败详情" || fail "未显示失败详情"
gone() {  # 删除不等待 Pod 退出，最多等 60 秒（T088 实测）
  local i
  for i in $(seq 1 12); do [[ -z $(K -n contexture-ci get pod contexture-toolbox --ignore-not-found -o name) ]] && return 0; sleep 5; done
  return 1
}
gone && pass "无残留工具箱 Pod" || fail "残留工具箱 Pod"
rm -f "$ROOT/tools/tests/test_zz_cloud_must_fail.py"
# 非交互 shell 中后台进程忽略 SIGINT（T075 实测）：以 setsid 起独立进程组，向整个进程组发 TERM
( cd "$ROOT" && exec setsid make cloud-lint ) > "$TMPDIR_T/int.log" 2>&1 & pid=$!
for i in $(seq 1 60); do K -n contexture-ci get pod contexture-toolbox >/dev/null 2>&1 && break; sleep 5; done
sleep 10; kill -TERM -- "-$pid" 2>/dev/null || true
int_status=0; wait "$pid" 2>/dev/null || int_status=$?
[[ $int_status != 0 ]] && pass "中断后命令非 0 退出（$int_status），未跑完" || fail "cloud-lint 未被中断"
gone && pass "中断后工具箱 Pod 已删除" || fail "中断后仍有工具箱 Pod"
finish
