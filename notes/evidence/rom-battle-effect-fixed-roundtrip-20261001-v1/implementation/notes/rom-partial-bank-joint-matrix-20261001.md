# 四类部分 bank 合同集中复验

## 结果

141 个固定输入（46,045,517B）前后身份一致，四类部分合同从永久证据目录重放通过。
候选分母是 193 records / 811 record×field 单元，实际覆盖 4 个，未覆盖 807 个。
全局 live 分母仍为 22 有效 bank / 2,954 records / 25,543 schema 单元，声明覆盖 23 条，
正式 typed bank 合同 0。候选与 live 数字分别保留，不相加冒充新增自然覆盖。

| bank | 固定单元 | 分母 | 变化像素 | 证据边界 |
| --- | --- | ---: | ---: | --- |
| map-sprites | 1 / definition_ptr | 86 | 213 | 受控物化，非自然 loader 重入 |
| cutscene-scripts | 1 / secondary_ptr | 16 | 778 | 固定胜利 palette 加载，三零输入对照 |
| menu-ui | 1 / gfx_ptr_0 | 630 | 1 | 固定头像加载，三零输入对照；scratch 前缀语义未解 |
| data-table-b | 0 / text_ptr | 79 | 928 | 历史两采集，零输入与共享锁身份未验证 |

cutscene 的旧 primary_ptr 样本是同一 record 1 的另一字段，不将其算为第二条记录。
本包也不把旧 primary 观测自动加入新 secondary 合同。四种控制路径各自保留限制，
不会通过统一矩阵被提升为同一种自然路径或硬件证明。

## 方法和可复用链路

按登记表“固定有效 bank 旧 runtime verifier 分母重放与身份漂移定位”使用脚本，
扩展到已经冻结的 typed partial proposal，无子代理。每项复用原 verifier/proof_binding、
auditor 的 _check_bank 与 _execute_contract；cutscene/menu 从 receipt 内 accepted final
重放，不依赖可清理的 build/experiments 目录。旧 manifest 中的历史命令保持原样，
新 proposal 的 evidence 路径绑定本次实际永久位置。

从 bank schema 重建全单元分母，验证覆盖 ID/字段集合、无重复、未覆盖差集与数量；
保存真实 CLI stdout/stderr，逐字段比较 contract assertions。每项另外用全量 ID 声明及
physical_gba_verified=true 两个错误断言执行 auditor，共 8 个反例均拒绝。
四个 CLI 合同均 contract_ok=true；四个 full-bank gate 均 complete=false，局部 blockers
分别 5/5/5/4。没有声称全局 formal 的 blocker 数量已减少。

受管 run=partial-bank-matrix/four-bank-20261001-v1，同 heavy lock，51.67s，148.68MiB，
非降级。研究脚本没有新增产品功能，不声称功能 TDD；原四 wrapper 的 TDD 记录分别
保留在各自包。语法、空白、固定输入 SHA 和全字段矩阵检查通过。

## 持久证据、下一动作与验收

[永久 receipt](evidence/rom-partial-bank-joint-matrix-20261001-v1/)保存 plan、matrix.py、
每项结果/proposal/stdout/stderr、8 个错误断言与 guard；manifest SHA=
aa30d6a3714d55f3b213580d9403a6eea0812886bbfc1720f4b762a4875f046e。
matrix.py 可在逆向树内用 --root/--plan/--output 指向新的受管目录复验；输出已存在时
拒绝覆盖。仅是离线复验，没有新 runtime、ROM 分类或正式 bank catalog 写入。
canonical/proof/bank-proofs 三个身份未变，unknown=87,631B；175 blockers 是历史 formal。

共同依赖可以复用，真正缺口是消费者与完整 record×field 域，不能靠更多重复签发消除。
资源路线优先修复已定位的 battle-effect 测试身份漂移，并贯通全部 34 content /
35 physical slots / 36 logical references 的固定导入→构建→重读矩阵；然后按资源族
批量推进 round-trip，避免继续逐像素或逐 record 拆包。自然全域与实体硬件继续独立。

- [ ] 打开 matrix.json → 4/811 单元、807 未覆盖，四类边界各自列出。
- [ ] 查看 cases/*/matrix-row.json → CLI 通过，完整 bank 门拒绝，两条假声明拒绝。
- [ ] 查看 global_inventory → 22/2,954/25,543 与 live typed=0，没有叠加候选记录数。
