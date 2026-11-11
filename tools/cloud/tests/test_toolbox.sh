#!/usr/bin/env bash
# T034：集群内工具箱运行封装（FR-015、FR-016、R12、R18）
source "$REPO_ROOT/tools/cloud/common.sh"
source "$REPO_ROOT/tools/cloud/lib/tags.sh"
source "$REPO_ROOT/tools/cloud/lib/state.sh"
source "$REPO_ROOT/tools/cloud/lib/toolbox.sh"
stub_log_init
CTX_CLOUD_KUBECONFIG=/k/doks.yaml CTX_CLOUD_CONTEXT=ctx-cloud CTX_CLOUD_NAMESPACE=contexture
CTX_CLOUD_REGISTRY=registry.example.com/ctx CTX_CLOUD_NODE_LABEL=example.com/pool CTX_CLOUD_NODE_POOL=elastic
UPLOAD=$(mktemp)
ctx_kubectl() {
  stub_record "kubectl $*"
  case "$*" in
    *"apply -f -"*) cat > "$STUB_LOG.manifest" ;;
    *"exec -i"*"tar"*) cat > "$UPLOAD" ;;
    *"exec "*"-- bash -lc"*"sleep"*) sleep 3 ;;
    *"exec "*"-- bash -lc"*) echo "running: ${*: -1}"; return "${RUN_STATUS:-0}" ;;
    *"exec "*"cat /workspace/coverage/bash/cobertura.xml"*) echo "<coverage/>" ;;
  esac
}

test_uploads_tracked_and_untracked_files_but_not_env_files() {
  ctx_toolbox_run "make test" >/dev/null
  local files; files=$(tar tzf "$UPLOAD")
  assert_contains "$files" "Makefile"
  assert_contains "$files" "tools/cloud/common.sh"
  assert_not_contains "$files" ".env.cloud
"
  while read -r f; do
    [[ $f =~ (^|/)\.env(\.[a-z]+)?$ ]] && fail "上传了凭证文件 $f"
  done <<< "$files"
  true
}

test_command_output_and_exit_status_are_passed_through() {
  RUN_STATUS=7
  local out status=0
  out=$(ctx_toolbox_run "make test") || status=$?
  assert_eq 7 "$status"
  assert_contains "$out" "running: cd /workspace && make test"
}

test_residual_pod_is_removed_before_start_and_pod_deleted_after() {
  ctx_toolbox_run "true" >/dev/null
  local calls; calls=$(stub_calls)
  local first_delete apply_line last
  first_delete=$(grep -n "delete pod contexture-toolbox" <<< "$calls" | head -1 | cut -d: -f1)
  apply_line=$(grep -n "apply -f -" <<< "$calls" | head -1 | cut -d: -f1)
  [[ $first_delete -lt $apply_line ]] || fail "启动前未清理残留 Pod"
  last=$(tail -1 <<< "$calls")
  assert_contains "$last" "delete pod contexture-toolbox"
}

test_interrupt_deletes_pod() {
  # 后台子 shell 会忽略 SIGINT，这里用 SIGTERM 模拟中断（交互式 Ctrl+C 走同一个 trap）
  ( ctx_toolbox_run "sleep 1" >/dev/null & pid=$!; sleep 0.5; kill -TERM $pid; wait $pid ) || true
  assert_contains "$(stub_calls | tail -1)" "delete pod contexture-toolbox"
}

test_manifest_injects_credentials_only_via_secret_and_runs_dind_sidecar() {
  ctx_toolbox_run "true" >/dev/null
  local m; m=$(cat "$STUB_LOG.manifest")
  assert_contains "$m" '"secretRef":{"name":"toolbox-env"}'
  assert_contains "$m" '"image":"docker:29.9.1-dind"'
  assert_contains "$m" '"privileged":true'
  assert_contains "$m" '"serviceAccountName":"toolbox"'
  assert_contains "$m" '"example.com/pool":"elastic"'
  assert_contains "$m" '"imagePullSecrets":[{"name":"docr-pull"}]'
}

test_kcov_report_is_fetched_when_requested() {
  local d; d=$(tmpdir)
  CTX_KCOV=1 CTX_KCOV_OUT=$d/cobertura.xml ctx_toolbox_run "make cloud-unit" >/dev/null
  assert_eq "<coverage/>" "$(cat "$d/cobertura.xml")"
}

test_git_metadata_is_uploaded_for_coverage_diff() {
  ctx_toolbox_run "true" >/dev/null
  assert_contains "$(tar tzf "$UPLOAD")" ".git/HEAD"
}

# T068 实测：Testcontainers 把工作区内的路径绑定挂载进容器（如 keycloak-config-cli 的 /config），而 Docker 守护进程在 dind 边车中，
# 看不到工具箱容器的文件系统，挂载结果为空目录。工作区须以相同路径挂入 dind
test_dind_sidecar_sees_workspace_at_same_path() {
  local m; m=$(ctx_toolbox_manifest)
  assert_eq "/workspace" "$(jq -r '.spec.containers[] | select(.name == "dind") | .volumeMounts[] | select(.name == "workspace") | .mountPath' <<< "$m")"
}

# T068 实测：测试夹具在临时目录（/tmp）生成文件再绑定挂载（如 Keycloak 登录主题），/tmp 也须与 dind 共享
test_dind_sidecar_shares_tmp() {
  local m; m=$(ctx_toolbox_manifest)
  assert_eq "/tmp" "$(jq -r '.spec.containers[] | select(.name == "dind") | .volumeMounts[] | select(.name == "tmp") | .mountPath' <<< "$m")"
  assert_eq "/tmp" "$(jq -r '.spec.containers[] | select(.name == "toolbox") | .volumeMounts[] | select(.name == "tmp") | .mountPath' <<< "$m")"
}
