# 角色场景视觉包导出证据（2026-07-29）

## 结论

ROM 表 `0x085A4CE8` 已从未覆盖的 LZ77 候选推进为可重复、可独立验证的整表图像成果：

- 精确范围为 9 条 × `0x1C`，结束于 `0x085A4DE4`；
- 每条包含一组 8bpp BG 图形、packed tilemap、128 色 BG palette、一组 4bpp OBJ
  图形、definition/animation 指针对、画布宽高、presentation ID 和生成对象数；
- 共导出 9 张原生紧致背景、9 组 OBJ 图形、18 张双 palette OBJ atlas 和 16 张
  definition frame PNG；
- 所有背景 tile 和 OBJ tile 都被对应 tilemap/definition 完整引用；
- 静态帧和 palette bank 已闭合，但最终屏幕位置、viewport 裁剪和动画时序仍未闭合。

本成果补齐 `menu-portraits-v1` 之前紧邻但不重叠的视觉表，不把人物可见身份或最终场景
合成冒充为已证明语义。

## ROM 与消费者锚点

- ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 表：`0x085A4CE8..0x085A4DE3`
- 表 SHA-256：
  `b562062061a088aac2e5ce2f2d9f8bbfd34f0cb53a794a7ea5b0f270ecf909b3`
- 条目数/步长：`9 / 0x1C`

字段由消费者直接闭合：

| 偏移 | 类型 | 消费方式 |
|---:|---|---|
| `+0x00` | BG graphics LZ77 | 解压到 `0x06004000` |
| `+0x04` | packed tilemap LZ77 | 解压到 `0x02002880`，再按宽高复制到 `0x06000000` |
| `+0x08` | raw BG palette | 复制 128 个 BGR555 色到 `0x05000000` |
| `+0x0C` | OBJ graphics LZ77 | 解压到 `0x06010000`，按 32-byte 4bpp tile 消费 |
| `+0x10` | definition pointer table | `0x080626B4` 写入 task，frame selector 读取 component list |
| `+0x14` | animation pointer table | 选择对应 frame；记录第二字段为 0，时序语义未命名 |
| `+0x18/+0x19` | packed width/height | 传给 BG tilemap copier |
| `+0x1A` | 1-based presentation ID | 非零时减一索引 `0x085A320C` |
| `+0x1B` | spawned task count | 1 或 2，也是 palette bank/frame 集合上界 |

关键消费者切片及 SHA-256 已写入 manifest：

- setup/row 0：`0x0808BAB0..0x0808BEDD`
- 通用 row loader：`0x0808BEE4..0x0808BF61`
- OBJ spawner：`0x0808C0B4..0x0808C163`
- presentation selector：`0x0808C18C..0x0808C1EB`
- controller：`0x0808C214..0x0808C4C1`
- task allocator：`0x080626B4..0x0806275D`
- animation/frame selector：`0x0806298C..0x080629F5`
- OAM attr2 writer：`0x08063108..0x0806311F`
- animation timing consumer：`0x08063256..0x080632D7`
- packed tilemap copier：`0x08063604..0x080636BF`

`BG0CNT=0x4086` 证明背景为 8bpp、charblock 1、screenblock 0、512×256 硬件画布。
packed rectangle 固定高 20 tile，宽 18–23 tile；导出的 144–184×160 PNG 是表自身能
证明的紧致画布。运行时 scroll 和 240×160 viewport 裁剪仍由 controller 状态决定。

## OBJ 调色板与静态帧

9 条记录共用两套 16 色 OBJ palette：

- bank 0：`0x083F2794` → `0x05000200`，SHA-256
  `14975f2391f88813040bbadc136bbfcaa736a408521af3701054bf0470d5a4f9`
- bank 1：`0x083F2CB0` → `0x05000220`，SHA-256
  `bb58f9bc0be9a3b7ad2604ced29815b23d55660c89e70e59430959cf7aed8b2f`

`0x0808C114..0x0808C11A` 把生成循环索引同时作为 animation selector 和 palette
bank；`0x0806298C..0x0806299C` 再读取 timeline frame ID 选择 definition frame。
当前九条数据恰好把 animation 0/1 一一映射到同号 frame 0/1，因此双对象条目最终使用
frame/bank 0、1，单对象条目只使用 0。definition 的 `0x14` 字节 component、H/V flip、
tile 范围和本地包围框均已解析，16 张 frame PNG 覆盖各自 OBJ 图形的全部 tile。

animation 表每项只包含 `(frame_id, 0), (0xFFFF, 0)`。它足以证明 frame 集合，但零值
不能被擅自解释为播放时长、循环或驻留时间。因此 manifest 明确保持：

- `obj_animation_frame_sets_complete=true`
- `obj_animation_timing_complete=false`
- `screen_space_composition_complete=false`

## 可重复成果

- 导出器：`tools/export_scene_visual_packs.py`
- 独立 verifier：`tools/verify_scene_visual_packs.py`
- 测试：`tests/test_export_scene_visual_packs.py`
- 产物：`artifacts/scene-visual-packs-v1/`
- 文件数：100
- 体积：约 640 KiB
- manifest SHA-256：
  `e41e510bafafbe5a022163d71a2bf2288dc8a4fe84a03f4ee5c07758cf5c895c`

重复生成和验证：

```bash
python3 tools/export_scene_visual_packs.py \
  --root . \
  --output-dir artifacts/scene-visual-packs-v1
python3 tools/verify_scene_visual_packs.py \
  --root . \
  --artifact-dir artifacts/scene-visual-packs-v1
python3 -m unittest tests.test_export_scene_visual_packs -v
```

独立 verifier 不导入导出器或仓库图像 helper，而是重新实现 LZ77、tilemap/definition
解析和 PNG raster/palette 检查；测试确认 manifest、背景 PNG 或 OBJ frame PNG
被篡改时都会拒绝。

本里程碑完全离线读取 ROM，没有启动 mGBA，也没有写入 `butano-sequel/`。生成时
`memory_pressure -Q` 报告系统可用内存 65%，未发生资源异常。

## 边界与下一批

本成果没有证明：

- 9 条记录的自然语言场景名或人物身份；
- controller 决定的最终横向 scroll、viewport crop、screen-space OBJ 位置和层级；
- animation 第二字段为 0 时的准确播放语义；
- `0x085A8014` 的三张世界地图背景及其相邻 overlay。

下一图像批次优先导出已闭合的 `0x085A8014` 三张 240×160、8bpp 世界地图背景，再追踪
紧邻 `0x085A8038` 的显示对象表以形成 overlay/composite。
