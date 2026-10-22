# 地形类别、逐路径被动预算与 Butano 运行时（2026-07-26）

## 纠错结论

此前把碰撞低四位 `1/3/7/15` 解释成四方向位掩码、又把被动 target
`0x1A–0x1C` 解释成“当前单位表现配置”，均不成立。本记录取代这些旧结论：

- 碰撞低四位是地形类别，不是四个可独立组合的方向位；
- `0` 是普通地形，`1/3/7` 是三个需要对应被动预算的类别，`15` 永远不可通行；
- `0x1A/0x1C/0x1B` 分别给类别 `1/3/7` 提供逐路径预算；
- 预算按候选路径局部消耗，路径中的起点也计数；递归回溯会恢复预算，不会永久消耗角色被动；
- 地图 0 还出现 `2/4`，但当前消费者没有给它们分配上述三项被动，不能自行命名。

机读碰撞结论位于
`notes/battle-map-collision-semantics-20260724.json`，被动消费者结论位于
`notes/battle-passive-consumer-bindings-20260725.json`。

## 原 ROM 机械证据

基准 ROM SHA-256：
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

| 作用 | ROM 范围 | 字节数 | SHA-256 |
|---|---|---:|---|
| 递归路径搜索与地形类别分支 | `0x080698B4..0x08069D1B` | 1128 | `143a7223550ccd44c69615b39e76fc2f96e7ba4ec62671a9ff6de62adaa844aa` |
| 路径搜索参数装配 | `0x08069D1C..0x08069DB7` | 156 | `7a33e919213bcd0f218293306f08587dd642414fb5f99e0da9147febcf0579be` |
| 当前单位三项被动查询与类别预算配置 | `0x08069DB8..0x08069E43` | 140 | `415a0f9cb1ab184f6b40d257a82905abb4201c7a2d8723621624ecbf2bf786fb` |

`0x08069DB8` 依次查询 target `0x1A/0x1B/0x1C`，把结果按地形类别
`1/7/3` 传给 `0x08069D1C`。三条成长定义都是一级基础值 2、每级增加 1；统一查询公式仍是
`base_a + per_level_a × (stored_level - 1)`。

路径搜索在访问一个类别 `1/3/7` 的格子时递减该类别的局部剩余量，剩余量不足即拒绝该条
候选路径。起点经过同一分支，因此同样计数；递归调用按值保存剩余量，返回父层后兄弟路径
继续使用父层预算。这证明它是“单条候选路径可穿越多少格该类地形”，不是战斗内会被用掉的
资源，也不是渲染参数。

作为二级交叉证据，Wazap 攻略明确记载：角色必须学会“樹上歩行”才能到达附近森林深处。
该文字支持“训练能力控制地形到达性”，但只足以校正其中一个显示名，不足以给三种类别逐项
命名或声明专属动画。

## Butano 领域实现

`battle_terrain_traversal_limits()` 从单位的正式 `battle_passive_state` 和生成定义查询三个
预算，不建立场景特例。`grid_pathfinder` 的可达域与具体路径使用同一套逐路径类别预算；
玩家移动预览、AI 行动规划和 AI 威胁场都从各自行动单位的被动状态计算预算。渲染器只读取
已经确定的领域结果，不拥有修改坐标、预算或行动资格的通道。

玩家可以在原地跳过移动，即使关卡初始部署把该单位放在其未受训地形上；只要真正离开或
重新进入该类格，就必须满足预算。这一例外只保证已有部署不会把回合锁死，不会让角色穿越
未学习的地形。

宿主测试固定了以下行为：

- 无被动不能进入类别 `1/3/7`；
- 预算 2 只能覆盖同一路径中的前两格对应类别，且起点计数；
- passive ID `21/22/23` 的一级/二级/三级分别映射到类别 `1/7/3` 的预算 `2/3/4`；
- 玩家预览与 AI 规划共享规则，训练前后产生不同的合法候选；
- 原地确认可进入命令阶段，不能利用该例外移动到相邻未受训地形。

## TDD 与运行时验收

红灯证据：

