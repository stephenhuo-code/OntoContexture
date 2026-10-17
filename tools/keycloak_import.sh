#!/usr/bin/env bash
# 把织境的 Keycloak 配置增量导入外部 Keycloak（本机为负责人的 Keycloak，经 Paperclip 的 Caddy）。
# 凭证与参数来自 .env.local；导入参数见 deploy/components/keycloak/import.env（只增不删）。
# 用法：tools/keycloak_import.sh [--with-test-users]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env.local; set +a

CONFIG_DIR=deploy/components/keycloak/config
FILES=/config/contexture.yaml
[[ "${1:-}" == "--with-test-users" ]] && FILES='/config/*.yaml'

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
docker exec paperclip-caddy-1 cat /data/caddy/pki/authorities/local/root.crt > "$WORK/ca.crt"
docker run --rm -v "$WORK:/w" --entrypoint keytool quay.io/keycloak/keycloak:26.8.0 \
  -importcert -noprompt -alias caddy -file /w/ca.crt -keystore /w/truststore.p12 \
  -storetype PKCS12 -storepass changeit >/dev/null

docker run --rm --add-host sso.127.0.0.1.nip.io:host-gateway \
  --env-file deploy/components/keycloak/import.env \
  -v "$PWD/$CONFIG_DIR:/config:ro" -v "$WORK/truststore.p12:/truststore.p12:ro" \
  -e JAVA_TOOL_OPTIONS="-Djavax.net.ssl.trustStore=/truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12" \
  -e KEYCLOAK_URL -e KEYCLOAK_LOGINREALM="$KEYCLOAK_REALM" -e KEYCLOAK_GRANTTYPE=client_credentials \
  -e KEYCLOAK_CLIENTID="$KEYCLOAK_PROVISIONER_CLIENT_ID" \
  -e KEYCLOAK_CLIENTSECRET="$KEYCLOAK_PROVISIONER_CLIENT_SECRET" \
  -e IMPORT_FILES_LOCATIONS="$FILES" -e CONTEXTURE_BFF_CLIENT_SECRET -e CTX_PUBLIC_URL \
  adorsys/keycloak-config-cli:6.5.1-26.5.5
