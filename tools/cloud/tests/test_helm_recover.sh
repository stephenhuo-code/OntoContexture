#!/usr/bin/env bash
# T042 实测：DOKS API 连接中断（EOF）使 Helm release 停在 pending-upgrade，此后每次部署都报 “another operation is in progress”。
# 部署前把停在 pending-* 的 release 回滚到最近一次成功的版本；没有成功版本（pending-install）的只报告、不删除
source "$REPO_ROOT/tools/cloud/deploy.sh"
stub_log_init
PENDING='[]'
ctx_helm() {
  case "$*" in
    *"list -A --pending -o json"*) echo "$PENDING" ;;
    *"history cnpg -o json"*) echo '[{"revision":5,"status":"superseded"},{"revision":6,"status":"deployed"},{"revision":7,"status":"pending-upgrade"}]' ;;
    *"history fresh -o json"*) echo '[{"revision":1,"status":"pending-install"}]' ;;
    *) stub_record "helm $*" ;;
  esac
}

test_no_pending_release_does_nothing() {
  ctx_recover_pending_releases >/dev/null
  assert_eq "" "$(stub_calls)"
}

test_pending_upgrade_is_rolled_back_to_last_deployed_revision() {
  PENDING='[{"name":"cnpg","namespace":"cnpg-system","status":"pending-upgrade"}]'
  local out; out=$(ctx_recover_pending_releases)
  assert_contains "$(stub_calls)" "helm -n cnpg-system rollback cnpg 6"
  assert_contains "$out" "cnpg"
}

test_pending_install_without_deployed_revision_is_only_reported() {
  PENDING='[{"name":"fresh","namespace":"contexture","status":"pending-install"}]'
  local out; out=$(ctx_recover_pending_releases)
  assert_not_contains "$(stub_calls)" "rollback"
  assert_not_contains "$(stub_calls)" "uninstall"
  assert_contains "$out" "fresh"
}

test_helmfile_sync_limits_concurrency() {
  assert_contains "$(sed -n '/ctx_helmfile -l/p' "$REPO_ROOT/tools/cloud/deploy.sh")" "--concurrency"
}
