#!/usr/bin/env bash
# make cloud-build（030 US5、FR-022）：基于开发机当前工作区（含未提交改动）在集群内构建 bff / web 并部署到云端环境，
# 部署后即为稳定版本（clarify Q4）。--dev 构建开发模式镜像、--toolbox 构建工具箱镜像，均只构建不部署。
# OpenMetadata 相关镜像不在集群内构建，只由 cloud-images 流水线构建。
# 用法：tools/cloud/build.sh [bff|web|all|--dev|--toolbox]
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"
source "$HERE/lib/tags.sh"
source "$HERE/lib/state.sh"
source "$HERE/lib/buildkit.sh"

ctx_dev_reset() { "$HERE/dev.sh" reset; }

ctx_dev_image() {  # ctx_dev_image <bff|web>：开发镜像引用，标签只随依赖锁文件变化
  local locks
  case $1 in
    bff) locks=("$CTX_REPO_ROOT/uv.lock" "$CTX_REPO_ROOT/services/bff/Dockerfile") ;;
    web) locks=("$CTX_REPO_ROOT/pnpm-lock.yaml" "$CTX_REPO_ROOT/apps/web/Dockerfile") ;;
  esac
  printf '%s/%s-dev:%s' "$CTX_CLOUD_REGISTRY" "$1" "$(ctx_tag_lock dev "${locks[@]}")"
}

ctx_toolbox_image_ref() {
  printf '%s/toolbox:%s' "$CTX_CLOUD_REGISTRY" \
    "$(ctx_tag_lock toolbox "$CTX_REPO_ROOT/deploy/components/ci-toolbox/Dockerfile" "$CTX_REPO_ROOT/tools/cloud/tools.lock")"
}

ctx_build_main() {
  local target=${1:-all}
  ctx_load_config
  case $target in
    --dev)
      ctx_buildkit_build services/bff/Dockerfile dev "$(ctx_dev_image bff)" || exit "$CTX_EXIT_FAILED"
      ctx_buildkit_build apps/web/Dockerfile dev "$(ctx_dev_image web)" || exit "$CTX_EXIT_FAILED"
      return 0 ;;
    --toolbox)
      local image; image=$(ctx_toolbox_image_ref)
      ctx_buildkit_build deploy/components/ci-toolbox/Dockerfile "" "$image" || exit "$CTX_EXIT_FAILED"
      ctx_state_set "toolboxImage=$image"
      return 0 ;;
    bff | web | all) ;;
    *) ctx_die "$CTX_EXIT_CONFIG" "只能构建 bff、web、all（或 --dev、--toolbox）；OpenMetadata 相关镜像由 cloud-images 流水线构建" ;;
  esac

  local tag bff_tag web_tag
  tag=$(ctx_tag_workspace "$CTX_REPO_ROOT")
  bff_tag=$(ctx_state_get stableVersion.bffTag); web_tag=$(ctx_state_get stableVersion.webTag)
  if [[ $target == bff || $target == all ]]; then
    ctx_buildkit_build services/bff/Dockerfile "" "$CTX_CLOUD_REGISTRY/bff:$tag" || exit "$CTX_EXIT_FAILED"
    bff_tag=$tag
  fi
  if [[ $target == web || $target == all ]]; then
    ctx_buildkit_build apps/web/Dockerfile "" "$CTX_CLOUD_REGISTRY/web:$tag" || exit "$CTX_EXIT_FAILED"
    web_tag=$tag
  fi

  # R11：开发模式中 helm 更新会让原 Pod 与开发 Pod 同时运行，须先结束开发模式
  if [[ $(ctx_state_get devMode.active) == true ]]; then
    ctx_confirm "开发模式正在运行：部署新构建的镜像会先结束开发模式。"
    ctx_dev_reset
  fi
  export CTX_CLOUD_BFF_TAG=$bff_tag CTX_CLOUD_WEB_TAG=$web_tag
  ctx_helmfile -l name=contexture -l name=web sync --skip-needs || exit "$CTX_EXIT_FAILED"
  local commit=${tag#ws-}; commit=${commit%%-*} dirty=false
  ctx_workspace_dirty "$CTX_REPO_ROOT" && dirty=true
  ctx_state_set "stableVersion.bff=$CTX_CLOUD_REGISTRY/bff:$bff_tag" "stableVersion.web=$CTX_CLOUD_REGISTRY/web:$web_tag" \
    "stableVersion.bffTag=$bff_tag" "stableVersion.webTag=$web_tag" "stableVersion.source=workspace" \
    "stableVersion.commit=$commit" "stableVersion.dirty=$dirty" "devMode.active=false"
  echo "已部署：bff $bff_tag，web $web_tag（来源：工作区$([[ $dirty == true ]] && echo '，含未提交改动')）"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_build_main "$@"
fi
