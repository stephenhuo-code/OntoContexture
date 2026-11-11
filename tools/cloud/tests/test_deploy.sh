#!/usr/bin/env bash
# T041：cloud-deploy（FR-002～FR-006、FR-013、FR-024、FR-028；spec 边界情况：CRD 冲突、调度失败与镜像拉取失败的报告）
source "$REPO_ROOT/tools/cloud/deploy.sh"
stub_log_init
STATE_DEV=false STATE_TAG= HELM_RELEASES=" cnpg-system/cnpg doris-system/doris-operator envoy-gateway-system/envoy-gateway cert-manager/cert-manager "
CRDS="clusters.postgresql.cnpg.io envoyproxies.gateway.envoyproxy.io"
# 桩：配置已加载；记录所有可能修改集群的调用
ctx_load_config() { CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_REGISTRY=registry.example.com/ctx CTX_CLOUD_DOMAIN=ctx.example.com
  CTX_CLOUD_NODE_LABEL=example.com/pool CTX_CLOUD_NODE_POOL=elastic CTX_CLOUD_CONTEXT=ctx CTX_CLOUD_KUBECONFIG=/k; }
ctx_state_get() { case $1 in devMode.active) echo "$STATE_DEV" ;; stableVersion.bffTag | stableVersion.webTag) echo "$STATE_TAG" ;; esac; }
ctx_state_set() { stub_record "state $*"; }
ctx_ensure_secrets() { stub_record "secrets"; }
ctx_helmfile() { stub_record "helmfile $* BFF=$CTX_CLOUD_BFF_TAG WEB=$CTX_CLOUD_WEB_TAG"; return "${HELMFILE_STATUS:-0}"; }
ctx_helm() { local rel="${*: -1}" ns; ns=$(sed -nE 's/.*-n ([^ ]+).*/\1/p' <<< "$*"); [[ $HELM_RELEASES == *" $ns/$rel "* ]]; }
ctx_kubectl() {
  case "$*" in
    *"get crd -o name"*) for c in $CRDS; do echo "customresourcedefinition.apiextensions.k8s.io/$c"; done ;;
    *"get pods"*"Pending"*) printf 'contexture\topenmetadata-0\tUnschedulable: 0/2 nodes are available: insufficient memory\n' ;;
    *"get pods"*) printf 'contexture\tbff-1\tImagePullBackOff\n' ;;
    *) stub_record "kubectl $*" ;;
  esac
}
ctx_dev_reset() { stub_record "dev-reset"; }
ctx_deploy_om_config() { stub_record "om-config"; }
ctx_run_smoke_tests() { stub_record "smoke"; return "${SMOKE_STATUS:-0}"; }
ctx_deploy_resume() { stub_record "resume"; }
ctx_print_access() { :; }

test_missing_config_exits_before_touching_cluster() {
  ctx_load_config() { exit 2; }
  assert_status 2 ctx_deploy_main
  [[ ! -s $STUB_LOG ]] || fail "配置缺失时不应调用集群：$(stub_calls)"
}

test_first_deploy_requires_version() {
  assert_status 2 ctx_deploy_main
  assert_contains "$OUTPUT" "VERSION"
}

test_version_sets_both_image_tags_and_records_pipeline_source() {
  ctx_deploy_main git-0123456789ab >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "BFF=git-0123456789ab WEB=git-0123456789ab"
  assert_contains "$calls" "stableVersion.source=pipeline"
  assert_contains "$calls" "stableVersion.bff=registry.example.com/ctx/bff:git-0123456789ab"
  assert_contains "$calls" "lifecycle.state=running"
}

test_redeploy_without_version_reuses_stable_tags() {
  STATE_TAG=ws-aaaaaaaaaaaa
  ctx_deploy_main >/dev/null
  assert_contains "$(stub_calls)" "BFF=ws-aaaaaaaaaaaa WEB=ws-aaaaaaaaaaaa"
}

test_dev_mode_requires_confirmation_then_ends_dev_mode_first() {
  STATE_DEV=true
  CONFIRM= assert_status 3 ctx_deploy_main git-0123456789ab
  [[ -z $(stub_calls | grep helmfile) ]] || fail "未确认时不应部署"
  stub_log_init
  CONFIRM=yes ctx_deploy_main git-0123456789ab >/dev/null
  local calls; calls=$(stub_calls)
  [[ $(grep -n dev-reset <<< "$calls" | cut -d: -f1) -lt $(grep -n helmfile <<< "$calls" | cut -d: -f1) ]] ||
    fail "须先结束开发模式再部署"
}

test_foreign_crd_stops_deploy() {
  HELM_RELEASES=" doris-system/doris-operator envoy-gateway-system/envoy-gateway cert-manager/cert-manager "
  assert_status 2 ctx_deploy_main git-0123456789ab
  assert_contains "$OUTPUT" "clusters.postgresql.cnpg.io"
  [[ -z $(stub_calls | grep -E 'helmfile|secrets') ]] || fail "CRD 冲突时不应修改集群"
}

test_failed_sync_reports_unschedulable_and_image_pull_errors() {
  HELMFILE_STATUS=1
  assert_status 1 ctx_deploy_main git-0123456789ab
  assert_contains "$OUTPUT" "openmetadata-0"
  assert_contains "$OUTPUT" "insufficient memory"
  assert_contains "$OUTPUT" "ImagePullBackOff"
}

test_failed_smoke_tests_fail_the_command_but_keep_order() {
  SMOKE_STATUS=1
  assert_status 1 ctx_deploy_main git-0123456789ab
  local calls; calls=$(stub_calls)
  [[ $(grep -n secrets <<< "$calls" | cut -d: -f1) -lt $(grep -n helmfile <<< "$calls" | cut -d: -f1) ]] || fail "顺序错误"
  assert_contains "$calls" "om-config"
}

test_mock_sources_are_excluded_from_deploy() {
  ctx_deploy_main git-0123456789ab >/dev/null
  assert_contains "$(stub_calls)" "group!=mock-sources"
}

# T052 实测：停止后的环境（或手工缩容的控制器）直接部署时，Envoy 代理等由控制器管理的工作负载不会被 Helm 恢复，入口无后端、证书无法签发。
# 部署须先恢复所有带停止注解的工作负载（幂等，未停止时无操作）
test_deploy_resumes_stopped_workloads_before_sync() {
  ctx_deploy_main git-0123456789ab >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "resume"
  [[ $(grep -n '^resume' <<< "$calls" | cut -d: -f1) -lt $(grep -n '^helmfile' <<< "$calls" | cut -d: -f1) ]] || fail "须在同步前恢复"
}
