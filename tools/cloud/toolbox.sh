#!/usr/bin/env bash
# make cloud-lint / cloud-test / cloud-e2e / cloud-seed / cloud-mock-data（030 US3）：在集群内工具箱中对开发机当前工作区运行，
# 输出实时显示、退出码透传（FR-015～FR-018）。重建模拟数据会清空 mes / qms / mock_dw，须确认（FR-026，clarify Q3）。
# 用法：tools/cloud/toolbox.sh <lint|test|e2e|seed|mock-data>
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"
source "$HERE/secrets.sh"
source "$HERE/lib/tags.sh"
source "$HERE/lib/state.sh"
source "$HERE/lib/toolbox.sh"

CTX_PREPARE="git config --global --add safe.directory /workspace && uv sync --all-packages --frozen >/dev/null && pnpm install --frozen-lockfile --reporter=silent"
# 工具箱在集群内使用自身的 ServiceAccount：模拟数据工具不指定 kube 上下文；kubectl 默认 namespace 与本地一致
CTX_IN_CLUSTER="export CTX_KUBE_CONTEXT=; "

ctx_mock_secrets() {
  KUBECONFIG=$CTX_CLOUD_KUBECONFIG KUBE_CONTEXT=$CTX_CLOUD_CONTEXT "$CTX_REPO_ROOT/testdata/deploy/secrets.sh"
}
ctx_mock_smoke() {
  local kube t; kube=$(mktemp); chmod 600 "$kube"
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" --context "$CTX_CLOUD_CONTEXT" config view --minify --flatten --raw > "$kube"
  for t in "$CTX_REPO_ROOT"/testdata/deploy/*/tests/smoke.sh; do
    KUBECONFIG=$kube KUBE_CONTEXT=$CTX_CLOUD_CONTEXT CTX_NODE_SELECTOR="$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" "$t" ||
      { rm -f "$kube"; return 1; }
  done
  rm -f "$kube"
}

ctx_toolbox_main() {
  local target=${1:-}
  ctx_load_config
  case $target in
    lint) ctx_toolbox_run "$CTX_PREPARE && make lint" ;;
    test)
      ctx_toolbox_run "$CTX_PREPARE && make test && pnpm --filter @contexture/web test:coverage && \
        pnpm --filter @contexture/ui test:coverage && CTX_KCOV=1 make cloud-unit && make coverage-check DIFF_BASE=${DIFF_BASE:-HEAD}" ;;
    e2e)
      ctx_toolbox_run "$CTX_PREPARE && ${CTX_IN_CLUSTER}pnpm exec playwright install chromium >/dev/null && \
        uv run pytest -m cluster -o addopts='--import-mode=importlib' deploy/components tests/e2e tests/cloud && \
        CTX_WRONG_AUDIENCE_TOKEN=\$(PYTHONPATH=tests uv run python tests/e2e/wrong_audience_token.py) pnpm e2e:browser && \
        pnpm e2e:ui" ;;
    seed) ctx_toolbox_run "$CTX_PREPARE && ${CTX_IN_CLUSTER}uv run python -m tools.seed" ;;
    mock-data)
      ctx_confirm "将清空并重建模拟数据：MES（MySQL 库 mes）、QMS（PostgreSQL 库 qms）、数仓（Doris 库 mock_dw），并重置 005 的只读账号与 viewlab。"
      ctx_mock_secrets
      ctx_helmfile -l group=mock-sources sync --skip-needs || exit "$CTX_EXIT_FAILED"
      ctx_mock_smoke || exit "$CTX_EXIT_FAILED"
      ctx_toolbox_run "$CTX_PREPARE && ${CTX_IN_CLUSTER}\
        uv run python -m mockfactory load --target local --months ${MONTHS:-12} --seed ${SEED:-20261001} && \
        uv run python -m mockfactory verify-cases --target local && uv run python -m mockfactory provision-005" ;;
    *) ctx_die "$CTX_EXIT_CONFIG" "用法：tools/cloud/toolbox.sh <lint|test|e2e|seed|mock-data>" ;;
  esac
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_toolbox_main "$@"
fi
