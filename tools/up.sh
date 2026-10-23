#!/usr/bin/env bash
# make up / make down：本地 kind 集群 + helmfile 部署全部组件，并运行各组件冒烟测试。
# 用法：tools/up.sh [up|down] [local|lite]
#   离线安装：CTX_OFFLINE_DIST=<离线包目录>（导入其中的镜像归档、使用其中的 Chart，不构建、不拉取）
#   集群名：CTX_KIND_CLUSTER（默认 contexture）
#   凭证来自 .env.local（Keycloak 导入用服务账号、bff 与 OM 的客户端密钥），见 specs/001-engineering-foundation/quickstart.md
set -euo pipefail
cd "$(dirname "$0")/.."

ACTION=${1:-up}
ENV=${2:-${CTX_ENV:-local}}
CLUSTER=${CTX_KIND_CLUSTER:-contexture}
OFFLINE=${CTX_OFFLINE_DIST:-}
NS=contexture

log() { printf '\n==> %s\n' "$*"; }

if [[ $ACTION == down ]]; then
  kind delete cluster --name "$CLUSTER"
  exit 0
fi

[[ -f .env.local ]] || { echo "缺少 .env.local（见 quickstart.md）"; exit 1; }
set -a; . ./.env.local; set +a

# ---------- 1. 集群 ----------
if ! kind get clusters | grep -qx "$CLUSTER"; then
  log "创建 kind 集群"
  kind create cluster --name "$CLUSTER" --config deploy/kind/cluster.yaml
fi
kubectl config use-context "kind-$CLUSTER" >/dev/null
kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

