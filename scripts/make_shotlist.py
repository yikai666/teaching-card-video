# -*- coding: utf-8 -*-
"""从 timeline.json 生成镜头表 CSV

用法: python make_shotlist.py [项目目录]
"""
import csv
import os
import sys

from nv_common import load_json, project_root, fmt_ts


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    root = project_root(ap.parse_args().root)
    tl = load_json(os.path.join(root, "timeline.json"))
    out = os.path.join(root, "out", "shotlist.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "场景", "类型", "开始", "时长(s)", "标题", "节拍数", "材料页码"])
        for i, s in enumerate(tl["scenes"], 1):
            title = s.get("title", "")
            if s["layout"] == "pause":
                typ = "暂停卡"
                title = f'保留题面（承接 {s.get("pauseFrom", "")}）'
                nbeats = 0
            elif s["layout"] == "stem":
                typ = "例题"
            elif "解析" in s.get("title", ""):
                typ = "例题解析"
            else:
                typ = "教学卡"
            w.writerow([i, s["id"], typ, fmt_ts(s["start"]), f"{s['duration']:.1f}",
                        title, nbeats if s["layout"] == "pause" else len(s.get("beats", [])),
                        s.get("ref", "")])
    print(f"[nv] {out}")


if __name__ == "__main__":
    main()
