# 安全与隐私

## 它对游戏做什么

**只看屏幕。** 它读的是屏幕上显示出来的像素，和你用眼睛看是一样的。

- 不读游戏内存、不注入、不改游戏文件、不抓网络包。
- 不会让角色移动、战斗或刷东西。
- 不会使用、合成、出售或丢弃任何物品：任何会改变账号的事都不做。
- 在 Windows 上，它只在背包这类菜单里工作；在 Mac 上，它完全不会按任何键。
- 只有游戏本身在最前面时才会读；你切走它就暂停。

这是一个非官方的爱好者工具。它的设计尽量避免任何可能带来风险的做法，但它和库洛游戏无关，也没有获得认可；用不用由你自己决定。

## 你的资料

- **玩家 ID 会被抹掉。** 游戏画面上一直显示着你的玩家 ID（特征码）；它会在每张图保存或显示之前被去掉。
- **所有东西都在你自己的设备上**：你的电脑，或你自己的主机。作者收不到任何东西：没有统计、没有错误报告、没有广告。
- 页面只在这台电脑上打开；想在手机上看，是通过**你自己的** Tailscale 网络，绝不公开到互联网。
- 扫描端发给主机的只有读出的数据和物品小图，**绝不包括整幅屏幕画面**。

## 它什么时候会用网络

只有这几种情况，而且每一次都由你发起：

- **更新图鉴：** 从库洛官方 Wiki 下载物品、料理、商店的资料和图片；从 GitHub 下载游戏的数据表。
- **安装：** 下载需要的软件（Python 软件包、PyTorch、识别模型）。
- **分享给自己的设备：** 通过 Tailscale，让你自己网络里的设备打开页面。
- **主机：** 扫描端和你自己的主机之间同步，只在你自己的 Tailscale 网络里。
- **更新扫描端：** 你双击「4 更新 Update」、而且主机比它新时，从本项目的 GitHub 发布页下载那个版本。

完整的隐私政策：[PRIVACY.zh-CN.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/PRIVACY.zh-CN.md)（参考译文，以[英文原文](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/PRIVACY.md)为准）。

## 许可与致谢

代码采用 Apache License 2.0，见 [LICENSE](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/LICENSE) 和 [TERMS.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/TERMS.md)。《鸣潮》中的一切名称、图标、立绘和美术都属于库洛游戏；程序不附带任何游戏图片，而是下载到你自己的电脑上。来源和用到的软件见 [CREDITS.md](https://github.com/oguessyky/wuwa-inventory-vision/blob/main/CREDITS.md)。
