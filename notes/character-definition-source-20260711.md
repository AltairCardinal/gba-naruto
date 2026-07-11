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
characterId；但 ROM raw record 到模板的字段级转换仍需 PC/LR、watchpoint 或受控
A/B 证明，不能只凭 character ID 一致把 units/角色定义提升为运行时验证。

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
逐字节复制到模板。`0x0806D4A0` 链的 ROM 源地址仍是代码级证据，后续需要在原生
mGBA/LLDB 中捕获 PC/LR/寄存器，或对 `0x5424D0` 做单字段受控 A/B 并观察模板字段
按预期变化。

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
