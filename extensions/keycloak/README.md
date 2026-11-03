# 织境 Keycloak 登录主题

使用 Keycloak 26.8.0 官方主题扩展点，继承 `keycloak`。只为 `contexture-bff`
客户端设置属性 `login_theme=contexture`，不设置 realm 的 `loginTheme`，不改变其他应用的登录状态。
原生表单、action、隐藏字段、账号切换及密码显隐脚本保留；扩展只移动原表单节点并增加品牌布局。
不覆盖上游 FreeMarker 模板，不读取、代理或自行提交密码。服务器原有的账号 / 密码分步流程保持。

共享视觉与中文文案的源文件在 `packages/ui/identity/`，主题专用适配在本目录。
生产代码独立实现，不依赖 `specs/` 原型，不加载外部字体或图片。升级 Keycloak 时重新执行真实身份与浏览器回归。

## 打包与自带身份服务

```bash
uv run python -m tools.keycloak_theme --write-values
uv run python -m tools.keycloak_theme --check
uv run python -m tools.keycloak_theme --bundle /tmp/contexture-theme
```

`deploy/components/keycloak/values/theme.yaml` 为生成的静态交付副本；不要直接编辑。
Helmfile 加载该副本，Chart 将主题挂载到 `/opt/keycloak/themes/contexture`，内容校验和触发滚动更新。
离线包包含 deploy 目录及全部主题资源，无需在客户环境运行打包器或联网下载素材。
`make components-check` 会拒绝过期副本。

## 外部身份服务

由身份服务运维人员将 bundle 的 `contexture/` 持久挂载至 `/opt/keycloak/themes/contexture`，
并通过官方管理界面 / API 仅为织境客户端设置上述属性。镜像中的官方主题继续提供原生表单。
不要为此修改共享 realm 的认证流程、语言、全局主题或其他客户端。

当前本机外部服务 `paperclip-keycloak-1` 已安装主题并限定到织境客户端；本次核对 realm 及另外
10 个客户端的完整配置保持不变。此次直接复制到现有容器的目录会在重建容器后丢失，
重建时必须重新安装或改为持久挂载；它不等同于已修改外部项目的 Compose 配置。

生产模式会缓存主题资源。原地更新后按 Keycloak 官方说明清理对应主题的 gzip 缓存，
并在浏览器强制刷新；本次仅清理了 contexture 自有脚本缓存，没有重启共享身份服务。
新建自带服务通过 Pod 滚动更新获得新资源。

参考：[官方主题说明](https://www.keycloak.org/ui-customization/themes)。
