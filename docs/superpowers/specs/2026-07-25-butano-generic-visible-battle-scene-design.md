# Butano 通用可见战斗场景设计

## 目标

把当前写死 battle row 43、9×22 地图和标题的 `scenario_43_scene.cpp` 收敛为一个按生成
内容装载的通用可见战斗场景，并以 battle row 9 的 3v5 编队证明后续关卡不需要复制新的
战斗 FSM、输入路由、单位生命周期或 AI 主链。

这是完整战斗系统 Goal 的一个集成里程碑，不表示 47 场关卡、章节脚本、最终角色美术或
音频已经功能等价。

## 证据映射

- 架构设计中的“scenario 47：3v5 多单位阶段”对应生成内容的 battle row 9。
- row 9 variant 0 是角色 1、2、3 对五个角色 41，地图为 16×32。
- row 9 的地图 tile graphics、palette、primary layout、metatile definitions 和 collision
  都来自哈希绑定的 `rom/base.gba`，不能复用 row 41 的草地截图或清图资产。
- row 43 继续承担影分身、固定 reserve 和一玩家对三敌的回归样本。

## 方案比较

### 方案 A：继续增加 `scenario_09_scene.cpp`

实现最短，但会复制输入路由、camera、sprite 生命周期、文本、AI tick 和表现事件消费。
它保留了用户指出的“每关一套拼接场景”问题，不采用。

### 方案 B：把所有地图提升为一个 23×32 最大尺寸运行时

运行时类型统一，但会扩大所有关卡的 pathfinding/AI scratch workspace，并要求重写当前
严格校验宽高的 map loader。本里程碑当时只需要验证第二张可见地图，因此暂不采用。

2026-07-25 后续全目录里程碑已用 ARM section 与 47 图/85 非空变体测试重新评估并采用该
方案：活动边界与固定容量分离后只保留一个 EWRAM controller，`.sbss` 反而从 169,960
降至 129,612 字节。最新约束以
`2026-07-25-butano-runtime-sized-battle-grid-design.md` 为准。

### 方案 C：编译期尺寸模板 + 运行时关卡配置

采用。`run_visible_battle_scene<Width, Height>` 持有相同的
`battle_scene_controller<12, Width, Height>`，配置只提供 battle ID、variant、condition
variant、seed、load policy 和背景资源。GBA 仍保留固定容量、无堆分配和精确 workspace
尺寸；不同地图只生成必要的模板实例。

## 组件边界

### ROM 地图重建

把现有 `reconstruct_map(rom_path)` 泛化为
`reconstruct_map(rom_path, battle_id=41)`。算法继续按 map row 的实际 coarse width/height
解码两个 metatile half，不接受越界 row、layout 长度不匹配或 metatile/tile 越界。

`generate_butano_battle_runtime_assets.py` 继续生成 row 41 资产，并新增 row 9 的
`battle_09_clean_map.bmp/json`。row 9 是 512×512 active map，无截图清人步骤。

### 通用场景运行器

新增 `battle_runtime_scene.h/.cpp`：

- `battle_runtime_scene_exit` 只有 `back` 和 `next_battle`；
- `battle_runtime_scene_config` 保存 battle/variant/condition/seed 以及开发标题；
- `run_visible_battle_scene<Width, Height>` 只通过 `battle_scene_controller` 发领域命令；
- renderer 从 snapshot 遍历 12 个稳定槽，位置、HP、查克拉、阵营、完成状态和召唤关系
  均来自权威 session；
- camera 同时按地图像素尺寸约束 X/Y，不再使用 row 43 的固定 X；
- 表现层继续只消费 `battle_scene_presentation_event`，没有 resolver/session 写入口；
- START 返回上一层，SELECT 返回 `next_battle`，仅用于开发验收关卡链。

`scenario_43_scene.cpp` 降为 row 43 wrapper；它收到 `next_battle` 后进入 row 9 wrapper。
row 9 使用独立的 16×32 controller 实例和 ROM 重建背景。

## 用户可见行为

1. scenario 41 战前按 SELECT 仍进入 row 43。
2. row 43 原影分身与三敌回合路线不变。
3. row 43 按 SELECT 进入 `BATTLE 9` 3v5 验收场。
4. 初始画面显示三个可行动玩家、五名敌人和 `ACTIVE 8/12`；L/R 按 roster 顺序选择
   P1、P2、P3。
