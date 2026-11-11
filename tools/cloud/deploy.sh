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
  local kube failed=0 t name
  kube=$(mktemp); chmod 600 "$kube"
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" --context "$CTX_CLOUD_CONTEXT" config view --minify --flatten --raw > "$kube"
  for t in "$CTX_REPO_ROOT"/deploy/components/*/tests/smoke.sh "$CTX_REPO_ROOT"/deploy/charts/*/tests/smoke.sh; do
    name=$(basename "$(dirname "$(dirname "$t")")")
    if KUBECONFIG=$kube NS=$CTX_CLOUD_NAMESPACE CTX_NODE_SELECTOR="$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" \
      "$t" > "$CTX_LOG_DIR/smoke-$name.log" 2>&1; then
      echo "  ✔ $name"
    else
      echo "  ✘ $name（日志 $CTX_LOG_DIR/smoke-$name.log）"; failed=1
    fi
  done
  rm -f "$kube"
  return $failed
}

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
  ctx_log "helmfile sync（云端环境；不含模拟源系统）"
  export CTX_CLOUD_BFF_TAG=$bff_tag CTX_CLOUD_WEB_TAG=$web_tag
  if ! ctx_helmfile -l 'group!=mock-sources' sync; then
    ctx_report_unschedulable
    exit "$CTX_EXIT_FAILED"
  fi
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
