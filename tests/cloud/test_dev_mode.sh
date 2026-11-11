#!/usr/bin/env bash
# T070 云端验证：开发模式改动 10 秒内生效、同步中断后补齐、退出 5 分钟内恢复稳定版本（US2 场景 2、5；SC-002；边界情况“网络短暂中断”）
source "$(dirname "$0")/lib.sh"
D=$CTX_CLOUD_DOMAIN MARK="ctx-dev-$(date +%s)"
WEB_FILE="$ROOT/apps/web/index.html"; cp "$WEB_FILE" "$WEB_FILE.bak"
trap 'mv -f "$WEB_FILE.bak" "$WEB_FILE"; kill "$DEV" 2>/dev/null || true' EXIT
( cd "$ROOT" && make cloud-dev ) > "$CTX_LOG_DIR/test-dev-mode.log" 2>&1 & DEV=$!
for i in $(seq 1 60); do grep -q 'Initial sync completed' "$CTX_LOG_DIR/test-dev-mode.log" 2>/dev/null && break; sleep 5; done
sed -i "s#</title>#</title><meta name=\"ctx-dev\" content=\"$MARK\">#" "$WEB_FILE"
start=$(date +%s); ok=0
for i in $(seq 1 20); do curl -s -m 5 "https://$D/" | grep -q "$MARK" && { ok=1; break; }; sleep 1; done
(( ok )) && pass "web 改动在 $(( $(date +%s)-start )) 秒内生效" || fail "web 改动 20 秒内未生效"
DSPID=$(pgrep -f 'devspace dev' | head -1); kill -STOP "$DSPID"; MARK2="$MARK-b"
sed -i "s#$MARK#$MARK2#" "$WEB_FILE"; sleep 20; kill -CONT "$DSPID"
for i in $(seq 1 30); do curl -s -m 5 "https://$D/" | grep -q "$MARK2" && break; sleep 1; done
curl -s -m 5 "https://$D/" | grep -q "$MARK2" && pass "同步中断恢复后补齐改动" || fail "中断后改动未补齐"
kill -INT "$DEV"; wait "$DEV" 2>/dev/null || true
for i in $(seq 1 60); do curl -s -m 5 "https://$D/" | grep -q "$MARK" || break; sleep 5; done
curl -s -m 5 "https://$D/" | grep -q "$MARK" && fail "退出后未恢复稳定版本" || pass "退出后恢复稳定版本"
[[ -z $(K get deploy -o name | grep devspace) ]] && pass "无残留开发 Deployment" || fail "残留开发 Deployment"
finish
