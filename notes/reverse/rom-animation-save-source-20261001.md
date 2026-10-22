# 动画保存回调来源与保存／恢复／冻结联合验证（2026-10-01）

> 后续联合结果：[IRQ RAM／协程／内置BIOS](rom-animation-irq-arm-native-20261001.md)。历史收据保持。

> 地址勘误（2026-10-01）：此前正文将两个RAM入口写偏0x10；实际为03005CE8／03005D50。
> 原始JSON数值及轨迹正确，冻结收据不改；复核来源是CpuSet固定复制638／690和624C0原始STR。

状态：8584C回调从真实slot5注册链取得 bounded source 证明，counter保存／恢复和128对象
freeze与四task清理已在原指令有限模型中接线。68DE4上游仍是8F654未知入口；全writer、
自然counter域、合法handle和同上下文恢复仍开放，**promotion=0**。

## 模式、复用与身份

沿用“固定producer根闭包”和“冻结CFG存储分母／物理别名联合调查”的脚本优先方式。
复用前包raw CPU、既有Thumb ISA／raw-control-flow oracle、branch scanner、v6来源verifier、
scheduler bundle及callback lifecycle gate；不另建scheduler，不启动子代理。
新功能追加到已有实验链，只有bounded source worklist与保存入口wrapper；不是另一套
执行器或独立产品功能。无mGBA或实机运行、提交、push，Butano工作树未改。

ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
336个当前输入在执行前后核对size/SHA；前包49成员及其284输入完整验真。
权威输出 `notes/evidence/rom-animation-save-source-20261001-v1/save-source.json`，SHA
`c74e7840505c983fbc05a1f6d41af13e5124ebc46fbb3d443fdf14e04a4da992`。
33成员manifest SHA `965e91b1843c02eb9d105a84f3f18ee5683b7076bcd45f3f7a635082b44b84da`；
portable-report SHA `9dda429594939a0454103f57ba415d82766f64c488c9a028eefa1f6025490fdb`。

## 固定注册、记录及dispatch绑定

原ROM85A14只有一次exact Thumb pointer0808584D出现。85A04 LDR r1取该literal，85A06
MOV r0=5，85A08真实BL61D7C。此来源属于v6的859B8 CFG；本次fresh独立verifier重建
v6的12,564指令／2,305block／85frontier，四source点在artifact分区和新raw worklist一致。
不靠literal出现本身、历史笔记或coverage片起点授予root。

61D7C把slot截断u8，置argument r2=0后实际执行61D8C；人工原指令执行结果：

| 槽5的字段 | 原指令结果 |
| --- | --- |
| callback | 03000CE8+4×(5-1)=03000CF8写0808584D |
| user argument | 03000D00+16=03000D10写0 |
| task record | base03000A88+5×4C，SP初始化按原算式 |
| task PC+8 | 从53D5F0+4×5取得08061CBD |

PC指向既有slot wrapper61CBC，共用61C58从callback数组读取，再经9C114的BX r1进入
8584C。fresh scheduler bundle重建116指令／33block及原register provenance138B，
1处indirect frontier保持；旧308B不重复计入净增。raw registrar完整返回／恢复SP，
trace SHA `35ac8477518ab7a0b22aaf40f1bc0d179eb2a7fc6134d9c4212e20be54789ddf`。

这证明固定注册与dispatch结构，**不证明自然slot5已运行、全注册入口有界、callback
记录不会被外部writer覆盖或9C574能恢复到同一上下文**。callback literal和registrar
mutation都拒绝，原artifact／manifest不改。

## 原指令图及执行边界

11个有限source group、350个unique指令，builder与独立raw halfword worklist逐组相同。
独立worklist验证直接控制流；ISA合法性仍复用既有decoder，并不声称两套完全独立ISA。
BL目标opaque，fallthrough与branch必须在source范围，literal读取单独记录。

| source group | 指令数 | 边界 |
| --- | ---: | --- |
| save8584C..859B0 | 136 | 固定callback绑定；外部callee和context切换不外推 |
| status64A48..64A5C | 10 | 读取03005D44，非零→return0，零→return1 |
| restore857E4..8584A | 36 | 继承前包guard／saved／wait语义 |
| cleanup61E00..61E1C | 14 | slot截断u8，record+4和+8写FFFFFFFF |
| saved init857B8..857D0 | 12 | 五个byte清0，counter保持 |
| registrar wrapper／inner | 7／47 | 实际raw callee执行，slot5与argument0 |
| producer859B8..85A1E | 36 | v6分区／worklist内真实85A08 |
| candidate68DE4／8F618／8F654 | 8／22／22 | entry仍未证明，不晋升 |

运行save时从8584C入口开始，实际调用64A48、857E4、必要时61E00和857B8，均执行真实
指令，无callee stub。人工SP03007000、IWRAM fixture、固定guard／busy／flags仅为有限
模型前提，不自动成为自然内存或private-frame证明。

普通保存路径 **stop85988** 在9C574调用之前，SP仍有callback自己的40B frame；它不是
函数return或恢复成功。timeout路径 **stop858E4** 在后续IRQ／图形资源操作之前，不能
把只执行前半回调的结果说成完整保存UI或完整freeze→unfreeze链。

## counter保存→恢复及timeout effects

从完整save入口验证256个counter byte：busy=0、guard0、wait0、saved0时，857E4真实
return0；85876读取saved0，85882读取counter、85884写saved，85888写counter=1，然后
到85988。saved原本非零且guard不满足时保持counter/saved，避免重复覆盖保存值。

