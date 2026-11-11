#!/usr/bin/env bash
# 集群内构建（030 research R10）：把 contexture-build 中的 buildkitd 扩为 1 → 开发机 buildctl 经 kubectl exec 传上下文构建并推送 → 缩回 0。
# 推送凭证只放在一次性的 DOCKER_CONFIG 临时目录中（buildctl 由客户端提供仓库认证），结束即删除。
CTX_BUILD_NS=contexture-build

ctx_buildkit_up() {
  ctx_kubectl -n "$CTX_BUILD_NS" scale deployment/buildkitd --replicas=1 >/dev/null
  ctx_kubectl -n "$CTX_BUILD_NS" rollout status deployment/buildkitd --timeout=900s >/dev/null
  ctx_kubectl -n "$CTX_BUILD_NS" get pods -l app.kubernetes.io/name=buildkitd \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'
}

ctx_buildkit_down() {
  ctx_kubectl -n "$CTX_BUILD_NS" scale deployment/buildkitd --replicas=0 >/dev/null
}

# ctx_buildkit_build <Dockerfile 相对路径> <目标阶段或空> <镜像引用>：构建上下文为仓库根目录（遵循 .dockerignore）
ctx_buildkit_build() {
  local dockerfile=$1 target=$2 image=$3 pod status=0 cfg
  [[ -n ${CTX_CLOUD_REGISTRY_WRITE_TOKEN:-} ]] ||
    { echo "错误：集群内构建需要 .env.cloud 中的 CTX_CLOUD_REGISTRY_WRITE_TOKEN" >&2; return 2; }
  cfg=$(mktemp -d); chmod 700 "$cfg"
  jq -n --arg host "${CTX_CLOUD_REGISTRY%%/*}" \
    --arg auth "$(printf 'contexture:%s' "$CTX_CLOUD_REGISTRY_WRITE_TOKEN" | base64 -w0)" \
    '{auths: {($host): {auth: $auth}}}' > "$cfg/config.json"
  chmod 600 "$cfg/config.json"

  pod=$(ctx_buildkit_up)
  local args=(build --frontend dockerfile.v0
    --local "context=$CTX_REPO_ROOT"
    --local "dockerfile=$CTX_REPO_ROOT/$(dirname "$dockerfile")"
    --opt "filename=$(basename "$dockerfile")"
    --output "type=image,name=$image,push=true")
  [[ -n $target ]] && args+=(--opt "target=$target")
  DOCKER_CONFIG=$cfg KUBECONFIG=$CTX_CLOUD_KUBECONFIG \
    buildctl --addr "kube-pod://$pod?namespace=$CTX_BUILD_NS&context=$CTX_CLOUD_CONTEXT" "${args[@]}" || status=$?
  rm -rf "$cfg"
  ctx_buildkit_down
  return $status
}
