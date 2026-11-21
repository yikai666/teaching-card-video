---
name: notebook-video
description: "把教学卡片/讲稿做成 16:9 中文讲解视频：无笔草稿纸风格、按 TTS 词级时间戳逐字展开、LaTeX 公式用 MathJax 渲染、例题前自动插 3 秒“保留原题”的思考暂停；右上角常驻公式/符号速查小卡。适用于“把这几张教学卡做成视频”“notebook video”“讲解视频”“草稿纸动画”“公式逐个写出来”“配音+烧字幕+成片”等请求。先出静帧接触表供确认，再渲染 MP4。"
version: "1.9.0"
author: "CodeBuddy AI"
created: "2026-11-20"
updated: "2026-11-21"
---

# Notebook Video

> **Goal**: 输入一组教学卡片（标题 / 屏幕文字 / TTS 旁白 / 画面动作），输出一支 16:9 的中文讲解视频。画面像草稿纸，没有笔；每个元素等旁白讲到它时才从左向右写出；公式全部走 LaTeX。

## 不可妥协的十二条

1. **无笔草稿纸**：纸纹网格 + 衬线墨字，全片不出现笔、手、光标、箭头指针。
2. **讲到才出现**：元素由旁白词级时间戳触发，中文逐字、公式左→右软遮罩；未讲到的位置保持空白。
3. **同屏最多 2 个元素在生长**；相邻元素起始间隔 **≥ 12 帧**（24fps 即 0.5s，默认 0.55s）。
4. **公式必须是 LaTeX**（`\( \)` / `$$ $$`），由 MathJax 渲染，不降级成纯文本或图片。
5. **例题即正片**：例题不靠 3 秒暂停卡交差。每道题单独成段（1–3 张卡），用 `layout: "example"`：**左栏整块题面常驻**（题号、条件、分段函数、设问一个不少），题面下方「本页用到」列 2–3 条本页依赖的知识点；**右栏**按旁白逐步展开推导。题面从这道题的第一张卡到最后一张卡都不消失，也不被遮罩压暗。
6. **知识点块**：每张教学卡至少有一个 `def` 块（定义，带「定义」标签）作为知识锚点，旁白按「定义 → 性质/用法 → 易错点」组织；口语可以用，但不能只有口语。
7. **符号首次出现必须解释**：`E(X)` `D(X)` `Cov` `r_{XY}` `N(\mu,\sigma^2)` `\mu` `\sigma` `\int` `\sum` `j` 这类记号，要么在开场的符号卡里集中认一遍，要么在首次出现的卡上加 `sym` 块写清读法与含义。
8. **字幕跟读**：底部单行、随旁白逐句出现；公式与英文单词不拆行，绝不出现三个字以下的孤条。
9. **公式/符号上屏即配速查卡**：每页正文里出现的公式与记号，右上角自动挂 1–2 条一句话解释（由 `glossary.json` 驱动）。学生忘了随时能扫一眼，不靠旁白记忆；同一符号只在其首次登场时重点解释，后续页兜底一条。
10. **例题要讲完**：每道题按「建模/求谱 → 代入 → 化简 → 结论」铺拍，课件上的两种解法都要讲（如冲激响应法 + 频谱法），并点明各自适用范围；有电路或示意图的，用 `fig` 节拍内联 SVG 画出来，不要只写一句“电路略”。
11. **高数工具单独放右下角**：凡用到积分、求导、卷积、傅里叶变换、查表对、欧拉公式、级数求和、共轭、帕塞瓦尔、施瓦兹、中心极限定理，写一个 `aside` 节拍，把**本次真正用到的那一条**公式放进「高数备忘」框，配一句人话说明；不要塞进正文，也不要堆整套公式表。
12. **节拍顺序＝旁白顺序**：`beats` 里除 `title` 打头、`banner` 收尾外，中间各拍必须按触发词在 `tts` 中出现的先后排列；定义/知识点块跟着第一句上屏，标题写完再出第一块内容（否则会「先出结论、后念定义」或开场空屏）。生成脚本里用 `tidy()` 统一排序，别靠手写顺序。

## 工作流（严格按顺序）

