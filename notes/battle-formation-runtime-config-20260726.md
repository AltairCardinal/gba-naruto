# 战斗编队运行时配置闭环（2026-07-26）

## 纠错结论

此前 Butano 只从 `0xB8` 编队记录读取角色、阵营、坐标、面向和携带经验，实际战斗等级、
主动术、被动状态和忍具仍从通用角色模板或关卡手填 policy 获得。这会把“同一角色在不同
关卡拥有不同等级/技能/装备”的原作数据压平，也无法支撑后续关卡。

当前内容链完整保留每条编队记录的运行时配置：

```text
ROM 0xB8 formation record
  ├─ +0x0F level
  ├─ +0x10 15 × { action, state, unlock_level, reserved }
  ├─ +0x4C 24 × { passive, state, unlock_level, reserved }
  └─ +0xAC 9 × ninja_tool_id
            │
            ▼
BattleScenarioUnitRuntimeConfig
            │  progression > explicit policy > formation > character template
            ▼
BattleUnitInstance
  ├─ level + level-grown stats
  ├─ primary_action_ids[15] + primary_action_levels[15]
  ├─ passive slots[24]
  └─ equipped_tools[9]
            │
            ▼
shared player/defense/AI action catalog (capacity 24)
```

这不是按截图拼菜单。动作身份、等级、被动和忍具进入同一 `BattleUnitInstance`，玩家、AI、
防御目录和 resolver 都读取该实例。

## 原 ROM 字段与控制流证据

完整原始矩阵仍按以下公式提取：

```text
file 0x5461C4
  + group_id × 0x1AAC
  + variant_id × 0x08E4
  + 4
  + record_id × 0xB8
```

原始范围为 48×3×12，共 1,728 条；Butano 当前场景目录消费其中 47 个已验证 battle ID。
每个四字节动作槽按 `{action, state, unlock_level, reserved}` 原样保存。`+0x0E`
`unit_parameter` 也进入实例，但其完整业务名称仍保持中性。

静态证据：

- 构造器 `0x0806ACAC..0x0806ADC4` 复制 level、15 个主槽、24 个副槽和 9 个忍具，再应用
  角色成长；对应 ROM 文件切片 `0x6ACAC..0x6ADC4` SHA-256 为
  `f83af5b97e73a29d9914028d3ab7c17c31d98da02da1299800dd940fbd308360`；
- 调用/选择链 `0x0806E1C0..0x0806E332` 的文件切片 SHA-256 为
  `9f639f6f06b68e56515f85447e2fc03167924826bfa7e934145dc55d19dca6fc`；
- selector `0` 是 inactive；`0xFA..0xFF` 走部署占位映射；固定敌方记录直接构造；
  普通玩家记录优先查找已存在的 24 槽队伍模板，只有脚本/显式配置记录由编队拥有完整配置。

因此当前所有权规则是：

1. 玩家 progression 已初始化时，持久角色状态优先；
2. 章节显式 policy 可覆盖等级或 9 个忍具，并可用独立布尔值明确覆盖为空；
3. 固定敌方、脚本角色或带非零主动作的固定玩家记录使用编队内嵌配置；
4. 普通玩家记录继续使用角色/队伍模板，不能因编队记录的零填充清空技能；
5. 部署 placeholder 只提供位置和 selector，不拥有内嵌角色配置。

## 代表性记录纠错

battle 10 variant 0 record 2 的原始尾部是 `... C8 00 01 14`，其中 `+0x0E=1`，
`+0x0F=0x14`，所以敌方鸣人是 **LV20**，不是此前人工摘要里的 LV1/LV2：

- 等级属性：HP355、AT33、DF32、AG27（CK5、MV3、忍具容量5）；
- 主动作前三槽：动作 `1/2/5`，状态均为 `2`；
- 副槽前三项：`{6,1}`、`{5,3}`、`{2,2}`；
- 忍具：`[1,19,41,41,41,0,0,0,0]`；
- 正式动作目录为 3 个主动术 + 5 个忍具，共 8 项。

该样本由提取测试、生成测试和 `test_battle_scenario_loader` 同时锁定。

## 多体召唤与占位

effect `0x17` 的成对召唤会在同一目标格激活两个 reserve，并通过
`ai_linked_unit/ai_secondary_linked_unit` 组成一个多体实体。此前地图占位器把第二个成员
当作普通重复单位，下一名 AI 在重建占位图时返回 `execution_failed`。

当前修复要求施术者、主召唤体和辅助召唤体都携带 `unit_state_code=0x06`；地图只允许
`0x06` 且确有链接关系的成员共享格点。普通同格活动单位仍返回
`duplicate_unit_position`。battle 30 全场景推进测试已覆盖召唤后的后续 AI 回合。

## 内存预算

15 个主动术 + 9 个忍具要求目录容量 24。为了不突破 GBA 场景快照预算：

- `BattleActionMenuView` 的 source/cost/target 三个小枚举共用一个字节位域；
- 结算定义仍保留 16 位 cost；只读菜单快照使用 8 位 cost，完整原 ROM 动作/忍具表最大值
  为 200，并由运行时门禁遍历验证；
- 菜单项不超过 9 字节，玩家 flow 快照不超过 384 字节，12 单位场景快照不超过
  1,120 字节。

## 验证

- 提取/生成：11 项 Python 测试通过；重新提取的 1,728 条 JSON 与重新生成的 C++ 头文件
  逐字节一致；
- 宿主：全场景测试可把所有非空变体推进到 round 101 或合法结束；完整宿主测试在修正一条
  过期射程路线后通过；最终 77/77 程序通过，guard 与逐项日志分别为
  `build/resource-guard/butano-formation-final-full-host-20260726-13.json` 和
  `build/resource-guard/butano-formation-final-full-host-20260726-13.log`；
- 文档、提取、生成与 mGBA 路线契约合计 69 项 Python 测试通过；
- ARM：固定 devkitARM Docker 构建成功，ROM/ELF 分别为 9,786,292 / 20,240,536 字节；
  最终产物复核 guard 为
  `build/resource-guard/butano-formation-final-arm-build-20260726-14.json`；
- mGBA：`artifacts/butano-formation-runtime-20260726-02/` 在 frame 2791 完成部署、
  battle 41→43→9、鸣人位移、忍具、樱召唤、佐助动作 2/5/16、五敌 AI 和 round 2；
  活动单位 9，controller/player error 为 0；
- 当前 ROM SHA-256：
  `230e61f83028499822b221cb4470005529f06b747172ce1514cca7adb4336635`；
- `rom/base.sav` SHA-256 保持
  `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

第一次 mGBA 尝试使用旧 `mgba_battle_09_multi_unit.lua`，它不认识当前真实部署阶段
`0xFFFFFFFE/0xFFFFFFFD`，因此停在 battle 41 部署并由 guard idle timeout 清理；失败证据
保留在 `artifacts/butano-formation-runtime-20260726-01/`，不计为 ROM 失败。

## 边界

- 自动 mGBA 路线静音，只证明 ARM 会话、部署、技能和回合链，不签发音频听感；
- `unit_parameter`、部分零配置敌方记录、章节队伍模板持久化仍需继续取证；
- 24 个副槽当前进入已知被动消费者；未知被动不能仅凭名称实现；
- 该里程碑闭合编队数据所有权与运行时接线，不代表所有动作可达性、对象专属表现、章节脚本、
  动态选人换装和全游戏战斗功能等价已经完成。
