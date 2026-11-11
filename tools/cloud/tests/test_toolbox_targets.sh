#!/usr/bin/env bash
# T064：集群内检查与测试命令（FR-015、FR-018、FR-026、FR-029；clarify Q3：清空 / 重建数据前须确认）
source "$REPO_ROOT/tools/cloud/toolbox.sh"
stub_log_init
ctx_load_config() { CTX_CLOUD_NAMESPACE=contexture CTX_CLOUD_CONTEXT=ctx CTX_CLOUD_KUBECONFIG=/k CTX_CLOUD_NODE_LABEL=l CTX_CLOUD_NODE_POOL=p; }
ctx_toolbox_run() { stub_record "toolbox: $1"; return "${RUN_STATUS:-0}"; }
ctx_ensure_secrets() { stub_record "secrets"; }
ctx_helmfile() { stub_record "helmfile $*"; }
ctx_mock_secrets() { stub_record "mock-secrets"; }
ctx_mock_smoke() { stub_record "mock-smoke"; }

test_lint_runs_make_lint_with_dependencies() {
  ctx_toolbox_main lint >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "uv sync --all-packages --frozen"
  assert_contains "$c" "pnpm install --frozen-lockfile"
  assert_contains "$c" "make lint"
}

test_test_runs_python_web_and_bash_coverage() {
  ctx_toolbox_main test >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "make test"
  assert_contains "$c" "test:coverage"
  assert_contains "$c" "CTX_KCOV=1 make cloud-unit"
}

test_e2e_targets_cloud_environment_without_kind_context() {
  ctx_toolbox_main e2e >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "pytest -m cluster"
  assert_contains "$c" "tests/cloud"
  assert_contains "$c" "pnpm e2e:browser"
  assert_contains "$c" "CTX_KUBE_CONTEXT="
  assert_not_contains "$c" "kind-contexture"
}

test_seed_and_e2e_need_no_confirmation() {
  CONFIRM= ctx_toolbox_main seed >/dev/null
  CONFIRM= ctx_toolbox_main e2e >/dev/null
  assert_contains "$(stub_calls)" "tools.seed"
}

test_mock_data_lists_databases_and_requires_confirmation() {
  CONFIRM= assert_status 3 ctx_toolbox_main mock-data
  assert_contains "$OUTPUT" "mes"
  assert_contains "$OUTPUT" "qms"
  assert_contains "$OUTPUT" "mock_dw"
  [[ -z $(stub_calls | grep -E 'toolbox:|helmfile') ]] || fail "未确认时不应有任何动作"
}

test_confirmed_mock_data_deploys_sources_then_loads_in_toolbox() {
  CONFIRM=yes ctx_toolbox_main mock-data >/dev/null
  local c; c=$(stub_calls)
  assert_contains "$c" "helmfile -l group=mock-sources sync --skip-needs"
  assert_contains "$c" "mockfactory load --target local"
  assert_contains "$c" "mockfactory verify-cases --target local"
  assert_contains "$c" "mockfactory provision-005"
  [[ $(grep -n helmfile <<< "$c" | cut -d: -f1) -lt $(grep -n 'mockfactory load' <<< "$c" | cut -d: -f1) ]] || fail "须先部署模拟库"
}

test_exit_status_of_toolbox_is_passed_through() {
  RUN_STATUS=5
  assert_status 5 ctx_toolbox_main test
}

test_unknown_target_is_a_config_error() {
  assert_status 2 ctx_toolbox_main deploy
}

# 变更行覆盖率默认比较 HEAD（工作区未提交改动）；验收整个特性分支时传 DIFF_BASE=main（T068）
test_test_passes_diff_base_to_coverage_gate() {
  DIFF_BASE=main ctx_toolbox_main test >/dev/null
  assert_contains "$(stub_calls)" "make coverage-check DIFF_BASE=main"
}

test_test_defaults_coverage_base_to_head() {
  env -u DIFF_BASE bash -c 'true'
  unset DIFF_BASE
  ctx_toolbox_main test >/dev/null
  assert_contains "$(stub_calls)" "make coverage-check DIFF_BASE=HEAD"
}
