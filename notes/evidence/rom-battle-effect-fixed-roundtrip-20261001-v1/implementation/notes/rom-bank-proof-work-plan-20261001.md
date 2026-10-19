# 有效bank严格完成债务与验收复用路线

> 2026-10-01 [四类部分 bank 集中复验](../notes/rom-partial-bank-joint-matrix-20261001.md)与
> [battle-effect 全固定变异写回](../notes/rom-battle-effect-fixed-roundtrip-20261001.md)完成：
> 141 输入／4 CLI／8 假声明拒绝，候选4/811单元；全bank门仍拒绝，正式0 typed保持。
> 容量证据按当前身份独立双重重建，语义不变；51输入、34content/35slots/36refs贯通35个
> 真build CLI，23接受（24slots/24refs）、11容量拒绝不发布输出；22相关测试、53文件目录
> 迁移全result精确一致。固定变异／无DB／无runtime，未完成graphics整体release case。
> 下一里程碑转map resource 166/217/249第二族，先审mutation合法域，再复用fixture/CLI，
> 域拒绝与容量拒绝分别记账；不继续逐字段微包。canonical／proof／bank不变，Goal active。

> 2026-10-01 [data-table-b 部分字段合同／可移植重放](../notes/rom-data-table-b-partial-bank-20261001.md)完成：
> 22 固定输入、1/79 text_ptr 单元、928 像素，23 相关测试与真实 auditor CLI 通过。
> 24 文件目录迁移在禁止源工作树／旧 Qt 读取及进程启动下仍精确重放；旧 manifest 不改。
> 两历史采集没有零输入对照和外层共享锁身份，限制明确保留；全量 bank gate 仍拒绝。
> 下一里程碑集中重放四类 partial 合同的 record×field 矩阵与依赖，不继续逐像素拆包，
> 再选择小 bank 完整矩阵／资源 round-trip 入口。promotion=0，canonical／proof／bank不变，
> Goal active，最近周剩25%，用户允许推进至剩20%。

> 2026-10-01 [menu-ui 指针隔离与新收据](rom-menu-gfx-pointer-ab-20261001.md)通过：
> 旧内容样本用当前 renderer 重算/独立双验，payload 相同且旧 artifact 不改；新 record1/
> gfx_ptr_0 是独立指针 A/B，40 输入、43 raw 成员、5 个 c16 正确锁捕获、1 像素、1/630 单元。
> 26 项相关测试、受管发布、双重独立重建与真实 auditor CLI 通过，全 bank 仍拒绝。
> EWRAM 前128B只固定观察身份，语义未解；canonical/proof/bank-proofs 与正式0typed保持。
> 下一主线返回458混合池 flags/slot，旧 primary 的合同迁移留待批量，避免继续拆单像素包。

> 2026-10-01 [cutscene 自然调色板部分合同](rom-cutscene-secondary-ptr-contract-20261001.md)
> 已完成：45 固定输入、43 原始成员、8×2 完整分母中的 ID 1 / secondary_ptr 单元；
> 三零输入与两单输入由正确共享锁重跑，778 像素且只改 PRAM 一字节，31 相关测试通过。
> 独立双重重建、受管发布和真实 auditor CLI 通过，完整 bank gate 仍拒绝部分覆盖。
> 旧捕获错误锁与笔记地址错误已明确取代/更正；canonical/proof/bank-proofs 未变。
> 下一步 menu-ui 新冻结样本及旧 primary 的部分合同迁移；458 动画 flags/slot 仍待闭合。
> 下方保留阶段历史；早先“捕获完成、语义验收待补”已由本条取代。

> 2026-10-01追加：[11命令实际重放](rom-bank-runtime-replay-20261001.md)10/11通过，
> menu-ui仅renderer SHA漂移；cutscene secondary_ptr已有隔离输入/自然捕获，独立验收仍待补。

> 2026-10-01更新：[部分合同 canary](rom-map-sprites-partial-bank-20261001.md)已实现，
> 19测试和真实CLI通过；仅1/86单元，离线proposal尚未接入。下述0typed是原正式矩阵。

状态：冻结清单研究，不修改bank proof声明、不新增runtime样本；仅重放一份既有map-sprites
离线证据。模式为固定公开合同下的身份/分母清单重建，脚本优先，无子代理。
永久收据：`notes/evidence/rom-bank-proof-work-plan-20261001-v1/`。

## 核对结果

从32-bank固定集合排除10个disproved后，22有效bank共2,954记录，声明覆盖23记录。
所有22份bank文件SHA均匹配proof，证据引用与11条verifier源码身份本轮核对全部匹配。
因此当前问题不是这些引用丢失，而是证明覆盖范围和严格机器合同不足。

