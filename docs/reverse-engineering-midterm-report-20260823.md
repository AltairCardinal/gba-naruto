# ROM 字节级逆向中期报告（2026-08-23 暂停点）

## 1. 当前结论

本 Goal 尚未达到 100%。当前 canonical coverage 为：

| 指标 | Goal 起始基线 | 当前 | 变化 |
| --- | ---: | ---: | ---: |
| classified bytes | 6,078,368 | 6,119,244 | +40,876 |
| classified percent | 96.6131% | 97.2628% | +0.6497 percentage points |
| unknown bytes | 213,088 | 172,212 | -40,876 |
| unknown percent | 3.3869% | 2.7372% | -0.6497 percentage points |
| claim count | — | 14,403 | — |
| segment count | — | 16,492 | — |

当前机器证据：

- coverage：`sequel/rom-byte-coverage.json`，SHA-256
  `c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396`；
- proof spec：`sequel/reverse-engineering-proof.json`，SHA-256
  `75d5e48249a3ee200dd8b741faf2c304e390d74614a25c8a161746300d8017e1`；
- formal report：
  `build/experiments/active/cfg-proven-roots-v10/codex-formal-r1-20260823/formal-report.json`，
  SHA-256 `0d761f8cdc7d21de305af6295d518981a0b6bafb242e5b4e433c83e5a4aeacda`；
- formal guard：SHA-256
  `915828bb3b01d54c7c7802ca482d6416df07ce2702e7531e0ee17186a7f94822`，
  2,592.267 秒，峰值 RSS 615.17578125 MiB，非 degraded；
- 73/73 实际执行的结构化 verifier 均为 `exit_code=0`、`contract_ok=true`；ROM byte
  gate 63/63、bad=0。proof spec 的 gate verifier 配置总数为 74，其中 11 个旧 gate
  verifier 只有哈希绑定；不能把 74 写成实际执行次数；
- 全局 proof 仍为 `complete=false`、`claim_status=incomplete`、175 blockers，这是
  unknown、有效 bank 穷尽、最终七门和仓库外 trust anchor 尚未闭合的正确结果。

## 2. 已完成内容

Goal 创建后的路线图记录了 21 个已闭环 coverage/proof 里程碑。倒数第二项为固定
battle-condition records：

- canonical artifact：`artifacts/rom-battle-condition-records-v1/`；
- 完整物理分母：47 battles × 3 variants × `0x44` bytes，141 variants、1,128
  predicate slots；
- 独立 verifier 绑定 raw interpreter layout、ROM/实现身份、完整 scope 与 23 项
  non-claims；
- coverage 只提升接入前 current-unknown 的 84 个 fragment / 2,772 bytes：41 个
  variant-prefix fragment / 164 bytes，43 个 predicate fragment / 2,608 bytes；
- 既有 fixed-table 与 positions-aux primary owner 不变；
  `[0x00596CCC,0x00596D5C)` 的 144-byte zero gap 继续 unknown；
- artifact、coverage、proof 与 formal audit 均完成 TDD 和独立复核；Sol medium 最终
  review 为 ACCEPT，无 P0/P1/P2。

边界：本里程碑不证明自然 battle/variant 可达、全消费者穷尽、prefix/predicate
业务语义、handler 4/5 自然使用、编辑/写回/重定位或 free/allocatable space。

当前最后一项为已完整闭环的 `0x08B278` CFG proven-roots v10：

- 已冻结全 ROM 3 条直接 BL 分母、source bounded worklist（264 instructions / 35
  blocks / 580 bytes / 26 external call edges / 0 frontier）与 target worklist（36
  instructions / 7 blocks / 72 code bytes / 0 frontier）；
- 两条 PC-relative LDR 独立消费 8 literal bytes，完整 promotion envelope 为
  `[0x08B278,0x08B2C8)` 的 80 个 current-unknown bytes；
