# 运行时 Mode 0 最终屏幕合成核心（2026-07-30）

## 结论

`tools/render_mode0_checkpoint.py` 已把 tracked `.ss9` 中的 Mode 0 text BG、
普通 OBJ、window、alpha/darken 和 backdrop 合成为 240×160 RGB8。它使用
hardware OAM `0x07000000`，不把 shadow OAM 当作当前显示域。

91 个 checkpoint 的离线结果：

| 项目 | 结果 |
|---|---:|
| Mode 0 | 91/91 |
| active OAM | 1211 |
| 1D OBJ mapping | 91/91 |
| normal / non-affine OBJ | 1211/1211 |
| alpha effect | 53 |
| darken effect | 38 |
| WIN0 | 5 |
| 与 `.ss9` 内嵌 PNG 逐 RGB 字节完全一致 | 89/91 |

逐像素实现先按 enabled BG 解码完整层，再按每个实际 OBJ 的包围盒建立候选表；
不再对每个屏幕像素扫描 128 个 OAM，因此全 91 帧测试约 28 秒、峰值进程树 RSS
约 31 MiB。

## 两个截图相位边界

唯二非 exact 的帧都只差 OAM entry 0 的一个 8×16 动画光标：

| checkpoint | serialized hardware/shadow tile | screenshot exact tile | 差异 |
|---|---:|---:|---:|
| `alternate-character-submenu.ss9` | `0x3F4` | `0x3FA` | 53 pixels / 157 bytes |
| `skill-list-pre-controller.ss9` | `0x3FA` | `0x3F8` | 30 pixels / 88 bytes |

两帧的 hardware OAM 与 shadow OAM 完全相等；分别只替换 attr2 tile 后，其他
IO/PRAM/VRAM/OAM 不变即可与内嵌 PNG 全帧逐字节一致。因此 PNG 与序列化状态
处于不同 cursor tile phase，而非序列化 GPU 状态的 exact frame。产物不得把
这两张 PNG 冒充当前 hardware OAM golden。

严格来说，现有证据只证明“内嵌 PNG 与序列化 OAM 的 cursor tile phase 不同”，
没有证明两者在时间上一定相邻；`screenshot_capture_phase_timing_complete` 因此
保持 `false`。

## 可审计成果

`artifacts/runtime-screen-composites-v1/` 已把全部 91 个静态 checkpoint
成果化：

- `runtime-screen-composites.json` 逐项绑定 checkpoint、IO、PRAM、VRAM、
  hardware OAM、shadow OAM、rendered RGB 与 screenshot RGB 的 SHA-256；
- renderer 输入明确固定为 hardware OAM `0x07000000`，shadow OAM
  `0x0300027C` 只用于相位诊断；
- 91 张 rendered PNG 收进 1.7 MiB 的确定性 `frames.zip`，避免把大量小文件
  直接加入 Git；
- 两个非 exact 项记录 OAM entry 0 原始字节、对象矩形、差异坐标哈希，并证明
  所有差异都位于该对象矩形内；仅替换 attr2 tile 后反事实全帧 exact，未解释
  差异数为 0；
- `tools/verify_runtime_screen_composites.py` 不复用 exporter/renderer，
  独立解析 `.ss9`、重建 BG/OBJ/window/blend、ZIP 和 promotion manifest，
  对 91 项得到 `verified=true`、`exact_rgb_count=89`、`errors=[]`。

这闭合的是“已跟踪序列化 GPU 域的 Mode 0 静态屏幕合成”，不是所有游戏视觉
状态、跨帧 scanline 行为或实体 GBA 输出。

## 合成规则

- BG：priority 数值小者在前，同 priority 时 BG index 小者在前；
- OBJ：同 priority 时覆盖 BG，OBJ 间 OAM index 小者在前；
- window：`WIN0 > WIN1 > OBJ-window > outside`，WININ/WINOUT 控制
  BG0–BG3、OBJ 和 special effect；
- alpha：只在 top first-target 与 behind second-target 成立时应用；
- brighten/darken 的 BGR555 公式保留为硬件语义测试；
- `.ss9` PNG 比较复现 mGBA 32-bit software renderer 的 RGB8 packed-mColor
  舍入。

mGBA 官方源码 commit `1d65391d3531f9338300f306c4e1d76c258ce657` 的
`src/gba/renderers/software-private.h` SHA-256 为
`7bd0201cbd81aa74186121c91bf830ff3e33591a241f5ac5dd66d4842fe7b3aa`。
其 `_brighten`、`_darken` 正是在 packed `mColor` 上执行；红通道未移位，
green/blue 先移位再除法，所以 darken 的 RGB8 舍入不能用一个普通三通道公式
替代。`tools/verify_mgba_renderer_source.py` 会从该固定 commit 的官方 raw URL
下载文件，校验完整 SHA 及三组 packed channel 表达式；它只在显式证据验证时联网，
不进入日常单元测试。

## 当前证据边界

自然 corpus 未覆盖 2D/8bpp odd-index OBJ、semi-transparent、OBJ-window、
brighten、WIN1 与 wrapped window，但这些路径现已有独立合成 fixture：

- 8bpp OBJ 明确清除 attr2 tile index bit 0；
- 2D 4bpp OBJ 第二 tile row 使用固定 32 tile-unit stride；
- semi-transparent OBJ 对 backdrop second-target 强制 alpha；
- OBJ-window 非零像素只产生 mask，不绘制自身颜色；
- brighten、`WIN0 > WIN1 > outside` 与 wrapped/empty range。

仍未闭合：

- affine OBJ、object mode 3 的自然行为；
- 非零 BG/OBJ mosaic；
- scanline 中途寄存器变化；
- 实体 GBA 的物理显示输出。

合成 fixture 证明确定性算法分支，但不冒充原 ROM 的自然使用证据；screen
artifact 的 scope 已分别记录 natural-covered、synthetic-covered 与 unresolved。

## 验证

```sh
python3 -m unittest tests.test_render_mode0_checkpoint -v
python3 tools/render_mode0_checkpoint.py \
  --checkpoints artifacts/runtime-checkpoints
python3 tools/verify_runtime_screen_composites.py \
  --root . \
  --artifact artifacts/runtime-screen-composites-v1
python3 tools/verify_mgba_renderer_source.py
```
