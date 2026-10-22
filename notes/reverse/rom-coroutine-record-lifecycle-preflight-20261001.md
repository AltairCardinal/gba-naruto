# 共享任务记录初始化与恢复链（2026-10-01）

状态：有限初始化、生产者编码与地址关系已复现；全局槽域、writer和同上下文恢复仍开放，
promotion=0。沿用固定producer/consumer窗口与scheduler生命周期模式，直接复用已有
`verify_rom_task_scheduler_core`和callback lifecycle gate，不另写调度器或生产分析模块。
本轮脚本只做可复现实验，没有功能代码变更、提交或push。

## 与既有成果的关系

上一轮renderer handler的9C574→ARM026C恢复链使用的记录，正是61D8C注册、61E00清理的
4C记录；与59EAE0方向已有callback注册器是同一条链，不能重复构造另一套生命周期模型。
所有地址为ROM offset，RAM值则完整写出。

ROM SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
固定coverage raw SHA `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`。
既有scheduler producer合同重放通过，代码/artifact身份由本轮观测收据固定；这不等于
重跑整个scheduler或formal合同。Butano复用仍需已提交证据闭包，本轮未提交材料只作规划。

## 已绑定的RAM关系

| 地址/计算 | 本轮能够绑定的用途 | 不能外推的内容 |
| --- | --- | --- |
| `03000A88` | 61D1C、61D98、61E04 literal均指向任务记录base | 不代表所有运行入口的record地址域 |
| `03000A88 + slot×4C` | 初始化/注册/清理与ARM推进的固定形态 | 不代表注册slot全局有界 |
| `03000CE8` | callback word基址；等于base+8×4C | 间距不是独立物理数组长度证明 |
| `03000D00` | callback参数word基址 | 不证明高slot与callback区没有别名 |
| `03000D18` | ARM当前record指针的literal绑定 | 所有writer和生命周期仍未枚举闭合 |
| `03000D1C + slot×580` | 非零slot注册时声明的初始SP算式 | 不证明实际栈深、互不覆盖或恢复安全 |
| `03002E1C / 03002E20` | ARM初始入口保存外层LR/SP、结束边界取回 | 不证明动态续入身份始终正确 |

这些literal是 **IWRAM的0300地址**，不能误读为EWRAM的0200地址。
非零slot1..6声明的stack top依次为129C、181C、1D9C、231C、289C、2E1C（均0300前缀）。
slot6的top等于外层LR保存地址，只是端点相等，不由此推导栈溢出或安全。

61D10初始化从r2=0开始，4C stride，store后r2+1并以`<=7`回边；该循环本身无callee，
固定覆盖slot0..7，共8条。每条tag=slot+1、wait byte=1、SP和PC字段初始FFFFFFFF。
因此slot7初始tag8；ARM0338的tag8判断是扫描停止条件，不是可以运行的第八个callback证明。
这是初始化模板，不是所有后续状态的槽域证明。

## slot0的literal参数与实际存储须区分

旧记录列出61D4E的callback参数61D70，这个参数事实保留。但61D8C在slot0时通过61D9C
跳到61DC8，跳过SP初始化、callback参数和用户参数的存储。之后从53D5F0+4×slot取得
record+8的初值，slot0读到的是FFFFFFFF sentinel。不能把“传入61D70”说成“已存入并
会通过record+8执行61D70”。旧producer artifact身份不改写，当前语义解释由本记录补充。

## 复用后的producer分母与未闭合入口

既有独立producer扫描重建：61D10只有616C0一个BL；61D7C有8个BL；61D8C有2个BL
（61D84、7C61C）；61E00有12个BL。没有重复新建全ROM扫描器。
新增目标7C5E8有5个BL形态：7BA0E、7BE36、7F0D6、7F10C、7F2B6。
9C574有353个BL形态；不是只有renderer的两个调用点。
精确tagged pointer出现亦逐字节枚举，61E00有一个，其余这五个目标均无命中。
范围只覆盖该编码/字样合同，不排除computed、RAM或间接producer，不证明自然调用。

61D7C的8个已知固定参数slot落在0..5，可复用旧注册参数流；不能外推所有入口。
另一入口7C61C的局部形态来自7C5E8：u8保存值在声明不变时加2再截为u8，仍可取0..255；
没有从这段算术得到`slot<=6`的守卫。7C5E8还调用7FE2C，r4保存义务没有闭合。
其中两个上游点使用来自字段的XOR/寄存器值，也不能只凭一个CMP推断全入口为0/1。

首轮41个scheduler点加7个7C5E8窗口点的owner检查在后者失败：primary是
`consumer_code_slice`，不能当instruction membership。原脚本和空输出保留。
后续把这7个点从已验证instruction列表中排除，保留raw decoder shapes并标false；
**没有放宽验证规则或晋升**。须从已验证入口独立重建到7C61C的CFG/path与callee条件，
再组合五个producer的参数域，不能仅复用形态清单。

## 具体别名反例的边界

对假设slot8，base+8×4C恰等于callback base03000CE8；其SP字段store地址03000CEC
恰等于callback数组slot2的word地址。独立算术复现一致，说明任意u8 slot与安全record
模板不能混同。没有证明slot8自然发生，也不宣称实际越界、损坏或用户可见BUG。

## 复验、归档与后续动作

复用callback gate的真实分母与pointer/registration变异测试2/2通过，guard非降级exit0。
独立raw replay重算literal、循环常量、slot0分支/sentinel和别名地址，结果一致。
源码未修改；不运行会重导出历史managed artifact的旧测试，避免覆盖历史产物。
没有mGBA、canonical或formal重跑，当前仍87,631B未知。

永久收据`notes/evidence/rom-coroutine-record-lifecycle-preflight-20260930-v1/`：当前record
输出为`record-shapes-v3.json`，生产者为`producers.json`；初始空输出无效，v2只作过程记录。
manifest绑定14个文件，原始run已completed。重放需仓库根、固定ROM与已提交基线合同；
新的扫描使用新run，不覆盖原始目录。

该路线暂不继续增加局部字段检查。重开条件是取得7C61C完整root-to-source证明与槽域，
以及current record/SP/LR所有相关writer、clear/inherit和同上下文恢复不变量的新证据。
这同样不能跳过59EAE0的08F654 producer frontier。125B五根仍未通过Tier-1。
当前可继续处理另一个已找到固定consumer、无需新opcode的脚本增量簇。

## 可执行验收

- [ ] 查看record-shapes-v3 → 8条初始记录，slot7 tag8，slot0 PC marker FFFFFFFF。
- [ ] 查看excluded_raw_decoder_shapes → 7点membershipfalse，未混入41个已验证点。
- [ ] 查看producer输出 → 61D8C两个入口、7C5E8五个形态、9C574的353个形态。
- [ ] 查看alias与独立重放 → 假设slot8地址相等，自然发生false。
- [ ] 查看regression/guard → 2/2通过、exit0、非降级；canonical没有改变。
