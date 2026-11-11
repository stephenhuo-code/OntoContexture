#!/usr/bin/env bash
# T009：云端命令固定使用 .env.cloud 的 kubeconfig / 上下文 / namespace（FR-001a、FR-002）
source "$REPO_ROOT/tools/cloud/common.sh"
stub_log_init
kubectl() { stub_record "kubectl $*"; }
helm() { stub_record "helm $*"; }
helmfile() { stub_record "helmfile $* KUBECONFIG=${KUBECONFIG:-}"; }
CTX_CLOUD_KUBECONFIG=/k/doks.yaml CTX_CLOUD_CONTEXT=ctx-cloud CTX_CLOUD_NAMESPACE=contexture

test_kubectl_is_pinned() {
  ctx_kubectl get pods
  assert_contains "$(stub_calls)" "kubectl --kubeconfig /k/doks.yaml --context ctx-cloud --namespace contexture get pods"
}

test_helm_is_pinned() {
  ctx_helm list
  assert_contains "$(stub_calls)" "helm --kubeconfig /k/doks.yaml --kube-context ctx-cloud --namespace contexture list"
}

test_helmfile_uses_cloud_environment_and_context() {
  ctx_helmfile sync
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "--kube-context ctx-cloud"
  assert_contains "$calls" "-e cloud"
  assert_contains "$calls" "KUBECONFIG=/k/doks.yaml"
}

test_common_never_switches_current_context() {
  assert_not_contains "$(cat "$REPO_ROOT/tools/cloud/common.sh")" "use-context"
}
