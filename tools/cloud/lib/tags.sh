#!/usr/bin/env bash
# 镜像标签规则（030 data-model.md 第 4 节）：标签可追溯到提交；含未提交改动时附改动摘要，同样的工作区得到同样的标签。

ctx_tag_pipeline() { printf 'git-%s' "${1:0:12}"; }

ctx_workspace_dirty() {  # 有未提交改动（含未跟踪且未忽略的文件）时返回 0
  [[ -n $(git -C "${1:-.}" status --porcelain) ]]
}

ctx_workspace_digest() {  # 改动摘要：git diff HEAD 与未跟踪文件（名称 + 内容）的 SHA-256
  local dir=${1:-.} file
  {
    git -C "$dir" diff HEAD --binary
    while IFS= read -r -d '' file; do
      printf '%s\0' "$file"; cat "$dir/$file"
    done < <(git -C "$dir" ls-files -z -o --exclude-standard | sort -z)
  } | sha256sum | cut -c1-8
}

ctx_tag_workspace() {
  local dir=${1:-.} head
  head=$(git -C "$dir" rev-parse HEAD)
  if ctx_workspace_dirty "$dir"; then
    printf 'ws-%s-%s' "${head:0:12}" "$(ctx_workspace_digest "$dir")"
  else
    printf 'ws-%s' "${head:0:12}"
  fi
}

ctx_tag_lock() {  # ctx_tag_lock <前缀> <锁文件...>：只随锁文件内容变化（开发镜像、工具箱镜像）
  local prefix=$1; shift
  printf '%s-%s' "$prefix" "$(cat "$@" | sha256sum | cut -c1-12)"
}
