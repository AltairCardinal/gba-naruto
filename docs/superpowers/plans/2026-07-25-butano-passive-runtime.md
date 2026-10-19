# Butano 被动内容与逐击修正运行时实施计划

**Goal:** 把 ROM 已确认的 45 条被动成长记录、角色 24 个被动槽和首批真实消费者接入
共享战斗运行时，使被动不再只是内容目录里的原始数据；逐 hit 会心与无视防御必须按原作
顺序查询、抽 RNG、选择伤害候选并留下可审计事件。

**Architecture:** `battle_passives.h` 提供固定 24 槽的角色被动状态、按 target type
首项命中的查询，以及 `base + per_level * (level - 1)` 值对。生成器只把
`sequel/content/levels/bank.json` 的 45×12 字节 ROM 真值转成
`generated_battle_passive_content.h`。`battle_unit_instance` 持有可变被动槽；
`instantiate_unit` 复制模板初始状态，不臆造训练结果。伤害 resolver 在每个基础命中后
条件查询 type `0x0C`、再查询 type `0x19`，只在对应被动存在时抽附加 RNG，并按 flag
选择普通/会心、计防御/无视防御四候选。

**Evidence boundary:** 本里程碑只实现已经由
`0x0806DDA4`、`0x08076034` 和受控运行样本闭合的规则。其余 target type 先完整建模、
可查询、可升级，但保持“消费者待证”，不得根据名称原始字节或数值形状猜效果。被动
显示名仍为自定义字库原始字节，不能伪造中文转写。

**Constraints:**

- 复用 `battle_unit_instance`、`battle_action_resolver`、`deterministic_rng` 和现有生成器
  模式，不创建关卡专用被动系统。
- 运行时槽严格固定 24 项；ID 0、level 0、level `0xFF` 都不参与查询。
- 同 target type 有多个活动槽时返回槽顺序中的第一个。
- 预览只能展示无随机修正的普通计防御基础值，不提前消耗 RNG。
- 所有改动先 RED、再最小 GREEN、最后重构；不提交、不推送。

---

## Task 1：固化 ROM 被动查询证据

**Files:**

- Create: `tools/analyze_battle_passive_query.py`
- Create: `tests/test_analyze_battle_passive_query.py`
- Create: `notes/battle-passive-query-bindings-20260725.json`

- [x] 先写失败测试，要求 manifest 固定 ROM 哈希、函数范围
  `0x0806DDA4..0x0806DE15`、45×12 表范围、24 槽步进、无效 level 规则、首项命中与两值公式。
- [x] 运行测试确认因 analyzer/manifest 缺失而 RED。
- [x] 实现 analyzer：逐字节校验查询函数与表，读取 45 条记录，输出确定性 manifest。
- [x] 生成 checked-in manifest，重跑测试至 GREEN。

## Task 2：生成完整被动内容表

**Files:**

- Create: `tools/generate_butano_battle_passive_content.py`
- Create: `tests/test_generate_butano_battle_passive_content.py`
- Create: `butano-sequel/game/include/konoha/generated_battle_passive_content.h`
- Create: `butano-sequel/game/include/konoha/battle_passives.h`

- [x] 先写失败测试，要求 45 条 ID 连续记录、原始字段完整、ID 9/type `0x0C` 和
  ID 20/type `0x19` 精确值、生成结果确定。
- [x] 运行测试确认 RED。
- [x] 实现最小生成器与固定容量领域类型；生成 checked-in header。
- [x] 加入宿主测试，锁定 24 槽、无效 level、首项命中、A/B 成长公式和越界 ID 安全失败。
- [x] 重跑 Python 与宿主测试至 GREEN。

## Task 3：把角色 secondary 槽实例化为战斗状态

**Files:**

- Modify: `butano-sequel/game/include/konoha/battle_session.h`
- Modify: `butano-sequel/game/include/konoha/battle_unit_content.h`
- Create: `butano-sequel/game/tests/test_battle_passives.cpp`
- Modify: `tests/test_generate_butano_battle_unit_content.py`