| 步骤 | 命令 | 产出 | 闸门 |
|---|---|---|---|
| 1. 建项目 | `python scripts/init_project.py <dir> --name "第1章_xxx"` | `stage.html`、`assets/`、`project.json`、`cards.json` | — |
| 2. 写卡 | 编辑 `cards.json` + `glossary.json`（见 `references/card-schema.md`） | 卡片清单、符号表 | 屏幕文字 ≤20 字；公式用 LaTeX；每个新记号进符号表 |
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
> 第 3 步的两个引擎：`gen_audio.py` 走千问（`DASHSCOPE_API_KEY`，带合成指纹，改文案自动重录）；没有 Key 或只想试片时用 `gen_audio_edge.py`（edge-tts，免费），两者产出的 `timings.json` 结构一致，后续步骤不用改。

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
- `pause_after: true` 在该卡后自动插 3 秒暂停卡：**继承该卡画面**，盖一层 40% 纸色遮罩，底部弹提示条；标题、题目、图示都不消失。写**整数 n** 则连续插 n 张（一个模块末尾有多道例题时用，如 `pause_after: 3` 对应习题 3.15 / 3.16 / 3.18）。
- `def` 写 `"定义 1.2｜正文"`：竖线前是标签、后面是正文；`sym` 写 `"符号｜正文"`，左侧自动出现「符号」小签。`kp` 与 `def` 同一套渲染，默认标签是「知识点」，写 `"定理 2｜正文"` 即可换标签。
- `aside` 写 `"公式｜一句人话"`：公式进右下角「高数备忘」框，人话在下面一行；一张卡最多一条，触发词同样要在 `tts` 里出现。
- 解析卡（`layout: steps`）加 `"stem_bar": "一行紧凑题面"`，标题下会固定一条「原题」栏，步骤区自动下移。

## 版式与图示

`layout` 可选：`concept` / `list` / `steps` / `chips` / `stem`（题干）/ `example`（例题：左题面常驻 + 右推导）。有无 `diagram` 自动决定正文栏宽（716px / 1148px）。

`example` 版式要点：左栏 `#exPanel` 宽 372，`stem` 按 17px 起排，超过 6 行自动降到 11.2px 封底，**题面控制在 8 行内**（含分段条件与三小问）；`used` 紧贴题面下方，2–3 条，每条 ≤16 字，只写本页真要用的公式或结论（如 `c_t=\cos\omega_0 t`、`f_X=1/|c_t|`），不写“注意定义域”这类空话。右栏宽 716，`beats` 里第一拍用 `def` 写“这一步做什么”，后续每步一个 `step`，收尾 `banner` 给一句可背的结论。

内置图示：`map` `cdf` `density` `moments` `corr` `indep` `parabola` `joint` `branch` `deadzone` `char` `gauss2d` `block` `expo` `slice` `recip` `gap` `custom`。

v1.5.0 起带一套**线性变换专题**图示（第 3 章实测可用）：
`convchain` 卷积记忆链｜`ramp` 暂态爬升 vs 双侧平稳｜`evenodd` 偶函数切线｜`ident` 互相关测冲激响应｜`bandlimit` 限带谱｜`band2x` 低通/带通上下对比｜`zplane` s 平面→z 平面映射｜`artrail` AR 拖尾柱｜`mathree` MA 三点柱｜`comb` 梳状对消｜`armapk` ARMA 峰谷｜`match` 匹配滤波器镜像｜`triout` 矩形卷积出三角｜`whiten` 白化＋匹配两级｜`gaussout` 正态输出。参数见 `references/diagrams.md`。

v1.7.0 起带一套**窄带随机过程专题**图示（第 5 章实测可用，22 个）：
`hilbphase` 90° 相移｜`hilb2` 两次变换=−x｜`hstat` 变换后统计不变｜`odd0` 奇函数过原点｜`aspec` 双边→单边谱｜`aspec4` 解析信号功率 4 倍｜`narrow` 窄带钟形谱｜`rot` 矢量投影 Ac/As｜`rdecomp` 包络＋振荡｜`core2` 分量自相关/互相关｜`lowfreq` 频谱搬移｜`polar` 极坐标面积元｜`rayleigh` 瑞利密度｜`unif` 相位均匀｜`sameproc` 同时独立≠全程独立｜`rician` 莱斯分布族｜`expdist` 指数分布｜`syncdet` 同步检波框图｜`gain3db` +3 dB 柱状｜`envdet` 包络检波波形｜`threshold` 门限效应曲线｜`gains` 四种检波器增益。清单见 `references/diagrams.md`。

v1.8.0 起带一套**非线性变换专题**图示（第 4 章实测可用，22 个）：
`memoryless` 无记忆系统｜`vslinear` 线性 vs 非线性谱｜`jacobian` 单调映射与雅可比｜`multival` 多值映射逐支相加｜`egx` 期望不能换序｜`threeg` 三种检波器曲线｜`sqpdf` 平方律输出密度｜`fullwave` 全波半正态｜`halfdelta` 半波原点冲激｜`fourth` 四阶矩三对分解｜`sqspec` 直流＋带宽加倍｜`transfun` 特征函数法框架｜`pricepre` Price 三前提｜`price4` Price 四步｜`foursum` 四个汇总式｜`boundary` 边界定常数｜`typo` 半波系数笔误｜`taylor` 泰勒逼近｜`series2` 双重求和｜`limit3` 三条红线｜`parab2` 抛物线非线性｜`cyclostat` 周期平稳。清单见 `references/diagrams.md`。

