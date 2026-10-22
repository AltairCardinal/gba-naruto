# 战斗 AI 候选类型与动作组件整数路径（2026-07-27）

## 结论

原作 AI 评分器不会把角色身份当作“是否休息/提炼查克拉”的分类依据。候选追加器
`0x08082040` 把外层候选类型写到 `0x0202D262[candidate_index]`；执行器
`0x080829CC` 以固定类型生成候选：

- `1`：移动；
- `2`：提炼查克拉；
- `3`：休息；
- `4`：已选择动作。

评分器从 `u8(0x0202D261)-1` 取得当前候选索引。类型 4 才读取 16 字节运行时动作描述；
类型 2/3 使用配置 `+0x24` 权重，其他无动作候选使用 `+0x28`。Butano 先前错误地把这一路
映射到未由正式内容赋值的 `battle_unit_instance.ai_role`。本轮已撤销该映射，并让提炼
查克拉、休息分别显式投影为候选类型 2、3。

## ROM 绑定

- ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 候选追加器 `0x08082040..0x080820A6`：
  `0d081b0ff74444e057215a6cf2d775d25fc6bdd9ceabc35900c2f603167c9e7b`
- 候选执行器 `0x080829CC..0x08083040`：
  `eaef7cf8e1e03d7b4bd6679ce20e16a93f5794ddfe9b97f9a786dbaa9e6fdb7b`
- AI scorer `0x08084274..0x08085154`：
  `c9da91cd096b36f325f3b975a416c83578048a1d588f89cafa1e1ec9dc075830`
- 配置表 `0x0853F348..0x0853F888`：
  `6bcd51c9faede066805b9f0e427217925b14ad5b7d99e7b98876d17f23e87504`

候选追加器在 `0x08082058/60/64` 依次定位计数区 `+0x39`、类型数组 `+0x3A` 并写入传入
的类型。执行器对同一追加器的五个调用中，`0x08082BF0` 传类型 1，
`0x08082A4C` 传类型 2，`0x08082AC0` 传类型 3，`0x08082EC6` 传类型 4；
类型 0 是无动作占位。评分器 `0x08084714..0x08084742` 再读取同一数组，减 2 后只接受
0/1，因此类型 2、3 精确共享 `+0x24`。

## 已闭合的动作组件

运行时动作描述表位于 `0x02030D29`，步长 16。描述 `+0` 是 runtime kind，
`+1..+2` 半字中的 `0x0700` 是 effect low 3：

- kind 1：加入配置 `+0x18`，再加入一个聚合伤害组件，component count 合计增加 2；
- kind 4：加入配置 `+0x20`，component count 增加 1；
- kind 5：加入配置 `+0x1C`，再按 effect low 3 选择
  `[+0x84,+0x74,+0x78,+0x7C,+0x80,+0x74,0,0]`，component count 增加 2；
- 其他已选择 kind：加入零值组件，component count 增加 1；
- 未选择动作：候选类型 2/3 使用 `+0x24`，其他类型使用 `+0x28`，component count
  增加 1。

effect low 3 为 2/3 时启用异阵营七槽 bank `0x02030E83`；为 1/3/5 时启用同阵营
bank `0x02030E7C`。每个启用 bank 只增加一个 component count。每个 selector 的权重只在
至少一个合格 queued event 命中其单位时加入一次；重复 event 不重复同一 selector 权重。

kind 1 的伤害、成功率、覆盖率和范围四个加权子项先求和，再作为一个聚合组件加入平均，
不是四个独立分母项。actor event/status 对 `0x12/0x12` 或 `0x0D/0x0D` 首次命中时，
只从分子减一次 `weight[0x84]+weight[0x1C]`，随后退出循环；惩罚发生在整数除法之前。

### event `0x11` 的条件减分

`0x08084D2A..0x08084D80` 已完成逐指令绑定。评分器扫描到 queued event 低 6 位
`0x11` 时，读取模拟后行动者的当前/最大 HP（`unit+0x0C/+0x0E`）和当前/最大查克拉
（`unit+0x07/+0x08`）：

- 当前 HP 严格大于 `floor(max_hp/2)` 且当前查克拉严格大于
  `floor(max_chakra/2)` 时直接减分；
- 否则以 `unit+0xC5 * u8(0x0201BE2A) + unit+0xC4` 索引
  `0x02002880`，动态候选场 `bit 0` 为 1 时减分；
- 两条分支都复用 `weight[0x84]+weight[0x1C]`，只减一次，不增加 component count。