- [x] 先写失败宿主测试：Sakura 的 ID 26/level 1 与 unit 62 的 level 3 槽被复制；
  Naruto 的 `0xFF` 与敌人 level 0 槽保持未激活；运行时可由训练/存档层显式改写。
- [x] 编译确认因 `battle_unit_instance` 尚无被动状态而 RED。
- [x] 加入紧凑 24×2-byte 状态并在 `instantiate_unit` 中复制 ROM 初始状态。
- [x] 断言被动状态尺寸预算，重跑相关宿主测试至 GREEN。

## Task 4：实现逐 hit 会心与无视防御

**Files:**

- Modify: `butano-sequel/game/include/konoha/battle_action_system.h`
- Modify: `butano-sequel/game/tests/test_battle_action_system.cpp`
- Modify: `butano-sequel/game/tests/test_battle_multi_target_action.cpp`

- [x] 先写失败测试：无被动只抽基础命中 RNG；type `0x0C` 在每个基础命中后先抽会心；
  type `0x19` 后抽无视防御；100% 样本分别选择 flag 2 与 flag 5。
- [x] 测试四候选公式：普通计防御、会心计防御、普通无视防御、会心无视防御；逐 hit
  结果保存 flag，不能只保存总伤害。
- [x] 编译运行确认 RED。
- [x] 实现最小 `HitDraft`/modifier 查询与条件 RNG；单目标、范围目标均走同一 resolver。
- [x] 重跑聚焦测试和全部宿主测试至 GREEN，重构重复候选计算。

## Task 5：ARM 与跨关卡验收、持久化边界

**Files:**

- Modify: `notes/butano-battle-domain-rewrite-20260723.md`
- Modify: `notes/battle-system-restoration-evidence-20260723.md`
- Modify: `docs/sequel-roadmap.md`
- Modify: `tools/README.md`

- [x] 运行相关 Python 测试、全部宿主 C++ 测试、格式检查和 `git diff --check`。
- [x] 通过 `tools/run_guarded.py` 构建 ARM ROM，检查 ROM/ELF 哈希和 IWRAM/EWRAM 预算。
- [x] 通过守卫重放 battle 09、scenario 41、scenario 43，确认无回归；自动化保持静音，
  不宣称音频已验证。
- [x] 文档明确：45 条被动已进入通用模型；当前只闭合 type `0x0C` 与 `0x19` 的战斗
  消费者；其他 target type、训练 UI 与被动显示名仍是后续 Goal，不把本里程碑误报为
  完整战斗系统完成。

## 实施补充：ARM 事务工作区

被动状态令每个 `battle_session<12>` 增长后，mGBA 运行证据暴露了此前宿主测试无法看到的
嵌套大对象栈问题。最终实现把 scenario/map 加载候选，以及玩家命令全过程使用的
session/player-flow 候选统一迁到 `battle_encounter_runtime` 的 EWRAM 工作区；动作解析
在该唯一候选上使用显式 `*_in_place` 内层，不再让 resolver、turn-flow 各自嵌套复制整份
session。对外事务语义保持“失败不提交”。

最终证据：

- ROM SHA-256 `02cd264c7fa3b9c4efd86559cfebb56bafe99da4a9a18dec7750166faf6d7080`；
- ELF SHA-256 `91cb32ac39acb713e84940883561484db170209532085d58b3ff7d472c36e140`；
- `.iwram` 8,840、IWRAM `.bss` 2,172、EWRAM `.ewram` 224、
  `.sbss` 169,960 字节；
- 60 个宿主 C++ 程序通过；
- `artifacts/butano-action-workspace-runtime-b09-full-20260725-26/` 在第 996 帧进入
  battle 9 第 2 回合，活动单位为 9；
- scenario 43、battle 9 多单位基线、scenario 41 三条路线均通过；
- `mp_mix_seg` 连续 20 帧写监视只见 Maxmod 自身的单字节 `00/FF` 翻转。
