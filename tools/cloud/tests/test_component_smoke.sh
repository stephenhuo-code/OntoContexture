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
  assert_not_contains "$(run_airflow_smoke contexture/openmetadata-ingestion-airflow:2.0.3-ctx.0)" "不是织境采集镜像"
}

test_airflow_smoke_accepts_registry_prefixed_image() {
  local out; out=$(run_airflow_smoke registry.example.com/team/openmetadata-ingestion-airflow:2.0.3-ctx.0)
  assert_contains "$out" "airflow OK"
  assert_not_contains "$out" "不是织境采集镜像"
}

test_airflow_smoke_rejects_upstream_image() {
  assert_contains "$(run_airflow_smoke apache/airflow:3.3.2)" "不是织境采集镜像"
}
