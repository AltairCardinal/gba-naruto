# 45832C动画候选池：双base用途与旧合同复用

> 后续[完整 caller/flags 批量局部审计](rom-animation-pool-lifecycle-20261001.md)已纠正
> 本文旧位编号及地址笔误：实际是 `0x63244..0x6324C` 的 `flags & 0x8`（bit 3）。
> group 1 与非零 callback 必须保留；序列 sentinel 后的 duration 在循环更新中可能读取，
> 与 descriptor 只读 sentinel head 是两种边界。原永久收据保持原样。

状态：固定两条调用路径的只读预检，未Tier-1、promotion=0。
永久收据`notes/evidence/rom-animation-base-pairs-preflight-20261001-v1/`。
ROM固定1198ece7…9d05b，coverage固定b568db6f…cf06d2；完整SHA在bases-v2.json。
模式仍为固定consumer窗口/指针/解析器身份复用，不另造模型执行路线。

## 本轮确立的复用边界

旧`rom-fixed-animation-descriptor-groups-v1`真实独立CLI重放：verified=true、errors=[]、
descriptor_count=12、历史promotion_bytes=1,136。这些数字只属于旧12D574包，不是新池收益。
allocator626B4..62766、renderer select62924..62A0A、step631F6..63208、advance63238..632BA
四段原字节SHA与旧合同全部一致。新样例可使用同一指针/序列/0x14 entry语法方法，
却不能沿用旧4groups×3records分母或统一0x54 descriptor长度。

| 新callsite | r0描述器表base | r1组表base | group0序列 | 首record | 首descriptor | 条目数 |
| --- | --- | --- | --- | ---: | --- | ---: |
| 06F914 | 45854C | 458558 | 458550 | 0 | 458520 | 2 |
| 071060 | 458510 | 45851C | 458514 | 0 | 4584E4 | 2 |

两序列首记录low halfword=0、duration=1，下一head为FFFF。每个descriptor按0x14步进
得到两条entry，随后word为FFFF0000。**止步证明直接读取的是2B的FFFF head**；后续
2B零以及序列终止字节是否实际读取必须分别证明，不能凭4B外观或物理相邻直接提升。
表中解析是group0/初始slot0假设下的原字节重建，不是完整新消费者合同。

## 下一包还缺什么

1. 新池已有116个LDR形态。批量从固定来源CFG重枚举到626B4的真正r0/r1参数流，
   固定全部候选、排除项与ROM target-limited caller分母；不能只硬编码这两个成功样例。
2. 冻结group、stack arguments和初始化的slot域。07105A令r2=0，071056/071058把8写
   caller SP+C，allocator将该参数参与flags；63244..6324C按mask 0x8（bit 3）决定是否跳过advance。
   这个分支意味着不能直接搬旧“每组访问0..2”的序列消费结论。
3. 06F908写SP+C的值来自r6，窗口没有其完整域；即使r2=0，flags和后续writer仍待查。
   两路径不能合成一个未经证明的统一状态。callback、allocator失败、外部object mutation
   与renderer前的有效对象域必须列为限制或正向证明，不能靠参数名字解决。
4. 只按真实指针与parser stop界定每个record，并逐claim与immutable unknown去重。
   如果一组只用初始slot0，未消费的next-sequence不能随包络晋升。扩展源码需TDD、
   两套原输入重建、ROM/字段/终止符变异、发布/CLI集成及post-promotion稳定重放。

## 对路线的影响

45832C..458794仍值得先做完整producer/参数域合同，因为allocator和descriptor语法
已有可独立复验基础，两个固定样例也符合该语法；但“同一callee”只能复用parser方法，
不能复用全部group/slot生命周期结论。最小闭环应一次处理完整该池固定caller分母，
不再按两个样例各开一个小包或反复审计。随后再评估12EE10 RAM文本链与AI生命周期。

## 验证与历史失败

首次脚本错误使用63238..6327A短窗口比较旧合同63238..632BA的SHA，因此断言失败；
原脚本、空输出、stderr与guard.json保留。修正为完整历史范围后guard-v2 exit0、非降级。
这只是预检窗口修正，不是功能TDD红绿。旧verifier实际通过；最终bases输出两次一致。
研究脚本不产出claims、不修改生产parser或历史artifact；未跑mGBA/完整来源CFG/formal，
未修改ROM、canonical/proof，unknown87,631B保持，未提交。

- [ ] 查看historical-verifier.json → 旧包verified=true，仅旧12records。
- [ ] 查看两row → 4个table base、2个descriptor、每个2entries、FFFF head一致。
- [ ] 对照flags窗口 → 071060的SP+C=8与06F914的未闭合r6分开记录。
- [ ] 下一包先冻结完整caller/group/slot域 → 不以此预检认领整段1,128B。
