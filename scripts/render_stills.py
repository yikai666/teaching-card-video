# -*- coding: utf-8 -*-
"""静帧接触表：每个场景抽 2 帧（45% / 90%），供人工确认镜头节奏后再出片

用法: python render_stills.py [项目目录]
输出: out/stills/*.png  out/contact_sheet.png
"""
import asyncio
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright

from nv_common import load_json, project_root, ensure_dir, clean_math, fmt_ts

BASE = None


def cjk_font(size, bold=False):
    for name in ("Noto Sans CJK SC:style=Bold" if bold else "Noto Sans CJK SC", "Noto Sans SC", "DejaVu Sans"):
        try:
            p = subprocess.check_output(["fc-match", "-f", "%{file}", name]).decode()
            if p and os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def fit(draw, text, font, maxw):
    if draw.textlength(text, font=font) <= maxw:
        return text
    while text and draw.textlength(text + "…", font=font) > maxw:
        text = text[:-1]
    return text + "…"


async def shoot(root):
    tl = load_json(os.path.join(root, "timeline.json"))
    out = ensure_dir(root, "out", "stills")
    shots = []
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
        pg = await br.new_page(viewport={"width": tl["width"], "height": tl["height"]}, device_scale_factor=1)
        await pg.goto("file://" + os.path.join(root, "stage.html"))
        await pg.wait_for_function("window.READY===true", timeout=60000)
        await pg.evaluate("(m)=>window.setMeta(m)", tl["meta"])
        for s in tl["scenes"]:
            await pg.evaluate("(s)=>window.setScene(s)", s)
            await pg.wait_for_function("window.SCENE_READY===true", timeout=30000)
            await pg.evaluate("window.SCENE_READY=false")
            fracs = [0.5] if s["layout"] == "pause" else [0.45, 0.9]
            for f in fracs:
                t = s["duration"] * f
                await pg.evaluate("(t)=>window.seek(t)", t)
                fn = os.path.join(out, f"{s['id']}_{int(f*100)}.png")
                await pg.screenshot(path=fn)
                shots.append({"id": s["id"], "layout": s["layout"], "title": s.get("title", ""),
                              "frac": f, "t": s["start"] + t, "file": fn, "dur": s["duration"]})
                print(f"  {s['id']:>7} {int(f*100):3d}%  {fmt_ts(s['start']+t)}")
        await br.close()
    return tl, shots


def sheet(root, tl, shots):
    cols, tw, th = 4, 430, 242
    pad, top, lab = 16, 92, 34
    rows = (len(shots) + cols - 1) // cols
    W = cols * (tw + pad) + pad
    H = top + rows * (th + lab + pad) + 46
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)
    f_title, f_sub = cjk_font(24, True), cjk_font(13)
    f_lab, f_foot = cjk_font(13, True), cjk_font(12)
    d.text((pad + 2, 18), f"{tl['name']} · 静帧接触表", fill="#1E1B16", font=f_title)
    cps = sum(x["cps"] * x["dur"] for x in load_json(os.path.join(root, "timings.json"))) / sum(
        x["dur"] for x in load_json(os.path.join(root, "timings.json")))
    d.text((pad + 2, 54),
           f"{len(tl['scenes'])} 个场景 · {tl['width']}×{tl['height']} · {tl['fps']} fps · "
           f"总长 {fmt_ts(tl['duration'])} · 语速约 {cps:.1f} cps · 每卡两帧（45% / 90%）",
           fill="#6E685B", font=f_sub)
    d.line([(pad, 80), (W - pad, 80)], fill="#D9D2C0", width=1)

    for i, s in enumerate(shots):
        x = pad + (i % cols) * (tw + pad)
        y = top + (i // cols) * (th + lab + pad)
        im = Image.open(s["file"]).convert("RGB").resize((tw, th), Image.LANCZOS)
        img.paste(im, (x, y))
        if s["layout"] == "pause":
            d.rectangle([x, y, x + tw, y + th], outline="#1E1B16", width=2)
        else:
            d.rectangle([x, y, x + tw, y + th], outline="#E2DBC9", width=1)
        if s["layout"] == "pause":
            label = f"{s['id']} · 暂停卡 · {int(s['frac']*100)}% · {fmt_ts(s['t'])}"
        else:
            label = f"{s['id']} · {clean_math(s['title'])}"
        d.text((x + 2, y + th + 8), fit(d, label, f_lab, tw - 4), fill="#24221C", font=f_lab)
        if s["layout"] != "pause":
            d.text((x + 2, y + th + 23), f"{int(s['frac']*100)}% · {fmt_ts(s['t'])}  ({s['dur']:.0f}s)",
                   fill="#8A8374", font=f_sub)

    d.line([(pad, H - 40), (W - pad, H - 40)], fill="#D9D2C0", width=1)
    d.text((pad + 2, H - 30), "检查点：每张卡是否从空页开始、元素是否在旁白讲到时才出现、有无越界或空白帧",
           fill="#6E685B", font=f_foot)
    out = os.path.join(root, "out", "contact_sheet.png")
    img.save(out)
    print(f"[nv] {out}  {img.size[0]}x{img.size[1]}")


def main():
    global BASE
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    root = project_root(ap.parse_args().root)
    BASE = root
    tl, shots = asyncio.run(shoot(root))
    sheet(root, tl, shots)


if __name__ == "__main__":
    main()
