#!/usr/bin/env bash
# T076/T077：cloud-stop / cloud-start / cloud-status（FR-032～FR-038、R13、R7、R18）
source "$REPO_ROOT/tools/cloud/lifecycle.sh"
stub_log_init
FAKE=$(mktemp -d)
# 假集群：每个 namespace 一个文件，行格式 “Kind/名称 副本数 停止注解”
printf 'Deployment/contexture-bff 1 \nDeployment/web 1 \nStatefulSet/doris-be 1 \nStatefulSet/opensearch 1 \n' > "$FAKE/contexture"
printf 'StatefulSet/mock-mes 1 \n' > "$FAKE/mock-sources"
printf 'Deployment/buildkitd 0 \n' > "$FAKE/contexture-build"
: > "$FAKE/contexture-ci"
printf 'Deployment/envoy-gateway 1 \nDeployment/envoy-contexture-contexture-1 1 \n' > "$FAKE/envoy-gateway-system"
printf 'Deployment/cert-manager 1 \nDeployment/cert-manager-webhook 1 \n' > "$FAKE/cert-manager"
printf 'Deployment/cnpg-cloudnative-pg 1 \n' > "$FAKE/cnpg-system"
printf 'Deployment/doris-operator 1 \n' > "$FAKE/doris-system"
NODES=0 BLOCKERS="" STATE_DEV=false TOOLBOX_RUNNING="" LIFECYCLE=running
ctx_load_config() { CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_NODE_LABEL=example.com/pool CTX_CLOUD_NODE_POOL=elastic CTX_LOG_DIR=$(mktemp -d); }
ctx_state_get() { case $1 in devMode.active) echo "$STATE_DEV" ;; lifecycle.state) echo "$LIFECYCLE" ;; stableVersion.source) echo pipeline ;; stableVersion.bffTag) echo git-abc ;; stableVersion.dirty) echo false ;; esac; }
ctx_state_set() { stub_record "state $*"; }
ctx_dev_reset() { stub_record "dev-reset"; }
ctx_run_smoke_tests() { stub_record "smoke"; }
ctx_lc_wait_ready() { stub_record "wait-ready $*"; }
ctx_kubectl() {
  local ns=contexture args=("$@") i s="$*"
  for ((i = 0; i < ${#args[@]}; i++)); do [[ ${args[i]} == -n ]] && ns=${args[i + 1]}; done
  case "$*" in
    *"get deploy,statefulset"*) cat "$FAKE/$ns" 2>/dev/null ;;
    *"annotate "*) stub_record "annotate -n $ns ${s##*annotate }" ;;
    *"scale "*) stub_record "scale -n $ns ${s##*scale }" ;;
    *"get nodes"*) for ((i = 0; i < NODES; i++)); do echo "node/n$i"; done ;;
    *"get pods"*"--field-selector=spec.nodeName"*) printf '%s' "$BLOCKERS" ;;
    *"get pod contexture-toolbox"*) printf '%s' "$TOOLBOX_RUNNING" ;;
    *"get clusters.postgresql.cnpg.io"*) printf 'contexture/pg\nmock-sources/mock-qms\n' ;;
    *"get cronjob"*) printf 'openmetadata-reindex\n' ;;
    *"get certificate"*) echo True ;;
    *) stub_record "kubectl -n $ns $*" ;;
  esac
}

line_of() { stub_calls | grep -n -- "$1" | head -1 | cut -d: -f1; }

test_stop_records_replicas_then_scales_to_zero() {
  ctx_lc_stop >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "annotate -n contexture deployment/contexture-bff contexture.io/stopped-replicas=1"
  assert_contains "$c" "scale -n contexture deployment/contexture-bff --replicas=0"
  assert_contains "$c" "annotate -n contexture-build deployment/buildkitd contexture.io/stopped-replicas=0"
}

