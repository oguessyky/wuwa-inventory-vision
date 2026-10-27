# 在 Mac 上安装

Mac 用的是库洛官方的 Mac 客户端。程序和 Windows 版一样，只是双击的文件是 `.command`，而且不带 Windows 用的 Python。在 Mac 上它**只读不点**：不会替你按任何键。

## 1. 先装好 Python

打开「终端」，运行：

```
brew install python@3.12
```

（还没有 Homebrew 的话，先按 <https://brew.sh> 上的一行命令装好。）

## 2. 下载、解压

到 [GitHub 发布页](https://github.com/oguessyky/wuwa-inventory-vision/releases/latest)下载：

- 一台 Mac 全部搞定：`wuwa-inventory-vision-<版本>-mac-full.zip`
- Mac 只负责扫描、结果发给[主机](/home)：`wuwa-inventory-vision-<版本>-mac-scanner.zip`

解压到一个之后不会移动的地方。

## 3. 安装（只需一次）

双击 **`1 安装 Setup`**。第一次打开时 macOS 可能说「无法验证开发者」：右键点这个文件 → **打开** → 再点 **打开**。

## 4. 允许「屏幕录制」

macOS 不允许任何程序读取别的窗口，除非你同意：

1. **系统设置 → 隐私与安全性 → 屏幕与系统录音**
2. 打开你用来运行它的程序（通常是「终端」），不是 Python，也不是游戏。第一次被拒绝后，它会自动出现在列表里。
3. 关掉终端再重新打开，然后再试一次。

## 5. 扫描

用 scanner 包的话，先双击 **`2 连接主机 Connect home`**（见[用 NAS 当主机](/home)）。

然后双击 **`扫描 Scan`**：

1. **点一下游戏窗口**：在 Mac 上，只有点进去的窗口才算在最前面，把鼠标移过去不算。
2. 打开背包，慢慢滚动每个分页；想读准数量就点一下那样东西。
3. 扫完后，回到扫描的终端窗口按 **Ctrl+C**。Mac 上没有 F9：要让一个按键在所有程序里都有效，需要「辅助功能」权限，而这个项目从不索取这个权限。

## 6. 看结果

mac-full：双击 **`3 总览 Dashboard`**，在浏览器打开 <http://127.0.0.1:4000>。用主机的话，直接打开主机的地址。

## 卡住了？

Mac 上什么都截不到，几乎都是「屏幕录制」没开。见[出了问题怎么办](/troubleshooting)。
