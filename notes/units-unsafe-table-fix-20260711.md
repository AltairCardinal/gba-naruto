# Units 旧表语义与危险回写修正（2026-07-11）

## 尝试

利用首战 WASM 样本继续验证 `units` 时，复核了旧文档声称的消费者
`0x0806E654`、ROM 表 `0x0853F298` 及 WRAM 单位槽字段。

## 发现

1. `0x0806E654` 是 `ldrb r1, [unit + 0xC5]`，结合此前已确认的
   `unit + 0xC4`，它读取的是 y/x 坐标并索引 `0x02021E2C` 网格，不是角色 ID。
2. 单位物理 stride 是 `0x1D4`（468）；旧工具所写 234 已被证明错误。
3. ROM 指针 `0x0853F298` 在整份 ROM 中只有一个直接字面量引用，位于
   `0x08080B5C`。实际消费者 `0x08080B2E..0x08080B36` 用输入字节
   `r3 * 2` 索引该 u16 表，再加上 `0x0202CA24` 的基值，所处函数还读取对象
   `+0x90/+0x98`。这更符合渲染/对象偏移查找，而非 battle slot → character ID。
4. 表后半含 `0xFFFC, 0, 0xFFFA, 4, ...` 等有符号偏移，也与连续角色 ID
   语义冲突。

## 安全修正

`generate_unit_patches()` 原先把 editor `units.char_id` 按 row id 写到
`0x53F298 + index*2`，可能破坏渲染或对象定位。按 TDD：

1. 新增 `tests/test_unsafe_unit_patch.py`，首次运行得到 `bytes` patch，按正确原因失败；
2. 最小修改后只产生 `db_unit_unmapped` 诊断，不含 `offset/after_hex`；
3. lossless `rom_units` mirror 仍可保存原始字节；后续已确认真实角色记录映射，但
   legacy units 语义编辑在字段语义和安全序列化完成前仍不得写 ROM。

后续已定位真实角色定义表 `0x54241C`，并通过
`tools/extract_character_definitions.py` 将 `sequel/content/units/bank.json`
迁移为 63×`0xB4` 的 lossless character definition bank。该迁移只恢复了正确 ROM
身份和可重复提取；`generate_unit_patches()` 仍保持 diagnostic-only，因为 editor
`units.char_id/name/hp` 还没有逐字段、可回写的 ROM 记录身份。

## 重要范围与边界

- 代码：`0x0806E64C..0x0806E674`（坐标→网格索引），
  `0x08080B08..0x08080B50`（`0x53F298` 唯一消费者）。
- ROM：`0x53F298`（当前只能称 u16 offset/value lookup，不能称角色 ID 表）。
- WRAM：`0x020240C0 + slot*0x1D4`；坐标字段 `+0xC4/+0xC5`。
- 后续已将 `units` 迁移到 `0x54241C` 真实角色定义表，并通过首战 template→battle
  slot 样本及 `0x5424D1` byte `0x0e→0x0f` A/B 达到结构身份 runtime 证据；本 note
  的安全结论仍成立：旧 `0x53F298` 写回必须保持禁用，legacy 语义字段仍待安全序列化。
