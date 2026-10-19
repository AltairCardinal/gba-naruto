# 45832C混合池：116 literal候选的批量调用筛选

> 后续[完整 BL 分母与生命周期局部审计](rom-animation-pool-lifecycle-20261001.md)已从
> 固定来源重建出 47 条局部双表调用：保留本次历史 44 条，新增 2 条 group 1 和 1 条
> group 0。实际冻结位为 mask 0x8（bit 3）；本文的 44/116 仍只代表当时筛选窗口。
> 未覆盖 predecessor、外部 writer 或自然执行，不修改本次原始收据。

状态：只读预检，未Tier-1、promotion=0。永久收据
`notes/evidence/rom-animation-pool-caller-screen-20261001-v1/`。
复用前轮固定literal清单、raw BL目标解码、Capstone和两套renderer parser；没有子代理。
ROM SHA1198ece7…9d05b、coverage SHAb568db6f…cf06d2保持。

## 冻结的筛选分母

116个既有LDR形态全部处理：最多80B且不得跨原canonical owner末尾，逐指令保守跟踪
literal/立即数/shift/精确copy常量；其他写入清除对应寄存器，遇控制分支停止，首BL不
按fallthrough继续。指令源CFG和stack/flags并未独立重建，因此这仍不是参数流验收。

- 114项到首call，2项在control boundary停止。
- 首call到626B4为94项，其余20项到其他callee。
- 44项可在局部得到r0/r1都位于池内、r2=0，对应44个不同callsite和7对base。
- 其余72项的排除理由：48缺局部常量参数、20首callee不同、2不是group0、2控制边界。
  缺参数经常是窗口从r1 literal开始而无法重建此前r0，不能解释为这些caller没有固定base。
- 全ROM按2B对齐raw Thumb BL编码扫描得到指向626B4的113个形态，44个callsite均包含
  在该编码分母；不是所有113个都已证明是指令，也不涵盖B/ARM/indirect/computed入口。

7对base为`458474/45848C`、`4584AC/4584B8`、`4584D4/4584E0`、`458510/45851C`、
`45854C/458558`、`458574/458580`、`45859C/4585A8`。完整site、literal、已知寄存器、
trace及排除理由在callers-v3.json，后续独立verifier必须从来源重新枚举，不能用此成功
site清单直接生成accepted claims。

## 池的性质应改为混合，而非整个动画段

20项不同callee中，7到66758、4到667A0、6到66EFC；另有92E80、68660和9C3EC各1。
11个66758/667A0入口局部r0为池内固定root，复用两套parser的记录终点一致、range互不
重叠，共**123B假设文本**，位于458620之后。6个66EFC路径是截断复制器，继续保持
独立合同要求；不能借renderer parser认领。前半多条animation base路径和后半文本
共享一个unknown segment只是ledger边界，不是同一种记录格式。

这123B可以在来源/数据流合同闭合后与前述352B renderer候选组成同类增量，仍须去重、
逐byte unknown投影和失败关闭；当前合计475B只是规划估计，不计canonical或队列。
动画方向应把7对base的group/slot/flags及共享allocator字段一次性证明，而不是做44个
重复小实验。不同group或未闭合常量路径单列，不能因只有7对字样就称base分母穷尽。

## 下一步实现合同的输入边界

1. 来源raw CFG/producer及完整指令boundary验真，排除coarse owner；44候选只作提示。
2. 对allocator的caller stack args尤其SP+C flags建立完整数据流；mask 0x8（bit 3）的固定frame与
   正常slot advance分开，确认callback/外部writer能否改对象字段。
3. 从group表、slot初始化、descriptor pointer、0x14 step、读取到的FFFF head重建精确
   claim，未消费的终止word后缀不认领。新base不能直接套旧4×3或0x54范围。
4. 文本和动画分别受管Tier-1，TDD/独立raw verifier/CLI发布集成；同类批量达门槛再
   Tier-2，不能把混合池整段或两类证据混在一起凑门槛。

## 验证与边界

最终v3报告两次重放一致，116分母/44+72分类、44call包含于113形态、11文本双parser
一致与无重叠均检查；113raw BL点用Capstone独立复解目标一致。guard非降级、exit0。
首版与v2过程报告保留，分别缺显式排除原因及文本拆分，仅v3作本轮最终研究输出。
没有功能代码变更、功能TDD、新artifact接入、完整来源verifier、mGBA或formal；没有
自然运行、可编辑性或全局producer穷尽声明。canonical/proof不变，unknown87,631B。

- [ ] 查看row_count与排除理由 → 116=44+72，每项都有trace。
- [ ] 查看candidate_base_pairs → 7对去重，不等于113个producer都已证明。
- [ ] 查看renderer_hypotheses → 11条共123B，66EFC未被renderer结果包含。
- [ ] 规划下一批 → 文本同类增量与动画生命周期分别维护，不整段认领1,128B。