v1.9.0 起带一套**随机过程基础专题**图示（第 2 章实测可用，29 个）：
`teplane` t–e 二维表与两种切法｜`fourclass` 四类过程 2×2｜`dist12` 一维/二维分布｜`fourmom` 四数字特征｜`pyth` 总功率勾股｜`phasesig` 随机相位信号｜`nested` 严平稳⊂广义平稳｜`ampvphase` 随机幅度 vs 随机相位｜`judge3` 平稳判断三步｜`cyclo` 循环平稳与随机化｜`ergodic` 集平均/时间平均｜`sve` 平稳非遍历反例｜`acf5` 自相关五性质｜`strip` 剔除周期项｜`corrtime` 相关时间面积｜`wk` 维纳–辛钦双面板｜`pairs4` 四组变换对｜`specfac` s 平面谱分解｜`xcorr` 互相关镜像｜`xspec` 互谱虚实部｜`ranging` 相关测距｜`white` 白噪声｜`color` 色噪声｜`normal` 正态过程两等价｜`vcos` 余弦样本族｜`vpdf4` 四时刻密度族｜`coin1`/`coin2`/`coin3` 掷币过程一维/二维/阶梯。清单见 `references/diagrams.md`。

> **新增图示先查重名**：全章图示共用一个 `DIAG` 对象，后定义的会静默覆盖先定义的。加图前先 `grep -oE "^[a-zA-Z0-9_]+:\(p=\{\}\)" assets/stage.html | sort | uniq -d`。第 4 章的 `parabola` 就与第 1 章撞过，改名 `parab2`；第 5 章的 `indep`/`expo` 同理改成 `sameproc`/`expdist`。

### 图示什么时候出现

`diagram` 由 `build_timeline.py` 自动排到节拍数组末尾，但**不参与文字节拍的顺延链**：v1.7.0 起它**紧跟第二拍（知识点/定义）长完之后**出现，先给画面再讲细节。这样图示与后面的正文并排生长，画面上仍然只有两样在动；后面密集的要点不会被图挤晚，也不会出现「图在最后一秒才冒出来」。


> **有图时正文只有 716px**：带 `diagram` 的卡，一行 `\(...\)` 超过约 55 个字符就会伸进图示区（第 4 章的四重期望就撞过）。拆成两拍：第一拍写等号左边和前两项，第二拍以 `+` 开头写余项，视觉上仍是连续两行。

`diagram2` 控制图示里数值层（`.jval`）的二次出现，用于"先出空网格、讲到才填数"。图示里所有坐标都在 `viewBox="0 0 360 320"` 内，容器宽 410；有 `aside` 时高度压到 318，画图时把关键元素放在 y ≤ 290。

## 公式 / 符号速查小卡

每页右上角会自动浮出一张浅色小卡（标题「本页符号」），列出本页出现的 1–2 个公式/记号及一句话解释。
内容来自项目根目录的 `glossary.json`：

```json
{"items": [
  {"k": "E(X)", "sym": "E(X)", "note": "数学期望：加权平均，重心"},
  {"k": "\\mathrm{Cov}(X,Y)", "sym": "\\mathrm{Cov}(X,Y)", "note": "协方差：同向偏离的程度"},
  {"k": "f_G(g)", "sym": "f_G(g)", "note": "电导的密度：由 R 的密度变换而来"}
]}
```

| 字段 | 作用 |
|---|---|
| `k` | 匹配串：在该卡 `beats` 的 LaTeX 源码里能直接找到的片段，**越具体越好**。写 `\\mu=E(X)` 就不会被别处的 `\\mu` 抢走 |
| `sym` | 屏幕上显示的 LaTeX（不带 `\\( \\)`），一般就是符号本身 |
| `note` | 一句话解释，**≤14 字**；超了会换行把卡片顶高，可能压到插图 |

挑选规则（`build_timeline.py` 自动执行）：

1. 把该卡标题、`stem_bar`、全部 beat 文本拼起来，按 `k` 首次出现的位置排序。
2. 优先给**本模块还没解释过**的符号（每页最多 2 条）；全是旧符号时只兜底 1 条。
3. 一条都没命中就不显示小卡（如纯文字卡、开场的符号总览卡）。

写作约束：

