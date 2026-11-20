# 排障

## 环境

```bash
# 必需
python3 -c "import playwright, PIL, numpy; print('ok')"
python3 -m playwright install chromium     # 只装一次
fc-list :lang=zh | head                    # 需要 Noto Sans/Serif CJK SC
pip install websocket-client imageio-ffmpeg
ffmpeg -encoders 2>/dev/null | grep libx264

# 配音用千问，需要一个 API Key（不要写进仓库）
export DASHSCOPE_API_KEY=sk-xxx
# 或：echo 'DASHSCOPE_API_KEY=sk-xxx' >> ~/.dashscope/config
```

`ffmpeg` 没编 `libx264` 时，`encode.py` 会通过 `imageio-ffmpeg` 找一个带 x264 的静态版本；找不到才报错。

## 症状 → 原因 → 处理

### 1. 每张卡一入场就整页铺满

`seek(t)` 的参数是**场景内相对时间**。渲染脚本里必须是：

```python
t = k / FPS - scene["start"]      # 不是 k / FPS
```

同理，静帧脚本用 `scene["duration"] * frac`。检查 `render_frames.py` 是否被改过。

### 2. 公式显示成 `\(f_Y(y)\)` 原文

- `assets/tex-svg.js` 不存在或路径错：项目根目录下必须有 `assets/tex-svg.js`，`stage.html` 用相对路径加载。
- 打开控制台看 `MathJax is not defined`；用 `file://` 打开时确认目录结构没变。
- 文案里用了 `$...$` 单美元：本流水线只认 `\(...\)` 与 `$$...$$`。

### 3. 中文变方块 / 字号忽大忽小

装字体后重启 Chromium：

```bash
apt-get install -y fonts-noto-cjk
fc-cache -f
```

`stage.html` 的字体栈是 `Noto Sans CJK SC` / `Noto Serif CJK SC`；服务器上没有 serif 时会退到 sans，标题会显得平，但不影响正确性。

### 4. 触发词没命中

`build_timeline.py` 会打印 `missing` 并退出。把 `beats` 里的触发词换成 `tts` 中真实连续出现的片段（建议 2–6 字），或先用：

```bash
python - <<'PY'
import json
T=json.load(open('timings.json'))
print(' '.join(w['w'] for w in T[0]['words'][:40]))
PY
```

看千问切出来的字级时间戳。

### 5. 语速不对

`timings.json` 里有每卡 `cps`。目标 5.5：

- 偏快（>6.2）：`project.json` 的 `rate` 调低，如 `1.04`。
- 偏慢（<4.6）：调高，如 `1.16`。
- `rate` 是倍数（0.5–2.0），不是百分数；写 `"+12%"` 也能识别。
- 改完 `rate` 直接重跑 `gen_audio.py` 即可：`sig` 指纹里含 rate，会自动重录；只有想强制重录全部才加 `--force`。

### 6. 千问配音报错

- `没找到千问 API Key`：Key 有三个落点（环境变量 / `~/.dashscope/config` / 项目 `.env`），或临时加 `--api-key`。Key 不要写进 `project.json`。
- `InvalidApiKey` / 401：Key 与地域要配套（北京 key 配 `dashscope.aliyuncs.com`）。
- `voice_not_found`：音色名要跟模型匹配——`qwen-audio-3.1-tts-flash` 用 `longanhuan_v3.1` 这类 `_v3.1` 后缀的音色；`qwen3-tts-flash` 才是 `Cherry`。
- WebSocket 连不上（`Handshake status 403/404`）：换业务空间专属域名，`--ws-url wss://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference`，或设 `DASHSCOPE_WS_URL`。
- 拿不到字级时间戳时脚本会打印 `没拿到字级时间戳，已按字数插值`：画面仍能渲，但“讲到才出现”会退化成按时长均分，尽量把 Key/模型修好再跑。

### 7. 渲染很慢 / 卡死

- 单进程约 30 fps 抓帧；4 进程约 110 秒出 12k 帧（720p）。
- 每个 worker 各开一个 Chromium；内存 <2GB 时把 `-j` 降到 2。
- 中断后用 `--resume` 续渲（会跳过已存在且 >2KB 的帧）。

### 8. 成片有 0.5 秒空白开头

首卡 `start = lead`（默认 0.4s），帧 0 起就是空页。想更快进标题，把 `project.json` 的 `lead` 调到 0.1，或把首卡标题节拍的触发词改成 `__start__`（固定 0.15s）。

### 9. 一卡讲完停很久

`check_timeline.py` 会报“结尾静默 >8s”。处理方式：

- 把最后一个节拍的触发词换到更靠后的句子；
- 或补一个 `note` 节拍，承接旁白最后一句；
- 或删掉旁白里重复的收尾。

### 10. 成片音画不同步

时间轴是用**同一次** `timings.json` 建的。若改过配音却没重建时间轴，就会出现漂移：

```bash
python scripts/gen_audio.py <dir> --force
python scripts/build_timeline.py <dir>
```

顺序不能反。

## 快速自检脚本

```bash
python scripts/check_timeline.py <dir>
ffprobe -v error -show_entries format=duration -of csv=p=0 out/<name>.mp4
ffmpeg -v error -i out/<name>.mp4 -f null - && echo decode-ok
```
