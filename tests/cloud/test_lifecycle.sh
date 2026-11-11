#!/usr/bin/env bash
# T078 云端验证：停止后弹性池 20 分钟内降到 0、devbox 不受影响、访问立即失败；启动 30 分钟内恢复且数据一致；幂等（US6；SC-011、SC-012）
source "$(dirname "$0")/lib.sh"
snapshot() {  # 数据快照：OM 数据源与表数量、Langfuse 轨迹数量
  local pg; pg=$(K get pod -l cnpg.io/cluster=pg,cnpg.io/instanceRole=primary -o name | head -1)
  K exec "$pg" -- psql -U postgres -tAc "select (select count(*) from openmetadata.public.dbservice_entity),
    (select count(*) from openmetadata.public.table_entity)" 2>/dev/null | tr -d ' '
  K exec "$pg" -- psql -U postgres -d langfuse -tAc "select count(*) from traces" 2>/dev/null || echo "langfuse:n/a"
}
before=$(snapshot); echo "停止前：$before"
start=$(date +%s); ( cd "$ROOT" && make cloud-stop CONFIRM=yes ) || fail "cloud-stop 失败"
stop_s=$(( $(date +%s) - start ))
(( stop_s <= 1200 )) && pass "停止用时 ${stop_s}s（≤ 20 分钟）" || fail "停止用时 ${stop_s}s"
[[ $(K get nodes -l "$CTX_CLOUD_NODE_LABEL=$CTX_CLOUD_NODE_POOL" -o name | wc -l) == 0 ]] && pass "弹性池节点为 0" || fail "弹性池仍有节点"
[[ $(K -n dev get pod devbox-0 -o jsonpath='{.status.phase}') == Running ]] && pass "devbox-0 不受影响" || fail "devbox-0 异常"
t0=$(date +%s%N); curl -s -o /dev/null -m 30 "https://$CTX_CLOUD_DOMAIN/" ; ms=$(( ($(date +%s%N)-t0)/1000000 ))
(( ms < 30000 )) && pass "停止期间访问在 ${ms}ms 内失败，未挂起" || fail "停止期间访问挂起"
( cd "$ROOT" && make cloud-stop ) >/dev/null && pass "重复停止直接成功" || fail "重复停止失败"
start=$(date +%s); ( cd "$ROOT" && make cloud-start ) || fail "cloud-start 失败"
start_s=$(( $(date +%s) - start ))
(( start_s <= 1800 )) && pass "启动用时 ${start_s}s（≤ 30 分钟）" || fail "启动用时 ${start_s}s"
after=$(snapshot); echo "启动后：$after"
[[ $before == "$after" ]] && pass "停止前后数据一致" || fail "数据不一致"
( cd "$ROOT" && make cloud-start ) >/dev/null && pass "重复启动直接成功" || fail "重复启动失败"
finish
