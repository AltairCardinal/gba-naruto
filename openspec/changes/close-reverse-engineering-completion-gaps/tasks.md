## 1. 前置依赖与安全基线

- [ ] 1.1 读取前三个 change 的验证报告、证据哈希和当前 bank 状态，生成可机器复核的依赖基线；任一依赖未完成时记录 `not_proven`，但不伪造最终通过
- [ ] 1.2 盘点当前 80 个有效 audio cue、legacy CRUD/mirror 字段、玩家可见字段与 32-bank 权威清单，保存本 change 的输入版本和缺口清单
- [ ] 1.3 先写 dependency/baseline 缺失或状态漂移时失败的红测，确认因正确原因失败，再实现最小依赖门禁并重构复验
- [ ] 1.4 核对 mGBA 快照索引、ROM/状态哈希与 `run_guarded.py` 共享锁/owned-tree 清理入口，记录实施前系统内存基线
- [ ] 1.5 同步基线调查到 `notes/` 与路线图，运行聚焦测试后形成首个独立提交并推送远端

## 2. Audio cue 语义闭合

- [ ] 2.1 先为语义账本 schema、有效 ID 精确覆盖、证据字段、`official_name_known` 和 unknown fail-closed 规则编写红测并确认失败原因
- [ ] 2.2 最小扩展 audio cue 提取/审计工具与持久账本，使 80 个有效 ID 可逐项登记、校验和报告，再重构并重跑测试
- [ ] 2.3 先扩展运行时 probe 的失败测试，再实现 cue ID、调用 PC、事件状态、输入/快照和结果哈希采集；所有重放经过资源守卫
- [ ] 2.4 建立按自然事件分类的 mGBA 快照索引，优先复用离目标调用最近的状态，并验证 control/variant 使用相同 ROM 基线和快照
- [ ] 2.5 闭合 unknown cue 1、2、3、5、6：每项取得两个一致自然实例或单因素 A/B，并更新账本与持久证据
- [ ] 2.6 闭合 unknown cue 7、8、9、10、11：逐项保存 source addresses、玩家事件与复放哈希
- [ ] 2.7 闭合 unknown cue 12、13、14、15、16：逐项排除仅凭 player/track 家族或听感猜名
- [ ] 2.8 闭合 unknown cue 17、18、51、52、53、54：区分循环音乐与一次性 jingle 的具体玩家事件语义
- [ ] 2.9 复核既有候选 cue 4、101、102、103、104、105，使每项达到统一的两个实例或单因素 A/B 门槛
- [ ] 2.10 复核既有候选 cue 118、144，分别闭合具体 title/new-game 事件与 battle selector index 53 的实际动作
- [ ] 2.11 闭合 unknown cue 106–111，并将动态 selector 来源与具体玩家事件逐项关联
- [ ] 2.12 闭合 unknown cue 112–117，记录高频调用的语义一致性和任何冲突实例
- [ ] 2.13 闭合 unknown cue 119–124，先证明 selector 上游身份再赋予稳定调查语义
- [ ] 2.14 闭合 unknown cue 125–130，保持每个 ID 的运行时事件与 source address 可追溯
- [ ] 2.15 闭合 unknown cue 131–136，使用相同快照的隔离输入避免路线漂移
- [ ] 2.16 闭合 unknown cue 137–143，逐项区分共享 battle selector 中的具体动作
- [ ] 2.17 闭合 unknown cue 145–149，并对低频调用优先使用单因素 A/B
- [ ] 2.18 闭合 unknown cue 150–154，不可达或证据冲突时保留失败并继续调查，不降低门槛
- [ ] 2.19 闭合 unknown cue 155–158，并核对 system/gameplay 家族与实际事件边界
- [ ] 2.20 运行 80/80 覆盖审计，确认零 unknown、零重复、零无来源语义且所有非官方标签为 `official_name_known=false`
- [ ] 2.21 安排独立审查 audio 证据等级与命名边界，修正问题后同步 bank/notes/docs/roadmap、运行聚焦回归并提交推送该阶段成果

## 3. 玩家可见字段与语义写回

- [ ] 3.1 先写字段盘点完整性红测，要求 bank schema、UI/runtime reader、CRUD/API 和 generator 中的字段都被分类，且任何已暴露 unknown 字段导致失败
- [ ] 3.2 实现最小字段盘点/机器清单，分类 player-visible、internal、reserved、padding 与 unknown，重构后重跑测试
- [ ] 3.3 对 units 的未命名玩家可见字段逐项追踪 ROM record→template→battle/UI consumer，使用最近 mGBA 快照执行安全单因素 A/B 并固化证据
- [ ] 3.4 对 skills `+2/+3/+9` 及其他仍暴露的未命名字段逐项定位 consumer、编码和玩家可见结果，歧义项保持不可编辑
- [ ] 3.5 审计其余 bank 的 editor 字段与玩家 UI/行为消费者，闭合所有玩家可见 unknown 项并为 internal/padding 分类保存负边界证据
- [ ] 3.6 先为字段 codec 的合法往返、未修改位保留、范围/枚举/指针拒绝和 immutable-base 校验编写红测
- [ ] 3.7 按已证明字段族实现最小 serializer/codec，使单字段编码只改变声明字节；重构公共能力并重跑单元测试
- [ ] 3.8 为每个新 serializer 运行正式 build 单字段 diff 和同快照 mGBA control/variant，确认可见或行为差异方向符合预期
- [ ] 3.9 建立字段能力清单，使语义、serializer、build diff、集成测试或 mGBA 证据任一缺失时字段自动保持 denied
- [ ] 3.10 运行玩家可见字段覆盖审计，确认无已暴露 unknown、无无证据开放字段，并安排独立审查语义与写回边界
- [ ] 3.11 同步字段 schema、bank、notes、交接文档和路线图，运行聚焦测试后形成独立提交并推送远端

