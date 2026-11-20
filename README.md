# teaching-card-video

把一组**教学卡片**（标题 + 屏幕文字 + 旁白 + 画面动作）自动做成一支 16:9 的中文讲解视频：草稿纸质感、没有笔，每个元素等旁白讲到它时才从左往右写出，公式全部走 LaTeX，例题前面自动插 3 秒“保留原题”的思考暂停。

这是给 AI Agent 用的 **skill**（技能包）：放进 skills 目录后，Agent 读 `SKILL.md` 就能按固定工作流建项目、配音、排时间轴、渲帧、出片。

> 实测成品：《随机信号分析》第 1 章，19 张卡 + 4 张暂停卡，12 分 25 秒，1280×720 / 24 fps，295 条烧录字幕，响度 −16.1 LUFS。

## 它解决什么问题

做教学视频最烦的不是剪辑，是**对齐**：字什么时候出现、说到哪个词出现、公式和旁白对不对得上。这个 skill 把对齐这件事变成数据问题——

- 旁白用**千问 Qwen-Audio-TTS**（WebSocket 流式）合成，直接拿到**字级时间戳**；
- 每个画面元素的触发词必须在旁白原文里**逐字命中**，命中时刻就是它的入场时刻；
- 于是改一句旁白，整段动画自动重新对齐，不用手动拖时间线。

## 六条硬规矩

1. **无笔草稿纸** — 纸纹网格 + 衬线墨字，全片不出现笔、手、光标。
2. **讲到才出现** — 元素由词级时间戳触发，中文逐字、公式左→右软遮罩，没讲到的地方保持空白。
3. **同屏最多 2 个元素在生长**，相邻起始间隔 ≥ 12 帧（0.5 s）。
4. **公式必须是 LaTeX**（`\( \)` / `$$ $$`），MathJax 本地渲染，不降级成文本或图片。
5. **例题节奏** — 题干卡只放原题，讲完插 3 秒暂停卡（原题压淡保留，底部提示“请暂停，自己先算一遍”），再进解析卡。
6. **字幕跟读** — 单行、随旁白出现；公式与英文单词不拆行，不出现三个字以下的孤条。

## 安装

```bash
git clone https://github.com/yikai666/teaching-card-video.git ~/.codebuddy/skills/teaching-card-video
```

其他 Agent 宿主把仓库放到它自己的 skills 目录即可；脚本不依赖特定 IDE，解压到任意目录也能直接跑。

依赖（一次性）：

```bash
pip install playwright websocket-client numpy pillow imageio-ffmpeg
python -m playwright install chromium
# 中文字体：Linux 装 fonts-noto-cjk；Windows 用系统自带的微软雅黑/宋体即可

# 配音走千问，需要一个百炼 API Key（三选一，别写进仓库）
export DASHSCOPE_API_KEY=sk-xxx
# echo 'DASHSCOPE_API_KEY=sk-xxx' >> ~/.dashscope/config
```

`ffmpeg` 需要带 libx264；系统没有时脚本会自动切到 `imageio-ffmpeg` 自带的二进制。

## 快速开始

先跑自带的 3 卡示例（约 38 秒，覆盖概念卡 / 题干卡 / 暂停卡 / 解析卡）：

```bash
cd examples/demo
python ../../scripts/init_project.py . --name 示例_三卡
python ../../scripts/gen_audio.py .
python ../../scripts/build_timeline.py .
python ../../scripts/check_timeline.py .      # 必须 PASS
python ../../scripts/render_stills.py .       # 先看 out/contact_sheet.png 再继续
python ../../scripts/build_audio.py .
python ../../scripts/render_frames.py . -j 4
python ../../scripts/encode.py .
```

成片在 `out/示例_三卡.mp4`。示例目录里已经带了一份跑好的 `audio/`、`timings.json`、`timeline.json`，想直接看画面可以从 `render_stills.py` 开始。

## 完整工作流

