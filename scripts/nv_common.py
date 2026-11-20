# -*- coding: utf-8 -*-
"""Shared helpers for the teaching-card-video pipeline."""
import json
import os
import re
import subprocess
import sys


def project_root(arg=None):
    root = os.path.abspath(arg or os.getcwd())
    if not os.path.isfile(os.path.join(root, "project.json")):
        sys.exit(f"[nv] {root} 不是项目目录：缺少 project.json")
    return root


def load_json(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        sys.exit(f"[nv] 缺少文件：{path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_project(root):
    meta = load_json(os.path.join(root, "project.json"))
    raw = load_json(os.path.join(root, "cards.json"))
    cards = raw.get("cards", raw) if isinstance(raw, dict) else raw
    if not isinstance(cards, list) or not cards:
        sys.exit("[nv] cards.json 里没有卡片")
    return meta, cards


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def fmt_ts(sec):
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


def clean_math(text):
    """Strip LaTeX wrappers for labels/titles used outside MathJax."""
    t = str(text or "")
    while "\\(" in t and "\\)" in t:
        i = t.index("\\(")
        j = t.index("\\)", i)
        t = t[:i] + t[i + 2:j] + t[j + 2:]
    for a, b in [("\\mathrm{Cov}", "Cov"), ("\\delta", "δ"), ("\\sigma", "σ"),
                 ("\\frac", ""), ("\\sqrt", ""), ("\\", ""), ("{", ""), ("}", "")]:
        t = t.replace(a, b)
    return t


def ffmpeg_bin():
    """Any working ffmpeg (decode / probe only)."""
    for exe in ("ffmpeg",):
        try:
            if subprocess.run([exe, "-version"], capture_output=True).returncode == 0:
                return exe
        except FileNotFoundError:
            pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("[nv] 找不到 ffmpeg：apt install ffmpeg 或 pip install imageio-ffmpeg")


def ffmpeg_exe():
    """A build with libx264 (encoding)."""
    for exe in ("ffmpeg",):
        try:
            out = subprocess.run([exe, "-hide_banner", "-encoders"],
                                 capture_output=True, text=True).stdout
            if "libx264" in out:
                return exe
        except FileNotFoundError:
            pass
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        out = subprocess.run([exe, "-hide_banner", "-encoders"],
                             capture_output=True, text=True).stdout
        if "libx264" in out:
            return exe
    except Exception:
        pass
    sys.exit("[nv] 找不到带 libx264 的 ffmpeg：apt install ffmpeg 或 pip install imageio-ffmpeg")


def probe_duration(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True).stdout
        if out.strip():
            return float(out.strip())
    except FileNotFoundError:
        pass
    exe = ffmpeg_bin()
    txt = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", txt)
    if not m:
        sys.exit(f"[nv] 读不到时长：{path}")
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


_MP3_BR = {
    3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],   # MPEG1 L3
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],      # MPEG2 L3
    0: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],      # MPEG2.5 L3
}
_MP3_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def mp3_duration(path):
    """纯 Python 走 MP3 帧头算时长——不依赖 ffmpeg（云 TTS 产物是 CBR/AAC 之外的纯 MP3）。"""
    with open(path, "rb") as f:
        data = f.read()
    n = len(data)
    pos = 0
    if data[:3] == b"ID3" and n > 10:  # 跳过 ID3v2 头
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | \
               ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        pos = 10 + size
    total, frames = 0.0, 0
    while pos + 4 <= n:
        if data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
            pos += 1
            continue
        b1, b2 = data[pos + 1], data[pos + 2]
        ver = (b1 >> 3) & 0x03
        layer = (b1 >> 1) & 0x03
        br_i = (b2 >> 4) & 0x0F
        sr_i = (b2 >> 2) & 0x03
        pad = (b2 >> 1) & 0x01
        if ver == 1 or layer != 1 or br_i in (0, 15) or sr_i == 3:
            pos += 1
            continue
        br = _MP3_BR[ver][br_i] * 1000
        sr = _MP3_SR[ver][sr_i]
        spf = 1152 if ver == 3 else 576
        flen = (144 if ver == 3 else 72) * br // sr + pad
        if flen < 4:
            pos += 1
            continue
        total += spf / float(sr)
        frames += 1
        pos += flen
    if not frames:
        sys.exit(f"[nv] 读不到时长：{path}")
    return total


def duration_of(path):
    """优先不依赖 ffmpeg：wav 读头，mp3 走帧头；其他格式再交给 ffprobe。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        import wave
        try:
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            pass
    if ext == ".mp3":
        try:
            return mp3_duration(path)
        except SystemExit:
            pass
    return probe_duration(path)


def file_uri(path):
    """本地文件转 file:// URL；Windows 盘符也能转成合法的 file:///D:/...（别用字符串拼）。"""
    from pathlib import Path
    return Path(path).resolve().as_uri()


def ensure_dir(*parts):
    p = os.path.join(*parts)
    os.makedirs(p, exist_ok=True)
    return p


def die(msg, code=1):
    print(msg)
    sys.exit(code)
