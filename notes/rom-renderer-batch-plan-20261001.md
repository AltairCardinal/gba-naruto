# 下一 renderer 文本包的去重分母与验收设计

## 任务模式与结论

模式为“固定候选范围集合的去重、交叠与 immutable 输入身份核对”，使用低成本可复现脚本。
复用已有文本消费调查、显示文本双parser和受管 Tier-1 框架；不另建解析器。
本次输出只是研究分母，不是可直接执行或已经验收的生产合同。

三组候选合并后92个局部调用点、85条记录、1,053B：routes14/14/352B，animation11/11/123B，
ram67/60/578B。85条彼此无重叠、均全范围属于当前unknown，与已有29条/1,668B Tier-1包
也无重叠。因此下一步可按一个信任边界规划单一文本包，不按三池拆成三个代理或重复审计。
RAM标签、固定copy、90A20 wrapper、animation descriptor均不属于本包。

## 输入与复用边界

[来源核对与复用更正](rom-renderer-source-plan-20261001.md)取代前轮直接追加旧delta的建议：
92site属于六组指令类CFG证据，预检身份全部吻合，完整语义验证仍缺。

三份永久研究JSON、已有Tier-1 payload、canonical及proof SHA逐一绑定在union.json中。
完整区间和来源site列表已经冻结；这些site仍是局部预检，不是全ROM producer穷尽分母。
后续必须从已验真上游CFG入口重建source路径与指令边界；coarse consumer_code_slice
不能直接当指令membership。不同上游artifact保留各自身份，最终使用相同renderer消费合同。

直接复用现有显示文本双parser和66758/667A0桥接能力；绑定显示文本专用合同。
旧renderer_records_delta实际上是67158命令脚本合同，不能直接追加这些显示文本；
只复用受管发布和投影公共能力，旧包保持独立可重放。不要改写旧manifest、重复认领已有1,668B或合并异构RAM协议证明。

## 后续红绿验收设计

1. 红：以完整92site来源合同作为输入；对错误入口、跳入指令中部、literal错位、
   BL目标改变、参数被覆盖、桥接或parser身份改变、跨owner路径缺失必须失败关闭。
2. 绿：只补源CFG/参数路径和消费边界，独立raw verifier不能依赖exporter结论。
   文本控制字节截断、缺终止、越界、记录交叠与非unknown投影均有正确原因的失败测试。
3. 重构：复用delta公共验证能力；真实managed CLI、inactive run拒绝及输出篡改集成测试，
   固定immutable precoverage，并连续双重重放稳定报告。验证全部通过才进入Tier-1。

92site或85record如果被独立来源验证否证，应输出逐项排除与原因，不把研究分母硬写成通过分母。
本次不写上述生产测试，也未开始功能实现；只读脚本断言不冒充功能TDD。

## 阶段审计与收益边界

即使新包完全通过，新增仍只是假设1,053B；旧包1,668B与本包合计2,721B只用于调度估算，
不是canonical净增或formal结果；二者语法不同，不能合计两个同类包。
新的显示文本候选尚未满足任何Tier-1验收或Tier-2门槛。
不得人为拆包凑4包，也不得把animation/RAM生命周期证据加入同类计数。
不宣称自然运行、Unicode正确、可编辑安全或工期。发布和有效bank矩阵仍是独立验收主线。

## 证据与验证

[永久receipt](evidence/rom-renderer-batch-plan-20261001-v1/)包含union.py、union.json及双重重放。
同一heavy lock下两次exit0/non-degraded；结果逐字节一致，范围完整投影、无重叠与输入身份
断言通过。源语义verifier、生产单元/集成、运行时及formal未执行。
canonical unknown87,631B、175 blockers、Tier-1队列1包/1,668B不变；未提交或push。
