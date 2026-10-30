# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
# ruff: noqa: E501 -- the pages' words, Chinese and English, read better unbroken
"""The guides with pictures, one per release package (PLAN.md D185).

    uv run python tools/make_guides.py        writes deploy/release/guides/{full,scanner,server}.html

Each is one page that opens in any browser with nothing else: no script, nothing fetched, the
pictures drawn in it (SVG). A step is a number, what to do in Chinese and in English, and a
picture of it. The pictures are sketches -- a Docker app, Tailscale's keys page, a console --
not copies of anyone's screen. `{version}` is filled in by tools/make_release.py, which puts
the page in its zip as START-HERE.html.
"""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "release" / "guides"

BG, PANEL, PANEL2, LINE = "#0b0d10", "#15181e", "#1c2027", "#2a303a"
INK, MUTED, ACCENT, OK, DANGER = "#e8eaee", "#98a1ad", "#e8c15b", "#4ec98b", "#ef6461"
FONT = "'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',system-ui,sans-serif"
MONO = "Consolas,'SF Mono',Menlo,monospace"

CSS = f"""
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:{BG};color:{INK};font:15px/1.65 {FONT}}}
::selection{{background:rgba(232,201,90,.34);color:#fff}}
main{{max-width:880px;margin:0 auto;padding:32px 16px 64px}}
header h1{{font-size:26px;margin:0 0 4px}}
header .v{{color:{ACCENT};font-weight:600}}
header p{{color:{MUTED};margin:4px 0}}
.hero{{background:{PANEL};border:1px solid {LINE};border-radius:14px;padding:16px;margin:20px 0 28px}}
.hero figcaption{{color:{MUTED};font-size:13px;margin-top:8px}}
.step{{background:{PANEL};border:1px solid {LINE};border-radius:14px;padding:18px 18px 14px;
  margin:18px 0}}
.step h2{{display:flex;gap:12px;align-items:baseline;font-size:19px;margin:0 0 6px}}
.step h2 .n{{flex:none;width:30px;height:30px;border-radius:50%;background:{ACCENT};color:#111;
  display:inline-grid;place-items:center;font-size:15px;font-weight:700}}
.step h2 small{{color:{MUTED};font-weight:400;font-size:14px}}
.step p{{margin:6px 0}}
.step p[lang=en]{{color:{MUTED};font-size:14px}}
.step ol,.step ul{{margin:6px 0 6px 20px;padding:0}}
.step svg{{display:block;width:100%;height:auto;margin:12px 0 4px;border-radius:10px}}
code{{font-family:{MONO};background:{PANEL2};border:1px solid {LINE};border-radius:5px;
  padding:1px 5px;font-size:13px}}
pre{{font-family:{MONO};background:{PANEL2};border:1px solid {LINE};border-radius:8px;
  padding:10px 12px;overflow-x:auto;font-size:13px}}
.warn{{border-left:3px solid {DANGER};padding:6px 10px;background:#2a1517;border-radius:6px}}
.tip{{border-left:3px solid {OK};padding:6px 10px;background:#13241c;border-radius:6px}}
a{{color:{ACCENT}}}
h3{{font-size:16px;margin:28px 0 6px;color:{ACCENT}}}
footer{{color:{MUTED};font-size:13px;margin-top:40px}}
"""


# --- drawing --------------------------------------------------------------------------------

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def t(x: float, y: float, s: str, size: int = 14, fill: str = INK, weight: int = 400,
      mono: bool = False, anchor: str = "start") -> str:
    family = MONO if mono else FONT
    keep = ' xml:space="preserve"' if mono else ""     # code keeps its indentation
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'font-family="{esc(family)}" text-anchor="{anchor}"{keep}>{esc(s)}</text>')


def box(x: float, y: float, w: float, h: float, fill: str = PANEL2, stroke: str = LINE,
        r: int = 8, width: float = 1) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"/>')


def window(x: float, y: float, w: float, h: float, title: str) -> str:
    """A window: a title bar with three dots, and its name."""
    return (box(x, y, w, h, PANEL2, LINE, 10)
            + f'<path d="M{x} {y + 28}h{w}" stroke="{LINE}"/>'
            + "".join(f'<circle cx="{x + 16 + i * 14}" cy="{y + 14}" r="4" fill="{c}"/>'
                      for i, c in enumerate(("#5a616c", "#5a616c", "#5a616c")))
            + t(x + 64, y + 19, title, 12, MUTED))


def button(x: float, y: float, w: float, label: str, lit: bool = True, h: int = 30) -> str:
    fill, ink = (ACCENT, "#111") if lit else (PANEL, INK)
    return (box(x, y, w, h, fill, ACCENT if lit else LINE, 7)
            + t(x + w / 2, y + h / 2 + 5, label, 13, ink, 600, anchor="middle"))


def ring(x: float, y: float, w: float, h: float) -> str:
    """The thing to look at: a gold outline round it."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="none" '
            f'stroke="{ACCENT}" stroke-width="2.5" stroke-dasharray="6 4"/>')


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = ACCENT) -> str:
    return (f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{color}" stroke-width="2.5" '
            f'marker-end="url(#ah)" fill="none"/>')


def svg(body: str, w: int = 640, h: int = 260, label: str = "") -> str:
    marker = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
              f'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" '
              f'fill="{ACCENT}"/></marker></defs>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'xmlns="http://www.w3.org/2000/svg"><rect width="{w}" height="{h}" fill="{BG}"/>'
            f"{marker}{body}</svg>")


def files(x: float, y: float, rows: list[tuple[str, str]], lit: tuple[str, ...] = ()) -> str:
    """A folder's rows: (name, note); a folder ends in /."""
    out = []
    for i, (name, note) in enumerate(rows):
        yy = y + i * 26
        icon = ("M0 4h7l2 2h9v10H0z" if name.endswith("/") else "M2 0h9l5 5v13H2z")
        colour = ACCENT if name.endswith("/") else MUTED
        out.append(f'<path transform="translate({x} {yy - 13})" d="{icon}" fill="none" '
                   f'stroke="{colour}" stroke-width="1.5"/>')
        out.append(t(x + 26, yy, name, 13, INK if name in lit or not lit else MUTED,
                     600 if name in lit else 400, mono=True))
        if note:
            out.append(t(x + 270, yy, note, 12, MUTED))
        if name in lit:
            out.append(ring(x - 8, yy - 18, 250, 25))
    return "".join(out)


