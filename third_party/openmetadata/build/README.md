# OpenMetadata 镜像构建

从 `../src`（子仓库，分支 `ctx/2.0.3`）构建镜像，版本号见 `../UPSTREAM.yaml` 的 `image_version`。

```bash
git submodule update --init --depth 1 third_party/openmetadata/src
third_party/openmetadata/build/build.sh server      # openmetadata-server（Maven 构建，含界面）
third_party/openmetadata/build/build.sh ingestion   # openmetadata-ingestion（上游 Dockerfile）
third_party/openmetadata/build/build.sh fuseki      # openmetadata-fuseki（上游 docker/rdf-store）
```

服务端首次构建约需 30–60 分钟（下载 Maven 与 npm 依赖），之后有缓存。
