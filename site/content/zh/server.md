# 用 NAS 当服务器

**服务器**是一台一直开着的机器（NAS、迷你电脑），它保存数据、提供页面。玩游戏的电脑只负责扫描，每扫完一个分页就发给服务器。手机随时能打开，电脑关着也行。

你要准备：

- 有 Docker（带 Compose）的 NAS（绿联 UGOS、群晖、Unraid、威联通…）或任何 Linux 机器；
- 一个免费的 [Tailscale](https://tailscale.com) 账号。

NAS 上不用编译、不用敲命令：复制下面的配置，粘贴进 Docker 应用就好。服务器只在你自己的 Tailscale 网络里，不会公开到互联网。

{{steps}}

## 备份

一切都在存储路径的 `data` 文件夹里：`wuwa.sqlite`、`icons/`、`catalogue/`、`server.key`。先停止项目再复制。

## 接下来

- [怎么扫描](/scan)，[更新](/update)。
- 卡住了：[出了问题怎么办](/troubleshooting)。
