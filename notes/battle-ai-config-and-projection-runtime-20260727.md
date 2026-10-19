# 战斗 AI 配置与行动者投影评分闭环（2026-07-27）

## 结论

原作不是“所有敌人共用一套权重，再由关卡代码临时加分”。单位运行时字段
`unit+0xCD` 直接选择 `0x0853F348` 的一条 `0xA8` AI 配置；阵型内容中的
`unit_parameter` 正是这一配置编号的持久来源。Butano 先前只保存
`formation_unit_parameter`，没有写入 `ai_config_id`，导致正式关卡中配置 2–7 的 typed
规则全部不可达。本次已把阵型参数接入单位 AI 配置，并让 planner 同时按该编号选择公共
utility 权重和四个 scenario rule 槽。

行动者自身的 HP/查克拉评分也不是四项同时参与平均。原作
`0x080843DC..0x0808444E` 先加入 `weight[0x00] + weight[0x0C]`，然后 HP 与查克拉各自只
选择一个互斥分支：

- candidate 值严格大于 baseline 时，按增量/最大值使用 `0x04` 或 `0x08`；
- 否则按 candidate/baseline 保留比例使用 `0x10` 或 `0x14`；
- 两个资源分支合计只把 component count 增加 2。

Butano 先前把一个 base weight 二选一，又把 HP 生存、查克拉保留、HP 增益、查克拉增益
四项全部加入平均，因而会系统性改变移动、治疗、休息与补充查克拉之间的整数比较。本次已
改为原作的两分量互斥公式。

## ROM 证据

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- AI scorer：
  `0x08084274..0x08085154`
- scorer SHA-256：
  `c9da91cd096b36f325f3b975a416c83578048a1d588f89cafa1e1ec9dc075830`
- candidate unit pool literal：
  `0x020240C0`（ROM literal `0x080842BC`）
- baseline unit pool literal：
  `0x0202F564`（ROM literal `0x080842C0`）
- AI 配置表：
  `0x0853F348..0x0853F888`，8 条 × `0xA8`
- 配置表 SHA-256：
  `6bcd51c9faede066805b9f0e427217925b14ad5b7d99e7b98876d17f23e87504`
- config 0 的整条记录为零；config 1–7 的 `0x00..0x87` 完全相同，差异位于
  `0x88..0xA7` 的四个 typed rule 槽。
- 完整 34 个 common weight 字段、目标索引、damage utility、状态过滤及规则记录保存在
  `notes/battle-ai-utility-policy-bindings-20260723.json`。

阵型参数与配置编号的内容分布进一步验证它不是任意业务字段：

- battle 1 的 character 25/26 使用 config 3；对应规则包含指定 character 31 以及 action
  74/75；
- battle 3 的 character 20 使用 config 5；对应规则关注 effect family
  `0x02/0x07/0x17`；
- battle 14 的 character 55 使用 config 4；对应规则关注 character 30；
- battle 20 的 character 4/5/6 使用 config 7；对应规则读取 tile class/side；
- battle 30 的 character 22/23/24 使用 config 6；
- battle 15 护送 character 30 的原作运行时 `unit+0xCD == 2`，其阵型
  `unit_parameter` 同为 2；普通敌人均为 1。

## TDD 与实现边界

红灯：

- `test_battle_scenario_loader` 首先在 battle 15 的护送单位上失败：
  `ai_config_id == 1`，预期为 2；
- battle 1 config 3 与 battle 20 config 7 的装载断言同属该红灯；
- `test_battle_ai_utility` 首先因不存在 `ai_utility_policies` 与
  `score_actor_projection` 编译失败。

绿灯：

- 固定阵型拥有内嵌角色配置时，loader 同时写入
  `formation_unit_parameter` 与 `ai_config_id`；
- 动态部署占位槽没有内嵌配置，参数 0 表示“未提供”，因此保留实例的标准 config 1，
  不错误降级为 config 0；
- planner 对 active、tool 与 resource 候选统一读取
  `ai_utility_policies[acting_unit.ai_config_id]`；
- config 0 使用零 common weights，但保留 scorer 已证的固定 0–9 final RNG；
- config 1–7 使用 ROM 相同的 common subset，各自 scenario rule 仍由原有 typed table
  选择；
- 行动者投影已改为两个互斥资源分量。

旧的资源集成测试曾把“低 HP 时必定选择休息”写成固定偏好，同时又给行动者保留瞬身术。
ROM 没有证明这一偏好。本次把测试夹具的主动术清空，使它只验证“唯一合法资源动作能够经
planner 和共享事务完成”，不再用启发式断言覆盖原作整数评分。

## 后续闭合

`0x18/0x1C/0x20/0x24/0x28` 的 action 分类、`0x74..0x84` 的 kind-5 selector、
同/异阵营 target bank 门、damage 单组件计数和 actor penalty 的除法前位置，已在后续
`notes/battle-ai-action-component-runtime-20260727.md` 闭合。该后续取证同时纠正了
一个新的生产错误：`+0x24/+0x28` 选择的是候选类型，不是单位 `ai_role`。

后续 `notes/battle-ai-action-component-runtime-20260727.md` 已继续闭合 event `0x11`
条件分支、effect-low-6 等于 7 的安全落点固定奖励，以及 kind 1 为 2、kind 2–5 为 1
的 custom-rule component count。`0x08083AF4` 也已在同一后续记录中闭合为
battle-ID 驱动的八记录地图拓扑距离，并接入目标索引、queued-event 距离和规则进度；
五种 custom rule 的可见名称仍保持中性。

## 验证

- 94/94 个 `butano-sequel/game/tests/test_*.cpp` 编译执行通过：
  `build/resource-guard/butano-ai-config-projection-host-20260727-03.json`，峰值
  tree RSS 140.56640625 MiB。
- 相关 ROM/analyzer、生成内容、单领域与研究文档测试 89/89 通过。
- `test_battle_all_scenario_runtime` 继续让 85 个可玩 battle/variant 组合各运行 100 回合；
  `test_battle_dynamic_deployment_turn` 复验动态竞技场不会把“缺少内嵌配置”误当成 config 0。
- 固定 devkitARM 构建通过：
  `build/resource-guard/butano-ai-config-projection-arm-20260727-02.json`。
  - ROM SHA-256：
    `547705ab2b78e93e0581043809a4b05e08361a7f3b1a88a061d3e12211af17df`
  - ELF SHA-256：
    `45ace60762bb73951bb76d48e1ab4b86dd4623b522548515b54a2d81746543ff`
- 受守护静音 mGBA：
  `build/butano-ai-config-projection-runtime-20260727-01/`。
  - frame 2803，battle 9，9 个活动单位，round 2，phase 1；
  - controller/player trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `90771569028e9d77fe566a3e15871feb5afb6c5f8128e2dc1811a5d87609d5de`。
- `python3 -m py_compile` 与目标文件 `git diff --check` 通过。
- mGBA 本轮明确使用 `mute=1`，不能据此宣称音频撕裂已经修复。
