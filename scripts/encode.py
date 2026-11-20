# -*- coding: utf-8 -*-
"""帧序列 + master.wav -> MP4（H.264/AAC，响度归一到 -16 LUFS）

用法: python encode.py [项目目录] [--out 名称.mp4] [--crf 18] [--preset medium]
                      [--srt auto|off|路径] [--sub-size 17] [--sub-margin 30]

字幕默认自动找 out/<name>.srt（由 make_srt.py 生成），烧在页脚上方的空白带。
"""
import os
import shutil
import subprocess
import sys

from nv_common import load_json, project_root, ffmpeg_exe, probe_duration

FONT = "Noto Serif CJK SC"
INK = "&H0020262B"      # #2B2620 墨色（ASS 是 &HAABBGGRR）
PAPER = "&H00E0EDF3"    # #F3EDE0 纸色


def pick_font():
    # 字幕字体必须确定有汉字字形，否则 libass 会画成方块
    windir = os.environ.get("WINDIR") or "C:/Windows"
    for name, fn in (("Microsoft YaHei", "msyh.ttc"), ("SimHei", "simhei.ttf"),
                     ("SimSun", "simsun.ttc")):
        if os.path.exists(os.path.join(windir, "Fonts", fn)):
            return name
    try:
        out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return "sans-serif"
    for f in (FONT, "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei"):
        if f.lower() in out.lower():
            return f
    return "sans-serif"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out")
    ap.add_argument("--crf", default="18")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--srt", default="auto", help="auto | off | 指定 srt 路径")
    ap.add_argument("--sub-size", type=float, default=17, help="720p 下的字号")
    ap.add_argument("--sub-margin", type=float, default=30, help="720p 下距底边距")
    a = ap.parse_args()
    root = project_root(a.root)
    tl = load_json(os.path.join(root, "timeline.json"))
    meta = load_json(os.path.join(root, "project.json"))
    name = tl.get("name") or meta.get("name") or "video"
    out = os.path.abspath(a.out) if a.out else os.path.join(root, "out", f"{name}.mp4")
    crf, preset = a.crf, a.preset
    os.makedirs(os.path.dirname(out), exist_ok=True)

    frames = os.path.join(root, "frames")
    if not os.path.exists(os.path.join(frames, "000000.jpg")):
        sys.exit("[nv] frames/ 为空：先跑 render_frames.py")
    audio = os.path.join(root, "master.wav")
    if not os.path.exists(audio):
        sys.exit("[nv] 缺少 master.wav：先跑 build_audio.py")

    fps = int(tl.get("fps", 24))
    dur = tl["duration"]
    w = int(tl.get("width", 1280))
    h = int(tl.get("height", 720))
    exe = ffmpeg_exe()

    srt = a.srt
    if srt == "auto":
        cand = os.path.join(root, "out", f"{name}.srt")
        srt = cand if os.path.exists(cand) else None
    elif srt == "off":
        srt = None

    vf = []
    if srt:
        if not os.path.exists(srt):
            sys.exit(f"[nv] 找不到字幕：{srt}")
        # 滤镜里的路径不做转义：复制成 ASCII 文件名，cwd=root 用相对路径
        local = os.path.join(root, "_subs.srt")
        if os.path.abspath(srt) != os.path.abspath(local):
            shutil.copyfile(srt, local)
        size = max(10, round(a.sub_size * h / 720))
        margin = max(0, round(a.sub_margin * h / 720))
        style = (f"FontName={pick_font()},FontSize={size},PrimaryColour={INK},"
                 f"OutlineColour={PAPER},BorderStyle=1,Outline=1.2,Shadow=0,"
                 f"MarginV={margin},Alignment=2")
        opts = f"filename=_subs.srt:original_size={w}x{h}"
        vf.append(f"subtitles={opts}:force_style='{style}'")
        print(f"[nv] 字幕 {os.path.basename(srt)}  {size}px  margin={margin}")

    cmd = [exe, "-y", "-v", "error", "-stats",
           "-framerate", str(fps), "-i", os.path.join(frames, "%06d.jpg"),
           "-i", audio, "-t", f"{dur:.3f}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", out]
    print("[nv]", " ".join(cmd[:8]), "...")
    subprocess.run(cmd, check=True, cwd=root)
    print(f"[nv] {out}  {os.path.getsize(out)/1024/1024:.1f} MB  {probe_duration(out):.1f}s")


if __name__ == "__main__":
    main()
