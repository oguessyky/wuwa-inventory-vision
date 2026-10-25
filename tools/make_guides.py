# Copyright 2026 oguessyky
# SPDX-License-Identifier: Apache-2.0
# Part of WuWa Inventory Vision (https://github.com/oguessyky). Keep this notice: see NOTICE.
# ruff: noqa: E501 -- the pages' words, Chinese and English, read better unbroken
"""The guides with pictures, one per release package (PLAN.md D185).

    uv run python tools/make_guides.py        writes deploy/release/guides/{full,scanner,home}.html

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
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'font-family="{esc(family)}" text-anchor="{anchor}">{esc(s)}</text>')


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


def pic_setup(scanner: bool) -> str:
    lines = [("machine   : Windows AMD64", MUTED), ("  gpu     : NVIDIA GeForce RTX ...", MUTED),
             ("torch     : cuda", MUTED), ("install the dependencies? [Y/n] _", ACCENT),
             ("download the DINOv2 weights (~346 MB)? [Y/n]", MUTED)]
    if scanner:
        lines.append(("catalogue : the home sends it before each scan", OK))
    else:
        lines.append(("download the catalogue now? [Y/n]", MUTED))
    return svg(files(24, 40, [("1 安装 Setup.cmd", "双击 · double-click")], ("1 安装 Setup.cmd",))
               + arrow(150, 62, 150, 92)
               + console(24, 100, 592, 64 + len(lines) * 20, "1 安装 Setup", lines)
               + t(612, 92, "按 Enter = 是 · Enter = yes", 12, ACCENT, anchor="end"),
               640, 180 + len(lines) * 20, "the setup asking before each step")


def pic_connect() -> str:
    return svg(window(20, 16, 250, 150, "data/ (主机 · the home)")
               + files(44, 70, [("home.key", "1 行"), ("wuwa.sqlite", ""), ("icons/", "")],
                       ("home.key",)).replace('x="314"', 'x="9999"')
               + arrow(280, 90, 330, 90)
               + console(340, 16, 280, 200, "2 连接主机 Connect home", [
                   ("Home address:", MUTED), ("http://wuwa-home.", ACCENT),
                   ("  your-tailnet.ts.net:4000", ACCENT), ("Home key (home.key):", MUTED),
                   ("3f9c…(paste)", ACCENT), ("home: saved", OK)]),
               640, 232, "the key from home.key, pasted into Connect home")


def pic_scan() -> str:
    grid = "".join(box(330 + (i % 5) * 44, 70 + (i // 5) * 44, 38, 38, PANEL,
                       ACCENT if i == 7 else LINE, 6, 2 if i == 7 else 1) for i in range(15))
    return svg(console(20, 16, 280, 150, "3 扫描 Scan", [
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


def pic_env() -> str:
    lines = [("TS_AUTHKEY=tskey-auth-kXXXX…", ACCENT),
             ("# TS_HOSTNAME=wuwa-home", MUTED), ("# WUWA_NAME=wuwa-home", MUTED),
             ("# WUWA_DATA=./data", MUTED), ("# WUWA_VERSION=latest", MUTED)]
    body = window(20, 16, 600, 60 + len(lines) * 26, ".env  (复制自 .env.example)")
    for i, (line, colour) in enumerate(lines):
        body += t(44, 70 + i * 26, line, 14, colour, 600 if i == 0 else 400, mono=True)
    body += ring(34, 50, 330, 28) + t(380, 70, "← 只要填这一行 · only this line", 13, ACCENT)
    return svg(body, 640, 92 + len(lines) * 26, "the .env file with the auth key on its first line")


def pic_project() -> str:
    side = "".join(t(40, 84 + i * 30, s, 13, ACCENT if s == "Project" else MUTED,
                     700 if s == "Project" else 400)
                   for i, s in enumerate(("Overview", "Container", "Image", "Project")))
    return svg(window(20, 16, 600, 236, "Docker")
               + f'<path d="M140 44v208" stroke="{LINE}"/>' + side
               + t(160, 74, "Create project · 创建项目", 15, INK, 700)
               + t(160, 104, "Name", 12, MUTED) + box(240, 90, 200, 24, PANEL, LINE, 6)
               + t(250, 107, "wuwa-home", 13, INK, mono=True)
               + t(160, 136, "Path", 12, MUTED) + box(240, 122, 360, 24, PANEL, LINE, 6)
               + t(250, 139, "/volume1/docker/wuwa-home", 13, INK, mono=True)
               + t(160, 170, "Compose", 12, MUTED)
               + t(240, 170, "docker-compose.yaml  ✓ found", 13, OK, mono=True)
               + button(500, 206, 100, "Deploy") + ring(494, 200, 112, 42),
               640, 268, "the NAS's Docker app: create a project in the folder, deploy")


def pic_open() -> str:
    return svg(phone(40, 6, "wuwa-home.….ts.net:4000")
               + t(230, 60, "手机或电脑，登录同一个 Tailscale：", 14, INK)
               + t(230, 84, "phone or PC, signed in to the same tailnet:", 13, MUTED)
               + box(230, 104, 380, 34, PANEL, ACCENT, 8, 2)
               + t(244, 126, "http://wuwa-home.your-tailnet.ts.net:4000", 13, ACCENT, mono=True)
               + t(230, 168, "用名字（…ts.net），不是 100.x 地址。", 13, MUTED)
               + t(230, 190, "Use the name (…ts.net), not the 100.x address.", 12, MUTED),
               640, 264, "the home's address opened on a phone")


def pic_expiry() -> str:
    menu = (box(420, 112, 186, 92, PANEL, LINE, 8) + t(436, 136, "Edit machine name…", 13, MUTED)
            + t(436, 162, "Disable key expiry", 13, ACCENT, 700) + t(436, 188, "Remove…", 13, MUTED)
            + ring(426, 145, 174, 26))
    return svg(window(20, 16, 600, 200, "login.tailscale.com/admin/machines")
               + t(44, 72, "Machines", 18, INK, 700)
               + box(44, 86, 552, 30, PANEL, LINE, 6)
               + t(56, 106, "wuwa-home", 13, INK, 700, mono=True)
               + t(200, 106, "100.x.y.z", 12, MUTED, mono=True) + t(320, 106, "● Connected", 12, OK)
               + t(574, 106, "…", 16, ACCENT, 700) + menu, 640, 232,
               "Tailscale's machines page: disable key expiry for the home")


def pic_update() -> str:
    return svg(window(20, 16, 600, 120, "Docker · Project")
               + box(44, 58, 552, 40, PANEL, LINE, 8)
               + t(60, 83, "wuwa-home", 14, INK, 700, mono=True) + t(220, 83, "● Running", 12, OK)
               + button(470, 63, 110, "Update") + ring(464, 57, 122, 42),
               640, 152, "the project's update button")


def pic_beside() -> str:
    rows = ""
    for i, (name, note) in enumerate((("wuwa-home", "你现在用的 · the one you use"),
                                      ("wuwa-home-test", "试新版 · trying a version"))):
        y = 58 + i * 48
        rows += (box(44, y, 552, 40, PANEL, ACCENT if i else LINE, 8, 2 if i else 1)
                 + t(60, y + 25, name, 14, INK, 700, mono=True) + t(240, y + 25, "● Running", 12, OK)
                 + t(340, y + 25, note, 12, MUTED))
    return svg(window(20, 16, 600, 160, "Docker · Project") + rows, 640, 192,
               "two homes side by side, each its own project and its own device")


def pic_move() -> str:
    return svg(window(20, 16, 280, 170, "旧的 · the old home")
               + files(44, 70, [("…/wuwa_inventory_vision/", ""), ("  wuwa.sqlite", ""),
                                ("  icons/", ""), ("  home.key", "")]).replace('x="314"', 'x="9999"')
               + arrow(306, 100, 346, 100)
               + t(326, 88, "复制", 12, ACCENT, anchor="middle")
               + window(352, 16, 268, 170, "新的 · the new wuwa-home/")
               + files(374, 70, [("docker-compose.yaml", ""), (".env", ""),
                                 ("seed-data/", ""), ("tailscale/", "")],
                       ("seed-data/",)).replace('x="644"', 'x="9999"'),
               640, 200, "the old home's data folder copied into seed-data of the new one")


# --- the three guides -----------------------------------------------------------------------

def guide_home() -> str:
    hero = ('<figure class="hero">' + svg(
        box(20, 40, 150, 90, PANEL2, LINE, 10) + t(95, 72, "电脑 · PC", 14, INK, 700, anchor="middle")
        + t(95, 96, "扫描器 scanner", 12, MUTED, anchor="middle")
        + arrow(178, 85, 238, 85) + t(208, 74, "Tailscale", 11, ACCENT, anchor="middle")
        + box(246, 20, 200, 130, PANEL2, ACCENT, 12, 2)
        + t(346, 46, "主机 · the home", 14, INK, 700, anchor="middle")
        + box(262, 60, 168, 32, PANEL, LINE, 7) + t(346, 81, "Tailscale (wuwa-home)", 12, INK,
                                                    anchor="middle")
        + box(262, 102, 168, 32, PANEL, LINE, 7) + t(346, 123, "app · 127.0.0.1:4000", 12, INK,
                                                     anchor="middle")
        + arrow(454, 85, 514, 85) + t(484, 74, "Tailscale", 11, ACCENT, anchor="middle")
        + box(522, 40, 100, 90, PANEL2, LINE, 10) + t(572, 72, "手机", 14, INK, 700, anchor="middle")
        + t(572, 96, "phone · PC", 12, MUTED, anchor="middle"),
        640, 170, "the scanner sends to the home; phones and PCs of the tailnet open it")
        + '<figcaption lang="zh-CN">主机只在你自己的 Tailscale 网里能打开：不开端口，不上公网。</figcaption>'
        '<figcaption lang="en">The home opens only inside your own tailnet: no port, never the '
        "internet.</figcaption></figure>")
    steps = [
        step(1, "把文件夹放到 NAS 上", "Put the folder on the NAS",
             "解压到 NAS 上一个固定的文件夹，例如 <code>/volume1/docker/wuwa-home</code>。"
             "<code>data/</code> 和 <code>tailscale-state/</code> 会在第一次启动时自己出现。",
             "Unzip it into a folder the NAS keeps, e.g. <code>/volume1/docker/wuwa-home</code>. "
             "<code>data/</code> and <code>tailscale-state/</code> appear on the first start.",
             pic_unzip("/volume1/docker/wuwa-home", [
                 ("docker-compose.yaml", ""), (".env.example", "复制成 .env · copy to .env"),
                 ("tailscale/serve.json", ""), ("START-HERE.html", "这一页 · this page"),
                 ("data/", "第一次启动后 · after the first start")], ())),
        step(2, "拿一把 Tailscale 钥匙", "Get a Tailscale auth key",
             '打开 <a href="https://login.tailscale.com/admin/settings/keys">Tailscale 的 Keys 页</a>，'
             "按 Generate auth key，复制出来的 <code>tskey-auth-…</code>。一次性的就够了：只在第一次启动用。",
             'Open <a href="https://login.tailscale.com/admin/settings/keys">Tailscale\'s keys '
             "page</a>, press Generate auth key and copy the <code>tskey-auth-…</code>. A one-off "
             "key is enough: it is used once, on the first start.", pic_key()),
        step(3, "填好 .env", "Fill in .env",
             "把 <code>.env.example</code> 复制成 <code>.env</code>，第一行 <code>TS_AUTHKEY=</code> "
             "后面贴上钥匙。其余都有默认值。",
             "Copy <code>.env.example</code> to <code>.env</code> and paste the key after "
             "<code>TS_AUTHKEY=</code> on its first line. Everything else has a default.",
             pic_env()),
        step(4, "在 Docker 应用里部署", "Deploy it from the Docker app",
             "NAS 的 Docker 应用 → <b>Project</b>（项目 / Compose / Stacks）→ 新建，路径选这个文件夹，"
             "它会找到 <code>docker-compose.yaml</code> → 部署。它会下载两个镜像并启动。",
             "The NAS's Docker app → <b>Project</b> (Compose, Stacks) → create, in this folder; it "
             "finds <code>docker-compose.yaml</code> → deploy. It pulls the two images and starts "
             "them.", pic_project()),
        step(5, "打开它", "Open it",
             "在登录了同一个 Tailscale 的手机或电脑上打开 "
             "<code>http://wuwa-home.&lt;你的 tailnet&gt;.ts.net:4000</code>。",
             "On a phone or PC signed in to the same tailnet, open "
             "<code>http://wuwa-home.&lt;your tailnet&gt;.ts.net:4000</code>.", pic_open()),
        step(6, "关掉钥匙过期", "Turn off key expiry",
             "Tailscale 的 Machines 页里会多一台 <code>wuwa-home</code>：点 … → Disable key expiry，"
             "否则半年后要重新登录。",
             "A <code>wuwa-home</code> appears on Tailscale's machines page: … → Disable key "
             "expiry, or it asks to log in again in six months (key expiry).", pic_expiry()),
        step(7, "连接扫描器", "Connect a scanner",
             "扫描器要的钥匙是 <code>data/home.key</code> 里那一行（NAS 的文件管理器能打开）。"
             "在装了扫描器的电脑上双击 <b>2 连接主机 Connect home</b>，贴上地址和钥匙。",
             "The key a scanner needs is the one line of <code>data/home.key</code> (the NAS's "
             "file manager opens it). On the PC with the scanner, double-click "
             "<b>2 连接主机 Connect home</b> and paste the address and the key.", pic_connect()),
        step(8, "更新", "Updating",
             "在 Docker 应用里对这个项目按 <b>Update</b>：拉下新镜像，数据不动。扫描器也更新到同一版本。",
             "Press <b>Update</b> on the project in the Docker app: the new image is pulled and "
             "the data stays. Update the scanner to the same version.", pic_update()),
        step(9, "在旁边试新版", "Try a version beside the one you have",
             "再建一个文件夹放这些文件，<code>.env</code> 里写 <code>TS_HOSTNAME=wuwa-home-test</code> 和 "
             "<code>WUWA_NAME=wuwa-home-test</code>，部署成第二个项目。它是 Tailscale 里另一台设备、"
             "另一份数据，不影响原来的。",
             "Another folder with these files, <code>TS_HOSTNAME=wuwa-home-test</code> and "
             "<code>WUWA_NAME=wuwa-home-test</code> in its <code>.env</code>, deployed as a second "
             "project: another device on the tailnet with its own data; the first is untouched.",
             pic_beside()),
        step(10, "从旧的主机搬过来", "Moving from the old home",
             "旧的主机（自己编译的那种）的数据都在它的数据文件夹里：扫描、改过的名字、目标、底数、规划、"
             "抽卡记录和 <code>home.key</code>。按下面的顺序搬，什么都不会丢。",
             "Everything the old home (the one built from source) has is in its data folder: "
             "scans, names, targets, base amounts, plans, the pull history and "
             "<code>home.key</code>. Move it in this order and nothing is lost.", pic_move(),
             '<ol lang="zh-CN"><li>在 Docker 应用里<b>停掉</b>旧项目——先别删。</li>'
             "<li>找到它的数据文件夹（旧项目 <code>.env</code> 里的 <code>WUWA_DATA</code>），整个复制到新文件夹的 "
             "<code>seed-data/</code> 里。</li><li>按上面 1–6 部署新的：第一次启动会把 seed-data 收进来。</li>"
             "<li>打开新地址，确认数据都在。<code>home.key</code> 也搬过来了，钥匙不变：扫描器只要用 "
             "<b>2 连接主机</b> 换成新地址。</li><li>都没问题了，再删掉旧项目。</li></ol>"
             '<ol lang="en"><li><b>Stop</b> the old project in the Docker app -- do not delete it '
             "yet.</li><li>Find its data folder (<code>WUWA_DATA</code> in the old project's "
             "<code>.env</code>) and copy all of it into <code>seed-data/</code> of the new "
             "folder.</li><li>Deploy the new one (1–6 above): its first start takes seed-data in.</li>"
             "<li>Open the new address and check your data is there. <code>home.key</code> came "
             "along, so the key is the same: a scanner only needs the new address (<b>2 连接主机</b>)."
             "</li><li>When all is well, delete the old project.</li></ol>"
             '<p class="warn" lang="zh-CN">没复制数据就删旧项目，扫描以外的东西（改过的名字、目标、规划）都会没有。</p>'
             '<p class="warn" lang="en">Delete the old project without copying its data and what '
             "only it held -- names given on a phone, targets, plans -- is gone.</p>"),
    ]
    return page("WuWa Inventory Vision · 主机 home",
                "家里一直开着的机器上的总览：用现成的镜像，在 NAS 的 Docker 应用里部署，不用编译、不用 SSH。",
                "The dashboard on a box that is always on: a ready-made image, deployed from the "
                "NAS's Docker app -- nothing to build, no SSH.", "".join(steps), hero)


def guide_scanner() -> str:
    steps = [
        step(1, "解压到一个不会再动的地方", "Unzip it somewhere it stays",
             "例如 <code>C:\\wuwa-scanner</code>。安装会用到里面的 Python，以后搬走文件夹就要重新安装。",
             "Such as <code>C:\\wuwa-scanner</code>. The setup builds on the Python inside it, so a "
             "folder moved later means setting up again.",
             pic_unzip("C:\\wuwa-scanner", [
                 ("1 安装 Setup.cmd", ""), ("2 连接主机 Connect home.cmd", ""),
                 ("3 扫描 Scan.cmd", ""), ("python/", "已带 Python · Python included"),
                 ("START-HERE.html", "这一页 · this page")],
                 ("1 安装 Setup.cmd", "2 连接主机 Connect home.cmd", "3 扫描 Scan.cmd"))),
        step(2, "双击 1 安装 Setup", "Double-click 1 安装 Setup",
             "它会说找到了什么，每一步都先问（按 Enter 就是“是”）。装依赖、显卡对应的 PyTorch 和识别模型；"
             "图鉴由主机发过来，这里不用下。",
             "It says what it found and asks before each step (Enter is yes): the packages, the "
             "PyTorch for your GPU and the recognition model. The catalogue comes from the home.",
             pic_setup(True)),
        step(3, "双击 2 连接主机 Connect home", "Double-click 2 连接主机 Connect home",
             "贴上主机的地址和钥匙（主机 <code>data/home.key</code> 里那一行）。只要做一次。",
             "Paste the home's address and its key (the one line of <code>data/home.key</code> on "
             "the home). Once.", pic_connect()),
        step(4, "双击 3 扫描 Scan", "Double-click 3 扫描 Scan",
             "然后 Alt-Tab 切到游戏，打开背包，一页一页慢慢滚；点一下物品，名字和数量从详情读。"
             "按 <b>F9</b> 结束，读到的都会留下。每个标签扫完就发到主机。",
             "Then alt-tab into the game, open the bag and scroll each tab a page at a time; click "
             "an item to read its name and count. <b>F9</b> stops, and everything read is kept. "
             "Each tab goes home as soon as it is finished.", pic_scan()),
        step(5, "在主机上看结果", "See it on the home",
             "在手机上打开主机的地址：总览、库存、材料……都是刚扫的。",
             "Open the home's address on your phone: 总览, 库存, 材料… as just scanned.",
             pic_open()),
    ]
    return page("WuWa Inventory Vision · 扫描器 scanner",
                "在有游戏的电脑上读背包，发到你的主机。只读屏幕，不碰游戏文件。",
                "Reads the bag on the PC with the game and sends it to your home. Screen pixels "
                "only; the game's files are never touched.", "".join(steps))


def guide_full() -> str:
    steps = [
        step(1, "解压到一个不会再动的地方", "Unzip it somewhere it stays",
             "例如 <code>C:\\wuwa-vision</code>。安装会用到里面的 Python，以后搬走文件夹就要重新安装。",
             "Such as <code>C:\\wuwa-vision</code>. The setup builds on the Python inside it, so a "
             "folder moved later means setting up again.",
             pic_unzip("C:\\wuwa-vision", [
                 ("1 安装 Setup.cmd", ""), ("2 扫描 Scan.cmd", ""), ("3 总览 Dashboard.cmd", ""),
                 ("python/", "已带 Python · Python included"), ("START-HERE.html", "这一页 · this page")],
                 ("1 安装 Setup.cmd", "2 扫描 Scan.cmd", "3 总览 Dashboard.cmd"))),
        step(2, "双击 1 安装 Setup", "Double-click 1 安装 Setup",
             "它会说找到了什么，每一步都先问（按 Enter 就是“是”）：依赖、显卡对应的 PyTorch、识别模型，"
             "还有从库洛官方 Wiki 下载的图鉴（几分钟）。",
             "It says what it found and asks before each step (Enter is yes): the packages, the "
             "PyTorch for your GPU, the recognition model, and the catalogue from Kuro's wiki (a "
             "few minutes).", pic_setup(False)),
        step(3, "双击 2 扫描 Scan", "Double-click 2 扫描 Scan",
             "然后 Alt-Tab 切到游戏，打开背包，一页一页慢慢滚；点一下物品，名字和数量从详情读。"
             "按 <b>F9</b> 结束，读到的都会留下。",
             "Then alt-tab into the game, open the bag and scroll each tab a page at a time; click "
             "an item to read its name and count. <b>F9</b> stops, and everything read is kept.",
             pic_scan()),
        step(4, "双击 3 总览 Dashboard", "Double-click 3 总览 Dashboard",
             "在浏览器打开 <code>http://127.0.0.1:4000</code>。窗口开着页面就在；关掉窗口就停。",
             "Open <code>http://127.0.0.1:4000</code> in a browser. The pages run while its window "
             "is open; close it to stop them.", pic_dashboard()),
    ]
    return page("WuWa Inventory Vision · 完整版 full",
                "一台电脑上全都有：扫描器和总览。只读屏幕，不碰游戏文件，数据都在你自己电脑上。",
                "Everything on one PC: the scanner and the dashboard. Screen pixels only, and "
                "everything stays on your own computer.", "".join(steps))


def pages() -> dict[str, str]:
    return {"full": guide_full(), "scanner": guide_scanner(), "home": guide_home()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for kind, text in pages().items():
        (OUT / f"{kind}.html").write_text(text, encoding="utf-8", newline="\n")
        print(f"{kind}.html  {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
