# AI planner 前后渲染脚本依赖（2026-09-30）

状态：复用既有解析与两个已证明指令窗口的参数流，promotion=0。
输入与边界继承`notes/rom-ai-entry-local-domains-20260930.md`；不追加完整生命周期结论。
实验沿用固定少量消费者窗口的低成本脚本预检模式，不调用模型子代理。

## 修正假设与直接复用

原恢复计划将67158暂称“状态切换函数”；本次原始窗口与已提交training/fixed-renderer
成果确认它是渲染命令解释器。这只是调查假设修正，不能反向声明callee没有单位或
异步副作用。interpreter入口67158的已验收CFG owner与6717C消费literal，连同
`verify_rom_training_text_script_inventory.py`的interpreter范围/dispatch，均可复用。

- 主路径74210加载r2 literal74294=`0800175D`，74252复制给r0，74254调用67158。
- 次路径74304加载r2 literal74384=`0800175D`，74346复制给r0，74348调用67158。
- 两段均属于battle-controller instruction-only primary owner；复用原始
  `verify_rom_fixed_renderer_script_records._prove_parameter_flow`在条件分支/循环中
  重放r0 sink，未另建taint/decoder。输出重复两次逐字节一致。
- pre script175D..177D共32B，独立原始parser重放opcode `[1,5,4,0]`；post
  script177D..1781共4B，opcode `[3,4,0]`。它们已由fixed-renderer artifact分类，
  不追加字节，不把新caller加入旧artifact的冻结41-site分母。
- artifact SHA `7b56a9a05d8ea7d78bddd68dba874f0c7cae2ae3fa5d1aa6c2ab3a3949ec7698`，
  原verifier SHA `c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927`。
  record内容hash、现有owner、ROM身份、两个已证明literal到r0的流均在重放中核对。

永久证据：`notes/evidence/rom-ai-renderer-script-dependencies-20260930-v1/`。
可重放命令（stdout另存新文件，不覆盖原收据）：

```sh
python3 notes/evidence/rom-ai-renderer-script-dependencies-20260930-v1/replay_script_dependencies.py .
```

## 首次失败与新CFG依赖

首次脚本尝试同时检查postplanner literal sites7425E、74352，找不到完整instruction
owner而失败。失败脚本、原因JSON与空的首次stdout保留；修正后将两点明确excluded，
没有用consumer slice或能解码的ROM原字节补充membership。

真实canonical在7425E..7428A及74352..74378均unknown。两个v2直接BL producer
7425A/7434E已分类，battle-controller artifact则在74258/7434C之后以
`frozen_baseline_entry` opaque fallthrough止于这两个producer。它没有越过该入口
证明BL后的续段。因此即使raw postcall加载literal177D形态明确，也不能宣称它们
已是accepted consumer。

下一CFG候选是这两条已验收BL后的静态fallthrough续段，窗口分别44B与38B。
82B仅调查窗口规模；边界、实际code/literal、opaque cross-edge、current-unknown及
新合同仍未验收，也不是已进入Tier-1队列的收益。不得把callee结构化返回、自然
执行到续段、原opaque入口已被穿透或后段完整包络分类当作已证明。
冻结包必须独立绑定两个producer的原始BL/owner、父级opaque edges和immutable
baseline，明确是static conditional return edge；若现有root准入合同不能表达它，
先用TDD与独立raw verifier建立必要合同，不能改写旧artifact或放宽旧opaque stop。

## 生命周期后续

已分类渲染脚本的命令1/5/4会调用渲染函数或等待帧，post脚本命令3/4亦含等待/调用。
配置表域闭合还需要这两个preplanner脚本及其callee/等待期间的单位状态保持，planner
内部业务函数，以及其他scorer/initializer入口和slot13耗尽状态。32B脚本语法完整
不等于作用域、无副作用、自然返回或单位CD不变量。

## 验收

- [ ] 重放脚本 → 两条preplanner参数流通过，postplanner两点显式excluded，promotion0。
- [ ] 对照原artifact → 两条记录opcode与hash一致，不改原consumer分母。
- [ ] 查看canonical → 两个后续窗口仍unknown，不把82B窗口计为新增覆盖。
- [ ] 核对失败记录 → 首次失败原因是缺指令owner，修正后保留该限制。

上述两条parent opaque edge、accepted producer、unknown window及源摘要另冻结在
`notes/evidence/rom-ai-cfg-continuation-preflight-20260930-v1/`。snapshot明确
root_admissibility_proved=false、classified_instruction_membership_claimed=false；82B不能作为Tier-1收益。
