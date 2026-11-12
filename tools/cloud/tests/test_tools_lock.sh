#!/usr/bin/env bash
# T004：开发机工具锁文件（FR-031、R15）
LOCK="$REPO_ROOT/tools/cloud/tools.lock"

lock_entries() { grep -vE '^\s*(#|$)' "$LOCK"; }

test_lock_exists_with_required_tools() {
  [[ -f $LOCK ]] || fail "缺少 tools/cloud/tools.lock"
  local names; names=$(lock_entries | awk '{print $1}' | sort | tr '\n' ' ')
  for tool in buildctl devspace doctl helm helmfile jq kubectl; do
    assert_contains " $names" " $tool " "锁文件缺少 $tool"
  done
}

test_each_entry_has_seven_fields_and_valid_sha256() {
  while read -r name version license published url sha member; do
    [[ -n $member ]] || fail "$name 字段不足（名称 版本 许可 发布日期 URL SHA256 包内路径）"
    [[ $sha =~ ^[0-9a-f]{64}$ ]] || fail "$name 的 SHA256 格式不对"
    [[ $url == https://* ]] || fail "$name 的 URL 必须是 https"
    [[ $published =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || fail "$name 的发布日期格式不对"
    [[ -n $license && -n $version ]] || fail "$name 缺少版本或许可"
  done < <(lock_entries)
}

test_versions_are_at_least_two_weeks_old_at_lock_date() {
  local locked; locked=$(sed -n 's/^# locked: //p' "$LOCK")
  [[ -n $locked ]] || fail "缺少 # locked: YYYY-MM-DD"
  local limit; limit=$(date -d "$locked -14 days" +%F)
  while read -r name _ _ published _; do
    [[ ! $published > $limit ]] || fail "$name 发布于 $published，晚于 $limit（不满两周）"
  done < <(lock_entries)
}
