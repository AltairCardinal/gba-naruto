# 剧情场景时间线与离线合成（2026-07-29）

## 成果

`artifacts/story-scene-timelines-v1/` 将全部 24 条剧情视觉记录导出为：

- 24 份逐 tick JSON，覆盖 linked tick 1..106；
- 24 张 1200×190 RGBA contact sheet，依次展示 tick 16、32、50、106 和
  overlay wall frame 144；
- 1 份 ROM、上游产物和代码切片哈希绑定的 manifest。

该成果供剧情编辑器离线预览 B/C/D linked scene 与 BG3 overlay 的组合状态。它不是
简单叠加静态 PNG：导出器会解释 scroll、BG enable、priority、alpha/brightness、
palette rotation/brighten、config 4 的 C-path 资源替换，以及 linked palette 的最终
灰度变换。

## 精确时序

单条 story 的控制器时序为：

| 阶段 | wall frame | linked tick |
|---|---:|---:|
| installer prelude 与资源装载 | 1..21 | - |
| installer 内部更新 | 22..37 | 1..16 |
| controller 固定更新 | 38..127 | 17..106 |
| linked palette 灰度变换 | 128..143 | 冻结于 106 |
| BG3 overlay 可见 | 144..383 | 冻结于 106 |

因此旧记录中的“overlay 前只有 90 个 linked frame”不完整：90 是 controller 外层调用
次数，安装器已经先执行 16 次，总 linked tick 数是 106；单条 story 总时长是 383 帧。

## 六种实际 callback mode

24 个 config 的低字节只落入六种专用路径加通用路径：

- config 4：`resource_swap_scroll`，tick 33..66 亮度过渡，tick 50 把 D 资源装到
  C display path；
- config 10：`alpha_enable_and_palette`，tick 32 启用 D，随后 alpha、D palette
  brighten 与 D scroll 同步推进；`0x08098AA0..0x08098AB8` 将截断到 0..7 的
  phase 左移后以 `phase × 2` 加到 B/G/R，故 tick 106 的每通道增量是 14；
- config 17：`secondary_x_motion`；
- config 61/74：`alpha_enable`，tick 32 启用 D；
- config 16：`d_bg_flicker`，task counter modulo 4 的余数 2 启用、余数 0 关闭；
- 其余 18 项：`common_only`。

所有路径仍执行公共 B scroll（每 tick +2 px fixed）和 B palette 2..9 的奇数 tick
轮换。24 个剧情 config 均不使用 updater 的 flag `0x0100` 动态 enable 分支。

## 证据边界

导出器绑定以下原 ROM 代码切片：

- story controller `0x08087C9C..0x08087F24`
- palette transform `0x08088008..0x08088154`
- easing `0x080986E8..0x080986F8`
- visual task `0x0809880C..0x08098E58`
- linked installer `0x080990BC..0x080995C0`
- linked updater `0x080995E8..0x08099ADE`

manifest 明确签发：

- `offline_deterministic_text_bg_composite=true`
- `all_story_rows=true`
- `all_actual_callback_modes=true`
- `runtime_pixel_equivalence=false`

尚未签发的像素级边界是 shadow register 提交顺序、window mask 边缘和代表配置的 mGBA
golden frame。当前系统交换内存压力高，本轮没有启动 mGBA；这不影响离线状态机成果，
但不得据此宣称与硬件逐像素等价。

## 可重复验证

```bash
python3 tools/export_story_scene_timelines.py
python3 tools/verify_story_scene_timelines.py
python3 -m unittest \
  tests.test_export_story_scene_layer_bindings \
  tests.test_export_story_scene_timelines \
  tests.test_export_story_visual_layers \
  tests.test_export_tile_asset_bg_layers
```

验证器同时执行两层检查：

1. 独立校验 24 项顺序、descriptor flags、callback mode、阶段表、逐 tick 交叉字段、
   事件白名单、哈希、PNG 完整性和目录文件集；
2. 从哈希绑定 ROM 重建全部 JSON/PNG 并逐字节比较，证明产物可复现。

运行时像素等价仍需后续受资源守卫的代表帧验证，不能由第 2 层自我重建单独推出。