这里的 `0x02002880` 是 `0x080833A8` 构建的敌方伤害威胁场，不是地形表；`bit 0`
表示当前格被敌方可达站位和伤害动作范围覆盖。Butano 复用既有
`battle_ai_candidate_field`，把投影后单位所在格的 threatened 状态传给同一个
`battle_ai_utility_scorer`，没有另建截图或关卡专用分支。

### effect `0x07` 的安全落点奖励

`0x080850BA..0x08085126` 的末尾固定奖励也已闭合。评分器只在以下条件全部满足时，
向分子加入常量 8000：

- 四个 scenario rule 槽没有处理过 kind 1–5；
- selected action index 不是 `0xFF`；
- 第一条 queued event 的低 6 位是 `0x07`；
- 被选择的位置在动态候选场 `0x02002880` 中没有 threat bit `0x01`。

位置来源由第一条 event 的 raw byte `+0x15` 选择：为 0 时使用 event `+2/+3`，
非 0 时使用行动者 `+0xC4/+0xC5`。奖励直接加到分子，不增加 component count，也不
扫描后续 event。当前内容中 effect `0x07` 是召唤变体；Butano 的 empty-tile 候选把
目标落点的 threatened 状态随 queued event 投影，并从同一个 typed scenario-rule 配置
计算“是否存在 kind 1–5”，没有用动作名称或画面推断。

### scenario rule 的分量计数与共同平均

`0x08084DAA..0x080850AC` 的四槽规则循环现已把分子和分母一起闭合。每个被识别的
kind 即使条件未命中、组件值为 0，也会增加最终整数平均的 component count：

- kind 1 把“对活动敌方的平均移动进度”和“候选格安全奖励”作为两个分量，count `+2`；
- kind 2 把“接近 parameter character”和“伤害 event 命中该 character”的合计作为
  一个分量，count `+1`；
- kind 3 的 action-ID event 奖励占一个分量；
- kind 4 的 tile-class/side 奖励占一个分量；
- kind 5 的 eligible event-family 奖励占一个分量。

`0x08085132..0x08085136` 最终使用累积后的总 component count 做一次整数除法，然后才加
0–9 RNG。Butano 先前把 `scenario_rule_score` 加在已经完成平均和随机扰动的
`utility.score` 后面，使 10000 权重被当作裸最终分数。现在
`battle_ai_scenario_rule_scorer` 返回 `{component_sum, component_count}`，player-independent
planner 在通用 utility 完成最终除法前合并它们；移动、提炼查克拉、休息、单目标、范围和
空地/召唤候选都走同一入口。

## TDD

红灯先要求：

- analyzer 输出候选执行器、追加器哈希和类型 1–4 映射；
- `ai_action_projection` 不再暴露 `no_action_role`；
- 提炼查克拉和休息分别映射为候选类型 2、3；
- 配置字段改用 candidate kind 命名；
- analyzer 输出 `0x11` 的资源阈值、候选场地址和威胁位；
- 领域测试区分低资源安全格、低资源受威胁格和高资源安全格；
- planner 集成测试要求受威胁格上的 `0x11` 候选低于同分量结构的 `0x21` 对照候选。
- analyzer 输出 effect `0x07` 的首 event、rule 门、位置选择器、威胁位和固定 8000；
- 领域测试覆盖 event 落点、actor 落点、active rule 与 component count 不变；
- 真实 planner 的单一安全召唤落点必须跨过只可能由该固定奖励达到的分数阈值。
- analyzer 输出 kind 1 的两个分量与 kind 2–5 的单分量计数；
- typed-rule 领域测试要求未命中的零值组件仍留在分母；
- 跨配置 planner 不能再把 10000 规则权重直接加到最终平均值之后。

旧实现按预期出现 analyzer `KeyError`、旧 manifest 字段不匹配，以及 C++ 缺少
`ai_candidate_kind`/`resource_candidate_kind`/`actor_threatened_after`/
`target_position_threatened`/`has_active_scenario_rule` 的编译失败；规则计数测试还因
scorer 只返回裸 `int` 而无法读取 component sum/count。旧 planner 的
`0x11` 两个对照候选分数相同，安全召唤分数也低于阈值，集成断言按预期失败。绿灯后
聚焦 analyzer 11/11，
`test_battle_ai` 与 `test_battle_ai_utility` 均通过。

## `0x08083AF4` 地图拓扑距离闭环

后续反汇编确认该函数不是通用寻路，也不是普通曼哈顿距离。它从
`0x02026805` 读取 battle ID，并以 `0x0853F888 + battle_id × 8 × 16`
选择八条地图路由记录：

- kind 0：以当前两点的曼哈顿段结束；
- kind 1/2：纵向/横向屏障与通道 breakpoint；
- kind 3：map 5 的固定转换补偿；
- kind 4：map 23 的 15×17 signed distance lookup；
- kind 5：map 24 的 13×17 双入口 lookup；
- kind 6：map 17/37 的固定转换补偿。

