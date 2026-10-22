# Renderer 7/8 handler：原始图、早退与任务上下文依赖

> 后续已[合并到既有scheduler生产链](rom-coroutine-record-lifecycle-preflight-20261001.md)，完成有限模板/别名预检；全局恢复仍开放，当前暂停局部扩张。

状态：原始图和相关栈槽写入分母已复现；**完整handler合同仍未闭合，promotion=0**。
125B五根仍是语法候选，canonical unknown保持87,631B。本轮直接执行active Goal，
按固定CFG消费者/解释器合同的已有任务模式优先复用脚本，不外派模型。

## 可复用能力与范围

新增`tools/analyze_rom_renderer_handler_graphs.py`：复用prebattle独立verifier的原始
Thumb BL/B/Bcond位移decoder；复用固定renderer verifier从v2/v3验证所得block与指令
membership；复用boot-interwork独立ARM decoder和完整92条指令重建。每次调用重新
核对六个CFG上游输入，不能让共享缓存代替本次身份校验。

新工具是调查入口，明确区分内部call target、条件式call continuation、条件式context
resumption和直接边界stop。没有新账本、parser、发布系统或正式artifact。
范围固定为7=`675E4..68084`、8=`68090..681AC`；68354与6835E只作已知控制边界stop，
未证明dispatch后的执行或epilog结构化返回。每条遍历指令都要求固定v2/v3指令membership，
不线性解码literal，也不越过未绑定入口。

## 原始图实测分母

| opcode | 指令 | 指令字节 | edge | BL sites | 唯一BL目标 | 直接SP word store |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 1,171 | 2,410 | 1,256 | 34 | 10 | 34 |
| 8 | 114 | 244 | 121 | 8 | 6 | 7 |

这是以外部call可返回为条件、内部call同时保留target与条件式continuation的图。
没有把callee指令加入handler分母，也没有证明任何一个call返回。
raw图没有outside-bounds或indirect-PC frontier，仅说明本窗口的已遍历直接控制边；
**不能称为零语义frontier**，所有opaque callee、任务切换、间接RAM别名义务仍开放。
直接SP stores不等于所有通过寄存器别名或callee写入栈的store分母。

指针栈槽`SP+14`的直接word stores仍只有：7的67F50/67F84，8的68174/68194。
7另有67C1A→6835E和68038→6835E的直接退出路径；后者沿输入/flags分支到达，
不经过两个加3的store。因此“每次进入7都会加3并继续读取下一个命令”不成立。
7的68058 BL→67810是同一解释器内共享代码入口；它没有独立函数prolog，不能只
解码BL后的fallthrough便当作已经关闭该调用。工具保留target及条件continuation。

独立sidecar使用Capstone指令ID/PC目标重新worklist，而非builder的raw分支helper；
精确复现两图的全部node、edge和直接SP store。两者共享Capstone作指令解码/显示，
但分支位移与edge构建方式独立；没有藉此证明callee语义。

## 9C574是上下文依赖，不能套用普通callee保存假设

两个相关调用点：7的67CFE、8的68108，目标均9C574。
原始链：Thumb `BX pc`于9C574→ARM B于9C578→ARM026C。
boot-interwork旧合同已固定这段sibling身份但明确排除其晋升；本轮不改旧合同，也不
晋升sibling。026C与后续关键ARM指令则在已接受boot-root指令分母内。

- 026C保存整组寄存器，随后读取SPSR；不能视为普通Thumb叶子调用。
- 0320把SP写入`record+4`；032C按4C形态推进record地址。
- 039C从`record+4`加载SP，恢复记录中的寄存器；03A4以BX LR继续。
- 另一边界03AC从另一指针加载SP，03B8同样以BX LR继续。

这些raw读写形态证明它涉及记录化SP保存/恢复和间接续入，**不证明实际task分母、
目标record有效、caller必然再次被选中、同一上下文恢复或栈槽跨帧保持**。
工具把两处后继标为`conditional_context_resumption`；不使用普通callee-return标签。
完整ARM代码/旧artifact/manifest/verifier身份及原始字节均由当前报告绑定。

## TDD与缓存问题修复

首轮RED因新图分析模块缺失，GREEN为7项新测试+7项Thumb分支回归，共14/14。
新增context continuation合同先RED缺参数，再GREEN15/15。
随后真实缓存变异测试确认：先加载CFG，再改变上游manifest输入，同进程旧实现仍
返回报告。RED为“应抛ValueError却未抛”；补每次调用上游六文件SHA校验后，16/16通过。
**已修复新分析器中缓存掩盖上游输入变化的BUG**：变更输入现在失败关闭，不产生可信图报告。
变异通过mock输入完成，没有改用户工作树的上游文件。

最终guard非降级exit0、11.4s、峰值171.70703125MiB；当前CLI报告guard非降级exit0、
12.4s、峰值169.78125MiB。py_compile、限定路径diff和新文件空白检查通过。
没有运行mGBA、完整formal或coverage rebuild，原因是本轮未形成Tier-1包，更未达Tier-2门槛。

永久收据：`notes/evidence/rom-renderer-handler-context-preflight-20260930-v1/`，
当前输出是`report-context-v2.json`和`final-green.log`；首份`report.json`缺context注记，
已被取代，仅作原始调查历史，不宣称绑定最终实现身份。旧14/15项日志同样仅作TDD过程。
manifest包含源码/测试快照、全部红绿/guard、独立重放脚本及结果；原始run已completed。

重放工具应置于新的唯一run并经同一heavy lock；已有收据不能覆盖。
独立sidecar可以在仓库根直接重放永久报告：

```sh
PYTHONPATH=. python3 notes/evidence/rom-renderer-handler-context-preflight-20260930-v1/independent_graph_replay.py
```

## 下一完整里程碑

不把125B语法假设自动升级为“固定宽度完整消费”。先复用boot与既有task/callback
成果，查明026C消费的当前record来源、4C槽域、SP/LR字段初始化与所有writer、清理/
继承、选择与恢复条件。只有关联caller的跨帧不变量闭合，才能组合7/8等待与续读合同。
其余9个外部目标的相关SP/寄存器/内存效果也需按实际依赖闭合，不能只依赖ABI习惯。

该依赖也可能影响AI在等待帧前后组合筛选条件，但目前只记录共同核对点，不推导AI域。
若仍缺record/间接续入分母，保留unknown并转向有独立闭合入口的其他消费者簇；不得
继续重复局部加法检查，也不得将永久收据通过说成完整上下文证明。

## 可执行验收

- [ ] 打开report-context-v2 → 两图分母与上表一致，完整语义false、promotion0。
- [ ] 查看context_switch_dependency → 两个调用点、ARM026C、SP恢复点，same-contextfalse。
- [ ] 查看upstream-red与final-green → 首次暴露漏检；最终16/16且guard非降级。
- [ ] 重放独立sidecar → node/edge/直接SP stores精确一致，不声明callee闭合。
- [ ] 查看canonical → unknown仍87,631B，125B候选与sibling未晋升。
