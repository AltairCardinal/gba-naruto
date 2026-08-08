# battle-encounters（story visual descriptor）玩家可见闭环

## 结论

历史 slug `battle-encounters` 实际是 ROM `0x54229C` 的 24 条 story visual
descriptor。2026-08-09 的受控运行时 A/B 已证明 record 0 的 `gfx_lz_ptr` 会经
原生 story opcode、状态机和 loader 改变最终画面，因此 bank 从
`code_verified` 升为 `runtime_verified`。

证据为 `artifacts/battle-encounters-story-visual-pixel-ab-v1/`；独立 verifier：

```bash
python3 tools/verify_battle_encounters_story_visual_pixel_ab.py \
  --root . \
  --artifact artifacts/battle-encounters-story-visual-pixel-ab-v1
```

## 可复用入口

规范快照
`artifacts/runtime-checkpoints/scenario-53-story-slideshow-command-controlled.ss9`
由已验真的 `scenario-41-postbattle-dialogue-8.ss9` 只修改 IWRAM
`0x030011F0` 的脚本游标得到：

- parent cursor：`0x08031F31`
- controlled cursor：`0x08049E63`
- 快照 SHA-256：`65cd8b010f9c21a6d5bc93fe8ed1b84fada025136936f6a42f0d540d0f7ab0a9`
- 解压状态只有 offsets `106992..106994` 三字节不同
- `0x08049E63` 是 primary/alternate scenario 53 都可达的原生 opcode `0x14`
  命令 `14 68 01`，把 story state 设为 `0x0168`

该快照只为避免重放长流程；它不证明自然走到 scenario 53。完整 lineage 和重建
命令见同目录的 `scenario-53-story-slideshow-command-controlled-evidence.json`。

## 最小 ROM A/B

构建器只替换 record 0 的 `gfx_lz_ptr`：

- ROM 字段：`0x54229C` / GBA `0x0854229C`
- baseline：`0x0812FF50`
- candidate：record 1 的合法图形流 `0x081303E8`
- 实际变化：`0x54229C..0x54229E` 三字节
- palette 与 tilemap 指针不变

两案各发送一次相同的 `A`（frame 2..9），运行时链一致：

1. `0x08049E63`：opcode `0x14`
2. `0x0808FA2C`：story state `0x8000` dispatch
3. `0x0808A69C`：wrapper
4. `0x08087C9C`：descriptor loader
5. `0x0854229C`：descriptor 0
6. `0x0809C0E8`：graphics、palette、tilemap 三路 LZ77

原生 loader 内部包含同步 VBlank 循环，普通 Lua frame callback 会等函数返回后才
恢复。正式捕获因此在循环内 `0x08087EC0` 断点计数，第 8 次 VBlank 保存 state 和
PNG；不能把函数返回后的帧冒充 overlay 中间帧。

## 运行结果

- baseline/candidate 均在 frame 205 捕获
- graphics source：`0x0812FF50` / `0x081303E8`
- graphics destination：`0x0600E800`
- palette、tilemap、IO、OAM、EWRAM 完全相同
- VRAM：2,348 字节不同，范围 `0xE83E..0xF5C2`
- IWRAM：`0x7F9C` 一字节固定路径残留，已精确签入合同
- 最终像素：1,603 个不同，bbox `(88,48)..(159,108)`
- 离线 Mode-0 renderer 与两张 mGBA PNG 逐像素一致
- 两次资源守卫峰值：108.77 / 108.90 MiB，均 completed、non-degraded、无崩溃

## 失败诊断与边界

早期首次 VBlank 截图发生在 Qt 可见帧更新前，虽有 VRAM 差异但 PNG 尚无差异；
普通 frame callback 延后捕获则已错过 overlay。两者都保留在临时实验历史中，未
进入正式 artifact。

后续两次重跑在 Lua 未产出 audit/start marker 时由资源守卫 `idle-timeout` 清理，
峰值约 111 MiB、无崩溃。`project_resource_guard.py` 当前只用 stdout/stderr 完整行
刷新进度而不保存文本，故不能把这两次静默启动失败归因于 ROM；它们未进入证据链。

本闭环只签发：record 0 图形指针、原生 consumer 和最终像素因果。它不签发自然
scenario-53 导航、其他 23 条 record、其他字段、实体 GBA 或“战斗遭遇”语义。
