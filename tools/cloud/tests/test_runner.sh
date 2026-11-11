#!/usr/bin/env bash
# T068 实测：kcov 按“被执行程序”判断插桩方式；以 `kcov <目录> bash run.sh` 运行时执行的是 bash（ELF），
# 不会启用 bash 脚本覆盖率，合并结果为空（cobertura 中没有任何文件），覆盖率门禁报“缺少源码覆盖率报告”。
# 须直接执行带 shebang 的 run.sh
test_kcov_executes_the_script_directly() {
  local line; line=$(grep -E '^\s+kcov .*--single' "$REPO_ROOT/tools/cloud/tests/run.sh")
  assert_contains "$line" '"$HERE/run.sh" --single'
  assert_not_contains "$line" ' bash "$HERE/run.sh"'
}
