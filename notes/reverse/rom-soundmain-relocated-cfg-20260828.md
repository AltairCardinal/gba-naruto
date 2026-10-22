# SoundMain relocated mixed-ISA 与边界 gap 证据（2026-08-28）

## 结论

`rom-soundmain-relocated-cfg-v1` 已按固定 CpuSet 搬运合同闭合 ROM source
`[0x099E10,0x09A1B4)` 中可证明的 924 字节：916 字节 mixed ARM/Thumb 指令和
8 字节实际消费 literal。随后独立 boundary verifier 又只分类 source artifact 明确
跳过的三个 2-byte align4 gap，共 6 字节。累计净晋升 930 字节。

这不是“整个 1,024-byte CpuSet 窗口都是代码”的证明。`[0x09A1AE,0x09A1B0)`
两字节 return veneer 保留既有 boot-handoff owner，只作 opaque-stop provenance；
三个 gap 也不称为指令、NOP、padding、reserved/free/allocatable space。

## 冻结边界

- ROM source envelope：`[0x099E10,0x09A1AE)`，926 字节；
- IWRAM runtime root：`0x030077C8`；
- CpuSet copy window：`[0x099E10,0x09A210)`，1,024 字节；
- code：
  - `[0x099E10,0x099E1A)`；
  - `[0x099E1C,0x099EC2)`；
  - `[0x099EC8,0x099FA6)`；
  - `[0x099FA8,0x09A1AE)`；
- consumed literals：`[0x099EC4,0x099EC8)`、`[0x09A1B0,0x09A1B4)`；
- additive alignment gaps：
  - `[0x099E1A,0x099E1C)`；
  - `[0x099EC2,0x099EC4)`；
  - `[0x099FA6,0x099FA8)`；
- preowned return veneer：`[0x09A1AE,0x09A1B0)`。

core artifact 独立重建 315 条指令、73 个 block、四次 ARM/Thumb 模式切换、一个
opaque return、0 unresolved target frontier。alignment-gap verifier 绑定 core
manifest/payload/verifier/test 的 canonical 大小与 SHA、三组左右边界、raw ROM、
`gap_end == align4(left_owner_end)` 以及 live coverage whole-range unknown。

## TDD 与信任边界加固

初版 gap verifier 的 7 项测试通过后，Sol medium 只读复核发现两个 P1：嵌套 payload
漂移可能沿用旧 receipt，以及 wrapper 路径在校验后仍存在重新打开的 TOCTOU。新增两项
利用测试先确认 RED，再以 canonical payload/manifest 大小与 SHA、精确 literal ranges/
bindings，以及“执行已哈希 wrapper bytes 的 stdin 副本”修复；最终 9/9 通过，复核无
P0/P1。

alignment-gap verifier / test SHA-256：

- verifier：`0ae3c5c6f2a4d2315cd3f5b10f422faa2babfafe220d8b12069f510a6badc00a`；
- test：`220e3e3ecdda28cf7675952e0823aba8baefcaea6663ec36333120353c8155d5`；
- canonical compact report：
  `95b54d511b064b652c50b5b34519ae6bc887a41e60c0321aa56fc9cc4a059b5f`；
- range vector：`80e7409ef3fd737361faa6a08ae8e2efbedd9891c31e4f4b98392a3ad91da3af`；
- packed gap bytes：`b0f66adc83641586656866813fd9dd0b8ebb63796075661ba45d1aa8089e1d44`。

## Coverage 与正式审计

canonical coverage：

- classified：6,123,419（97.3291%）；
- unknown：168,037（2.6709%）；
- claims：14,493；
- segments：16,600；
- coverage SHA-256：
  `31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563`；
- coverage auditor SHA-256：
  `7cd79b584b8ae43706c97df4c3604d4fcf344288c95052bda7072e7e0ff9a3d4`。

正式报告位于
`build/experiments/active/soundmain-relocated-alignment-gap-proof/codex-r1-20260828/formal-report.json`：

- report SHA-256：
  `d2e265e4c7ddc3148eeaa877772246a4944b53f1bfc75c8c97fc99ca5826f8b1`；
- guard SHA-256：
  `edf30aa3feb13ba7500973c2ecad10a2f7f2c3bfb9c1f47d6f3d4d6d5c48c084`；
- proof spec SHA-256：
  `c8e18ab374b96962d4b1a65d44bd4a0de85dece8d71e6906f39e0143d9a84604`；
- formal auditor SHA-256：
  `1562de7b02fc781b79ede13a29a03137a02082ff2aa59b3ec212b90ae797104b`；
- 84/84 唯一结构化 contract 全部 `exit_code=0`、`contract_ok=true`；其中
  ROM byte gate 74/74、bank contract 10/10、bad=0；
- proof spec 的哈希绑定 gate 配置总数为 85，不能写成 85 次实际执行；
- 2,866.934973 秒，峰值 RSS 597.23046875 MiB，非降级；
- `complete=false`、`claim_status=incomplete`、175 blockers，符合仍有
  168,037 unknown bytes 的事实。

## 明确不声明

不声明动态 IWRAM 内容、自然运行时可达、全局 caller/code/indirect/computed producer
穷尽、音频业务行为、compiler authorship、编辑、写回、重定位或 free/allocatable
space。后续包不得借本证据扩张 1,024-byte copy window 或把三个 gap 重命名为代码。
