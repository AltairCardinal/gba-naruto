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
  （2026-10-21 交叉确认：逆向侧的原生消费者扫描把 `0x53F298` 独立认定为 43 项
  u16 **单位槽重映射表**（`tools/table_registry.py` 的 `unit_slot_remap`，
  读者 `0x08080B2C`），与本 note 的"旧基址不是角色 ID 表"结论一致；
  `0x54241C` 才是角色定义表，消费者扫描复核到 2 个原生读者。）

---

## 2026-10-21 追加：判据已被证实，表被拆成三张

本轮把上面第 3 条提出的可证伪判据（「若能证明它把读出的 u16 **加到某个基址上**」）
正面做掉了，完整证据见 `notes/evidence/units-offset-table-20261020.md`。

1. **证实**：消费者 `0x08080B2C`（属函数 `0x08080B08`）执行
   `ldrh` 取 `0x53F298 + (入参 & 0xFF) * 2` 的 u16，
   **加上 WRAM `0x0202CA24` 里的 u16**（**运行时**值），
   再 `lsls #0x10 / lsrs #0x10` **掩回 16 位** ⇒ 目标是一个 **64 KB 窗口内的索引**。
   因为基址是运行时量而不是 ROM 常量，「表值 + 常量 = 某个 ROM 地址」并不成立，
   **写回仍然必须限制在原生出现过的取值内** —— 上面那条安全修正是对的，保留。
2. **表被拆开**：旧 bank 的「`0x53F298`，128 字节，`u16[64]`」横跨了**三张表**：
   - `0x53F298`..`0x53F2EE`（**43 项 u16**）= {0..48} 去掉 {14,15,16,17,19,20}
     的一个**排列** —— 这是「单位 id → 内部槽位」的**重映射表**，不是连续 ID 表；
   - `0x53F2EE`..`0x53F30E`（16 项 u16）= 有符号增量表，独立读者 `0x08080AE0`；
   - `0x53F318` 起 = 代码指针表。
3. **附带发现**：`0x53EE98` 是一张此前**完全没被登记**的活表 ——
   3 个原生读者、10 字节步长、15 条记录。提取器 `tools/frame_descriptors.py`
   （自带取值域自检，当场上界写错时立刻报错）。
   它之所以在证据文件里查不到，是因为那份文件只存了 **54 张表**，
   而字面量索引有 **18051** 个值（1196 个是活的）——
   **任何邻域分析都必须查全量索引**，否则候选集会被静默截断。

本轮**没有**改 `sequel/content/units/bank.json`（它仍写着旧的「u16[64]」框架）：
该 bank 与 `tools/populate_bank_json.py` 的生成逻辑同源，要改得一起改，
留给 owner 统一处理。

> **2026-10-21 合并更新**：上面这句已经过时——重制侧已把 `units` 迁移到
> `0x54241C` 角色定义表（63×`0xB4`，`tools/extract_character_definitions.py`
> 生成），本 note 上文的 runtime 证据正是那次迁移的依据。
> `tools/populate_bank_json.py` 也已改为调用同一个提取器，
> `tools/table_registry.py` 里 `units` 已从 `unit_slot_remap` 改指
> `character_definition_table`（`0x54241C`，2 个原生读者）。
> 旧 `0x53F298` 仍是**被禁写的** legacy 基址，安全结论不变。
