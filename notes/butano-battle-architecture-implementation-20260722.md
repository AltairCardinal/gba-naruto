# Butano 通用战斗架构首个实现切片（2026-07-22）

## 结论

已把 scenario 41 从“单关卡按回合硬编码”迁移到第一版通用战斗领域组件，并完成受资源守卫的 Butano 构建与 2580 帧 mGBA 冷启动路线。此切片证明通用组件可以在 GBA ROM 中运行；它不代表全游戏内容、全部技能和所有入口演出资产已经迁移完成。

## 已实现领域边界

- `BattleSession`：固定容量单位集合、阵营阶段、回合推进、可行动单位轮换、单位行动账本和事务式 `ActionDraft`。
- `CommandEligibilityService`：移动、能力/忍具、补充查克拉、休息和结束行动的可用/禁用/隐藏及稳定拒绝原因。
- `PresentationQueue`：自动步骤与可见输入等待严格分离；不可见等待被拒绝，黑场必须具有正时长。
- `AbilityResolver` / `EffectResolver`：距离与目标校验、查克拉原子消费、多段伤害、治疗、状态、移动、召唤、捕获、防御准备、替身和脚本事件。
- `ObjectiveEngine`：后缀表达式形式的 `all/any/not/count`，支持击倒、存活、捕获、位置、朝向、行动完成、回合和脚本变量；按领域事件触发并以显式优先级裁决胜负。
- `BattleAI`：复用命令资格、能力预览、占位和同一地图代价场；稳定 tie-break，无合法动作时安全结束。
- scenario 41：入口步骤队列、移动草案、结束行动提交、组合拳能力、击倒目标和敌方位置规划均已接入通用组件；不再按回合号改写敌人坐标。

## 本轮发现并修复的 GBA 专属问题

第一版 AI 为 9×22 地图的每个候选格重复运行完整 Dijkstra。宿主测试快速通过，但 ROM 在敌方阶段长时间不调用 `bn::core::update()`，表现为画面停住。密集探针 `build/butano-battle-flow-probe-20260722-01/` 证明防御确认后 105 帧仍停在敌方阶段。

修复后先计算一次固定容量可达代价场，再按格索引稳定评分。`build/butano-battle-flow-probe-20260722-02/` 在 frame 740 正确进入教程画面；相同修复由完整黄金路线继续验证到胜利、结算和战后地图。

## 构建与运行证据

- ROM：`butano-sequel/butano-sequel.gba`
- 大小：`7,796,396` 字节
- SHA-256：`e04e218e9dbcede120f0b8544e44a47df68160258539d40eea303afd25fa44a6`
- 构建守卫：`build/butano-battle-architecture-20260722-03/build-guard.json`
  - exit `0`，`degraded=false`，峰值 RSS `69.5703125 MiB`
- mGBA 路线：`build/butano-battle-architecture-runtime-20260722-04/`
  - mGBA 0.10.5 script-backport
  - 2580 帧，exit `0`，`degraded=false`，峰值 RSS `109.453125 MiB`
  - 黄金路线脚本 SHA-256：`96cce98eb9f7f2862215f3d0d5f7d2e3f85950c2e603c544003c1742c8ad25ac`
  - 已人工核对教程、术菜单、目标确认、组合拳、战斗对白、弹窗、胜利、结果和战后地图截图。

入口回归的关键事实：`intro-black.png` 是唯一纯黑帧边界，属于 30 帧自动步骤；随后 `intro-dialogue.png` 恢复为 27 色可见地图，A 只在此等待步骤生效；`battle-entry.png` 有 62 色且黑像素比例为 0。确认开始后不再依赖黑屏中的额外 A。

## 验证结果

- 15 个宿主 C++ 测试全部通过。
- `tests.test_butano_scenario_41_audio`、`tests.test_butano_build`、`tests.test_butano_scenario_41_runtime_script` 共 22 项通过，1 项需显式环境变量的重复构建测试按设计跳过；实际 ROM 已另由资源守卫完成构建。
- 当前音频资源和 Maxmod 接线未改变，格式/来源静态回归通过；本轮没有重新执行宿主听感录音，因此不把用户侧音频听感重新签发为已确认。

## 明确未完成边界

- 入口的鸣人亮相已显示角色；木叶丸亮相、“开始”标题、战前对白和手里剑转场目前只保证状态、时序和可见背景，四张截图仍共享同一临时地图画面。必须从哈希绑定的原 ROM checkpoint 导入专用 BG/OBJ 后，才能宣称入口视觉功能等价。
- scenario 41 仍只有一个玩家单位和一个能力；L/R 已接通通用轮换，但多单位可见验收要在 scenario 47 进行。
- 通用系统已支持召唤、捕获、护送类谓词和替身等基础语义，但 scenario 43–50 的内容定义、演出和关卡适配尚未迁移。
- 敌方 AI 已依据玩家位置和占位寻路；本关未配置敌方攻击能力，因此只验证了移动规划闭环。
