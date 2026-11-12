#!/usr/bin/env bash
# 组件冒烟测试在云端的镜像名：云端镜像带仓库前缀（如 registry.example.com/team/），不得只认本地的 contexture/ 前缀（FR-027）

# 假 kubectl：exec 一律返回健康；镜像查询返回 $FAKE_IMAGE；其余成功且无输出
fake_kubectl_path() {
  local dir; dir=$(tmpdir)
  cat > "$dir/kubectl" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"containers[0].image"*) echo "$FAKE_IMAGE" ;;
  *exec*) echo '{"scheduler": {"status": "healthy"}, "status": "healthy"}' ;;
esac
exit 0
SH
  chmod +x "$dir/kubectl"
  printf '%s' "$dir"
}

run_airflow_smoke() {  # 只关心镜像检查；之后的步骤在假 kubectl 下的结果不作断言
  PATH="$(fake_kubectl_path):$PATH" FAKE_IMAGE=$1 bash "$REPO_ROOT/deploy/components/airflow/tests/smoke.sh" 2>&1 || true
}

test_airflow_smoke_accepts_local_image() {
  assert_not_contains "$(run_airflow_smoke contexture/openmetadata-ingestion-airflow:2.0.3-ctx.1)" "不是织境采集镜像"
}

test_airflow_smoke_accepts_registry_prefixed_image() {
  local out; out=$(run_airflow_smoke registry.example.com/team/openmetadata-ingestion-airflow:2.0.3-ctx.1)
  assert_contains "$out" "airflow OK"
  assert_not_contains "$out" "不是织境采集镜像"
}

test_airflow_smoke_rejects_upstream_image() {
  assert_contains "$(run_airflow_smoke apache/airflow:3.3.2)" "不是织境采集镜像"
}

# 云端专用组件（cert-manager、buildkit、ci-toolbox）的冒烟测试：本地 make up 也会遍历，须在非云端环境跳过，不访问集群
fake_recording_path() {  # kubectl / curl 记录调用；curl 按 URL 返回预期内容
  local dir; dir=$(tmpdir)
  printf '#!/usr/bin/env bash\necho "kubectl $*" >> "$STUB_LOG"\n' > "$dir/kubectl"
  cat > "$dir/curl" <<'SH'
#!/usr/bin/env bash
echo "curl $*" >> "$STUB_LOG"
case "$*" in
  *"%{redirect_url}"*) echo "https://sso.example/realms/x/protocol/openid-connect/auth" ;;
  *"%{http_code}"*) echo 401 ;;
  *) echo '<div id="root">' ;;
esac
SH
  chmod +x "$dir/kubectl" "$dir/curl"
  printf '%s' "$dir"
}

test_cloud_only_smoke_tests_skip_outside_cloud() {
  stub_log_init
  local c out p; p=$(fake_recording_path)
  for c in cert-manager buildkit ci-toolbox; do
    out=$(env -u CTX_ENV PATH="$p:$PATH" bash "$REPO_ROOT/deploy/components/$c/tests/smoke.sh") || fail "$c 非云端应跳过并成功"
    assert_contains "$out" "跳过" "$c"
  done
  assert_eq "" "$(stub_calls)" "非云端不应访问集群"
}

test_cloud_only_smoke_tests_run_in_cloud() {
  stub_log_init
  local c; c=$(fake_recording_path)
  CTX_ENV=cloud PATH="$c:$PATH" bash "$REPO_ROOT/deploy/components/cert-manager/tests/smoke.sh" >/dev/null
  assert_contains "$(stub_calls)" "kubectl -n contexture wait certificate/contexture"
}

test_bff_and_web_smoke_default_to_local_entry() {
  stub_log_init
  local p; p=$(fake_recording_path)
  env -u CTX_SMOKE_BASE_URL PATH="$p:$PATH" bash "$REPO_ROOT/deploy/charts/bff/tests/smoke.sh" >/dev/null
  env -u CTX_SMOKE_BASE_URL PATH="$p:$PATH" bash "$REPO_ROOT/deploy/charts/web/tests/smoke.sh" >/dev/null
  assert_contains "$(stub_calls)" "http://localhost:8080/bff/v1/me"
  assert_contains "$(stub_calls)" "http://localhost:8080/objects/equipment"
  assert_not_contains "$(stub_calls)" " -k "
}

test_bff_and_web_smoke_use_cloud_base_url_and_staging_insecure() {
  stub_log_init
  local p; p=$(fake_recording_path)
  CTX_SMOKE_BASE_URL=https://ctx.example.com CTX_SMOKE_INSECURE=1 PATH="$p:$PATH" \
    bash "$REPO_ROOT/deploy/charts/bff/tests/smoke.sh" >/dev/null
  CTX_SMOKE_BASE_URL=https://ctx.example.com CTX_SMOKE_INSECURE=1 PATH="$p:$PATH" \
    bash "$REPO_ROOT/deploy/charts/web/tests/smoke.sh" >/dev/null
  assert_contains "$(stub_calls)" "https://ctx.example.com/bff/v1/me"
  assert_contains "$(stub_calls)" "https://ctx.example.com/objects/equipment"
  assert_not_contains "$(stub_calls)" "localhost"
  assert_contains "$(stub_calls)" "-k"
}

