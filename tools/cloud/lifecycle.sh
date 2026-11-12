#!/usr/bin/env bash
# make cloud-stop / cloud-start / cloud-status（030 US6、FR-032～FR-038、research R13）。
# 停止：按依赖顺序把织境的工作负载缩为 0（副本数记在注解 contexture.io/stopped-replicas），PostgreSQL 用 CNPG 休眠，
#       不删除持久卷、Secret 与配置；随后等待弹性池节点被集群自动扩缩释放。
# 启动：逆序恢复，等待就绪与证书，运行冒烟测试。两者均可重复执行，并能从中途失败收敛到目标状态。
# 只处理织境的 namespace，永不触碰 dev（devbox-0）与 kube-*。
# 用法：tools/cloud/lifecycle.sh <stop|start|status|resume>（resume：只恢复不等待，供 cloud-deploy 使用）
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/deploy.sh"

CTX_LC_WORKLOAD_NS=(contexture mock-sources contexture-build contexture-ci)
CTX_LC_ANNOTATION=contexture.io/stopped-replicas

# 列出 namespace 中的 Deployment / StatefulSet：“Kind/名称 副本数 停止注解”
ctx_lc_list() {
  ctx_kubectl -n "$1" get deploy,statefulset --ignore-not-found \
    -o jsonpath='{range .items[*]}{.kind}/{.metadata.name} {.spec.replicas} {.metadata.annotations.contexture\.io/stopped-replicas}{"\n"}{end}'
}

# ctx_lc_stop_ns <namespace> [只处理的名称（正则）] [排除的名称（正则）]
ctx_lc_stop_ns() {
  local ns=$1 only=${2:-} skip=${3:-} ref replicas recorded kind name
  while read -r ref replicas recorded; do
    [[ -z $ref ]] && continue
    kind=${ref%%/*}; name=${ref#*/}; kind=${kind,,}
    [[ -n $only && ! $name =~ $only ]] && continue
    [[ -n $skip && $name =~ $skip ]] && continue
    [[ -z $recorded ]] && ctx_kubectl -n "$ns" annotate "$kind/$name" "$CTX_LC_ANNOTATION=${replicas:-0}" --overwrite >/dev/null
    [[ ${replicas:-0} != 0 ]] && ctx_kubectl -n "$ns" scale "$kind/$name" --replicas=0 >/dev/null
  done < <(ctx_lc_list "$ns")
  return 0
}

# ctx_lc_start_ns <namespace> [只处理的名称（正则）] [排除的名称（正则）]：恢复注解中记录的副本数并删除注解
ctx_lc_start_ns() {
  local ns=$1 only=${2:-} skip=${3:-} ref replicas recorded kind name
  while read -r ref replicas recorded; do
    [[ -z $ref || -z $recorded ]] && continue
    kind=${ref%%/*}; name=${ref#*/}; kind=${kind,,}
    [[ -n $only && ! $name =~ $only ]] && continue
    [[ -n $skip && $name =~ $skip ]] && continue
    ctx_kubectl -n "$ns" scale "$kind/$name" --replicas="$recorded" >/dev/null
    ctx_kubectl -n "$ns" annotate "$kind/$name" "$CTX_LC_ANNOTATION-" >/dev/null
  done < <(ctx_lc_list "$ns")
  return 0
}

