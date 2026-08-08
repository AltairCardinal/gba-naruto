# Group 6 受控 production pixel A/B（2026-08-09）

## 结论

Group 6 / sequence 8 已完成 production 资源重定位后的最终像素 A/B。该结果将
战斗特效 production modified-ROM pixel 覆盖由 12/18 提升为 13/18。

入口是受控 sequence binder，不是自然玩法；结论只证明 Group 6 的资源经游戏
加载、task renderer、shadow OAM、submit、ack 和最终 Mode-0 合成链生效，不证明
剧情自然可达或实体 GBA 执行。

## 严格对照

- 输入：已验证的 scenario 50 玩家回合快照，scratch 初值为 0。
- 两份 ROM 使用相同 relocation 拓扑、相同 sequence-8 probe 和相同 494-byte
  LZ77 长度；仅解压图形 offset `0x1E` 的低 nibble 从索引 2 改为 8。
- 两次 mGBA 均完成 binder→renderer→submit→ack，task 固定为 slot 108、tile
  base 800、palette bank 13。
- 六个内存域中仅 VRAM offset `0x1641E`（绝对地址 `0x0601641E`）变化。
- ack savestate 的离线 Mode-0 重建仅出现两个最终像素变化：`(173,9)` 与
  `(183,33)`，均由 `[206,255,255]` 变为 `[255,0,0]`；第三个同源 OAM 实例
  `(199,24)` 被合成层遮挡，未计入最终差分。
- mGBA breakpoint PNG 在 A/B 间逐字节相同，未被当作像素证据；像素结论来自
  完整 ack savestate 的独立离线重建。
- 峰值 owned-tree RSS：baseline 79.453 MiB，candidate 79.242 MiB；两次
  `pgid_clean=true`。

## 产物与复核

- 产物：`artifacts/battle-effect-group06-controlled-pixel-ab-v1/`
- 配置：`sequel/content/battle-effect-controlled-pixel-ab/group-06-sequence-08-controlled.json`

```bash
python3 tools/verify_controlled_battle_effect_pixel_ab.py \
  --root . --artifact artifacts/battle-effect-group06-controlled-pixel-ab-v1
python3 tools/verify_battle_effect_observed_frame_phases.py \
  --root . --artifact artifacts/battle-effect-observed-frame-phases-v1
```
