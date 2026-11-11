#!/usr/bin/env bash
# make cloud-info（030 FR-029）：各组件的云端地址、登录方式与凭证位置（只给出 Secret 名与键，不输出凭证值）。
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "$HERE/common.sh"

ctx_info_main() {
  ctx_load_config
  local d=$CTX_CLOUD_DOMAIN ns=$CTX_CLOUD_NAMESPACE
  local get="kubectl --kubeconfig $CTX_CLOUD_KUBECONFIG --context $CTX_CLOUD_CONTEXT -n $ns get secret"
  cat <<INFO

织境云端环境（$d）
  织境 Web               https://$d                 测试用户 user1 / engineer1 / admin1（密码同用户名）
  OpenMetadata           https://om.$d              Keycloak 登录（admin1 为 OM 管理员）
  Langfuse（决策轨迹）   https://langfuse.$d        admin@contexture.local；密码：Secret langfuse-init 键 admin-password
  Airflow                https://airflow.$d         openmetadata；密码：Secret om-secrets 键 airflow-password
  Jaeger（服务追踪）     https://jaeger.$d          无登录（公网开放，只放模拟数据）
  Prometheus（指标）     https://prometheus.$d      无登录（同上）
  OpenSearch Dashboards  https://dashboards.$d      无登录（同上）；日志索引 ctx-logs
  AI 网关管理界面        https://gateway-admin.$d/ui/   无登录（同上）
  Keycloak 管理          https://sso.$d/admin/      admin；密码：Secret keycloak-keycloak-admin 键 password

读取某个密码（只在你的终端显示）：
  $get <Secret 名> -o jsonpath='{.data.<键>}' | base64 -d; echo
INFO
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  set -euo pipefail
  ctx_info_main "$@"
fi
