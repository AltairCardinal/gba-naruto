# 458 混合动画池：完整 BL 分母与生命周期局部审计

> 后续整图前驱审计见[caller前驱与共享callee缺口](rom-animation-caller-predecessor-20261001.md)：
> 47条双表在两个模型均重建，剩25字段集中五callee。下文12条局部固定／35项缺口是上包
> 历史分母；新13／22候选带固定图与条件保存边界，不升级成完整自然域证明。

状态：批量研究闭环完成，完整消费者合同仍开放；未新增 Tier-1，promotion=0。
永久收据为 `notes/evidence/rom-animation-pool-lifecycle-20261001-v1/`。
最终参数报告 `audit-final.json`、原始字段事实 `facts-final-v2.json`、来源与探针报告
`validation.json`、最终测试 `final-checks.json`、跨目录复验 `portable-report.json`。
ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

## 方法与复用

沿用固定消费者／双层动画表模式，先使用可复现脚本、参数化 TDD 与统一 heavy lock。
复用 vendored Capstone、独立 raw ARMv4T decoder 和九组已有 CFG verifier；没有子代理。
旧 `rom-fixed-animation-descriptor-groups-v1` 保持原样，不搬用其 4×3 group 域或
0x54 descriptor 长度。新增的是受管实验脚本与证据，不另建生产动画系统。

输入、输出与边界：固定原 ROM、coverage、旧 116 literal 筛选及 source artifact；
从全 ROM 重枚举目标 626B4 的 raw BL 编码，对真实来源指令分区重建局部参数，再用
有限原始指令探针检查 advance/helper 的人工状态。产物是每项 trace、排除理由、
来源独立报告及可重放矩阵；不把形态、局部常量或人工状态升级成自然执行证明。

## 分母与新增发现

- 113 个 raw Thumb BL 形态全部保留。96 项匹配来源指令分区并由九组 CFG 独立重放；
  16 项 primary owner 只是 consumer slice，另 1 项无唯一完整 primary owner，均排除。
- 96 项中，47 条能在局部固定 r0/r1 双表地址和 group：45 条 group 0、2 条 group 1。
  原筛选的 44 条全部保留；新增 `86374`、`88A80`（group 1）和 `8E7F4`（group 0）。
  其余 49 条未满足本次局部固定双表条件，不能据此否认其他逻辑引用。
- 仍为七对 base；12 条同时固定 flags 和 callback，35 条至少一项待完整前驱证明。
  已知非零 callback 是 `0808AA51` 与 `0808EE41`，不能统一假定 callback=0。
- group 1 使用 `45848C+4 → 458484`，record=1、duration=0，描述器为
  `458420..458472`，4 个 0x14 entry 后只计 2B sentinel head。
  两调用的 caller flags 为 0x388，allocator 写入 0x389，callback=0，冻结 mask 已置位。
- 七个 group 0 描述器与这个 group 1 描述器共 8 个、24 个 entry；按 stride 与
  sentinel head 得到 496B 候选范围。它不是 accepted claim，也不是已晋升收益。

## 必须纠正的字段与终止边界

allocator `626B4..62786` 的两次 push 和局部 SP 分配合计 0x28B。
`626CA` 的 `[SP+0x34]` 因此是 caller `SP+0xC` flags；`62728..6272C` 写入
`caller_flags | 1`。`6275E..62760` 把 caller `SP+0x10` 写入 object+0x28 callback。
`62750/62752/62754` 分别初始化 group/slot/timer；slot 和 timer 初始为零。

`63244..6324C` 测试 **mask 0x8，即 bit 3**，不是旧记录里的 bit 8。
callback 在 `62954` 经 interwork dispatcher 调用，发生在描述器选择之前。
`8EE40..8EE56` 的短 callback 条件调用 disable helper `62788`；另一个 callback
`8AA50..8ACC6` 含多条调用与别名对象写入，其完整 effects 尚未签发。

当 next-head 为 FFFF 时，`flags & 0x30` 分为：

