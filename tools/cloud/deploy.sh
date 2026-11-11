#!/usr/bin/env bash
# make cloud-deploy（030 US1）：在 .env.cloud 指定的集群部署或更新整套织境，可重复执行。
# 流程：校验配置 → 开发模式确认并先结束 → CRD 冲突检查 → Secret → helmfile 同步 → OpenMetadata 本体配置（工具箱）
#       → 冒烟测试 → 记录稳定版本 → 输出访问地址与 DNS 记录。
# 用法：tools/cloud/deploy.sh [镜像版本，如 git-<12 位>]（首次部署必填；省略时沿用状态记录中的稳定版本）
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"
source "$HERE/secrets.sh"
source "$HERE/lib/tags.sh"
source "$HERE/lib/state.sh"
source "$HERE/lib/toolbox.sh"

# 织境安装的 CRD 组与对应的 Helm release（namespace/名称）；同组 CRD 已存在而 release 不在时视为其他负载所装（spec 边界情况）
CTX_OWNED_CRD_GROUPS=(
  "postgresql.cnpg.io cnpg-system cnpg"
  "doris.selectdb.com doris-system doris-operator"
  "gateway.envoyproxy.io envoy-gateway-system envoy-gateway"
  "cert-manager.io cert-manager cert-manager"
)

