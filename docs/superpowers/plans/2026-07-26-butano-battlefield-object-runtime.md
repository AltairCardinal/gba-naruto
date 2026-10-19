# Butano 战场对象运行时实现计划

> 范围：落实既有战斗架构中尚未闭合的战场对象领域链，不扩展新的战斗设计。

**目标：** 让微型卷轴、引爆牌及关卡对象不再只是“可选择并生成一个占位记录”，而是按原 ROM 的对象布局进入阵营结束计时、到期解析、伤害/状态、条件解释器和表现队列。

**原作约束：**

- 对象表位于 `0x02026604`，32 项、每项 16 字节，slot 0 保留。
- `0x08081024` 分配对象并复制 `+4/+6/+8/+10` 四个 16 位字段。
- effect `0x0C` 在 `0x0807726E` 创建 type 2；effect `0x18` 在 `0x08077514` 创建 type 1。
- 两类对象均把事件 `+0x0C` 写入对象 `+4`，把事件 `+0x11 * 2` 写入对象 `+6`；type 1 还把事件 `+0` 写入对象 `+8`。
- `0x08081B70` 在每次阵营交替前遍历对象：type 1/2 都递减 `+6`；type 2 到期先播放 sequence 7 的坐标特效并等待完成后释放，type 1 到期按 `+4` 的忍具模板和 `+8` 的施放者解析范围效果后释放。

## 任务 1：固化逆向证据

- 新增 `tools/analyze_battlefield_object_runtime.py`。
- 新增 `tests/test_analyze_battlefield_object_runtime.py`，先写失败断言，再实现分析器。
- 输出 `notes/battlefield-object-runtime-20260726.json`，绑定 ROM 哈希、代码段哈希、调用点、字段来源和边界。

## 任务 2：恢复精确对象布局与生命周期

- 修改 `butano-sequel/game/include/konoha/battlefield_objects.h`，用明确字段替换猜测的 byte 数组，并以 `offsetof` 固定 16 字节 ABI。
- 新增对象阵营结束 tick 结果，区分“仍存活”“type 2 到期”“type 1 待解析”。
- 先在 `test_battle_action_system.cpp` 和 `test_battle_session.cpp` 写红测，确认现状因 payload、16 位 duration 和未计时而失败。

## 任务 3：接入到期领域效果

- 对 type 1 从生成的忍具目录按 payload ID 恢复威力、范围和标志。
- 使用既有伤害、被动、反应和状态链处理范围内单位，不另写平行伤害公式。
- 只在 `side_changed` / `round_advanced` 边界计时；在关卡条件求值前完成到期解析。
- 毒引爆牌必须走可测试的状态消费链；若原 ROM 证据不足，保留原始 flags 并把未证实语义标为边界，不猜测状态码。

## 任务 4：接入控制器与表现

- 暴露对象快照和到期事件给战斗场景控制器。
- 引爆/消失应进入既有表现队列；渲染器只读，不改变领域状态。
- 集成测试覆盖玩家放置、两次阵营结束、范围伤害、对象释放、条件解释器在同一边界观察到更新。

## 任务 5：验证和持久记录

- 运行相关 Python、主机 C++ 单元/集成测试。
- 运行完整主机战斗测试、内容生成一致性、ARM ROM 构建。
- 经 `tools/run_guarded.py` 运行 mGBA 自动化场景；自动化保持静音，不能据此宣称音频问题修复。
- 更新 `notes/battle-system-restoration-evidence-20260723.md`、架构设计和 `docs/sequel-roadmap.md`，明确已闭合与仍未闭合边界。

## 2026-07-26 type 2 纠偏补充

- [x] 不再把 `0x037F/12/14` 错称为资源 ID/参数；它们是
  tile index end 与 palette bank 区间，起点分别是 `0x0300/12`。
- [x] 绑定 sequence 7 → resource group `0x12` → graphics
  `0x083478F4` / palette `0x083480C8`，提取精确 7 帧 32×32 资源。
- [x] controller 将 actorless `type_2_expired` 事件排入统一表现 FIFO，
  presentation 管理生命周期，renderer 只读事件并播放专属精灵。
- [x] 删除存活对象的 `scenario_41_cursor` sprite。原作分配器只写地图格元数据，
  不创建可见游标；领域对象仍保留在 session snapshot/telemetry。
- [x] 聚焦 C++/Python 测试和 ARM 零缓存构建通过。
- [x] 新档 campaign 第三忍具槽暴露忍具 37；静音 mGBA 从正式动作目录创建对象，
  跨两次阵营边界后观察 kind 2 表现事务和对象释放。
- [ ] 原版自然路线的逐帧 hold 时长与音效仍需运行时证据；当前每帧 hold 4 帧是暂定值。
