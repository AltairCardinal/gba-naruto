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
IO/PRAM/VRAM/OAM 不变即可与内嵌 PNG 全帧逐字节一致。因此 PNG 是相邻 cursor
animation phase，而非序列化 GPU 状态的 exact frame。产物不得把这两张 PNG
冒充当前 hardware OAM golden。

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

自然 corpus 未覆盖：

- 2D OBJ mapping；
- affine、semi-transparent、OBJ-window 或 object mode 3；
- brighten、no-effect、非零 mosaic；
- WIN1、OBJ-window precedence 和 wrapped window；
- scanline 中途寄存器变化；
- 实体 GBA 的物理显示输出。

这些规则必须用合成 fixtures、独立 verifier 或新增自然样本闭合，不能用当前
89 个 exact PNG 代替。

## 验证

```sh
python3 -m unittest tests.test_render_mode0_checkpoint -v
python3 tools/render_mode0_checkpoint.py \
  --checkpoints artifacts/runtime-checkpoints
python3 tools/verify_mgba_renderer_source.py
```
