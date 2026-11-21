# -*- coding: utf-8 -*-
"""cards.json + timings.json  ->  timeline.json  (scene graph for the stage)

用法: python build_timeline.py [项目目录]
"""
import os
import re
import sys

from nv_common import load_project, load_json, save_json, project_root, fmt_ts

RISE = {"title": 0.80, "main": 1.20, "note": 0.90, "step": 0.90,
        "banner": 1.20, "formula": 1.40, "chip": 0.60, "diagram": 1.20}


def plain_len(html):
    t = re.sub(r"\\\(.*?\\\)|\$\$.*?\$\$", "XXXX", html or "")
    t = re.sub(r"\\[a-zA-Z]+", "", t)
    return max(4, len(re.sub(r"[{}$^_\\]", "", t)))


def build(root):
    meta, cards = load_project(root)
    timings = {x["id"]: x for x in load_json(os.path.join(root, "timings.json"))}
    fps = int(meta.get("fps", 24))
    lead = float(meta.get("lead", 0.4))
    tail = float(meta.get("tail", 0.9))
    gap = float(meta.get("gap", 0.55))
    pause_dur = float(meta.get("pause_duration", 3.0))
    module_gap = float(meta.get("module_gap", 0.5))
    end_pad = float(meta.get("end_pad", 0.4))
    modules = meta.get("modules") or {"A": {"label": "模块 A", "accent": "#2F5D8A", "tint": "#E8EFF6"}}
    default_mod = next(iter(modules))

    missing_all = []

    # 公式/符号速查表：按页面正文里首次出现的位置，每页挑 1–2 条挂到右上角小卡
    gloss_path = os.path.join(root, "glossary.json")
    GLOSS = []
    if os.path.exists(gloss_path):
        try:
            GLOSS = (load_json(gloss_path) or {}).get("items", [])
        except Exception as e:
            print(f"[nv] glossary.json 读取失败，速查卡关闭：{e}")
    seen_gloss = set()

    def pick_gloss(card, beats):
        if not GLOSS or card.get("gloss") is False:
            return []
        text = "\n".join([card.get("title", ""), card.get("stem_bar", "")]
                         + [b.get("html") or "" for b in beats])
        hits = []
        for i, g in enumerate(GLOSS):
            pos = text.find(g.get("k", ""))
            if pos >= 0 and g.get("sym"):
                hits.append((pos, i, g))
        if not hits:
            return []
        hits.sort(key=lambda x: (x[0], x[1]))
        new = [g for _, _, g in hits if g["k"] not in seen_gloss]
        old = [g for _, _, g in hits if g["k"] in seen_gloss]
        out = (new[:2] if new else old[:1])
        seen_gloss.update(g["k"] for g in out)
        return [{"sym": g["sym"], "note": g.get("note", "")} for g in out]

    def t_at(cid, phrase):
        text = next(c["tts"] for c in cards if c["id"] == cid)
        if not phrase or phrase.startswith("__"):
            return (1.2 if phrase == "__diagram__" else 0.15), 0
        idx = text.find(phrase)
        if idx < 0:
            return None, None
        for w in timings[cid]["words"]:
            if w.get("j", 0) > idx:
                return max(0.05, w["t"]), idx
        return timings[cid]["dur"], idx

    def build_scene(card, page):
        cid = card["id"]
        if cid not in timings:
            sys.exit(f"[nv] {cid} 没有配音：先跑 gen_audio.py")
        tim = timings[cid]
        mod_key = card.get("module") or default_mod
        mod = modules.get(mod_key, modules[default_mod])

        raw = card.get("beats") or []
        beats_in = []
        for b in raw:
            if isinstance(b, dict):
                beats_in.append((b["kind"], b.get("content"), b.get("trigger")))
            else:
                beats_in.append((b[0], b[1] if len(b) > 1 else None, b[2] if len(b) > 2 else None))

        if not any(k == "title" for k, _, _ in beats_in) and card.get("layout") != "example":
            beats_in.insert(0, ("title", None, "__start__"))
        auto_diagram = False
        if card.get("diagram") and not any(k == "diagram" for k, _, _ in beats_in):
            beats_in.append(("diagram", None, "__diagram__"))
            auto_diagram = True
        auto_t = None
        for k, _, tr in beats_in:
            if k == "main":
                auto_t = t_at(cid, tr)[0]
                break

        beats, missing = [], []
        prev, prev_rise, step_no = -gap, 0, 0

        for kind, content, trig in beats_in:
            if trig == "__diagram__" and auto_t is not None:
                t = auto_t + 0.55
            else:
                t, _ = t_at(cid, trig)
            if t is None:
                if kind == "diagram":
                    t = prev + 0.7
                else:
                    missing.append(trig)
                    t = prev + 1.2
            rise = float(RISE.get(kind, 0.8))
            if kind in ("note", "step"):
                rise = min(1.8, max(0.8, plain_len(content) / 13.0))
            if auto_diagram and kind == "diagram":
                # 图示独立于文字流：紧跟在第二拍（知识点/定义）之后成形，先给画面再讲细节
                ref = beats[1] if len(beats) >= 2 else beats[0]
                start = max(0.4, ref["start"] + ref["rise"] + gap)
            else:
                start = max(prev + gap, t)
                if beats and beats[-1]["kind"] == "title":
                    # 标题先写完，再上第一块内容
                    start = max(start, prev + prev_rise + gap * 0.6)
            start = min(start, max(0.4, tim["dur"] - 0.6))
            if kind == "title":
                content = card["title"]
            elif kind == "main":
                content = content or card.get("screen") or ""
            elif kind == "step":
                step_no += 1
            beats.append({"kind": kind, "html": content, "start": round(start, 3),
                          "rise": round(rise, 3), "trigger": trig,
                          **({"n": str(step_no)} if kind == "step" else {})})
            if auto_diagram and kind == "diagram":
                continue          # 图示跟随主讲公式，不参与文字节拍的顺延链
            prev, prev_rise = start, rise

        # 逐字展开时长自适应：保证同屏最多两样在生长，且不推迟出现时刻
        seq = [b for b in beats if b["kind"] != "diagram"]
        for i, b in enumerate(seq):
            lim = tim["dur"] - 0.2
            if i + 1 < len(seq):
                lim = min(lim, seq[i + 1]["start"] - gap * 0.6)
            if i + 2 < len(seq):
                lim = min(lim, seq[i + 2]["start"] - gap)
            avail = lim - b["start"]
            b["rise"] = round(max(0.35, min(b["rise"], avail)), 3)

        dur = max(tim["dur"] + tail,
                  beats[-1]["start"] + beats[-1]["rise"] + 1.0 if beats else 3.0, 3.0)

        d2 = None
        d2 = card.get("diagram2")
        if isinstance(d2, str) and d2:
            t2, _ = t_at(cid, d2)
            if t2 is not None:
                d2 = round(t2 + 0.25, 3)

        label = mod.get("label", f"模块 {mod_key}")
        return {
            "id": cid, "title": card["title"], "module": mod_key, "layout": card.get("layout", "concept"),
            "moduleLabel": label, "accent": mod.get("accent", "#2F5D8A"), "tint": mod.get("tint", "#E8EFF6"),
            "page": f"{page} / {len(cards)}", "ref": card.get("ref", ""),
            "diagram": card.get("diagram"), "diagramParams": card.get("diagramParams") or {},
            "stemBar": card.get("stem_bar") or "",
            "stem": card.get("stem") or "", "exNo": card.get("ex_no") or "",
            "exTitle": card.get("ex_title") or "", "used": card.get("used") or [],
            "gloss": pick_gloss(card, beats),
            "diagram2": d2, "audio": f"audio/{cid}.mp3",
            "duration": round(dur, 3), "beats": beats, "missing": missing,
            "autoDiagram": auto_diagram,
        }

    scenes, clock, page, last_mod = [], lead, 0, None
    for card in cards:
        page += 1
        sc = build_scene(card, page)
        if page == 1 and sc["beats"] and sc["beats"][0]["kind"] == "title":
            sc["beats"][0]["start"] = float(meta.get("first_title_at", 0.35))
        if last_mod is not None and sc["module"] != last_mod:
            clock += module_gap
        last_mod = sc["module"]
        sc["start"] = round(clock, 3)
        clock += sc["duration"]
        scenes.append(sc)
        missing_all += [(card["id"], m) for m in sc["missing"]]
        pa = card.get("pause_after") or 0
        if pa:
            # pause_after 为整数 n 时连续生成 n 张暂停卡（一个模块多道例题）
            n = pa if isinstance(pa, int) else 1
            for k in range(n):
                # 暂停卡继承本卡画面：题目留在屏幕上（压淡），只叠遮罩与底部提示条
                hold = dict(sc)
                hold.update({"id": f"PAUSE{page}" if n == 1 else f"PAUSE{page}_{k+1}",
                             "layout": "pause", "duration": pause_dur,
                             "title": sc["title"],
                             "pauseText": meta.get("pause_text", "请暂停，自己先算一遍"),
                             "audio": None, "start": round(clock, 3),
                             "pauseFrom": sc["id"]})
                scenes.append(hold)
                clock += pause_dur
    clock += end_pad

    timeline = {"fps": fps, "width": int(meta.get("width", 1280)), "height": int(meta.get("height", 720)),
                "name": meta.get("name", "notebook-video"), "meta": meta,
                "duration": round(clock, 3), "scenes": scenes, "missing": missing_all}
    save_json(os.path.join(root, "timeline.json"), timeline)
    return timeline


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    root = project_root(ap.parse_args().root)
    tl = build(root)
    print(f"[nv] timeline: {len(tl['scenes'])} scenes, {fmt_ts(tl['duration'])} ({tl['duration']}s)")
    for s in tl["scenes"]:
        if s["layout"] == "pause":
            print(f"  {s['id']:>8}  PAUSE  {fmt_ts(s['start'])}  +{s['duration']:.1f}s  hold {s.get('pauseFrom','')}")
            continue
        print(f"  {s['id']:>8}  {fmt_ts(s['start'])}  {s['duration']:5.1f}s  beats={len(s['beats']):2d}  {s['title'][:26]}")
    if tl["missing"]:
        print("\n[!] 触发词没找到（这些节拍用了兜底时间）：")
        for cid, m in tl["missing"]:
            print(f"    {cid}: {m}")
        sys.exit(1)
    print("\n[nv] 触发词全部命中")


if __name__ == "__main__":
    main()
