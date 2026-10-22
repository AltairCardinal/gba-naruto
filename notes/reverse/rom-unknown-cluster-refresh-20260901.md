# ROM unknown 集群刷新（2026-09-01）

## 输入与模式

- canonical coverage SHA-256：`4e8ab6b090825901ab7b055326e64a6a16343ec95ac33cfe5e0dbe7721eb2440`
- 输入分母：140,020 unknown bytes / 1,422 ranges。
- 任务模式：固定 direct producer 证明的新 Thumb CFG root 与闭包内 consumed-literal
  投影；复用 `AGENTS.md` 已登记的脚本优先、TDD、独立 raw verifier 模式。
- 生成方式：`tools/analyze_rom_unknown_clusters.py` 重聚类，Luna max / Sol medium
  只读筛选，最终合同、实现与验收由 Codex 本体完成。

## 候选裁决

1. `[0x091676,0x091FE0)` 接受精确子集。两个已分类 direct Thumb BL
   `0x08F9E6/0x08F9F0 -> 0x0914D8` 闭合 root producer 分母；完整闭包重建为
   2,217 instructions / 4,840 code bytes / 377 blocks / 15 frontiers。目标本地精确
   晋升 2,092 reachable code bytes + 308 closure-wide consumed literal bytes = 2,400
   bytes。五个 2-byte gaps 共 10 bytes 既不可达也未被完整 word 消费，保持 unknown。
2. `[0x59EAE0,0x59F560)` 全部拒绝，`bytes_promoted=0`。先前十六进制候选起点
   `0x59EC20` 是十进制换算错误。该 112×24-byte 外观的 consumer index 为
   `byte[0x348DAC + state[0x16]] + state[0x19]`；冻结 scenario 50 得到 index=120，
   callback producer 与两个状态字段 writer/inheritance 分母仍开放。详见
   `notes/rom-unknown-candidate-59eae0-negative-evidence-20260827.md`。
3. `[0x0B9BB4,0x0B9E94)` 736-byte 全零区间全部拒绝，`bytes_promoted=0`。任务中的
   `[0x0B9DB4,0x0BA094)` 是另一处坐标错误。左端是字体 source endpoint，右端是
   pointer-reachable LZ77 起点，但相距 `0x2E0`，不满足 align4 或现有 parser-bound
   padding 合同；无内部 pointer 也不能推出全局无消费者、free 或 allocatable。

## 结果与边界

- 正式 artifact：`artifacts/rom-cfg-proven-roots-v17/`；不可变 precoverage：
  `artifacts/rom-cfg-proven-roots-v17-precoverage-v1/`。
- v17 合并代码/literal 为一个 artifact、一个独立 verifier、一次 coverage 调用；这是
  审计去重，不是放宽 producer、CFG、literal、owner 或字节身份合同。
- 接入后 canonical coverage 为 6,153,836 classified / 137,620 unknown / 16,087
  claims / 17,513 segments，SHA-256
  `23eb0ceaf4d38b8cadb74e05ddf8686de454d5e73c433da26073075d1fa71e78`。
- 不声明自然运行时可达、全 ROM 代码/间接目标穷尽、literal 业务含义、alignment
  padding、相邻字节、编辑/写回/重定位安全或 free/allocatable space。

## v18 后续里程碑

- authoritative v17 coverage `23eb0cea...1e78` 上，两个已证明 roots
  `0x0910D0/0x0914D8` 的 target-local 合并包精确分类
  `[0x09106C,0x09163E)` 内 1,386 reachable Thumb code bytes 与 96 consumed-literal
  bytes，合计 1,482 bytes / 17 claims。四个 2-byte 零洞保持 unknown，两个
  `indirect_pc_target` frontier 为 `0x0910CC/0x0914C8`；目标外子树不投影。
- direct producer 分母为四条：`0x091E82/0x091F1C -> 0x0910D0` 与
  `0x08F9E6/0x08F9F0 -> 0x0914D8`。正式 artifact 为
  `artifacts/rom-cfg-proven-roots-v18/`，不可变基线为
  `artifacts/rom-cfg-proven-roots-v18-precoverage-v1/`。
- `[0x063ADC,0x064478)` 的 2,460-byte code-like 候选全部拒绝。其条件闭包虽可解出
  2,436 bytes，但五个 root 依赖 unknown-owner dispatcher；dispatcher 唯一 direct
  producer `0x06109A -> 0x064670` 也位于 unknown，且前置 interwork reset 路径不证明
  返回/fallthrough，因此 accepted promotion 为 0，整段继续 unknown。
