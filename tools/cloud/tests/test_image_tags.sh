#!/usr/bin/env bash
# T027：镜像标签规则（data-model.md 第 4 节；FR-022、FR-023）
source "$REPO_ROOT/tools/cloud/lib/tags.sh"

new_repo() {
  local d; d=$(tmpdir)
  git -C "$d" init -q; git -C "$d" config user.email t@example.com; git -C "$d" config user.name t
  echo a > "$d/a.txt"; echo lock1 > "$d/uv.lock"; printf 'secret\n' > "$d/.gitignore"
  git -C "$d" add . && git -C "$d" commit -qm init
  printf '%s' "$d"
}

test_pipeline_tag_uses_first_12_chars_of_commit() {
  assert_eq git-0123456789ab "$(ctx_tag_pipeline 0123456789abcdef0123456789abcdef01234567)"
}

test_clean_workspace_tag() {
  local d; d=$(new_repo); local head; head=$(git -C "$d" rev-parse HEAD)
  assert_eq "ws-${head:0:12}" "$(ctx_tag_workspace "$d")"
}

test_dirty_workspace_tag_is_stable_for_same_changes() {
  local d; d=$(new_repo); local head; head=$(git -C "$d" rev-parse HEAD)
  echo changed >> "$d/a.txt"; echo new > "$d/new.txt"
  local t1 t2; t1=$(ctx_tag_workspace "$d"); t2=$(ctx_tag_workspace "$d")
  [[ $t1 =~ ^ws-${head:0:12}-[0-9a-f]{8}$ ]] || fail "格式不对：$t1"
  assert_eq "$t1" "$t2" "同样的工作区应得到同样的标签"
  echo more >> "$d/new.txt"
  [[ $(ctx_tag_workspace "$d") != "$t1" ]] || fail "改动不同时标签应不同"
}

test_ignored_files_do_not_affect_workspace_tag() {
  local d; d=$(new_repo); local before; before=$(ctx_tag_workspace "$d")
  echo token > "$d/secret"
  assert_eq "$before" "$(ctx_tag_workspace "$d")"
}

test_workspace_is_dirty_reports_correctly() {
  local d; d=$(new_repo)
  ctx_workspace_dirty "$d" && fail "干净工作区被判为有改动"
  echo x >> "$d/a.txt"
  ctx_workspace_dirty "$d" || fail "有改动未识别"
}

test_lock_tag_changes_only_with_lock_files() {
  local d; d=$(new_repo)
  local t1; t1=$(ctx_tag_lock dev "$d/uv.lock")
  [[ $t1 =~ ^dev-[0-9a-f]{12}$ ]] || fail "格式不对：$t1"
  echo changed >> "$d/a.txt"
  assert_eq "$t1" "$(ctx_tag_lock dev "$d/uv.lock")" "非锁文件改动不影响标签"
  echo lock2 > "$d/uv.lock"
  [[ $(ctx_tag_lock dev "$d/uv.lock") != "$t1" ]] || fail "锁文件改动后标签应变化"
}