ctx_check_crd_conflicts() {
  local crds entry group ns release conflicts=()
  crds=$(ctx_kubectl get crd -o name 2>/dev/null | sed 's#.*/##')
  for entry in "${CTX_OWNED_CRD_GROUPS[@]}"; do
    read -r group ns release <<< "$entry"
    local found; found=$(grep -E "\.${group//./\\.}$" <<< "$crds" || true)
    [[ -z $found ]] && continue
    ctx_helm -n "$ns" status "$release" >/dev/null 2>&1 && continue
    conflicts+=($found)
  done
  if [[ ${#conflicts[@]} -gt 0 ]]; then
    printf '集群中已有以下 CRD，且不是织境的 Helm release 安装的，为避免覆盖其他负载已停止：\n' >&2
    printf '  %s\n' "${conflicts[@]}" >&2
    return 2
  fi
}

# 部署或启动等待失败时：列出无法调度的 Pod 及原因、镜像拉取失败的 Pod（spec 边界情况）
ctx_report_unschedulable() {
  echo "以下 Pod 未能调度（多为弹性池节点不足或仍在扩容）："
  ctx_kubectl get pods -A --field-selector=status.phase=Pending \
    -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.conditions[?(@.type=="PodScheduled")].reason}: {.status.conditions[?(@.type=="PodScheduled")].message}{"\n"}{end}' |
    sed 's/^/  /'
  echo "以下 Pod 拉取镜像失败（检查镜像版本与仓库凭证 docr-pull）："
  ctx_kubectl get pods -A \
    -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.status.containerStatuses[*].state.waiting.reason}{"\n"}{end}' |
    grep -E 'ImagePullBackOff|ErrImagePull' | sed 's/^/  /' || true
}

ctx_dev_reset() { "$HERE/dev.sh" reset; }

# OpenMetadata 本体配置（对应 tools/up.sh 第 6 步）：在工具箱中经集群内地址调用，凭证来自 toolbox-env
ctx_deploy_om_config() {
  ctx_toolbox_run "uv sync --frozen --package contexture-tools >/dev/null && \
    uv run python -m tools.om_config --om-url http://openmetadata.$CTX_CLOUD_NAMESPACE.svc:8585"
}

# 冒烟测试：沿用各组件 tests/smoke.sh；用只含云端上下文的临时 kubeconfig，临时 Pod 固定到弹性池
ctx_run_smoke_tests() {
  local kube failed=0 t name insecure=
  [[ ${CTX_CLOUD_ACME_SERVER:-production} == staging ]] && insecure=1   # staging 证书不受信任
  kube=$(mktemp); chmod 600 "$kube"
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" --context "$CTX_CLOUD_CONTEXT" config view --minify --flatten --raw > "$kube"
  for t in "$CTX_REPO_ROOT"/deploy/components/*/tests/smoke.sh "$CTX_REPO_ROOT"/deploy/charts/*/tests/smoke.sh; do
    name=$(basename "$(dirname "$(dirname "$t")")")
    if KUBECONFIG=$kube NS=$CTX_CLOUD_NAMESPACE CTX_NODE_SELECTOR="$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" CTX_ENV=cloud \
      CTX_SMOKE_BASE_URL="https://$CTX_CLOUD_DOMAIN" CTX_SMOKE_INSECURE="$insecure" \
      "$t" > "$CTX_LOG_DIR/smoke-$name.log" 2>&1; then
      echo "  ✔ $name"
    else
      echo "  ✘ $name（日志 $CTX_LOG_DIR/smoke-$name.log）"; failed=1
    fi
  done
  rm -f "$kube"
  return $failed
}

# 证书签发守护（T052 实测）：首次签发时 cert-manager 的集群内自检可能先于公网负载均衡器健康检查通过，Let's Encrypt 从公网取验证
# 文件失败，证书进入约 1 小时的失败退避；而 AI 网关等依赖证书就绪，Helm 等待会先超时。部署期间在后台运行：发现签发失败
# （status.lastFailureTime）即等待负载均衡器稳定后重建证书对象（去掉 status，绕过退避），最多 CTX_CERT_GUARD_ROUNDS 次。
ctx_cert_guard() {
  local ns=$CTX_CLOUD_NAMESPACE rounds=0 i json
  local interval=${CTX_CERT_GUARD_INTERVAL:-20} settle=${CTX_CERT_GUARD_SETTLE:-60} max=${CTX_CERT_GUARD_ROUNDS:-3}
  for ((i = 0; i < 120; i++)); do
    [[ $(ctx_kubectl -n "$ns" get certificate contexture \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null) == True ]] && return 0
    if [[ -n $(ctx_kubectl -n "$ns" get certificate contexture -o jsonpath='{.status.lastFailureTime}' 2>/dev/null) ]]; then
      if ((rounds >= max)); then
        echo "证书签发已重试 $max 次仍失败：kubectl -n $ns get challenge 查看原因（DNS 记录是否指向负载均衡器）"
        return 0
      fi
      rounds=$((rounds + 1))
      echo "证书签发失败，${settle} 秒后重建证书对象重试（第 $rounds 次）"
      sleep "$settle"
      json=$(ctx_kubectl -n "$ns" get certificate contexture -o json |
        jq 'del(.status, .metadata.uid, .metadata.resourceVersion, .metadata.creationTimestamp, .metadata.generation, .metadata.managedFields)')
      ctx_kubectl -n "$ns" delete certificate contexture >/dev/null
      ctx_kubectl -n "$ns" create -f - <<< "$json" >/dev/null
    fi
    sleep "$interval"
  done
  return 0
}

# 后台启动 / 结束证书守护（单独成函数，便于测试同步替换）
ctx_cert_guard_start() { ctx_cert_guard & CTX_CERT_GUARD_PID=$!; }
# 注意 set -e：&& 列表的最后一条失败会使脚本退出，守护已结束时 kill 必然失败，须用 if 包住
ctx_cert_guard_stop() {
  if [[ -n ${CTX_CERT_GUARD_PID:-} ]]; then kill "$CTX_CERT_GUARD_PID" 2>/dev/null || true; fi
}

# 部署前恢复停止中的工作负载（T052 实测：Envoy 代理等由控制器管理，Helm 不会恢复其副本）
ctx_deploy_resume() { "$HERE/lifecycle.sh" resume; }

ctx_print_access() {
  local ip
  ip=$(ctx_kubectl -n envoy-gateway-system get svc -l gateway.envoyproxy.io/owning-gateway-name=contexture \
    -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null)
  cat <<INFO

织境云端环境
  织境 Web     https://$CTX_CLOUD_DOMAIN        测试用户 user1 / engineer1 / admin1（密码同用户名）
  其他组件     make cloud-info
  负载均衡器   ${ip:-（尚未分配）}
  DNS 记录     $CTX_CLOUD_DOMAIN  A  ${ip:-<负载均衡器 IP>}
               *.$CTX_CLOUD_DOMAIN  A  ${ip:-<负载均衡器 IP>}
INFO
}

ctx_deploy_main() {
  local version=${1:-${VERSION:-}} bff_tag web_tag
  ctx_load_config
  if [[ -z $version ]]; then
    bff_tag=$(ctx_state_get stableVersion.bffTag); web_tag=$(ctx_state_get stableVersion.webTag)
    [[ -n $bff_tag && -n $web_tag ]] ||
      ctx_die "$CTX_EXIT_CONFIG" "首次部署须指定镜像版本：make cloud-deploy VERSION=git-<提交前 12 位>（由 cloud-images 流水线产出）"
  else
    bff_tag=$version; web_tag=$version
  fi

  if [[ $(ctx_state_get devMode.active) == true ]]; then
    ctx_confirm "开发模式正在运行：部署会先结束开发模式（bff / web 恢复为稳定版本）再更新环境。"
    ctx_dev_reset
  fi
  ctx_check_crd_conflicts || exit "$CTX_EXIT_CONFIG"

  ctx_log "生成 Secret（已存在的不覆盖）"
  ctx_ensure_secrets
  ctx_deploy_resume
  ctx_log "helmfile sync（云端环境；不含模拟源系统）"
  export CTX_CLOUD_BFF_TAG=$bff_tag CTX_CLOUD_WEB_TAG=$web_tag
  ctx_cert_guard_start
  if ! ctx_helmfile -l 'group!=mock-sources' sync; then
    ctx_cert_guard_stop
    ctx_report_unschedulable
    exit "$CTX_EXIT_FAILED"
  fi
  ctx_cert_guard_stop
  ctx_log "OpenMetadata：本体共用字段与关系类型"
  ctx_deploy_om_config || exit "$CTX_EXIT_FAILED"

  local source=pipeline commit dirty=false
  [[ $bff_tag == ws-* ]] && source=workspace
  commit=${bff_tag#*-}; commit=${commit%%-*}
  [[ $bff_tag =~ ^ws-[0-9a-f]+-[0-9a-f]+$ ]] && dirty=true
  ctx_state_set "stableVersion.bff=$CTX_CLOUD_REGISTRY/bff:$bff_tag" "stableVersion.web=$CTX_CLOUD_REGISTRY/web:$web_tag" \
    "stableVersion.bffTag=$bff_tag" "stableVersion.webTag=$web_tag" "stableVersion.source=$source" \
    "stableVersion.commit=$commit" "stableVersion.dirty=$dirty" \
    "devMode.active=false" "lifecycle.state=running"

  ctx_log "冒烟测试"
  local smoke=0
  ctx_run_smoke_tests || smoke=1
  ctx_print_access
  [[ $smoke == 0 ]] || { echo "有组件未通过冒烟测试"; exit "$CTX_EXIT_FAILED"; }
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_deploy_main "$@"
fi
