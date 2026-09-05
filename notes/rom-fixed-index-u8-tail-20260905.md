# Fixed-index u8 tail Tier-1 packet（2026-09-05）

## 任务模式与复用判断

本包归类为“固定 table-base、窄索引、确定宽度 load 的小型物理表投影”。直接复用
`rom-bounded-index-u16-pair-table-v1` 的 TDD、raw consumer 绑定、独立 verifier、
canonical JSON 和 atomic no-replace 发布模式；无需抽取新的公共框架。新证据追加到既有
`0x0853E424 + u8(r0)` lookup 链，只新增此前为 unknown 的四字节尾部，不重分类已有
consumer、literal 或 caller owner。

## 固定输入与结论

- ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- coverage baseline 由 immutable
  `artifacts/rom-post-story-dependency-precoverage-v1` 重放；解压后原始路径仍为
  `sequel/rom-byte-coverage.json`，SHA-256
  `2cc07bc74d24276b994219900ad7419787f9b8832dd62a66bb7839d09df42c01`。
  snapshot manifest / gzip SHA-256 为 `95cb2fef...e65a` / `88365f67...a6b6`；
  exporter/verifier 均不读取 live coverage。
- consumer `[0x07C724,0x07C7B2)` 固定 SHA-256
  `30db564e71b99a0b9b28c2736aa4c5903f46f62be3f38a37fe7ec9ebe512025e`；
  `[0x07C728,0x07C734)` 原始指令证明先把 `r0` 截断为 u8，再从唯一
  `0x0853E424` literal 加 index 并执行单字节 `LDRB`。
- 全 ROM 对 literal word 的逐字节扫描仅命中 `0x07C7B8`；对其 Thumb
  PC-relative literal-LDR 的逐半字扫描仅命中 `0x07C72E`。
- 全 ROM target-limited Thumb BL 扫描重建到 `0x0807C724` 的完整有序 13 条分母。
  其中 `0x07EB14`、`0x07EBBC`、`0x07EC6E`、`0x07EC90` 紧邻固定
  `MOVS r0,#0x6E..#0x71`，对应 `[0x53E492,0x53E496)` 的 `2b 2c 36 3f`。
  其余九条 caller 没有被上述四个 immediate window 证明，统一记为
  `excluded_non_fixed`；本包不判断其 index provenance，也不产生 promotion。
- Tier-1 projection 仅为 1 claim / 4 bytes；candidate 在绑定的 current coverage
  中完整为 unknown，consumer、literal 和四个 caller window 保持原 owner。

## TDD 与验证

- 初始 RED：`build/experiments/active/fixed-index-u8-tail-20260905/red.log`，因三个产品
  模块缺失而失败，原样保留。
- CLI wiring 补充 RED：`cli-red.log`，直接执行 exporter 时因缺少仓库根 import path
  而失败；加入定向集成测试后最小修复，`cli-green.log` 通过。
- 初始实现 GREEN：
  `python3 -m unittest tests.test_export_rom_fixed_index_u8_tail -v`，11/11 通过；日志为
  `green.log`。
- 独立验证：
  `python3 tools/verify_rom_fixed_index_u8_tail.py --root . --artifact artifacts/rom-fixed-index-u8-tail-v1`
  返回 `verified=true`、`contract_ok=true`、13 callers / 4 fixed / 9 excluded non-fixed、
  1 claim / 4 bytes。
- verifier 不导入 exporter；双方分别执行 raw BL、literal word 与 literal-LDR 扫描。
  测试覆盖范围/顺序、代表性单字节 ROM 篡改、payload/manifest/额外成员篡改、symlink、
  coverage identity/current-unknown/owner 以及 atomic no-replace。

## 产物身份

- manifest SHA-256：
  `4e8bbe70226849ce64a5e892bfbbcea88465e45528a61ec588c0ebadd724fa88`
- payload SHA-256：
  `25c49e182f4e08366afcc4326c21488ae6d5657ff64fcfc37e946ed7d1d42666`
- verifier SHA-256：
  `ab5ee9ab06ec8c2f41a3cbae0466f31a176ec512e24e8066f20b2548daf9a11f`

## 父级复核加固

Sol medium 只读 review 发现三个 P1，随后均先增加失败测试再最小修复：九个非固定
caller 改为 `excluded_non_fixed`，不再把未证明的 index provenance 称作 dynamic；
coverage gate 改为逐 segment 无缝覆盖整个 owner range；输出在任何建目录前拒绝 `..`
路径穿越。三项定向 RED 均因正确原因失败，GREEN 后父代理通过同一 heavy lock 受守卫
复跑 13/13，随后补 immutable replay RED/GREEN；precoverage + packet 联合 16/16、
Tier-1 3/3，guard 均非降级，峰值分别 289.05078125 / 293.6953125 MiB。正式 artifact
已按最终实现与测试身份重新生成，独立 verifier 返回 `verified=true` / `contract_ok=true`；父级报告为
`build/experiments/active/fixed-index-u8-tail-20260905/parent-verifier-report.json`。

## 边界

本包不声明完整 114-byte 逻辑表、九条动态 caller 的索引域、自然运行时可达性、业务
字段或数值语义、编辑/写回/重定位安全，亦不声明 free/allocatable space。4 bytes 仍是
Tier-1 projection，尚未写入 canonical coverage，也未执行 Tier-2 coverage/proof/formal。