- Luna max 完成局部实现后，Sol medium 独立复核发现并拦截了 3 项关键证据链问题：
  verifier 复用 exporter 的 block builder、external-edge vector 只绑定盲常量，以及
  manifest 不符合标准 `git-artifact-promotion-v1` 事务；父代理均先补 RED 再修复；
- 当前 exporter/verifier 共 17/17 定向测试通过；父代理受守卫完整复跑为非 degraded，
  峰值 RSS 182.54 MiB。verifier 已独立重建 source `264/35/580/0/26` 与 target
  `36/7/72/0`，且不再导入任何 `tools.export_rom_cfg*`；
- 标准受管实验已完成 candidate 导出、pre-promotion 独立验证、accepted receipt、
  事务 promotion 与 promoted-copy 独立复验；canonical artifact 位于
  `artifacts/rom-cfg-proven-roots-v10/`。manifest SHA-256 为
  `7bc6a70cb8409b44075df6e1031b9d80bdb19898605735dedd2a2acf9d495991`，payload
  SHA-256 为
  `5edad0689b630e68c6ee304aac2f56e3d5c83e65ee7c2c7a7308e0fd980fd50e`；
- coverage 接入先以缺少 v10 身份常量与 claim builder 的正确 RED 失败，再由最小实现
  转 GREEN；canonical write 与独立 no-write readback 均通过，实际结果为
  `classified=6,119,244`、`unknown=172,212`、`claims=14,403`、`segments=16,492`；
- proof spec 先以旧 coverage 身份产生正确 RED，再加入 v10 独立 verifier、summary
  assertion 与 limitation。54 项 proof 测试全部通过，其中 52 项轻量测试和 2 项深度
  测试分别验收；
- 最终受守卫 formal audit 非降级完成，73/73 唯一结构化 contract 全部通过，ROM byte
  gate 63/63、bad=0。报告仍为 `complete=false`、`claim_status=incomplete`、175
  blockers，正确反映剩余 172,212 unknown bytes、七个最终门和外部 trust anchor。

## 3. 模型消耗

Goal 计量快照（2026-08-23 06:26 左右，暂停前最终口径）：

- aggregate tokens：20,004,570；
- aggregate elapsed：280,646 秒，即 77.957 小时；
- 从本次“从中断处继续”快照到暂停快照：+1,995,652 tokens、+29,353 秒
  （8.154 小时）；
- 这部分包含候选纠错、`0x08B278` 合同冻结、3 轮证据链缺陷的 TDD 修复、标准
  artifact promotion、coverage RED/GREEN、proof RED/GREEN、43 分钟 formal audit、
  文档固化和独立复核，不能全部归为 canonical 字节产出。

当前里程碑使用的模型编排：

- Codex 主代理：高风险合同判断、TDD 修复、coverage/proof 接入、正式验收和文档；
- GPT-5.6 Luna max：可由当前记录确认 2 个冻结公开合同 writer packet，分别负责
  battle-condition 与 CFG v10；CFG v10 通过同一原生代理的受限 follow-up 完成局部
  exporter/verifier 修复及 coverage GREEN；收尾阶段另有 2 个只读 Luna max 小包分别
  复核 formal report 与陈旧文档位置，最终结论仍由父代理复核；
- GPT-5.6 Sol medium：可由当前记录确认至少 6 个独立只读代理，覆盖候选筛选、
  coverage 设计、合同复核和 P0/P1/P2 review；其中 1 个 reviewer 有追加复核 turn。

Goal API 只提供所有模型合计 token，不提供逐模型 token、现金成本或套餐剩余百分比。
因此不能诚实地把 20,004,570 拆分到 Luna、Sol 与主代理，也不能验证账户是否仍高于
5%；任何逐模型 token 或余额百分比都将是编造值。

## 4. 无用浪费量

可由收据确认的硬浪费下限：

