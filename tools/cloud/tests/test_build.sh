#!/usr/bin/env bash
# T061：cloud-build（FR-022；US5 场景 1、5；R11：开发模式中先结束再部署）
source "$REPO_ROOT/tools/cloud/build.sh"
stub_log_init
STATE_DEV=false
ctx_load_config() { CTX_CLOUD_REGISTRY=registry.example.com/ctx CTX_CLOUD_NAMESPACE=contexture; }
ctx_tag_workspace() { echo ws-0123456789ab-deadbeef; }
ctx_workspace_dirty() { return 0; }
ctx_state_get() { case $1 in devMode.active) echo "$STATE_DEV" ;; stableVersion.webTag) echo git-aaaaaaaaaaaa ;; stableVersion.bffTag) echo git-aaaaaaaaaaaa ;; esac; }
ctx_state_set() { stub_record "state $*"; }
ctx_buildkit_build() { stub_record "build $*"; return "${BUILD_STATUS:-0}"; }
ctx_helmfile() { stub_record "helmfile $* BFF=$CTX_CLOUD_BFF_TAG WEB=$CTX_CLOUD_WEB_TAG"; }
ctx_dev_reset() { stub_record "dev-reset"; }

test_bff_only_builds_bff_and_keeps_stable_web() {
  ctx_build_main bff >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "build services/bff/Dockerfile  registry.example.com/ctx/bff:ws-0123456789ab-deadbeef"
  assert_not_contains "$calls" "apps/web/Dockerfile"
  assert_contains "$calls" "BFF=ws-0123456789ab-deadbeef WEB=git-aaaaaaaaaaaa"
  assert_contains "$calls" "stableVersion.source=workspace"
  assert_contains "$calls" "stableVersion.dirty=true"
  assert_contains "$calls" "stableVersion.commit=0123456789ab"
}

test_all_builds_both() {
  ctx_build_main all >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "services/bff/Dockerfile"
  assert_contains "$calls" "apps/web/Dockerfile"
  assert_contains "$calls" "BFF=ws-0123456789ab-deadbeef WEB=ws-0123456789ab-deadbeef"
}

test_never_builds_openmetadata_images() {
  assert_status 2 ctx_build_main openmetadata
  assert_contains "$OUTPUT" "流水线"
  ctx_build_main all >/dev/null
  assert_not_contains "$(stub_calls)" "openmetadata"
}

test_failed_build_does_not_deploy_or_record() {
  BUILD_STATUS=1
  assert_status 1 ctx_build_main bff
  assert_not_contains "$(stub_calls)" "helmfile"
  assert_not_contains "$(stub_calls)" "state"
}

test_dev_and_toolbox_images_are_built_without_deploying() {
  ctx_build_main --dev >/dev/null
  ctx_build_main --toolbox >/dev/null
  local calls; calls=$(stub_calls)
  assert_contains "$calls" "build services/bff/Dockerfile dev registry.example.com/ctx/bff-dev:dev-"
  assert_contains "$calls" "build apps/web/Dockerfile dev registry.example.com/ctx/web-dev:dev-"
  assert_contains "$calls" "build deploy/components/ci-toolbox/Dockerfile  registry.example.com/ctx/toolbox:toolbox-"
  assert_contains "$calls" "state toolboxImage=registry.example.com/ctx/toolbox:toolbox-"
  assert_not_contains "$calls" "helmfile"
}

test_dev_mode_is_ended_before_deploying_a_build() {
  STATE_DEV=true
  CONFIRM=yes ctx_build_main bff >/dev/null
  local calls; calls=$(stub_calls)
  [[ $(grep -n dev-reset <<< "$calls" | cut -d: -f1) -lt $(grep -n helmfile <<< "$calls" | cut -d: -f1) ]] ||
    fail "须先结束开发模式再部署"
}