47 张地图的 376 条记录类型计数为
`0:320, 1:18, 2:33, 3:1, 4:1, 5:2, 6:1`。函数、记录表和两张
lookup 均已由 SHA-256 与关键跳转/字面量绑定到 ROM，机读结果写入
`notes/battle-ai-utility-policy-bindings-20260723.json`。

Butano 没有另建第二套移动系统：`grid_pathfinder` 继续负责真实可达域和路径，
`battle_map_topology_distance` 只实现原作 AI 的地图拓扑评价。正式 map loader
把 battle ID 写入 `grid_map`，目标索引、queued-event 距离效用、关卡追敌进度和
AI 的目标点推进共用该模型。map 16 的隔墙样例从曼哈顿 2 纠正为拓扑 8，最近目标
也从直线更近但被墙隔开的单位改为通道路线上更近的单位。

## 验证

- 94/94 个 `butano-sequel/game/tests/test_*.cpp` 编译执行通过：
  `build/resource-guard/butano-ai-action-components-host-20260727-02.json`，峰值 tree RSS
  `145.015625 MiB`；
- utility/status ROM analyzer 13/13，通过 `python3 -m py_compile`；
- ARM/Butano 构建通过：
  `build/resource-guard/butano-ai-action-components-arm-20260727-02.json`，峰值
  `19.18359375 MiB`；
  - ROM SHA-256：
    `675926bfba070dbcf3ea48a0a6b27510106f8f88543d1972850940b178824ded`；
  - ELF SHA-256：
    `cf6ae568720cd5d962c0343c7de890ff1afeca349485c0c054575d1b7d6120f7`；
- 静音 mGBA 路线：
  `build/butano-ai-action-components-runtime-20260727-02/`；
  - frame 2803，battle 9，9 个活动单位，round 2，phase 1；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `c124faacdc9f5546df13f75008607a95060755fce4c37a41f20fd5ed5dd93f47`；
  - 守卫成功标记完成，峰值 tree RSS `119.234375 MiB`。

mGBA 明确以 `mute=1` 运行；本里程碑不签发音频质量或音频撕裂修复结论。

### event `0x11` 增量验证

- 94/94 个宿主 C++ 测试程序通过：
  `build/resource-guard/butano-ai-event11-host-20260727-01.json`，峰值 tree RSS
  `148.203125 MiB`；
- utility/status/research-doc Python 回归 72/72，通过 `py_compile` 与 scoped
  `git diff --check`；
- ARM/Butano 构建通过：
  `build/resource-guard/butano-ai-event11-arm-20260727-01.json`，峰值
  `18.98828125 MiB`；
  - ROM SHA-256：
    `ed6dd8e079e169eec452e851abea83d5d8201bb4124c768abe3c7f91726534b9`；
  - ELF SHA-256：
    `d2a99d7fe945de862bf2cb0d1fa1c5fa2a16d2d939e52a598d3032467dc358e4`；
- 生成 manifest SHA-256：
  `fdcd7d3b58cd016800941f5634fa3d7bbdc71e80697acf9689c1b92beaee0488`；
- 静音 mGBA 路线：
  `build/butano-ai-event11-runtime-20260727-01/`；
  - frame 2803，battle 9，9 个活动单位，round 2，phase 1；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `a58762e5e56a8565cf8f1a9851195307819165b4c2c1ca5a7c83de3c1c8f4a10`；
  - success marker 完成，峰值 tree RSS `119.99609375 MiB`。

该运行仍明确使用 `mute=1`；只验收战斗状态机与内存安全，不验收音频。

### effect `0x07` 增量验证

- 94/94 个宿主 C++ 测试程序通过：
  `build/resource-guard/butano-ai-effect7-host-20260727-02.json`，峰值 tree RSS
  `137.30078125 MiB`；
- utility/status/research-doc Python 回归 73/73，通过 `py_compile` 与 scoped
  `git diff --check`；
- `test_battle_dynamic_deployment_turn` 不再沿用“敌方三次行动后仍固定为 6 个活动单位”的
  旧预期。安全召唤候选取得原作固定奖励后，battle 32 会在同一个
  `battle_scene_controller` 中创建一个带有效 `summoner` 的领域单位，活动单位数变为 7；
- ARM/Butano 构建通过：
  `build/resource-guard/butano-ai-effect7-arm-20260727-01.json`，峰值
  `90.98046875 MiB`；
  - ROM SHA-256：
    `d2cac529a1a730c29dc3699323987f3d2c29c9e7be428c9f8734bb0682e72d6d`；
  - ELF SHA-256：
    `e0219cb7b4c5f14620df2666bac3f7449e4490e1f8d290ec597aa298445a2274`；
