# Omnigent 镜像构建

从 `../src`（子仓库，分支 `ctx/v0.18.0`）构建 `omnigent-server`、runner、host 镜像，版本号见 `../UPSTREAM.yaml`。构建脚本在 014 中编写。

克隆织境仓库后拉取子仓库：`git submodule update --init --depth 1 third_party/omnigent/src`