| 步骤 | 命令 | 产出 | 闸门 |
|---|---|---|---|
| 1 建项目 | `init_project.py <dir> --name "..."` | `stage.html`、`project.json`、`cards.json` | — |
| 2 写卡 | 编辑 `cards.json` | 卡片清单 | 屏幕文字 ≤ 20 字 |
| 3 配音 | `gen_audio.py <dir>` | `audio/*.mp3`、`timings.json` | 语速 4.6–6.2 cps |
| 4 时间轴 | `build_timeline.py <dir>` | `timeline.json` | 触发词全命中 |
| 5 体检 | `check_timeline.py <dir>` | 终端报告 | 必须 PASS |
| 6 静帧 | `render_stills.py <dir>` | `out/contact_sheet.png` | **给用户看，等确认** |
| 7 字幕 | `make_srt.py <dir>` | `out/<name>.srt` | 单条 ≤ 22 视觉宽 |
| 8 音轨 | `build_audio.py <dir>` | `master.wav` | — |
| 9 渲帧 | `render_frames.py <dir> -j 4` | `frames/*.jpg` | 帧数 = 时长 × fps |
| 10 出片 | `encode.py <dir>` | `out/<name>.mp4` | 字幕已烧入 |
| 11 清单 | `make_shotlist.py <dir>` | `out/shotlist.csv` | — |

第 6 步是硬闸门：没确认静帧不要直接渲 MP4（用户明确说“直接出片”才跳过）。

## 目录

```
.
├── SKILL.md                  # 方法论：硬规矩、工作流、版式、字幕规则、排障
├── scripts/                  # 11 个脚本，纯命令行，互不依赖 IDE
│   ├── init_project.py       # 建项目骨架 / 升级 stage.html
│   ├── gen_audio.py          # 千问配音 + 字级时间戳
│   ├── build_timeline.py     # 卡片 → 场景时间轴（触发词 → 绝对秒）
│   ├── check_timeline.py     # 体检：同屏 ≤2、间隔 ≥12 帧、触发词命中
│   ├── render_stills.py      # 静帧接触表（确认画面用）
│   ├── make_srt.py           # 词级时间戳 → 语义断句 SRT
│   ├── build_audio.py        # 逐卡 mp3 → master.wav
│   ├── render_frames.py      # Playwright 逐帧截图，多进程
│   ├── encode.py             # ffmpeg 编码 + 烧字幕 + 响度归一
│   ├── make_shotlist.py      # 场景/起止/页码清单
│   └── nv_common.py          # 共享工具
├── assets/
│   ├── stage.html            # 渲染舞台：版式、图示注册表、seek() 时间语义
│   └── tex-svg.js            # MathJax 离线包（不联网也能渲公式）
├── references/
│   ├── card-schema.md        # project.json / cards.json 字段字典
│   ├── diagrams.md           # 18 个内置图示及参数
│   └── troubleshooting.md    # 按现象查的排障表
└── examples/demo/            # 3 卡可跑示例（含音频与时间戳）
```

## 卡片的形状

`cards.json` 是唯一需要手写的文件：

```json
{
  "id": "B5", "module": "B", "layout": "steps", "ref": "[1-2 p18]",
  "title": "例题解析｜\\(\\mathrm{Cov}\\) 归零，独立照样翻车",
  "tts": "第一步列分布……",
  "diagram": "joint",
  "beats": [
    ["title", null, "第一步列分布"],
    ["step", "分布：\\(P(X=\\pm0.5)=P(X=0)=\\frac13\\)", "第一步列分布"],
    ["banner", "不相关 \\(\\neq\\) 独立", "踩坑点"]
  ],
  "pause_after": false
}
```

`beats` 的第三项是**触发词**，必须能在该卡 `tts` 里原样找到——这是全片“讲到才出现”的唯一机制。`layout` 可选 `concept` / `list` / `steps` / `chips` / `stem`；图示有 `map` `cdf` `density` `moments` `corr` `indep` `parabola` `joint` `branch` `deadzone` `char` `gauss2d` `block` `expo` `slice` `recip` `gap` `custom`。

## 常见坑（摘）

| 现象 | 原因 |
|---|---|
| 画面一入场就全满 | `seek()` 收的是场景内相对时间，渲染时要用 `k/FPS - scene.start` |
| 中文变方块 | 缺 Noto CJK 字体 |
| 公式显示成反斜杠 | `assets/tex-svg.js` 没加载 |
| 暂停卡纯黑 | 项目里的 `stage.html` 是旧版，`init_project.py --update-stage` 更新 |
| 字幕把公式劈两半 | `--max-len` 太小；保持 22 |
| 字幕压页脚 | libass 对 `MarginV` 有缩放，720p 用 `--sub-margin 30` |
| 改完文字音画不同步 | 改了 `tts` 没重跑 `gen_audio.py` |

完整排障见 `references/troubleshooting.md`。

## 许可

MIT，见 `LICENSE`。
