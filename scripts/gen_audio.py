# -*- coding: utf-8 -*-
"""逐卡合成旁白（千问 Qwen-Audio-TTS 流式接口），记录字级时间戳（驱动画面逐字展开）

用法: python gen_audio.py [项目目录] [--dry-run] [--force] [--voice longanhuan_v3.1] [--rate 1.12]

省事：每张卡带合成指纹（文案/音色/语速/模型），指纹没变就复用已有音频，
改了文案会自动重录；`--dry-run` 只看要动几张卡，不调接口。

鉴权（按顺序找，找到即用）:
  1. --api-key
  2. 环境变量 DASHSCOPE_API_KEY
  3. ~/.dashscope/config 里的一行 DASHSCOPE_API_KEY=sk-xxx
  4. 项目目录下的 .env 同名字段

依赖: pip install websocket-client
"""
import hashlib
import json
import os
import re
import sys
import time
import uuid

from nv_common import (load_project, load_json, save_json, project_root,
                       ensure_dir, duration_of)

DEFAULT_MODEL = "qwen-audio-3.1-tts-flash"
DEFAULT_VOICE = "longanhuan_v3.1"
DEFAULT_WS = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

_PUNCT = "，。、；：？！,.;:?!…—（）()《》“”‘’\"'"


# ---------------------------------------------------------------- 配置解析