def console(x: float, y: float, w: float, h: float, title: str,
            lines: list[tuple[str, str]]) -> str:
    """A console window: (text, colour) lines."""
    out = [box(x, y, w, h, "#07090b", LINE, 10), f'<path d="M{x} {y + 26}h{w}" stroke="{LINE}"/>',
           t(x + 12, y + 18, title, 12, MUTED)]
    for i, (line, colour) in enumerate(lines):
        out.append(t(x + 14, y + 48 + i * 20, line, 12.5, colour, mono=True))
    return "".join(out)


def phone(x: float, y: float, address: str) -> str:
    """A phone showing 总览 at an address."""
    out = [box(x, y, 150, 250, "#07090b", LINE, 22), box(x + 10, y + 14, 130, 22, PANEL2, LINE, 11),
           t(x + 75, y + 29, address, 8.5, MUTED, anchor="middle", mono=True),
           t(x + 16, y + 62, "总览", 15, INK, 700)]
    for i in range(3):
        out.append(box(x + 14 + i * 42, y + 74, 36, 36, PANEL, LINE, 18))
        out.append(f'<path d="M{x + 22 + i * 42} {y + 92}l5 5l9 -10" stroke="{OK}" '
                   f'stroke-width="2.5" fill="none"/>')
    for i in range(3):
        out.append(box(x + 14, y + 122 + i * 38, 122, 30, PANEL, LINE, 7))
        out.append(box(x + 20, y + 130 + i * 38, 14, 14, ACCENT if i == 0 else LINE, LINE, 3))
        out.append(box(x + 40, y + 133 + i * 38, 70 - i * 14, 8, LINE, LINE, 4))
    return "".join(out)


def keycap(x: float, y: float, label: str) -> str:
    return box(x, y, 46, 40, PANEL, ACCENT, 7, 2) + t(x + 23, y + 26, label, 15, ACCENT, 700,
                                                     anchor="middle")


# --- one step -------------------------------------------------------------------------------

def step(n: int, zh_title: str, en_title: str, zh: str, en: str, picture: str,
         extra: str = "") -> str:
    """A step: its number, what to do in both languages (the text may hold markup), a picture."""
    return (f'<section class="step" id="s{n}">'
            f'<h2><span class="n">{n}</span><span lang="zh-CN">{zh_title}</span>'
            f'<small lang="en">{en_title}</small></h2>'
            f'<p lang="zh-CN">{zh}</p><p lang="en">{en}</p>{picture}{extra}</section>')


def page(title: str, intro_zh: str, intro_en: str, body: str, hero: str = "") -> str:
    return ("<!doctype html>\n"
            f'<html lang="zh-CN"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body><main>"
            f'<header><h1>{esc(title)} <span class="v">v{{version}}</span></h1>'
            f'<p lang="zh-CN">{intro_zh}</p><p lang="en">{intro_en}</p></header>'
            f"{hero}{body}"
            f'<footer><p>WuWa Inventory Vision · Apache 2.0 · '
            f'<a href="https://github.com/oguessyky/wuwa-inventory-vision">github.com/oguessyky/'
            f'wuwa-inventory-vision</a></p><p lang="zh-CN">非官方的爱好者工具，与库洛游戏无关。图里是示意，'
            f'不是哪个软件的截图。</p><p lang="en">An unofficial fan-made tool, not affiliated with '
            f"Kuro Games. The pictures are sketches, not screenshots of any program.</p></footer>"
            f"</main></body></html>\n")


# --- the pictures each guide is made of -----------------------------------------------------

def pic_unzip(folder: str, rows: list[tuple[str, str]], lit: tuple[str, ...]) -> str:
    return svg(window(20, 16, 600, 50 + len(rows) * 26, folder)
               + files(46, 72, rows, lit), 640, 76 + len(rows) * 26, f"the folder {folder}")


def pic_setup(scanner: bool, mac: bool = False) -> str:
    machine = ([("machine   : macOS arm64", MUTED), ("  gpu     : Apple Silicon", MUTED),
                ("torch     : mps", MUTED)] if mac else
               [("machine   : Windows AMD64", MUTED), ("  gpu     : NVIDIA GeForce RTX ...", MUTED),
                ("torch     : cuda", MUTED)])
    lines = machine + [("install the dependencies? [Y/n] _", ACCENT),
                       ("download the DINOv2 weights (~346 MB)? [Y/n]", MUTED)]
    if scanner:
        lines.append(("catalogue : the server sends it before each scan", OK))
    else:
        lines.append(("download the catalogue now? [Y/n]", MUTED))
    name = "1 安装 Setup.command" if mac else "1 安装 Setup.cmd"
    return svg(files(24, 40, [(name, "双击 · double-click")], (name,))
               + arrow(150, 62, 150, 92)
               + console(24, 100, 592, 64 + len(lines) * 20, "1 安装 Setup", lines)
               + t(612, 92, "按 Enter = 是 · Enter = yes", 12, ACCENT, anchor="end"),
               640, 180 + len(lines) * 20, "the setup asking before each step")


def pic_connect() -> str:
    return svg(window(20, 16, 250, 150, "Downloads (下载 · from the NAS)")
               + files(44, 70, [("server.key", "下载 · downloaded"), ("…", ""), ("", "")],
                       ("server.key",)).replace('x="314"', 'x="9999"')
               + arrow(280, 90, 330, 90)
               + console(340, 16, 280, 200, "2 连接服务器 Connect server", [
                   ("Server address [Enter = wuwa-server]:", MUTED), ("(Enter)", ACCENT),
                   ("Server key [Enter = Downloads]:", MUTED),
                   ("(Enter)", ACCENT), ("server: saved", OK)]),
               640, 232, "server.key downloaded from the NAS, then Enter in Connect server")


