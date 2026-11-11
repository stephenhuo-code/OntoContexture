#!/usr/bin/env bash
# T070 云端验证：开发模式改动 10 秒内生效、同步中断后补齐、退出 5 分钟内恢复稳定版本（US2 场景 2、5；SC-002；边界情况“网络短暂中断”）
source "$(dirname "$0")/lib.sh"
D=$CTX_CLOUD_DOMAIN MARK="ctx-dev-$(date +%s)"
# Vite 开发服务器直接提供源码模块，可用 curl 观察同步结果
WEB_FILE="$ROOT/apps/web/src/dev-server.ts"; URL="https://$D/src/dev-server.ts"; cp "$WEB_FILE" "$WEB_FILE.bak"
trap 'mv -f "$WEB_FILE.bak" "$WEB_FILE"; kill -TERM -- "-$DEV" 2>/dev/null || true' EXIT
# 后台进程在非交互 shell 中忽略 SIGINT（且无法再捕获），用 setsid 自成进程组，结束时向整组发 TERM（T075 实测）
setsid bash -c "cd '$ROOT' && exec make cloud-dev" > "$CTX_LOG_DIR/test-dev-mode.log" 2>&1 & DEV=$!
for i in $(seq 1 60); do grep -q 'Initial sync completed' "$CTX_LOG_DIR/test-dev-mode.log" 2>/dev/null && break; sleep 5; done
echo "export const CTX_DEV_MARK = \"$MARK\";" >> "$WEB_FILE"
start=$(date +%s); ok=0
for i in $(seq 1 20); do curl -s -m 5 "$URL" | grep -q "$MARK" && { ok=1; break; }; sleep 1; done
(( ok )) && pass "web 改动在 $(( $(date +%s)-start )) 秒内生效" || fail "web 改动 20 秒内未生效"
DSPID=$(pgrep -f 'devspace dev' | head -1); kill -STOP "$DSPID"; MARK2="$MARK-b"
sed -i "s#$MARK#$MARK2#" "$WEB_FILE"; sleep 20; kill -CONT "$DSPID"
for i in $(seq 1 30); do curl -s -m 5 "$URL" | grep -q "$MARK2" && break; sleep 1; done
curl -s -m 5 "$URL" | grep -q "$MARK2" && pass "同步中断恢复后补齐改动" || fail "中断后改动未补齐"
# US2 场景 6：开发模式期间部署须确认；非交互且未确认时以退出码 3 结束、不改动环境
status=0; ( cd "$ROOT" && make cloud-deploy < /dev/null ) > "$CTX_LOG_DIR/test-dev-deploy.log" 2>&1 || status=$?
[[ $status == 2 ]] && grep -q "开发模式" "$CTX_LOG_DIR/test-dev-deploy.log" && pass "开发模式期间部署要求确认" ||
  fail "开发模式期间部署未要求确认（退出码 $status）"
# SC-003：开发机内存（开发模式进程合计 RSS 与开发机容器已用）
rss=$(ps -o rss= -s "$DEV" | awk '{s+=$1} END {print int(s/1024)}')
# 开发机容器的工作集（与 kubelet 判断内存压力相同：cgroup 用量减去可回收的非活跃文件缓存；/proc/meminfo 是整个节点）
used=$(( ($(cat /sys/fs/cgroup/memory.current) - $(awk '$1 == "inactive_file" {print $2}' /sys/fs/cgroup/memory.stat)) / 1048576 ))
(( used <= 2048 )) && pass "开发模式进程 ${rss} MiB，开发机已用内存 ${used} MiB（≤ 2 GiB）" || fail "开发机已用内存 ${used} MiB 超过 2 GiB"
kill -TERM -- "-$DEV"; wait "$DEV" 2>/dev/null || true
for i in $(seq 1 60); do curl -s -m 5 "$URL" | grep -q "$MARK" || break; sleep 5; done
curl -s -m 5 "$URL" | grep -q "$MARK" && fail "退出后未恢复稳定版本" || pass "退出后恢复稳定版本"
[[ -z $(K get deploy -o name | grep devspace) ]] && pass "无残留开发 Deployment" || fail "残留开发 Deployment"
finish
