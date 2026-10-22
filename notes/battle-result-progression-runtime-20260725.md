# 战斗结算、经验与成长链（2026-07-25）

> 2026-07-27 纠正：下文 round 2 / total 175 是当时通用链路的早期样本，已被
> `artifacts/butano-s41-four-round-runtime-20260727-22/audit.json` 取代。当前
> scenario 41 通过共享 controller 在 round 4 结束，结果为
> `100 + 50 + 0 = 150`，鸣人升级到 LV2、剩余经验 0，并继续完成动作 8 修炼和
> campaign 存档。任务规则与运行边界见
> `notes/battle-scenario-41-mission-rules-runtime-20260727.md`。

## 结论

原 ROM 的战后页面不是关卡脚本中的固定截图。它由四类独立数据和三个阶段组成：

```text
formation unit +0x0C
    -> battle unit +0xCE carried EXP
    -> 击败/关联单位结算给实际归属角色
    -> result preview（任务 / 回合奖励 / 战斗 EXP）
    -> apply experience
    -> level settlement（阈值、修炼点、七项成长差）
```

Butano 版现按同一边界实现：

- 编队记录的 `battle_experience` 进入 `battle_unit_instance::carried_experience`；
- 伤害 resolver 只在目标真正被击败时把携带经验转移给攻击归属角色；
- `battle_result_system::preview()` 不修改持久进度；
- 结果页确认后 `apply_experience()` 写入经验；
- `settle_levels()` 再按角色阈值扣除经验、升级、增加修炼点并计算属性差；
- 通用 `battle_scene_controller` 负责
  `outcome -> result -> level_up -> complete`，renderer 只显示快照。

这条链同时被旧 scenario 41 兼容入口和当前 ROM 主路径
`battle_runtime_scene` 使用，关卡不再直接写 `100/50/150/2/+14`。

## 原 ROM 证据

### 编队携带经验

formation 记录 stride 为 `0xB8`。`0x0806ACAC` 接收该记录，先构造角色模板，再由：

```text
0x0806AD92  ldrh r0, [record, #0x0C]
0x0806AD96  unit + 0xCE
0x0806AD98  strh r0, [unit + 0xCE]
```

写入战斗单位。基准 ROM 的交叉样本：

| battle/group | 单位 | record `+0x0C` |
|---:|---|---:|
| 41 | 鸣人 | 0 |
| 41 | 木叶丸（character 30） | 50 |
| 9 | 鸣人/佐助/小樱 | 0 |
| 9 | 五只猫（character 41） | 每只 30 |

运行时在胜利边界观察到 scenario 41 鸣人 `+0xCE=50`；battle 9 三名玩家分别为
`60/60/30`。静态转移点 `0x0806B224..230`、`0x0806B29E..2AA`、
`0x0806B2EC..2F8` 会把被击败或关联单位的 `+0xCE` 加给归属单位。

### 任务与回合奖励

- 场景到奖励记录映射：file `0x348DAC`，48 个 u8；
- 奖励表：file `0x59EAE0`，112×`0x18`；
- 表尾严格等于经验阈值表起点 `0x59F560`；
- 已证明的奖励记录前三个 u16：
  `mission_experience`、`round_bonus_experience`、`round_limit`；
- `current_round <= round_limit` 才取得回合奖励。

scenario 41 映射到 record 104：`100,25,3`。原作自然路线在 round 4 结束，所以
显示 `100 + 50 + 0 = 150`。当前通用 Butano 接线样本在 round 2 结束，因此同一规则显示
`100 + 50 + 25 = 175`；这不是另一组硬编码数字，而是当前实际回合数造成的可解释差异。

record `+0x06..+0x17` 作为九个原始 postbattle u16 保留，但在消费者语义闭合前不命名。

### 等级阈值

`0x0808983C` 使用 file `0x59F560` 的 63×4 表：

```text
required(level) = base_threshold + per_level_increment * (level - 1)
```

经验足够时反复扣除并升级，最大等级 50。`0x080898E0` 在实际结算时把升级数加入
持久修炼点，满级剩余经验钳制到 999。

| character | increment | base |
|---:|---:|---:|
| 鸣人 1 | 15 | 250 |
| 佐助 2 | 15 | 180 |
| 小樱 3 | 15 | 150 |

因此鸣人初始 `LV1 EXP100` 在原作 scenario 41 得到 150 后为 `LV2 EXP0`；当前
round-2 接线样本得到 175 后为 `LV2 EXP25`。

### 属性成长

`0x0806D964` 消费既有 file `0x545068` 的 63×`0x10` 成长表：

```text
value(level) = clamp(base + growth * (level - 1) / 100)
```

战后 `0x08089AE0` 分别构造旧等级和新等级模板，再显示七项差值。鸣人 `LV1 -> LV2`
的 HP `+14` 来自 `1450 * 1 / 100` 的整数除法，不是固定升级页面常量。

## 生成内容与运行实现

- `tools/extract_positions.py` 无损提取 formation `battle_experience`；
- `tools/extract_battle_result_content.py` 提取 112 条奖励、48 条映射和 63 条阈值；
- `tools/generate_butano_battle_result_content.py` 生成固定容量 C++ 表，并复用
  `sequel/content/character-stats/bank.json` 的 63 条成长；
- `battle_progression.h` 只负责角色属性和等级纯函数；
- `battle_results.h` 只负责预览、经验应用和等级结算；
- `battle_action_system.h` 负责战斗内携带经验归属；
- `battle_scene_controller.h` 负责可见阶段，不计算奖励公式；
- `battle_runtime_scene.cpp` 只渲染结果。

`battle_scene_snapshot<12>` 仍保持原 1100-byte 上限；较大的三人结果和持久 roster 留在
EWRAM controller，通过只读 accessor 提供给 renderer，避免重新把大对象压入 GBA 栈。

## 验证

- ROM 表提取/生成交叉测试覆盖 scenario/battle 41、9、角色 1/2/3；
- 宿主测试覆盖携带经验加载、击败转移、回合奖励边界、跨关卡阈值、多级升级、
  preview 不写持久状态及通用 controller 结果阶段；
- 全部 game host C++ 程序通过严格 warning-as-error 编译；
- Docker devkitARM 构建通过；
- 静音 mGBA 证据：
  `artifacts/butano-battle-results-s41-20260725-315/`。

最终审计为 round 2、participant 1、mission 100、battle 50、bonus 25、total 175、
`LV1 -> LV2`、remaining EXP 25、HP `+14`，control/player error 均为 0。
最终 ROM SHA-256 为
`9c45c5cb6e40f446c3b1d9de638e29870dcd1059a8131b5623c1fe0dd8969b78`。

## 边界

- 自动 mGBA 静音，不能证明主观音频质量；
- 当前可见通用结果页先显示第一个角色；领域结果已经保存三名参与者，但多角色逐页浏览、
  多个升级页和战后物品/解锁页面仍需接入；
- 奖励记录后九个 u16、被动 EXP 加成 `type 0x15`、召唤/关联单位的全部特殊归属分支仍需
  更多运行时样本；
- 当前 scenario 41 通用接线在 round 2 结束，尚未恢复原作教程强制走到 round 4 的章节脚本；
- 这完成的是可复用结算纵链，不代表完整战斗系统 Goal 已完成。
