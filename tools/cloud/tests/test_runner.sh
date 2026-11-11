#!/usr/bin/env bash
# T068 实测：kcov 按“被执行程序”判断插桩方式；以 `kcov <目录> bash run.sh` 运行时执行的是 bash（ELF），
# 不会启用 bash 脚本覆盖率，合并结果为空（cobertura 中没有任何文件），覆盖率门禁报“缺少源码覆盖率报告”。
# 须直接执行带 shebang 的 run.sh
test_kcov_executes_the_script_directly() {
  local line; line=$(cat "$REPO_ROOT/tools/cloud/tests/run.sh")
  assert_contains "$line" '"$HERE/run.sh" --single'
  assert_not_contains "$line" ' bash "$HERE/run.sh"'
}

# T068 实测：工具箱容器的文件描述符上限为 1073741816，kcov 43 的 bash 引擎据此选取描述符号后报
# “Failed to exchange stderr for pipe: Bad file descriptor”，无法启动；上限降到 1024 后正常
test_kcov_mode_lowers_huge_fd_limit() {
  assert_contains "$(cat "$REPO_ROOT/tools/cloud/tests/run.sh")" "ulimit -n 1024"
}