test_stop_order_controllers_workloads_cnpg_then_remaining_controllers() {
  ctx_lc_stop >/dev/null
  [[ $(line_of "scale -n doris-system") -lt $(line_of "scale -n contexture statefulset/doris-be") ]] || fail "Doris operator 须先停"
  [[ $(line_of "scale -n envoy-gateway-system deployment/envoy-gateway ") -lt $(line_of "scale -n envoy-gateway-system deployment/envoy-contexture") ]] ||
    fail "Envoy Gateway 控制器须先于代理停止"
  [[ $(line_of "scale -n contexture deployment/web") -lt $(line_of "cnpg.io/hibernation=on") ]] || fail "工作负载须先于 PostgreSQL 停止"
  [[ $(line_of "cnpg.io/hibernation=on") -lt $(line_of "scale -n cnpg-system") ]] || fail "CNPG 休眠须在 operator 停止前"
  [[ $(line_of "cnpg.io/hibernation=on") -lt $(line_of "scale -n cert-manager") ]] || fail "cert-manager 最后停止"
  assert_contains "$(stub_calls)" "patch cronjob openmetadata-reindex"
}

test_stop_never_touches_dev_or_system_namespaces() {
  ctx_lc_stop >/dev/null
  assert_not_contains "$(stub_calls)" "-n dev "
  assert_not_contains "$(stub_calls)" "-n kube-system"
}

test_stop_waits_for_pool_to_reach_zero_and_records_stopped() {
  ctx_lc_stop >/dev/null
  assert_contains "$(stub_calls | tail -1)" "lifecycle.state=stopped"
}

test_stop_timeout_reports_blocking_pods_and_exits_4() {
  NODES=1 BLOCKERS=$'other-ns\tsomething-0\n' CTX_LC_TIMEOUT=1 CTX_LC_POLL=1
  assert_status 4 ctx_lc_stop
  assert_contains "$OUTPUT" "something-0"
}

test_stop_confirms_when_dev_mode_or_toolbox_running_and_ends_dev_mode() {
  STATE_DEV=true
  CONFIRM= assert_status 3 ctx_lc_stop
  assert_not_contains "$(stub_calls)" "scale"
  STATE_DEV=false TOOLBOX_RUNNING=pod/contexture-toolbox
  CONFIRM= assert_status 3 ctx_lc_stop
  STATE_DEV=true TOOLBOX_RUNNING=
  CONFIRM=yes ctx_lc_stop >/dev/null
  [[ $(line_of dev-reset) -lt $(line_of "scale ") ]] || fail "须先结束开发模式"
}

test_stop_is_idempotent_when_already_stopped() {
  LIFECYCLE=stopped
  printf 'Deployment/web 0 1\n' > "$FAKE/contexture"
  ctx_lc_stop >/dev/null
  assert_not_contains "$(stub_calls)" "annotate -n contexture deployment/web contexture.io/stopped-replicas=0"
}

test_start_restores_recorded_replicas_in_reverse_order_and_runs_smoke() {
  for f in "$FAKE"/*; do sed -i -E 's#^([^ ]+) ([0-9]+) $#\1 0 \2#' "$f"; done
  LIFECYCLE=stopped
  ctx_lc_start >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "scale -n contexture deployment/contexture-bff --replicas=1"
  assert_contains "$c" "annotate -n contexture deployment/contexture-bff contexture.io/stopped-replicas-"
  [[ $(line_of "scale -n cnpg-system") -lt $(line_of "cnpg.io/hibernation-") ]] || fail "CNPG operator 须先恢复"
  [[ $(line_of "cnpg.io/hibernation-") -lt $(line_of "scale -n contexture deployment/contexture-bff") ]] || fail "数据库须先于工作负载恢复"
  [[ $(line_of "scale -n envoy-gateway-system deployment/envoy-gateway ") -lt $(line_of "scale -n envoy-gateway-system deployment/envoy-contexture") ]] ||
    fail "R3：先恢复 Envoy Gateway 控制器，再恢复代理副本"
  assert_contains "$c" "smoke"
  assert_contains "$(stub_calls | tail -1)" "lifecycle.state=running"
}

test_status_reports_state_dev_mode_version_nodes_and_residue() {
  NODES=2 TOOLBOX_RUNNING=pod/contexture-toolbox STATE_DEV=true
  local out; out=$(ctx_lc_status)
  assert_contains "$out" "运行状态"
  assert_contains "$out" "开发模式（无本地进程）"
  assert_contains "$out" "git-abc"
  assert_contains "$out" "流水线"
  assert_contains "$out" "弹性池节点：2"
  assert_contains "$out" "contexture-toolbox"
}
