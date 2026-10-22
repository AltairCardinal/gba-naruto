# 战役队伍/装备到动态部署的正式接线（2026-07-26）

## 缺口

SRAM 已保存 63 个角色记录、三人队伍和每角色九个已装备忍具，但此前可见战斗只把
`CharacterProgressionRecord` 投影给 controller：

- `0xFF/0xFE/0xFD` 三个常用部署占位符没有从 campaign party 取得角色；
- campaign 中的九格装备没有进入 `battle_scenario_load_policy`；
- battle 41 的 campaign overload 仍在 scene 中硬编码忍具 67/11；
- 因此存档字段、部署画面、动作目录和忍具 resolver 是断开的四段。

## 所有权与实现

新增纯领域函数 `apply_battle_campaign_scene_policy()`。它先用既有
`project_battle_campaign_party()` 验证队伍，再在候选 policy 上原子完成：

1. party 位置 0/1/2 分别填充尚未绑定的 placeholder 0/1/2，也就是 selector
   `0xFF/0xFE/0xFD`；
2. 对每个队伍角色，把 campaign 九格装备设为显式 loader override；
3. 章节已经显式提供的 placeholder 或装备 override 保持优先；
4. 校验失败时不修改调用者 policy。

`run_battle_scene(request)` 在任何 deployment/controller 创建之前应用该 policy。随后同一份
policy 同时进入：

```text
Campaign party / equipped tools
            │
            ▼
BattleDeploymentFlow（可见逐单位确认）
            │
            ▼
BattleScenarioLoader → BattleUnitInstance
            │
            ▼
ActionCatalog / Browser / Resolver / tool-slot consumption
```

battle 41 的 campaign overload 已删除场景级装备常量。新档案的默认 Naruto 装备 67/11/37
现在写入 `campaign_checkpoint.characters[1].equipped_tools`，再经过上述正式链进入战斗；
读取到有效旧档案时，SRAM 内容仍优先，不会被新档案默认值覆盖。无 campaign 的独立
battle 41 fixture 继续保留显式装备，避免把测试入口误当成存档入口。

## TDD

红阶段：

- `test_battle_campaign_scene_policy.cpp` 因缺少
  `apply_battle_campaign_scene_policy` 无法编译；
- source wiring 测试先发现 campaign overload 仍直接写
  `character_equipped_tools[1][0/1]`。

绿阶段：

- party `{1,2,3}` 解析 battle 1 variant 2 的三个部署占位，部署预览和最终 loader
  都得到角色 1/2/3；
- Naruto 的 `{1,17,73}` 进入单位九格装备，Sasuke 的章节显式 `{93}` 保持优先，
  Sakura 的 campaign 空装备显式清除编队内嵌值；
- 无效 party 返回 `inactive_character`，placeholder、装备和 override 三组 policy
  均保持不变；
- battle 41 campaign 入口不再含场景硬编码，新档案默认装备从 campaign 字段进入。

## 验证

- 全量宿主：82/82，guard
  `build/resource-guard/butano-campaign-scene-policy-full-host-20260726-01.json`；
- 清洁 devkitARM：
  `build/resource-guard/butano-campaign-scene-policy-arm-build-20260726-02.json`，
  exit 0、无代码 warning/error、peak 89.008 MiB；
- 静音 mGBA：
  `artifacts/butano-campaign-scene-policy-b11-runtime-20260726-02/`，冷启动经过
  battle 41→43→9→11，battle 11 五单位部署后进入 round 1，并观察地图 chunk
  `0→1→0`，最终 controller/player error 为 0。

最终 ROM/ELF SHA-256：

- ROM：`ff2a69238ac45805110d90e9eda6405769d1b04e9812837596d2d42d41089c39`
- ELF：`ea86a5b129f7b7f59abd74e867e7eaf18a444f0eee8a678592beb2d9a3e442b3`

`rom/base.sav` SHA-256 仍为
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。

## 边界

- 33 个只使用 `0xFF/0xFE/0xFD` 的动态编队变体现在具备正式三人队伍来源；
- battle 31 variant 1 与 battle 32–38 的 `0xFA..0xFF` 六席已经由 ROM affiliation、
  竞技场攻略流程和双方选择顺序闭合为 Arena 玩家队/对手队，不再归因于章节 NPC 或临时
  队伍；它们通过独立的 arena roster policy 填充，不能从 campaign 复制前三人，详见
  `notes/battle-arena-roster-runtime-20260726.md`；
- campaign 当前保存的是已装备九格，不是完整背包；后续里程碑已经闭合战斗内消费到九格
  campaign/SRAM 的回写，见 `notes/battle-campaign-tool-writeback-runtime-20260726.md`。
  章节背包数量、补给和换装 UI 仍未闭合，不能把本项宣称为完整道具库存系统；
- 当前主循环没有 33 个动态变体各自的章节入口。该链闭合的是后续关卡可复用的正式部署和
  装备依赖，不是伪造关卡选择器。
