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

# T083 实测：开发机 shell 的 PATH 中 ~/.local/bin 排在 /usr/bin 之后，脚本调用的是系统自带的 jq 1.6 而非锁定的 1.8.2。
# 云端脚本须优先使用 cloud-tools 按锁文件安装的工具，不依赖用户 shell 的配置
test_locked_tools_directory_comes_first_in_path() {
  local first
  first=$(PATH="/usr/bin:/bin:$HOME/.local/bin" bash -c 'source "$1/tools/cloud/common.sh"; echo "${PATH%%:*}"' _ "$REPO_ROOT")
  assert_eq "$HOME/.local/bin" "$first"
}
