# -*- coding: utf-8 -*-
"""逐卡合成旁白，并记录词级时间戳（驱动画面逐字展开）

用法: python gen_audio.py [项目目录] [--force] [--voice zh-CN-XiaoxiaoNeural] [--rate +12%]
依赖: pip install edge-tts
"""
import asyncio
import json
import os
import re
import subprocess
import sys

from nv_common import load_project, load_json, save_json, project_root, ensure_dir, probe_duration


def _ensure_edge_tts():
    try:
        import edge_tts  # noqa: F401
        return
    except ImportError:
        pass
    for cand in ("/usr/bin/python3", "python3.11", "python3"):
        if os.path.abspath(cand) == os.path.abspath(sys.executable):
            continue
        if subprocess.run([cand, "-c", "import edge_tts"],
                          capture_output=True).returncode == 0:
            os.execv(cand, [cand, os.path.abspath(__file__)] + sys.argv[1:])
    sys.exit("[nv] 缺少 edge-tts：pip install edge-tts")


async def synth(text, voice, rate, out_mp3, tries=3):
    import edge_tts
    last = None
    for attempt in range(tries):
        try:
            tts = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
            data, words, pos = b"", [], 0
            async for ch in tts.stream():
                if ch["type"] == "audio":
                    data += ch["data"]
                elif ch["type"] == "WordBoundary":
                    w = ch["text"]
                    j = text.find(w, pos)
                    if j < 0:
                        j = pos
                    i, pos = j, j + len(w)
                    words.append({"t": round(ch["offset"] / 1e7, 3),
                                  "d": round(ch["duration"] / 1e7, 3),
                                  "w": w, "i": i, "j": pos})
            if not data:
                raise RuntimeError("空音频")
            with open(out_mp3, "wb") as f:
                f.write(data)
            return words
        except Exception as e:  # 网络抖动：退避重试
            last = e
            await asyncio.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"{out_mp3} 合成失败: {last}")


async def run(root, force, voice, rate):
    meta, cards = load_project(root)
    voice = voice or meta.get("voice", "zh-CN-XiaoxiaoNeural")
    rate = rate or meta.get("rate", "+0%")
    audio_dir = ensure_dir(root, "audio")
    old = {}
    if not force and os.path.exists(os.path.join(root, "timings.json")):
        old = {x["id"]: x for x in load_json(os.path.join(root, "timings.json"))}

    sem = asyncio.Semaphore(3)
    results = {}

    async def one(card):
        cid = card["id"]
        mp3 = os.path.join(audio_dir, f"{cid}.mp3")
        if not force and cid in old and os.path.exists(mp3):
            results[cid] = old[cid]
            print(f"  {cid:>6} 复用 {old[cid]['dur']:5.1f}s")
            return
        async with sem:
            words = await synth(card["tts"], voice, rate, mp3)
            dur = probe_duration(mp3)
            cps = len(re.sub(r"\s", "", card["tts"])) / max(0.1, dur)
            results[cid] = {"id": cid, "dur": round(dur, 3), "cps": round(cps, 2), "words": words}
            print(f"  {cid:>6} {dur:5.1f}s  {cps:4.1f} cps  {len(words)} words", flush=True)

    await asyncio.gather(*[one(c) for c in cards])
    ordered = [results[c["id"]] for c in cards]
    save_json(os.path.join(root, "timings.json"), ordered)

    cps_all = [x["cps"] for x in ordered]
    print(f"\n[nv] {len(ordered)} 张卡，语速 {sum(cps_all)/len(cps_all):.2f} cps "
          f"(min {min(cps_all):.1f} / max {max(cps_all):.1f})")
    slow = [x["id"] for x in ordered if x["cps"] < 4.6]
    fast = [x["id"] for x in ordered if x["cps"] > 6.2]
    if slow:
        print(f"[!] 偏慢（<4.6 cps）：{', '.join(slow)}")
    if fast:
        print(f"[!] 偏快（>6.2 cps）：{', '.join(fast)}")


def main():
    import argparse
    _ensure_edge_tts()
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voice")
    ap.add_argument("--rate")
    a = ap.parse_args()
    asyncio.run(run(project_root(a.root), a.force, a.voice, a.rate))


if __name__ == "__main__":
    main()
