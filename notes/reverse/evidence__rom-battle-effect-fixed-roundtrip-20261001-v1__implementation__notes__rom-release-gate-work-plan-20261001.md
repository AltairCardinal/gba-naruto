# 资源写回与发布门禁：实际重放及剩余路线

> 2026-10-01 [四类部分 bank 集中复验](../notes/rom-partial-bank-joint-matrix-20261001.md)与
> [battle-effect 全固定变异写回](../notes/rom-battle-effect-fixed-roundtrip-20261001.md)完成：
> 141 输入／4 CLI／8 假声明拒绝，候选4/811单元；全bank门仍拒绝，正式0 typed保持。
> 容量证据按当前身份独立双重重建，语义不变；51输入、34content/35slots/36refs贯通35个
> 真build CLI，23接受（24slots/24refs）、11容量拒绝不发布输出；22相关测试、53文件目录
> 迁移全result精确一致。固定变异／无DB／无runtime，未完成graphics整体release case。
> 下一里程碑转map resource 166/217/249第二族，先审mutation合法域，再复用fixture/CLI，
> 域拒绝与容量拒绝分别记账；不继续逐字段微包。canonical／proof／bank不变，Goal active。

状态：本次约3个百分点周额度授权下的只读研究。复用七组固定slot writeback verifier，
没有生成新ROM、改历史artifact或执行UI/模拟器实验。永久收据在
`notes/evidence/rom-release-gate-work-plan-20261001-v1/`。
ROM/coverage/proof仍为既有基线；proof SHA
`465a13104b6c9a6d0ea418ca513dd0be732438634f1124a3a531c893b11db568`。

## 实际执行结果

同一个heavy lock下串行重放七个既有只读命令，逐命令保存stdout/stderr和exit code：

| 资源族 | exit code / verified | 能复用的分母 |
| --- | --- | --- |
| menu/story portrait | 0 / true | 74 resource |
| map resource | 0 / true | 166 content / 217 physical slots / 249 logical references |
| battle-effect | 1 / false | 34 content / 35 physical slots / 36 logical references，implementation mismatch |
| BG resource | 0 / true | 31 content / 36 slots / 36 references |
| character palette | 0 / true | 250 resources / 48 palettes / 342 slots |
| character graphics | 0 / true | 250 resources / 2,190 components / 342 slots |
| character structure | 0 / true | 250 resources / 2,190 components / 3,187 keyframes / 342 slots |

外层research脚本exit0表示七个子命令均完成并记录，不表示7/7通过；实际为6/7。
guard非降级，约9.3秒、峰值44.17MiB。上表三种character表示共享资源分母，不能相加
冒充750种不同资源。固定slot审计也不覆盖任意修改、容量增长或自然runtime行为。

## 失败项定位与恢复方法

battle-effect payload的7项implementation身份中，只有
`tests/test_import_battle_effect_resources.py`不符：
历史SHA `1331e9586a1d46fef82931a2c1bc4c2bee63fd30d6df382b3e41698561f38293`，
当前SHA `a6e8519ff82f5b719e57bcbe0b04fd090f881aba20e1c0ad309cd131a4598583`。
其余六项含exporter、verifier、importer、build_mod和VRAM测试身份均匹配；verifier此次
没有报告resource records或scope差异。因此不能把本次失败说成资源内容已损坏，也不能
因为只是测试身份变化就豁免身份合同。完整对照见implementation-drift.json。

后续恢复应在新受管run中以当前测试重新生成一个替代证据包，复用旧资源目录与
独立 `_expected_payload` 重建；独立验证resource/mutation/alias/容量边界及输出成员身份。
先做相关失败关闭和真实发布集成TDD，再按里程碑接入；旧payload和manifest原封保留，
新旧关系记录为supersedes，禁止直接刷新旧hash。没有必要因这一离线身份差异重新跑
同一份mGBA捕获，但新证据不可声称本轮重新验证了runtime。

## 七门的推进依赖

1. **资源round-trip（固定7case）**：先修复上述失效证据和typed合同，再补audio/text/
   maps/levels/story/characters对应的完整提取→修改→编码→回写→重读矩阵。六组图像族
   通过不能直接把graphics整个case标covered，更不能代表另外六case。
2. **干净重建（固定3case）**：先冻结可提交输入闭包、ROM外部供给/hash、toolchain
   版本与锁定依赖。在独立干净checkout重建全部提升产物和最终ROM，第二次独立输出
   比较完整bytes/SHA。当前`automated_test.py --suite build`会调用build_mod并写项目
   声明的输出，不是只读审计，也不证明clean-checkout；本轮明确未运行它。
3. **逻辑修改（固定2case）**：菜单/战斗分别建立baseline/candidate行为断言与输入
   路径。旧patches suite验证字节应用、大小/header等，不能代替行为变化归因。
4. **模拟器回归（固定2case）**：固定base/rebuilt同一验收面、合法输入与状态快照。
   复用现有guarded捕获与raw archive；单场controlled素材不能代表完整回归矩阵。
5. **编辑器round-trip（固定4case）**：按项目“逆向先行、编辑器后建”约束，依赖相应
   数据格式稳定和重建可用后再做UI→DB→ROM→启动→读取的端到端案例；db_integrity
   只验证镜像/patch完整性，不是UI wiring验收，不把测试suite名字当完成证明。
6. **实体硬件（固定1case）**：准备release ROM/input/hash和预期检查表，再由实体GBA、
   flash cart及原始采集完成。当前环境缺硬件证据，保持blocked_external；模拟器或
   人工文字确认都不能替代原始硬件证据与独立验真。

上述六门共19个固定case，当前case_ids_covered均为空；字节覆盖门另外要求unknown=0。
每门还要typed合同绑定 `/gate_cases/<name>` 与 `/gate_evidence/<name>`，全部case/evidence
身份准确并实际重放；无合同的exit0不足以验收。case名单不因当前难度而删减。

## 下一轮最值得投入的闭环

静态路线先完成已有renderer delta的完整合同；运行时路线先迁移map-sprites样本合同。
两者分别积累各自完整证据，不能把不同信任边界合并凑审计次数。资源路线优先处理
battle-effect测试身份失效这一明确、有限的恢复点，再建设可重复clean checkout。
有新函数实现或发布/adapter变更时必须TDD及集成测试；研究预检不替代验收。
不继续反复全量formal来验证已知175 blockers，门禁有实质新证据时才按里程碑审计。

## 验收与边界

- [ ] 查看report.json → successes=6，battle-effect子命令exit1、verified=false。
- [ ] 查看implementation-drift.json → 仅测试文件SHA不同，旧manifest保持。
- [ ] 查看proof固定集合 → 六门19case仍为空，硬件blocked_external。
- [ ] 查看后续依赖 → 离线证据恢复与clean rebuild先行，UI和硬件在依赖满足后验收。

本轮执行七项资源独立verifier并做逐输入哈希检查；未做功能TDD、UI测试、新runtime、
clean build或全量formal。文档链接/格式及canonical/proof未变检查通过；未提交或push。