| 目前的债务 | 数量/范围 | 后续动作 |
| --- | --- | --- |
| 有verifier command | 11/22 bank | 复用原始archive重放能力，但不能直接增加covered数字 |
| 缺结构化contract | 22/22 bank | 新typed verifier输出绑定record/field IDs、bank SHA与evidence SHA；单条样本只声明单条 |
| 字段总分母不吻合schema | 6/22 bank | audio、battle-config、levels、positions、sappy-engine、units；先冻结字段ID映射和布局，不扩张已覆盖字段 |
| verifier command含机器绝对路径 | 3 bank | data-table-b、levels、sappy-engine；恢复可复现toolchain身份和可移植运行入口，不仅删除参数 |
| 没有独立verifier command | 11 bank | audio、battle-config、character-stats、data-table-a、function-pointers、positions、save-state、skills、story、story-b、units；先把旧观察变成可复验原始证据 |

字段具体差异：battle-config声明byte_0c，而schema是growth_target_type；levels遗漏reserved1。
audio、positions、sappy-engine、units的总分母仍写unknown，但schema已有字段列表。
不得凭“名字现在对齐”把runtime coverage变成exhaustive；保留原证据的适用范围。
schema按现有审计器 `_schema_field_ids` 计入derived ID、raw_hex及重叠视图，矩阵合
25,543个记录×字段格。这是验收维度，不是物理字节数，也不是必须运行25,543次模拟器；
原始archive、共同消费者证明和受控批量调用可复用，但必须对每个ID/字段给出可验证结果。

## 已实际重放的可复用种子

运行`tools/verify_map_sprites_definition_pixel_ab.py --root . --artifact
artifacts/map-sprites-definition-id1-pixel-ab-v1`，guard exit0、非降级，峰值40.09MiB。
原始tar、implementation、内存差异和图片归因均通过，输出entry_id=1、changed_pixel_count=213、
bbox=[178,64,215,71]。未启动mGBA，重放的是已有controlled-materialization证据。

这份输出没有field IDs、bank SHA、evidence SHA等严格合同字段；成功只验证record1的
definition_ptr旧样本，不证明43×2字段、自然入口、animation_ptr或编辑安全。
本轮不能称11个verifier都重放通过：仅身份全部核对，执行只有上述一个。

## 下一阶段应如何拆包

1. **先做证据合同迁移包。** 以map-sprites旧样本为首个canary，新增wrapper/typed结果
   时先写RED：缺field/record ID、错误bank SHA、archive变化、错路径及普通verified=true
   都必须拒绝。GREEN只能声明record1/definition_ptr；只有证明覆盖整个固定分母才能
   合同化exhaustive。旧manifest不改写，新增证据绑定历史身份并保留控制路径限制。
2. **再做小bank完整矩阵。** cutscene-scripts为8records×2fields，且前四条是gfx/palette，
   后四条是definition/animation，必须分消费者验证，不因同stride共用语义。map-sprites为
   43×2，已有raw archive/内存/OAM/像素因果链，适合第二个批量矩阵。先复验各自种子
   和每类资源解码边界；暂不保证所有ID都有自然导航路径，controlled证据分别标记。
3. **文本bank共用parser与显示验收。** data-table-a46×1、data-table-b79×1，可复用已有
   静态parser closure与文本显示差分；前者尚缺独立runtime verifier，后者命令有绝对
   binary路径。先修复可复现证据路线，不能仅复用全部ROM fidelity来声明125条自然可达。
4. **大运行时簇统一调查。** positions占1,728records，不要派发1,728份独立实验。与
   main/extra单位池、formation索引、AI writer沿用同一生命周期模型；units、成长字段和
   skills同样按共享消费者整批。可批量验证内容物化与字段影响，但其证据类型不能混同。
5. **save-state单独验收。** 10×2字段必须覆盖有效/空槽、长度、校验与冷启动恢复，
   先把旧save/load观察归档成独立verifier。不能只验证buffer地址和记录数就称持久化完成。

这些包不依赖unknown全部清零才能准备合同/复验已有种子，可与字节调查按里程碑交替。
动态运行仍需可恢复快照、零输入对照、单次单输入与同heavy lock。下一阶段首次运行前
重新检查Goal/额度/Git，资源守卫拒绝或身份漂移时停止，不复制脏工作树材料到Butano。

## 验收与边界

- [ ] 查看matrix.json → 22banks、2,954/23、11commands、0typed contracts、6字段分母差异。
- [ ] 查看map-sprites-result.json → entry1/213像素；不能解释成43条全通过。
- [ ] 查看inputs与manifest → 每项身份匹配，absolute command保留为调查事实。
- [ ] 后续实现先写失败合同/集成测试 → 任意错ID/哈希/来源均不可合并。

矩阵脚本两次稳定重放、输入身份/布局计数及语法/文档检查通过；只读研究没有生产功能
变化，不声称功能TDD或全量formal。未修改ROM、bank-proofs、canonical/proof，未提交。
