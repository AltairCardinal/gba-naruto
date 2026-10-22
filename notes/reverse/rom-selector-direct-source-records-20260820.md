# Selector direct source records（2026-08-20）

## 结论

`artifacts/rom-selector-direct-source-records-v1/` 固定并独立复验了
`0x0059F5F0..0x0059F988` 的 46 条、每条 20 字节来源记录，共 920 字节。
该范围来自既有 selector direct producer 的完整 46-row 分母，不是对相邻数据的
启发式扫描。

- ROM SHA-256：`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- manifest SHA-256：`094dbb593b2b8e09849ea795f4a09155598936cd3a1bc0b36e2eda6a413cf789`
- payload SHA-256：`adc03bd5e29e956c208698fedc733e305ea87e519e17dfa405ff813939149430`
- packed bundle SHA-256：`a11475d1eea2ce15968ac2dc52addabcfa59354ccf80b702f922e2af548a4b56`
- record vector SHA-256：`065fca6237d166557a03cf30ddd309f695b825f5c850356a3c736e396d9478db`
- range denominator SHA-256：`a4fb31202d48f65f839217585495c2dc40d29cc63b25ff7a3d5594673056e608`

## 证据链

`tools/export_rom_selector_direct_source_records.py` 与
`tools/verify_rom_selector_direct_source_records.py` 分别重建同一合同；verifier 不
导入 exporter。两者都固定并检查：

- 完整 ROM 中到 direct consumer 的 Thumb BL producer 分母；
- 46 项 source ID／record pointer／slot ID 向量；
- `0x0808B02C..0x0808B03A` 的 Thumb 运算链，并从寄存器系数
  `1 → 4 → 5 → 20 → 19` 推导 19 字节目标文本槽 stride；
- direct consumer 内恰好 6 个到 `0x08066758` 的调用点；
- bridge `0x0806678A → 0x0806626C` 的 parser 调用；
- 46 条记录的范围、原始字节、顺序、bundle 和 exact artifact file set。

独立 verifier 的期望报告为 `verified=true`、`record_count=46`、
`record_bytes=920`。最终相关单测为 12 项，覆盖 source vector、producer loop、
stride、bridge/parser、额外全 ROM BL、篡改、symlink 和 relative-root 失败关闭。

## Coverage 晋升

本批在接入前的 920 字节全部属于 current unknown，因此按 46 个完整 20 字节
range 晋升为 `selector_direct_source_record`，不做切片，也不覆盖既有 primary
claim。正式可复现 coverage 为：

- classified：`6,091,909 / 6,291,456`（`96.8283%`）
- unknown：`199,547`（`3.1717%`）
- claim：`13,783`
- segment：`16,055`
- coverage SHA-256：`d441f702add65e36dce291cfa6e6235e3ee7156cbb7b259ad47255848a581049`
- coverage auditor SHA-256：`46a86a8bbf37695584f44ed38f10a4e871abd2ede011e7270933373c5723845b`

写盘命令会先 build 一次，再在 `audit_manifest()` 中完整 build 第二次；该任务可
连续静默约 20 分钟。首次守卫把 `idle-timeout` 设为 1200 秒，恰在第二次 build
结束前终止，但 JSON 已原子写稳。随后用只读命令重新验证一次，10 分钟 exit 0、
峰值 RSS 385.57 MiB。以后同类 `--write` 应给超过 20 分钟的 idle 上限，或将写盘
与只读复验拆成两个独立受守卫步骤；不能用“无 stdout”判断挂死。

## 边界

本成果只证明固定 46-row 物理记录分母及其消费者关系。除已由 producer 使用的
字段外，不为每条记录 bytes 2..19 赋予字段语义；也不证明自然玩法遍历全部行、
Unicode 含义、编辑／写回安全或可分配空间。范围在 `0x0059F988` 前严格结束，
不包含该字节或相邻 profile 数据，也不把 selector 文本表扩张为 63 槽完整分母。

## 正式证明收据

受守卫 formal audit 实际执行 62 个唯一 verifier；62/62 均 `exit_code=0`、
`contract_ok=true`，ROM byte gate 为 52/52，峰值 RSS 507.49 MiB。报告仍为
`complete=false`、`claim_status=incomplete`、175 个 blocker，这是 unknown 与其他
最终门尚未完成的正确结果。

- report：
  `build/experiments/active/reverse-proof/codex-selector-source-formal-proof-20260820-1250/formal.report.json`
- report SHA-256：`dc15268b5cbff9113d241737529f591bac2836c51104696f49295b266d6e10d5`
- guard SHA-256：`3cb89ec78f6a76e3412abac6c7c425becc18f9af46bd498ea8b11a21c02785d9`
- proof spec SHA-256：`ddde15d20e145a24ed7f63a6bd7d369178642bd4804f84a2ba10ace7e56c0b07`
- formal auditor SHA-256：`4e5b95705a2aa8252da96f927872a6701bb1561b6748230cbc4c209815e28d36`

## 后续增量

本页的 920 字节 coverage 与 62/62 正式收据是 source-record 里程碑当时的历史事实，
不应被后续数字覆盖。随后 `rom-selector-code-windows-v1` 只分类 selector consumer
source windows 中的 current-unknown 交集，没有重复认领这 46×20 字节记录；最新
分母、边界和 63/63 收据见 `notes/rom-selector-code-windows-20260820.md`。
