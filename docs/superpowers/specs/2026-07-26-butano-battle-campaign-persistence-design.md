# Butano 战斗角色持久档案设计

## 目标

建立独立于单场 `BattleSession` 的战斗角色持久档案，使角色在一场战斗中获得的经验、
等级、修炼点以及主/副技能状态能够安全写入 SRAM，并在冷启动后的后续关卡重新进入既有
`progression → scenario loader → catalog → resolver` 链。

本设计解决的是战斗领域的跨关卡所有权，不把临时场景配置或画面状态当作存档。

## 证据边界

- 原 ROM 已证明角色持久保存等级、经验、修炼点、15 个主技能槽和 24 个副技能槽；
  技能状态转换与数值成长见
  `notes/battle-action-progression-20260726.md`。
- 原作攻略说明角色每级获得一点可分配技能点，战前可查看已选择的战斗技能；
  日文评测反复描述三人小队。攻略只能补充用户可见语义，字段和写入规则仍以 ROM 为准。
- `notes/battle-start-control-flow-20260713.md` 已证明三人编队/技能/装备属于战前流程，
  不是单场战斗控制器内部的截图页面。
- Butano 现有 `character_progression_record` 已是角色等级和 15/24 槽的唯一事实源，
  但 `battle_runtime_scene_request` 仍按值接收三条临时记录，退出后没有持久所有者。

## 方案比较

### 方案 A：只保存当前场景的三条 progression

实现量最小，但角色一旦不在当前三人队伍中就没有持久位置；后续关卡换人、隐藏角色和
自由三人组仍要重新注入夹具。该方案继续把当前场景误当作完整角色系统，不采用。

### 方案 B：直接把 C++ struct 原样写入 SRAM

能够快速冷启动恢复，但结果依赖编译器 padding、`int` 宽度和未来字段排列；任何结构调整
都可能把旧档解释为新档。单副本写入还会让掉电或中断破坏唯一存档，不采用。

### 方案 C：63 角色领域档案 + 显式字节协议 + 双槽恢复

这是采用方案。运行时档案保存全部角色，三人小队只是按角色 ID 建立的视图。存储协议逐
字段编码，带 magic、版本、payload 长度、generation 和 CRC32；两个固定槽总是保留一个
已验证旧 generation。格式与运行时 struct 解耦，可对坏 magic、坏版本、坏 CRC 和非法
领域值失败关闭。

## 领域模型

`battle_campaign_state` 包含：

- 63 个按 `character_id` 索引的 `character_progression_record`；
- 三个当前小队角色 ID；
- 当前章节 ID 与持久 flags；
- 每名角色九个持久忍具装备 ID。

当前里程碑只让 progression 和小队投影进入战斗。忍具装备随档案保存并验证，但在现有
章节/装备 UI 完成前，不替代显式 `battle_scenario_load_policy`；这避免把 battle 41
验证夹具误报成原作库存。

档案不保存：

- 当前战斗 HP、查克拉、坐标、行动账本、RNG 或表现队列；
- 世界地图脚本栈、忍具背包数量或武器强化；
- mGBA savestate。

## 存储协议

SRAM 使用两个 4096 字节槽。每槽布局：

```text
0x000  magic "KBCS"
0x004  version u8
0x005  reserved u8
0x006  payload_size u16
0x008  generation u32
0x00C  payload
0xFFC  crc32(bytes[0..0xFFB])
```

payload 先保存章节、flags、三人小队，再保存 63 条定长角色记录。角色 ID 由数组索引
隐含，不重复序列化。每条记录显式保存 active、level、experience、training_points、
action_states_initialized、15 个主技能状态、24 个副技能状态和 9 个忍具 ID。未使用字节
固定清零，保证同一输入生成完全相同的字节。

解码还要执行领域验证：

- active 角色必须指向有效的生成角色定义；
- level 必须为 1–50，经验和修炼点必须在编码范围内；
- 技能状态只允许 `0`、`1..3` 和 `0xFF`；
- 忍具 ID 必须为 `0..93`；
- 非零小队角色必须 active、互不重复。

两个槽都无效时返回调用方提供的新游戏默认档案，而不是从随机 SRAM 猜状态。只有一个槽
有效时使用该槽；两个都有效时按 32 位串行号选择 generation 较新者。`0xFFFFFFFF→1`
视为合法回绕，不能用普通无符号大小比较把旧槽误判为最新。

保存时向较旧/无效槽写入 `generation + 1`，再读回并完整解码验证。验证失败不得更新内存中
的 generation，也不得破坏另一个有效槽。

## 运行时数据流

```text
SRAM 双槽
   │ load + validate
   ▼
BattleCampaignState[63]
   │ project party by character_id
   ▼
BattleRuntimeSceneRequest
   ▼
BattleSceneController progression roster[3]
   │ result / level-up / training
   ▼
merge by character_id
   ▼
BattleCampaignState[63]
   │ encode + inactive-slot write + read-back verify
   ▼
SRAM 双槽
```

`run_battle_scene` 负责场景边界的投影与合并；controller 不依赖 SRAM，也不知道完整 63 人
档案。表现层只读取 controller snapshot。用户按 START 中途退出时，战斗内状态不会进入
档案；只有结果/修炼已经改变 progression 时，合并结果才与入场档案不同。

## 用户可见行为

- 冷启动时自动读取最新有效档案；全新或双槽损坏时使用明确的新游戏默认值。
- battle 41 升级并投入技能点后退出，ROM 把角色档案写入 SRAM。
- 再次冷启动进入 battle 41 时，鸣人的等级、经验、剩余修炼点和已学习技能沿用上次结果。
- 单槽损坏时自动回退到另一有效 generation，不显示伪造的半份角色数据。
- 本里程碑不新增存档选择 UI；当前自动档用于证明战斗领域的跨关卡所有权。

## 测试与验收

1. 纯领域测试先失败于缺少 campaign 模型，随后覆盖 63 角色初始化、三人投影、按角色 ID
   合并以及无关角色零改动。
2. codec 测试先失败于缺少编码器，随后覆盖确定性字节、完整 round-trip、坏 magic、
   坏版本、坏 CRC、非法角色/小队/技能/忍具和双槽回退。
3. 场景集成测试证明 controller 产生的 `LV1→LV2`、经验和技能 `0→1` 会合并回 campaign；
   取消或未结算退出不改变档案。
4. ARM 构建检查两个 4096 字节工作槽位于 EWRAM，不进入 IWRAM 栈。
5. mGBA 使用隔离的 staged ROM/SAV：第一次完成 battle 41 并保存，第二次冷启动读取同一
   `.sav`，从屏幕/遥测和 SRAM generation 同时确认 LV2 与技能状态。

## 未纳入本里程碑

- 原作 SRAM 二进制兼容；
- 手动存档槽 UI、世界地图和章节解锁；
- 忍具背包/强化与战前装备页面；
- 副技能修炼资格；
- 战斗中途存档；
- 非静音音频签发。
