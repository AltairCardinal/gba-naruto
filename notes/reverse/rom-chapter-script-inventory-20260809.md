# 章节脚本精确字节清单（2026-08-09）

## 结论

固定基准 ROM 的四张章节指针表形成一个可重复、失败关闭的静态控制流闭包：

- primary：`0x08060C74..0x08060D54`，56 项、55 个非空槽；
- alternate：`0x08060D54..0x08060E34`，56 项、55 个非空槽；
- runtime_state：`0x08060E34..0x08060EF0`，47 项、46 个非空槽；
- positions_formation：`0x08060EF0..0x08060FA4`，45 项、44 个非空槽。

四表共 204 个槽、200 个非空槽和 188 个唯一根。独立遍历得到 18,994 个唯一
解释器节点、590 个终止节点、43 种 opcode，解析失败和节点重叠均为 0。节点字节
精确合并为 92 个区间、334,060 字节；区间间 91 个缝隙共 3,769 字节继续保留为
`unknown`。范围分母 SHA-256 为
`351b76c28ab7ead1a1ea086523fb55f2178f2449076fe01a2460efa51ae9d2d2`，顺序 bundle
SHA-256 为 `eba1393714485ab78d0dbde6cb1b9cf407e031ce8c2a86068038a3920d5f0699`。

这批章节脚本本体在当轮把 ROM 语义分类增加到 334,060 字节；随后同一证据链又按
renderer 的实际消费边界接入 49 个 speaker-label、251 字节。当前仓库总覆盖率还包含
其他同期批次，以 `sequel/rom-byte-coverage.json` 为唯一当前口径。

## 根表与解释器绑定

primary/alternate 由 `0x0808F594..0x0808F5D4` 的选择链消费；runtime_state 与
positions_formation 分别由 `0x0808A55C`、`0x0808A5CE` 的 table-base+index
查找消费，随后均调用解释器 `0x080977B8`。后两表只证明固定结构域：runtime_state
没有静态运行时上界保护；positions header 在固定 ROM 中只枚举
`{0,6,8,10,11,12,14}`。因此产物不把静态表槽冒充自然玩法全索引覆盖。

解释器范围为 `0x080977B8..0x08097E34`，其中 `0x080977F4..0x080978DC` 是
58 项 dispatch 表。遍历器按解释器记录协议处理：

- 固定长度 opcode 按 handler 的 cursor 增量推进；
- `0x01`、`0x05`、`0x20` 包含 NUL 终止的 renderer text；
- `0x13` 包含一段或两段 token text；
- `0x06`、`0x07`、`0x0D` 及条件 opcode 跟随 ROM pointer 分支，并按 handler
  语义保留 fallthrough；
- `0x00` 终止当前解释器调用；
- 保留 opcode `0x24..0x31` 显式拒绝。

文本边界绑定 renderer parser `0x0806626C..0x08066736`、token helper
`0x080960F0..0x08096138` 和 31×8 的 SJIS range 表
`0x0853D644..0x0853D73C`。opcode `0x06` 固定出现 42 个节点；它没有运行时索引
上界检查，因此这里只跟随固定记录中的两个指针分支。

## Speaker-label 引用

opcode `0x08` 与 `0x0E` 的 dispatch 都进入 `0x080979E8`。四表节点给出 5,715
次 operand 引用，去重后是 49 个 label ID。handler 按
`0x085A57C4 + id * 12` 取固定槽，再交给 `0x0806626C` renderer。

49 个槽的结构字节共 588 字节，但 renderer 只消费每槽第一个合法 NUL 为止：精确
语义并集为 251 字节，剩余 337 字节 post-NUL padding 保持 unknown。语义范围分母
SHA-256 为 `118e9d300bded69407cfe4fe7a8625654af6532ba5a4da3058ca8542fa5e1779`，
语义内容 SHA-256 为 `07c5281f03633aea88c4b70a4a0f755da92707aa2ab6e1a205a20252f8e78831`。

## 产物与防篡改边界

正式产物 `artifacts/rom-chapter-script-inventory-v1/` 只含三个聚合文件：

- `chapter-script-inventory.json`：四表、逐段 SHA-256、解释器/consumer 证据、
  speaker-label 引用和完整分母；
- `chapter-script-bytes.bin`：92 段按顺序连接的 334,060 字节；
- `manifest.json`：固定 ROM、exporter、verifier、测试及产物哈希。

没有生成 18,994 个小文件。独立 verifier 不导入 exporter，而是重新解析四张根表、
重走全部节点、重建 92 段、bundle 和 speaker-label renderer 边界，并拒绝 ROM、
manifest、范围或实现哈希漂移。

```bash
python3 -m unittest tests.test_export_rom_chapter_script_inventory -v
python3 tools/export_rom_chapter_script_inventory.py --root .
python3 tools/verify_rom_chapter_script_inventory.py --root .
python3 tools/audit_rom_byte_coverage.py --root .
```

## 限制

- `chapter_script_record` 是解释器实际消费的 bytecode、内联编码文本和 pointer
  operand 的记录并集，不代表所有字节都已翻译成自然语言或高层命令名。
- 静态可达性不证明 200 个非空槽都能在自然玩法中进入。
- 3,769 字节内部缝隙、四表之外的字节和 speaker-label 的 337 字节 post-NUL
  padding 继续保持 unknown；后续只能凭新的消费者或结构证据接入。
