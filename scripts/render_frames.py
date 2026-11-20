# -*- coding: utf-8 -*-
"""逐帧渲染：Playwright 并行抓帧，seek() 用“场景内相对时间”

用法: python render_frames.py [项目目录] [-j 4] [--resume]
输出: frames/000000.jpg ...
"""
import asyncio
import os
import sys
import time
from multiprocessing import Pool

from playwright.async_api import async_playwright

from nv_common import load_json, project_root, ensure_dir

FPS = 24
W, H = 1280, 720
TL = None
SC = None
BASE = None
N = 0
BOUND = None


def plan(k):
    jobs = []
    for i, s in enumerate(SC):
        a, b = BOUND[i], BOUND[i + 1]
        if b > a:
            jobs.append((i, a, b))
    buckets = [[] for _ in range(k)]
    load = [0] * k
    for j in sorted(jobs, key=lambda x: x[2] - x[1], reverse=True):
        m = load.index(min(load))
        buckets[m].append(j)
        load[m] += j[2] - j[1]
    return buckets


def worker(args):
    wid, jobs, resume = args

    async def run():
        async with async_playwright() as p:
            br = await p.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text"])
            pg = await br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            await pg.goto("file://" + os.path.join(BASE, "stage.html"))
            await pg.wait_for_function("window.READY===true", timeout=60000)
            await pg.evaluate("(m)=>window.setMeta(m)", TL["meta"])
            t0, done = time.time(), 0
            for idx, a, b in jobs:
                s = SC[idx]
                await pg.evaluate("(s)=>window.setScene(s)", s)
                await pg.wait_for_function("window.SCENE_READY===true", timeout=30000)
                await pg.evaluate("window.SCENE_READY=false")
                for k in range(a, b):
                    path = os.path.join(BASE, "frames", f"{k:06d}.jpg")
                    if resume and os.path.exists(path) and os.path.getsize(path) > 2000:
                        done += 1
                        continue
                    t = max(0.0, k / FPS - s["start"])
                    await pg.evaluate("(t)=>window.seek(t)", t)
                    await pg.screenshot(path=path, type="jpeg", quality=93)
                    done += 1
                el = time.time() - t0
                print(f"[w{wid}] {s['id']} {done} frames, {el:.0f}s, {done/max(el,1):.0f} fps", flush=True)
            await br.close()

    asyncio.run(run())
    return wid


def main():
    global TL, SC, BASE, N, BOUND, FPS, W, H
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("-j", type=int, default=4)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    root = project_root(a.root)
    BASE = root
    resume = a.resume
    k = max(1, a.j)

    TL = load_json(os.path.join(root, "timeline.json"))
    FPS = int(TL.get("fps", 24))
    W, H = int(TL.get("width", 1280)), int(TL.get("height", 720))
    SC = TL["scenes"]
    N = int(round(TL["duration"] * FPS))
    BOUND = [0] + [int(round(s["start"] * FPS)) for s in SC[1:]] + [N]

    os.makedirs(os.path.join(root, "frames"), exist_ok=True)
    buckets = plan(k)
    for i, b in enumerate(buckets):
        print(f"worker {i}: {sum(x[2]-x[1] for x in b)} frames  "
              f"{[SC[x[0]]['id'] for x in b]}", flush=True)
    t0 = time.time()
    with Pool(k) as pool:
        pool.map(worker, [(i, b, resume) for i, b in enumerate(buckets)])
    print(f"[nv] ALL DONE {time.time()-t0:.0f}s, target {N} frames")


if __name__ == "__main__":
    main()
