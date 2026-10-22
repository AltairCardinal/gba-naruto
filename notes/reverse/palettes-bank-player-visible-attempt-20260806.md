# Palettes Bank Player-Visible Closure Attempt（2026-08-06）

> 历史失败记录。2026-08-09 已改用自然 Group 3 零输入快照完成闭环，见
> `notes/motion-effect-parameter-player-visible-20260809.md` 与
> `artifacts/motion-effect-parameter-pixel-ab-v1/`。旧实验的 blocker 仅对所选
> Group 13 路线成立，不是 bank 的真实阻塞。

## 结论：未达成 player-visible 差异

尝试对 `sequel/content/palettes/bank.json`（实际是 motion/effect
parameter records，15 条 10-byte records）做 player-visible closure：
1. baseline ROM 不修改
2. candidate ROM: palettes record 0 `y_offset` 字段从 0 改为 10（单字节
   patch at file offset 0x53EE9C = bank base + record 0 * 10 + offset 4）
3. mGBA spawn-capture run（`tools/mgba_palettes_spawn_capture.lua`）：
   - 加载 `artifacts/runtime-checkpoints/battle8-round3-ai-preconfirm.ss9`
   - 推进 600 frame，截图
   - baseline vs candidate PNG SHA 完全相同

## 失败原因

- palettes bank 的 consumer `0x080806B0/0x08080764/0x08080814` 是
  **task spawn** 路径——必须有 active task spawn 才能消费 record 数据
- battle 8 round 3 preconfirm 状态下 AI 选择 action 61（斩首大刀），
  此 action 不消费 palettes record 0（Group 13 sequence 15 走不同路径）
- record 0 的 y_offset 修改即使被消费也只影响 task spawn 时的 sprite
  偏移，不会触发 PNG pixel diff（OBJ-VRAM 在 0x06xxxx 区域，需要 OAM
  提交事务 + 渲染才能体现）

## 失败经验

palettes bank 的 player-visible closure 实际需要：
1. 找一条 formation 路径使 palettes record 0 被消费
2. mGBA 跑 task spawn（不只是 AI observer 选 action）
3. spawn 后捕获 frame，比对 OBJ-VRAM 偏移

该判断已被后续自然 Group 3 实验证伪：无需另造 controlled spawn，既有
scenario-49 延迟对象快照会在零输入下自然消费 record 0。

## 推进状态

- mGBA toolchain（d8bad14b commit 本地编译产物）已可用
- 大量 disasm 已闭合到 dispatcher 函数 + case handler + dispatch table 级
- 当前会话净增量 = 0 个闭合的指标
- 但 3 个可重用工具已签入：
  - `tools/disassemble_battle_effect_dispatchers.py`：dispatcher 链路反汇编
  - `tools/mgba_palettes_player_visible.lua`：cold-boot 截图 probe
  - `tools/mgba_palettes_spawn_capture.lua`：spawn-capture probe
