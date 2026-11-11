#!/usr/bin/env bash
# T037a：make cloud-images（FR-023，2026-11-11 澄清）——推送专用标签 cloud-images/<提交前 12 位> 触发镜像流水线
source "$REPO_ROOT/tools/cloud/images.sh"

# 临时仓库 + 裸远端，用真实 git 验证推送结果
setup_repo() {
  local base; base=$(tmpdir)
  git init -q --bare "$base/remote.git"
  git init -q -b work "$base/repo"
  git -C "$base/repo" config user.email t@example.com
  git -C "$base/repo" config user.name t
  echo a > "$base/repo/a.txt"
  git -C "$base/repo" add a.txt
  git -C "$base/repo" commit -q -m init
  git -C "$base/repo" remote add origin "$base/remote.git"
  CTX_IMAGES_REPO=$base/repo REMOTE=$base/remote.git
  SHA12=$(git -C "$CTX_IMAGES_REPO" rev-parse HEAD | cut -c1-12)
}

remote_refs() { git ls-remote "$REMOTE"; }

test_pushes_branch_and_tag_after_confirmation() {
  setup_repo
  CONFIRM=yes ctx_images_main >/dev/null
  local refs; refs=$(remote_refs)
  assert_contains "$refs" "refs/heads/work"
  assert_contains "$refs" "refs/tags/cloud-images/$SHA12"
}

test_prints_image_tag_and_where_to_watch() {
  setup_repo
  local out; out=$(CONFIRM=yes ctx_images_main)
  assert_contains "$out" "git-$SHA12"
  assert_contains "$out" "make cloud-deploy VERSION=git-$SHA12"
}

test_refuses_dirty_workspace() {
  setup_repo
  echo b > "$CTX_IMAGES_REPO/b.txt"
  CONFIRM=yes assert_status 2 ctx_images_main
  assert_contains "$OUTPUT" "未提交"
  assert_eq "" "$(remote_refs)" "不应推送任何引用"
}

test_refuses_detached_head() {
  setup_repo
  git -C "$CTX_IMAGES_REPO" checkout -q --detach
  CONFIRM=yes assert_status 2 ctx_images_main
  assert_eq "" "$(remote_refs)"
}

test_unconfirmed_pushes_nothing() {
  setup_repo
  assert_status 3 ctx_images_main < /dev/null
  assert_eq "" "$(remote_refs)"
}

test_existing_remote_tag_is_not_pushed_again() {
  setup_repo
  CONFIRM=yes ctx_images_main >/dev/null
  local out; out=$(CONFIRM=yes ctx_images_main)
  assert_contains "$out" "已触发过"
}

test_workflow_triggers_only_on_manual_run_or_dedicated_tag() {
  local wf; wf=$(sed -n '/^on:/,/^permissions:/p' "$REPO_ROOT/.github/workflows/cloud-images.yml")
  assert_contains "$wf" "workflow_dispatch:"
  assert_contains "$wf" "- 'cloud-images/*'"
  assert_not_contains "$wf" "branches"
  assert_not_contains "$wf" "pull_request"
  assert_contains "$(cat "$REPO_ROOT/.github/workflows/cloud-images.yml")" 'ref: ${{ inputs.ref || github.ref }}'
}

# 2026-11-11：自建镜像（bff、web）漏洞扫描阻断推送；OpenMetadata 第三方镜像扫描结果留档并告警、不阻断（与 ci.yml 只门禁自建镜像一致）
scan_step() { sed -n '/name: SBOM、许可与漏洞扫描/,/name: 统一推送/p' "$REPO_ROOT/.github/workflows/cloud-images.yml"; }

test_scan_blocks_own_images_and_reports_third_party() {
  local s; s=$(scan_step)
  assert_contains "$s" "--fail-on critical"
  assert_contains "$s" 'openmetadata-*)'
  assert_contains "$s" "::warning::"
  assert_contains "$s" "sbom/\$name.grype.txt"
}

test_scan_reports_are_uploaded_even_when_scan_fails() {
  local wf; wf=$(sed -n '/uses: actions\/upload-artifact/,$p' "$REPO_ROOT/.github/workflows/cloud-images.yml")
  assert_contains "$(grep -B1 'uses: actions/upload-artifact' "$REPO_ROOT/.github/workflows/cloud-images.yml")" "if: always()"
  assert_contains "$wf" "sbom/"
}
