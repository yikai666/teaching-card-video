# -*- coding: utf-8 -*-
"""新建一个 notebook-video 项目（复制舞台模板、写入最小 project.json / cards.json）

用法: python init_project.py <目标目录> --name "第2章_xxx"
"""
import json
import os
import shutil
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--name")
    ap.add_argument("--update-stage", action="store_true")
    a = ap.parse_args()
    dest = os.path.abspath(a.dest)
    name = a.name or os.path.basename(dest)
    os.makedirs(dest, exist_ok=True)
    os.makedirs(os.path.join(dest, "assets"), exist_ok=True)

    stage = os.path.join(dest, "stage.html")
    if a.update_stage or not os.path.exists(stage):
        shutil.copy(os.path.join(SKILL, "assets", "stage.html"), stage)
    tex = os.path.join(dest, "assets", "tex-svg.js")
    if not os.path.exists(tex):
        shutil.copy(os.path.join(SKILL, "assets", "tex-svg.js"), tex)

    project = {
        "name": name,
        "course": "课程名",
        "chapter": "第 X 章 章节名",
        "fps": 24, "width": 1280, "height": 720,
        "voice": "zh-CN-XiaoxiaoNeural", "rate": "+12%",
        "lead": 0.4, "tail": 0.9, "gap": 0.55, "pause_duration": 3.0,
        "pause_text": "请暂停，自己先算一遍",
        "modules": {
            "A": {"label": "模块 A · 概念", "accent": "#2F5D8A", "tint": "#E8EFF6"},
            "B": {"label": "模块 B · 方法", "accent": "#8A4B2F", "tint": "#F6EBE4"},
            "C": {"label": "模块 C · 应用", "accent": "#2F6B4F", "tint": "#E6F2EC"}
        }
    }
    cards = {"cards": [{
        "id": "A1", "module": "A", "layout": "concept", "ref": "[1-1 p1]",
        "title": "示例：把一句话讲成一个画面",
        "screen": "\\(X:S\\to\\mathbb{R}\\) 单值映射",
        "tts": "先给结论：随机变量不是一个飘来飘去的数，它是一个函数。你把试验结果代进去，它就按规则还你一个实数。",
        "diagram": "map",
        "beats": [["title", None, "先给结论"], ["main", None, "它是一个函数"],
                  ["note", "每个结果 \\(e\\) 对应一个实数 \\(X(e)\\)", "代进去"]]
    }]}
    for fn, data in [("project.json", project), ("cards.json", cards)]:
        p = os.path.join(dest, fn)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"[nv] 已创建 {dest}")
    print("下一步：编辑 cards.json → python scripts/gen_audio.py <dir> → "
          "python scripts/build_timeline.py <dir> → python scripts/render_stills.py <dir>")


if __name__ == "__main__":
    main()