# cloud-deploy 运行冒烟测试时传入环境标识、入口地址；staging 证书不受信任，允许跳过证书校验
deploy_smoke_env() {  # deploy_smoke_env <acme server>
  stub_log_init
  local root p; root=$(tmpdir); p=$(fake_recording_path)
  mkdir -p "$root/deploy/components/probe/tests"
  printf '#!/usr/bin/env bash\necho "env CTX_ENV=$CTX_ENV BASE=$CTX_SMOKE_BASE_URL INSECURE=${CTX_SMOKE_INSECURE:-}" >> "$STUB_LOG"\n' \
    > "$root/deploy/components/probe/tests/smoke.sh"
  chmod +x "$root/deploy/components/probe/tests/smoke.sh"
  (
    source "$REPO_ROOT/tools/cloud/deploy.sh"
    CTX_REPO_ROOT=$root CTX_LOG_DIR=$(tmpdir) CTX_CLOUD_DOMAIN=ctx.example.com CTX_CLOUD_ACME_SERVER=$1
    CTX_CLOUD_KUBECONFIG=/k CTX_CLOUD_CONTEXT=c CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_NODE_LABEL=l CTX_CLOUD_NODE_POOL=p
    PATH="$p:$PATH" ctx_run_smoke_tests >/dev/null
  )
  grep '^env ' "$STUB_LOG"
}

test_deploy_smoke_passes_cloud_env_and_domain() {
  assert_eq "env CTX_ENV=cloud BASE=https://ctx.example.com INSECURE=" "$(deploy_smoke_env production)"
}

test_deploy_smoke_allows_untrusted_staging_certificate() {
  assert_eq "env CTX_ENV=cloud BASE=https://ctx.example.com INSECURE=1" "$(deploy_smoke_env staging)"
}

# T068 实测：模拟源系统的冒烟测试以 KUBE_CONTEXT 选上下文（默认 kind-contexture），云端调用须传入云端上下文
test_mock_source_smoke_uses_cloud_context() {
  stub_log_init
  local root p; root=$(tmpdir); p=$(fake_recording_path)
  mkdir -p "$root/testdata/deploy/mes/tests"
  printf '#!/usr/bin/env bash\necho "ctx=${KUBE_CONTEXT:-unset}" >> "$STUB_LOG"\n' > "$root/testdata/deploy/mes/tests/smoke.sh"
  chmod +x "$root/testdata/deploy/mes/tests/smoke.sh"
  (
    source "$REPO_ROOT/tools/cloud/toolbox.sh"
    CTX_REPO_ROOT=$root CTX_CLOUD_KUBECONFIG=/k CTX_CLOUD_CONTEXT=do-cloud CTX_CLOUD_NODE_LABEL=l CTX_CLOUD_NODE_POOL=p
    PATH="$p:$PATH" ctx_mock_smoke
  )
  assert_contains "$(stub_calls)" "ctx=do-cloud"
}

# T082 实测：停止 / 启动后 Airflow 元数据库仍列出已删除文件的 DAG（e2e 与 ctx005_chain 测试的残留），冒烟误判为首轮遗留
fake_airflow_dags_path() {  # $FAKE_DAG_LIST：dags list 输出；$FAKE_DAG_FILES：dags 目录中的文件
  local dir; dir=$(tmpdir)
  cat > "$dir/kubectl" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"containers[0].image"*) echo "registry.example.com/team/openmetadata-ingestion-airflow:2.0.3-ctx.1" ;;
  *" logs smoke-"*) echo 000 ;;   # incluster curl 的输出：非授权 Pod 连不上 api-server
  *"dags list"*) printf 'dag_id fileloc\n%s\n' "$FAKE_DAG_LIST" ;;
  *"ls -1"*) printf '%s\n' "$FAKE_DAG_FILES" ;;
  *"dags_folder"*) echo /opt/airflow/dags ;;
  *"DAG_GENERATED_CONFIGS"*) echo /opt/airflow/dags/generated ;;
  *"claimName"*) echo "airflow-dags" ;;
  *"test ! -e"*) exit 0 ;;
  *exec*) echo '{"scheduler": {"status": "healthy"}, "status": "healthy"}' ;;
esac
exit 0
SH
  chmod +x "$dir/kubectl"
  printf '%s' "$dir"
}

test_airflow_smoke_ignores_stale_dag_records_without_files() {
  local out
  out=$(PATH="$(fake_airflow_dags_path):$PATH" FAKE_DAG_LIST="ctx005_chain_mes_metadata_3Y3LdvDY /opt/airflow/dags/ctx005_chain_mes_metadata_3Y3LdvDY.py" \
    FAKE_DAG_FILES="" bash "$REPO_ROOT/deploy/components/airflow/tests/smoke.sh" 2>&1) || fail "无文件的残留记录不应判失败：$out"
  assert_contains "$out" "no legacy dags OK"
}

test_airflow_smoke_still_rejects_first_round_dag_files() {
  local out
  out=$(PATH="$(fake_airflow_dags_path):$PATH" FAKE_DAG_LIST="" FAKE_DAG_FILES="metadata_mock_mes.py" \
    bash "$REPO_ROOT/deploy/components/airflow/tests/smoke.sh" 2>&1) && fail "首轮遗留 DAG 文件应判失败"
  assert_contains "$out" "存在首轮遗留 DAG"
}

# T082 实测：停止释放节点后，已完成的导入 Job 的 Pod 已被回收，kubectl logs 超时，冒烟误判失败
test_keycloak_smoke_accepts_completed_import_whose_pod_was_reclaimed() {
  local dir out; dir=$(tmpdir)
  cat > "$dir/kubectl" <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"get jobs"*) echo "job.batch/keycloak-import-abc" ;;
  *"wait"*) echo "job.batch/keycloak-import-abc condition met" ;;
  *"get pods"*) ;;
  *"logs"*) echo "error: timed out waiting for the condition" >&2; exit 1 ;;
esac
exit 0
SH
  chmod +x "$dir/kubectl"
  out=$(PATH="$dir:$PATH" bash "$REPO_ROOT/deploy/components/keycloak/tests/smoke.sh" 2>&1) || fail "Job 已完成应通过：$out"
  assert_contains "$out" "import OK"
}
