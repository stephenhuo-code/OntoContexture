# OpenMetadata 镜像构建

从 `../src`（子仓库，分支 `ctx/2.0.3`）构建 `openmetadata-server` 与 `openmetadata-ingestion` 镜像，版本号见
`../UPSTREAM.yaml` 的 `image_version`。构建脚本与 Dockerfile 由 001 的任务 T045 编写。

克隆织境仓库后拉取子仓库：`git submodule update --init --depth 1 third_party/openmetadata/src`
