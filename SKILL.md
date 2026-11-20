---
name: teaching-card-video
description: "把教学卡片/讲稿做成 16:9 中文讲解视频：无笔草稿纸风格、按 TTS 词级时间戳逐字展开、LaTeX 公式用 MathJax 渲染、例题前自动插 3 秒“保留原题”的思考暂停。适用于“把这几张教学卡做成视频”“teaching card video”“讲解视频”“草稿纸动画”“公式逐个写出来”“配音+烧字幕+成片”等请求。先出静帧接触表供确认，再渲染 MP4。"
version: "1.2.2"
author: "CodeBuddy AI"
created: "2026-11-20"
updated: "2026-11-20"
---

# Teaching Card Video

> **Goal**: 输入一组教学卡片（标题 / 屏幕文字 / TTS 旁白 / 画面动作），输出一支 16:9 的中文讲解视频。画面像草稿纸，没有笔；每个元素等旁白讲到它时才从左向右写出；公式全部走 LaTeX。

## 不可妥协的六条

1. **无笔草稿纸**：纸纹网格 + 衬线墨字，全片不出现笔、手、光标、箭头指针。
2. **讲到才出现**：元素由旁白词级时间戳触发，中文逐字、公式左→右软遮罩；未讲到的位置保持空白。
3. **同屏最多 2 个元素在生长**；相邻元素起始间隔 **≥ 12 帧**（24fps 即 0.5s，默认 0.55s）。
4. **公式必须是 LaTeX**（`\( \)` / `$$ $$`），由 MathJax 渲染，不降级成纯文本或图片。
5. **例题节奏**：题干卡把**原题完整放上屏**（题号、条件、分段函数、设问一个不少），屏幕不出现解法；讲完题干后插 **3 秒暂停卡**：题目原地留在屏幕上（压淡到四成），底部浮出一条提示“请暂停，自己先算一遍”，再进解析卡逐步拆解。
6. **字幕跟读**：底部单行、随旁白逐句出现；公式与英文单词不拆行，绝不出现三个字以下的孤条。

## 工作流（严格按顺序）

| 步骤 | 命令 | 产出 | 闸门 |
|---|---|---|---|
| 1. 建项目 | `python scripts/init_project.py <dir> --name "第1章_xxx"` | `stage.html`、`assets/`、`project.json`、`cards.json` | — |
| 2. 写卡 | 编辑 `cards.json`（见 `references/card-schema.md`） | 卡片清单 | 屏幕文字 ≤20 字；公式用 LaTeX |
| 3. 配音 | `python scripts/gen_audio.py <dir>` | `audio/*.mp3`、`timings.json` | 语速 4.6–6.2 cps，目标 5.5 |
| 4. 时间轴 | `python scripts/build_timeline.py <dir>` | `timeline.json` | 触发词全部命中 |
| 5. 体检 | `python scripts/check_timeline.py <dir>` | 终端报告 | 必须 PASS |
| 6. 静帧 | `python scripts/render_stills.py <dir>` | `out/contact_sheet.png` | **给用户看，等确认** |
| 7. 字幕 | `python scripts/make_srt.py <dir>` | `out/<name>.srt` | 单条 ≤22 视觉宽；无孤字条 |
| 8. 铺音轨 | `python scripts/build_audio.py <dir>` | `master.wav` | — |
| 9. 渲帧 | `python scripts/render_frames.py <dir> -j 4` | `frames/*.jpg` | 帧数 = duration×fps |
| 10. 出片 | `python scripts/encode.py <dir>` | `out/<name>.mp4` | 字幕已烧入；响度 −16 LUFS |
| 11. 清单 | `python scripts/make_shotlist.py <dir>` | `out/shotlist.csv` | 场景 / 起止 / 页码 |

> 第 6 步是硬闸门：**没有用户确认静帧，不要直接渲 MP4**。若用户明确说“直接出片”，才可跳过。
> 第 7 步可以提前跑：`make_srt.py` 只依赖 `timings.json` + `timeline.json`，配音完就能出字幕，方便先审文字。
> 第 3 步可以先看账单：`gen_audio.py <dir> --dry-run` 只报「要合成几张、多少字」，不调接口。
> `timings.json` 里每张卡带 `sig`（文案+音色+语速+模型的指纹）：指纹没变就复用 `audio/`，改了文案才重录，改音色也一样会重录。

新手先跑 `examples/demo/`：3 张卡、约 38 秒，覆盖概念卡、题干卡、暂停卡、解析卡。

## 从材料到卡片