1. 首次全 coverage integration 因父代理把 wall timeout 设为 1,200 秒而超时：
   1,200 秒，约 1 个 CPU core，峰值 RSS 355.398 MiB；随后以正确时限一次通过。
2. 一次未受守卫的 atomize 探针在输出保存前结束，结果不可复用：约 32–60 秒，RSS
   约 132 MiB；随后用 1.3 秒线性 endpoint 计算替代。
3. 首次 Luna coverage summary integration 的 900 秒 idle timeout 没有留下可复用
   assertion 结果；父代理随后用正确时限的同一集成测试通过。
4. 一次诊断命令使用了错误的 `xargs` 环境传递语法，约 1.5 秒后立即改正。
5. 收尾时两次错误排除 proof 深度测试，分别被守卫在 300.775 秒与 61.218 秒
   idle timeout 终止；均未写文件。纠正后的 52 项轻量集合在 6.251 秒内一次通过。

合计硬浪费下限为 2,495.5–2,523.5 CPU 秒，即 41.59–42.06 CPU 分钟；占当前 Goal
累计 elapsed 的 0.889%–0.899%。这是可证明的下限，不把正常 RED、独立 verifier
复算、formal audit 的双 coverage 失败关闭验证计为浪费。

首次 35 分钟 proof 全套运行虽然最终因 proof policy 旧数字失败，但它准确暴露了
文档身份漂移，因此不算纯浪费；修正文档后的两项深度测试与正式审计均通过。

`battle-condition-records/codex-r2` 约 1,408 KiB，虽被 r3 取代，但保留了 manifest
fail-open 与动态 import alias 绕过的负证据，因此不算纯废弃空间。逐模型 token 浪费
无法从现有计量器分离，保持 unknown。

本阶段另发现一项可识别但无法从 Goal 收据单独计量的返工：`0x0914D8` 曾被初筛为
422-byte/0-frontier 小 CFG；Sol medium 独立复核按真实 v8/v9 语义重建后，确认它实际为
2,217 instructions / 377 blocks / 4,840 bytes / 165 baseline cross-edges / 15 indirect
frontiers。该错误在编写 v10 代码前被拦截，没有污染 artifact/coverage/proof；其 token
与 wall time 没有逐代理收据，故只登记为“软浪费、数值 unknown”，不混入上述硬下限。

## 5. 剩余时间估算

以 Goal 起始后的 21 个已闭环 coverage/proof 里程碑为样本：

- 净增 40,876 classified bytes，平均 1,946.5 bytes / milestone；
- 77.957 小时 / 21，平均 3.712 小时 / milestone；
- 剩余 172,212 unknown bytes，相当于约 88.47 个同等里程碑，向上取整约 89 个。

按字节吞吐线性估计约 328.4 小时；按向上取整的 89 个里程碑估计约 330.4 小时，即
约 13.8 个 24 小时连续日或 41.3 个 8 小时工作日。剩余区间通常比已完成区间更难；
按 1.5–2.0 难度系数，风险调整后为约 495.6–660.8 小时，即 20.6–27.5 个连续日或
61.9–82.6 个 8 小时工作日。

该估算只针对 `unknown_bytes=0` 的字节级 Goal，不代表有效 bank 全记录/字段、资源与
编辑器 round-trip、mGBA 发布矩阵或实体 GBA 七门全部完成时间。字节收益高度偏斜，
因此任务数和工期只能作为容量规划区间，不能视为承诺日期。

## 6. 暂停与恢复

用户已要求中期报告直接在等待期间完成，并在当前手头任务收尾后暂停。v10 artifact、
coverage、proof 与 formal audit 现已全部完成；没有启动下一候选。Goal API 没有 pause
状态，故机器状态仍显示 `active`，但本线程已经进入实际暂停：收到用户明确恢复指令前
不再启动逆向 writer 或高成本审计。