# ---------- 2. 接入本机 Keycloak（经 Paperclip 的 Caddy） ----------
log "集群内解析 Keycloak 域名、注入受信 CA"
HOST_IP=$(docker run --rm --network kind alpine:3.22 getent ahostsv4 host.docker.internal | awk 'NR==1{print $1}')
sed "s/HOST_GATEWAY_IP/${HOST_IP}/" deploy/kind/coredns-hosts.yaml | kubectl apply -f - >/dev/null
kubectl -n kube-system rollout restart deployment coredns >/dev/null
CA=$(mktemp); trap 'rm -f "$CA"' EXIT
docker exec paperclip-caddy-1 cat /data/caddy/pki/authorities/local/root.crt > "$CA"
kubectl -n "$NS" create secret generic ctx-trusted-ca --from-file=ca.crt="$CA" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# ---------- 3. Secret（已存在的不覆盖，避免密码变化） ----------
log "生成 Secret"
rand() { openssl rand -hex "${1:-16}"; }
fernet() { python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"; }
ensure() {  # ensure <名称> <kubectl create secret generic 的其余参数...>
  local name=$1; shift
  kubectl -n "$NS" get secret "$name" >/dev/null 2>&1 || kubectl -n "$NS" create secret generic "$name" "$@" >/dev/null
}
apply_secret() {  # 来自 .env.local 的凭证：每次以最新值覆盖
  local name=$1; shift
  kubectl -n "$NS" create secret generic "$name" "$@" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}
for db in openmetadata langfuse airflow bff; do
  ensure "pg-$db" --type=kubernetes.io/basic-auth --from-literal=username="$db" --from-literal=password="$(rand)"
done
pg_password() { kubectl -n "$NS" get secret "pg-$1" -o jsonpath='{.data.password}' | base64 -d; }
apply_secret keycloak-provisioner --from-literal=client-id="$KEYCLOAK_PROVISIONER_CLIENT_ID" \
  --from-literal=client-secret="$KEYCLOAK_PROVISIONER_CLIENT_SECRET"
apply_secret bff-oidc --from-literal=client-secret="$CONTEXTURE_BFF_CLIENT_SECRET"
apply_secret om-oidc --from-literal=client-id=contexture-openmetadata \
  --from-literal=client-secret="$CONTEXTURE_OM_CLIENT_SECRET"
ensure om-secrets --from-literal=fernet-key="$(fernet)" --from-literal=airflow-password="$(rand 12)"
ensure fuseki-auth --from-literal=admin-password="$(rand 12)" --from-literal=openmetadata-password="$(rand 12)"
ensure doris-root --from-literal=username=root --from-literal=password="$(rand 12)"
ensure doris-reader --from-literal=username=ctx_reader --from-literal=password="$(rand 12)"
ensure langfuse-secrets --from-literal=salt="$(rand)" --from-literal=encryption-key="$(rand 32)" \
  --from-literal=nextauth-secret="$(rand 32)"
ensure langfuse-init --from-literal=public-key="pk-lf-$(rand 12)" --from-literal=secret-key="sk-lf-$(rand)" \
  --from-literal=admin-password="$(rand 12)"
ensure langfuse-clickhouse --from-literal=password="$(rand)"
LF_PK=$(kubectl -n "$NS" get secret langfuse-init -o jsonpath='{.data.public-key}' | base64 -d)
LF_SK=$(kubectl -n "$NS" get secret langfuse-init -o jsonpath='{.data.secret-key}' | base64 -d)
apply_secret otel-langfuse --from-literal=auth="$(printf '%s:%s' "$LF_PK" "$LF_SK" | base64)"
apply_secret airflow-metadata \
  --from-literal=connection="postgresql://airflow:$(pg_password airflow)@pg-rw:5432/airflow?sslmode=disable"
ensure airflow-secrets --from-literal=fernet-key="$(fernet)" --from-literal=api-secret-key="$(rand)" \
  --from-literal=jwt-secret="$(rand 32)"
# 模型服务（AI 网关的模型路由）：.env.local 中 MODEL_HOST / MODEL_NAME / MODEL_API_KEY 由负责人配置，未配置时为占位
apply_secret ai-gateway-model --from-literal=host="${MODEL_HOST:-api.deepseek.com:443}" \
  --from-literal=model="${MODEL_NAME:-deepseek-chat}" --from-literal=api-key="${MODEL_API_KEY:-unset}"
# bff：挂载为文件（CTX_SECRETS_DIR）；OM 机器人令牌由 make seed 写入
kubectl -n "$NS" get secret bff-secrets >/dev/null 2>&1 || apply_secret bff-secrets --from-literal=ctx_om_token=""
kubectl -n "$NS" patch secret bff-secrets --type merge -p "$(python3 -c "
import json,sys
print(json.dumps({'stringData': {
  'ctx_client_secret': sys.argv[1],
  'ctx_database_url': 'postgresql+asyncpg://bff:%s@pg-rw:5432/bff' % sys.argv[2]}}))
" "$CONTEXTURE_BFF_CLIENT_SECRET" "$(pg_password bff)")" >/dev/null

# ---------- 4. 镜像 ----------
if [[ -n $OFFLINE ]]; then
  log "导入离线包中的镜像（$(ls "$OFFLINE"/images/*.tar | wc -l | tr -d ' ') 个）"
  for archive in "$OFFLINE"/images/*.tar; do
    kind load image-archive "$archive" --name "$CLUSTER" >/dev/null
  done
  export CTX_OFFLINE_CHARTS="$OFFLINE/charts"
else
log "构建并导入自建镜像"
image_exists() { docker image inspect "$1" >/dev/null 2>&1; }
OM_VERSION=$(awk '/^image_version:/{print $2}' third_party/openmetadata/UPSTREAM.yaml)
image_exists "contexture/openmetadata-server:$OM_VERSION" || third_party/openmetadata/build/build.sh server
image_exists contexture/openmetadata-fuseki:6.2.0-ctx.0 || third_party/openmetadata/build/build.sh fuseki
docker build -q -f services/bff/Dockerfile -t contexture/bff:dev . >/dev/null
docker build -q -f apps/web/Dockerfile -t contexture/web:dev . >/dev/null
kind load docker-image --name "$CLUSTER" "contexture/openmetadata-server:$OM_VERSION" \
  contexture/openmetadata-fuseki:6.2.0-ctx.0 contexture/bff:dev contexture/web:dev >/dev/null
  # 开源组件的镜像：本机 Docker 已有的预先导入集群（新建集群时免去重新下载），其余由节点自行拉取。
  # 按本机架构逐个导出：多架构镜像在本机只有一种架构的数据，整体导出后 kind 无法导入
  PLATFORM=$([[ $(uname -m) == arm64 || $(uname -m) == aarch64 ]] && echo linux/arm64 || echo linux/amd64)
  TMP_IMAGES=$(mktemp -d)
  loaded=0
  for image in $(uv run python -m tools.offline_package --list); do
    [[ $image == contexture/* ]] && continue
    docker image inspect "$image" >/dev/null 2>&1 || continue
    if docker save --platform "$PLATFORM" -o "$TMP_IMAGES/image.tar" "$image" 2>/dev/null \
      && kind load image-archive "$TMP_IMAGES/image.tar" --name "$CLUSTER" >/dev/null 2>&1; then
      loaded=$((loaded + 1))
    fi
  done
  rm -rf "$TMP_IMAGES"
  log "预先导入本机已有的组件镜像：$loaded 个（其余由节点从网络拉取）"
fi

# ---------- 5. 部署 ----------
log "helmfile sync（环境：$ENV）"
# 模拟源系统（003）不随 make up 部署，由 make mock-data 按需部署；这里排除而非设为不安装，以免卸载已有的模拟库
if [[ -n $OFFLINE ]]; then
  helmfile -f deploy/helmfile.yaml.gotmpl -e "$ENV" -l 'group!=mock-sources' sync --skip-deps
else
  helmfile -f deploy/helmfile.yaml.gotmpl -e "$ENV" -l 'group!=mock-sources' sync
fi

# ---------- 6. 组件配置（需服务就绪后经 API 写入） ----------
log "OpenMetadata：本体共用字段与关系类型"
kubectl -n "$NS" port-forward svc/openmetadata 8585:8585 >/dev/null 2>&1 &
PF=$!
for _ in $(seq 1 30); do curl -sf -o /dev/null http://localhost:8585/api/v1/system/version && break; sleep 2; done
SSL_CERT_FILE="$CA" uv run python -m tools.om_config --om-url http://localhost:8585 || { kill $PF 2>/dev/null; exit 1; }
kill $PF 2>/dev/null || true  # 端口转发可能已自行退出

# ---------- 7. 冒烟测试 ----------
log "冒烟测试"
failed=0
for t in deploy/components/*/tests/smoke.sh deploy/charts/*/tests/smoke.sh; do
  name=$(basename "$(dirname "$(dirname "$t")")")
  if "$t" >/tmp/ctx-smoke-"$name".log 2>&1; then echo "  ✔ $name"; else echo "  ✘ $name（日志 /tmp/ctx-smoke-$name.log）"; failed=1; fi
done
[[ $failed == 0 ]] && log "环境就绪：织境 http://localhost:8080" || { log "有组件未通过冒烟测试"; exit 1; }
