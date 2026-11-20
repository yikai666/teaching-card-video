# 图示库

所有图示画在 360×320 的 viewBox 内，位于右侧 410×392 区域；颜色自动跟随模块 `accent`，浅色底用 `tint`。每个渲染器接收 `diagramParams`，下面只列可改的键，未写则用默认值。

| 名称 | 画面 | 参数 |
|---|---|---|
| `map` | 样本空间三个点 → 实数轴 | `space`、`axis` |
| `cdf` | 阶梯型分布函数，标出一个跳变点 | `mark` |
| `density` | 高矩形 + 窄条，说明密度可大于 1 | `area`、`slice` |
| `moments` | 散点 + 均值竖线 + 宽度括号 | `mean`、`spread` |
| `corr` | 三联小散点：正相关 / 负相关 / U 形 | `labels`（三元数组） |
| `indep` | 一条钟形曲线，两端落到同一 Y | `note` |
| `parabola` | `y=x²` 型抛物线，两点同高 | `left`、`right`、`mid` |
| `joint` | 联合分布表（行×列），数值层可延后 | `rows`、`cols`、`values`（填要显示的文字，0/null 显示 0）、`caption`、`title`、`rowLabel`、`colLabel`、`highlightRow` |
| `branch` | 同一 y 对应两支反函数 | `note` |
| `deadzone` | 平台 + δ 冲激箭头 | `delta`、`note` |
| `char` | 上下两条反向箭头，表示符号相反 | `top`、`bottom`、`note` |
| `gauss2d` | 旋转椭圆族 + r=0 虚线椭圆 | `note` |
| `block` | 输入分布 → 方框变换 → ? | `input`、`box`、`output` |
| `expo` | 指数衰减密度 + 曲线下面积 + 均值虚线 | `mean`、`top` |
| `slice` | 单位正方形 + y=常量切片线，表示条件密度 | `tag` |
| `recip` | r 轴与 g 轴两列，两条曲线交叉，表示倒数把区间翻转 | `note` |
| `gap` | 两段平移斜线，中间留空带，表示取不到的区间 | `band` |
| `custom` | 直接塞一段 SVG 内层代码 | `svg` |

## 用法

```json
"diagram": "joint",
"diagramParams": {
  "rows": ["−0.5", "0", "0.5"],
  "cols": ["0", "0.25"],
  "values": [[0, "1/3"], [1, 0], [0, "1/3"]],
  "highlightRow": 2,
  "caption": "0.5 这一行，两格对不上边缘乘积"
}
```

## 分两段出现（先骨架，后数值）

`joint` 的格子线、行列标签一开始就画好；概率值放在 `<g class="jval" opacity="0">` 里。给卡片加：

```json
"diagram2": "第四步判独立"
```

`diagram2` 的值是触发词，`build_timeline.py` 会把它换算成时间点，`seek()` 在该时刻用 0.7s 淡入数值层。适合“先让学生自己填表，再揭晓”的例题。

其它图示也可以照此思路扩展：把需要延后的部分包进 `class="jval"` 即可。

## 自定义 SVG

`custom` 直接接收一段 SVG 内层标记，坐标按 360×320 设计：

```json
"diagram": "custom",
"diagramParams": {"svg": "<line x1='20' y1='260' x2='340' y2='260' stroke='#9C9483'/><text x='180' y='290' text-anchor='middle' font-size='12'>t</text>"}
```

注意 JSON 里用单引号包属性，避免转义；颜色建议用 `currentColor` 或模块色，保持统一。

## 选图原则

- 一张卡只放一个图示，且必须与这一句旁白直接相关；不要当装饰。
- 图示出现时机由 `diagram` 节拍的触发词控制，通常放在“看这条曲线 / 这张表”那句话上。
- 图内文字不超过 8 处，字号 ≥11.5px，避免在 720p 下糊。
