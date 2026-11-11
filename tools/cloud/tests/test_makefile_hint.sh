#!/usr/bin/env bash
# T036：缺少 uv 的开发机上执行 make lint / make test，提示改用云端命令（FR-001a）
no_uv_path() {
  local d; d=$(tmpdir); local c
  for c in make sh bash env cat; do ln -s "$(command -v "$c")" "$d/$c"; done
  printf '%s' "$d"
}

test_lint_without_uv_points_to_cloud_lint() {
  local p; p=$(no_uv_path)
  assert_status 2 env PATH="$p" make -s -C "$REPO_ROOT" lint
  assert_contains "$OUTPUT" "make cloud-lint"
}

test_test_without_uv_points_to_cloud_test() {
  local p; p=$(no_uv_path)
  assert_status 2 env PATH="$p" make -s -C "$REPO_ROOT" test
  assert_contains "$OUTPUT" "make cloud-test"
}
