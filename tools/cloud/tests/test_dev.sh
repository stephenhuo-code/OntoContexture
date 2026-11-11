#!/usr/bin/env bash
# T069：cloud-dev / cloud-dev-reset（FR-011～FR-014、R11、R18）
source "$REPO_ROOT/tools/cloud/dev.sh"
stub_log_init
STATE_LIFECYCLE=running READY=1 DEV_IMAGE_RECORDED=yes
ctx_load_config() { CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_REGISTRY=registry.example.com/ctx CTX_CLOUD_DOMAIN=ctx.example.com
  CTX_CLOUD_CONTEXT=ctx CTX_CLOUD_KUBECONFIG=/k; }
ctx_state_get() {
  case $1 in
    lifecycle.state) echo "$STATE_LIFECYCLE" ;;
    devImage.bff | devImage.web) [[ $DEV_IMAGE_RECORDED == yes ]] && ctx_dev_image "${1#devImage.}" ;;
  esac
}
ctx_state_set() { stub_record "state $*"; }
ctx_kubectl() { case "$*" in *"readyReplicas"*) echo "$READY" ;; *) stub_record "kubectl $*" ;; esac; }
ctx_build_dev_images() { stub_record "build-dev"; }
devspace() { stub_record "devspace $* BFF=${CTX_DEV_BFF_IMAGE:-} WEB=${CTX_DEV_WEB_IMAGE:-}"; return "${DEVSPACE_STATUS:-0}"; }

test_refuses_when_environment_is_not_running() {
  STATE_LIFECYCLE=stopped
  assert_status 2 ctx_dev_main all
  assert_contains "$OUTPUT" "cloud-start"
  READY=0 STATE_LIFECYCLE=running
  assert_status 2 ctx_dev_main all
}

test_marks_dev_mode_runs_devspace_and_restores_on_exit() {
  ctx_dev_main all >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "state devMode.active=true"
  assert_contains "$c" "devspace dev"
  assert_contains "$c" "--config $REPO_ROOT/deploy/cloud/devspace.yaml"
  assert_contains "$c" "-n contexture"
  assert_contains "$c" "BFF=registry.example.com/ctx/bff-dev:dev-"
  assert_contains "$c" "devspace reset pods"
  assert_contains "$(stub_calls | tail -1)" "devMode.active=false"
}

test_restores_even_when_devspace_fails_or_is_interrupted() {
  DEVSPACE_STATUS=130
  ctx_dev_main all >/dev/null || true
  assert_contains "$(stub_calls)" "devspace reset pods"
  assert_contains "$(stub_calls | tail -1)" "devMode.active=false"
}

test_target_selects_profile() {
  ctx_dev_main bff >/dev/null
  assert_contains "$(stub_calls)" "-p bff-only"
  stub_log_init
  ctx_dev_main web >/dev/null
  assert_contains "$(stub_calls)" "-p web-only"
}

test_missing_dev_images_are_built_first() {
  DEV_IMAGE_RECORDED=no
  ctx_dev_main all >/dev/null
  local c; c=$(stub_calls)
  [[ $(grep -n build-dev <<< "$c" | cut -d: -f1) -lt $(grep -n 'devspace dev' <<< "$c" | cut -d: -f1) ]] ||
    fail "须先构建开发镜像"
}

test_reset_works_without_local_process() {
  ctx_dev_main reset >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "devspace reset pods"
  assert_contains "$c" "devMode.active=false"
  assert_not_contains "$c" "devspace dev"
}

# T075 实测：devspace.yaml 的变量取自环境，缺少时连配置都无法加载（“couldn't find environment variable CTX_DEV_WEB_IMAGE”），
# 单独执行 cloud-dev-reset（及开发模式异常退出后的恢复）全部失败。reset 须自行提供这些变量
test_reset_provides_variables_needed_to_load_devspace_config() {
  unset CTX_DEV_BFF_IMAGE CTX_DEV_WEB_IMAGE
  ctx_dev_main reset >/dev/null
  local line; line=$(stub_calls | grep "devspace reset pods" | head -1)
  [[ $line != *"BFF= "* && $line != *"WEB=" ]] || fail "reset 未提供开发镜像变量：$line"
}

# T075 实测：devspace 自行退出（如同步连接中断）后，清理中 kill 已退出的进程失败，set -e 使脚本在恢复稳定版本前退出，
# 环境停留在开发模式。在独立的 bash -e 进程中验证（run.sh 在 if 中执行测试函数，set -e 不生效）
test_cleanup_restores_even_when_devspace_has_already_exited() {
  local out
  out=$(bash -ec 'source "$1/tools/cloud/dev.sh"
    ctx_dev_reset() { echo reset-called; }
    (exit 0) & CTX_DEV_PID=$!; wait "$CTX_DEV_PID"; CTX_DEV_WATCHER=$CTX_DEV_PID CTX_DEV_CLEANED=
    ctx_dev_cleanup' _ "$REPO_ROOT" 2>&1) || true
  assert_contains "$out" "reset-called"
}
