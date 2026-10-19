# 固定 u8 索引双 u16 lookup overlay

## 状态

2026-08-27 已完成 canonical artifact、TDD 和独立 verifier；尚未接入
`sequel/rom-byte-coverage.json`。因此本文成果预计可在下一次批量 coverage rebuild
中晋升 144 个 current-unknown 字节，但当前正式 coverage 仍是 v11 基线：

- classified：6,119,306 / 6,291,456（97.2637%）
- unknown：172,150
- coverage SHA-256：
  `4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd`

不得在 coverage auditor 正式接线并重建前，把这 144 字节计入全局进度。

## 冻结范围与身份

- 逻辑视图：file `[0x59F560,0x59F960)`，256 cells × 4 bytes = 1,024 bytes。
- cell 编码：little-endian `u16 multiplier` + little-endian `u16 addend`。
- 真实结果：`u16(multiplier_u16 * (count - 1) + addend_u16)`。
- 逻辑 bundle SHA-256：
  `adaa3da39ee951908263186ab1587a95f827b3041b4a59055da9fb54eb7cdf53`。
- current-unknown primary：`[0x59F560,0x59F5F0)`，36 cells / 144 bytes，
  SHA-256 `36799e6ed48b1bb9dfb3b6ed607e114ef6477174ce57f57ad352b8cab0441f60`。
- existing-owner overlap：`[0x59F5F0,0x59F960)`，220 cells / 880 bytes，
  SHA-256 `8e709ff34aa30c2d5f1639513fee9cfabd54e88e726112f5d49e3253549306f1`；
  owner 保持 `selector_direct_source_record` rows 0..43，不重分类。

固定 base literal `0x0859F560` 在全 ROM 恰有三处：

- `0x08078094`，由 `0x08077F34` 的 raw `5749` 加载；
- `0x080898D8`，由 `0x08089868` 的 raw `1b48` 加载；
- `0x08093C6C`，由 `0x08093A26` 的 raw `914a` 加载。

三个 consumer entry 的全 ROM直接 Thumb BL caller 分母分别为：

- `0x08077C90` ← `0x080795D4`, `0x08086B90`；
- `0x0808983C` ← `0x08089464`, `0x08089920`；
- `0x08093818` ← `0x08095E68`。

三者的精确 Thumb entry pointer literal 出现数均为 0。consumer 指令链冻结 `u8`
index、4-byte scale、两个 `u16` 字段加载及最终窄化；特别是：

- `0x08077F4C/0x08077F4E`；
- `0x08089880/0x08089882`；
- `0x08093A42/0x08093A44`。

第二条消费路径的固定分支域为 `[0,21] ∪ {29,62}`；这只证明这些分支类到达
lookup load，不证明自然运行时覆盖全部 256 cells。cell 29 raw `00008eb9`，cell 62
raw `05000000`。

## 产物与验证

- artifact：`artifacts/rom-u8-indexed-u16-pair-lookup-v1/`
- exporter：`tools/export_rom_u8_indexed_u16_pair_lookup.py`
- verifier：`tools/verify_rom_u8_indexed_u16_pair_lookup.py`
- tests：`tests/test_export_rom_u8_indexed_u16_pair_lookup.py`
- manifest SHA-256：
  `926c2df1b1154181b28dcb65369471f87cdb35c986ce9d0c15a942a3e6fef81a`
- payload SHA-256：
  `40d08a678b7e5dcc13afb02f50f6def28787c1a72a245dbaaf2d117efabda90c`

TDD 证据位于
`build/experiments/active/u8-indexed-u16-pair-lookup-v1/`：初始 RED 和 P1 RED 均
`exit_code=1`；最终完整 GREEN 23/23，201.861 秒，峰值 RSS 149.140625 MiB；独立
verifier `exit_code=0`，峰值 RSS 25.4765625 MiB。P1 审查修复了三类问题：遗漏最终
`u16` 截断、相对输出错误地按进程 cwd 解析、accepted receipt 未固定 verifier
reproduction command。

## 边界

本成果不声明独立物理 bank、22/63-entry 物理表、自然全索引可达、computed/RAM/
indirect consumer 穷尽、业务字段单位、cell 62 的玩法必要性或 bug、既有 selector
owner 撤销、编辑/写回/重定位安全、可分配或 free space。