def _read_kv(path, key):
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def resolve_api_key(explicit, root="."):
    if explicit:
        return explicit.strip()
    for k in ("DASHSCOPE_API_KEY", "QWEN_API_KEY"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    for p in (os.path.expanduser("~/.dashscope/config"),
              os.path.expanduser("~/.qwen/config")):
        v = _read_kv(p, "DASHSCOPE_API_KEY")
        if v:
            return v
    v = _read_kv(os.path.join(root, ".env"), "DASHSCOPE_API_KEY")
    if v:
        return v
    sys.exit("[nv] 没找到千问 API Key。三选一：\n"
             "      export DASHSCOPE_API_KEY=sk-xxx\n"
             "      echo 'DASHSCOPE_API_KEY=sk-xxx' >> ~/.dashscope/config\n"
             "      命令行加 --api-key sk-xxx（不写进 project.json）")


def norm_rate(v):
    """'+12%' / 1.12 / '1.1' 统一成 0.5–2.0 的浮点倍数。"""
    if v is None:
        return 1.0
    if isinstance(v, (int, float)):
        r = float(v)
    else:
        s = str(v).strip()
        m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*%$", s)
        try:
            r = 1 + float(m.group(1)) / 100.0 if m else float(s)
        except (AttributeError, ValueError):
            r = 1.0
    return max(0.5, min(2.0, round(r, 3)))


def norm_voice(v):
    v = (v or DEFAULT_VOICE).strip()
    if v.startswith(("zh-CN-", "zh-TW-", "en-US-", "Microsoft")) or "Neural" in v:
        print(f"[!] project.json 里的 voice 是 edge-tts 音色（{v}），改用千问默认音色 "
              f"{DEFAULT_VOICE}；可在 project.json 换成任意 Qwen 音色名", flush=True)
        return DEFAULT_VOICE
    return v


# ---------------------------------------------------------------- 千问合成

def card_sig(cfg, text):
    """一张卡的合成指纹：只要文案/音色/语速/模型任一项变了，才需要重录。"""
    raw = "|".join([cfg["model"], cfg["voice"], str(cfg["rate"]), cfg["format"], text])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _send(ws, task_id, action, payload):
    ws.send(json.dumps({
        "header": {"action": action, "task_id": task_id, "streaming": "duplex"},
        "payload": payload,
    }, ensure_ascii=False))


def _one_task(text, cfg):
    """建一条连接跑一张卡，返回 (音频字节, 字级时间戳列表)。"""
    import websocket

    ws = websocket.create_connection(
        cfg["ws_url"],
        header=["Authorization: bearer " + cfg["api_key"]],
        timeout=cfg["timeout"],
    )
    task_id = uuid.uuid4().hex
    audio = bytearray()
    by_sentence = {}
    usage = {}
    err = None
    try:
        _send(ws, task_id, "run-task", {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "model": cfg["model"],
            "parameters": {
                "text_type": "PlainText",
                "voice": cfg["voice"],
                "format": cfg["format"],
                "sample_rate": cfg["sample_rate"],
                "volume": 50,
                "rate": cfg["rate"],
                "pitch": 1,
                "enable_ssml": False,
                "word_timestamp_enabled": True,
                "language_hints": ["zh"],
            },
            "input": {},
        })
        while True:
            msg = ws.recv()
            if isinstance(msg, bytes):
                audio += msg
                continue
            data = json.loads(msg)
            head = data.get("header") or {}
            event = head.get("event")
            if event == "task-started":
                _send(ws, task_id, "continue-task", {"input": {"text": text}})
                _send(ws, task_id, "finish-task", {"input": {}})
            elif event == "result-generated":
                out = (data.get("payload") or {}).get("output") or {}
                sent = out.get("sentence") or {}
                # words 是「累积增长」的：sentence-begin 给开头几个，
                # 之后的 sentence-synthesis 逐句补齐，偶尔夹几条空数组。
                # 所以按句号收最新一次非空结果，空数组直接忽略。
                if sent.get("words"):
                    by_sentence[sent.get("index", 0)] = sent["words"]
            elif event == "task-finished":
                usage = (data.get("payload") or {}).get("usage") or {}
                break
            elif event == "task-failed":
                err = head.get("error_message") or head.get("error_code") or "task-failed"
                break
            elif event == "error":
                err = (data.get("payload") or {}).get("message") or "error"
                break
    finally:
        try:
            ws.close()
        except Exception:
            pass
    if err:
        raise RuntimeError(err)
    words = [w for i in sorted(by_sentence) for w in by_sentence[i]]
    return bytes(audio), words, usage


def _map_words(words, text):
    """把服务端的字级时间戳对回原文字符区间，产出 timings 里的 words。

    服务端是对“它念出来的文本”做对齐的：遇到 X(t) 这类符号，它会念成
    “X 左括号 t 右括号”，这些口语化的字在旁白文本里并不存在。
    旧逻辑找不到时原地占一格，导致后面的字符区间整体漂移、节拍全部提前。
    现在改成：找不到的粒度直接丢弃（时间由下一个命中的粒度兜住），只保留
    真正能在旁白里定位到的粒度。
    """
    out, pos = [], 0
    for w in words:
        t = (w.get("text") or "").strip()
        if not t:
            continue
        k = text.find(t, pos)
        if k < 0:
            continue
        i, j = k, k + len(t)
        pos = j
        b = (w.get("begin_time") or 0) / 1000.0
        e = (w.get("end_time") or b * 1000) / 1000.0
        out.append({"t": round(b, 3), "d": round(max(0.0, e - b), 3),
                    "w": t, "i": i, "j": pos})
    return out


def _interp_words(text, dur):
    """拿不到字级时间戳时的兜底：按字重比例铺满整段时长（标点多留一点）。"""
    idx = [(i, ch) for i, ch in enumerate(text)]
    if not idx:
        return []
    weights = []
    for _, ch in idx:
        if ch in _PUNCT:
            weights.append(3.0)
        elif ch.isspace():
            weights.append(0.2)
        else:
            weights.append(1.0)
    total = sum(weights)
    out, acc = [], 0.0
    for (i, ch), w in zip(idx, weights):
        t = dur * acc / total
        acc += w
        out.append({"t": round(t, 3), "d": round(dur * w / total, 3),
                    "w": ch, "i": i, "j": i + 1})
    return out


def synth(text, cfg, out_path, tries=3):
    last = None
    for attempt in range(tries):
        try:
            audio, words, usage = _one_task(text, cfg)
            if not audio:
                raise RuntimeError("空音频")
            with open(out_path, "wb") as f:
                f.write(audio)
            return words, usage
        except Exception as e:
            last = e
            if attempt < tries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{os.path.basename(out_path)} 合成失败: {last}")


# ---------------------------------------------------------------- 主流程

def run(root, force, voice, rate, api_key, model, ws_url, dry_run=False):
    meta, cards = load_project(root)
    cfg = {
        "api_key": api_key or "dry-run",  # dry-run 不调接口，不读 Key
        "model": model or meta.get("tts_model") or DEFAULT_MODEL,
        "voice": norm_voice(voice or meta.get("voice")),
        "rate": norm_rate(rate if rate is not None else meta.get("rate")),
        "format": meta.get("tts_format") or "mp3",
        "sample_rate": int(meta.get("tts_sample_rate") or 24000),
        "ws_url": ws_url or os.environ.get("DASHSCOPE_WS_URL") or DEFAULT_WS,
        "timeout": 180,
    }
    if not dry_run:
        cfg["api_key"] = resolve_api_key(api_key, root)

    audio_dir = ensure_dir(root, "audio")
    old = {}
    if not force and os.path.exists(os.path.join(root, "timings.json")):
        old = {x["id"]: x for x in load_json(os.path.join(root, "timings.json"))}

    ext = cfg["format"]
    print(f"[nv] {cfg['model']} / {cfg['voice']} / rate {cfg['rate']}")

    # 先算账：只有文案/音色/语速变了才重录，一分额度都不多花
    plan = []
    for card in cards:
        cid = card["id"]
        sig = card_sig(cfg, card["tts"])
        path = os.path.join(audio_dir, f"{cid}.{ext}")
        have = cid in old and os.path.exists(path)
        old_sig = old[cid].get("sig") if have else None
        reuse = bool(have) and not force and (old_sig is None or old_sig == sig)
        plan.append({"card": card, "sig": sig, "path": path, "reuse": reuse,
                     "legacy": bool(have) and old_sig is None})

    todo = [p for p in plan if not p["reuse"]]
    chars = sum(len(re.sub(r"\s", "", p["card"]["tts"])) for p in todo)

    if dry_run:
        for p in plan:
            tag = "复用" if p["reuse"] else "合成"
            print(f"  {p['card']['id']:>6} {tag}  {len(p['card']['tts']):>4} 字")
        print(f"\n[nv] 待合成 {len(todo)} 张 / 可复用 {len(plan) - len(todo)} 张")
        print(f"[nv] 预计消耗约 {chars} 字符 ≈ {int(chars * 1.9)} tokens（本次不调接口）")
        return

    results, tokens = {}, 0
    total = len(cards)
    for n, p in enumerate(plan, 1):
        card, cid = p["card"], p["card"]["id"]
        if p["reuse"]:
            results[cid] = dict(old[cid], sig=p["sig"])
            note = "（旧 timings 无签名，按原样复用）" if p["legacy"] else ""
            print(f"  {cid:>6} 复用 {old[cid]['dur']:5.1f}s{note}", flush=True)
            continue
        raw, usage = synth(card["tts"], cfg, p["path"])
        tokens += int(usage.get("total_tokens") or 0)
        dur = duration_of(p["path"])
        words = _map_words(raw, card["tts"]) if raw else []
        # 质量闸：符号密集的旁白（X(t)、cos ω₀t 这类）会让服务端粒度大面积对不上，
        # 少量幸存粒度还会“短粒度乱配”，时间戳非单调。命中太少或时间倒退，
        # 就整卡退回按字重插值——节拍位置是近似值，但单调、 sane。
        frac = len(words) / max(1, len(raw)) if raw else 0.0
        mono = all(words[k + 1]["t"] >= words[k]["t"] - 0.05 for k in range(len(words) - 1))
        if words and (frac < 0.6 or not mono):
            print(f"  [!] {cid} 字级时间戳对不上（命中 {len(words)}/{len(raw)}，"
                  f"{'非单调' if not mono else '覆盖不足'}），改按字数插值", flush=True)
            words = _interp_words(card["tts"], dur)
        if not words:  # 服务端没回时间戳：按字数铺开，仍能渲
            words = _interp_words(card["tts"], dur)
            print(f"  [!] {cid} 没拿到字级时间戳，已按字数插值", flush=True)
        if not dur:
            dur = (words[-1]["t"] + words[-1]["d"]) if words else 0.0
        chars_one = len(re.sub(r"\s", "", card["tts"]))
        cps = chars_one / max(0.1, dur)
        results[cid] = {"id": cid, "dur": round(dur, 3), "cps": round(cps, 2),
                        "sig": p["sig"], "words": words}
        print(f"  {cid:>6} [{n}/{total}] {dur:5.1f}s  {cps:4.1f} cps  "
              f"{len(words)} 字  {usage.get('total_tokens', '?')} tok", flush=True)

    ordered = [results[c["id"]] for c in cards]
    save_json(os.path.join(root, "timings.json"), ordered)

    cps_all = [x["cps"] for x in ordered]
    print(f"\n[nv] {len(ordered)} 张卡，语速 {sum(cps_all)/len(cps_all):.2f} cps "
          f"(min {min(cps_all):.1f} / max {max(cps_all):.1f})")
    if tokens:
        print(f"[nv] 本次新合成 {len(todo)} 张，消耗 {tokens} tokens")
    else:
        print("[nv] 全部复用，本次零消耗")
    slow = [x["id"] for x in ordered if x["cps"] < 4.6]
    fast = [x["id"] for x in ordered if x["cps"] > 6.2]
    if slow:
        print(f"[!] 偏慢（<4.6 cps）：{', '.join(slow)}　可把 rate 调大一点")
    if fast:
        print(f"[!] 偏快（>6.2 cps）：{', '.join(fast)}　可把 rate 调小一点")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="只算要合成几张、多少字，不调用接口")
    ap.add_argument("--voice")
    ap.add_argument("--rate")
    ap.add_argument("--api-key")
    ap.add_argument("--model")
    ap.add_argument("--ws-url")
    a = ap.parse_args()
    try:
        import websocket  # noqa: F401
    except ImportError:
        if not a.dry_run:
            sys.exit("[nv] 缺少 websocket-client：pip install websocket-client")
    root = project_root(a.root)
    run(root, a.force, a.voice, a.rate, a.api_key, a.model, a.ws_url, a.dry_run)


if __name__ == "__main__":
    main()