## 4. Legacy CRUD 与 ROM mirror 边界

- [ ] 4.1 先写 CRUD/mirror 全字段映射、默认拒绝、诊断无写入载荷和授权漂移的红测，并确认旧路径按预期暴露缺口
- [ ] 4.2 实现机器可读 legacy 字段能力清单，覆盖 battle config、units、chapters、skills、story beats、audio、maps、levels、character stats、battle_config_data、encounter zones 与 items
- [ ] 4.3 让现有 CRUD/API 和 generator 共享同一 allowlist/deny 决定；未知、无 serializer 或证据退化字段均返回明确错误或无 `offset/after_hex` 的诊断
- [ ] 4.4 逐项核对每个 allowlisted 字段的 mirror identity、索引、offset 公式、宽度、immutable-base bytes、范围/指针/长度约束与冲突域
- [ ] 4.5 为证伪 tombstone、历史错位别名和未证明 legacy 字段增加绕过 API 直接污染 DB 的回归测试，确认正式 build 仍不修改 ROM
- [ ] 4.6 先为每个恢复写入的字段族补 CRUD/API→隔离 DB snapshot→正式 build 的失败集成测试，再接通最小 wiring
- [ ] 4.7 对每个 allowlisted 字段族执行完整 mirror DB 单字段构建，断言 ROM diff 只包含声明范围、全局 DB/build 哈希不变且报告哈希匹配
- [ ] 4.8 故意破坏 CRUD 列、mirror identity、offset 和 serializer，确认对应集成测试均会失败且没有 silent skip
- [ ] 4.9 运行 legacy 边界覆盖审计，确认每个输入字段恰有一个 editable/denied 决定、无悬空映射和无旧模板/合成写入
- [ ] 4.10 安排独立安全审查 patch allowlist、immutable-base 与冲突门禁，修正后同步 notes/docs/roadmap、运行聚焦回归并提交推送

## 5. 最终 100% 完成门禁

- [ ] 5.1 先为 completion audit 编写红测，覆盖缺失前置 change、缺失证据、有效 bank 仍为 code/static、tombstone 非空、unknown cue/field、危险 CRUD 和 required test skip
- [ ] 5.2 扩展机器可读完成矩阵，逐行聚合 32 个结构的身份/边界、提取器、字段语义、写回、测试与运行时制品，并区分 `pass`、`fail`、`not_proven`
- [ ] 5.3 实现 23 个有效 `runtime_verified` / 9 个 `disproved` tombstone 的当前分布门禁；权威身份变化时强制同步清单、原因与计数后全量重审
- [ ] 5.4 聚合 audio 80/80、玩家可见字段和 legacy CRUD 边界报告，任何 unknown、unclassified、not_proven、哈希漂移或不安全写入均令 `completion_claim_allowed=false`
- [ ] 5.5 先写最终报告/交接/路线图与机器报告不一致时失败的红测，再实现文档一致性检查并重构复验
- [ ] 5.6 在全量运行前后检查系统可用内存；所有重型测试、build 和模拟器验收串行经过共享锁与 owned-process-tree 守卫并保存峰值摘要
- [ ] 5.7 在同一 commit/基准 ROM 上运行格式检查、全量 Python/Node/backend 单元与集成测试、正式 ROM build 和 completion audit，required 集成项不得 silent skip
- [ ] 5.8 从已追踪 mGBA 快照复放 scenario 41、levels、剩余 bank 与字段写回的代表性验收链，核对 ROM/状态/输入/结果哈希和资源报告
- [ ] 5.9 安排独立审查 32 行证据矩阵、全量测试覆盖和完成布尔逻辑；所有审查问题解决并重新验证前保持非完成状态
- [ ] 5.10 仅依据最终机器报告更新 `docs/final-completion-report.md`、交接文档和路线图；若任一门禁失败，报告明确列出缺口且不恢复 100% 声明
- [ ] 5.11 检查 `git status`、`git diff --check` 与变更范围，排除临时 mGBA/build 产物和无关用户改动，提交并推送最终审计批次
- [ ] 5.12 在已推送 commit 上复核远端分支、持久报告哈希和全部 required gate；只有全为 `pass` 时才设置 `completion_claim_allowed=true` 并进入 Comet verify/归档流程
