# Selector consumer source windows（2026-08-20）

## 结论

`artifacts/rom-selector-code-windows-v1/` 固定并独立复验了 selector 数据流上的
10 个完整 consumer source window，共 2,754 字节。coverage 只将其中仍为
current unknown 的 19 个不重叠区间、1,252 字节提升为 `consumer_code_slice`；
其余 1,502 个已有 primary claim 字节保持原 owner，不重复认领。

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- manifest SHA-256：`bb3f2588ad22567190c1084a12eca42a1615091bc335fe45788d2556299ba6c0`
- payload SHA-256：`23b830dc19248b3192198757da6e41624f804e78a5ee4e10764c8702947ca39b`
- verifier SHA-256：`e9d8ea4cbe5aec14359b5c8ba74ac3e8182f0441a3014d3f760196242601665b`
- source range denominator：`c45e828631f019ea506b0b24a0efeb16ed8508377277bc27936e8a8932fa8d43`
- promotion range denominator：`1a1e50479424dbd441bc81adeca3c7d9075dc1a8ca13869e94693a71e702563e`
- full bundle：`4c1d5865350a66b57db7b483f68c6bf97e9c88fcd5372f021358d4ad8c917523`
- promotion bundle：`2207f28f0e2635b7cff09660d4440d5f8c926017583d210b748a34ac2639672b`

## 固定分母

10 个 window 由上游 selector artifact、ROM 原始字节和消费者合同共同确定：

| window | ROM file offset 半开区间 | 字节 |
| --- | --- | ---: |
| renderer-parser | `0x06626C..0x066736` | 1,226 |
| renderer-bridge | `0x066758..0x066790` | 56 |
| enumerator | `0x08A6AC..0x08A700` | 84 |
| direct-text-consumer | `0x08AFE0..0x08B07C` | 156 |
| menu-selector | `0x08B2C8..0x08B580` | 696 |
| lifecycle | `0x08B58C..0x08B65A` | 206 |
| three-way-mapper | `0x08CC80..0x08CCB4` | 52 |
| configured-text-consumer | `0x08CD5A..0x08CDF8` | 158 |
| three-way-producer | `0x097C6C..0x097C98` | 44 |
| copy-parser | `0x09C4DC..0x09C528` | 76 |

promotion 分母固定为 19 段、1,252 字节。bridge 与 mapper 的 promotion count
均为 0；它们完整冻结为来源证据，但已有更具体 primary 分类，因此不重复晋升。

## 失败关闭

exporter 与不导入 exporter 的独立 verifier 分别重建同一合同，并固定：

- 两份上游 selector artifact、ROM、覆盖基线和实现身份；
- 完整 10-window 分母、字节顺序、source/full bundle 与 promotion bundle；
- current-primary ownership：promotion 只允许来自 `unknown` 或本 batch 的同范围 owner；
- segment class、claim class/range、反向 ownership 与无 dangling batch claim；
- 动态重算的 `consumer_code_slice` 字节数和 claim 数；
- artifact 的精确文件集合、路径与 symlink 防护。

任何窗口、owner、range、summary、bundle、上游证据或实现身份漂移都会失败。artifact
中的 coverage SHA 只是冻结生成时基线，不作为后续 live coverage 的自引用输入；live
晋升始终从传入的先行 claims 重新计算 current-unknown 交集。

## Coverage 与边界

接入后的正式 coverage：

- classified：`6,093,161 / 6,291,456`（`96.8482%`）
- unknown：`198,295`（`3.1518%`）
- claim：`13,802`
- segment：`16,066`
- coverage SHA-256：`5cee1d349689bf735e3517662f9142fbac5dd421dbf8c107ea6219ee6801a8b8`
- coverage auditor SHA-256：`5cefcc73df537785a51d3c6bb1a30de17e206c43ff514930cabd0ef5b179f954`

本成果是 consumer-bounded source-window 分类，不是全局 CFG 或函数图；不声明每个
字节都是指令、自然玩法会到达全部路径、全局 caller 已穷尽，也不声明安全编辑、
重定位、可分配/free-space 状态或新字段语义。

## 正式证明收据

受守卫 formal audit 实际执行 63 个唯一 verifier；63/63 均 `exit_code=0`、
`contract_ok=true`，ROM byte gate 为 53/53，峰值 RSS 508.91 MiB。报告仍为
`complete=false`、`claim_status=incomplete`、175 个 blocker，这是 198,295 个
unknown 字节及其他全局门尚未完成的正确结果。

- report：
  `build/experiments/active/reverse-proof/codex-selector-code-formal-proof-20260820-1649/formal.report.json`
- report SHA-256：`6b8b7632f3957184ee539fa02c1951fc9fb7d88a19c15fb07411b513991b6473`
- guard SHA-256：`3b676d12e65bb24d56ddc203348fe139ebe94c348fb47655150d40bb53246b20`
- proof spec SHA-256：`8df1b5f891bafa51b6f41c424a0c0302a93a4e511aa4f07e7c216ccf4cb87f77`
- formal auditor SHA-256：`4e5b95705a2aa8252da96f927872a6701bb1561b6748230cbc4c209815e28d36`

