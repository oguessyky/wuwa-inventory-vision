# 用 NAS 当服务器

**服务器**是一台一直开着的机器（NAS、迷你电脑），它保存数据、提供页面。玩游戏的电脑只负责扫描，每扫完一个分页就发给服务器。手机随时能打开，电脑关着也行。

你要准备：

- 有 Docker（带 Compose）的 NAS（绿联 UGOS、群晖、Unraid、威联通…）或任何 Linux 机器；
- 一个免费的 [Tailscale](https://tailscale.com) 账号。

NAS 上不用编译、不用敲命令：复制下面的配置，粘贴进 Docker 应用就好。服务器只在你自己的 Tailscale 网络里，不会公开到互联网。

{{steps}}

## 改成一个容器

用旧配置文件装的服务器有三个容器：`…-net-1`、`…-tailscale-1` 和 `…-wuwa-1`。它还能继续用，也能继续更新，但重启时可能报 “network namespace” 错误。改成一个容器后就不会再这样。步骤：

1. 先按 **Update**，把新镜像拉到 NAS 上：旧镜像里没有 Tailscale，服务器会从你的 tailnet 上掉线。
2. 在 NAS 的 Docker 应用里**先停止项目**。旧的 Tailscale 不能和新的同时运行，否则两个会抢同一台设备。
3. 把新的 `docker-compose.yaml` 粘贴覆盖旧的，如果你改过 `wuwa-server` 这个名字，就把它改回你自己的，再**部署**。
4. 删掉留下的两个容器：`…-net-1` 和 `…-tailscale-1`。

数据和 Tailscale 里的名字都不变，也不需要新的钥匙。

## 备份

一切都在存储路径的 `data` 文件夹里：`wuwa.sqlite`、`icons/`、`catalogue/`、`server.key`。先停止项目再复制。

## 接下来

- [怎么扫描](/scan)，[更新](/update)。
- 卡住了：[出了问题怎么办](/troubleshooting)。