- `build/resource-guard/butano-terrain-passive-red-20260726-01.json`
- `build/resource-guard/butano-terrain-stationary-red-20260726-01.json`
- `build/resource-guard/butano-terrain-runtime-script-red-20260726-01.json`
- `build/resource-guard/butano-terrain-map-semantics-red-20260726-01.json`
- `build/resource-guard/butano-terrain-semantic-api-red-20260726-01.json`
- `build/resource-guard/butano-b09-preparation-route-red-20260726-01.json`

绿灯证据：

- 地形领域测试：
  `build/resource-guard/butano-terrain-passive-green-20260726-02.json`
- 89/89 宿主程序：
  `build/resource-guard/butano-terrain-passive-full-host-20260726-03.json`
- ARM 构建：
  `build/resource-guard/butano-terrain-passive-arm-build-20260726-01.json`
- 碰撞语义分析：
  `build/resource-guard/butano-terrain-map-semantics-green-20260726-01.json`
- 地图/路径语义 API 聚焦测试：
  `build/resource-guard/butano-terrain-semantic-api-green-20260726-01.json`
- 单一领域 API 防回归：
  `build/resource-guard/butano-terrain-single-domain-green-20260726-01.json`
- 89/89 语义 API 后全量宿主：
  `build/resource-guard/butano-terrain-semantic-api-full-host-20260726-01.json`
- 语义 API 后 ARM 构建：
  `build/resource-guard/butano-terrain-semantic-api-arm-build-20260726-01.json`
- battle 9 当前战前入口脚本：
  `build/resource-guard/butano-b09-preparation-route-green-20260726-01.json`
- mGBA：
  `build/resource-guard/butano-terrain-semantic-api-mgba-20260726-01.json`
- 分析器、脚本、单一领域、研究文档与构建契约最终回归：
  `build/resource-guard/butano-terrain-final-regression-20260726-01.json`

mGBA 从当前 ROM 启动 battle 41、完成部署并清空开场脚本。未训练 target `0x1B` 的鸣人在
`(4,10)` 选择相邻类别 7 格 `(3,9)` 时得到玩家错误 4，领域坐标保持不变；回到原点确认后
正常进入命令阶段。审计记录为
`artifacts/butano-terrain-traversal-runtime-20260726-02/audit.json`，对应截图为
`class-seven-rejected.png` 与 `terrain-origin-accepted.png`。

为排除递归路径规则只在 9×22 教学图成立、却在较大地图重新覆盖 GBA 栈，又执行了 battle 9
的 16×32 多角色回归。第一次使用旧 `mgba_battle_09_multi_unit.lua` 时只有 frame 30 的
Select 输入、没有任何 battle telemetry，最终 idle timeout；这说明脚本已经落后于新增的
实时战前页，不能解释成 ROM 黑屏。失败原始产物保留在
`artifacts/butano-terrain-large-grid-b09-20260726-01/`。

随后先用红绿脚本契约给当前 `mgba_battle_09_character_actions.lua` 增加 frame 30 的 A，
从正式战前页进入 battle 41，再通过既有共享路由进入 battle 9。精确当前 ROM 在 frame
2794 完成 16×32 地图的三名玩家、五名初始敌人、一次分身后的 9 个活动单位和完整换边，
到达 round 2 / player unit selection；鸣人动作 2 与忍具、樱动作 1、佐助动作
2/5/16 都来自正式目录，控制错误为 0，SP 为 `0x03005754`。证据为
`build/resource-guard/butano-terrain-large-grid-b09-mgba-20260726-02.json` 和
`artifacts/butano-terrain-large-grid-b09-20260726-02/audit.json`。这排除了本次
pathfinder 修改在该 ARM 大地图路线上的栈回归。

本轮 ROM SHA-256 为
`726c9f30e4cd2283fc138c38ec5e3e2afceb975ef9005719db8ea0860aa74da4`，
ELF SHA-256 为
`132cb9390777eb14e48f4aec9d677b1ea345196b064ed58e97a15ac98a447b0c`。
基准与工作 ROM 存档 SHA-256 均保持
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

## 边界

本里程碑闭合三个地形被动的路径规则，不代表 45 条被动全部完成。仍有 28 条成长定义没有
统一查询器的直接战斗消费者；三种类别的完整日文显示名、教学提示和专属表现也没有全部
校字。路径类别规则已经是玩家、AI 与威胁计算共享的领域真值，后续关卡只能通过地图数据和
单位被动配置扩展，不得回退为截图分支或 scene 私有选项。
