# 剧情视觉场景图层绑定（2026-07-29）

## 结论

剧情 opcode handler `0x0808FA2C` 经 `0x0808A69C` 进入 `0x08087C9C`，后者按
0..23 顺序播放 `0x0854229C` 的全部 24 条 story descriptor。每条 `+0x0C`
`config_id` 在 `0x08087DE8` 被截为 `u8`，随后直接按
`0x085A320C + config_id × 0x44` 索引：

- 这是零基 direct ID，不使用公共入口 `0x08098442` 的 `input_id - 1` 规则；
- 24 个 config 依次为
  `4,10,14,24,17,18,21,25,29,28,34,76,30,47,48,49,51,52,58,61,74,16,77,5`；
- 全部落在 0..78，且没有命中 sentinel `13/31/32/46`；
- 人类可见的一基 consumer ID 是 `config_id + 1`。

持久成果 `artifacts/story-scene-layer-bindings-v1/manifest.json` 将 24 条映射逐项
绑定到已验证的 `story-visual-layers-v1` 与修正后的 `tile-assets-bg-v2`，同时记录
ROM、上游 manifest 和三段消费者代码哈希。

## 同屏硬件图层

| 逻辑层 | GBA BG | priority | charblock | screenblock | palette | 色深 |
|---|---:|---:|---:|---:|---:|---:|
| story overlay | BG3 | 0 | 3 | 3 | bank 15 | 4bpp |
| linked B | BG2 | 3 | 3 | 2 | bank 12 | 4bpp |
| linked C | BG0 | 2，flag `0x0200` 时 1 | 1 | 0 | bank 0 | 8bpp |
| linked D | BG1 | 1，flag `0x0200` 时 2 | 1 | 1 | bank 4 | 4bpp |

- story overlay gfx 写 `0x0600E800`，相对 charblock 3 的 tile base 为 `0x140`，
  tilemap 写 `0x06001800`；
- 通用初始化器 `0x08065404` 先把 BG3CNT 临时设为 `0x0300`，剧情专用路径随后在
  `0x08087CEA` 明确写入 `0x030C`，在启用 BG3 前选择 charblock 3、screenblock 3、
  priority 0；因此 `0x0600C000 + 0x140 × 32 = 0x0600E800`，寄存器与资源地址一致。
  只观察通用初始化的中间值会错误得出 charblock 0；
- B gfx 从 `0x0600C000` 开始，32×14 tilemap 从 screenblock 2 的第二行
  `0x06001040` 开始；
- C gfx 从 `0x06004000` 开始，tile base 是 `state[0x16] >> 1`；消费者设置
  BG 8bpp bit，并复制 128-byte/64-color palette；
- D 与 C 共用 charblock 1，tile base 是
  `u16(state[0x12] + state[0x16])`，保持 4bpp。

A (`descriptor +0x0C/+0x10/+0x14`) 只由另一条 caller-argument 加载路径使用；
story installer 不加载它，因此本工件明确排除 A，不把它误叠入剧情画面。

## D 层与优先级门

24 项中只有 config `4/10/61/74/16` 带完整 D 资源：

- config 4 因 flag `0x0400` 禁止加载；
- config `10/61/74/16` 实际加载；
- config `10/61/74` 因初始 enable 门 `flags & 0x0900` 关闭 BG1；
- config 16 是安装结束时唯一立即启用 BG1 的项；
- config 61 置 flag `0x0200`，因此 C/BG0 与 D/BG1 的 priority 交换为 1/2。

“初始关闭”不等于整段永不显示；`0x080995E8` 后续仍会更新 enable、scroll 和 blend。

## 为什么不输出伪最终截图

loader 安装 linked scene 后先调用 `0x080995E8` 90 帧，才启用 story BG3；overlay
显示 240 帧后关闭。现有静态资源不能单独确定第 90 帧或任意展示帧的：

- BG scroll、wrap 和 viewport；
- BG enable 的动态变化；
- brightness、alpha 与 blend 寄存器；
- palette transform；
- C/D 共用 charblock 1 时的实际 VRAM 状态。

所以本成果的 `scope.final_composite=false`。它闭合“哪组资源进入哪个硬件层”，但不以
简单 PNG alpha 覆盖冒充原作运行帧。最终像素等价 composite 仍需固定 tick 的 GPU
状态证据，或对 `0x080990BC/0x080995E8` 状态机的独立解释器。

## 可重复成果

- 导出器：`tools/export_story_scene_layer_bindings.py`
- 独立验证器：`tools/verify_story_scene_layer_bindings.py`
- 测试：`tests/test_export_story_scene_layer_bindings.py`
- 工件：`artifacts/story-scene-layer-bindings-v1/`

```bash
python3 tools/export_story_scene_layer_bindings.py
python3 tools/verify_story_scene_layer_bindings.py
python3 -m unittest \
  tests.test_export_story_scene_layer_bindings \
  tests.test_export_tile_asset_bg_layers
```

验证结果为 24/24 bindings、79/79 linked descriptors、236/236 linked complete
layers、108/108 atlases，`errors=[]`。本轮只离线读取 ROM，没有启动新的 mGBA，也没有
写入 `butano-sequel/`。
