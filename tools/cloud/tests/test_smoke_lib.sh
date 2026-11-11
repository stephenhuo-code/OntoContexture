#!/usr/bin/env bash
# T049：冒烟测试的临时 Pod 在设置 CTX_NODE_SELECTOR 时固定到弹性池；未设置时行为不变（FR-027、R7）
stub_log_init
kubectl() {
  stub_record "kubectl $*"
  case "$*" in *"jsonpath={.status.phase}"*) echo Succeeded ;; esac
}
source "$REPO_ROOT/deploy/components/smoke-lib.sh"

test_without_node_selector_run_is_unchanged() {
  unset CTX_NODE_SELECTOR
  incluster busybox:1.37 true >/dev/null
  assert_not_contains "$(stub_calls)" "--overrides"
}

test_with_node_selector_run_is_pinned() {
  CTX_NODE_SELECTOR=example.com/pool=elastic incluster busybox:1.37 true >/dev/null
  assert_contains "$(stub_calls)" '--overrides={"spec":{"nodeSelector":{"example.com/pool":"elastic"}}}'
}