- 新 canonical coverage 为 6,155,318 classified / 136,138 unknown / 16,104 claims /
  17,533 segments，即 97.836144765218%；SHA-256 为
  `984eb8ed8ef72691e1b580b00465d24e1762bb5c0604c35fe76db40153fc42e0`。
  v18 继续复用“一个 code+literal artifact、一个独立 verifier、coverage 内执行一次、
  formal 进程内复用 coverage”的简化审计结构，未放宽 raw rebuild 或失败关闭边界。

## continuation + v19 原子依赖里程碑

- `0x061086 BL -> 0x09C56C` 的冻结 interwork callee 已由独立 verifier 证明所有 ARM
  终止路径均 `BX lr`，因此只把 LR 静态 continuation root `0x06108A` 作为新 Thumb
  CFG root；精确晋升 74 code + 20 literal = 94 bytes。不声明 reset 路径或自然可达。
- continuation 内唯一 `0x061092 BL -> 0x065728` 解锁 v19。目标重建为 798
  instructions / 54 blocks，精确晋升 1,600 code + 60 literal = 1,660 bytes；两条
  opaque call 均绑定冻结 v2 Thumb block entry `0x063604`，唯一 frontier 为
  `0x065D98 indirect_pc_target`，六个 2-byte 零洞保持 unknown。
- 两包共享 immutable precoverage `984eb8ed...fc42e0`，通过无环 DAG
  `precoverage -> continuation -> v19` 在 validated overlay 中全部验真后一次性写入。
  coverage 使用一个通用 dependency-packet 投影 helper 去重，但两包仍分别执行独立
  verifier，未伪造中间 coverage 或放宽 owner/hash/overlap/receipt 门。
- canonical coverage 为 6,157,072 classified / 134,384 unknown / 16,124 claims /
  17,557 segments，即 97.86402384440103%；SHA-256
  `b51f322daf9e1b9af453f5423fad590d81eb42ae0440cc76482553a15d574008`。
  formal report/guard SHA-256 为 `f31c5546...fc95` / `73b3d913...89c2`；106/106
  contracts、ROM gate 96/96 通过，complete 仍因 134,384 unknown 与既有 gate 为 false。
- Luna max 产出正确 RED 后长期无实现写入，被终止并由 Codex 本体接管；Sol medium
  只读复核发现共享 CFG 引擎、receipt 可伪造、祖先 symlink 越界、opaque baseline
  未绑定四项 P1。四项均先补 RED 再修复，最终复核无 P0/P1。

## unbound chapter-script tail 与审计依赖修复（2026-09-02）

- 物理 tail vector `[0x060FA4,0x060FAC)` 固定 slots 45/46，分别指向
  `0x05BFDF/0x05C6D3`。独立 parser worklist 闭合
  `[0x05BFDF,0x05C5DC)` 1,533 bytes 与 `[0x05C6D3,0x05CD40)` 1,645 bytes，
  共 128 nodes / 128 directed edges / 0 frontier；连同 8-byte vector 精确晋升
  3,186 bytes / 3 claims。`[0x05C5DC,0x05C5DD)` 与
  `[0x05CD40,0x05CD41)` 保持 unknown；不声明 live consumer、自然可达、编辑、重定位、
  padding 或 free space。
- 初版 verifier 在 replay 时读取 mutable canonical coverage，并要求旧 SHA
  `b51f322d...74008`；coverage 写入自身 claims 后 formal 因 `input identity changed`
  正确失败。这是真实循环依赖，不是 ROM 结论错误。
- 修复后 payload 仅保留 `historical_coverage_reference`，明确本次构建未观察旧文件且
  projection gate 延后；verifier 明示 `current_unknown_checked=false`，coverage auditor
  则在投影前逐 claim 验证 unknown，并把 `current_unknown_verified_by_auditor=true` 写入
  accepted claims。Sol medium v6 canary 未发现剩余 P0/P1。
- authoritative coverage 为 6,160,258 classified / 131,198 unknown / 16,127 claims /
  17,559 segments，即 97.9146639506022%；SHA-256 为
  `3b13c811baf8f8d14af074c9e2dc9057932cfe720ad8e16e06f8f6cd17d09daf`。
  formal report `1f3a392b...ef75` 中 106/106 contracts 全部 contract-ok；整体仍因
  131,198 unknown 与既有发布 gate 保持 incomplete。
- 一次正式 coverage rebuild 在约 8 分钟时因 receipt P1 主动终止并保留实验记录；它是
  本里程碑的无用计算浪费。最终 coverage/formal 分别耗时 29分32秒/38分20秒，非降级。
