# Maps 运行时字段链（2026-07-11）

## 静态消费链

map header 基址为 `0x0853D910`，stride 32。`0x08068FB4` 按活动 ID 选择行：

- row `+0` width → `0x0201BE28`；
- row `+2` height → `0x0201BE29`；
- `width >> 2` → `0x0201BE2A`；
- `height >> 1` → `0x0201BE2B`。

`0x08068FF0` 继续从同一行 `+4/+8/+0C/+10（可选）/+14` 读取资源指针并调用
`0x0809C0E8/0x0809C0EC`。

首战 `0x02026805 = 40`，因此候选行是 file `0x53DE10`，原始头
`24 00 2C 00`，即 36×44；运行时预期四字节为 `[36,44,9,22]`。

## 动态探针与门禁

`runtime-formation-probe.js` 已按 TDD 增加 `0x0201BE28..2B` 读取和派生一致性检查。
在真实结果同时满足 battle ID 40、map runtime `[36,44,9,22]` 之前，maps 不升级。

更强 A/B 方案：本地 ROM B 仅把 `0x53DE10` width 从 36 缩为 32，资源指针不变；
相同路线应得到 `[32,44,8,22]`。WASM 的 `uploadRom/loadGame` 支持自动加载本地
ROM，因此无需重新部署。只缩小逻辑边界比扩大尺寸或修改资源指针安全。

## 当前运行限制

固定计数路线多次停在人物页或其转场。探针现增加画面比例分类、B 后等待战前菜单
及显式点击游戏区域恢复键盘焦点。失败样本仍只作导航诊断，不能作为 maps 证据。

## 2026-07-11 A/B 闭环

使用 `play/_scripts/runtime-formation-probe.js` 的 `PROBE_ROM` request-interception
路径加载本地 ROM，完成相同输入路线的 base 与 width32 A/B：

### Baseline

- ROM：部署默认 `naruto-sequel-dev.gba`；
- result：`/tmp/maps-units-result.json`；
- result SHA-256：`d4cee7372be246814eab9a5c5b24c2e5ce1874533622bc19e0a9ab42e8de6fb8`；
- final screenshot SHA-256：`159aa8d898f04619832405c30f6fb62d2dc0519dc8fe3cbd7a5fc04824a6528b`；
- battle ID：40；
- slot 1：`characterId=1, x=4, y=4`；
- positions match：group 40 / variant 0，unique；
- map runtime：`24 2c 09 16` = `[36,44,9,22]`。

### Width32 ROM B

- source ROM：`build/naruto-sequel-dev.gba`；
- patched ROM：`/tmp/maps-width32-build.gba`；
- patch：file `0x53DE10` width byte `0x24 -> 0x20`，即 u16 width `36 -> 32`；
- `cmp -l build/naruto-sequel-dev.gba /tmp/maps-width32-build.gba` 只报告
  `5496337 44 40`（1-based offset，八进制值；对应 file `0x53DE10`）；
- base ROM SHA-256：`eaa515841820cdb1eb75e9b70df827a7722706b2b27b76f9aa6b419cfed22140`；
- patched ROM SHA-256：`b6c394a11566c8d369c104a3c26a7b438542ec87c84f035dbfce3e0928f2187e`；
- result：`/tmp/maps-width32-build-result.json`；
- result SHA-256：`1ab0048655dd033ec652813b0c8b10e0667f82ba237a95546582541e9610aa38`；
- final screenshot SHA-256：`15eae341c684093b4157d676fe0b7a57de636f55782b952630c8c918629e7434`；
- battle ID：40；
- slot 1：`characterId=1, x=4, y=4`；
- positions match：group 40 / variant 0，unique；
- map runtime：`20 2c 08 16` = `[32,44,8,22]`。

判定：该 A/B 只改变 map row 40 的 width 字段，并在同一路线中使运行时 width 和
`width >> 2` 派生值按预期变化，同时 height 与 `height >> 1` 保持不变。因此 maps
row 40 的 width/height runtime 字段链已满足动态验证门禁。资源指针字段仍只由代码链
证明，未因本次 A/B 获得独立字段语义。
