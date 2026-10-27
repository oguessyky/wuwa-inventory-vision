# 用 NAS 当主机

「主机」是一台一直开着的机器（NAS、迷你电脑、小服务器），它保存数据、提供页面。玩游戏的电脑负责扫描，扫完的每个分页都会发给主机。这样你的手机、笔电随时都能打开结果，玩游戏的电脑关着也行。

主机是**现成的**：程序是已经做好的镜像，Tailscale 也一起放在同一个项目里。NAS 上什么都不用编译、不用敲命令，只要把一个配置文件粘贴进 NAS 的 Docker 应用。主机和扫描端各自的图文指南在[安装指南](/guides#home)里。

## 需要什么

- 有 Docker（带 Compose）的 NAS（绿联 UGOS、群晖、Unraid、威联通…）或任何 Linux 机器。
- 一个免费的 [Tailscale](https://tailscale.com) 账号。NAS 或电脑上已经装了 Tailscale 也没关系，不会被动到：主机会作为一个新设备加入你的网络。

## 1. 拿一个 Tailscale 授权密钥

打开 <https://login.tailscale.com/admin/settings/keys>，点 **Generate auth key**，复制 `tskey-auth-…`。一次性的密钥就够了：只在第一次启动时用一次。别给别人看。

## 2. 在 Docker 应用里建项目

在 NAS 的 Docker 应用里：**项目** → **创建项目**：

- **名称：** `wuwa-inventory-vision`
- **存储路径：** 一个空文件夹，比如 `/volume1/docker/wuwa-inventory-vision`。数据就保存在这里；别把它放在会和电脑同步的文件夹里。
- **Compose 配置：** 把发布页上的 `docker-compose.yaml` 整个粘贴进去，并把 `TS_AUTHKEY` 那一行里的 `tskey-auth-PUT-YOURS-HERE` 换成你的密钥。

然后点 **部署**。Docker 应用会下载两个镜像：`wuwa-inventory-vision-home`（程序本身）和 `wuwa-inventory-vision-tailscale`（Tailscale 官方镜像，用本程序的名字发布），然后启动它们。

## 3. 打开它

在登录了同一个 Tailscale 的手机或电脑上，打开 `http://wuwa-home:4000`。

在 Tailscale 管理后台会看到一个新设备 `wuwa-home`。把它的 **key expiry（密钥过期）** 关掉，否则半年后它会要求重新登录。

主机只能从你自己的 Tailscale 网络里打开，不会公开到互联网上。

## 4. 下载图鉴（第一次）

新主机还没有图鉴：没有物品名称、图片、配方。第一次打开时，新手引导的最后一步会提供「下载图鉴」，点一下就开始，并带你到「更新」页看进度和剩余时间。第一次下载需要一点时间，失败的条目会自动重试。

## 5. 连接扫描端

玩游戏的电脑用 **scanner** 程序包：

1. 像 [Windows 安装](/install)一样解除锁定、解压，双击 **`1 安装 Setup`**（扫描端不下载图鉴，它会从主机拿）。
2. 双击 **`2 连接主机 Connect home`**。地址直接按回车就是 `wuwa-home`；密钥是主机存储路径里 `data/home.key` 文件的那一行（用 NAS 的文件管理器打开）。
3. 双击 **`3 扫描 Scan`** 开始扫描（见[怎么扫描](/scan)）。每扫完一个分页就会发给主机。

第二台扫描端（比如笔电）用同一个密钥。

## 备份

所有东西都在存储路径里的 `data` 文件夹：`wuwa.sqlite`、`icons/`、`catalogue/` 和 `home.key`。先停止项目再复制，数据库才完整。

## 卡住了？

见[出了问题怎么办](/troubleshooting)。
