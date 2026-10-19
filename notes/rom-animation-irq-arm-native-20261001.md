# IRQ RAM、协程和内置 BIOS 联合验证（2026-10-01）

状态：固定来源及人工状态下，IRQ→两个真实RAM回调→返回、协程保存／选择／恢复、
CpuSet已接入同一原生内核。**自然入口、全writer、实机BIOS和完整上下文恒等仍未证明；
promotion=0，无游戏UI变化。**

## 模式、复用与身份

新增登记模式“冻结来源的ARM/Thumb迁移回调与协程／BIOS有限夹具差分”：脚本优先，
复用既有boot-copy、boot-interwork、IRQ raw verifier及已有本地mGBA内核。
不另建ARM解释器或scheduler，不启动子代理、不安装依赖。
已有verifier只证明复制字节／参数或固定CFG，不能直接复用为ARM effects证明；
因此追加有PC范围、停止点与步数上限的原生夹具。脚本和C源随证据封存供后续复用。

ROM SHA256 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b。
权威目录：[v2收据](evidence/rom-animation-irq-arm-native-20261001-v2/manifest.json)。

| 身份 | 哈希 |
| --- | --- |
| irq-arm-native.json SHA256 | ab80481b9c79849d0519a01cbb2e315906d9a3f88f8ba2103b9c9dc66b77c11d |
| 96成员manifest SHA256 | df5c56b0dc8e76a4460c706cec5a89bb03c313b457b1af58698924016740373f |
| 人工baseline 397,312B SHA1 | e7ade0ed82bb0f2d3d52070b280a8c84bb8abbab |
| provider-contract.json SHA256 | 919bdaef8f0cf9c99204945d2bd742d10230de29f5f1505b3468028690b3f2ad |
| 内置BIOS 16KiB SHA256 | ea370175428d57d0bb77cd6b8e3b3c56a63849ff2122de9e5c2ddf256c2d3836 |

mGBA source commit c16c3ff55585e71bee83c95539c2ecde15d728c8；六个关键源码与其
Git blob相同。70项头文件、构建宏来源、源码及动态库依赖固定；这些绝对路径仅为
本次本地provider依赖，不是Butano资源输入或跨机器保证。
实际内核BIOS字节与固定生成数组及零后缀一致。

每个原生进程先验证save/load/save逐字节相同，然后每case恢复内存baseline，
每条轨迹绑定其SHA1；不是自然游戏状态快照。447个当前输入执行前后验size/SHA；
旧保存包33成员和336输入验真。不是重证全部历史CFG或88,472指令。
v1原始收据保留；v2追加快照哈希和第13项测试，不改旧manifest。

## 入口勘误及复制边界

前两份笔记把入口写成5CF8／5D60，偏0x10；原JSON／轨迹数值正确。
正文已更正且保留勘误，冻结收据不改。624C0保存R1原值，不能假设加0x10。

| 注册caller／slot | RAM入口 | ROM复制范围 | 代码 | literal／邻接字节 |
| --- | --- | --- | --- | --- |
| 64594／0 | 03005CE8 | 638..694，92B | 638..680，72B | 680..690四word literal；690..694是相邻首指令 |
| 65234／2 | 03005D50 | 690..734，164B | 690..714，132B | 714..734八word literal |

CpuSet参数分别由6459E和646DE来源绑定，复制长度不等于函数代码长度。
busy byte03005D44恰在第一份复制尾后。IRQ loader的固定DMA描述符复制
104..304共512B至0300007C；IRQ代码仅104..244，literal244..24C，
其后协程字节不自动进入IRQ执行域。
fresh copy verifier重建9描述符和5 operation；报告中的620B是历史packet收益，
本批新增分类0。

## 回调与 IRQ effects

638读取VCOUNT；小于160时，从02000000 + u8(03005CE6)*1280 + VCOUNT*8
读取两个word，写IO04000040／44。高bank跨物理EWRAM256KiB时按固定内核镜像读；
fixture向对应物理地址布置数据，不将逻辑地址说成另一份RAM。
VCOUNT≥160直接返回。

690读取02002740 + u8(03005D4E)*160 + VCOUNT的byte：
非零取0300004E／52的halfword和03005CCC的word，写IO04000050／54／48；
零写FF／10／3F3F3F3F；VCOUNT≥160无回调store。
这些路径直接store目标固定为IO，不能排除其他向量、动态callback、DMA或未知SP
对counter75和对象池的写入。

9,620条回调样例执行ROM及RAM版本，按源码offset规范化PC后逐项比较
visited、write、registers、CPSR/SPSR、counter，全部一致。
覆盖所有可见scanline在若干bank、全部256bank在0／159／160／65535边界及两分支；
**不声称全输入笛卡尔积穷举**。
48条IRQ样例固定IE/IF、VCOUNT、向量及IRQ/System银行SP，执行真实ROM或迁移IRQ，
进入真实RAM回调，再返回IRQ。IRQ SP／LR和SPSR恢复；源码21C将CPSR低byte置92，
不能要求保留人工初始D2的F位或比较flags。
未选向量、2000挂起分支、嵌套IRQ与自然事件时序开放。

