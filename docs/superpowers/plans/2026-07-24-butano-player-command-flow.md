# Butano 通用玩家基础指令事务与 Command Flow 计划

**目标：** 用可复用领域规则取代场景内的菜单/截图分支，使移动、术/忍具、补充查克拉、
休息和行动结束都由同一个 `BattleSession` 与玩家行动控制器执行。

**架构：** 原作 `0x3000/0x3200/0x3210/0x3300/0x3310/0x6000` 证明资源指令同样遵循
“预览无写入、确认原子提交、行动尾部统一调度”。Butano 侧新增固定容量命令目录和资源事务，
由 `battle_player_action_flow` 组合；场景只投影 snapshot、输入和演出，不再直接调用
`BattleSession::preview_move` 或自行改变 HP/查克拉。

## Task 1：原作资源规则证据

- [x] 红测：锁定 `0x3200` 的每点查克拉成本读取 `unit+0x0A`，且要求 `HP > cost`。
- [x] 红测：锁定 `unit+0x0E` 为战斗内最大 HP，并用跨角色样本验证休息量
  `floor(max_hp / 5)`。
- [x] 扩展机读 manifest、逆向记录和架构文档；保留尚未闭合的被动修正边界。

## Task 2：命令目录与资源事务

- [x] 红测：五类命令按单位状态和移动草案动态返回 available/disabled/hidden/reason。
- [x] 红测：查克拉数量上限同时受缺失查克拉与“HP 至少保留 1”约束。
- [x] 红测：查克拉/休息预览零写；非法确认零写；合法确认一次性提交并截断到资源上限。
- [x] 在 `UnitInstance` 保存原作 `hand_seals` 字段，角色模板实例化时传入。

## Task 3：通用玩家 Command Flow

- [x] 红测：`begin` 生成命令 snapshot；循环、进入/取消移动、合法路径预览都不由场景判断。
- [x] 红测：移动确认回到动态命令菜单，取消完整回滚草案。
- [x] 红测：补充查克拉数量选择和休息确认走共享资源事务；提交后完成单位并求值目标。
- [x] 保留技能/目标/面向/防御已有流程，避免另建平行状态机。

## Task 4：场景适配与验收

- [x] 场景 41 的移动合法性和预览委托 `_player_flow`，教程 policy 只过滤可见命令。
- [x] source wiring 测试禁止场景直接调用 `_session.preview_move` 或写资源。
- [x] 运行全部宿主 C++、定向 Python、`diff --check`、无警告 devkitARM 构建和受守卫
  mGBA 路线；全量 Python discovery 的 Python 3.9/API 不兼容、既有语义断言与历史归档
  输入缺失单独记录，不伪报通过。
- [x] 更新 `notes/`、架构文档和 `docs/sequel-roadmap.md`，明确场景 41 教程不会开放
  休息/补充查克拉，但后续关卡可直接复用同一事务。
