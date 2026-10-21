# deploy/offline/

离线安装包（D9）。镜像清单由各组件的 `component.yaml` 汇总（`python -m tools.offline_package --list`）。

```bash
make offline-package                 # 生成 dist/：images.txt、images/*.tar、charts/、repo/
deploy/offline/install.sh dist       # 在无外网环境中安装（kind：设置 CTX_KIND_CLUSTER）
tests/e2e/test_offline_install.sh    # 验收：断网 kind 集群中安装并就绪
```

客户集群：把 `images/*.tar` 导入内网镜像仓库（`docker load` 后 `docker tag` / `docker push`），并在各组件 values 中
把镜像仓库前缀改为内网地址，再执行 `install.sh`。Secret 与 `.env.local` 的准备同 `tools/up.sh` 第 3 步。
