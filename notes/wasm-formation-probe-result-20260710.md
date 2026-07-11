# WASM formation probe structured result

```json
{
  "schemaVersion": 1,
  "deployment": "https://sh.kibox.com.cn/gba-naruto/play/",
  "outcome": "matched",
  "reason": "unique-formation-after-settle",
  "plan": {
    "startCount": 30,
    "advanceCount": 250,
    "startDelayMs": 500,
    "confirmDelayMs": 750,
    "advanceDelayMs": 300,
    "keyHoldMs": 150,
    "tailKeys": ["KeyX", "ArrowDown", "ArrowDown", "KeyZ", "KeyZ"],
    "settleCount": 40,
    "settleDelayMs": 500
  },
  "stages": [
    { "step": 30, "phase": "boot", "wramState": "empty", "nonzeroBytes": 0 },
    { "step": 31, "phase": "new-game", "wramState": "empty", "nonzeroBytes": 0 },
    { "step": 281, "phase": "story", "wramState": "empty", "nonzeroBytes": 0 },
    { "step": 286, "phase": "tail", "wramState": "changed", "nonzeroBytes": 111 },
    { "step": 326, "phase": "settle", "wramState": "stable", "nonzeroBytes": 121 }
  ],
  "final": {
    "step": 326,
    "phase": "settle",
    "wramState": "stable",
    "nonzeroBytes": 121,
    "runtimePositions": [{ "slot": 1, "x": 4, "y": 4 }],
    "observedScreen": "首战地图已加载，鸣人战斗单位已实例化"
  },
  "match": {
    "groupId": 40,
    "variantId": 0,
    "recordId": 0,
    "romOffset": "0x588CA8",
    "romCoordinate": [4, 4],
    "unique": true
  },
  "rawArtifact": "/tmp/formation-confirm-result.json",
  "screenshots": [
    "/tmp/formation-confirm-final-tail.png",
    "/tmp/formation-confirm-final-settle.png",
    "/tmp/formation-confirm-final.png"
  ]
}
```

## 证据修正

原始结果还列出 slot 21/22 的 `(0,0)`，原因是旧探针扫描 24 个
`0x1D4` 槽位，但 `0x02026804` 已是下一个已知战斗控制块。
`(0x02026804 - 0x020240C0) // 0x1D4 = 21`，因此合法单位槽位只有
`0..20`。TDD 回归测试先复现 slot 21 误报，修正扫描上限后只剩
slot 1 `(4,4)`。

positions bank 中仅 group 40 / variant 0 在无多余活动记录的情况下
精确包含该坐标：record 0，ROM `0x588CA8`，`+2/+3 = 4/4`。

## 2026-07-11 独立重放

相同导航路线再次成功进入首战，结构化结果保存于本机
`/tmp/formation-recovery-result.json`：

- step 286（tail）首次出现单位区变化，共 102 个非零字节；
- slot 1 坐标仍为 `(4,4)`，再次唯一匹配 group 40 / variant 0；
- `0x02026804..0x0202680B = 00 28 00 00 00 00 00 00`，因此
  `0x02026805` 的章节/战斗标识为十进制 40，与编成 group 40 一致；
- 最终截图 SHA-256 为
  `b78e2635b9938289e95542f0e9f12d35ab8350400aa7885adb68b2be4ad15478`。

本次运行配置了 settle 每 2 轮补发 A 的恢复策略，但单位在进入 settle 前已出现，
所以该样本证明原始尾序列可再次成功，不构成恢复按键已被真实触发的证据。

同一 ID 可索引 maps 第 40 行（ROM `0x53DE10`，36×44），但 WASM 没有 PC/LR，
且本次没有把某个 map header 字段与加载器输出建立因果对应。因此该关联只作为
maps 后续探针线索，不能把 maps 从 `code` 提升为 `runtime_verified`。

## 2026-07-11 maps/units baseline 重放

使用 macOS Chrome 和 `PROBE_BROWSER` 路径参数重跑交接文档推荐路线，结果保存于
本机 `/tmp/maps-units-result.json`：

- `outcome=matched`，`reason=unique-formation`；
- step 286（tail）首次出现单位区变化，共 102 个非零字节；
- slot 1：`characterId=1, x=4, y=4`；
- 唯一匹配 positions group 40 / variant 0，且无 missing/extra；
- `0x02026804..0x0202680B = 00 28 00 00 00 00 00 00`，battle ID 为 40；
- map runtime `0x0201BE28..2B = 24 2c 09 16`，解码为 `[36,44,9,22]`，
  且 `36>>2=9`、`44>>1=22`；
- 最终截图显示首战地图已加载。

本次 artifact 摘要：

- result SHA-256：`d4cee7372be246814eab9a5c5b24c2e5ce1874533622bc19e0a9ab42e8de6fb8`；
- final screenshot SHA-256：`159aa8d898f04619832405c30f6fb62d2dc0519dc8fe3cbd7a5fc04824a6528b`。

该样本满足 maps A/B 实验的 baseline 前置条件，并把 slot 1 runtime
`characterId=1` 与首战 positions group 40/variant 0 同步记录到同一次采集中。
但 WASM 仍无 PC/LR/断点能力；maps 还需 width 36→32 的受控 A/B，units 还需把
runtime character ID 1 明确闭合到 `0x54241C + 1*0xB4` 的真实角色定义记录后，
才能升级为 `runtime_verified`。
