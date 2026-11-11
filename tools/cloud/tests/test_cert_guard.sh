#!/usr/bin/env bash
# T052 实测：首次签发时 cert-manager 的集群内自检先于公网负载均衡器健康检查通过，Let's Encrypt 从公网取验证文件失败，
# 证书进入约 1 小时的失败退避；而 AI 网关等依赖证书就绪，Helm 等待会先超时。部署期间的后台守护：发现签发失败即重建证书对象。
source "$REPO_ROOT/tools/cloud/deploy.sh"
stub_log_init
CTX_CLOUD_NAMESPACE=contexture
READY=False FAILED=""
CTX_CERT_GUARD_INTERVAL=0 CTX_CERT_GUARD_SETTLE=0 CTX_CERT_GUARD_ROUNDS=3
ctx_kubectl() {
  case "$*" in
    *"jsonpath={.status.conditions"*) echo "$READY" ;;
    *"jsonpath={.status.lastFailureTime}"*) echo "$FAILED" ;;
    *"get certificate contexture -o json"*) echo '{"metadata":{"name":"contexture","uid":"u","resourceVersion":"1"},"spec":{},"status":{"x":1}}' ;;
    *) stub_record "kubectl $*"; [[ $* == *"create -f -"* ]] && cat >> "$STUB_LOG"; return 0 ;;
  esac
}

test_guard_does_nothing_when_certificate_becomes_ready() {
  READY=True
  ctx_cert_guard >/dev/null
  assert_not_contains "$(stub_calls)" "delete certificate"
}

test_guard_recreates_certificate_after_failed_issuance_without_status() {
  FAILED=2026-11-11T09:00:00Z
  ctx_cert_guard >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "kubectl -n contexture delete certificate contexture"
  assert_contains "$calls" "kubectl -n contexture create -f -"
  assert_not_contains "$calls" '"status"'
  assert_not_contains "$calls" '"uid"'
}

test_guard_gives_up_after_limited_rounds() {
  FAILED=2026-11-11T09:00:00Z
  ctx_cert_guard >/dev/null
  assert_eq 3 "$(stub_calls | grep -c 'delete certificate')" "最多重建 CTX_CERT_GUARD_ROUNDS 次"
}
