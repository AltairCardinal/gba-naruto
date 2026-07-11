# 角色定义与战斗单位复制链（2026-07-11）

## 结论

真实角色定义表位于 ROM `0x0854241C`（file `0x54241C`），共 63 条（ID 0..62），
stride `0xB4`。末条从 `0x544FB4` 开始，表结束于 `0x545068`。`0x545068..0x545079`
是 18 字节 gap，实际字节为 `00000000000000000000000000000000aa05`：前 16 字节为零，
末 2 字节不是零。现有成长表 bank 仍从 `0x54507A` 开始，因此不能再把整段 gap 记为
“18 字节零填充”。

旧 `units` bank 所称 `0x53F298` 角色 ID 表已撤销；该地址唯一消费者属于对象/渲染
偏移查找。

## ROM → 模板 → 战斗槽

1. `0x0806D4A0` 输入 character ID 和 level，创建 WRAM 角色模板；
2. `0x0806D4D6` 把 character ID 写到模板 `+0`；定义源为
   `0x0854241C + character_id*0xB4`；
3. 模板池基址 `0x02022E34`，24 槽，stride `0xBC`；
4. `0x0806E2F4..0x0806E312` 用 formation record `+0` 与模板 `+0` 匹配；
5. `0x0806AC88..0x0806AC98` 计算模板源地址；
6. `0x0806AAA4..0x0806AAB0` 复制模板前 `0xBC` 字节到
   `0x020240C0 + battle_slot*0x1D4`，所以战斗槽 `+0` 也是 character ID。

首战 formation `0x588CA8` 的 record[0]=1，动态预期 slot 1
`0x02024294[0]=1`，并应与某个模板槽 `+0=1` 一致。探针已输出战斗槽
characterId。后续单字节 A/B 已证明 ROM raw record 的至少一个字段进入模板；但其余
字段语义和安全语义回写仍需逐项证明。

## 2026-07-11 WASM 首战样本

使用 `play/_scripts/runtime-formation-probe.js` 读取首战运行时内存，结果保存于本机
`/tmp/units-template-result.json`：

- `outcome=matched`，唯一匹配 positions group 40 / variant 0；
- battle ID 40，map runtime `[36,44,9,22]`；
- 战斗 slot 1 为 `characterId=1, x=4, y=4`；
- 模板池 slot 1 为 `characterId=1`，前 16 字节
  `01010e0d0803050505000f0050005000`；
- 战斗 slot 1 的前 `0xBC` 字节与模板池 slot 1 完整匹配；
- `characterId=1` 对应 ROM record `0x5424D0`，但模板 payload
  `+1..+0xB4` 与 ROM raw record 仅前 7 字节一致：
  - template first16：`010e0d0803050505000f005000500000`
  - ROM first16：`010e0d08030505000f00500002010000`
  - `matchingPrefixBytes=7`
  - `firstMismatchOffset=7`
  - `rawRecordMatchesRom=false`

Artifact SHA-256：

- result：`47eb0ce26fe1f0296b448ab931cbf4d9ddf91b00592397bcafc5770029b9819b`
- final screenshot：`a5fb3caaad684fb83a19e83ddfcc258ef0cfd2b6c5c2504532865d5b0d16fb24`

解释：这个样本动态证明了 formation character ID → runtime template slot →
battle unit slot 的选择和复制链；它没有证明 `0x5424D0` 的 180 字节 raw record 被
逐字节复制到模板。

## 2026-07-11 `0x5424D0` 单字节 A/B

用 `PROBE_ROM` request interception 加载本地 patched ROM，只改一字节：

- file offset：`0x5424D1`；
- ROM record：`characterId=1`，`0x5424D0 + 1`；
- baseline byte：`0x0e`；
- patched byte：`0x0f`；
- patched ROM：`/tmp/units-char1-byte01-0f.gba`；
- patched ROM SHA-256：
  `734ea05625f4a54d1dbfa2201a8ad75e2c4619e0d14dac92967be87440f4b632`。

同一路线结果：

- `outcome=matched`，唯一匹配 positions group 40 / variant 0；
- battle ID 40，map runtime `[36,44,9,22]`；
- slot 1 仍为 `characterId=1, x=4, y=4`；
- template slot 1 first16 从 baseline
  `01010e0d0803050505000f0050005000` 变为
  `01010f0d0803050505000f0050005000`；
- battle slot 1 first16 同步变为
  `01010f0d0803050505000f0050005000`，并继续匹配 template slot 1；
- template payload first16 为 `010f0d0803050505000f005000500000`。

Artifact SHA-256：

- result：`ae30e8a149106e4ea4df5dcd67d4e46e29af106efc48023693180ed6c91e0495`
- final screenshot：`9154ccd58af26ca9f2181ceb0c1271e7aa7ad0006451479b53a30fe5876cca97`

解释：这个 A/B 动态证明 `0x5424D0` raw record 的 byte `+1` 被运行时消费并进入
`0x02022E34` 模板 payload，再由模板复制到 `0x020240C0 + slot*0x1D4` 的战斗单位槽。
因此 units/角色定义结构身份和至少一个 raw 字段消费链已达到动态证据级别。尚未完成的是
`0xB4` 记录所有字段的语义命名和安全语义写回。

ID 57/58 在 `0x0806D964` 有基础统计特例，但 `0x0806D4A0` 的技能填充仍先按原始
ID×`0xB4` 读取，后续提取器必须保留全部 63 条原始记录。

## 可重复提取器

`tools/extract_character_definitions.py` 已固化该表：

- 输入：`rom/base.gba`；
- 输出：`sequel/content/units/bank.json`；
- 记录数：63；
- stride：`0xB4`；
- 地址公式：`0x54241C + character_id*0xB4`；
- `character_id` 是代码使用的表索引，不是记录内首字节；
- 每条记录保留完整 `raw_hex`，仅暴露 `field_00..field_03` 为保守原始字段。

覆盖测试：`tests/test_extract_character_definitions.py`。