再以counter=1和刚保存的saved、guard303执行同一入口：非零saved被857E4原样恢复
并清0；**原counter=0时saved也是0，restore将它当空marker，counter保持1**。
256组合轨迹明确这个zero-marker例外，不能把save/restore写成所有u8值的恒等round-trip，
也不能据此证明counter自然值任意或仅0/1。这是原ROM语义，未作为游戏BUG修改。

wrong guard、wait59且argument1时，helper把wait推进到60并return2，进入8589C分支：

1. 858A2／A8／AE／B4分别以1／2／3／4调用61E00，两marker word各写FFFFFFFF；8个
   精确record store，未清记录的其他字段，不外推全部task lifecycle。
2. 858C0..858DE遍历pool03003BB8的slot0..127，stride60；只有flags&1非零时858D4写
   flags|8。byte截断和signed回边在slot127后结束，不访问第129项。
3. 858E0实际调用857B8清saved等五byte，counter保持，858E4停止。

mixed／all-active／all-inactive／only-last四组，pool flags store数分别 **64／128／0／1**；
每个store地址、值、四task marker和callee顺序核对，不把所有pool字段都视作清零。
这个新writer解释了freeze bit3的一条真实来源，但回调后半及外部writer仍可改变状态。

权威cases共 **521**：256 save、256配对restore、3 existing-saved、4 timeout、1 busy、
1 postbattle候选。每条含input、完整trace SHA、step/store、stop/SP/callee信息，脚本可
逐字节重建；registrar trace另外绑定，不把测试内部重复执行算额外独立case。

## 68DE4与8F654仍开放

复用全ROM halfword **BL/B** scanner：68DE4唯一直接形态8F640，8F618唯一8F668，
8F654无命中；三个exact odd Thumb pointer出现均0。8584C无BL/B，只有85A14一次pointer。
此scanner不含Bcond、ARM或computed producer；原始形态分母不等于自然caller分母。

68DE4局部原指令在68DEA写counter=1，探针在外部controller732B4调用68DEC前停止。
新raw图可重建8F654→8F618→68DE4的局部直接关系，但fresh callback lifecycle gate
仍明确阻断 `open_callback_8f654`，没有它的producer入口证明。
因此原两个candidate ref中 **85880已有固定注册来源，68DE6仍是入口开放候选**；
旧counter-inventory.json与14ref／12旧来源／2旧候选的历史身份保持，不改成新receipt。
59EAE0候选或“无exact pointer”均不由此获得分类、表长或自然不可达证明。

## TDD、修复及复验

10项测试先缺模块正确red。首次最小实现有两项真实boundary失败：decoder把ROM外
branch/call列成frontier，wrapper错误把它当普通终点而漏记录target。现在用raw target
显式检查branch/fallthrough范围，call保留opaque target；修复后10/10。

补全flags输入域与256保存→恢复组合后，12项先因缺flag_words参数正确red；最小实现
通过，再整理callee target映射并在主集成重新跑12/12。首份batch因ThumbBranch实际
字段叫mnemonic而失败，原脚本／45.58s guard保留；修正后真实batch与永久重放通过。
以上都是调查工具问题，**已修复**；没有修改原游戏行为。版本映射与全部red／green／
失败日志在33成员收据中，未覆盖失败。

主batch46.65s／241.10MiB；永久目录46.68s／247.52MiB，显式同heavy.lock、非降级
exit0，12tests、521raw traces、11raw source groups、三来源／lifecycle verifier及权威输出
逐字节相同。两owned run均completed，AST／行尾检查和相关git diff检查通过。
无新runtime捕获，故自然执行及硬件未验证；无promotion，未重复运行full formal。

约一分钟复验；在逆向工作树根选择新CHECK_UNIQUE：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-save-source-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-save-source-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 300 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-save-source-20261001-v1/replay_receipt.py build/experiments/active/animation-save-source-replay/CHECK_UNIQUE/output build/experiments/active/animation-save-source-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-save-source-replay --run-id CHECK_UNIQUE
```

## 下一联合里程碑

停止重复保存小窗口；后续以IRQ RAM5CE8／5D50、ARM与BIOS/DMA的实际memory effects、
object handle／group／slot／timer域和同上下文恢复为一批依赖闭环。callback后半对
其他对象字段的改写要与lookup／两层sentinel共用源模型。8F654只有找到新producer或
运行时入口证据才继续扩展，不能因它挡路就猜根或重复扫exact pointer。

全88,472工作图本批未重算，9,730／8,785等writer数仍是前包固定统计；新350局部图
不能直接相加当新的全局分母。31双字段／16缺口未重算，完整bank合同仍未闭合。
canonical SHA保持 `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`，
未知87,631B；proof SHA保持 `465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568`；
bank SHA保持 `f52524fbba244cf0497ffa021503702da9a185485c13027872f2a65dad56bed2`。
175 blockers是历史formal，不是本次重跑。Goal active，封存时周剩29%，20%停止线有效。

### 【功能特性】
- 从本记录进入收据，查看slot5注册→保存／恢复→四task清理／128对象freeze；仅有限逆向模型，无游戏UI变化。

### 【BUG 修复】
- wrapper把越界direct branch的frontier当普通终点 → 显式检查raw目标并失败关闭；工具BUG已修复。
- batch错误读取branch.kind → 使用已有scanner的mnemonic；真实batch及永久重放通过，已修复。

### 【验收清单】
- [x] 查看callback_binding → callback03000CF8=0808584D、argument0、task PC08061CBD；自然运行仍false。
- [x] 查看521cases／freeze_cases → 原counter0配对恢复为1；四flags矩阵store64／128／0／1，task marker各8项。
- [x] 按上述新run命令复验 → 12tests、三独立verifier、权威输出精确一致；context切换明确拒绝。
