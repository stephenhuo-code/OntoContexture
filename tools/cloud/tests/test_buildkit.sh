#!/usr/bin/env bash
# T031：集群内 BuildKit 构建封装（R10、R18）
source "$REPO_ROOT/tools/cloud/common.sh"
source "$REPO_ROOT/tools/cloud/lib/buildkit.sh"
stub_log_init
CTX_CLOUD_KUBECONFIG=/k/doks.yaml CTX_CLOUD_CONTEXT=ctx-cloud CTX_CLOUD_NAMESPACE=contexture
CTX_CLOUD_REGISTRY=registry.example.com/ctx CTX_CLOUD_REGISTRY_WRITE_TOKEN=write-token
ctx_kubectl() {
  stub_record "kubectl $*"
  case "$*" in *"get pods"*) echo buildkitd-abc ;; esac
}
buildctl() {
  stub_record "buildctl $* DOCKER_CONFIG=$DOCKER_CONFIG KUBECONFIG=$KUBECONFIG"
  stub_record "auth=$(cat "$DOCKER_CONFIG/config.json")"
  return "${BUILD_STATUS:-0}"
}

test_build_scales_up_builds_pushes_and_scales_down() {
  ctx_buildkit_build services/bff/Dockerfile "" registry.example.com/ctx/bff:ws-abc
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "-n contexture-build scale deployment/buildkitd --replicas=1"
  assert_contains "$calls" "--addr kube-pod://buildkitd-abc?namespace=contexture-build&context=ctx-cloud"
  assert_contains "$calls" "--opt filename=Dockerfile"
  assert_contains "$calls" "--local dockerfile=$REPO_ROOT/services/bff"
  assert_contains "$calls" "--local context=$REPO_ROOT"
  assert_contains "$calls" "name=registry.example.com/ctx/bff:ws-abc,push=true"
  assert_contains "$calls" "KUBECONFIG=/k/doks.yaml"
  assert_contains "$(stub_calls | tail -1)" "--replicas=0"
}

test_target_stage_is_passed_when_given() {
  ctx_buildkit_build apps/web/Dockerfile dev registry.example.com/ctx/web-dev:dev-1
  assert_contains "$(stub_calls)" "--opt target=dev"
}

test_push_credentials_come_from_a_temporary_docker_config() {
  ctx_buildkit_build services/bff/Dockerfile "" registry.example.com/ctx/bff:x
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "registry.example.com"
  assert_contains "$calls" "$(printf 'contexture:write-token' | base64 -w0)"
  local dir; dir=$(sed -nE 's/.*DOCKER_CONFIG=([^ ]+).*/\1/p' <<< "$calls" | head -1)
  [[ ! -e $dir ]] || fail "临时 DOCKER_CONFIG 未删除：$dir"
}

test_failed_build_returns_nonzero_and_still_scales_down() {
  BUILD_STATUS=1
  assert_status 1 ctx_buildkit_build services/bff/Dockerfile "" registry.example.com/ctx/bff:x
  assert_contains "$(stub_calls | tail -1)" "--replicas=0"
}

test_missing_write_token_is_a_config_error() {
  CTX_CLOUD_REGISTRY_WRITE_TOKEN=
  assert_status 2 ctx_buildkit_build services/bff/Dockerfile "" registry.example.com/ctx/bff:x
}
