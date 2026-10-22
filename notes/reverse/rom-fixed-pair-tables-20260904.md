# ROM fixed pair tables（2026-09-04）

## 结论

`rom-fixed-pair-tables-v1` 精确分类两个相邻、consumer-bound 的固定表：

- `[0x53E00A,0x53E014)`：5 个 signed-u16，完整消费偏移为
  `0,2,4,6,8`；
- `[0x53E014,0x53E034)`：8×4-byte records，每条为两个 u16，consumer
  以 unsigned `&7` 限定索引、`<<2` 形成 4-byte stride，并读取偏移 `0/2`。

净晋升 42 bytes / 2 claims。左侧 `[0x53DFBF,0x53E00A)` 与右侧
`[0x53E034,0x53E496)` 保持 unknown；不得外推自然运行时可达、业务字段含义、
computed/indirect consumer 穷尽、padding/free space 或编辑/写回/重定位安全。

## 证据

- artifact：`artifacts/rom-fixed-pair-tables-v1/`
- payload SHA-256：
  `dae6a76120eed784f528469ef6d565ad8a4f70bd78e3521c90ebdd33cf9e98dc`
- manifest SHA-256：
  `3a704a55d005496ad9c534108bc86fe8e6e6c07ab4c0e021afd8f264943d4d9f`
- verifier SHA-256：
  `7f2b03ae46478ffaacc049902a3223e0a070aeb582ca79306d410d96f0d29225`
- 9/9 packet tests、独立 verifier、原子 no-replace、member/ancestor symlink、
  manifest/payload/consumer mutation、`..` traversal 与输出范围 guard 均通过。

Luna max 只留下初始 RED，约 9 分钟无新增实现或 blocker 后被中止；Terra medium
完成初版 exporter/verifier，Codex 本体补齐 accepted promotion receipt、精确 claims、
路径安全、原子发布和结构化 verifier 报告后正式提升；R2 又关闭
`build/experiments/../...` traversal。旧 staged/R1 候选保留在实验与
`build/experiments/superseded/`，不得作为正式证据引用。

## 分层审计状态

该包与 `rom-v17-v18-helper-cfg-v1` 合并后的历史 Tier-1 overlay 为：

- classified：6,195,412
- unknown：96,044
- 字节语义覆盖率：98.47342173258463%
- 相对 authoritative canonical 净增：1,296 bytes / 16 claims / 2 packets

这只是入队时的历史状态。2026-09-05 scene source 成为第四包后，四包已统一通过
Tier-2 接入；当前 canonical 为 6,198,347 classified / 93,109 unknown /
98.52007230122885%，SHA-256 为
`b14d1778bc9961356cca7f319c9d2ae85a07a6811276f9ee0cd1bc2070e96b82`。

Tier-1 current-unknown gate 已从反复全 ROM atomization 改为等价的线性 primary-range
交叠检查；新包同组 5 项测试由 215.686 秒降至 55.812 秒（约减少 74%），仍失败关闭
拒绝重复 ID、非法 role/range、既有 primary 冲突和目标重叠。
