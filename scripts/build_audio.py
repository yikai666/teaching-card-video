# -*- coding: utf-8 -*-
"""把逐卡 mp3 按时间轴铺成一条 master.wav（44.1k 单声道）

用法: python build_audio.py [项目目录]
"""
import os
import subprocess
import sys
import wave

import numpy as np

from nv_common import load_json, project_root, ffmpeg_bin

SR = 44100


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    root = project_root(ap.parse_args().root)
    tl = load_json(os.path.join(root, "timeline.json"))
    total = int(round(tl["duration"] * SR)) + SR
    buf = np.zeros(total, dtype=np.float32)
    exe = ffmpeg_bin()

    for sc in tl["scenes"]:
        if sc["layout"] == "pause" or not sc.get("audio"):
            continue
        fn = os.path.join(root, sc["audio"])
        if not os.path.exists(fn):
            sys.exit(f"[nv] 缺少配音 {fn}")
        raw = subprocess.run(
            [exe, "-v", "error", "-i", fn, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
            capture_output=True, check=True).stdout
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        start = int(round(sc["start"] * SR))
        end = min(total, start + len(a))
        buf[start:end] += a[:end - start]
        print(f"  {sc['id']:>6} @ {sc['start']:7.2f}s  {len(a)/SR:5.2f}s")

    peak = float(np.abs(buf).max())
    if peak > 0:
        buf *= 0.89 / peak
    pcm = (np.clip(buf, -1, 1) * 32767).astype("<i2")
    out = os.path.join(root, "master.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"[nv] master.wav  {len(buf)/SR:.2f}s  peak={peak:.2f}")


if __name__ == "__main__":
    main()
