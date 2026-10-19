# 被动覆盖矩阵与 battle 11 target 0x20（2026-07-26）

## 为什么 45 条定义不是 45 个已实现效果

`tools/analyze_battle_passive_coverage.py` 把 45×12 字节成长表、24 槽查询器、
全部 15 个通用查询调用点、`0x0806D964` 内联属性消费者、内容目录引用和 Butano
消费者合并为
`notes/battle-passive-coverage-20260726.json`。

当前结果是：

- 45 条成长定义；
- 17 条定义的 target type 在原 ROM 有通用查询调用；
- 18 条 targets `0x01–0x0B` 不调用查询器，而是在角色属性装载器内联消费；
- 9 条 targets `0x0D–0x13` 不调用查询器，而是在主动技/忍具初始化器内联修改运行时
  动作定义；
- 合计 44 条定义已有 ROM 生产消费者，剩余 1 条为 ID 0 / target 0 哨兵；
- Butano 已有 44 条真实玩法消费者；
- `0x1A–0x1C` 已由 `0x08069DB8 → 0x08069D1C → 0x080698B4` 的完整数据流
  纠正为三个地形类别的逐路径穿越预算，不是当前单位表现配置。

旧版矩阵以“是否 BL 到 `0x0806DDA4`”作为唯一消费者口径，因而把 targets
`0x01–0x0B` 错记成无消费者；该结论已被
`notes/battle-persistent-passive-stat-bindings-20260727.json` 取代。targets
`0x0D–0x13` 又由 `notes/battle-passive-action-modifier-bindings-20260727.json`
闭合为动作初始化内联消费者。当前只对 ID 0 哨兵保持“无生产消费者”。本文早期将
`0x1A–0x1C` 登记为
`unimplemented_visual` 的结论也已被
`notes/battle-terrain-passive-runtime-20260726.md` 取代，不再作为当前事实。

## target 0x20 的闭合实现

确定性证据来自 `notes/battle-side-start-passive-bindings-20260725.json`：

- 查询优先级是 `0x1D → 0x1E → 0x1F → 0x20`；
- passive ID 35 是唯一 target `0x20`；
- 只在 battle ID 11 触发；
- 依次写 status `0x1E(value_a,duration=0)` 和
  `0x22(value_b,duration=0)`；
- 成功后设置共享 latch 并重算属性。

Butano 现在把 `battle_scenario_definition::battle_id` 写入候选
`battle_session`，阵营开始 scheduler 将该 ID 传给统一被动系统。ID 35 使用中性的
`battle_11_dual_boost` 领域身份：两次 status upsert 在 session 副本中完成，任一失败
都返回零事件且不写原单位；两次都成功后才设置 latch、重算并提交。表现事件同时携带
`0x1E/0x22`，HUD 显示 `BATTLE 11 BOOST` 及 ATK/AGI 数值，但不猜测尚未校字的原作名称。

## TDD 证据

红阶段：

- Python 覆盖测试先因 `tools.analyze_battle_passive_coverage` 不存在而失败；
- 分析器落地后，ID 35 仍被正确报告为 `withheld_gameplay`，期望 14 条实现时失败；
- C++ side-start 测试因缺少 battle ID 参数、`battle_11_dual_boost` kind 和第二状态字段
  编译失败；
- loader 测试因 session 没有 battle ID 编译失败。

绿阶段：

- 45 行矩阵为 `17 direct / 28 no-direct`；
- ID 35 level 2 物化为 `value_a=15,value_b=15`，battle 10 零写，
  battle 11 建立两状态并把基准 20 的攻击/敏捷重算为 23；
- 15 个已占用状态槽只剩一个空位时，第一条候选写入也会随第二条失败整体回滚；
- 自定义 battle 11 场景经真实 loader → session → start-round 链得到一个 ID 35 事件和
  两条状态；
- 普通 `0x1D–0x1F` 聚焦测试保持通过。

## 边界

生成场景目录目前没有自然学会 passive 35 的 battle 11 编队，因此 mGBA 通用 battle 11
路线只能证明 battle ID 接线与既有回合没有回归，不能伪称已经观察到原作被动演出。
首次回归还暴露了连续场景的静态精灵缓存没有在下一场部署前释放，battle 11 曾稳定停在
部署第 6 帧；该资源生命周期缺陷已由
`notes/butano-battle-scene-resource-lifetime-20260726.md` 的红绿测试和 mGBA
`0→1→0` streaming 路线修复并闭合。
自然取得条件、日文名和专属动画仍需原 ROM 脚本/存档证据。`0x1A–0x1C` 已在后续地形
里程碑闭合为类别 `1/3/7` 的逐路径预算，并同时接入玩家移动、AI 规划和威胁场；证据与
边界见 `notes/battle-terrain-passive-runtime-20260726.md`。
targets `0x01–0x0B` 的双 pass 属性规则及 Butano 接线见
`notes/battle-persistent-passive-stat-runtime-20260727.md`；`0x0D–0x13` 的双 pass
动作修正规则及统一 catalog 接线见
`notes/battle-passive-action-modifier-runtime-20260727.md`。
