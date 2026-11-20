# -*- coding: utf-8 -*-
"""timings.json -> 底部字幕 SRT（按标点断句，单行限长）

用法: python make_srt.py [项目目录] [--max-len 14] [--min-dur 0.9] [--hold 0.35]
产出: out/<name>.srt

时间来源是配音服务返回的字级时间戳：每个字的起始时刻按词内线性插值，
所以断句边界落在 SentenceSplit 的任意字符上都能拿到近似精确的时间。
"""
import bisect
import os
import sys

from nv_common import load_json, load_project, project_root

STRONG = "。！？!?；;…"
WEAK = "，,：:"
TAIL_STRIP = "。，,、；;：: "
# 这些字符连成一片时视为一个不可拆的原子（公式、英文、数字）
SYMBOLS = "−≤≥≠≈×÷±∞∑∫√→←↔∈∀∃·—…"


def char_times(text, words):
    """把词级时间戳摊到每个字符上：ct[p] = 第 p 个字开始说的时刻。"""
    n = len(text)
    ct = [None] * (n + 1)
    for w in words:
        i, j = int(w["i"]), int(w["j"])
        t, d = float(w["t"]), float(w["d"])
        i, j = max(0, i), min(n, j)
        if j <= i:
            continue
        span = j - i
        for p in range(i, j):
            ct[p] = t + (p - i) / span * d
        ct[j] = t + d if ct[j] is None else max(ct[j], t + d)
    # 标点等未覆盖位置：用前一个字的时间兜底，再做后向填充
    for p in range(1, n + 1):
        if ct[p] is None:
            ct[p] = ct[p - 1]
    first = next((v for v in ct if v is not None), 0.0)
    for p in range(n + 1):
        if ct[p] is None:
            ct[p] = first
    return ct


def _is_symbol(ch):
    if ch.isspace():
        return False
    o = ord(ch)
    if o < 128:
        return True
    return (ch in SYMBOLS or 0x0300 <= o <= 0x03FF or 0x2070 <= o <= 0x209F
            or o in (0xB2, 0xB3, 0xB9) or 0x2100 <= o <= 0x22FF)


def vlen(s):
    """视觉宽度：中文 1 格，ASCII/数学符号约 0.55 格。"""
    return sum(0.55 if (ord(c) < 128 or c in SYMBOLS) else 1.0 for c in s)


def atomize(text):
    """切成不可再拆的原子：连续 ASCII/希腊字母/数学符号算一块，中文一字一块。"""
    atoms, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if _is_symbol(ch):
            j = i
            while j < n and _is_symbol(text[j]):
                j += 1
            atoms.append((i, j))
            i = j
        else:
            atoms.append((i, i + 1))
            i += 1
    return atoms


def split_text(text, words, max_len=22, soft_min=6):
    """按标点断句；超长时退到最近的词边界，绝不劈开公式或半个词。"""
    atoms = atomize(text)
    if not atoms:
        return []
    wb = sorted({int(w["j"]) for w in words if w.get("j")})

    def word_dist(p):
        """到最近词边界的字符距离。"""
        k = bisect.bisect_left(wb, p)
        best = 99
        for q in (k - 1, k):
            if 0 <= q < len(wb):
                best = min(best, abs(wb[q] - p))
        return best
    segs, k, n = [], 0, len(atoms)
    while k < n:
        length, j, cut = 0, k, None
        while j < n:
            a, b = atoms[j]
            chunk = text[a:b]
            if chunk in STRONG and j > k:
                j += 1
                cut = j
                break
            add = vlen(chunk)
            length += add
            j += 1
            # 只有长到一行放不下（max_len+10）才硬切，否则等标点
            if length >= max_len + 10:
                cut = j
                for p in range(j, max(k, j - 6), -1):
                    a2, b2 = atoms[p - 1]
                    if word_dist(b2) <= (1 if b2 - a2 > 1 else 0):
                        cut = p
                        break
                break
            if (chunk in WEAK or chunk == "——") and length >= soft_min:
                cut = j
                break
        if cut is None:
            cut = n
        # 标点永远跟着前一段，不许落到下一段开头
        while cut < n and text[atoms[cut][0]:atoms[cut][1]] in STRONG + WEAK + "、":
            cut += 1
        segs.append((atoms[k][0], atoms[cut - 1][1]))
        k = cut

    # 收拾碎段：段首的标点只把标点本身搬回前段，别把整段拖过去
    head_punct = STRONG + WEAK + "、）)】」”’》"
    cleaned = []
    for a, b in segs:
        s = text[a:b]
        if not s.strip():
            continue
        m = 0
        while m < len(s) and s[m] in head_punct:
            m += 1
        if cleaned and m:
            cleaned[-1] = (cleaned[-1][0], a + m)
            if m < len(s):
                cleaned.append((a + m, b))
            continue
        cleaned.append((a, b))

    merged = []
    for a, b in cleaned:
        n = vlen(text[a:b].strip())
        if merged and n <= 2:
            pa, pb = merged[-1]
            if vlen(text[pa:pb].strip()) + n <= max_len + 2:
                merged[-1] = (pa, b)
                continue
        merged.append((a, b))

    # 半句（以逗号收尾或过短）不要单独成条：并到前一条，读起来才连贯
    final = []
    for i, (a, b) in enumerate(merged):
        s = text[a:b].strip()
        if final and vlen(s) <= 6:
            pa, pb = final[-1]
            prev = text[pa:pb].strip()
            # 前一条也没收句，说明是同一句被逗号切开，短尾巴要带回去
            same_sentence = (s[-1] not in STRONG) or (prev and prev[-1] not in STRONG)
            if same_sentence and vlen(prev) + vlen(s) <= max_len + 6:
                final[-1] = (pa, b)
                continue
        if (vlen(s) <= 3 and i + 1 < len(merged)
                and not s.endswith(tuple(STRONG))):
            na, nb = merged[i + 1]
            if vlen(s) + vlen(text[na:nb].strip()) <= max_len + 4:
                final.append((a, nb))
                merged[i + 1] = (a, nb)
                continue
        final.append((a, b))
    merged = final

    out = []
    for a, b in merged:
        s = text[a:b]
        lead = len(s) - len(s.lstrip())
        trail = len(s) - len(s.rstrip())
        out.append((a + lead, b - trail))
    return out


