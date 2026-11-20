# -*- coding: utf-8 -*-
"""镜头纪律检查：同屏生长数、最小间隔帧数、触发词命中、长静默

用法: python check_timeline.py [项目目录]
硬性：同屏最多 2 个元素生长；相邻元素起始间隔 ≥ 12 帧（24fps）
"""
import os
import sys

from nv_common import load_json, project_root, fmt_ts


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    root = project_root(ap.parse_args().root)
    tl = load_json(os.path.join(root, "timeline.json"))
    fps = tl["fps"]
    problems, warns = [], []

    if tl.get("missing"):
        problems.append(f"触发词未命中 {len(tl['missing'])} 处：{tl['missing'][:5]}")

    for s in tl["scenes"]:
        if s["layout"] == "pause":
            continue
        if not os.path.exists(os.path.join(root, s.get("audio", ""))):
            problems.append(f"{s['id']} 缺配音文件")
        beats = s["beats"]
        ev = []
        for b in beats:
            ev += [(b["start"], 1), (b["start"] + b["rise"], -1)]
        ev.sort()
        cur = mx = 0
        for _, d in ev:
            cur += d
            mx = max(mx, cur)
        gaps = [beats[i + 1]["start"] - beats[i]["start"] for i in range(len(beats) - 1)]
        mingap = min(gaps) if gaps else 99
        if mx > 2:
            problems.append(f"{s['id']} 同屏生长 {mx} 个")
        if mingap * fps < 12 - 0.01:
            problems.append(f"{s['id']} 最小间隔 {mingap*24:.1f} 帧 < 12")
        tail = tl_tail(root, s)
        if tail > 8:
            warns.append(f"{s['id']} 结尾静默 {tail:.1f}s（最后一拍之后没有新内容）")
        for b in beats:
            if b["start"] + b["rise"] > s["duration"] + 0.01:
                warns.append(f"{s['id']} 节拍超出场景时长：{b['kind']} @{b['start']:.2f}")

    print(f"[nv] {len(tl['scenes'])} 场景，总长 {fmt_ts(tl['duration'])}")
    if problems:
        print("\n[FAIL]")
        for p in problems:
            print("  -", p)
    else:
        print("[PASS] 同屏 ≤2、间隔 ≥12 帧、触发词全命中")
    if warns:
        print("\n[WARN] 节奏提示")
        for w in warns:
            print("  -", w)
    sys.exit(1 if problems else 0)


def tl_tail(root, scene):
    try:
        tim = {x["id"]: x for x in load_json(os.path.join(root, "timings.json"))}[scene["id"]]
    except Exception:
        return 0
    if not scene["beats"]:
        return 0
    return tim["dur"] - (scene["beats"][-1]["start"] + scene["beats"][-1]["rise"])


if __name__ == "__main__":
    main()
