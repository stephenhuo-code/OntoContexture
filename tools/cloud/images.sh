#!/usr/bin/env bash
# make cloud-images（030 FR-023，2026-11-11 澄清）：为当前提交推送专用标签 cloud-images/<提交前 12 位>，触发 cloud-images 流水线。
# 特性合并到默认分支之前使用（GitHub 界面的手动运行要求流水线文件已在默认分支上）；普通分支推送与合并不会触发流水线。
# 只处理已提交的代码：工作区有未提交改动时拒绝（未提交的改动请用 make cloud-build 在集群内构建）。
# 用法：tools/cloud/images.sh；非交互环境须 CONFIRM=yes
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"
source "$HERE/lib/tags.sh"

ctx_images_actions_url() {  # 由远端地址推出 GitHub Actions 页面；非 GitHub 远端返回空
  local url; url=$(git -C "$1" remote get-url "$2" 2>/dev/null) || return 0
  url=${url%.git}
  case $url in
    https://github.com/*) printf '%s/actions/workflows/cloud-images.yml' "$url" ;;
    git@github.com:*) printf 'https://github.com/%s/actions/workflows/cloud-images.yml' "${url#git@github.com:}" ;;
  esac
}

ctx_images_main() {
  local repo=${CTX_IMAGES_REPO:-$CTX_REPO_ROOT} remote=${CTX_GIT_REMOTE:-origin} branch sha tag url
  branch=$(git -C "$repo" branch --show-current)
  [[ -n $branch ]] || ctx_die "$CTX_EXIT_CONFIG" "当前处于游离 HEAD；请切换到要构建的分支"
  ctx_workspace_dirty "$repo" &&
    ctx_die "$CTX_EXIT_CONFIG" "工作区有未提交改动：流水线只构建已提交的代码。请先提交，或用 make cloud-build 在集群内构建工作区"
  sha=$(git -C "$repo" rev-parse HEAD)
  tag="cloud-images/${sha:0:12}"
  url=$(ctx_images_actions_url "$repo" "$remote")

  if [[ -n $(git -C "$repo" ls-remote --tags "$remote" "refs/tags/$tag") ]]; then
    printf '提交 %s 已触发过流水线（远端已有标签 %s），不重复推送。\n' "${sha:0:12}" "$tag"
    printf '如需重跑，请在 Actions 页面对该次运行选择 Re-run%s\n' "${url:+：$url}"
    return 0
  fi

  ctx_confirm "将推送分支 $branch 与标签 $tag 到 $remote，触发 cloud-images 流水线构建提交 ${sha:0:12}"
  ctx_log "推送分支 $branch"
  git -C "$repo" push "$remote" "$branch" || ctx_die "$CTX_EXIT_FAILED" "推送分支失败"
  git -C "$repo" rev-parse -q --verify "refs/tags/$tag" >/dev/null || git -C "$repo" tag "$tag" "$sha"
  ctx_log "推送标签 $tag（触发流水线）"
  git -C "$repo" push "$remote" "refs/tags/$tag" || ctx_die "$CTX_EXIT_FAILED" "推送标签失败"

  printf '\n已触发 cloud-images 流水线：bff / web 的镜像标签为 git-%s\n' "${sha:0:12}"
  [[ -n $url ]] && printf '查看运行：%s\n' "$url"
  printf '完成后部署：make cloud-deploy VERSION=git-%s\n' "${sha:0:12}"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_images_main "$@"
fi
