# -*- coding: utf-8 -*-
"""Shared helpers for the notebook-video pipeline."""
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


def ensure_dir(*parts):
    p = os.path.join(*parts)
    os.makedirs(p, exist_ok=True)
    return p


def die(msg, code=1):
    print(msg)
    sys.exit(code)
