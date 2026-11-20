# 三卡示例

约 38 秒，覆盖一张概念卡、一道题干卡（后接 3 秒暂停卡）、一张解析卡。

```bash
cd examples/demo
python ../../scripts/init_project.py . --name 示例_三卡   # 只补 stage.html / assets，不覆盖已有 json
python ../../scripts/gen_audio.py .
python ../../scripts/build_timeline.py .
python ../../scripts/check_timeline.py .
python ../../scripts/render_stills.py .        # 先看 out/contact_sheet.png
python ../../scripts/make_srt.py .             # 出 out/示例_三卡.srt
python ../../scripts/build_audio.py .
python ../../scripts/render_frames.py . -j 4
python ../../scripts/encode.py .
```

成片在 `out/示例_三卡.mp4`（默认烧入字幕）。

目录里已带一份跑好的 `audio/`、`timings.json`、`timeline.json`、`out/示例_三卡.srt`：
想直接看画面，可以从 `render_stills.py` 开始；改过 `cards.json` 才需要重跑配音。