1. **切模块**：按教材小节或题型分 2–4 个模块，每个模块 3–5 张教学卡。
2. **一卡一句主张**：先写 `title`（这卡要纠正/建立什么），再写 `screen`（≤20 字的那句话），最后写 3–5 条 `note` 支撑。
3. **写旁白**：150–300 字，口语化；先给结论，再解释，最后点一个易错点或反例。念一遍，读起来别扭的地方就是该拆句的地方。
4. **配画面**：`layout` 选版式，`diagram` 选一张与这句话直接相关的图；不要用图当装饰。
5. **排节拍**：把旁白里“讲到这个元素”的词抄进 `beats` 的第三项；顺序按“标题 → 主张 → 图示 → 要点”。
6. **例题两卡**：题干卡用 `layout: "stem"` + `pause_after: true`，屏幕只放已知和所求；解析卡用 `layout: "steps"`，一步一个 `step`，末尾用 `banner` 点坑。

| layout | 用在 |
|---|---|
| `concept` | 概念解释、一条主张 + 若干要点 |
| `list` | 并列关系、三类对比 |
| `steps` | 例题解析、推导步骤（自动编号） |
| `chips` | 多个并列名词（五种分布、三类变换） |
| `stem` | 题干（不出现解法） |

## 目录约定

```
<project>/
  project.json      # 课程名、章节、音色、语速、模块配色
  cards.json        # 卡片与节拍（唯一需要手写的文件）
  stage.html        # 从 skill 复制，勿改
  assets/tex-svg.js # MathJax 本地库
  audio/            # 逐卡 mp3
  timings.json      # 词级时间戳
  timeline.json     # 场景图
  _subs.srt         # 编码时用的 ASCII 副本（自动生成）
  frames/           # 逐帧 jpg
  out/              # contact_sheet.png / stills / <name>.srt / mp4
```

## 卡片数据长什么样

```json
{
  "id": "B5", "module": "B", "layout": "steps", "ref": "[1-2 p18]",
  "title": "例题解析｜\\(\\mathrm{Cov}\\) 归零，独立照样翻车",
  "tts": "第一步列分布……",
  "diagram": "joint",
  "diagramParams": {"rows": ["−0.5","0","0.5"], "cols": ["0","0.25"],
                    "values": [[0,"1/3"],["1/3",0],[0,"1/3"]], "caption": "0.5 这一行对不上"},
  "diagram2": "第四步判独立",
  "beats": [
    ["title", null, "第一步列分布"],
    ["step", "分布：\\(P(X=\\pm0.5)=P(X=0)=\\frac13\\)", "第一步列分布"],
    ["step", "\\(E(X)=0\\)，\\(E(Y)=\\frac16\\)", "第二步算 Y"],
    ["diagram", null, "第二步算 Y"],
    ["banner", "不相关 \\(\\neq\\) 独立", "踩坑点"]
  ],
  "pause_after": false
}
```

- `beats` 的第三项是**触发词**：必须能在该卡 `tts` 原文里找到；节拍时间 = 该词在配音里的起始时刻。
- `diagram2` 让图示的“数值层”等到某句话再出现（如联合分布表先出空网格，判独立时才填数）。
- `pause_after: true` 在该卡后自动插 3 秒暂停卡：**继承该卡画面**，盖一层 40% 纸色遮罩，底部弹提示条；标题、题目、图示都不消失。

## 版式与图示

`layout` 可选：`concept` / `list` / `steps` / `chips` / `stem`（题干）/ `steps`（解析）。有无 `diagram` 自动决定正文栏宽（716px / 1148px）。

内置图示：`map` `cdf` `density` `moments` `corr` `indep` `parabola` `joint` `branch` `deadzone` `char` `gauss2d` `block` `expo` `slice` `recip` `gap` `custom`。参数见 `references/diagrams.md`。

## 字幕

`make_srt.py` 把词级时间戳摊到每个字上（词内线性插值），再按语义断句，产出标准 SRT；`encode.py` 默认自动找 `out/<name>.srt` 并烧进画面。

| 规则 | 说明 |
|---|---|
| 断句优先级 | 句号/问号/分号 > 逗号/冒号 > 最近词边界 |
| 不可拆 | 连续英文、公式（`P(X=x)`、`F(x−)`、`σ²`）算一个原子，绝不从中间劈开 |
| 长度 | 目标 ≤22 格（中文 1 格、ASCII 0.55 格）；到 32 格才硬切 |
| 只切标点 | 没有标点就整条保留——宁长勿断。数学口语（“1 减 e 的负 x 除以 5 次方”）一旦从中间劈开就没法读 |
| 最短停留 | 0.9s；末条念完多留 0.35s |
| 位置 | 页脚上方空白带：720p 下字号 17、距底 30 |

