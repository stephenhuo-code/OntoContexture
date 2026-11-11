#!/usr/bin/env bash
# make cloud-dev / cloud-dev-reset（030 US2、FR-011～FR-014、research R11、R18）：
# 把云端环境中的 bff / web 替换为开发镜像并同步开发机工作区的源码（几秒内生效，不经 git、不构建镜像）；
# 退出（含 Ctrl+C、出错）时恢复为稳定版本。开发机重建等导致异常退出后，用 reset 恢复。
# 用法：tools/cloud/dev.sh [bff|web|all|reset]
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"
source "$HERE/lib/tags.sh"
source "$HERE/lib/state.sh"
source "$HERE/build.sh"
CTX_DEVSPACE_CONFIG="$CTX_REPO_ROOT/deploy/cloud/devspace.yaml"

ctx_build_dev_images() { ctx_build_main --dev; }

ctx_devspace() {
  KUBECONFIG=$CTX_CLOUD_KUBECONFIG DEVSPACE_DISABLE_TELEMETRY=true \
    devspace "$@" --config "$CTX_DEVSPACE_CONFIG" --kube-context "$CTX_CLOUD_CONTEXT" -n "$CTX_CLOUD_NAMESPACE" --no-warn
}

ctx_dev_reset() {  # 恢复稳定版本；不依赖本地进程（开发机重建后同样可用）
  ctx_devspace reset pods >/dev/null 2>&1 || ctx_devspace reset pods
  ctx_state_set devMode.active=false
}

ctx_dev_cleanup() {
  [[ -n ${CTX_DEV_CLEANED:-} ]] && return 0
  CTX_DEV_CLEANED=1
  [[ -n ${CTX_DEV_PID:-} ]] && kill -KILL "$CTX_DEV_PID" 2>/dev/null
  [[ -n ${CTX_DEV_WATCHER:-} ]] && kill "$CTX_DEV_WATCHER" 2>/dev/null
  ctx_log "恢复稳定版本"
  ctx_dev_reset
}

ctx_dev_main() {
  local target=${1:-all} profile=() lock_tag
  ctx_load_config
  if [[ $target == reset ]]; then ctx_dev_reset; echo "已恢复为稳定版本"; return 0; fi
  case $target in
    all) ;;
    bff) profile=(-p bff-only) ;;
    web) profile=(-p web-only) ;;
    *) ctx_die "$CTX_EXIT_CONFIG" "用法：tools/cloud/dev.sh [bff|web|all|reset]" ;;
  esac

  local ready
  ready=$(ctx_kubectl get deployment contexture-bff web -o jsonpath='{.items[*].status.readyReplicas}' 2>/dev/null || true)
  if [[ $(ctx_state_get lifecycle.state) != running || -z ${ready// /} || ${ready// /} == 0* ]]; then
    ctx_die "$CTX_EXIT_CONFIG" "云端环境未运行：先执行 make cloud-deploy 或 make cloud-start"
  fi

  export CTX_DEV_BFF_IMAGE CTX_DEV_WEB_IMAGE CTX_CLOUD_DOMAIN
  CTX_DEV_BFF_IMAGE=$(ctx_dev_image bff); CTX_DEV_WEB_IMAGE=$(ctx_dev_image web)
  if [[ $(ctx_state_get devImage.bff) != "$CTX_DEV_BFF_IMAGE" || $(ctx_state_get devImage.web) != "$CTX_DEV_WEB_IMAGE" ]]; then
    ctx_log "依赖有变化或首次使用：在集群内构建开发镜像"
    ctx_build_dev_images
    ctx_state_set "devImage.bff=$CTX_DEV_BFF_IMAGE" "devImage.web=$CTX_DEV_WEB_IMAGE"
  fi

  ctx_state_set devMode.active=true "devMode.startedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # 结束时（正常、出错或中断）恢复稳定版本，只执行一次；devspace 后台运行时不响应 INT/TERM，须 KILL（research R11）
  CTX_DEV_PID= CTX_DEV_WATCHER= CTX_DEV_CLEANED=
  trap 'ctx_dev_cleanup; exit 130' INT TERM
  trap 'ctx_dev_cleanup' EXIT
  # 依赖锁文件变化时提示重启（重启会自动重建开发镜像，US2 场景 4）
  lock_tag=$CTX_DEV_BFF_IMAGE$CTX_DEV_WEB_IMAGE
  ( while sleep 5; do
      [[ $(ctx_dev_image bff)$(ctx_dev_image web) == "$lock_tag" ]] ||
        { echo "依赖已变化：按 Ctrl+C 后重新执行 make cloud-dev（将自动重建开发镜像）"; break; }
    done ) &
  CTX_DEV_WATCHER=$!
  ctx_log "开发模式：https://$CTX_CLOUD_DOMAIN（保存文件后几秒内生效；Ctrl+C 结束并恢复稳定版本）"
  ctx_devspace dev "${profile[@]}" & CTX_DEV_PID=$!
  local status=0
  wait "$CTX_DEV_PID" || status=$?
  ctx_dev_cleanup
  return $status
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_dev_main "$@"
fi
