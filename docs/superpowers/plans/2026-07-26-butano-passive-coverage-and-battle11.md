# Butano 被动覆盖审计与 battle 11 双属性被动实施计划

1. [x] 红测：新增 45 行覆盖矩阵测试，固定 ROM 调用覆盖与 Butano 状态分类。
2. [x] 绿灯：实现可复现覆盖分析器并生成 `notes/` manifest。
3. [x] 红测：固定 battle 11 `0x20` 的双状态、battle ID 门、优先级、latch 和失败原子性。
4. [x] 红测：固定场景 loader 把 `scenario.battle_id` 接入 session。
5. [x] 绿灯：给 session 增加 battle ID，并实现 `battle_11_dual_boost` 领域事件。
6. [x] 重构：统一 side-start 查询与条件分发，不改变 `0x1D–0x1F` 行为。
7. [x] 集成：验证 presentation/controller 能观察到 battle 11 被动事件。
8. [x] 验证：运行相关 Python/C++、全量主机测试、ARM 构建与受守卫 mGBA。
9. [x] 更新架构、证据笔记和路线图，明确 28 条无直接消费者；当时对
   `0x1A–0x1C` 的视觉边界判断已被后续地形被动里程碑取代。
10. [x] 后续纠错：闭合 `0x1A–0x1C` 为类别 `1/3/7` 的逐路径预算，并接入玩家、AI
    与威胁场，证据见 `notes/battle-terrain-passive-runtime-20260726.md`。
