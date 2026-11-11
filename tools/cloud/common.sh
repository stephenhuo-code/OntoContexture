#!/usr/bin/env bash
# 云端命令公共库（030）：读取并校验 .env.cloud，所有集群操作固定到配置中的 kubeconfig / 上下文 / namespace，
# 不读写 kubeconfig 的当前上下文（FR-001a、FR-002、FR-004、FR-005）。约定见 specs/030-doks-deploy/contracts/。
# 用法：source tools/cloud/common.sh; ctx_load_config

CTX_REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
CTX_LOG_DIR="$HOME/.cache/contexture/logs"   # 持久卷，开发机重建后仍在（R18）

# 退出码（contracts/cloud-commands.md）
readonly CTX_EXIT_FAILED=1 CTX_EXIT_CONFIG=2 CTX_EXIT_UNCONFIRMED=3 CTX_EXIT_TIMEOUT=4 2>/dev/null || true

CTX_CONFIG_KEYS=(CTX_CLOUD_KUBECONFIG CTX_CLOUD_CONTEXT CTX_CLOUD_NAMESPACE CTX_CLOUD_NODE_LABEL CTX_CLOUD_NODE_POOL
  CTX_CLOUD_STORAGE_CLASS CTX_CLOUD_DOMAIN CTX_CLOUD_ACME_EMAIL CTX_CLOUD_ACME_SERVER CTX_CLOUD_REGISTRY
  CTX_CLOUD_REGISTRY_READ_TOKEN CTX_CLOUD_REGISTRY_WRITE_TOKEN)
CTX_REQUIRED_KEYS=(CTX_CLOUD_KUBECONFIG CTX_CLOUD_CONTEXT CTX_CLOUD_NODE_LABEL CTX_CLOUD_NODE_POOL
  CTX_CLOUD_STORAGE_CLASS CTX_CLOUD_DOMAIN CTX_CLOUD_ACME_EMAIL CTX_CLOUD_REGISTRY CTX_CLOUD_REGISTRY_READ_TOKEN)

ctx_log() { printf '\n==> %s\n' "$*"; }
ctx_die() {  # ctx_die <退出码> <消息>
  local code=$1; shift
  printf '错误：%s\n' "$*" >&2
  exit "$code"
}

# 读取并校验配置；出错时以退出码 2 退出，且不回显任何令牌值
ctx_load_config() {
  local file=${1:-${CTX_CLOUD_ENV_FILE:-$CTX_REPO_ROOT/.env.cloud}}
  [[ -f $file ]] || ctx_die "$CTX_EXIT_CONFIG" "找不到 $file；请从 .env.cloud.example 复制并填写"
  local key
  for key in "${CTX_CONFIG_KEYS[@]}" MODEL_HOST MODEL_NAME MODEL_API_KEY; do unset "$key"; done
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
  CTX_CLOUD_NAMESPACE=${CTX_CLOUD_NAMESPACE:-contexture}
  CTX_CLOUD_ACME_SERVER=${CTX_CLOUD_ACME_SERVER:-production}
  export CTX_CLOUD_NAMESPACE CTX_CLOUD_ACME_SERVER

  for key in "${CTX_REQUIRED_KEYS[@]}"; do
    [[ -n ${!key:-} ]] || ctx_die "$CTX_EXIT_CONFIG" "$file 缺少必填项 $key"
  done
  [[ -f $CTX_CLOUD_KUBECONFIG ]] || ctx_die "$CTX_EXIT_CONFIG" "CTX_CLOUD_KUBECONFIG 指向的文件不存在：$CTX_CLOUD_KUBECONFIG"
  [[ $(stat -c %a "$CTX_CLOUD_KUBECONFIG") == 600 ]] ||
    ctx_die "$CTX_EXIT_CONFIG" "kubeconfig 权限必须为 600：chmod 600 $CTX_CLOUD_KUBECONFIG"
  ctx_valid_domain "$CTX_CLOUD_DOMAIN" ||
    ctx_die "$CTX_EXIT_CONFIG" "CTX_CLOUD_DOMAIN 不是可用的公网域名：$CTX_CLOUD_DOMAIN"
  [[ $CTX_CLOUD_ACME_SERVER == staging || $CTX_CLOUD_ACME_SERVER == production ]] ||
    ctx_die "$CTX_EXIT_CONFIG" "CTX_CLOUD_ACME_SERVER 只能是 staging 或 production"
  [[ $CTX_CLOUD_ACME_EMAIL == *@*.* ]] || ctx_die "$CTX_EXIT_CONFIG" "CTX_CLOUD_ACME_EMAIL 格式不对"
  [[ $CTX_CLOUD_NAMESPACE =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] ||
    ctx_die "$CTX_EXIT_CONFIG" "CTX_CLOUD_NAMESPACE 不符合 DNS-1123：$CTX_CLOUD_NAMESPACE"
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" config get-contexts -o name 2>/dev/null | grep -qx "$CTX_CLOUD_CONTEXT" ||
    ctx_die "$CTX_EXIT_CONFIG" "kubeconfig 中没有上下文 $CTX_CLOUD_CONTEXT"
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" --context "$CTX_CLOUD_CONTEXT" get --raw /version >/dev/null 2>&1 ||
    ctx_die "$CTX_EXIT_CONFIG" "无法访问集群（上下文 $CTX_CLOUD_CONTEXT）；kubeconfig 令牌可能已过期"
  mkdir -p "$CTX_LOG_DIR"
}

ctx_valid_domain() {
  local domain=$1
  [[ $domain =~ ^([a-z0-9]([-a-z0-9]*[a-z0-9])?\.)+[a-z]{2,}$ ]] || return 1
  case $domain in
    localhost | *.localhost | *.nip.io | *.sslip.io | *.local | *.internal) return 1 ;;
  esac
}

# 固定上下文的命令封装：调用方传入的 -n 写在后面，会覆盖默认 namespace
ctx_kubectl() {
  kubectl --kubeconfig "$CTX_CLOUD_KUBECONFIG" --context "$CTX_CLOUD_CONTEXT" --namespace "$CTX_CLOUD_NAMESPACE" "$@"
}
ctx_helm() {
  helm --kubeconfig "$CTX_CLOUD_KUBECONFIG" --kube-context "$CTX_CLOUD_CONTEXT" --namespace "$CTX_CLOUD_NAMESPACE" "$@"
}
# helmfile 不传 --namespace：各 release 在 helmfile 中自带 namespace
ctx_helmfile() {
  KUBECONFIG=$CTX_CLOUD_KUBECONFIG helmfile --kube-context "$CTX_CLOUD_CONTEXT" \
    -f "$CTX_REPO_ROOT/deploy/helmfile.yaml.gotmpl" -e cloud "$@"
}

# 确认：交互式终端输入 yes；非交互时需 CONFIRM=yes；否则退出码 3
ctx_confirm() {
  local message=$1 answer=
  [[ ${CONFIRM:-} == yes ]] && return 0
  if [[ -t 0 ]]; then
    printf '%s\n输入 yes 继续：' "$message"
    read -r answer
    [[ $answer == yes ]] && return 0
  else
    printf '%s\n非交互环境请设置 CONFIRM=yes\n' "$message" >&2
  fi
  ctx_die "$CTX_EXIT_UNCONFIRMED" "未确认，未做任何改动"
}
