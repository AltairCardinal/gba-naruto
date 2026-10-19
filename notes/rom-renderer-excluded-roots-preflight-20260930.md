# 五个被排除的 renderer 脚本根：推进形态与语法预检

> 后续[完整原始图与上下文依赖](rom-renderer-handler-context-preflight-20260930.md)已发现早退和SP切换；125B保持候选，旧局部加法证据不得升级。

状态：可复现预检完成，5个根/125B候选均落在固定unknown分母；**promotion=0、未通过Tier-1**。
本轮Goal active；沿用“canonical CFG内固定literal consumer到renderer/parser记录闭包”
模式，脚本优先，未外派代理。没有改旧exporter/verifier/artifact、coverage或proof。

## 复用与证据边界

复用既有独立`verify_rom_fixed_renderer_script_records._rebuild`，从v2/v3 block分母重新
枚举41个literal消费者并重放寄存器参数流，核对固定旧payload；不是仅硬编码五个site。
旧合同接受36 site/30 records/1,124B、排除5根。本轮只分析这5根，不外推全ROM脚本根。
复用旧renderer文本终止解析，候选parser追加7→3B、8→2B的语法假设。
新能力保存在`tools/analyze_rom_renderer_excluded_roots.py`，用途为调查入口，不能用于晋升。
不需要第二套消费分母或账本；最终接受仍走既有packet与分层审计链。

ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
immutable coverage raw SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。
旧payload SHA `7b56a9a05d8ea7d78bddd68dba874f0c7cae2ae3fa5d1aa6c2ab3a3949ec7698`，
旧verifier SHA `c7f3eeaabc4a6755c7974838084aa7495f866924e40fd4ea2bb072d5db7f3927`。
报告同时绑定上游六文件身份和路径分母，不依赖mutable live coverage。

## 原始指令证据与候选解析

脚本指针在67164存入`[sp+14]`。dispatch表67180的7/8槽分别指向675E4/68090。
7入口读`pointer+1`与`pointer+2`；8入口读`pointer+1`。18个关键指令点均绑定已有
v2/v3 instruction claim。局部推进形态：

| opcode | 原pointer load | add | 回写栈槽 | 局部增量 |
| --- | --- | --- | --- | ---: |
| 7 | 67F2C→r3 | 67F4E | 67F50 | 3 |
| 7 | 67F80→r5 | 67F82 | 67F84 | 3 |
| 8 | 68170→r6 | 68172 | 68174 | 2 |
| 8 | 68190→r0 | 68192 | 68194 | 2 |

独立sidecar直接按半字掩码解析LDR/ADD/STR的寄存器、栈槽和立即数，并重算dispatch
表值，结果一致；它不证明load与store之间完整控制流或callee副作用。opcode7范围里
夹杂literal，初始线性反汇编在解码障碍处停止，保留原窗口；后改用已有177个instruction
block输出，不将间隙数据当指令。177是窗口内block分母，不是新完整handler闭包声明。

| 根→候选终止后边界 | 字节 | opcode序列 |
| --- | ---: | --- |
| BC9→BCD | 4 | 7,0 |
| C2E→C34 | 6 | 7,3,0 |
| C34→C6C | 56 | 1,5,8,3,0 |
| 14B4→14BA | 6 | 8,3,4,0 |
| 15FC→1631 | 53 | 1,5,8,3,4,0 |

去重125B，固定canonical unknown交集也为125B。C2E结束于C34，二者在当前候选规则下
相邻而非重叠；不因此外推其他子根。BC9后的BCD..BF5等剩余间隙不属于本候选。
旧41site分母重建仍为36接受/5排除，不改变其历史状态。

## TDD、重放和未闭合义务

RED：新增测试先因缺少分析模块失败，原始red.log保留。GREEN：6/6通过，覆盖零值
操作数不能提前终止、截断/越界/未支持opcode/缺终止失败关闭、嵌套文本终止符、真实ROM
与CLI重放。整理后py_compile与限定路径diff检查通过。真实消费者重建包含独立旧CFG
verifier，不把纯合成parser测试当集成验收。

测试guard非降级exit0，23.7s、峰值442.1875MiB；独立CLI报告guard非降级exit0，12.4s、
峰值288.3359375MiB。完整formal和coverage没有重跑，也没有启动mGBA。
永久收据：`notes/evidence/rom-renderer-excluded-roots-preflight-20260930-v1/`，含红绿日志、
两份guard、报告、源码/测试快照、raw sidecar和block窗口，manifest逐文件固定哈希。

```sh
python3 tools/run_guarded.py --summary /tmp/renderer-preflight-guard.json \
  --lock-file build/experiments/heavy.lock --wall-timeout-s 240 --idle-timeout-s 180 -- \
  python3 tools/analyze_rom_renderer_excluded_roots.py
```

后续使用新的唯一run目录替代示例summary，不覆盖已completed实验或永久收据。

**下一里程碑仍是完整7/8 handler消费和续读合同**：从dispatch入口重建真正可达的
CFG、所有脚本operand read和pointer write分母，关闭opaque callee对脚本指针/栈槽及
保留寄存器的相关影响，区分等待自环与续读条件。局部两种加法相同并不证明所有路径
只按该宽度推进；也不证明按键必到达、脚本自然执行或整段可编辑。
只有独立verifier闭合上述合同后，125B才有资格作为packet的current-unknown投影候选。
若出现状态决定宽度/目标、未知入口或无法闭合的callee，保留unknown并记录精确重开条件。

## 可执行验收

- [ ] 打开report.json → 41site重建、5根、125B候选，promotion0/Tier1false。
- [ ] 查看raw-advance-shapes.json → 四个局部advance及dispatch一致，完整语义false。
- [ ] 查看red/green/guard → RED缺能力，GREEN6/6，guard非降级exit0。
- [ ] 查看canonical → unknown仍87,631B，不把候选125B计作净分类。