5. 三名玩家分别结束行动后才进入敌方阶段；敌人按五个单位逐个完成。
6. START 返回 scenario 41。非法输入显示稳定错误，不写入领域状态。

## 错误与边界

- 关卡 ID、map ID、宽高或条件不匹配时，controller load 失败并返回，不显示伪战场。
- 背景必须由对应 ROM row 重建；禁止以 row 41 背景代替 row 9。
- row 9 当前只验收多单位调度、输入和 AI 阶段，不把通用占位 sprite 误报为最终角色美术。
- 自动 mGBA 路线静音，只签发流程、图形和状态，不签发音频听感。
- 章节对白、部署 UI、结果演出、AI 防御/资源策略和部分碰撞规则继续作为完整 Goal 缺口。

## 测试与验收

- 生成器测试先证明 row 9 输出尺寸、哈希确定性和 row 41 默认兼容。
- C++ 宿主测试装载 row 9，验证 8 个活动单位、12 个稳定槽、P1/P2/P3 roster、三人全部
  完成后才切敌方，以及五名敌人顺序推进。
- source wiring 测试禁止通用场景写死 `[43]`、`9, 22` 或直接引用 resolver/session。
- ARM 构建检查 ROM、IWRAM/EWRAM section 和 warning/error。
- 受守卫 mGBA 路线捕获 row 9 编队、P1/P2/P3 选择、敌方 `AI DONE` 进度和下一玩家回合；
  row 41、43 既有路线必须同时通过。

## 最终实现约束与运行证据

通用 renderer 的首个 3v5 ARM 运行暴露了两类宿主测试无法覆盖的 GBA 资源边界：

- row 9 的 16×32 寻路结果、距离、父节点、访问标记和地图投影同时位于函数栈时，
  `find_path` 会进入 `__aeabi_memset4` 后覆盖 IWRAM 返回地址。现在
  `battle_encounter_runtime` 固定拥有 `pathfinder_workspace` 与移动地图工作区；
  16×32 `pathfinder_workspace` 为 8,704 字节并常驻 EWRAM，不再为每次预览或 AI
  行动压入栈。
- GBA 最多提供 128 个 OAM sprite。12 个单位、单位标签、光标和长文本叠加曾在创建
  第八个活动单位时耗尽 OAM；通用 HUD 现限定 78 个文本 sprite，并由
  `battle_runtime_scene_sprite_budget` 静态证明最坏 12 单位场景不超过 128。

场景导出固定 96 字节的 `battle_runtime_scene_telemetry`。前 72 字节继续镜像 controller snapshot
和表现队列状态，不拥有领域写入口；`presentation_busy` 明确区分“回合领域状态已推进”
与“最后一段演出已结束”。mGBA 脚本按该遥测驱动输入和截图，不能仅凭固定帧数或截图
文件名宣称完成。后 24 字节补充选中角色、动作总数/索引、选中动作、选择错误和最后结算
动作，供角色技能链验收。当前构建符号位于 `0x02012848`，地址必须从每次构建的 ELF 重新读取，
不能作为稳定 ABI 硬编码。

最终受守卫证据：

- row 9：`artifacts/butano-generic-scene-battle09-state-final-20260725-03/`。3 名玩家各
  移动一格并完成行动，5 名敌人依次执行，最后演出结束后在第 453 帧签发 round 2；
- row 43：`artifacts/butano-generic-scene-s43-final-20260725-05/`。影分身把活动单位
  从 4 增至 5，三敌完成后等待表现队列清空，在第 1235 帧签发 round 2；
- row 41：`artifacts/butano-generic-scene-scenario41-final-20260725-01/`。原有教学、
  技能、胜利、结算和战后 2,580 帧金路径保持通过。

最终 ARM section 为 `.iwram` 8,840 字节、IWRAM `.bss` 2,172 字节、
EWRAM `.ewram` 224 字节和 `.sbss` 123,332 字节。自动路线全部静音，只验证流程、图形
和状态；最终角色逐人美术/动作、章节部署与结果流程、AI 资源/防御策略、部分碰撞语义和
其余关卡仍是完整 Goal 的后续里程碑。
