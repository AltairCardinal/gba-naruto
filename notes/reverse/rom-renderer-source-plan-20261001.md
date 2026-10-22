# 显示文本候选的来源成本与复用更正

> 后续[六组实际语义重放](rom-renderer-source-replay-20261001.md)全部通过。
> 下文“未重放”描述本记录产生时的状态；新source参数路径仍未验收。

## 模式、输入与实际验证

模式为“固定CFG候选来源的证据身份与raw instruction membership筛选”；复用登记表
固定producer/消费者闭包中的脚本优先方式。输入绑定上一轮union、ROM和canonical SHA。
低成本脚本读取92site的primary claim，验证其ROM区间SHA、完整线性解码和site指令边界，
并核对LDR literal目标对应候选root；各artifact、manifest、verifier源码均按claim身份核验。
这只是已有证据的身份/成员预检，没有重放源CFG语义verifier或证明入口到source路径。

| 来源 | site数量 |
| --- | ---: |
| CFG inventory v2 | 50 |
| CFG inventory v3 | 14 |
| proven roots v6 | 12 |
| proven roots v18 | 12 |
| proven roots v17 | 2 |
| battle controller CFG | 2 |

全部92site有指令类claim，本次无coarse consumer_code_slice owner；证据、manifest、
verifier源码身份不匹配为0。无需为了补source重新做全ROM探索；后续统一绑定六组来源，
在它们各自verifier实际通过后，独立证明source参数到显示桥接的路径。
这些site是冻结候选集，不是新包全ROM消费者已穷尽的证明。

## 更正此前复用建议

前轮因工具名称含renderer，将显示文本与待晋升命令脚本包归为可直接追加的同类delta，
判断不准确。本记录取代这一实现建议，85record/1,053B去重结果不受影响。

`tools/export_rom_renderer_records_delta.py`使用training-record命令脚本parser；独立verifier
调用`verify_rom_fixed_renderer_script_records._parse`及67158解释器参数路径。
待晋升1,668B包的class是fixed_cfg_consumer_renderer_command_script。
本次候选则直接调用66758/667A0，再进入6626C显示字节parser，不经过67158命令解释器。

应直接复用`export_rom_fixed_consumer_text_inventory._renderer_record_end`及对应独立parser，
并创建或最小扩展显示文本专用消费合同。受管CLI发布、immutable precoverage、投影和
稳定receipt能力可共用；命令脚本消费合同及其验收结果不可复用为显示文本证明。
技术边界是不同字节语法和source sink；用户层区别是直接显示文本与解释器控制命令，
错误共用可能截错边界并把非文本认领成文字。既有脚本包保持原样独立可重放。

因此旧1包/1,668B与新候选包不能合计“两个同类包”；2,721B也不能当成同类里程碑收益。
显示文本三池仍可规划为一个同类包，待完整合同/TDD验证后才进入其自身Tier-1队列。
不通过拆池凑4包，不提前执行formal。RAM标签、fixed copy和animation仍在本合同之外。

## 后续最小闭环

冻结六来源的payload、manifest、verifier和各自入口/边界；重放它们的独立语义验证一次，
再检查92site的source CFG/path、参数覆盖、桥接身份以及85记录解析。新增代码严格TDD，
真实managed CLI和post-promotion稳定性有集成测试；不得直接修改历史哈希固定合同。
旧delta框架公共能力若需抽取，必须确保旧包回归不受影响，不做无关重构。

[永久证据](evidence/rom-renderer-source-plan-20261001-v1/)包含source_map.py、两份一致报告及
两个non-degraded exit0 guard，使用同一heavy lock，最大采样RSS约157MiB。
promotion=0；未执行功能TDD/运行时/全量formal。canonical、proof、队列不变，未提交。
