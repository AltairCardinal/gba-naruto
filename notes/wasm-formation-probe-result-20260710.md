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

## 2026-07-11 units template 重放

后续 `runtime-formation-probe.js` 增加模板池读取：

- template pool：`0x02022E34`，24×`0xBC`；
- result：`/tmp/units-template-result.json`；
- screenshot：`/tmp/units-template-final.png`；
- result SHA-256：`47eb0ce26fe1f0296b448ab931cbf4d9ddf91b00592397bcafc5770029b9819b`；
- final screenshot SHA-256：`a5fb3caaad684fb83a19e83ddfcc258ef0cfd2b6c5c2504532865d5b0d16fb24`。

结果仍为首战 group 40 / variant 0，slot 1 `characterId=1, x=4, y=4`。模板池
slot 1 也为 `characterId=1`，且 battle slot 1 的前 `0xBC` 字节与 template slot 1
完整匹配。

`characterId=1` 映射到 units ROM record `0x5424D0`，但 template payload
`+1..+0xB4` 与 ROM raw record 仅前 7 字节一致：

- template first16：`010e0d0803050505000f005000500000`
- ROM first16：`010e0d08030505000f00500002010000`
- `matchingPrefixBytes=7`
- `firstMismatchOffset=7`
- `rawRecordMatchesRom=false`

因此该样本升级了 formation ID → template → battle slot 的运行时证据，但没有把
units raw record 字段消费升级为 `runtime_verified`。

## 2026-07-11 units raw byte A/B

后续用 `PROBE_ROM` 加载本地 patched ROM，只改 `characterId=1` record 的 byte `+1`：

- file offset：`0x5424D1`
- baseline：`0x0e`
- patched：`0x0f`
- patched ROM：`/tmp/units-char1-byte01-0f.gba`
- patched ROM SHA-256：`734ea05625f4a54d1dbfa2201a8ad75e2c4619e0d14dac92967be87440f4b632`
- result：`/tmp/units-char1-byte01-0f-result.json`
- screenshot：`/tmp/units-char1-byte01-0f-final.png`
- result SHA-256：`ae30e8a149106e4ea4df5dcd67d4e46e29af106efc48023693180ed6c91e0495`
- final screenshot SHA-256：`9154ccd58af26ca9f2181ceb0c1271e7aa7ad0006451479b53a30fe5876cca97`

同一路线仍命中首战 group 40 / variant 0，slot 1 `characterId=1, x=4, y=4`。
template slot 1 first16 从 baseline `01010e0d0803050505000f0050005000` 变为
patched `01010f0d0803050505000f0050005000`，battle slot 1 first16 同步变为
`01010f0d0803050505000f0050005000`。

该 A/B 直接证明 `0x5424D0` raw record byte `+1` 进入 runtime template payload，
再复制到 battle unit slot。units 结构身份和至少一个 raw 字段消费链因此达到动态证据；
剩余工作是逐字段语义命名和安全语义写回。
