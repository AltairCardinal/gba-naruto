# 三个低地址脚本池的固定literal消费预检

后续结果：见[正式Tier-1增量验收](rom-low-script-delta-tier1-20261001.md)。以下accepted0状态为本次预检当时的历史结果；新包仍未Tier-2。

状态：新找到6个固定CFG消费点，两个旧语法完整record候选合计12B；**Tier-1未接受、promotion=0**。
本轮在任务恢复链出现明确未闭合入口后转向已有renderer/parser记录闭包模式，复用两套
已有参数流和语法实现，没有放宽opcode或写第二套parser，没有新增生产功能代码。

## 固定研究分母

ROM SHA1198ece7…59d05b；v2/v3 CFG及其六文件输入由旧独立verifier验真。
研究区间为578C..7554、42AB..542E、CEA..12F0，共13,649B，只作查找分母。
从全部已验证v2/v3 Thumb block重新枚举PC-relative literal值，得到6处命中，均在第二池。
其他两池零命中仅限这个literal/CFG合同，不代表没有其他根、指针表、computed读取或自然使用。
参数流由verifier和exporter各自实现重放，6处均进入67158；不声称全ROMconsumer穷尽。

| literal site | 目标root | 本轮语法结果 |
| --- | --- | --- |
| 79A8A、79B1C | 42B5 | 42B5..42BD，8B，opcodes1,0 |
| 79AD8、79B2E | 42BD | 旧合同不支持opcode2，保持排除 |
| 79AEC、79B42 | 42C2 | 42C2..42C6，4B，opcodes3,4,0 |

两个接受语法的独立root没有重叠；独立training exporter parser和renderer verifier parser
复现同一边界与opcode序列。immutable coverage b568db6f…cf06d2重算未知交集为12B。
42AB..42B5的10B前缀、42BD..42C2的5B间隙以及42C6之后全部不在该候选中。
间隙并不因短或包含零值而成为padding。

观察671DA handler可见opcode2局部加2形态；但这不是旧语法合同已接受它的证明，更不能
由dispatch6与5共享入口便把opcode6当opcode5。该目标必须保留排除，待完整消费合同验证。
本轮两个新候选只用已有冻结的0/1/3/4语法，不依赖新的7/8语法假设或任务槽域。
自然执行、callee/跨帧不变量、可编辑/回写仍不声明。

## 证据、验证与下一步

主枚举经heavy guard成功、exit0、非降级，约11.4s，观测峰值168MiB。
独立sidecar逐site重算PC-relative literal、exporter参数流和training语法，与verifier结果一致；
重算immutable unknown交集为12B。helpers原封不动，输入源码哈希另存。

永久收据：`notes/evidence/rom-low-script-fixed-consumers-preflight-20261001-v1/`，manifest
绑定7文件；原始run已completed。当前报告没有accepted claims，没有改coverage/proof或旧manifest。
本轮共享scheduler工具复用回归2/2通过；本预检只运行只读分析和两套实现重放，没有
宣称新feature的TDD或Tier-1验收。格式、JSON/manifest哈希检查通过。未运行mGBA和formal。

下一完整动作是沿已有固定consumer链建立delta packet：先TDD覆盖六site分母漂移、参数
错误、截断/终止、额外成员和unknown gap保留，再最小exporter、安全发布、独立verifier、
真实CLI/consumer集成和精确12B投影。不能把本预检直接改名为accepted artifact。
单包达标后保持Tier-1待接入，未到4包/10KiB/0.15个百分点门槛不重跑全量formal。
125B五根及其他13,637B研究区仍没有新接受结论；不把12B小包当作大型缺口已解决。

## 可执行验收

- [ ] 查看consumers → 三个池固定，6个消费点全部指向解释器。
- [ ] 查看独立重放 → 两个候选root，范围8B+4B，unknown交集12B，accepted0。
- [ ] 查看42BD两条记录 → unsupported opcode2，未扩展语法或自动接受间隙。
- [ ] 查看canonical → 仍87,631B未知，不混入本轮候选收益。
