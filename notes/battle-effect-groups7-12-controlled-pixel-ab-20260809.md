# Group 7/8/9/10/12 受控 production pixel A/B（2026-08-09）

## 结论

复用 Group 6 的数据驱动 build/run/export/verify 链，Group 7、8、9、10、12
均完成 production 资源重定位后的最终像素 A/B。聚合覆盖由 13/18 提升到
18/18。入口均为已验证的 controlled sequence binder，不声称自然玩法或实体
GBA 执行。

## 严格对照

| Group | sequence | 图形 offset | nibble | LZ77 | VRAM offset | 最终像素 |
|---:|---:|---:|---|---:|---:|---|
| 7 | 9 | `0x68` | `4→15` | 764 | `0x16468` | `(181,26)` |
| 8 | 10 | `0x237` | `7→8` | 1304 | `0x16637` | `(184,34)` |
| 9 | 11 | `0x17` | `13→6` | 554 | `0x16417` | `(198,6)`, `(170,7)`, `(184,15)` |
| 10 | 12 | `0x2D` | `3→5` | 235 | `0x1642D` | `(186,7)`, `(173,19)`, `(181,40)` |
| 12 | 14 | `0x7B` | `1→15` | 1106 | `0x1647B` | `(177,46)` |

- 每组 baseline/candidate 使用相同重定位拓扑、相同 probe 和相同压缩长度，只
  改一个解压图形 nibble；最终像素来自 ack savestate 的离线 Mode-0 重建。
- Group 7/8/9/12 的 EWRAM/IWRAM/IO/PRAM/OAM 均无差异，只有表中一个 VRAM
  字节变化。
- Group 9 初选候选引入栈或计时噪声后被拒绝；最终候选使压缩流仅一字节变化，
  六内存域重新恢复为仅 VRAM 差异。
- Group 10 的 frame-0 可见像素中只有 `3→5` 同时保持 235-byte 压缩长度。
  该候选在 `0x03007F9C` 留下固定 `0x30→0x2C` 差异（栈中的返回路径残留），
  其余非目标内存、OAM、phase 事务和最终像素完全受合同约束；证据没有将其
  误报为“仅 VRAM”。
- 主批 10 次 mGBA 运行以及候选重选运行均由 heavy lock 串行保护；被采用运行
  峰值 owned-tree RSS 为 77.09–79.99 MiB，全部 `pgid_clean=true`。

## 产物与复核

- `artifacts/battle-effect-group07-controlled-pixel-ab-v1/`
- `artifacts/battle-effect-group08-controlled-pixel-ab-v1/`
- `artifacts/battle-effect-group09-controlled-pixel-ab-v1/`
- `artifacts/battle-effect-group10-controlled-pixel-ab-v1/`
- `artifacts/battle-effect-group12-controlled-pixel-ab-v1/`

```bash
for gid in 07 08 09 10 12; do
  python3 tools/verify_controlled_battle_effect_pixel_ab.py \
    --root . --artifact "artifacts/battle-effect-group${gid}-controlled-pixel-ab-v1"
done
python3 tools/verify_battle_effect_observed_frame_phases.py \
  --root . --artifact artifacts/battle-effect-observed-frame-phases-v1
```