def build_cues(root, max_len, min_dur, hold):
    meta, cards = load_project(root)
    tl = load_json(os.path.join(root, "timeline.json"))
    timings = {x["id"]: x for x in load_json(os.path.join(root, "timings.json"))}
    tts = {c["id"]: c.get("tts", "") for c in cards}
    end_total = float(tl["duration"])

    cues = []
    for sc in tl["scenes"]:
        cid = sc.get("id")
        if sc.get("layout") == "pause" or not sc.get("audio") or cid not in timings:
            continue
        text = tts.get(cid, "")
        if not text.strip():
            continue
        tim = timings[cid]
        words = tim.get("words") or []
        ct = char_times(text, words)
        base = float(sc["start"])
        segs = split_text(text, words, max_len=max_len)
        sc_end = base + float(sc.get("duration", tim["dur"]))

        local = []
        for a, b in segs:
            s, e = ct[a], ct[b] if b < len(ct) else ct[-1]
            if e <= s:
                e = s + 0.5
            s, e = max(0.0, s), min(e, float(sc.get("duration", tim["dur"])))
            txt = text[a:b].rstrip(TAIL_STRIP)
            if not txt:
                continue
            local.append([base + s, base + e, txt])

        # 补足最短时长；最后一条多留一点，别念完就闪没
        for k, cue in enumerate(local):
            nxt = local[k + 1][0] if k + 1 < len(local) else sc_end
            if cue[1] - cue[0] < min_dur:
                cue[1] = min(cue[0] + min_dur, nxt)
            if k + 1 == len(local):
                cue[1] = min(cue[1] + hold, sc_end, end_total)
        cues.extend(c for c in local if c[1] > c[0] + 0.05)
    return cues


def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--max-len", type=int, default=22, help="单行最多视觉宽度（中文 1 格、ASCII 0.55 格）")
    ap.add_argument("--min-dur", type=float, default=0.9, help="单条最短停留秒数")
    ap.add_argument("--hold", type=float, default=0.35, help="末条延后消失秒数")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = project_root(a.root)
    meta = load_json(os.path.join(root, "project.json"))
    tl = load_json(os.path.join(root, "timeline.json"))
    name = tl.get("name") or meta.get("name") or "video"
    out = a.out or os.path.join(root, "out", f"{name}.srt")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    cues = build_cues(root, a.max_len, a.min_dur, a.hold)
    if not cues:
        sys.exit("[nv] 没生成任何字幕：检查 tts 与 timings.json")

    with open(out, "w", encoding="utf-8") as f:
        for i, (s, e, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{ts(s)} --> {ts(e)}\n{txt}\n\n")

    lens = [vlen(c[2]) for c in cues]
    dur = sum(c[1] - c[0] for c in cues)
    over = [c for c in cues if vlen(c[2]) > a.max_len]
    print(f"[nv] {out}  {len(cues)} 条 / 总显字 {dur:.0f}s / 平均 {sum(lens)/len(lens):.1f} 字"
          f" / 最长 {max(lens)} 字")
    if over:
        print(f"[nv] 警告：{len(over)} 条超过 {a.max_len} 字")
        for c in over[:5]:
            print("     ", c[2])
    print("[nv] 前 6 条：")
    for s, e, txt in cues[:6]:
        print(f"  {ts(s)[3:]} → {ts(e)[3:]}  {txt}")


if __name__ == "__main__":
    main()
