# 引用文本槽 NUL 后结构零填充

## 结论

`rom-referenced-text-slot-padding-v1` 只分类三个固定引用域中、消费者首个有效 NUL
之后到固定物理槽末尾的全零字节。分母为 133 个互不重叠范围、1,255 字节：

- direct selector：46 段 / 550 字节；
- configured selector：38 段 / 368 字节；
- chapter speaker-label：49 段 / 337 字节。

所有范围在接入前完整属于 `unknown`，不做 current-unknown 切片。combined range
denominator SHA-256 为
`0d565762f2bdfd18a6aa1f8c8cd25da5347da5184fe1c78e37de9c6334259b5a`，按范围顺序
拼接的 1,255 字节 bundle SHA-256 为
`920b0cbd31dee627e4e6f4cd4d7805da10ec58ec47d4be3cb4a2dfc98a3b442b`。

## 证据链

- ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- 正式 artifact：`artifacts/rom-referenced-text-slot-padding-v1/`；
- manifest SHA-256：
  `448da9894e01d750111cc0ea3467f3cbcd3c9f2b41fadf0f1972fc219809f9d3`；
- payload SHA-256：
  `c410b947cac7bdec55b027de98ee4c7dfe1a23fd0dfb076c96bf88cadc613dfa`；
- 独立 verifier：`tools/verify_rom_referenced_text_slot_padding.py`，SHA-256
  `0f206e51b0fc151de7d6c875fe24ca338aa36dc77c963d50b4b59bdb62b40d5b`；
- 来源分别绑定 `rom-selector-text-bindings-v1` 与
  `rom-chapter-script-inventory-v1` 的 manifest、payload 和独立 verifier 身份。

exporter 与 verifier 都从固定 base/stride/引用 ID 重新定位物理槽，从 ROM 独立扫描
首个 NUL，并要求 suffix 的每个字节均为零。verifier 不 import exporter；payload、
bundle 与 manifest 即使一起重算，仍必须与从 passed root 独立重建的期望值完全一致。
exporter 先在同父临时目录生成 candidate，真实执行 hash-bound 独立 verifier 并核对
完整报告，成功后才安装 accepted artifact；相对 root、祖先 symlink、额外成员或 verifier
失败均失败关闭。

## Coverage 接入

`tools/audit_rom_byte_coverage.py` 在初始静态文本 claims 之后、所有 CFG/reuse
current-unknown promotion 之前接入该批。它再次执行独立 verifier，固定 artifact
成员和哈希，并要求 133 个完整范围在接入点全部为 `unknown`。

接入后的正式 coverage：

- classified：6,090,989 / 6,291,456（96.8137%）；
- unknown：200,467（3.1863%）；
- claims：13,737；segments：16,009；
- coverage SHA-256：
  `aebd73ea9bcf2e7eaf87f25301da25293015224ae0c77045c9822eb3c7b1f894`。

正式 proof audit 位于
`build/experiments/active/reverse-proof/codex-text-padding-formal-proof-20260820-0955/formal.report.json`：
61/61 个唯一 verifier 均 `exit_code=0`、`contract_ok=true`，ROM byte gate 为 51/51，
峰值 RSS 446.34 MiB。报告 SHA-256 为
`cac3e4634052391ae91cbc7eb20a41e01af7ebf42d92e89bac9a3673300c134c`，guard SHA-256 为
`02b71cb791676f487d99f4c664eb3d628e99557501fa8f429e84eb5f9640d776`。

## 边界

本成果不分类未引用 selector/speaker 槽，也不分类 NUL 本身或此前的文本前缀；不声称
文本语义、Unicode、自然玩法全记录可达、编辑/写回安全或可安全分配空间。零值只是
固定槽内的结构填充，不能当作 ROM free space。
