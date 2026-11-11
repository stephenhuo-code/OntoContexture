#!/usr/bin/env bash
# T053 云端验证：受信任 HTTPS、HTTP 重定向、未登录跳转 Keycloak、组件子域名可达、模拟库端口不对外（US4 场景 1、3、4；FR-019、FR-020）
source "$(dirname "$0")/lib.sh"
D=$CTX_CLOUD_DOMAIN
for host in "$D" sso.$D om.$D langfuse.$D airflow.$D jaeger.$D prometheus.$D dashboards.$D gateway-admin.$D; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://$host/" || echo 000)   # 不加 -k：证书必须受信任
  [[ $code =~ ^(2|3|401|403) ]] && pass "https://$host 可达（$code，证书受信任）" || fail "https://$host 返回 $code"
done
loc=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -m 20 "http://$D/")
[[ $loc =~ ^30[18]\ https:// ]] && pass "HTTP 重定向到 HTTPS（$loc）" || fail "HTTP 未重定向：$loc"
login=$(curl -s -o /dev/null -w '%{redirect_url}' -m 20 "https://$D/bff/v1/auth/login" || true)
[[ $login == https://sso.$D/* ]] && pass "未登录跳转到 Keycloak" || fail "登录未跳转到 sso.$D：$login"
ip=$(K -n envoy-gateway-system get svc -l gateway.envoyproxy.io/owning-gateway-name=contexture -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}')
for port in 3306 5432 13306 15432 9030; do
  timeout 5 bash -c "exec 3<>/dev/tcp/$ip/$port" 2>/dev/null && fail "负载均衡器开放了数据库端口 $port" || pass "端口 $port 未对外开放"
done
finish
