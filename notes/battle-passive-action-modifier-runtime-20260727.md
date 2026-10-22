# 持久被动动作修正运行记录（2026-07-27）

## 纠错结论

旧覆盖矩阵把 targets `0x0D–0x13` 的 9 条定义记成“ROM 无消费者”，原因与 targets
`0x01–0x0B` 相同：分析只追踪了通用查询器 `0x0806DDA4`，没有识别动作初始化器内的
24 槽内联遍历。原 ROM 的 `0x0806D6B8` 不是菜单或表现函数，而是在每次主动技/忍具
模板物化后修改运行时动作字段；这直接影响正式预览、AI 与 resolver。

fail-closed 分析器 `tools/analyze_battle_passive_action_modifiers.py` 现锁定：

- 基准 ROM SHA-256：
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- 完整函数 `0x0806D6B8..0x0806D855`：
  `eb6688fd7b16927475ffe10c3a833326e0792ea13c8595de9a642722324182ff`；
- 百分比 pass `0x0806D6C0..0x0806D75D`：
  `60d7c5e123dc9f1ff1ecd2fa1b7f9ec13288263ea8f6cee7204c529febac090c`；
- 固定加值 pass `0x0806D75E..0x0806D84F`：
  `2627a331461dcb7a69d23ff10739f1842034b612f125a9e9ebb92f305467ae94`；
- flat jump table `0x0806D7B8`：
  `96d0da6fa4d9f53c7a9ea90ffe142314317fa5258f5dfa5dd80036308b86ddd2`；
- 主动技调用点 `0x0806D906` 与忍具调用点 `0x0806D954` 均 BL 到
  `0x0806D6B8`。

完整字段、指令门、调用顺序与谓词见
`notes/battle-passive-action-modifier-bindings-20260727.json`。

## 原作规则

每槽数值仍为：

```text
base_a + per_level_a × (stored_level - 1)
```

必须先完成全 24 槽百分比 pass，再完成全 24 槽固定 pass：

| target | 条件 | 字段与操作 |
|---:|---|---|
| 14 | `(header 0x0102 && effect != 0x21) || effect == 0x0A` | potency 百分比增加，上限 99 |
| 16 | header `0x0101` | potency 百分比增加，上限 99 |
| 13 | 与 target 14 相同 | potency 固定增加，上限 99 |
| 15 | header `0x0101` | potency 固定增加，上限 99 |
| 17 | header `0x0105` | potency 固定增加，上限 99 |
| 18 | effect `0x1A` | potency 固定增加，u8 保存、无显式 99 上限 |
| 19 | 所有运行时动作 | 成功率固定增加，写入前比较 999、最终 u8 保存 |

targets 14/16 在固定 jump table 中显式落到 no-op。主动技先执行动作等级成长再执行被动，
忍具先从模板建立工具槽成本再执行被动；顺序不能调换。

## Butano 数据流

`battle_action_loadout.h` 现提供一个纯动作副本修正器。生产接线只有一条：

```text
BattleUnitInstance.passives
  ├─ active definition → action_definition_at_level
  └─ tool definition   → ninja_tool_action_for_slot
                           │
                           ▼
              apply_persistent_passive_action_modifiers
                           │
                           ▼
                 BattleActionCatalog
                  ├─ player browser
                  ├─ AI candidates
                  └─ preview / resolver / presentation event
```

没有在 renderer、关卡 fixture 或单独菜单里复制规则。catalog 中主动技与忍具都使用角色
自身 24 槽状态；后续 resolver 直接消费修正后的 `action_definition`。

## TDD 证据

RED：

- 新领域测试因缺少 `apply_persistent_passive_action_modifiers` 编译失败；
- catalog 中主动技 16 和忍具 1 仍保持原始 potency/成功率；
- 覆盖矩阵仍报告 35 条有生产消费者、10 条无消费者，并把 passive IDs
  `10–14/31/32/36/40` 留在无消费者集合；
- 新 ROM 分析测试因缺少 `tools.analyze_battle_passive_action_modifiers` 失败。

GREEN：

- 主动技 5 的 target 14 百分比和 target 13 固定值按 `10 → 11 → 13` 生效；
- effect `0x21` 被物理谓词排除，effect `0x0A` 不依赖 header 仍可命中该谓词；
- 主动技 16 的 target 16/15 按百分比后固定值物化为 potency 18；
- 忍具 1 的 target 17 与通用 target 19、忍具 73 的 target 18 与 target 19 均通过；
- 99 上限与 effect `0x1A` 的 u8 边界由独立断言固定；
- 正式 catalog 的动作 16 送入正式 resolver 后，单段伤害严格高于未修正定义；
- 覆盖矩阵成为 44 条有 ROM 生产消费者、1 条无消费者；唯一无消费者行是 ID 0 哨兵。

## 验证

- 全部 94 个 `butano-sequel/game/tests/test_*.cpp` 以
  `clang++ -std=c++20 -Wall -Wextra -Werror` 编译并执行通过；guard：
  `build/resource-guard/butano-passive-action-modifiers-host-20260727-01.json`。
- 相关 ROM/analyzer/generator/单领域 Python 测试 30/30 通过。
- `python3 -m py_compile` 与 `git diff --check` 通过。
- 固定 devkitARM 构建通过；guard：
  `build/resource-guard/butano-passive-action-modifiers-arm-20260727-01.json`。
  - ROM SHA-256：
    `30719ed9750b832d6136967deeefad200101138d107fff186b1eb577c613aecd`
  - ELF SHA-256：
    `2a67a2367d09d8c6763efbe57a790a14e8986827fd1006f56bd5f061fffbc0d4`
- 受守护静音 mGBA：
  `build/butano-passive-action-modifiers-runtime-20260727-01/`。
  - exact ELF 遥测地址 `0x0201FB84`；
  - frame 2803，battle 9，round 2，phase 1，活动单位 9；
  - 鸣人动作 2/忍具、小樱动作 1、佐助动作 2/5/16 均来自正式目录；
  - controller/player error 为 0，两类 trap 文件均为空；
  - final state SHA-256：
    `2b433ce2f8f354fa0b34d331d3534cffb84bdbe09bf28256e2c87c9c0d6b60a5`。

## 未完成边界

- 当前自然新档 battle 9 路线没有已训练的 targets 13–19，因此 mGBA 只验收统一目录、
  resolver、玩家/AI 和回合结构；精确数值由 catalog/resolver 集成测试验收。
- passive ID 0 是内容哨兵，不应人为制造消费者以追求 45/45。
- 20 个初始未习得项已由统一训练状态机闭合为 `state 0 → 1`，动作 19 的额外场景解锁和
  动作 62 的 formation catalog 来源也已有 fail-closed 证据；见
  `notes/battle-action-reachability-20260726.md`。忍具装备例程同样已排除逐件容量成本。
  当前仍未闭合的是全零身份 39/40/52 的非命令用途、全部技能专属表现和非静音音频。
- 本轮 mGBA 明确静音，不能据此宣称用户报告的音频撕裂已经修复。