| 模式 | 原指令的局部行为 |
| --- | --- |
| 0x00 | 清 active 位，slot 不变，临时序列指针不推进 |
| 0x10 | 置冻结 mask 8，slot 不变；指针推进后冻结检查阻止下一次更新 |
| 0x20 | 重置 slot/timer，临时序列指针推进 4B；下一次循环可读 sentinel 的 duration |
| 0x30 | 调用真实 62798 helper，group/slot/timer 归零，临时指针不推进 |

七个 group 0 序列都是 `00000100 FFFF0000`。在 0x20 模式、counter≥2、初始 timer=0
的人工探针中，第二次更新真实读取 sequence+6 的 2B 零值。
把该 suffix 改为 1 后，会继续尝试读取 sequence+8，探针按冻结边界失败关闭。
所以 **sequence sentinel 的零 suffix 不能一概称未读取**；descriptor sentinel 后
2B suffix 是另一条链路，仍不分类。counter 用 LDRB 读取只给出 byte 上界，未证明
其 producer 域；672 组探针只验证所列人工输入，不穷尽 65,536 timer 或所有高 flags。

## 验证、过程失败与长期重放

19 项测试有红绿证据：局部参数 9 项，advance 原指令探针 10 项。最终重构复验全部
通过；七序列×八种低位模式×四个 counter×三个 timer 的 672 组结果按 trace SHA
再次复现。全 ROM 分母、完整成员／排除分类、group 1、字段 raw opcode 与 496B
候选计算都有实际脚本断言。九组来源 verifier 全部 verified=true、errors=[]。

首次来源 batch 因全部输出重定向而在累计 60s 触发守卫的 output idle-timeout，已
完成的四组报告保留；核对守卫按完整输出行计时后，固定输入验真并恢复其余五组。
恢复运行 45.5s、峰值约 270MiB、非降级、exit0；没有把超时说成 ROM 或 CFG 失败。
首次 shift 测试 fixture 编码有误，按真实编码修正；字段事实脚本两次手工地址假设
被断言拒绝后由 disassembly 修正，失败日志与所有中间结果均保留。

收据内 `replay_receipt.py` 已从 notes 路径执行：19 测试、参数语义、字段事实与 672
trace 全部复现。唯一允许变化的是脚本自身定位路径，其文件 SHA 必须相同；不依赖
原 `build/experiments/` 输入。重放输出必须放在新建且 active 的受管 run，原收据只读。
Python AST、空白检查通过；本轮无 mGBA、自然场景 A/B、硬件或全局 formal 重跑。

## 下一可验收包

1. 在同一 source CFG 上合并 47 个调用的前驱与 allocator 跨调用保留规则，闭合
   35 项 flags/callback 缺口；不得把单条 fallthrough 或 r6 历史常量当作完整域。
2. 固定 interwork dispatch、两类 callback、对象 handle 与外部 critical-field writer
   的边界；不能证明的逻辑别名／callee 保留 opaque，并明确哪些调用能够纳入合同。
3. 同时维护 group 0 与 group 1 的 descriptor/sequence 消费范围，区分两层 sentinel。
   完成独立 exporter/verifier、变异与受管发布集成后才签发同类动画 Tier-1。

pool 后半显示文本／截断复制器另用既有语法合同，不整段认领 1,128B。
canonical/proof/bank-proofs 的 SHA 保持，unknown 87,631B；未提交或 push，Goal active。

### 【功能特性】
- 从本记录进入收据，可查看 113 项分母、47 条固定双表路径及全部排除理由；用于继续逆向。

### 【BUG 修复】
- 位编号记录错误已修正：旧 bit 8／错误地址 → mask 0x8、bit 3、63244..6324C；未改游戏行为。

### 【验收清单】
- [ ] 查看 audit-final 的 summary → 113=96+16+1，47=45+2，原 44 条全部保留。
- [ ] 查看 facts-final-v2 的 group1 → descriptor 458420..458472，caller flags 0x388。
- [ ] 查看 validation 的 examples → mode 0x20、counter2 时包含 sequence+6 的 2B 读取。
- [ ] 查看 portable-report → 19 测试与 672 trace 复现，promotion=0；游戏与正式账本没有变化。