调参：

```bash
python scripts/make_srt.py <dir> --max-len 22 --min-dur 1.0
python scripts/encode.py <dir> --sub-size 17 --sub-margin 30   # 改字号/位置
python scripts/encode.py <dir> --srt off                        # 出无字幕版
```

> **旁白即字幕**：`tts` 会被原样打成字幕。所以旁白里的数学表达要写成“看得懂”的形式——写 `1/√(2πbσ²y)`，别写“1 除以 2 派 b sigma 平方 y”；实在要口语化，就接受字幕也长这样。

## 质量检查清单

- [ ] 每张卡第一帧是空页（只有页眉页脚），标题从 0.1–0.5s 开始写。
- [ ] 没有任何元素在旁白提到之前出现。
- [ ] `check_timeline.py` 输出 PASS（同屏 ≤2、间隔 ≥12 帧）。
- [ ] 题干卡只有题干，屏幕不出现“先求导 / 套公式 / 注意绝对值”等解法提示。
- [ ] 暂停卡 3.0s：**保留前一页画面**（题目仍可读）＋纸色遮罩＋底部提示条，前后无旁白，与前帧无跳变。
- [ ] 成片解码无错；响度约 −16 LUFS；总时长与 `timeline.json` 一致。
- [ ] 字幕每句完整、不压页脚；没有公式被劈成两半；没有三个字以下的孤条。

## 交付

主文件 `out/<name>.mp4`（已烧字幕），同时给 `out/contact_sheet.png`（镜头节奏）、`out/stills/`（代表帧）、`out/<name>.srt`（可单独编辑/翻译）、`out/shotlist.csv`（场景、起止、时长、页码，由 `make_shotlist.py` 生成）。

## 常见坑（先看这里再 debug）

- **画面一入场就全满**：`seek()` 收的是**场景内相对时间**，不是绝对时间。渲染时用 `k/FPS - scene.start`。
- **中文变方块**：缺 `Noto Sans CJK SC` / `Noto Serif CJK SC`，装 `fonts-noto-cjk` 后重跑。
- **公式显示成反斜杠**：`assets/tex-svg.js` 没加载，或本地 `file://` 路径不对；看控制台 `MathJax is not defined`。
- **ffmpeg 报 Unknown encoder 'libx264'**：系统 ffmpeg 没编 x264，`pip install imageio-ffmpeg`，脚本会自动切换。
- **配音报 401 / 没找到 Key**：配音走千问 `qwen-audio-3.1-tts-flash`（WebSocket 流式），Key 从 `DASHSCOPE_API_KEY` / `~/.dashscope/config` / 项目 `.env` 找，也可临时 `--api-key`。缺 `websocket-client` 就 `pip install websocket-client`。
- **触发词没命中**：`build_timeline.py` 会列出具体卡片和词；把 `beats` 里的触发词换成 `tts` 中真实出现的片段。
- **字幕没烧上**：`encode.py` 只在 `out/<name>.srt` 存在时自动启用；文件名取自 `timeline.json` 的 `name`（次选 `project.json`）。用 `--srt 路径` 直接指定最稳。
- **字幕位置偏上/压页脚**：libass 对 SRT 的 `MarginV` 有缩放，按 720p 实测调 `--sub-margin`（默认 30 → 字幕底约 637px）；别按像素直觉算。
- **暂停卡还是纯黑**：项目根目录的 `stage.html` 是旧版（v1.2.1 以前 pause 用黑底 CSS）。从 skill 的 `assets/stage.html` 重新复制一份，再重跑 `build_timeline.py`——pause 场景必须带上前一张卡的 `beats` / `title` / `diagram`，否则只能渲染出空白页。

更细的排障见 `references/troubleshooting.md`；卡片写法见 `references/card-schema.md`；图示参数见 `references/diagrams.md`。

## 扩展点

- 字幕改样式只动 `encode.py` 顶部的 `INK` / `PAPER` 与 `--sub-size` / `--sub-margin`；想改成硬字幕条（半透明底），把 `BorderStyle=1` 换成 `BorderStyle=3` 并设 `BackColour`。
- 追加例题时复制一对卡片：`stem` + `pause_after: true` 的题干卡，和 `steps` 的解析卡；已有卡片顺序即镜头顺序。
- 换风格只改 `assets/stage.html` 顶部的 CSS 变量（纸色、墨色、点阵密度），不要改 `seek()` 的时间语义。