def pic_scan(launcher: str = "3 扫描 Scan") -> str:
    grid = "".join(box(330 + (i % 5) * 44, 70 + (i // 5) * 44, 38, 38, PANEL,
                       ACCENT if i == 7 else LINE, 6, 2 if i == 7 else 1) for i in range(15))
    return svg(console(20, 16, 280, 150, launcher, [
                   ("waiting for the game ...", MUTED), ("alt-tab into it", ACCENT),
                   ("[素材] view 3: +12 new", OK), ("selected: 面粉 拥有 440", OK)])
               + box(320, 16, 300, 220, PANEL2, LINE, 10) + t(334, 42, "背包 · the bag", 13, MUTED)
               + grid + arrow(578, 80, 578, 190) + t(590, 140, "滚", 13, ACCENT)
               + keycap(26, 186, "F9") + t(84, 211, "结束 · stop (everything kept)", 13, INK),
               640, 250, "the scan, the bag scrolled by hand, F9 to stop")


def pic_dashboard() -> str:
    return svg(window(20, 16, 600, 220, "http://127.0.0.1:4000")
               + t(44, 74, "总览", 20, INK, 700)
               + "".join(box(44 + i * 130, 90, 118, 60, PANEL, LINE, 8) for i in range(4))
               + "".join(box(44 + i * 70, 166, 60, 52, PANEL, LINE, 8) for i in range(8))
               + ring(40, 50, 90, 34), 640, 252, "the dashboard in a browser")


def pic_key() -> str:
    return svg(window(20, 16, 600, 210, "login.tailscale.com/admin/settings/keys")
               + t(44, 72, "Keys", 18, INK, 700)
               + t(44, 98, "Auth keys", 13, MUTED)
               + button(440, 58, 160, "Generate auth key…")
               + ring(434, 52, 172, 42)
               + box(44, 128, 552, 74, PANEL, LINE, 8)
               + t(60, 152, "Generated new key", 13, MUTED)
               + t(60, 180, "tskey-auth-kXXXXXXXXXX-XXXXXXXXXXXXXXXX", 14, ACCENT, mono=True)
               + button(500, 162, 80, "Copy"),
               640, 242, "Tailscale's keys page: generate an auth key and copy it")


def pic_project() -> str:
    """UGOS-like Create project, sketched: name, storage path, the pasted compose file."""
    side = "".join(t(40, 84 + k * 30, w, 13, ACCENT if w == "Project" else MUTED,
                     700 if w == "Project" else 400)
                   for k, w in enumerate(("Overview", "Project", "Container", "Image")))
    yaml = [("services:", MUTED), ("  net:", MUTED), ("    image: registry.k8s.io/pause:3.10", MUTED),
            ("  tailscale:", MUTED),
            ("    image: ghcr.io/oguessyky/wuwa-inventory-vision-tailscale…", MUTED), ("    environment:", MUTED),
            ("      TS_AUTHKEY: ${TS_AUTHKEY:-tskey-auth-PUT-YOURS-HERE}", ACCENT),
            ("      TS_HOSTNAME: ${TS_HOSTNAME:-wuwa-server}", MUTED), ("  wuwa:", MUTED),
            ("    image: ghcr.io/oguessyky/wuwa-inventory-vision-server…", MUTED)]
    editor = box(160, 176, 440, 30 + len(yaml) * 17, "#07090b", LINE, 6)
    for k, (line, colour) in enumerate(yaml):
        editor += t(170, 196 + k * 17, line, 11, colour, 600 if colour == ACCENT else 400,
                    mono=True)
    lit = 196 + 6 * 17                 # the key's line (D215 put net: above it)
    return svg(window(20, 16, 600, 430, "Docker")
               + f'<path d="M140 44v402" stroke="{LINE}"/>' + side
               + t(160, 72, "Create project · 创建项目", 15, INK, 700)
               + t(160, 98, "Name", 12, MUTED) + box(160, 104, 300, 24, PANEL, LINE, 6)
               + t(170, 121, "wuwa-inventory-vision", 13, INK, mono=True)
               + t(160, 148, "Storage path · 空文件夹 an empty folder", 12, MUTED)
               + box(160, 154, 440, 18, PANEL, LINE, 6)
               + t(170, 167, "/volume1/docker/wuwa-inventory-vision", 11, INK, mono=True)
               + editor + ring(164, lit - 14, 432, 20)
               + t(160, 396, "Compose configuration：粘贴整个文件，把 PUT-YOURS-HERE 换成你的钥匙", 12, ACCENT)
               + t(160, 414, "paste the whole file; put your key over PUT-YOURS-HERE", 11, MUTED)
               + button(500, 400, 100, "Deploy"),
               640, 462, "the NAS's Docker app: name, an empty folder, the compose file pasted, deploy")


def pic_open() -> str:
    return svg(phone(40, 6, "wuwa-server.….ts.net:4000")
               + t(230, 60, "手机或电脑，登录同一个 Tailscale：", 14, INK)
               + t(230, 84, "phone or PC, signed in to the same tailnet:", 13, MUTED)
               + box(230, 104, 380, 34, PANEL, ACCENT, 8, 2)
               + t(244, 126, "http://wuwa-server.your-tailnet.ts.net:4000", 13, ACCENT, mono=True)
               + t(230, 168, "用名字（…ts.net），不是 100.x 地址。", 13, MUTED)
               + t(230, 190, "Use the name (…ts.net), not the 100.x address.", 12, MUTED),
               640, 264, "the server's address opened on a phone")


def pic_catalogue() -> str:
    side = "".join(t(40, 84 + i * 30, w, 13, ACCENT if w == "更新" else MUTED, 700 if w == "更新" else 400)
                   for i, w in enumerate(("总览", "规划", "料理", "库存", "更新")))
    return svg(window(20, 16, 600, 210, "http://wuwa-server.….ts.net:4000/update")
               + f'<path d="M110 44v182" stroke="{LINE}"/>' + side
               + t(130, 76, "更新", 20, INK, 700)
               + box(130, 92, 470, 116, PANEL, LINE, 10)
               + t(148, 120, "从 Wiki 更新", 15, INK, 700)
               + t(148, 144, "只有点这个按钮时才会联网（wiki.kurobbs.com）", 12, MUTED)
               + button(148, 160, 120, "从 Wiki 更新") + ring(142, 154, 132, 42)
               + t(290, 180, "● 运行中…  物品与图标 3/7", 12, OK),
               640, 242, "the server's update page: fetch the catalogue from the wiki")


def pic_expiry() -> str:
    menu = (box(420, 112, 186, 92, PANEL, LINE, 8) + t(436, 136, "Edit machine name…", 13, MUTED)
            + t(436, 162, "Disable key expiry", 13, ACCENT, 700) + t(436, 188, "Remove…", 13, MUTED)
            + ring(426, 145, 174, 26))
    return svg(window(20, 16, 600, 200, "login.tailscale.com/admin/machines")
               + t(44, 72, "Machines", 18, INK, 700)
               + box(44, 86, 552, 30, PANEL, LINE, 6)
               + t(56, 106, "wuwa-server", 13, INK, 700, mono=True)
               + t(200, 106, "100.x.y.z", 12, MUTED, mono=True) + t(320, 106, "● Connected", 12, OK)
               + t(574, 106, "…", 16, ACCENT, 700) + menu, 640, 232,
               "Tailscale's machines page: disable key expiry for the server")


def pic_update() -> str:
    return svg(window(20, 16, 600, 120, "Docker · Project")
               + box(44, 58, 552, 40, PANEL, LINE, 8)
               + t(60, 83, "wuwa-inventory-vision", 14, INK, 700, mono=True) + t(290, 83, "● Running", 12, OK)
               + button(470, 63, 110, "Update") + ring(464, 57, 122, 42),
               640, 152, "the project's update button")


def pic_beside() -> str:
    rows = ""
    for k, (name, host, note) in enumerate((
            ("wuwa-inventory-vision", "wuwa-server", "你现在用的 · the one you use"),
            ("wuwa-inventory-vision-test", "wuwa-server-test", "试新版 · trying a version"))):
        y = 58 + k * 48
        rows += (box(44, y, 552, 40, PANEL, ACCENT if k else LINE, 8, 2 if k else 1)
                 + t(60, y + 25, name, 13, INK, 700, mono=True)
                 + t(300, y + 25, host, 12, ACCENT, mono=True) + t(420, y + 25, note, 11, MUTED))
    return svg(window(20, 16, 600, 160, "Docker · Project") + rows, 640, 192,
               "two servers side by side, each its own project and its own device")


def pic_move() -> str:
    return svg(window(20, 16, 280, 170, "旧的 · the old server's data")
               + files(44, 70, [("…/wuwa_inventory_vision/", ""), ("  wuwa.sqlite", ""),
                                ("  icons/", ""), ("  server.key", "")]).replace('x="314"', 'x="9999"')
               + arrow(306, 100, 346, 100)
               + t(326, 88, "复制", 12, ACCENT, anchor="middle")
               + window(352, 16, 268, 170, "新的 · its storage path")
               + files(374, 70, [("seed-data/", ""), ("data/", ""), ("tailscale-state/", "")],
                       ("seed-data/",)).replace('x="644"', 'x="9999"'),
               640, 200, "the old server's data folder copied into seed-data in the new project's folder")


#: Said in the first step on a PC (D184): a zip from a browser marks every file in it.
UNBLOCK = ('<p class="tip" lang="zh-CN">解压之前：右键下载的压缩包 → <b>属性</b> → 勾选最下面的 '
           '<b>解除锁定</b> → 确定。否则 Windows 会对每个文件问一次（“打开文件 - 安全警告 … 未知发布者 / '
           'Unknown Publisher”）。真的问了也没关系，按“运行”：这些都是这个包自己的文件。</p>'
           '<p class="tip" lang="en">Before unzipping: right-click the downloaded zip → '
           '<b>Properties</b> → tick <b>Unblock</b> at the bottom → OK. Otherwise Windows asks '
           'about each file ("Open File - Security Warning ... Unknown Publisher"); if it does, '
           '<b>Run</b> is safe: the files are this package\'s own.</p>')


# --- the three guides -----------------------------------------------------------------------

def guide_server() -> str:
    hero = ('<figure class="hero">' + svg(
        box(20, 40, 150, 90, PANEL2, LINE, 10) + t(95, 72, "电脑 · PC", 14, INK, 700, anchor="middle")
        + t(95, 96, "扫描器 scanner", 12, MUTED, anchor="middle")
        + arrow(178, 85, 238, 85) + t(208, 74, "Tailscale", 11, ACCENT, anchor="middle")
        + box(246, 20, 200, 130, PANEL2, ACCENT, 12, 2)
        + t(346, 46, "服务器 · the server", 14, INK, 700, anchor="middle")
        + box(262, 60, 168, 32, PANEL, LINE, 7) + t(346, 81, "Tailscale (wuwa-server)", 12, INK,
                                                    anchor="middle")
        + box(262, 102, 168, 32, PANEL, LINE, 7) + t(346, 123, "app · 127.0.0.1:4000", 12, INK,
                                                     anchor="middle")
        + arrow(454, 85, 514, 85) + t(484, 74, "Tailscale", 11, ACCENT, anchor="middle")
        + box(522, 40, 100, 90, PANEL2, LINE, 10) + t(572, 72, "手机", 14, INK, 700, anchor="middle")
        + t(572, 96, "phone · PC", 12, MUTED, anchor="middle"),
        640, 170, "the scanner sends to the server; phones and PCs of the tailnet open it")
        + '<figcaption lang="zh-CN">服务器只在你自己的 Tailscale 网里能打开：不开端口，不上公网。</figcaption>'
        '<figcaption lang="en">The server opens only inside your own tailnet: no port, never the '
        "internet.</figcaption></figure>")
    steps = [
        step(1, "拿一把 Tailscale 钥匙", "Get a Tailscale auth key",
             '打开 <a href="https://login.tailscale.com/admin/settings/keys">Tailscale 的 Keys 页</a>，'
             "按 Generate auth key，复制出来的 <code>tskey-auth-…</code>。一次性的就够了：只在第一次启动用。别给别人看。",
             'Open <a href="https://login.tailscale.com/admin/settings/keys">Tailscale\'s keys '
             "page</a>, press Generate auth key and copy the <code>tskey-auth-…</code>. A one-off "
             "key is enough: it is used once, on the first start. Keep it to yourself.", pic_key()),
        step(2, "在 Docker 应用里建项目", "Create the project in the Docker app",
             "NAS 的 Docker 应用 → <b>Project</b> → Create project："
             "名称 <code>wuwa-inventory-vision</code>；存储路径选一个<b>空文件夹</b>（数据就放在里面）；"
             "Compose configuration 粘贴整个 <code>docker-compose.yaml</code>（在发布页或这个文件夹里），"
             "把 <code>tskey-auth-PUT-YOURS-HERE</code> 换成你的钥匙 → <b>Deploy</b>。",
             "The NAS's Docker app → <b>Project</b> → Create project: name it "
             "<code>wuwa-inventory-vision</code>; for the storage path pick an <b>empty folder</b> "
             "(the data is kept there); under Compose configuration paste the whole "
             "<code>docker-compose.yaml</code> (on the release page, or in this folder) and put your "
             "key over <code>tskey-auth-PUT-YOURS-HERE</code> → <b>Deploy</b>. With plain Docker, "
             "the key may go in a <code>.env</code> instead.", pic_project()),
        step(3, "打开它", "Open it",
             "在登录了同一个 Tailscale 的手机或电脑上打开 "
             "<code>http://wuwa-server.&lt;你的 tailnet&gt;.ts.net:4000</code>。",
             "On a phone or PC signed in to the same tailnet, open "
             "<code>http://wuwa-server.&lt;your tailnet&gt;.ts.net:4000</code>.", pic_open()),
        step(4, "第一次：拉取图鉴", "The first time: fetch the catalogue",
             "全新的服务器还没有图鉴：没有物品名、图、食谱和养成表。打开它的 <b>更新</b> 页，按 "
             "<b>从 Wiki 更新</b>，从库洛官方 Wiki 下载（几分钟，页面会显示进度）。扫描器每次扫描前从服务器拿图鉴，"
             "所以要在第一次扫描之前做。",
             "A server started from nothing has no catalogue yet: no item names, pictures, recipes or "
             "builds. Open its <b>更新</b> page and press <b>从 Wiki 更新</b>; it downloads Kuro's "
             "official catalogue (a few minutes, the page shows how far). Scanners take it from the "
             "server before each scan, so do it before the first scan.", pic_catalogue()),
        step(5, "关掉钥匙过期", "Turn off key expiry",
             "Tailscale 的 Machines 页里会多一台 <code>wuwa-server</code>：点 … → Disable key expiry，"
             "否则半年后要重新登录。",
             "A <code>wuwa-server</code> appears on Tailscale's machines page: … → Disable key "
             "expiry, or it asks to log in again in six months (key expiry).", pic_expiry()),
        step(6, "连接扫描器", "Connect a scanner",
             "在 NAS 的文件管理器里，把存储路径里的 <code>data/server.key</code> 下载到装了扫描器的电脑（放在「下载」文件夹）。"
             "然后双击 <b>2 连接服务器 Connect server</b>：地址和钥匙都直接按回车，钥匙会从「下载」里自己找。",
             "In the NAS's file manager, download <code>data/server.key</code> from the storage path "
             "to the PC with the scanner (it lands in Downloads). Then double-click "
             "<b>2 连接服务器 Connect server</b> and press Enter at both questions: the key is taken from Downloads.", pic_connect()),
        step(7, "更新", "Updating",
             "在 Docker 应用里对这个项目按 <b>Update</b>：拉下新镜像，数据不动。扫描器也更新到同一版本。",
             "Press <b>Update</b> on the project in the Docker app: the new image is pulled and "
             "the data stays. Update the scanner to the same version.", pic_update()),
        step(8, "在旁边试新版", "Try a version beside the one you have",
             "再建一个项目，名称 <code>wuwa-inventory-vision-test</code>、另一个空文件夹，粘贴同一个文件，"
             "只改一个词：<code>TS_HOSTNAME</code> 那行的 <code>wuwa-server</code> 改成 <code>wuwa-server-test</code>。"
             "它是 Tailscale 里另一台设备、另一份数据，不影响原来的。",
             "A second project, <code>wuwa-inventory-vision-test</code>, in another empty folder, "
             "with the same file and one word changed: <code>wuwa-server</code> in the "
             "<code>TS_HOSTNAME</code> line, to <code>wuwa-server-test</code>. Another device on the "
             "tailnet with its own data; the first is untouched.", pic_beside()),
        step(9, "从旧的服务器搬过来", "Moving from the old server",
             "旧的服务器（自己编译的那种）的数据都在它的数据文件夹里：扫描、改过的名字、目标、底数、规划、"
             "抽卡记录和 <code>server.key</code>。按下面的顺序搬，什么都不会丢。",
             "Everything the old server (the one built from source) has is in its data folder: "
             "scans, names, targets, base amounts, plans, the pull history and "
             "<code>server.key</code>. Move it in this order and nothing is lost.", pic_move(),
             '<ol lang="zh-CN"><li>在 Docker 应用里<b>停掉</b>旧项目——先别删。</li>'
             "<li>在新项目要用的空文件夹里建 <code>seed-data/</code>，把旧的数据文件夹（旧项目 <code>.env</code> 里的 "
             "<code>WUWA_DATA</code>）里的东西整个复制进去。</li>"
             "<li>按上面 1–3、5 建新项目：第一次启动会把 seed-data 收进来，图鉴也在里面，第 4 步不用做。</li>"
             "<li>打开新地址，确认数据都在。<code>server.key</code> 也搬过来了，钥匙不变：扫描器只要用 "
             "<b>2 连接服务器</b> 换成新地址。</li><li>都没问题了，再删掉旧项目。</li></ol>"
             '<ol lang="en"><li><b>Stop</b> the old project in the Docker app -- do not delete it '
             "yet.</li><li>In the empty folder the new project will use, make <code>seed-data/</code> "
             "and copy into it everything in the old data folder (<code>WUWA_DATA</code> in the old "
             "project's <code>.env</code>).</li><li>Create the new project (1–3 and 5 above): its "
             "first start takes seed-data in, the catalogue with it, so step 4 is not needed.</li>"
             "<li>Open the new address and check your data is there. <code>server.key</code> came "
             "along, so the key is the same: a scanner only needs the new address (<b>2 连接服务器</b>)."
             "</li><li>When all is well, delete the old project.</li></ol>"
             '<p class="warn" lang="zh-CN">没复制数据就删旧项目，扫描以外的东西（改过的名字、目标、规划）都会没有。</p>'
             '<p class="warn" lang="en">Delete the old project without copying its data and what '
             "only it held -- names given on a phone, targets, plans -- is gone.</p>"),
    ]
    return page("WuWa Inventory Vision · 服务器 server",
                "家里一直开着的机器上的总览：用现成的镜像，在 NAS 的 Docker 应用里粘贴一个文件就部署，不用编译、不用 SSH、不用下载压缩包。",
                "The dashboard on a box that is always on: a ready-made image, deployed from the "
                "NAS's Docker app from one pasted file -- nothing to build, no SSH, no zip.", "".join(steps), hero)


def guide_scanner() -> str:
    steps = [
        step(1, "解压到一个不会再动的地方", "Unzip it somewhere it stays",
             "例如 <code>C:\\wuwa-scanner</code>。安装会用到里面的 Python，以后搬走文件夹就要重新安装。",
             "Such as <code>C:\\wuwa-scanner</code>. The setup builds on the Python inside it, so a "
             "folder moved later means setting up again.",
             pic_unzip("C:\\wuwa-scanner", [
                 ("1 安装 Setup.cmd", ""), ("2 连接服务器 Connect server.cmd", ""),
                 ("3 扫描 Scan.cmd", ""), ("5 卸载 Uninstall.cmd", "不用时 · to remove it"),
                 ("python/", "已带 Python · Python included"),
                 ("START-HERE.html", "这一页 · this page")],
                 ("1 安装 Setup.cmd", "2 连接服务器 Connect server.cmd", "3 扫描 Scan.cmd")), UNBLOCK),
        step(2, "双击 1 安装 Setup", "Double-click 1 安装 Setup",
             "它会说找到了什么，每一步都先问（按 Enter 就是“是”）。装依赖、显卡对应的 PyTorch 和识别模型；"
             "图鉴由服务器发过来，这里不用下。最后分别问要不要在桌面、开始菜单放快捷方式。",
             "It says what it found and asks before each step (Enter is yes): the packages, the "
             "PyTorch for your GPU and the recognition model. The catalogue comes from the server. "
             "Last, it asks about shortcuts, one place at a time: the Desktop, the Start menu.",
             pic_setup(True)),
        step(3, "双击 2 连接服务器 Connect server", "Double-click 2 连接服务器 Connect server",
             "先从 NAS 下载服务器的 <code>data/server.key</code>（放在「下载」文件夹）。地址直接按回车就是 <code>wuwa-server</code>，"
             "钥匙也直接按回车：会从「下载」里自己找。也可以贴上钥匙那一行。只要做一次。",
             "First download the server's <code>data/server.key</code> from the NAS (it lands in Downloads). "
             "For the address, Enter alone takes <code>wuwa-server</code>; for the key, Enter alone takes "
             "server.key from Downloads (pasting its one line works too). Once.", pic_connect()),
        step(4, "双击 3 扫描 Scan", "Double-click 3 扫描 Scan",
             "然后 Alt-Tab 切到游戏，打开背包，一页一页慢慢滚；点一下物品，名字和数量从详情读。"
             "按 <b>F9</b> 结束，读到的都会留下。每个标签扫完就发到服务器。",
             "Then alt-tab into the game, open the bag and scroll each tab a page at a time; click "
             "an item to read its name and count. <b>F9</b> stops, and everything read is kept. "
             "Each tab goes to the server as soon as it is finished.", pic_scan()),
        step(5, "在服务器上看结果", "See it on the server",
             "在手机上打开服务器的地址：总览、库存、材料……都是刚扫的。",
             "Open the server's address on your phone: 总览, 库存, 材料… as just scanned.",
             pic_open()),
    ]
    return page("WuWa Inventory Vision · 扫描器 scanner",
                "在有游戏的电脑上读背包，发到你的服务器。只读屏幕，不碰游戏文件。",
                "Reads the bag on the PC with the game and sends it to your server. Screen pixels "
                "only; the game's files are never touched.", "".join(steps))


def guide_full() -> str:
    steps = [
        step(1, "解压到一个不会再动的地方", "Unzip it somewhere it stays",
             "例如 <code>C:\\wuwa-vision</code>。安装会用到里面的 Python，以后搬走文件夹就要重新安装。",
             "Such as <code>C:\\wuwa-vision</code>. The setup builds on the Python inside it, so a "
             "folder moved later means setting up again.",
             pic_unzip("C:\\wuwa-vision", [
                 ("1 安装 Setup.cmd", ""), ("2 扫描 Scan.cmd", ""), ("3 总览 Dashboard.cmd", ""),
                 ("5 卸载 Uninstall.cmd", "不用时 · to remove it"),
                 ("python/", "已带 Python · Python included"), ("START-HERE.html", "这一页 · this page")],
                 ("1 安装 Setup.cmd", "2 扫描 Scan.cmd", "3 总览 Dashboard.cmd")), UNBLOCK),
        step(2, "双击 1 安装 Setup", "Double-click 1 安装 Setup",
             "它会说找到了什么，每一步都先问（按 Enter 就是“是”）：依赖、显卡对应的 PyTorch、识别模型，"
             "还有从库洛官方 Wiki 下载的图鉴（几分钟）。最后分别问要不要在桌面、开始菜单放快捷方式。",
             "It says what it found and asks before each step (Enter is yes): the packages, the "
             "PyTorch for your GPU, the recognition model, and the catalogue from Kuro's wiki (a "
             "few minutes). Last, it asks about shortcuts, one place at a time: the Desktop, the Start "
             "menu.",
             pic_setup(False)),
        step(3, "双击 2 扫描 Scan", "Double-click 2 扫描 Scan",
             "然后 Alt-Tab 切到游戏，打开背包，一页一页慢慢滚；点一下物品，名字和数量从详情读。"
             "按 <b>F9</b> 结束，读到的都会留下。",
             "Then alt-tab into the game, open the bag and scroll each tab a page at a time; click "
             "an item to read its name and count. <b>F9</b> stops, and everything read is kept.",
             pic_scan("2 扫描 Scan")),
        step(4, "双击 3 总览 Dashboard", "Double-click 3 总览 Dashboard",
             "在浏览器打开 <code>http://127.0.0.1:4000</code>。窗口开着页面就在；关掉窗口就停。",
             "Open <code>http://127.0.0.1:4000</code> in a browser. The pages run while its window "
             "is open; close it to stop them.", pic_dashboard()),
    ]
    return page("WuWa Inventory Vision · 完整版 full",
                "一台电脑上全都有：扫描器和总览。只读屏幕，不碰游戏文件，数据都在你自己电脑上。",
                "Everything on one PC: the scanner and the dashboard. Screen pixels only, and "
                "everything stays on your own computer.", "".join(steps))


# --- a Mac (D204; drawn for D228: the user, 2026-10-28, "for mac version guideline you didnt
# include like the visual there") -----------------------------------------------------------

def toggle(x: float, y: float, on: bool) -> str:
    """A switch as System Settings draws one."""
    return (box(x, y, 40, 22, ACCENT if on else PANEL, ACCENT if on else LINE, 11)
            + f'<circle cx="{x + (29 if on else 11)}" cy="{y + 11}" r="8" fill="{"#111" if on else MUTED}"/>')


def pic_brew() -> str:
    return svg(console(20, 16, 600, 150, "Terminal — 终端", [
                   ("$ brew install python@3.12", ACCENT),
                   ("==> Downloading python@3.12 ...", MUTED),
                   ("==> Pouring python@3.12 ...", MUTED),
                   ("python@3.12 is installed", OK)])
               + t(612, 190, "没有 Homebrew：先按 brew.sh 上的一行装好 · no Homebrew yet: brew.sh", 12,
                   MUTED, anchor="end"),
               640, 204, "Terminal: brew install python@3.12")


def pic_open_anyway() -> str:
    menu = box(40, 70, 190, 104, PANEL, LINE, 8) + "".join(
        t(56, 96 + i * 26, item, 13, ACCENT if i == 0 else INK, 700 if i == 0 else 400)
        for i, item in enumerate(("打开 · Open", "显示简介 · Get Info", "压缩 · Compress")))
    return svg(files(24, 30, [("1 安装 Setup.command", "右键 · right-click")],
                     ("1 安装 Setup.command",))
               + menu + ring(44, 76, 182, 28) + arrow(240, 98, 290, 98)
               + box(300, 30, 320, 170, PANEL2, LINE, 12)
               + t(318, 62, "无法验证开发者 · cannot verify the developer", 13, INK, 700)
               + t(318, 88, "确定要打开吗？ · Are you sure you want to open it?", 12, MUTED)
               + button(318, 150, 120, "取消 Cancel", lit=False) + button(480, 150, 120, "打开 Open")
               + ring(474, 144, 132, 42),
               640, 216, "the first time: right-click, Open, then Open again")


def pic_screen_recording() -> str:
    side = "".join(t(40, 86 + i * 28, item, 13, ACCENT if i == 2 else MUTED, 700 if i == 2 else 400)
                   for i, item in enumerate(("Wi-Fi", "通用 · General", "隐私与安全性 · Privacy",
                                             "桌面与程序坞 · Desktop")))
    rows = [("终端 · Terminal", True), ("Python", False), ("鸣潮 · the game", False)]
    body = "".join(box(250, 98 + i * 40, 350, 34, PANEL, LINE, 7) + t(266, 120 + i * 40, name, 13, INK)
                   + toggle(548, 104 + i * 40, on) for i, (name, on) in enumerate(rows))
    return svg(window(20, 16, 600, 240, "系统设置 · System Settings")
               + f'<path d="M230 44v212" stroke="{LINE}"/>' + side
               + t(250, 78, "屏幕与系统录音 · Screen & System Audio Recording", 14, INK, 700)
               + body + ring(244, 92, 362, 46)
               + t(250, 240, "只打开「终端」，然后重开终端 · Terminal only, then reopen Terminal", 12, ACCENT),
               640, 272, "System Settings: Screen Recording on for Terminal")


def pic_scan_mac() -> str:
    grid = "".join(box(330 + (i % 5) * 44, 70 + (i // 5) * 44, 38, 38, PANEL,
                       ACCENT if i == 7 else LINE, 6, 2 if i == 7 else 1) for i in range(15))
    return svg(console(20, 16, 280, 150, "扫描 Scan — Terminal", [
                   ("waiting for the game ...", MUTED), ("click the game window", ACCENT),
                   ("[素材] view 3: +12 new", OK), ("selected: 面粉 拥有 440", OK)])
               + box(320, 16, 300, 220, PANEL2, LINE, 10) + t(334, 42, "背包 · the bag", 13, MUTED)
               + grid + arrow(578, 80, 578, 190) + t(590, 140, "滚", 13, ACCENT)
               + keycap(26, 186, "Ctrl") + t(80, 211, "+", 15, ACCENT) + keycap(94, 186, "C")
               + t(150, 211, "结束 · stop", 13, INK),
               640, 250, "the scan on a Mac: click the game, scroll, Ctrl+C in Terminal to stop")


def guide_mac(scanner: bool) -> str:
    rows = ([("1 安装 Setup.command", ""), ("2 连接服务器 Connect server.command", ""),
             ("3 扫描 Scan.command", "")] if scanner else
            [("1 安装 Setup.command", ""), ("2 扫描 Scan.command", ""), ("3 总览 Dashboard.command", "")])
    rows.append(("5 卸载 Uninstall.command", "不用时 · to remove it"))
    rows.append(("START-HERE.html", "这一页 · this page"))
    scan = "3 扫描 Scan" if scanner else "2 扫描 Scan"
    steps = [
        step(1, "解压到一个不会再动的地方", "Unzip it somewhere it stays",
             "例如个人文件夹里的 <code>wuwa-vision</code>。以后搬走文件夹就要重新安装。",
             "Such as <code>wuwa-vision</code> in your home folder. A folder moved later means "
             "setting up again.",
             pic_unzip(f"~/{'wuwa-scanner' if scanner else 'wuwa-vision'}", rows,
                       tuple(r[0] for r in rows[:3]))),
        step(2, "装好 Python 3.12", "Install Python 3.12",
             "打开「终端」，运行 <code>brew install python@3.12</code>。还没有 Homebrew 的话，先按 "
             '<a href="https://brew.sh">brew.sh</a> 上的一行命令装好。',
             "Open Terminal and run <code>brew install python@3.12</code>. No Homebrew yet? Its "
             'one line is on <a href="https://brew.sh">brew.sh</a>.', pic_brew()),
        step(3, "双击 1 安装 Setup", "Double-click 1 安装 Setup",
             "第一次 macOS 会说「无法验证开发者」：右键点它 → <b>打开</b> → 再点 <b>打开</b>。"
             "然后它会说找到了什么，每一步都先问（按 Enter 就是“是”）"
             + ("；图鉴由服务器发过来，这里不用下。" if scanner else "，包括从库洛官方 Wiki 下载的图鉴。")
             + "最后分别问要不要在桌面、「应用程序」（启动台、聚焦搜索）放快捷方式。",
             "The first time, macOS says it cannot verify the developer: right-click it → "
             "<b>Open</b> → <b>Open</b>. Then it says what it found and asks before each step "
             "(Enter is yes)" + ("; the catalogue comes from the server." if scanner
                                 else ", the catalogue from Kuro's wiki among them.")
             + " Last, it asks about shortcuts, one place at a time: the Desktop, Applications "
             "(Launchpad, Spotlight).",
             pic_open_anyway(), pic_setup(scanner, mac=True)),
        step(4, "允许「屏幕录制」", "Allow Screen Recording",
             "macOS 不让任何程序读别的窗口，除非你同意：<b>系统设置 → 隐私与安全性 → 屏幕与系统录音</b>，"
             "打开「终端」（不是 Python，也不是游戏），然后关掉终端再打开。",
             "macOS lets no program read another's window unless you agree: <b>System Settings → "
             "Privacy & Security → Screen & System Audio Recording</b>, turn on Terminal (not "
             "Python, not the game), then quit and reopen Terminal.", pic_screen_recording()),
    ]
    if scanner:
        steps.append(step(5, "双击 2 连接服务器 Connect server", "Double-click 2 连接服务器 Connect server",
             "先从 NAS 下载服务器的 <code>data/server.key</code>（放在「下载」文件夹）。地址和钥匙都直接按回车。只要做一次。",
             "First download the server's <code>data/server.key</code> from the NAS (it lands in "
             "Downloads). Press Enter at both questions. Once.", pic_connect()))
    steps.append(step(len(steps) + 1, f"双击 {scan}", f"Double-click {scan}",
         "<b>点一下游戏窗口</b>：在 Mac 上只有点进去的窗口才算在最前面。打开背包，慢慢滚每个分页；"
         "扫完回到终端按 <b>Ctrl+C</b>。在 Mac 上它只读不点，不会替你按任何键。",
         "<b>Click the game window</b>: on a Mac only the window clicked into is in front. Open "
         "the bag and scroll each tab slowly; when done, press <b>Ctrl+C</b> in Terminal. On a "
         "Mac it only reads: it never presses a key for you.", pic_scan_mac()))
    if scanner:
        steps.append(step(len(steps) + 1, "在服务器上看结果", "See it on the server",
             "在手机上打开服务器的地址：总览、库存、材料……都是刚扫的。",
             "Open the server's address on your phone: 总览, 库存, 材料… as just scanned.",
             pic_open()))
    else:
        steps.append(step(len(steps) + 1, "双击 3 总览 Dashboard", "Double-click 3 总览 Dashboard",
             "在浏览器打开 <code>http://127.0.0.1:4000</code>。窗口开着页面就在；关掉窗口就停。",
             "Open <code>http://127.0.0.1:4000</code> in a browser. The pages run while its window "
             "is open; close it to stop them.", pic_dashboard()))
    title = "Mac 扫描端 mac-scanner" if scanner else "Mac 完整版 mac-full"
    return page(f"WuWa Inventory Vision · {title}",
                ("在 Mac 上读背包，发到你的服务器。" if scanner else "一台 Mac 上全都有：扫描和页面。")
                + "用库洛官方的 Mac 客户端；只读屏幕，不碰游戏文件。",
                ("Reads the bag on a Mac and sends it to your server. " if scanner
                 else "Everything on one Mac: the scanner and the pages. ")
                + "With Kuro's own Mac client; screen pixels only, the game's files never touched.",
                "".join(steps))


def pages() -> dict[str, str]:
    return {"full": guide_full(), "scanner": guide_scanner(), "server": guide_server(),
            "mac-full": guide_mac(False), "mac-scanner": guide_mac(True)}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, text in pages().items():
        (OUT / f"{kind}.html").write_text(text, encoding="utf-8", newline="\n")
        print(f"{kind}.html  {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
