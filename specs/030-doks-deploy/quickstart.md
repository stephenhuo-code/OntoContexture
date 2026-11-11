# Quickstart: DOKS 云端开发与部署环境

验证从零到可用的全过程。命令都在开发机 devbox-0 的仓库根目录执行。各命令的细节见 [contracts/cloud-commands.md](contracts/cloud-commands.md)。

## 前置条件

1. `~/.kube/doks.yaml` 可用：`kubectl --kubeconfig ~/.kube/doks.yaml get nodes` 能列出节点。
2. 已有自有域名，可以添加 DNS 记录；已开通 DOCR，并准备好只读和读写两个令牌。
3. GitHub 仓库 Secret 中已设置 `DIGITALOCEAN_REGISTRY_TOKEN`（读写）。

## 1. 准备

```bash
make cloud-tools                       # 安装 kubectl / helm / helmfile / doctl / devspace / buildctl
cp .env.cloud.example .env.cloud       # 用 VS Code 打开填写：code .env.cloud
```

预期：`cloud-tools` 列出每个工具的版本，并显示“校验通过”。

## 2. 构建镜像（GitHub Actions）

在 GitHub → Actions → `cloud-images` → Run workflow，选择分支。
预期：运行成功，摘要中列出 5 个镜像，bff / web 的标签为 `git-<sha>`。

## 3. 首次部署

```bash
make cloud-deploy VERSION=git-<sha>
```

预期：输出 LB 公网 IP 与两条 DNS 记录（`<域名>`、`*.<域名>` → IP），各组件冒烟测试显示 ✔，最后输出访问地址。首次部署时证书要等 DNS 生效后才能签发，
命令会等待并提示；等待超时时，配置好 DNS 后再执行一次即可。

## 4. 访问（US4）

浏览器打开 `https://<域名>`，用 `user1 / user1` 登录。预期：证书受信任，进入首页。
`make cloud-info` 列出 OpenMetadata、Langfuse、Airflow 等的子域名地址，逐个打开验证。

## 5. 开发模式（US2）

```bash
make cloud-dev
```

修改 `apps/web/src` 中的一处文字并保存，10 秒内在浏览器中看到变化；按 `Ctrl+C` 退出。
预期：`make cloud-status` 显示“稳定版本”，页面恢复原样。

## 6. 集群内检查与测试（US3）

```bash
make cloud-lint
make cloud-test
make cloud-e2e
```

预期：结果实时输出，退出码与结果一致；结束后执行 `kubectl --kubeconfig ~/.kube/doks.yaml -n contexture-ci get pods`，没有残留的 Pod。

## 7. 集群内构建（US5）

```bash
make cloud-build TARGET=bff
make cloud-status
```

预期：10 分钟内完成；状态显示稳定版本的来源为“工作区”，并标明是否含未提交改动。

## 8. 启停（US6）

```bash
make cloud-stop     # 20 分钟内结束，显示弹性池节点数 0
make cloud-status   # 已停止
make cloud-start    # 30 分钟内结束，冒烟测试通过
```

预期：启动后，停止前接入的数据源和元数据仍在，域名不变；停止期间访问域名返回 503。

## 9. 本地不受影响（SC-007）

```bash
tools/cloud/tests/render-compare.sh    # local / lite 渲染与基线逐字节一致
```

## 10. 卸载（US7，可选）

```bash
make cloud-uninstall    # 输入 yes 确认
```

预期：织境管理的 namespace 被删除，`dev` 中的 devbox-0 不受影响。