- 同一页不要放两条语义重复的（`\\sigma^2` 与 `\\sigma`、`N(\\mu,\\sigma^2)` 与 `\\mu`）——挑更具体的那个当 `k`。
- 符号总览卡（开场认符号那张）设 `"gloss": false`，否则小卡会把刚讲完的内容再抄一遍。
- 卡片放在 `right:64 / top:78`，宽 238–364 自适应；标题实际宽度超过 772px 时自动隐藏，避免压字——标题太长就缩短。

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

> **读音→符号**：TTS 念的是英文/中文拼读，字幕由 `display_fix()` 自动换成符号，不影响时间轴：`omega/alpha/sigma/tau/rho/mu/pi` → `ω/α/σ/τ/ρ/μ/π`，`omega 零/一/二` 与 `ω0/ω1/ω2` → `ω₀/ω₁/ω₂`，`N0/t0` → `N₀/t₀`，`RX 零 / RX τ / RY` → `R_X(0) / R_X(τ) / R_Y`，`σX 平方 / σX` → `σ_X² / σ_X`。旁白按嘴顺写即可，不必为了字幕强行塞 LaTeX。

## 质量检查清单

- [ ] 每张卡第一帧是空页（只有页眉页脚），标题从 0.1–0.5s 开始写。
- [ ] 没有任何元素在旁白提到之前出现。
- [ ] `check_timeline.py` 输出 PASS（同屏 ≤2、间隔 ≥12 帧）。
- [ ] 题干卡只有题干，屏幕不出现“先求导 / 套公式 / 注意绝对值”等解法提示。
- [ ] 暂停卡 3.0s：**保留前一页画面**（题目仍可读）＋纸色遮罩＋底部提示条，前后无旁白，与前帧无跳变。
- [ ] 成片解码无错；响度约 −16 LUFS；总时长与 `timeline.json` 一致。
- [ ] 字幕每句完整、不压页脚；没有公式被劈成两半；没有三个字以下的孤条。
- [ ] 每页右上角速查小卡内容正确、不压标题与插图；符号总览页没有重复小卡。

## 交付

主文件 `out/<name>.mp4`（已烧字幕），同时给 `out/contact_sheet.png`（镜头节奏）、`out/stills/`（代表帧）、`out/<name>.srt`（可单独编辑/翻译）、`out/shotlist.csv`（场景、起止、时长、页码，由 `make_shotlist.py` 生成）。

## 常见坑（先看这里再 debug）

- **画面一入场就全满**：`seek()` 收的是**场景内相对时间**，不是绝对时间。渲染时用 `k/FPS - scene.start`。
- **中文变方块**：缺 `Noto Sans CJK SC` / `Noto Serif CJK SC`，装 `fonts-noto-cjk` 后重跑。
- **公式显示成反斜杠**：`assets/tex-svg.js` 没加载，或本地 `file://` 路径不对；看控制台 `MathJax is not defined`。
- **ffmpeg 报 Unknown encoder 'libx264'**：系统 ffmpeg 没编 x264，`pip install imageio-ffmpeg`，脚本会自动切换。
- **edge-tts 导入失败**：脚本会自动找 `/usr/bin/python3` 里装过的解释器；否则 `pip install edge-tts`。
- **触发词没命中**：`build_timeline.py` 会列出具体卡片和词；把 `beats` 里的触发词换成 `tts` 中真实出现的片段。
- **字幕没烧上**：`encode.py` 只在 `out/<name>.srt` 存在时自动启用；文件名取自 `timeline.json` 的 `name`（次选 `project.json`）。用 `--srt 路径` 直接指定最稳。
- **字幕位置偏上/压页脚**：libass 对 SRT 的 `MarginV` 有缩放，按 720p 实测调 `--sub-margin`（默认 30 → 字幕底约 637px）；别按像素直觉算。
- **暂停卡还是纯黑**：项目根目录的 `stage.html` 是旧版（v1.2.1 以前 pause 用黑底 CSS）。从 skill 的 `assets/stage.html` 重新复制一份，再重跑 `build_timeline.py`——pause 场景必须带上前一张卡的 `beats` / `title` / `diagram`，否则只能渲染出空白页。

更细的排障见 `references/troubleshooting.md`；卡片写法见 `references/card-schema.md`；图示参数见 `references/diagrams.md`。

## 扩展点

- 字幕改样式只动 `encode.py` 顶部的 `INK` / `PAPER` 与 `--sub-size` / `--sub-margin`；想改成硬字幕条（半透明底），把 `BorderStyle=1` 换成 `BorderStyle=3` 并设 `BackColour`。
- 追加例题时复制一对卡片：`stem` + `pause_after: true` 的题干卡，和 `steps` 的解析卡；已有卡片顺序即镜头顺序。
- 换风格只改 `assets/stage.html` 顶部的 CSS 变量（纸色、墨色、点阵密度），不要改 `seek()` 的时间语义。
