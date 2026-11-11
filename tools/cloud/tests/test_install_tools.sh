#!/usr/bin/env bash
# T005：开发机工具安装（FR-031、R18）
INSTALL="$REPO_ROOT/tools/cloud/install-tools.sh"

make_fixture() {  # 生成伪造的下载源与锁文件，输出锁文件路径
  local dir=$1
  mkdir -p "$dir/src/pkg"
  printf '#!/bin/sh\necho fake-raw\n' > "$dir/src/rawtool"
  printf '#!/bin/sh\necho fake-tar\n' > "$dir/src/pkg/tartool"
  tar czf "$dir/src/tartool.tgz" -C "$dir/src" pkg/tartool
  local raw_sha tar_sha
  raw_sha=$(sha256sum "$dir/src/rawtool" | cut -d' ' -f1)
  tar_sha=$(sha256sum "$dir/src/tartool.tgz" | cut -d' ' -f1)
  cat > "$dir/tools.lock" <<LOCK
# locked: 2026-11-11
rawtool 1.0 MIT 2026-01-01 file://$dir/src/rawtool $raw_sha -
tartool 2.0 Apache-2.0 2026-01-01 file://$dir/src/tartool.tgz $tar_sha pkg/tartool
LOCK
  printf '%s' "$dir/tools.lock"
}

test_installs_raw_and_archived_tools_into_local_bin() {
  local d; d=$(tmpdir); local lock; lock=$(make_fixture "$d")
  HOME=$d/home CTX_TOOLS_LOCK=$lock assert_status 0 bash "$INSTALL"
  assert_eq "fake-raw" "$("$d/home/.local/bin/rawtool")"
  assert_eq "fake-tar" "$("$d/home/.local/bin/tartool")"
}

test_sha256_mismatch_is_rejected_and_nothing_installed() {
  local d; d=$(tmpdir); local lock; lock=$(make_fixture "$d")
  echo tampered >> "$d/src/rawtool"
  HOME=$d/home CTX_TOOLS_LOCK=$lock assert_status 1 bash "$INSTALL"
  assert_contains "$OUTPUT" "SHA256"
  [[ ! -e $d/home/.local/bin/rawtool ]] || fail "校验失败的工具不得安装"
}

test_second_run_skips_already_installed_versions() {
  local d; d=$(tmpdir); local lock; lock=$(make_fixture "$d")
  HOME=$d/home CTX_TOOLS_LOCK=$lock bash "$INSTALL" >/dev/null
  HOME=$d/home CTX_TOOLS_LOCK=$lock assert_status 0 bash "$INSTALL"
  assert_contains "$OUTPUT" "rawtool 1.0 已安装"
}

test_missing_base_command_fails_with_exit_2() {
  local d; d=$(tmpdir); local lock; lock=$(make_fixture "$d")
  mkdir -p "$d/bin"
  local c
  for c in bash curl tar sha256sum openssl mkdir install chmod mktemp rm cat awk date dirname basename cp grep sed head tr cut sort; do
    ln -s "$(command -v "$c")" "$d/bin/$c"
  done
  HOME=$d/home CTX_TOOLS_LOCK=$lock PATH=$d/bin assert_status 2 "$d/bin/bash" "$INSTALL"
  assert_contains "$OUTPUT" "git"
}
