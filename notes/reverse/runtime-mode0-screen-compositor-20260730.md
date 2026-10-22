# 运行时 Mode 0 最终屏幕合成核心（2026-07-30）

## 结论

`tools/render_mode0_checkpoint.py` 已把 tracked `.ss9` 中的 Mode 0 text BG、
普通 OBJ、window、alpha/darken 和 backdrop 合成为 240×160 RGB8。它使用
hardware OAM `0x07000000`，不把 shadow OAM 当作当前显示域。

非零 mosaic 现也已按固定 mGBA software-renderer 源码模型接入：BG 在应用
scroll 前按屏幕坐标量化；普通 OBJ 按屏幕 block 量化并在对象边缘 clamp 后
处理 flip；affine OBJ 在 expanded output raster 上量化，再执行 Q8.8 逆变换。
这些规则由 synthetic vectors 覆盖，不冒充本 ROM 的自然非零 mosaic 使用或
实体 GBA 物理验证。

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
  对 91 项得到 `verified=true`、`exact_rgb_count=89`、`errors=[]`；
- 同一 artifact 还读取既有 `battle-effect-affine-runtime-v1` 的正常与阵营
  水平镜像 savestate，独立从 matrix slot `{240,0,0,240}` /
  `{-240,0,0,240}` 重建 OAM entry 2/5 的 32×32 RGBA，对两张已哈希绑定
  runtime-object PNG 均逐像素 exact。
- artifact 另绑定 mGBA commit `1d65391d` 的 Mode 0 BG、OBJ horizontal 和
  OBJ vertical mosaic 三份源码路径及完整 SHA-256；主 renderer 与不导入
  `tools` 的独立 verifier 都通过相同的 BG scroll 相位、4bpp flip/palette、
  normal OBJ screen-vs-local、flip/edge clamp、affine rotation、leading
  partial block 和 double-size vectors。

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

mGBA 官方源码 commit `1d65391d3531f9338300f306c4e1d76c258ce657`
已固定四份文件：

| 文件 | SHA-256 | 用途 |
|---|---|---|
| `software-private.h` | `7bd0201cbd81aa74186121c91bf830ff3e33591a241f5ac5dd66d4842fe7b3aa` | packed-mColor brighten/darken |
| `software-mode0.c` | `1e4104200fa1c068ff4ff17c24d8f99f9e1aed112d75e5088773e1bb6a318783` | text BG horizontal/vertical mosaic |
| `software-obj.c` | `b737ba2372054156fd987f95ed9350e3370f469cb38b40367657c70c02667fe9` | normal/affine OBJ horizontal mosaic |
| `video-software.c` | `39a03b64a3fe9ab384a17de7d92d215298e9f5b64415f7c550d33779c2bbaf70` | OBJ vertical mosaic/clamp |

`tools/verify_mgba_renderer_source.py` 会从固定 commit 的官方 raw URL 下载四份
文件并校验完整 SHA 与关键表达式；它只在显式证据验证时联网，不进入日常单元测试。

## 当前证据边界

91 个主 checkpoint 自然 corpus 未覆盖 2D/8bpp odd-index OBJ、
semi-transparent、OBJ-window、brighten、WIN1 与 wrapped window，但这些路径
现已有独立合成 fixture：

- 8bpp OBJ 明确清除 attr2 tile index bit 0；
- 2D 4bpp OBJ 第二 tile row 使用固定 32 tile-unit stride；
- semi-transparent OBJ 对 backdrop second-target 强制 alpha；
- OBJ-window 非零像素只产生 mask，不绘制自身颜色；
- brighten、`WIN0 > WIN1 > outside` 与 wrapped/empty range。

Affine OBJ 则有单独的原作 runtime corpus：正常/镜像两个 matrix slot 的 bound
object pixels 已 exact；synthetic double-size fixture 又证明扩大的是输出边界，
不缩放 source。mosaic 的 synthetic source-model vectors 已覆盖 normal、rotation、
leading partial block 和 double-size。

仍未闭合：

- object mode 3 的自然行为；
- 原 ROM 的自然非零 BG/OBJ mosaic 使用证据；
- OBJ-window+mosaic 的实体硬件语义；
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