恢复时必须先重新读取 Goal、`AGENTS.md`、本报告、
`docs/reverse-engineering-handoff-20260812.md`、最新 coverage/proof、Git 状态和套餐
余量。恢复后的第一任务是重新核验 v10 的 coverage/proof/formal 收据，再选择下一
只读候选；可优先考虑 `0x0633C0` 多 producer
小函数（估计 62 bytes）。`0x0914D8` 已被纠正为带 15 个 indirect frontier 的
4,840-byte 高风险候选，不再属于“小型闭合 CFG”优先队列。所有候选仍必须走
RED→GREEN→独立 verifier→coverage→proof→formal audit，不能直接写入 coverage。

## 7. 2026-08-27 恢复后增量附录

用户已明确要求从暂停点继续，Goal 仍为 `active`。v10 之后完成了 CFG proven-roots
v11、u8-indexed u16-pair lookup 和 boot Thumb handoff 三个 artifact 里程碑；按
Goal 起始后的 artifact/coverage 闭环计，样本数从 21 增至 24。当前权威状态为：

| 指标 | 2026-08-23 暂停点 | 当前 | 本次增量 |
| --- | ---: | ---: | ---: |
| classified bytes | 6,119,244 | 6,120,972 | +1,728 |
| classified percent | 97.2628% | 97.2902297974% | +0.0274 percentage points |
| unknown bytes | 172,212 | 170,484 | -1,728 |
| claim count | 14,403 | 14,459 | +56 |
| segment count | 16,492 | 16,568 | +76 |

相对 Goal 起始基线累计净增 42,604 classified bytes，覆盖率累计提升
0.6771723429 percentage points。当前 coverage/proof/formal SHA-256 分别为：

- `9ed94f7cab667383c136b6fdb11132d077329f8f6a67b74871ce32f4038b3529`；
- `ca2afde1b83177f1bf3e503a72c22729070915d7c262bd3b0b96e1c424c7334d`；
- `bc598b5a1f13547e80c35b0b765c9cea0cf89bb4a344a1bd69e04c049cf01eb8`。

正式审计执行 76 个唯一结构化 contract，76/76 均 `exit_code=0`、
`contract_ok=true`；ROM byte gate 66/66。全局仍为 `complete=false`、
`claim_status=incomplete`，这是 170,484 unknown bytes 和其他最终门未闭合的正确状态。

最新 Goal 计量快照：aggregate tokens 22,770,135，aggregate elapsed 308,395 秒
（85.6653 小时）。相对 2026-08-23 暂停快照增加 2,765,565 tokens 和 27,749 秒
（7.7081 小时）。本恢复段可确认已完成 4 个 Luna max 只读/冻结合同 sidecar 与 3 个
Sol medium 只读规划/review sidecar；
主代理负责 promotion 基础设施 TDD、coverage/proof 接入与 formal 验收。Goal API 仍不
提供逐模型 token、现金成本、剩余 token 或套餐余额百分比，因此逐模型消耗和 5% 阈值
继续保持不可验证。

新增可证明的硬浪费下限为约 90.4 CPU 秒：一次守卫外全 atomization 预测约 30 秒且
没有可用输出；一次误启动 proof 单测全集在 60.4 秒后发现其隐式重建 coverage 并被
主动中断。加到旧报告的 2,495.5–2,523.5 秒后，当前硬浪费下限为
2,585.9–2,613.9 CPU 秒，占 aggregate elapsed 的约 0.839%–0.848%。正常 TDD RED、
独立 verifier 复算和 formal audit 内为结构化合同再次执行 coverage 均不计为浪费。

按 24 个已闭环里程碑重新估算：平均 1,775.17 bytes / milestone，平均 3.5694 小时 /
milestone；剩余 170,484 unknown 相当于 96.04 个同等里程碑，向上取整 97 个。线性
字节吞吐估计 342.8 小时，按 97 个里程碑估计 346.2 小时；考虑剩余范围更难，乘
1.5–2.0 风险系数后约 514.2–685.6 小时，即 21.4–28.6 个 24 小时连续日，或
64.3–85.7 个 8 小时工作日。该估算只针对 `unknown_bytes=0`，仍不是其他最终门的
完成承诺。

