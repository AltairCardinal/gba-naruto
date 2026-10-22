# 动画关键字段写入分母、启动 DMA 与回调向量（2026-10-01）

> 后续联合结果：[IRQ RAM／协程／内置BIOS](rom-animation-irq-arm-native-20261001.md)。历史收据保持。

> 地址勘误（2026-10-01）：此前正文将两个RAM入口写偏0x10；实际为03005CE8／03005D50。
> 原始JSON数值及轨迹正确，冻结收据不改；复核来源是CpuSet固定复制638／690和624C0原始STR。

> 后续[save来源与保存／恢复／freeze联合包](rom-animation-save-source-20261001.md)已补8584C的slot5固定注册来源；
> 68DE4仍停在8F654入口缺口。本记录保留前包88,472声明图的原身份，下方下一步为当时计划。

本包将上一包的对象池／counter／saved 调查合并到一个写入分母，再验证启动清零、
向量索引别名和保存区初始化。新增的是可复现的依赖事实，**没有闭合全局 writer，
没有新增 ROM 分类或 bank 合同**。counter03000075 仍不能假定自然域只有0/1。

## 复用、模式与证据身份

任务模式：冻结覆盖声明与既有 CFG 的存储分母／物理别名联合调查。按登记表的
脚本优先模式执行，不启动子代理。直接复用上一包 `bounded_thumb.execute`、父包
保守 `flow.run_flow`、原始 Thumb decoder、既有受管目录与资源守卫；没有另建执行器。
新存储分类器用于工作图统计，三个原指令探针追加到既有执行链，DMA效果独立列前提。

输入为原 ROM、已冻结两组永久收据、canonical instruction 声明及45个相关来源文件；
共284个当前输入的size/SHA在批次前后检查。来源 hash 与声明不是新的语义验真，
本次只 fresh 重放 boot handoff 和 vector v14 两组独立 verifier，不声称45组全重放。

永久目录：`notes/evidence/rom-animation-writer-domain-20261001-v1/`，49成员；
manifest SHA `b6ff4a622e59440301e0452e9c0df2c291047a7d3e8832de18fa817db3eaf6db`。

| 权威输出 | SHA-256 |
| --- | --- |
| writer-domain.json | f54b8e5ea44cf0ccecd57db66f9bef99b5a65e75c19d537e3f62df2bc2ff0caf |
| summary.json | c8a95e3fe11a58e6d9d94bf189ad20d20f0467da395163386d31ab1efcec02a8 |
| coupled-writers.json | 0b240818d68eb9a9d449568989cd6c2452d018bb8d17a26d12a81bb8ec01a6cd |
| portable-report.json | 849a4af9440803e71e2c83b99e7bdbeb85a668566381df381405eeb8f7adb51a |
| iwram-bus-reference.json | 7cb64dc9feccfe5f3b369d4515a470975c4a8eae8ddefb7c55398c6104d26f26 |