## 协程保存／恢复

真实Thumb9C574→BX pc→ARM9C578→026C保存，再从024C调度。
slot2穷举256wait；六slot验证0／1／2／255及两组区分寄存器值，共300对。

| 字段／行为 | 原字节及内核结果 |
| --- | --- |
| record+4 | 弹栈后的原SP |
| record+8／+44 | 原LR，分别为resume PC与保存字段 |
| record+0C | 显式人工SPSR |
| record+14／+18 | 保存r1／r2 |
| 370／3A0 | 恢复r1←+18、r2←+14，交叉 |
| record+1 | r0低byte写wait |
| wait=1 | SUBS结果0，STRBNE不执行，record保留1并选中 |
| wait=0 | 写255并跳过 |
| wait>1 | 写wait-1并跳过 |

选中记录时r0、r3..r12、SP按夹具保留，r1/r2交换。
这不是所有寄存器恒等，也没有修复游戏ROM。
System模式SPSR属于固定mGBA及人工前提，不外推ARM7硬件保证。
callback record全writer、private-frame、正确bank/slot、自然重入次序仍未证明，
9C574仍不能作为普通返回callee。

## CpuSet 与内置 BIOS

两例执行真实9C0E0 SWI0B、mGBA内置BIOS ARM路径、9C0E2返回；
目标92／164B逐word等于原ROM，前后guard word及counter75保持。
SVC/System SP单列；不是手写memcpy冒充SWI。未使用官方BIOS或实机。
scalar store包装器转发原内核；STM仅记真实storeMultiple调用的base/mask/direction，
内容由实际RAM readback核对，不推导未观察的逐word bus事件。
nextEvent设远期且检查cycle预算，因此自然DMA／PPU／IRQ时序未验证。

## 验证、失败与复验

13tests、10,270轨迹：9,620 raster、300 save、300 resume、48 IRQ、2 CpuSet。
两个artifact verifier fresh通过，IRQ raw链另行重建；
压缩轨迹逐条SHA256对应authority，baseline SHA1唯一。
初始缺模块red只有guard摘要，stderr未留，不补造；后续context／IRQ／BIOS／snapshot
red保留完整日志。首份初始化崩溃是漏编译宏造成mCore ABI偏移，修复为完整构建宏；
不是ROM指令崩溃。EWRAM镜像夹具、SP不在STM mask、STRBNE、CPSR92等预期错误
按原字节纠正，不改游戏。快照哈希先经第13测试失败，再补SHA1并通过。

主v2 60.94s／159.07MiB，永久v2 60.63s／175.50MiB；同heavy.lock、非降级exit0。
两个权威输出逐字节相同。三owned run已completed；C编译-Wall/-Wextra/-Werror、
Python AST／行尾、git diff检查通过。无commit/push，Butano未改。
约一分钟复验，在逆向工作树选择新CHECK_UNIQUE：

~~~sh
python3 tools/experiment_workspace.py --root . init --task animation-irq-arm-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-irq-arm-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 300 --idle-timeout-s 150 --sample-interval-s 0.1 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-irq-arm-native-20261001-v2/replay_receipt.py build/experiments/active/animation-irq-arm-replay/CHECK_UNIQUE/output build/experiments/active/animation-irq-arm-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-irq-arm-replay --run-id CHECK_UNIQUE
~~~

缺provider或输入改变应失败关闭，不改历史manifest绕过。

## 下一联合里程碑

不重复这两个回调入口调查。复用原生夹具，将handle/group/slot/timer、long callback
后半、allocator与renderer两层sentinel接到同一来源模型；未知writer不猜为不写。
签发自然消费／同上下文摘要前须补task记录writer域与自然调度证据。
8F654未知producer开放，不重复扫exact pointer。
全writer88,472／9,730／8,785、双字段31／16仍是前包统计，不与本批算术相加。
canonical SHA b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2，
unknown87,631B；proof SHA 465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568；
bank SHA f52524fbba244cf0497ffa021503702da9a185485c13027872f2a65dad56bed2。
未触发新增分类Tier2门槛，不重跑full formal；175 blockers为历史formal。
Goal active，最近周剩28%，20%停止线继续有效。

### 【功能特性】

- 从本记录进入v2收据，复验RAM回调／IRQ／协程／CpuSet联合路径；仅逆向工具，无游戏UI变化。

### 【BUG 修复】

- 探针漏ABI宏初始化崩溃 → 固定完整宏后10,270样例重放通过，工具BUG已修复。
- 两笔记RAM入口偏0x10 → 更正为03005CE8／03005D50，原收据保留，文档错误已修复。

### 【验收清单】

- [x] 查看trace-audit → 10,270记录对应、baseline SHA1唯一；仅人工状态。
- [x] 按命令复验 → 13tests、两个输出逐字节相同；provider改变失败关闭。
- [x] 查看context轨迹 → r1/r2交叉、wait1保留、wait0回绕255；无自然可达声明。