## 8. 2026-08-27 task scheduler core R4 增量

R4 scheduler artifact、coverage、proof 与 formal audit 已全部闭环，样本数从 24 增至
25。相对上一附录净增 308 classified bytes；相对 2026-08-23 暂停点累计净增 2,036
bytes；相对 Goal 起始基线累计净增 42,912 bytes。当前权威指标为：

| 指标 | 上一附录 | 当前 | R4 增量 |
| --- | ---: | ---: | ---: |
| classified bytes | 6,120,972 | 6,121,280 | +308 |
| classified percent | 97.2902297974% | 97.2951253255% | +0.0048955281 percentage points |
| unknown bytes | 170,484 | 170,176 | -308 |
| claim count | 14,459 | 14,466 | +7 |
| segment count | 16,568 | 16,577 | +9 |

coverage/proof/formal report/formal guard SHA-256 分别为
`5c3c9bcaa90a4d55a2de5ef37effbd9947502aff75f01b73738b90aa704b0d9f`、
`6fd1fc01e7e52d44510ba66f7d83c5ef64f2d07b27a30554047e87929db955e5`、
`d975366d63c35c6a62f4e41d9199014828e689273d2d882f43188df519477c9e`、
`e2ae0a75f524e70634b1a318d719e26c6591b4d789d995fb2bb839dd6d34ddc3`。
正式审计 77/77 唯一结构化 contract 与 67/67 ROM byte gate 全部通过，bad=0；
`complete=false`、`claim_status=incomplete`、175 blockers 仍是正确结论。

最新 Goal 快照为 aggregate tokens 24,669,323、aggregate elapsed 330,787 秒
（91.8853 小时）。相对上一附录增加 1,899,188 tokens 与 22,392 秒（6.2200 小时）。
当前代理收据至少可确认 1 个 Luna max 只读 R4 proof/summary 映射复核，以及 2 个 Sol
medium 只读复核（scheduler 排序/coverage 与下一候选筛选）；主代理负责 R4 promotion、
TDD、coverage/proof 与 48 分 11.251 秒 formal audit。Goal API 仍只提供所有模型合计，
不能拆分逐模型 token/现金成本，也不提供套餐余额百分比；5% 阈值继续不可验证。

本增量新增的硬浪费下限为 339.7–344.7 CPU 秒：一次 143.15 秒无可用日志的 R4
回归、一次约 91.5 秒在 reviewer 发现旧 R3 排序缺陷后被终止的过期运行、约 45 秒在
已知 policy 失败后继续的 proof 深度扫描，以及至少约 60 秒可由后续 formal audit
覆盖的重复第二深度扫描；三次二进制 `rg` 误用和一次不存在的反汇编工具探测只计入
上界约 5 秒。加到上一附录后，累计硬浪费下限为 2,925.6–2,958.6 CPU 秒，占当前
aggregate elapsed 的 0.8844%–0.8944%。正常 RED、独立 verifier 重建、R4 coverage
write 和正式审计均产生可复用证据，不计为浪费；逐模型 token 浪费仍为 unknown。

按 25 个已闭环里程碑重新估算：平均 1,716.48 bytes / milestone，平均 3.6754 小时 /
milestone；剩余 170,176 unknown 相当于 99.14 个同等里程碑，向上取整为 100 个。
线性字节吞吐约 364.4 小时，按 100 个里程碑约 367.5 小时；考虑尾部范围更难，
1.5–2.0 风险系数给出 546.6–735.1 小时，即 22.8–30.6 个连续日或 68.3–91.9 个
8 小时工作日。该估算只针对 `unknown_bytes=0`，不是剩余全局 gate 的承诺日期。
