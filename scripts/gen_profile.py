#!/usr/bin/env python3
"""Build the profile: animated SVG pieces + README.md.

    python3 scripts/gen_profile.py

Inputs : profile.config.json   (content + "theme" -- edit this one)
         assets/profile.json   (live data, refreshed by scripts/fetch_profile_data.py)
Outputs: assets/stage/*.svg + README.md   (generated, never hand-edit)

Themes (profile.config.json -> "theme")
  blueprint : engineering drawing. White line work on blueprint blue, crop marks,
              ruler ticks, sharp corners, title block.
  gameboy   : DMG LCD. Light green screen panels, hard pixel shadows, and headings
              drawn as real 5x7 pixel grids instead of font glyphs.
  arcade    : neon cabinet. Dark panels, glow accents, scanlines.

GitHub renders README SVGs as <img>: CSS animation inside the SVG works, links do
not, and the camo proxy strips external fonts/images. So every clickable thing is its
own small SVG wrapped in <a> in the README, and all artwork is vector-only with
generic font stacks.
"""
import datetime
import glob
import json
import os
import re
import zlib

W = 900
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "profile.config.json")))
DATA = json.load(open(os.path.join(ROOT, "assets", "profile.json")))
OUT_DIR = os.path.join(ROOT, "assets", "stage")
REL = "assets/stage"

# ---------------------------------------------------------------- themes
THEMES = {
    "blueprint": {
        "style": "blueprint",
        "bg": "#0a2148", "bg2": "#123a72", "card": "#0c2750",
        "ink": "#eef4ff", "dim": "#93b6e2", "line": "#cfe0f7",
        "accents": ["#6fd3ff", "#7dffd4", "#ffcf6b", "#ff9ec4"],
        "radius": 0, "border": 1.4, "shadow": False, "pixel": False,
        "grid": "blueprint", "deco": "crop",
        "title_font": "'Courier New',Courier,monospace", "title_spacing": "3",
        "vig": .5,
    },
    "gameboy": {
        "style": "gameboy",
        "bg": "#a9c631", "bg2": "#b9d542", "card": "#9cba23",
        "ink": "#0e2a10", "dim": "#2f4d1c", "line": "#12300f",
        "accents": ["#12300f", "#315a1f", "#0e2a10", "#315a1f"],
        "radius": 0, "border": 2.5, "shadow": True, "pixel": True,
        "grid": "dither", "deco": "pixels",
        "title_font": "'Courier New',Courier,monospace", "title_spacing": "1",
        "vig": .12,
    },
    "arcade": {
        "style": "arcade",
        "bg": "#070b18", "bg2": "#101a38", "card": "#0b1428",
        "ink": "#e9f4ff", "dim": "#8299bd", "line": "#3ce6ff",
        "accents": ["#3ce6ff", "#ff4d9d", "#ffc447", "#8dff5a"],
        "radius": 10, "border": 1.5, "shadow": False, "pixel": False,
        "grid": "arcade", "deco": "brackets",
        "title_font": "'Arial Black','Helvetica Neue',Arial,sans-serif", "title_spacing": "1.5",
        "vig": .5,
    },
}
T = THEMES[CFG.get("theme", "blueprint")]
BG, BG2, CARD = T["bg"], T["bg2"], T["card"]
INK, DIM, LINE = T["ink"], T["dim"], T["line"]
ACCENTS, R = T["accents"], T["radius"]
GB = T["style"] == "gameboy"

MONO = "'JetBrains Mono','Fira Code','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "'Arial Black','Helvetica Neue',Arial,sans-serif"

# ---------------------------------------------------------------- 5x7 dot matrix
DOT = {
    "A": ".###.|#...#|#...#|#####|#...#|#...#|#...#", "B": "####.|#...#|#...#|####.|#...#|#...#|####.",
    "C": ".###.|#...#|#....|#....|#....|#...#|.###.", "D": "####.|#...#|#...#|#...#|#...#|#...#|####.",
    "E": "#####|#....|#....|####.|#....|#....|#####", "F": "#####|#....|#....|####.|#....|#....|#....",
    "G": ".###.|#...#|#....|#.###|#...#|#...#|.###.", "H": "#...#|#...#|#...#|#####|#...#|#...#|#...#",
    "I": "#####|..#..|..#..|..#..|..#..|..#..|#####", "J": "..###|...#.|...#.|...#.|...#.|#..#.|.##..",
    "K": "#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#", "L": "#....|#....|#....|#....|#....|#....|#####",
    "M": "#...#|##.##|#.#.#|#...#|#...#|#...#|#...#", "N": "#...#|##..#|#.#.#|#..##|#...#|#...#|#...#",
    "O": ".###.|#...#|#...#|#...#|#...#|#...#|.###.", "P": "####.|#...#|#...#|####.|#....|#....|#....",
    "Q": ".###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#", "R": "####.|#...#|#...#|####.|#.#..|#..#.|#...#",
    "S": ".####|#....|#....|.###.|....#|....#|####.", "T": "#####|..#..|..#..|..#..|..#..|..#..|..#..",
    "U": "#...#|#...#|#...#|#...#|#...#|#...#|.###.", "V": "#...#|#...#|#...#|#...#|#...#|.#.#.|..#..",
    "W": "#...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#", "X": "#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#",
    "Y": "#...#|#...#|.#.#.|..#..|..#..|..#..|..#..", "Z": "#####|....#|...#.|..#..|.#...|#....|#####",
    "0": ".###.|#...#|#..##|#.#.#|##..#|#...#|.###.", "1": "..#..|.##..|..#..|..#..|..#..|..#..|.###.",
    "2": ".###.|#...#|....#|..##.|.#...|#....|#####", "3": "####.|....#|....#|.###.|....#|....#|####.",
    "4": "...#.|..##.|.#.#.|#..#.|#####|...#.|...#.", "5": "#####|#....|####.|....#|....#|#...#|.###.",
    "6": "..##.|.#...|#....|####.|#...#|#...#|.###.", "7": "#####|....#|...#.|..#..|.#...|.#...|.#...",
    "8": ".###.|#...#|#...#|.###.|#...#|#...#|.###.", "9": ".###.|#...#|#...#|.####|....#|...#.|.##..",
    ".": ".....|.....|.....|.....|.....|.....|..#..", "-": ".....|.....|.....|#####|.....|.....|.....",
    "/": "....#|...#.|...#.|..#..|.#...|.#...|#....", ":": ".....|..#..|..#..|.....|..#..|..#..|.....",
    "!": "..#..|..#..|..#..|..#..|..#..|.....|..#..", " ": ".....|.....|.....|.....|.....|.....|.....",
    "·": ".....|.....|.....|.....|.....|..#..|.....", "★": "..#..|#####|.###.|.###.|..#..|.#.#.|#...#",
}