ROM6291456B，SHA `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
前包41成员和父包58成员分别按固定manifest检查；永久重放不依赖主实验目录或外部
mGBA源码缓存。源码摘录的commit确认收据也已封存。

## 存储分母及未闭合范围

旧67,243指令增加21,229个哈希固定的声明成员，工作图共 **88,472 Thumb 指令／4,420根**。
新增成员采用真实 block 或显式完整 CFG code_ranges 的分区，不将每个 coverage claim
的起点直接当完整指令入口。root 包含声明边界、直接callee、无前驱点及全部未证明的
断开环，根的入口值未知；callee一律opaque，调用后的寄存器和caller stack不猜保留。

| 工作图结果 | 数量／边界 |
| --- | --- |
| primary Thumb claims | 4,025；新增来源语义verifier重放数0 |
| 排除 | 9项缺明确Thumb mode／ARM或mixed；partition排除0 |
| flow | 136,953更新；88,464 reached；8个未到达点中store传输0 |
| store指令／传输 | 7,725／9,730；PUSH和STM按register list展开 |
| 未知地址传输 | **8,785**；保留可能别名，SP不能自动视为安全 |
| DMA寄存器已知写入 | 62；寄存器写入统计不等于DMA效果证明 |
| opaque内存effects | 5,877；call、SVC、return／indirect／mode边界 |
| 已知直接目标传输 | 4；counter两项、saved两项，未给pool排除证明 |

四个直接命中为857CC清saved、85808恢复counter、8580A清saved、8F74A写counter=1。
“没有固定数值pool写入”仅说明本保守图的地址常量不足，不能说pool没有writer。
对象句柄、循环计数、RAM重载、caller参数、计算地址、缺失入口、ARM、IRQ、BIOS及DMA
必须分别补域；8,785未知传输和5,877外部effects不能按非命中删除。

IWRAM物理别名规则按 region03 的32KiB镜像映射；word／half／byte先按4／2／1对齐。
例如word有效地址03000075实际落到03000074..78，覆盖counter byte。pool关键范围固定为
128×60、flags+0..4、group/slot/timer+14..1A、desc/seq+1C..24及callback+28..2C。
这里的may_alias_targets只表示直接物理字节；IO触发的DMA另保留义务。

规则参考mGBA commit `c16c3ff55585e71bee83c95539c2ecde15d728c8` 的memory.c、memory.h、
dma.c；原文件全文SHA与该commit的Git blob逐一匹配，摘录包含MPL2.0来源信息。
这是源码参考验真，**不是本次mGBA运行或实机验证**。

## 启动 DMA 的条件清零范围

boot root60FAC的60FB8..60FE0原指令窗口执行20条、8次word store，在人工SP03007000
把0放在[SP]，再配置DMA3 SAD040000D4、DAD040000D8、CNT040000DC。

| trigger | command | 条件模型效果 |
| --- | --- | --- |
| 60FCA | 85010000 | count低16=0解释为65,536word，02000000..02040000 |
| 60FDC | 85001EC0 | 7,872word，03000000..03007B00 |

DMA3控制保留低5位maskFFE0，两项有效control均8500：immediate、32bit、source fixed、
destination increment。第二项覆盖counter75、saved5E2D和pool3BB8..59B8，**不覆盖
IWRAM最后7B00..8000**。CPU trace只写寄存器，不模拟DMA实际传输及完成后的enable清除。
单独效果模型要求source word为0、source在有效RAM、没有外部改写、目的范围不越界；
不证明这些前提在全部自然入口成立。非零source和repeat控制变异都明确拒绝。
trace SHA `fcf27c97c4e0b52cc7c8ff67eca56ee626312f8d91a3d03cd51fae7e9df3e49a`。

fresh boot verifier重建583指令／125block／2frontier；其历史1,522B不是本次净增。
不能把条件启动清零等同于后续counter二值域或对象残留字段永远为零。

## 向量接口、counter别名与直接producer

v14原根624C0注册、62510恢复default，都先把argument截断u8，再以index×4访问
03000000..03000400。注册624F8写R1，恢复6251C写 **08061535**，是Thumb callback61534。
只有index29的word03000074..78覆盖counter75；注册12345678时counter=56，恢复时=15。
人工矩阵两接口×256索引共512态；其余索引保留counter=A5，高字节截断也测试。

61538原初始化给向量0／1／2填08061535。三个default状态测试覆盖恢复后IE04000200
清bit1、DISPSTAT04000004清bit4；注册路径在原三个entry均default时反向置相应位。
全ROM逐halfword BL/B/Bcond形态分别2／3项，五项都在当前call模型中：

| producer | root | 固定R0 | 注册R1 |
| --- | --- | --- | --- |
| 64594 | 624C0 | 0 | 03005CE8 |
| 65234 | 624C0 | 2 | 03005D50 |
| 644F2 | 62510 | 0 | — |
| 6452C | 62510 | 0 | — |
| 65258 | 62510 | 2 | — |

两根odd Thumb pointer全ROM逐byte出现均0。fresh v14 bundle重建5producer／2root、
60指令／10block／14内部block edge；624FE、62546两处indirect return frontier保留。
当前直接调用都避开29，但计算／间接／ARM producer、RAM目标与自然调用链未穷尽，
**不是全局有效index只0/2的证明**。历史160B不重复认领。

## 保存区初始化与候选producer

既有工作图root857B8..857D0有五个STRB0：857BC→5E4A、857C0→5E4B、857C6→5E49、
857C8→5E48、857CC→5E2D；counter保持原值，857CE BX LR返回。人工raw trace已复现。
该根全ROM直接形态858E0／85A22／85CDC／870A8，后3个是call模型成员，858E0仍是
未证明候选；odd Thumb pointer全ROM出现0。raw形态不能冒充自然producer闭包。

前包counter候选68DE6、85880仍未晋升；858E0候选关联8584C保存流程值得联合追踪，
需要可绑定的源分区、producer与callee边界后才能证明save→restore的自然生产域。
本包不把saved初始化的局部证明扩展成全部生产者穷尽。

## TDD、失败与永久复验

7项初始store测试先因模块缺失red，再green；追加root／传输保留测试9项时root_set缺失
正确red，再green；追加两项跨BL覆盖回归后cover_range缺失正确red，最终11/11。
向量／DMA／保存初始化5项先缺模块red，再green。版本对应关系在tdd-version-map.json。

第一版主集成明确失败并保留：coverage片6347E是BL6347C..63480的后半，99D70是
BL99D6E..99D72的后半。现在复用完整来源partition覆盖这两条claim，不发明后半入口；
没有受证完整prefix的partial instruction继续拒绝。**调查工具的切片分区问题已修复**，
不是游戏BUG。错误脚本、日志、guard及最小版本全部保留，不覆盖历史失败。

主盘点71.18s／419.59MiB，联合验证11.40s／154.03MiB；永久目录联合重放80.76s／
418.88MiB，均显式同heavy.lock、非降级exit0。永久重放把两批放在独立进程，避免
已加载module集合污染第二批的输入分母；三份权威输出逐字节相同，16项测试与两组
独立来源verifier通过。两个owned run均completed。新增脚本AST与行尾检查通过。

在逆向工作树根选择新的CHECK_UNIQUE，约两分钟复验，不改历史目录：

```sh
python3 tools/experiment_workspace.py --root . init --task animation-writer-domain-replay --run-id CHECK_UNIQUE
python3 tools/run_guarded.py --lock-file build/experiments/heavy.lock --summary build/experiments/active/animation-writer-domain-replay/CHECK_UNIQUE/guard.json --wall-timeout-s 300 --idle-timeout-s 120 --max-tree-rss-mib 1536 -- python3 notes/evidence/rom-animation-writer-domain-20261001-v1/replay_receipt.py build/experiments/active/animation-writer-domain-replay/CHECK_UNIQUE/output build/experiments/active/animation-writer-domain-replay/CHECK_UNIQUE/replay.log
python3 tools/experiment_workspace.py --root . complete --task animation-writer-domain-replay --run-id CHECK_UNIQUE
```

## 下一联合里程碑与完成边界

1. 把68DE4、8584C保存流程及858E0的raw producer统一做来源／上游合同，接已有857B8
   init和857E4 restore；候选不能因指针形态或线性显示晋升。
2. 与IRQ RAM5CE8／5D50、9项ARM/mixed排除和BIOS/DMA写入边界联合，归并未知store的
   地址来源；不能为了清空8,785计数而把caller指针或SP强设安全域。
3. 将合法object handle／group/slot/timer、两个callback、callee恢复及两层sentinel闭合
   后再提bank候选。31双字段／16缺口是之前的条件统计，本批未重新重算。

先复用已有source与整批工作图，仅在根合同改变时统一更新；不逐个store拆微实验，
不为promotion=0重跑完整formal。启动条件、全writer／自然域或关键alias不能证明时
保留开放，资源守卫拒绝则保存失败并停止扩张。

canonical SHA保持 `b568db6f2509ff67f214f7b17b4265dffec8d5c4207df2de997ba0a858cf06d2`，
未知87,631B；proof SHA保持 `465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568`；
bank SHA保持 `f52524fbba244cf0497ffa021503702da9a185485c13027872f2a65dad56bed2`。
175 blockers和107/97合同通过是历史正式结果，本包未重跑formal。mGBA、hardware、
canonical promotion及新增Tier-1均0。未提交／push，Butano未改；Goal active，周剩31%，
20%预算边界继续有效。

### 【功能特性】
- 从本记录进入永久收据，可查看启动清零范围、两向量接口全部u8索引及关键写入分母；仅用于逆向。

### 【BUG 修复】
- coverage切片从BL后半开始时被当完整入口、导致盘点失败 → 复用完整来源分区，未受证partial继续拒绝；工具问题已修复。

### 【验收清单】
- [x] 查看summary.json → 88,472声明指令、9,730传输、8,785未知地址；全writer仍false。
- [x] 查看coupled-writers.json → 向量slot29影响counter，5个已知caller仅0/2；DMA第二范围止于7B00。
- [x] 按上述命令新目录复验 → 16tests、512索引态、2来源verifier及三份输出精确重建，非零source／unsupported DMA拒绝。
