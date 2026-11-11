#!/usr/bin/env bash
# T028：环境状态记录 contexture-cloud-state（data-model.md 第 2 节；FR-036）
source "$REPO_ROOT/tools/cloud/common.sh"
source "$REPO_ROOT/tools/cloud/lib/state.sh"
CTX_CLOUD_NAMESPACE=contexture
STORE=$(mktemp); echo '{}' > "$STORE"
ctx_kubectl() {  # 桩：用 JSON 文件模拟 ConfigMap 的 data
  case "$*" in
    *"get configmap contexture-cloud-state -o json"*) jq '{data: .}' "$STORE" ;;
    *"get configmap contexture-cloud-state"*) [[ $(cat "$STORE") != '{}' ]] ;;
    *"create configmap contexture-cloud-state"*) echo '{"lifecycle.state":"running"}' > "$STORE" ;;
    *"patch configmap contexture-cloud-state"*)
      local patch; patch=$(sed -E "s/.* -p (.*)$/\1/" <<< "$*")
      jq --argjson p "$patch" '. + $p.data' "$STORE" > "$STORE.n" && mv "$STORE.n" "$STORE" ;;
    *) return 0 ;;
  esac
}

test_set_and_get_round_trip() {
  ctx_state_set stableVersion.bff=registry.example.com/ctx/bff:git-abc stableVersion.dirty=false
  assert_eq registry.example.com/ctx/bff:git-abc "$(ctx_state_get stableVersion.bff)"
  assert_eq false "$(ctx_state_get stableVersion.dirty)"
}

test_set_merges_without_dropping_other_keys() {
  ctx_state_set devMode.active=true
  ctx_state_set lifecycle.state=stopped
  assert_eq true "$(ctx_state_get devMode.active)"
  assert_eq stopped "$(ctx_state_get lifecycle.state)"
}

test_missing_key_returns_empty() {
  assert_eq "" "$(ctx_state_get nothing.here)"
}

test_set_records_timestamp_for_lifecycle_and_stable_version() {
  ctx_state_set lifecycle.state=running
  [[ $(ctx_state_get lifecycle.updatedAt) =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T ]] || fail "缺少 lifecycle.updatedAt"
  ctx_state_set stableVersion.bff=x
  [[ -n $(ctx_state_get stableVersion.deployedAt) ]] || fail "缺少 stableVersion.deployedAt"
}

test_derive_running() {
  assert_eq 运行中 "$(ctx_derive_state running 10 10 0)"
}

test_derive_stopped() {
  assert_eq 已停止 "$(ctx_derive_state stopped 0 0 10)"
}

test_derive_partial_when_some_not_ready_or_in_transition() {
  assert_eq 部分运行 "$(ctx_derive_state running 10 7 0)"
  assert_eq 部分运行 "$(ctx_derive_state stopping 4 4 6)"
  assert_eq 部分运行 "$(ctx_derive_state stopped 1 1 9)"
  assert_eq 部分运行 "$(ctx_derive_state starting 10 10 0)"
}