ctx_lc_cronjobs() {  # ctx_lc_cronjobs <true|false>：停止期间暂停定时任务（不补跑，R13）
  local cj
  for cj in $(ctx_kubectl -n "$CTX_CLOUD_NAMESPACE" get cronjob -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
    ctx_kubectl -n "$CTX_CLOUD_NAMESPACE" patch cronjob "$cj" --type merge -p "{\"spec\":{\"suspend\":$1}}" >/dev/null
  done
}

ctx_lc_cnpg() {  # ctx_lc_cnpg <on|off>：CNPG 原生休眠，保留 PVC
  local item ns name
  for item in $(ctx_kubectl get clusters.postgresql.cnpg.io -A --ignore-not-found \
    -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' 2>/dev/null); do
    ns=${item%%/*}; name=${item#*/}
    if [[ $1 == on ]]; then
      ctx_kubectl -n "$ns" annotate "cluster.postgresql.cnpg.io/$name" cnpg.io/hibernation=on --overwrite >/dev/null
    else
      # operator 刚恢复时 webhook 可能尚未接受请求（T082 实测 connection refused）：重试至成功
      local i
      for ((i = 0; ; i++)); do
        ctx_kubectl -n "$ns" annotate "cluster.postgresql.cnpg.io/$name" cnpg.io/hibernation- >/dev/null && break
        ((i < 60)) || return 1
        sleep "${CTX_LC_RETRY_SLEEP:-10}"
      done
    fi
  done
}

ctx_lc_wait_pg_down() {
  local i
  for ((i = 0; i < 60; i++)); do
    [[ -z $(ctx_kubectl get pods -A -l cnpg.io/podRole=instance -o name 2>/dev/null) ]] && return 0
    sleep 5
  done
}

ctx_lc_pool_nodes() {
  ctx_kubectl get nodes -l "$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" -o name 2>/dev/null | grep -c . || true
}

ctx_lc_blockers() {  # 仍在弹性池节点上、不属于 DaemonSet 的 Pod
  local node
  for node in $(ctx_kubectl get nodes -l "$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" -o name 2>/dev/null); do
    ctx_kubectl get pods -A --field-selector="spec.nodeName=${node#*/}" \
      -o jsonpath='{range .items[?(@.metadata.ownerReferences[0].kind!="DaemonSet")]}{.metadata.namespace}{"\t"}{.metadata.name}{"\n"}{end}'
  done
}

ctx_lc_busy() {  # 正在运行的集群内测试或构建（FR-038）
  ctx_kubectl -n contexture-ci get pod contexture-toolbox --ignore-not-found -o name 2>/dev/null
  ctx_kubectl -n contexture-build get pods -l app.kubernetes.io/name=buildkitd -o name 2>/dev/null
}

ctx_lc_stop() {
  ctx_load_config
  local dev busy
  dev=$(ctx_state_get devMode.active); busy=$(ctx_lc_busy)
  if [[ $dev == true || -n $busy ]]; then
    ctx_confirm "$([[ $dev == true ]] && echo '开发模式正在运行（将先恢复稳定版本）。')$([[ -n $busy ]] && echo "集群内测试或构建正在运行，将被终止：$busy")"
  fi
  ctx_state_set lifecycle.state=stopping
  [[ $dev == true ]] && ctx_dev_reset
  ctx_kubectl -n contexture-ci delete pod contexture-toolbox --ignore-not-found --wait=false >/dev/null

  ctx_log "停止会拉回工作负载的控制器（Doris operator、Envoy Gateway）"
  ctx_lc_stop_ns doris-system
  ctx_lc_stop_ns envoy-gateway-system '^envoy-gateway$'
  ctx_lc_cronjobs true
  ctx_log "停止织境工作负载"
  local ns
  for ns in "${CTX_LC_WORKLOAD_NS[@]}"; do ctx_lc_stop_ns "$ns"; done
  ctx_lc_stop_ns envoy-gateway-system '' '^envoy-gateway$'
  ctx_log "PostgreSQL 休眠（保留数据卷）"
  ctx_lc_cnpg on
  ctx_lc_wait_pg_down
  ctx_lc_stop_ns cnpg-system
  ctx_lc_stop_ns cert-manager

  ctx_log "等待弹性池释放节点（集群自动扩缩通常在约 10 分钟后回收闲置节点）"
  local timeout=${CTX_LC_TIMEOUT:-1500} poll=${CTX_LC_POLL:-30} waited=0 nodes
  while :; do
    nodes=$(ctx_lc_pool_nodes)
    [[ $nodes -le ${CTX_LC_MIN_NODES:-0} ]] && break
    if (( waited >= timeout )); then
      echo "超过 ${timeout} 秒弹性池仍有 $nodes 个节点；以下 Pod 阻止了释放："
      ctx_lc_blockers | sed 's/^/  /'
      exit "$CTX_EXIT_TIMEOUT"
    fi
    sleep "$poll"; waited=$((waited + poll))
  done
  echo "已停止；弹性池节点：$nodes"
  ctx_state_set lifecycle.state=stopped
}

# 等待全部工作负载就绪（失败时报告无法调度与镜像拉取失败的 Pod）
ctx_lc_wait_ready() {
  local ns
  for ns in cnpg-system cert-manager doris-system "${CTX_LC_WORKLOAD_NS[@]}" envoy-gateway-system; do
    ctx_kubectl -n "$ns" wait --for=condition=Available deployment --all --timeout="${CTX_LC_READY_TIMEOUT:-1500s}" >/dev/null 2>&1 &&
      ctx_kubectl -n "$ns" rollout status statefulset --timeout="${CTX_LC_READY_TIMEOUT:-1500s}" >/dev/null 2>&1 ||
      { ctx_report_unschedulable; return 1; }
  done
}

# 只恢复、不等待（cloud-start 与 cloud-deploy 共用；幂等，未停止时不改变副本数）
ctx_lc_resume() {
  ctx_log "恢复控制器与数据库"
  ctx_lc_start_ns cnpg-system
  ctx_lc_start_ns cert-manager
  # 弹性池为 0 时 operator 需等新节点就绪才能运行，解除休眠依赖其 webhook（T082 实测）
  ctx_kubectl -n cnpg-system rollout status deployment --timeout=1200s >/dev/null || return 1
  ctx_lc_cnpg off
  ctx_log "恢复织境工作负载（bff / web 为稳定版本）"
  ctx_lc_start_ns doris-system
  local ns
  for ns in "${CTX_LC_WORKLOAD_NS[@]}"; do ctx_lc_start_ns "$ns"; done
  # R3：Envoy Gateway 控制器不会把代理副本从 0 拉回，先恢复控制器，再按记录恢复代理
  ctx_lc_start_ns envoy-gateway-system '^envoy-gateway$'
  ctx_lc_start_ns envoy-gateway-system '' '^envoy-gateway$'
  ctx_lc_cronjobs false
}

ctx_lc_start() {
  ctx_load_config
  ctx_state_set lifecycle.state=starting
  ctx_lc_resume
  ctx_log "等待就绪"
  ctx_lc_wait_ready || exit "$CTX_EXIT_FAILED"
  local i
  for ((i = 0; i < 60; i++)); do
    [[ $(ctx_kubectl -n "$CTX_CLOUD_NAMESPACE" get certificate contexture \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null) == True ]] && break
    sleep 10
  done
  ctx_log "冒烟测试"
  ctx_run_smoke_tests || exit "$CTX_EXIT_FAILED"
  ctx_print_access
  ctx_state_set lifecycle.state=running
}

ctx_lc_status() {
  ctx_load_config
  local lifecycle desired=0 ready=0 stopped=0 ns ref replicas recorded dev source
  lifecycle=$(ctx_state_get lifecycle.state)
  for ns in "${CTX_LC_WORKLOAD_NS[@]}"; do
    while read -r ref replicas recorded; do
      [[ -z $ref ]] && continue
      desired=$((desired + ${replicas:-0}))
      [[ -n $recorded ]] && stopped=$((stopped + 1))
    done < <(ctx_lc_list "$ns")
  done
  ready=$(ctx_kubectl -n "$CTX_CLOUD_NAMESPACE" get deploy,statefulset \
    -o jsonpath='{range .items[*]}{.status.readyReplicas}{"\n"}{end}' 2>/dev/null | awk '{s+=$1} END {print s+0}')
  dev=$(ctx_state_get devMode.active)
  if [[ $dev == true ]]; then
    if [[ -f $CTX_LOG_DIR/dev.pid ]] && kill -0 "$(cat "$CTX_LOG_DIR/dev.pid")" 2>/dev/null; then dev=开发模式
    else dev='开发模式（无本地进程），执行 make cloud-dev-reset 可恢复'; fi
  else
    dev=稳定版本
  fi
  source=$(ctx_state_get stableVersion.source)
  [[ $source == workspace ]] && source=工作区构建 || source=流水线
  cat <<STATUS
运行状态：$(ctx_derive_state "${lifecycle:-running}" "$desired" "$ready" "$stopped")（记录：${lifecycle:-无}）
当前版本：$dev
稳定版本：bff/web $(ctx_state_get stableVersion.bffTag)（来源：$source；含未提交改动：$(ctx_state_get stableVersion.dirty)）
弹性池节点：$(ctx_lc_pool_nodes)
STATUS
  local off residue
  off=$(ctx_kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.spec.nodeName}{"\n"}{end}' 2>/dev/null |
    grep -E "^($(IFS='|'; echo "${CTX_LC_WORKLOAD_NS[*]}"))/" |
    grep -vF -f <(ctx_kubectl get nodes -l "$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" -o name 2>/dev/null | sed 's#.*/# #') || true)
  [[ -n $off ]] && { echo "不在弹性池上的织境 Pod："; sed 's/^/  /' <<< "$off"; }
  residue=$(ctx_lc_busy)
  [[ -n $residue ]] && { echo "残留或正在运行的工具箱 / 构建 Pod（下次同类命令或 cloud-stop 会清理）："; sed 's/^/  /' <<< "$residue"; }
  return 0
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  case ${1:-} in
    stop) ctx_lc_stop ;;
    start) ctx_lc_start ;;
    resume) ctx_load_config; ctx_lc_resume ;;   # cloud-deploy 部署前调用
    status) ctx_lc_status ;;
    *) ctx_die "$CTX_EXIT_CONFIG" "用法：tools/cloud/lifecycle.sh <stop|start|status|resume>" ;;
  esac
fi