def pixel_text(text, x, y, px, ink, shadow=None, stagger=0.03, delay=0.0, gap=1):
    """Text as a real pixel grid; `shadow` draws the hard offset copy behind it."""
    out, cx = [], x
    for i, ch in enumerate(str(text).upper()):
        rows = DOT.get(ch, DOT[" "]).split("|")
        px_boxes = [(c, r) for r, row in enumerate(rows) for c, cell in enumerate(row) if cell == "#"]
        for layer, (fill, off, dly) in enumerate([(shadow, px * .9, delay + i * stagger),
                                                  (ink, 0, delay + i * stagger)] if shadow
                                                 else [(ink, 0, delay + i * stagger)]):
            if fill is None:
                continue
            out.append(f'<g class="pop" style="animation-delay:{dly:.2f}s" transform="translate({cx + off:.1f},{y + off:.1f})">')
            out.append(f'<g fill="{fill}">')
            out.append("".join(f'<rect x="{c * px}" y="{r * px}" width="{px}" height="{px}"/>' for c, r in px_boxes))
            out.append("</g></g>")
        cx += 6 * px * (1 if not gap else 1)
    return "".join(out), cx


# ---------------------------------------------------------------- helpers
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def fmt(n):
    return f"{n:,}"


def uid(*parts):
    return "u" + format(zlib.crc32("|".join(map(str, parts)).encode()) & 0xFFFFFFFF, "x")


BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}
@keyframes slideL{from{opacity:0;transform:translateX(-900px)}to{opacity:1;transform:none}}
@keyframes slideR{from{opacity:0;transform:translateX(900px)}to{opacity:1;transform:none}}
@keyframes drop{from{opacity:0;transform:translateY(-320px)}to{opacity:1;transform:none}}
@keyframes pop{0%{opacity:0;transform:scale(.4)}70%{opacity:1;transform:scale(1.08)}100%{opacity:1;transform:scale(1)}}
@keyframes blink{50%{opacity:0}}
@keyframes fill{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes sweep{from{transform:translateY(-40px)}to{transform:translateY(420px)}}
@keyframes marquee{to{transform:translateX(var(--d))}}
@keyframes glow{0%,100%{opacity:.45}50%{opacity:1}}
@keyframes flick{0%,97%,100%{opacity:1}98%{opacity:.5}99%{opacity:.85}}
.rise{animation:rise .55s cubic-bezier(.2,.9,.3,1) both}
.slideL{animation:slideL .5s cubic-bezier(.2,1.1,.3,1) both}
.slideR{animation:slideR .5s cubic-bezier(.2,1.1,.3,1) both}
.drop{animation:drop .6s cubic-bezier(.2,1.3,.35,1) both}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.2,1.5,.4,1) both}
.blink{animation:blink 1.05s steps(1) infinite}
.fill{transform-box:fill-box;transform-origin:0 50%;animation:fill 1.1s cubic-bezier(.2,1,.3,1) both}
.sweep{animation:sweep 5.5s linear infinite}
.marquee{animation:marquee linear infinite}
.glow{animation:glow 2.4s ease-in-out infinite}
.flick{animation:flick 6s linear infinite}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01s!important;animation-iteration-count:1!important}}
"""


def svg(w, h, title, body, css="", defs="", clip_round=None):
    if clip_round is not None:
        defs += f'<clipPath id="frame"><rect width="{w}" height="{h}" rx="{clip_round}"/></clipPath>'
        body = f'<g clip-path="url(#frame)">{body}</g>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{esc(title)}"><title>{esc(title)}</title>'
            f"<style>{BASE_CSS}{css}</style><defs>{defs}</defs>{body}</svg>\n")


def panel_defs(pfx, w, h, accent):
    d = (f'<radialGradient id="{pfx}-bg" cx="50%" cy="0%" r="120%">'
         f'<stop offset="0%" stop-color="{BG2}"/><stop offset="72%" stop-color="{BG}"/></radialGradient>')
    if T["grid"] == "blueprint":
        d += (f'<pattern id="{pfx}-grid" width="24" height="24" patternUnits="userSpaceOnUse">'
              f'<path d="M24 0H0V24" fill="none" stroke="{LINE}" stroke-opacity=".14"/>'
              f'<path d="M6 0V24 M12 0V24 M18 0V24 M0 6H24 M0 12H24 M0 18H24" '
              f'stroke="{LINE}" stroke-opacity=".05"/></pattern>')
    elif T["grid"] == "dither":
        d += (f'<pattern id="{pfx}-grid" width="6" height="6" patternUnits="userSpaceOnUse">'
              f'<rect width="3" height="3" fill="{LINE}" fill-opacity=".12"/></pattern>')
    else:
        d += (f'<pattern id="{pfx}-grid" width="30" height="30" patternUnits="userSpaceOnUse">'
              f'<path d="M30 0H0V30" fill="none" stroke="{accent}" stroke-opacity=".10"/></pattern>'
              f'<pattern id="{pfx}-scan" width="4" height="4" patternUnits="userSpaceOnUse">'
              f'<rect width="4" height="2" fill="#000" fill-opacity=".22"/></pattern>')
    d += (f'<linearGradient id="{pfx}-vig" x1="0" y1="0" x2="0" y2="1">'
          f'<stop offset="0%" stop-color="#000" stop-opacity="0"/>'
          f'<stop offset="100%" stop-color="#000" stop-opacity="{T["vig"]}"/></linearGradient>')
    return d


def panel_bg(pfx, w, h):
    b = [f'<rect width="{w}" height="{h}" fill="url(#{pfx}-bg)"/>',
         f'<rect width="{w}" height="{h}" fill="url(#{pfx}-grid)"/>']
    if T["grid"] == "arcade":
        b.append(f'<rect width="{w}" height="{h}" fill="url(#{pfx}-scan)"/>')
    b.append(f'<rect width="{w}" height="{h}" fill="url(#{pfx}-vig)"/>')
    return "".join(b)


def deco(w, h, accent):
    """Corner furniture: drafting crop marks + rulers, pixel blocks, or HUD brackets."""
    if T["deco"] == "crop":
        p, s = 12, 18
        marks = "".join(
            f'<path d="M{x + dx} {y}H{x}V{y + dy}" fill="none" stroke="{LINE}" stroke-opacity=".5" stroke-width="1.2"/>'
            for x, y, dx, dy in ((p, p, s, s), (w - p, p, -s, s), (p, h - p, s, -s), (w - p, h - p, -s, -s)))
        ticks = "".join(f'<path d="M{x} 0v5" stroke="{LINE}" stroke-opacity=".35" stroke-width="1"/>'
                        for x in range(60, w - 40, 60))
        ticks += "".join(f'<path d="M{x} {h}v-5" stroke="{LINE}" stroke-opacity=".35" stroke-width="1"/>'
                         for x in range(30, w - 20, 60))
        return marks + ticks
    if T["deco"] == "pixels":
        out = []
        for x, y in ((12, 12), (w - 38, 12), (12, h - 38), (w - 38, h - 38)):
            out.append(f'<g fill="{LINE}">')
            for i in range(3):
                for j in range(3):
                    if i * j != 2:
                        out.append(f'<rect x="{x + i * 10}" y="{y + j * 10}" width="8" height="8"/>')
            out.append("</g>")
        return "".join(out)
    return "".join(
        f'<path d="M{x} {y + dy}V{y}H{x + dx}" fill="none" stroke="{accent}" stroke-width="2" stroke-opacity=".75"/>'
        for x, y, dx, dy in ((10, 10, 22, 22), (w - 10, 10, -22, 22), (10, h - 10, 22, -22), (w - 10, h - 10, -22, -22)))


def card(x, y, w, h, accent, opacity=".95", strong=False):
    """Card plate. Pixel themes get a hard offset shadow, so keep w/h 6px shy of the edge."""
    out = []
    if T["shadow"]:
        out.append(f'<rect x="{x + 5}" y="{y + 5}" width="{w}" height="{h}" fill="{LINE}"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{R}" fill="{CARD}" fill-opacity="{opacity}"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{R}" fill="none" stroke="{accent}" '
               f'stroke-opacity="{".95" if strong else ".6"}" stroke-width="{T["border"]}"/>')
    return "".join(out)


def chip_style(accent):
    """(fill, fill-opacity, text fill) for small chips/tags, per theme."""
    if GB:
        return LINE, ".95", BG
    if T["style"] == "arcade":
        return accent, ".14", accent
    return accent, ".2", accent


def wrap(text, n):
    lines, cur = [], ""
    for word in str(text).split():
        if cur and len(cur) + 1 + len(word) > n:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return lines + ([cur] if cur else [])


def clean(s):
    s = re.sub(r"https?://\S+", " ", str(s))
    return re.sub(r"\s+", " ", s).strip(" ·-–—")


def marquee(text, x, y, width, size, fill, speed=42, sep="   ◆   "):
    unit = text + sep
    tw = len(unit) * size * 0.62
    cid = uid("mq", text, y)
    return (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y - size * 1.3:.0f}" width="{width}" height="{size * 1.9:.0f}"/></clipPath>'
        f'<g clip-path="url(#{cid})"><g class="marquee" style="--d:-{tw:.1f}px;animation-duration:{tw / speed:.1f}s" '
        f'font-family="{MONO}" font-size="{size}" font-weight="700" fill="{fill}" letter-spacing="1">'
        + "".join(f'<text x="{x + k * tw:.1f}" y="{y}" textLength="{tw:.1f}" lengthAdjust="spacing" '
                  f'xml:space="preserve">{esc(unit)}</text>' for k in range(2 + int(width // tw)))
        + "</g></g>")


def title_width(text, size, px=None):
    if T["pixel"]:
        return len(text) * 6 * (px or max(3, round(size / 8)))
    return len(text) * size * 0.62 + int(T["title_spacing"]) * len(text)


def title_text(text, x, y, size, fill, cls="rise", delay=0.0, anchor="start", px=None):
    """Headline: dot-matrix in the gameboy theme, vector with tracking elsewhere."""
    if T["pixel"]:
        px = px or max(3, round(size / 8))
        body, _ = pixel_text(text, x, y - 7 * px, px, fill, stagger=.02, delay=delay)
        return body
    return (f'<text class="{cls}" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" font-family="{T["title_font"]}" '
            f'font-size="{size}" font-weight="800" letter-spacing="{T["title_spacing"]}" fill="{fill}" '
            f'text-anchor="{anchor}">{esc(text)}</text>')


# ---------------------------------------------------------------- data
STATS = DATA["stats"]


def targets():
    out = []
    for t in CFG.get("targets", []):
        r = DATA["repos"].get(t["repo"], {})
        out.append({
            "label": (t.get("label") or t["repo"]).upper(),
            "tag": (t.get("tag") or r.get("language") or "").upper(),
            "stars": r.get("stars", 0),
            "url": t.get("url") or r.get("url") or f"https://github.com/{CFG['login']}/{t['repo']}",
            "description": r.get("description", "").strip(),
            "blurb": t.get("blurb", ""),
            "pushed": r.get("pushed", ""),
        })
    return out


def posts():
    fc = CFG.get("feed") or {}
    if not fc.get("rss"):
        return []
    out = []
    for p in DATA.get("posts", []):
        title = clean(p.get("title", ""))
        if len(title) < 12:
            continue
        out.append({**p, "title": title})
        if len(out) >= fc.get("count", 3):
            break
    return out


# ---------------------------------------------------------------- pieces
def hero():
    h = 360
    accent = ACCENTS[0]
    defs = panel_defs("h", W, h, accent)
    b = [panel_bg("h", W, h)]
    if T["style"] == "arcade":
        # moving scanline sweep needs the frame clip, so hero keeps clip_round=R
        defs += (f'<linearGradient id="h-sweep" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{accent}" stop-opacity="0"/>'
                 f'<stop offset="100%" stop-color="{accent}" stop-opacity=".22"/></linearGradient>')
        b.append(f'<g clip-path="url(#frame)"><rect class="sweep" x="0" y="-60" width="{W}" height="60" fill="url(#h-sweep)"/></g>')
        b.append(f'<rect x="0" y="0" width="{W}" height="3" fill="{accent}" opacity=".8"/>')
    elif GB:
        b.append(f'<rect x="6" y="6" width="{W - 12}" height="{h - 12}" fill="none" stroke="{LINE}" stroke-width="3"/>')
    else:
        b.append(f'<rect x="0" y="0" width="{W}" height="2" fill="{LINE}" opacity=".85"/>')
    b.append(deco(W, h, accent))

    # header strip
    if T["style"] == "blueprint":
        b.append(f'<text x="42" y="56" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{DIM}">'
                 f'SHEET 01 · PROFILE · SCALE 1:1</text>')
        b.append(f'<text x="{W - 42}" y="56" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{DIM}" '
                 f'text-anchor="end">REV {datetime.date.today().isoformat()}</text>')
        b.append(f'<path d="M42 68H{W - 42}" stroke="{LINE}" stroke-opacity=".45" stroke-width="1"/>')
        b.append(f'<text x="42" y="128" font-family="{MONO}" font-size="11" letter-spacing="4" fill="{ACCENTS[1]}">'
                 f'SUBJECT / OPERATOR</text>')
        b.append(f'<path d="M34 150v42M28 150h12M28 192h12" stroke="{LINE}" stroke-opacity=".5"/>')
    else:
        b.append(f'<text x="42" y="56" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{DIM}">'
                 f'{"PLAYER ONE" if GB else "PLAYER ONE"} · SINCE {STATS.get("since", "2014")}</text>')
        b.append(f'<text x="{W - 42}" y="56" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{DIM}" '
                 f'text-anchor="end">{esc(CFG["location"])}</text>')

    first, last = CFG["name"]
    if GB:
        n1, cx1 = pixel_text(first, 42, 92, 10, INK, shadow=ACCENTS[1], stagger=.05, delay=.35)
        n2, cx2 = pixel_text(last, 42, 176, 10, INK, shadow=ACCENTS[1], stagger=.05, delay=.8)
        b.append(n1 + n2)
        b.append(f'<rect class="blink" x="{cx2 + 8:.0f}" y="176" width="12" height="70" fill="{INK}"/>')
    else:
        b.append(title_text(first, 42, 178, 74, INK, delay=.35))
        b.append(title_text(last, 42, 252, 74, accent, delay=.75))
        tw = title_width(last, 74)
        if T["style"] == "blueprint":
            b.append(f'<path d="M42 268H{42 + max(title_width(first, 74), tw):.0f}" stroke="{LINE}" stroke-opacity=".35"/>')
        b.append(f'<text class="flick" x="{42 + tw + 14:.0f}" y="{176 if T["style"] == "blueprint" else 246}" '
                 f'font-family="{MONO}" font-size="74" fill="{ACCENTS[2] if T["style"] == "blueprint" else INK}">▌</text>')

    # role strip
    role = CFG["role"]
    ry = 306 if GB else 296
    stack_y = ry + 22 if GB else ry + 14
    prompt_y = ry + 46 if GB else ry + 34
    rw = len(role) * 13.6 + 46
    if T["style"] == "blueprint":
        b.append(f'<g class="slideL" style="animation-delay:1.2s"><g transform="translate(42,{ry - 30})">'
                 f'<rect width="{rw:.0f}" height="32" fill="{CARD}" fill-opacity=".9"/>'
                 f'<rect width="{rw:.0f}" height="32" fill="none" stroke="{ACCENTS[1]}" stroke-width="1.4"/>'
                 f'<path d="M0 0h{rw:.0f}" stroke="{ACCENTS[1]}" stroke-width="4" stroke-opacity=".9"/>'
                 f'<text x="16" y="22" font-family="{MONO}" font-size="17" letter-spacing="2" fill="{INK}">{esc(role)}</text>'
                 f'</g></g>')
    elif GB:
        b.append(f'<g class="slideL" style="animation-delay:1.2s">'
                 f'<rect x="{52}" y="{ry - 36}" width="{rw + 16:.0f}" height="40" fill="{LINE}"/>'
                 f'<rect x="42" y="{ry - 46}" width="{rw + 16:.0f}" height="40" fill="{CARD}"/>'
                 f'<rect x="42" y="{ry - 46}" width="{rw + 16:.0f}" height="40" fill="none" stroke="{LINE}" stroke-width="2.5"/>'
                 f'<text x="{42 + (rw + 16) / 2:.0f}" y="{ry - 19}" font-family="{MONO}" font-size="18" font-weight="800" '
                 f'letter-spacing="2" fill="{INK}" text-anchor="middle">{esc(role)}</text></g>')
    else:
        b.append(f'<g class="slideL" style="animation-delay:1.2s"><g transform="translate(42,{ry - 28}) skewX(-14)">'
                 f'<rect x="6" y="6" width="{rw:.0f}" height="36" fill="{ACCENTS[1]}" opacity=".85"/>'
                 f'<rect width="{rw:.0f}" height="36" fill="{BG2}" stroke="{ACCENTS[1]}" stroke-width="2"/>'
                 f'<text x="16" y="26" font-family="{SANS}" font-size="19" fill="{INK}" letter-spacing="1.5">{esc(role)}</text>'
                 f'</g></g>')

    # stack + prompt
    stack = "  ▸  ".join(CFG["stack"])
    b.append(f'<g class="rise" style="animation-delay:1.45s"><text x="42" y="{stack_y}" font-family="{MONO}" '
             f'font-size="13" font-weight="700" letter-spacing="1.5" fill="{ACCENTS[2] if not GB else INK}">'
             f'{esc(stack)}</text></g>')
    prompt = "PRESS START  ▸  SCROLL DOWN" if GB else "> READY. SCROLL TO CONTINUE"
    b.append(f'<g class="rise" style="animation-delay:1.6s"><text x="42" y="{prompt_y}" font-family="{MONO}" font-size="12" '
             f'letter-spacing="1" fill="{DIM}">{esc(prompt)}</text></g>')
    b.append(f'<rect class="blink" x="{42 + len(prompt) * 7.4:.0f}" y="{prompt_y - 10}" width="8" height="13" fill="{INK}"/>')

    # stat blocks
    stats = [(fmt(STATS["commits"]), "COMMITS"), (fmt(STATS["stars"]), "STARS"),
             (str(STATS["repos"]), "PUBLIC REPOS"), (str(STATS["followers"]), "FOLLOWERS")]
    for i, (val, lbl) in enumerate(stats):
        acc = ACCENTS[i % len(ACCENTS)]
        x = 604 + (i % 2) * 142
        y = 96 + (i // 2) * 96
        delay = 1.0 + i * .16
        b.append(f'<g class="drop" style="animation-delay:{delay:.2f}s">')
        b.append(card(x, y, 128, 78, acc))
        b.append(f'<text x="{x + 16}" y="{y + 46}" font-family="{SANS if T["style"] == "arcade" else MONO}" '
                 f'font-size="{34 if T["style"] == "arcade" else 30}" font-weight="800" fill="{acc}">{esc(val)}</text>')
        b.append(f'<text x="{x + 16}" y="{y + 58}" font-family="{MONO}" font-size="10.5" letter-spacing="2" '
                 f'fill="{DIM}">{esc(lbl)}</text>')
        b.append(f'<rect class="fill" style="animation-delay:{delay + .35:.2f}s" x="{x + 16}" y="{y + 68}" '
                 f'width="96" height="{4 if GB else 3}" fill="{acc}"/>')
        b.append("</g>")

    # drafting title block (blueprint only)
    if T["style"] == "blueprint":
        tbx, tby, tbw, tbh = 604, 286, 266, 60
        rows = [("NAME", f"{first} {last}"), ("ROLE", CFG["role"]),
                ("ORIGIN", f'{CFG["location"]} · SINCE {STATS.get("since", "2014")}')]
        b.append(f'<g class="rise" style="animation-delay:1.7s">'
                 f'<rect x="{tbx}" y="{tby}" width="{tbw}" height="{tbh}" fill="{CARD}" fill-opacity=".92" '
                 f'stroke="{LINE}" stroke-opacity=".5"/>'
                 f'<path d="M{tbx} {tby + 20}H{tbx + tbw}M{tbx} {tby + 40}H{tbx + tbw}" stroke="{LINE}" stroke-opacity=".3"/>'
                 f'<path d="M{tbx + 60} {tby}V{tby + tbh}" stroke="{LINE}" stroke-opacity=".3"/>'
                 + "".join(f'<text x="{tbx + 8}" y="{tby + 14 + i * 20}" font-family="{MONO}" font-size="9" '
                           f'letter-spacing="1.2" fill="{DIM}">{k}</text>'
                           f'<text x="{tbx + 68}" y="{tby + 14 + i * 20}" font-family="{MONO}" font-size="9.5" '
                           f'fill="{INK}">{v}</text>'
                           for i, (k, v) in enumerate(rows))
                 + "</g>")

    title = (f'{first.title()} {last.title()} — {CFG["role"].title()}. '
             f'{fmt(STATS["commits"])} commits, {fmt(STATS["stars"])} stars, {STATS["repos"]} public repos.')
    return svg(W, h, title, "".join(b), "", defs, clip_round=R)


def about():
    lines = wrap(CFG["about"], 84)[:5]
    h = 96 + len(lines) * 30
    defs = panel_defs("a", W, h, ACCENTS[0])
    b = [panel_bg("a", W, h)]
    if T["style"] == "blueprint":
        b.append(f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" fill="none" stroke="{LINE}" '
                 f'stroke-opacity=".6" stroke-width="1.2"/>')
        b.append(f'<path d="M1 34H{W - 1}" stroke="{LINE}" stroke-opacity=".4"/>')
        b.append(f'<text x="24" y="24" font-family="{MONO}" font-size="12" letter-spacing="3" fill="{DIM}">'
                 f'FIG. 02 — NOTES / {esc((CFG.get("handle") or "").upper())}</text>')
        b.append(f'<text x="{W - 24}" y="24" font-family="{MONO}" font-size="11" letter-spacing="2" fill="{DIM}" '
                 f'text-anchor="end">{len(lines)} LINES</text>')
    elif GB:
        b.append(f'<rect x="6" y="6" width="{W - 12}" height="{h - 12}" fill="none" stroke="{LINE}" stroke-width="2.5"/>')
        b.append(f'<rect x="12" y="12" width="{W - 24}" height="34" fill="{LINE}"/>')
        b.append(f'<text x="{W / 2}" y="36" font-family="{MONO}" font-size="13" font-weight="800" letter-spacing="3" '
                 f'fill="{CARD}" text-anchor="middle">▸ {(CFG.get("handle") or "").upper()} : ABOUT</text>')
    else:
        b.append(f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="12" fill="none" stroke="{ACCENTS[0]}" '
                 f'stroke-opacity=".35" stroke-width="2"/>')
        b.append(f'<path d="M1 13a12 12 0 0 1 12-12h874a12 12 0 0 1 12 12v22H1z" fill="{ACCENTS[0]}" fill-opacity=".10"/>')
        for i, c in enumerate(ACCENTS[:3]):
            b.append(f'<circle cx="{26 + i * 20}" cy="18" r="5.5" fill="{c}" opacity=".9"/>')
        b.append(f'<text x="{W / 2}" y="23" font-family="{MONO}" font-size="12" fill="{DIM}" text-anchor="middle">'
                 f'{esc(CFG.get("handle", ""))}@profile — zsh — 80×24</text>')
        b.append(f'<rect x="1" y="35" width="{W - 2}" height="1" fill="{ACCENTS[0]}" fill-opacity=".3"/>')

    y = 74 if T["style"] != "gameboy" else 96
    t = 0.45
    for i, line in enumerate(lines):
        marker = "▸" if (GB and i == 0) else (">" if i == 0 else " ")
        color = INK if (i and not GB) else (INK if GB else ACCENTS[1])
        b.append(f'<text x="30" y="{y}" font-family="{MONO}" font-size="13" fill="{color}" opacity=".9">{marker}</text>')
        dur = max(0.35, len(line) / 55)
        cid = uid("ab", i)
        b.append(f'<clipPath id="{cid}"><rect class="fill" style="animation-delay:{t:.2f}s;animation-duration:{dur:.2f}s" '
                 f'x="46" y="{y - 15}" width="{len(line) * 9.3 + 12:.0f}" height="26"/></clipPath>'
                 f'<text clip-path="url(#{cid})" x="48" y="{y}" font-family="{MONO}" font-size="15" '
                 f'fill="{color}">{esc(line)}</text>')
        t += dur + 0.12
        y += 30
    b.append(f'<rect class="blink" x="48" y="{y - 13}" width="9" height="16" fill="{INK}"/>')
    return svg(W, h, CFG["about"], "".join(b), "", defs, clip_round=R)


def section(title, idx, accent, total=3):
    h = 66
    cid = uid("sec", title)
    b, defs = [], ""
    if T["style"] == "blueprint":
        defs = (f'<linearGradient id="{cid}-b" x1="0" y1="0" x2="1" y2="0">'
                f'<stop offset="0%" stop-color="{accent}" stop-opacity=".24"/>'
                f'<stop offset="45%" stop-color="{BG}" stop-opacity="0"/>'
                f'<stop offset="100%" stop-color="{accent}" stop-opacity=".12"/></linearGradient>')
        b.append(f'<g class="slideL"><rect x="0" y="8" width="{W}" height="50" fill="{CARD}" fill-opacity=".88"/>'
                 f'<rect x="0" y="8" width="{W}" height="50" fill="url(#{cid}-b)"/>'
                 f'<rect x="0" y="8" width="{W}" height="50" fill="none" stroke="{accent}" stroke-opacity=".7" stroke-width="1.2"/>'
                 f'<path d="M14 8v50M22 8v50" stroke="{accent}" stroke-opacity=".5"/></g>')
        b.append(f'<text class="rise" style="animation-delay:.2s" x="40" y="42" font-family="{MONO}" font-size="13" '
                 f'letter-spacing="2" fill="{accent}">[ {idx} ]</text>')
        b.append(title_text(title, 100, 43, 24, INK, delay=.3))
        b.append(f'<path d="M{100 + title_width(title, 24) + 18:.0f} 34H{W - 58}" stroke="{LINE}" stroke-opacity=".4"/>')
        b.append(f'<text x="{W - 16}" y="45" font-family="{MONO}" font-size="26" font-weight="700" fill="{accent}" '
                 f'opacity=".8" text-anchor="end">{idx}/{total:02d}</text>')
    elif GB:
        b.append(f'<g class="slideL">'
                 f'<rect x="10" y="18" width="{W - 20}" height="40" fill="{LINE}"/>'
                 f'<rect x="0" y="8" width="{W - 20}" height="40" fill="{CARD}"/>'
                 f'<rect x="0" y="8" width="{W - 20}" height="40" fill="none" stroke="{LINE}" stroke-width="2.5"/></g>')
        b.append(f'<g class="pop" style="animation-delay:.15s"><g fill="{LINE}">'
                 + "".join(f'<rect x="{20 + i * 16}" y="{20 + j * 16}" width="12" height="12"/>'
                           for i in range(2) for j in range(3) if (i, j) != (1, 2)) + "</g></g>")
        b.append(title_text(title, 76, 40, 24, INK, delay=.25))
        b.append(f'<text x="{W - 44}" y="40" font-family="{MONO}" font-size="22" font-weight="800" fill="{LINE}" '
                 f'text-anchor="end">{idx}</text>')
    else:
        defs = (f'<linearGradient id="{cid}-b" x1="0" y1="0" x2="1" y2="0">'
                f'<stop offset="0%" stop-color="{accent}" stop-opacity=".26"/>'
                f'<stop offset="55%" stop-color="{BG}" stop-opacity="0"/>'
                f'<stop offset="100%" stop-color="{accent}" stop-opacity=".14"/></linearGradient>')
        b.append(f'<g class="slideL"><rect x="0" y="4" width="{W}" height="58" rx="{R}" fill="{CARD}"/>'
                 f'<rect x="0" y="4" width="{W}" height="58" rx="{R}" fill="url(#{cid}-b)"/>'
                 f'<rect x="0" y="4" width="{W}" height="58" rx="{R}" fill="none" stroke="{accent}" stroke-opacity=".5" stroke-width="1.5"/>'
                 f'<rect x="0" y="19" width="6" height="28" rx="3" fill="{accent}"/></g>')
        b.append(title_text(title, 102, 43, 25, INK, delay=.34))
        b.append(f'<text class="rise" style="animation-delay:.42s" x="{102 + title_width(title, 25) + 16:.0f}" y="43" '
                 f'font-family="{MONO}" font-size="25" font-weight="800" fill="{accent}">▸▸▸</text>')
        b.append(f'<text x="{W - 26}" y="45" font-family="{MONO}" font-size="34" font-weight="800" fill="{accent}" '
                 f'opacity=".55" text-anchor="end" letter-spacing="2">{idx}</text>')
    return svg(W, h, title, "".join(b), "", defs)


def _split_label(label, max_chars):
    """Wrap a repo label on its hyphens/slashes, keeping the separator visible."""
    parts = re.split(r"(?<=[- /])", label)
    lines, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > max_chars:
            lines.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        lines.append(cur)
    return lines or [label]


def target_card(i, t, accent):
    """Grid cell (3 per row): same data as target_row, cartridge-sized."""
    cw, ch = 292, 182
    x0 = y0 = 3
    avail = cw - 32
    label = t["label"]
    px = 3
    while px > 2 and len(_split_label(label, int(avail / (6 * px)))) > 2:
        px -= 1
    tlines = _split_label(label, int(avail / (6 * px)))[:2]
    title_svg = "".join(pixel_text(ln, x0 + 16, y0 + 46 + n * (7 * px + 4), px, INK)[0]
                        for n, ln in enumerate(tlines))
    desc = clean(t.get("description") or t.get("blurb") or "")
    dlines = wrap(desc, 37)[:3]
    if len(wrap(desc, 37)) > 3:
        dlines[2] = dlines[2][:35].rstrip(" ,.;:") + "…"
    dy = y0 + 46 + len(tlines) * (7 * px + 4) + 6
    desc_svg = "".join(f'<text x="{x0 + 16}" y="{dy + n * 15}" font-family="{MONO}" font-size="11" '
                       f'fill="{DIM}">{esc(ln)}</text>' for n, ln in enumerate(dlines))
    fill_c, fill_o, txt_c = chip_style(accent)
    chip_y = y0 + ch - 30
    tag = ""
    if t["tag"]:
        tw = len(t["tag"]) * 7 + 18
        tag = (f'<g transform="translate({x0 + 16},{chip_y})">'
               f'<rect width="{tw:.0f}" height="21" fill="{fill_c}" fill-opacity="{fill_o}"/>'
               f'<rect width="{tw:.0f}" height="21" fill="none" stroke="{accent}" stroke-opacity=".8"/>'
               f'<text x="{tw / 2:.0f}" y="15" font-family="{MONO}" font-size="10" letter-spacing="1" fill="{txt_c}" '
               f'text-anchor="middle">{esc(t["tag"])}</text></g>')
    new = t["pushed"] and (datetime.date.today() - datetime.date.fromisoformat(t["pushed"])).days <= 90
    badge = ""
    if new:
        bw = 56
        badge = (f'<g class="pop" style="animation-delay:{.45 + i * .08:.2f}s" '
                 f'transform="translate({x0 + cw - 16 - bw},{chip_y})">'
                 f'<rect width="{bw}" height="21" fill="{fill_c}" fill-opacity="{fill_o}"/>'
                 f'<rect width="{bw}" height="21" fill="none" stroke="{accent}" stroke-opacity=".9"/>'
                 f'<text x="{bw / 2:.0f}" y="15" font-family="{MONO}" font-size="10" letter-spacing="1" '
                 f'fill="{txt_c}" text-anchor="middle">NEW</text></g>')
    star = (f'<text x="{x0 + cw - 16}" y="{y0 + 28}" font-family="{MONO}" font-size="12" font-weight="700" '
            f'fill="{INK}" text-anchor="end">★ {t["stars"]}</text>') if t["stars"] else ""
    body = [
        f'<g class="rise" style="animation-delay:{.12 + i * .07:.2f}s">',
        card(x0, y0, cw, ch, accent),
        f'<rect x="{x0}" y="{y0 + 12}" width="{6 if GB else 5}" height="{ch - 24}" fill="{accent}"/>',
        f'<text x="{x0 + 16}" y="{y0 + 28}" font-family="{MONO}" font-size="15" font-weight="800" '
        f'fill="{accent}">{i + 1:02d}</text>',
        star, title_svg, desc_svg, tag, badge,
        "</g>",
    ]
    return svg(cw + 10, ch + 10, f'{label}: {desc or t["tag"]}', "".join(body))


def target_row(i, t, accent):
    h = 82
    inset = 8 if T["shadow"] else 2
    new = t["pushed"] and (datetime.date.today() - datetime.date.fromisoformat(t["pushed"])).days <= 90
    desc = t.get("description") or t.get("blurb") or ""
    limit = 78 if not GB else 66
    if len(desc) > limit:
        desc = desc[:limit - 1].rstrip(" ,.;:") + "…"
    size = 20 if not GB else 21
    lab_w = title_width(t["label"], size)
    star = (f'<text x="{W - 30}" y="30" font-family="{MONO}" font-size="14" font-weight="700" fill="{INK}" '
            f'text-anchor="end">★ {t["stars"]}</text>') if t["stars"] else ""
    fill_c, fill_o, txt_c = chip_style(accent)
    tag = ""
    if t["tag"]:
        tw = len(t["tag"]) * 7.6 + 22
        tag = (f'<g transform="translate({W - 34 - tw:.0f},42)">'
               f'<rect width="{tw:.0f}" height="24" fill="{fill_c}" fill-opacity="{fill_o}"/>'
               f'<rect width="{tw:.0f}" height="24" fill="none" stroke="{accent}" stroke-opacity=".8"/>'
               f'<text x="{tw / 2:.0f}" y="17" font-family="{MONO}" font-size="11" letter-spacing="1.5" fill="{txt_c}" '
               f'text-anchor="middle">{esc(t["tag"])}</text></g>')
    newbadge = ""
    if new:
        nw = 62
        right_edge = W - 34 - (len(t["tag"]) * 7.6 + 34 if t["tag"] else 4)
        nx = min(82 + lab_w + 18, right_edge - nw)
        newbadge = (f'<g class="pop" style="animation-delay:{.5 + i * .08:.2f}s" transform="translate({nx:.0f},20)">'
                    f'<rect width="{nw}" height="19" fill="{fill_c}" fill-opacity="{fill_o}"/>'
                    f'<rect width="{nw}" height="19" fill="none" stroke="{accent}" stroke-opacity=".9"/>'
                    f'<text x="{nw / 2:.0f}" y="14" font-family="{MONO}" font-size="10" letter-spacing="1" '
                    f'fill="{txt_c}" text-anchor="middle">NEW</text></g>')
    desc_el = (f'<text x="82" y="{h - 20}" font-family="{MONO}" font-size="12.5" fill="{DIM}">{esc(desc)}</text>'
               if desc else f'<text x="82" y="{h - 20}" font-family="{MONO}" font-size="12.5" fill="{DIM}" '
                            f'opacity=".75">see the repo for details</text>')
    body = [
        f'<g class="rise" style="animation-delay:{.12 + i * .08:.2f}s">',
        card(1, 1, W - inset, h - inset, accent),
        f'<rect x="1" y="14" width="{7 if GB else 5}" height="{h - 28}" fill="{accent}"/>',
        f'<text x="30" y="{h - 26}" font-family="{MONO}" font-size="30" font-weight="800" fill="{accent}" '
        f'opacity=".9">{i + 1:02d}</text>',
        title_text(t["label"], 82, 38, size, INK, delay=.18 + i * .08),
        desc_el, star, tag, newbadge,
        "</g>",
    ]
    return svg(W, h, f'{t["label"]}: {desc or t["tag"]}', "".join(body))


def post_row(i, p, accent):
    h = 74
    inset = 8 if T["shadow"] else 2
    d = datetime.date.fromisoformat(p["date"])
    all_lines = wrap(p["title"], 86)
    lines = all_lines[:2]
    if len(all_lines) > 2:
        lines[1] = lines[1][:84].rstrip(" ,.;:") + "…"
    fill_c, fill_o, txt_c = chip_style(accent)
    stamp = (f'<g transform="translate(24,{h / 2 - 18})">'
             f'<rect width="64" height="36" fill="{fill_c}" fill-opacity="{fill_o}"/>'
             f'<rect width="64" height="36" fill="none" stroke="{accent}" stroke-opacity=".8"/>'
             f'<text x="32" y="16" font-family="{MONO}" font-size="12" font-weight="700" fill="{txt_c}" '
             f'text-anchor="middle">{d.day:02d}</text>'
             f'<text x="32" y="29" font-family="{MONO}" font-size="9.5" letter-spacing="1" fill="{DIM}" '
             f'text-anchor="middle">{d.strftime("%b %Y").upper()}</text></g>')
    text = "".join(f'<text x="108" y="{30 + n * 20}" font-family="{MONO}" font-size="14" '
                   f'fill="{INK if n == 0 else DIM}">{esc(line)}</text>' for n, line in enumerate(lines))
    body = [
        f'<g class="rise" style="animation-delay:{.12 + i * .1:.2f}s">',
        card(1, 1, W - inset, h - inset, accent),
        stamp, text,
        f'<text x="{W - 28}" y="{h / 2 + 5}" font-family="{MONO}" font-size="12" fill="{DIM}" text-anchor="end">↗</text>',
        "</g>",
    ]
    return svg(W, h, p["title"], "".join(body))


def feed_footer(label):
    h = 46
    fill_c, fill_o, txt_c = chip_style(ACCENTS[0])
    body = [
        f'<g class="slideR" style="animation-delay:.5s">',
        f'<rect x="{W - 392}" y="12" width="380" height="30" fill="{LINE}" fill-opacity=".85"/>',
        f'<rect x="{W - 398}" y="8" width="380" height="30" fill="{fill_c}" fill-opacity="{fill_o}" '
        f'stroke="{ACCENTS[0]}" stroke-opacity=".85" stroke-width="1.4"/>',
        f'<text x="{W - 208}" y="28" font-family="{MONO}" font-size="12" font-weight="700" letter-spacing="2" '
        f'fill="{txt_c}" text-anchor="middle">{esc(label)} ▸</text></g>',
    ]
    return svg(W, h, label, "".join(body))


def contact(i, c):
    label = c["label"]
    w = max(150, int(len(label) * 10) + 96)
    h = 58
    accent = ACCENTS[i % len(ACCENTS)]
    body = [
        f'<g class="pop" style="animation-delay:{.1 + i * .09:.2f}s">',
        card(1, 1, w - (8 if T["shadow"] else 2), h - (8 if T["shadow"] else 2), accent, strong=True),
        f'<rect class="glow" style="animation-delay:{i * .3:.1f}s" x="18" y="{h / 2 - 4}" width="8" height="8" fill="{accent}"/>',
        f'<text x="{w / 2 + 14}" y="{h / 2 + 5}" font-family="{MONO}" font-size="14" font-weight="700" '
        f'letter-spacing="2" fill="{INK}" text-anchor="middle">{esc(label)}</text>',
        "</g>",
    ]
    return svg(w, h, label, "".join(body))


def ticker():
    h = 44
    parts = [f"{fmt(STATS['commits'])} COMMITS", f"{fmt(STATS['stars'])} STARS", f"{STATS['repos']} PUBLIC REPOS",
             f"{STATS['followers']} FOLLOWERS", f"BUILDING SINCE {STATS.get('since', '2014')}",
             f"@{CFG.get('handle', '').upper()}"]
    ps = posts()
    if ps:
        parts.insert(4, f"LATEST: {ps[0]['title'].upper()[:56]}")
    cycle = "   ◆   ".join(parts)
    body = [f'<rect x="0" y="0" width="{W}" height="{h}" fill="{CARD}"/>',
            f'<rect x="0" y="0" width="{W}" height="{2.5 if GB else 2}" fill="{LINE}"/>',
            f'<rect x="0" y="{h - (2.5 if GB else 2)}" width="{W}" height="{2.5 if GB else 2}" fill="{LINE}"/>',
            marquee(cycle, 12, 27, W - 24, 12.5, INK)]
    return svg(W, h, cycle, "".join(body))


# ---------------------------------------------------------------- assemble
def slug(s):
    return "".join(ch if ch.isalnum() else "-" for ch in s.lower()).strip("-")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(OUT_DIR, "*.svg")):
        os.remove(f)

    def write(name, content):
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(content)
        return f"{REL}/{name}"

    tg, ps = targets(), posts()
    first, last = CFG["name"]
    feed_cfg = CFG.get("feed") or {}
    present = [n for n, on in (("targets", bool(tg)), ("feed", bool(ps)), ("contacts", bool(CFG.get("contacts")))) if on]
    total = len(present)
    num = {n: f"{i + 1:02d}" for i, n in enumerate(present)}
    md = [
        "<!--\n  GENERATED by scripts/gen_profile.py — do not edit by hand.\n"
        f"  theme: {CFG.get('theme', 'blueprint')}   |   content: profile.config.json\n"
        "  Run:  python3 scripts/gen_profile.py\n"
        "  The \"Refresh profile\" GitHub Action does this daily with fresh stats.\n-->\n",
        f'<p align="center"><img src="{write("hero.svg", hero())}" width="100%" '
        f'alt="{esc(first.title())} {esc(last.title())}, {esc(CFG["role"].title())}. '
        f'{fmt(STATS["commits"])} commits, {fmt(STATS["stars"])} stars, {STATS["repos"]} public repos." /></p>\n',
        f'<p align="center"><img src="{write("about.svg", about())}" width="100%" alt="{esc(CFG["about"])}" /></p>\n',
    ]
    if tg:
        md.append(f'<p align="center"><img src="{write("h-targets.svg", section("SELECT PROJECT", num["targets"], ACCENTS[0], total))}" '
                  f'width="100%" alt="Select project" /><br>')
        layout = CFG.get("targets_layout") or ("grid" if GB else "rows")
        for i, t in enumerate(tg):
            alt = f'{t["label"]}: {t["description"] or t["blurb"] or t["tag"]}'
            accent = ACCENTS[i % len(ACCENTS)]
            if layout == "grid":
                src = write(f"target-{i}.svg", target_card(i, t, accent))
                md.append(f'<a href="{esc(t["url"])}"><img src="{src}" width="32.5%" alt="{esc(alt)}" /></a>')
                if i % 3 == 2 or i == len(tg) - 1:
                    md.append("<br>")
            else:
                src = write(f"target-{i}.svg", target_row(i, t, accent))
                md.append(f'<a href="{esc(t["url"])}"><img src="{src}" width="100%" alt="{esc(alt)}" /></a><br>')
        md.append("</p>\n")
    if ps:
        label = feed_cfg.get("label", "LATEST POSTS")
        md.append(f'<p align="center"><img src="{write("h-feed.svg", section(label, num["feed"], ACCENTS[1], total))}" width="100%" '
                  f'alt="{esc(label)}" /><br>')
        for i, p in enumerate(ps):
            md.append(f'<a href="{esc(p["url"])}"><img src="{write(f"post-{i}.svg", post_row(i, p, ACCENTS[1]))}" '
                      f'width="100%" alt="{esc(p["title"])}" /></a><br>')
        if feed_cfg.get("all_url"):
            footer = write("feed-all.svg", feed_footer(feed_cfg.get("all_label", "ALL POSTS")))
            md.append(f'<a href="{esc(feed_cfg["all_url"])}"><img src="{footer}" width="100%" alt="All posts" /></a>')
        md.append("</p>\n")
    if CFG.get("contacts"):
        md.append(f'<p align="center"><img src="{write("h-contact.svg", section("CONNECT", num["contacts"], ACCENTS[2], total))}" '
                  f'width="100%" alt="Connect" /><br>')
        for i, c in enumerate(CFG["contacts"]):
            md.append(f'<a href="{esc(c["url"])}"><img src="{write(f"contact-{slug(c["label"])}.svg", contact(i, c))}" '
                      f'height="46" alt="{esc(c["label"].title())}" /></a> ')
        md.append("</p>\n")
    md.append(f'<p align="center"><img src="{write("ticker.svg", ticker())}" width="100%" alt="Stats ticker" /></p>\n')

    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    n = len(glob.glob(os.path.join(OUT_DIR, "*.svg")))
    print(f"theme={CFG.get('theme')} → README.md + {n} SVGs in {REL}/")


if __name__ == "__main__":
    main()
