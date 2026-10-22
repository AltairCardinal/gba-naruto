# 下一显示文本合同的局部路径规模

## 模式与方法

复用固定来源消费者预检的脚本优先方式，输入为三份已封存局部trace、union及source map。
逐项重新比对ROM原字节、连续指令地址、唯一末尾BL和整个路径的已有instruction claim范围。
只整理已有Capstone预检结果及身份，不新增独立参数语义证明，不重跑六来源verifier。

## 冻结的研究分母

92site的局部路径共559次指令出现，不是全局去重指令分母：
ldr96、movs231、str71、adds64、mov5、BL92。
路径长度4/5/6/7条分别17/4/26/45条；最长7条，全部首LDR起、唯一末尾BL止。
75条直接调用66758、17条调用667A0；每条路径均完整位于自身已分类instruction claim内。
ROM字节全部与原trace一致。候选85record/1,053B不变。

## 实现成本判断与复用边界

局部参数证明不需要通用符号执行、动态快照或扩大CFG探索。后续raw verifier只需覆盖
这批指令实际使用的Thumb编码子集，明确寄存器写入效果，证明初始固定r0未被改写，
且BL目标为对应bridge。写SP偏移的STR不写r0，但不能凭mnemonic推断所有store编码；
必须按raw encoding区分store/load、低/高寄存器及目的寄存器。遇未支持编码失败关闭。
已有双parser与66758/667A0桥接证据保留独立消费合同，不能沿用67158命令脚本解释器。
六来源CFG已有真实语义receipt，可一次绑定，避免为每个site重复全图验证。

最小TDD验收至少覆盖：r0被mov/ldr/add改写、store变load、BL目标改动、提前BL/分支、
未知opcode、路径超出owner/跳入指令中部、错literal目标、bridge/parser身份变化、
缺终止/控制字节截断/record overlap，以及managed CLI发布和immutable投影集成。
这只是下一步测试设计，当前未实现这些功能或宣称测试通过。

局部路径简单不意味着所有ROM消费者已穷尽，也不证明上游自然运行或文本可编辑安全。
将来的合同分母必须明确绑定冻结候选集和来源，不使用全ROM完成措辞。

## 验证及证据

[永久receipt](evidence/rom-renderer-flow-cost-20261001-v1/)有cost.py、原报告、逐字节一致
重放及同heavy lock的两个exit0/non-degraded guard。快速采样RSS不能代表准确进程峰值。
未执行功能TDD/集成/运行时/formal；promotion=0，canonical/proof/现有Tier-1队列不变。
本研究范围内的下一包执行方案已具体化，不以耗尽3个百分点为目标；未提交或push。