- 生成 manifest SHA-256：
  `7cf595b6b0cc4dac0f36aaf77f2dea23423bfb5a9c6a34d7bbf4fd96165ee5ae`；
- 静音 mGBA 路线：
  `build/butano-ai-effect7-runtime-20260727-03/`；
  - 当前 ELF 中 `konoha_battle_runtime_telemetry` 的精确地址是
    `0x0201FBB4`；新增 queued-event 字段令 controller 比上一构建增加 48 字节，
    因而旧地址 `0x0201FB84` 的两次运行只停在部署确认页等待驱动，不是 ROM 黑屏或
    战斗初始化死循环；
  - 使用当前 ELF 地址后在 frame 2803 到达 battle 9、9 个活动单位、round 2、phase 1；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `1924b1cfee9ed98e991bdbc034711a1f02d7445742fae8617fa1d341e7f2c76e`；
  - success marker 完成，峰值 tree RSS `119.31640625 MiB`。

该路线仍以 `mute=1` 运行，只证明部署、玩家动作、敌方回合与下一轮状态机可继续；
本增量不签发音频质量，也不把单一召唤样本扩张为完整 AI 逐整数等价。

### scenario custom rule component count 增量验证

- 94/94 个宿主 C++ 测试程序通过：
  `build/resource-guard/butano-ai-custom-rule-count-host-20260727-01.json`，峰值 tree RSS
  `142.25390625 MiB`；其中全场景矩阵继续让 85 个可玩 battle/variant 组合各运行
  100 回合；
- utility/status/research-doc Python 回归 74/74，通过 `py_compile` 与 scoped
  `git diff --check`；
- ARM/Butano 构建通过：
  `build/resource-guard/butano-ai-custom-rule-count-arm-20260727-01.json`，峰值
  `19.2265625 MiB`；
  - ROM SHA-256：
    `bf2fce14d2fd51c3855261663bb010f7350cd48c02ee545c09f534b7a08543c3`；
  - ELF SHA-256：
    `9bb2a2badd163b4f401a271a826948adaaa943cc03adbb453b952b65e18abc61`；
- 生成 manifest SHA-256：
  `1b62fb7c0bf11ad9c7316a7b7ad1f55dc2297800aaf333519c4b72c2fa1c1ca0`；
- 静音 mGBA 路线：
  `build/butano-ai-custom-rule-count-runtime-20260727-01/`；
  - 当前 ELF 遥测地址 `0x0201FBB4`；
  - frame 2803，battle 9，9 个活动单位，round 2，phase 1；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `fe36dd19eb62efa1390a309eed625d3d35c0c43ff8f7cc60b2cd2c4653090d10`；
  - success marker 完成，峰值 tree RSS `119.2109375 MiB`。

该运行仍以 `mute=1` 完成；它不证明音频质量。

### topology-distance 增量验证

- 94/94 个宿主 C++ 测试程序通过：
  `build/resource-guard/butano-ai-topology-distance-host-20260727-01.json`，
  峰值 tree RSS `140.984375 MiB`；地图内容测试覆盖 kind 0–6，并对 47 张地图的
  全部坐标对验证距离对称性；
- utility/status/map-generator/research-doc Python 回归 78/78，通过
  `py_compile` 与 scoped `git diff --check`；
- ARM/Butano 构建通过：
  `build/resource-guard/butano-ai-topology-distance-arm-20260727-01.json`，
  峰值 `18.87890625 MiB`；
  - ROM SHA-256：
    `e2640373df503bc96ee953a1e3c10d99ccbaf6c0b2de406f5b8fb314eca85bde`；
  - ELF SHA-256：
    `8b401d61fb34464d22fbe80de0bac565eaa3a6472ccf810c24b21410b17d56de`；
- 生成 manifest SHA-256：
  `61698900a9a71163188971d8f06896f8caee707f5abb965712cc84e50a9874e7`；
- 静音 mGBA 路线：
  `build/butano-ai-topology-distance-runtime-20260727-01/`；
  - 当前 ELF 遥测地址 `0x0201FBC4`；
  - frame 2805，battle 9，9 个活动单位，round 2，phase 1；
  - execution trap 与 memory-write trap 均为空；
  - final state SHA-256：
    `0b188dcbdb570f635f91c7444f4a56b5c88bb1c0e4620e3d6a41f00f452daf04`；
  - success marker 完成，峰值 tree RSS `120.0859375 MiB`。

该路线明确以 `mute=1` 运行，只证明部署、玩家动作、敌方规划和下一轮状态机继续；
音频撕裂仍未在本增量验收。
