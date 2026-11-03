# SBOM 许可复核记录（2026-11-02）

最终三份 SBOM 无禁止项；以下是现有 allowlist 之外的人工复核项，不表示已获许可批准。
Web 安装阶段含构建工具与嵌套依赖；最终 nginx 运行镜像不含 node_modules。
Node 22.23.4、npm 12.2.1 固定；不修改 allowlist 或例外。
根包 contexture 为本工程，UNKNOWN 是工具缺少版本元信息；其余缺失信息与非白名单许可须按实际发行物核对。

| 来源 | 包 | 固定版本 | 扫描许可 |
| --- | --- | --- | --- |
| bff | Simple Launcher | 1.1.0.14 | 无许可信息 |
| bff | certifi | 2026.10.19 | MPL-2.0 |
| bff | python | 3.12.16 | 无许可信息 |
| web-dependencies | chownr | 3.0.0 | BlueOak-1.0.0 |
| web-dependencies | common-ancestor-path | 2.0.0 | BlueOak-1.0.0 |
| web-dependencies | contexture | UNKNOWN | 无许可信息 |
| web-dependencies | fastlist-0.3.0-x64 | UNKNOWN | 无许可信息 |
| web-dependencies | fastlist-0.3.0-x86 | UNKNOWN | 无许可信息 |
| web-dependencies | glob | 13.0.6 | BlueOak-1.0.0 |
| web-dependencies | isexe | 4.0.0 | BlueOak-1.0.0 |
| web-dependencies | lightningcss | 1.32.0 | MPL-2.0 |
| web-dependencies | lightningcss | 1.33.0 | MPL-2.0 |
| web-dependencies | lightningcss-linux-arm64-musl | 1.32.0 | MPL-2.0 |
| web-dependencies | lightningcss-linux-arm64-musl | 1.33.0 | MPL-2.0 |
| web-dependencies | lru-cache | 11.5.2 | BlueOak-1.0.0 |
| web-dependencies | lru-cache | 11.5.3 | BlueOak-1.0.0 |
| web-dependencies | minimatch | 10.2.5 | BlueOak-1.0.0 |
| web-dependencies | minimatch | 10.2.6 | BlueOak-1.0.0 |
| web-dependencies | minipass | 7.1.3 | BlueOak-1.0.0 |
| web-dependencies | minipass-flush | 1.0.6 | BlueOak-1.0.0 |
| web-dependencies | node | 22.23.4 | 无许可信息 |
| web-dependencies | npm | 12.2.1 | Artistic-2.0 |
| web-dependencies | path-scurry | 2.0.2 | BlueOak-1.0.0 |
| web-dependencies | spdx-exceptions | 2.5.0 | CC-BY-3.0 |
| web-dependencies | tar | 7.5.22 | BlueOak-1.0.0 |
| web-dependencies | yallist | 5.0.0 | BlueOak-1.0.0 |
