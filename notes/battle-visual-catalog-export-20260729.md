# 79 项战斗视觉表现目录（2026-07-29）

## 结论

原 ROM 的 79 项 `0x44` visual descriptor 与 79 条表现消息并非两套无关编号：

- `0x08098442..0x08098460` 将调用方的 1-based `input_id` 减一，保存为状态字节 0，
  并以 `state_id × 0x44` 索引 `0x085A320C`；
- `0x08099564..0x08099582` 从同一状态字节 0 以 `state_id × 4` 索引
  `0x085A2B08` 的 message pointer；
- `0x08098138..0x0809816B` 又以同一 `state_id × 10` 读取
  `0x085A2EF4` 的 message/glyph binding。

因此可以签发完整的：

```text
consumer input 1..79
  → descriptor/message ID 0..78
  → A/B/C/D 静态图层
  → 原始消息字节
  → 有序 glyph/skip 槽
```

统一成果 `artifacts/battle-visual-catalog-v1/` 包含 79 项机器可读目录和 79 张编辑器
预览图；每张预览按 A/B、C/D 两行展示已闭合的静态图层，并在底部按原 binding 槽位
排列运行时 palette bank 13 的消息字形。用户可以直接按 consumer ID 浏览一项表现会
使用的角色图、背景/特效图层和术名字形，不再需要手工对齐两份 manifest。

目录现同时保留每项完整的 17 个 raw words、packed definition、全部资源指针和图层
状态，并把运行时装载门解释为机器字段。descriptor 0 的 D 不是“等待寻找 gfx/palette”
的可显示层：它只有 tilemap `0x0836774C`，gfx 指针为零，因此 installer 明确拒绝装载；
该孤立 tilemap 仍被无损保留。相反，descriptor 4 的 D 三件套完整，只因 flag
`0x0400` 不走 D installer，随后在 tick 50 作为 C display path 的动态资源来源。
这一区分使编辑器不会把 dormant 指针误报成缺失素材，也不会误删 config 4 的切换资源。

## 数量与边界

- descriptor/message：`79/79`
- 完整静态图层：`236`
- 实际 glyph 槽：`284`
- `0xFF` 跳过槽：`10`
- sentinel descriptor：`13、31、32、46`
- 预览：`79` 张，固定 `600×368` RGBA
- 文件数：`80`
- 体积：约 `2.2 MiB`

`0xFF` 是消费者明确跳过的槽，不是 glyph 255。目录保留它们的原始 slot 与空白间距，
避免把 `[glyph, glyph, 0xFF, glyph]` 错排成连续三个字符。

预览图是编辑器用分区 contact sheet，不是原 ROM 最终屏幕合成。以下内容仍保持未完成：

- `0x080990BC` / `0x080995E8` 状态机的逐 tick scroll、enable、blend 与 palette
  transform；
- 各图层的最终 screen-space 叠加、共享 VRAM 覆盖和 OBJ 层级；
- 原始消息字节到字符的完整文本解码；
- 79 项自然语言业务名称。

## 来源与可审计性

- ROM：`rom/base.gba`
- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 图层来源：`artifacts/tile-assets-bg-v2/manifest.json`
- 图层 manifest SHA-256：
  `1df63cf6cf49079115e997c6f0f33c57578e517dbe22dc16c15f64c4d218a749`
- 字形来源：`artifacts/battle-presentation-glyphs-v1/manifest.json`
- 字形 manifest SHA-256：
  `ecc44fde0d886b75397d34181112f5b86dbb791b09e3b85797e9b4013f4e74a7`
- 本成果 manifest SHA-256：
  `1ccbdfda751953328104c845e061074150324ca69a569330a25263e5be787bcc`

导出器拒绝覆盖仓库根、仓库父目录或无本 schema manifest 的非空目录；发布采用同目录
原子替换，注入替换失败时会恢复上一份完整成果。独立 verifier 不导入导出器，重新核对
ROM consumer slice、两份来源 manifest、全部源 PNG 哈希、79 项索引关系、预览像素和
精确文件集合。

## 重放与验证

```bash
python3 tools/export_battle_visual_catalog.py \
  --root . \
  --output-dir artifacts/battle-visual-catalog-v1
python3 tools/verify_battle_visual_catalog.py \
  --root . \
  --artifact-dir artifacts/battle-visual-catalog-v1
python3 -m unittest \
  tests.test_export_tile_asset_bg_layers \
  tests.test_export_battle_presentation_glyphs \
  tests.test_export_battle_visual_catalog -v
```

本轮相关来源与新增测试全部通过；独立 verifier 返回
`79/236/284/10、errors=[]`。人工抽查 `visual-00`、`visual-10` 和带 `0xFF` 空槽的
`visual-35`，图层和字形均可读。全程离线读取 ROM 与已提交 artifact，没有启动 mGBA、
没有写入 `butano-sequel/`。
