# Battle 31 佐助动作 19 场景解锁证据（2026-07-26）

## 结论

佐助主技能槽 10 的动作 19“狮子连弹”不是等级解锁，也不属于通用卷轴解锁。
原 ROM 在角色技能同步函数中写死了一条场景规则：

```text
battle_id == 31
variant == 0
character_id == 2（佐助）
primary action_id == 19
locked 0xFF → unlocked/unlearned 0
```

状态 0 仍不能进入战斗目录；玩家之后必须通过统一训练事务消耗一点修炼点，
把 `0→1` 后才可使用。场景规则不会直接授予 LV1，更不会绕开
`character_progression_record`、训练 controller 或 SRAM。

## 原 ROM 证据

基准 `rom/base.gba` SHA-256：
`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。

| 证据 | ROM 范围 / 地址 | SHA-256 / 值 |
|---|---|---|
| 完整技能同步函数 | `0x080899EC..0x08089AE0` | `30463276e94bac6f9727ed8975be22ccf0d140a03909c15b3c0cfbf60dda0cc1` |
| battle 31 专属分支 | `0x08089A1A..0x08089A4A` | `fc1be93699732ac44bbb2503a0aff271d25ab24e7f567d029eece500698d8f83` |
| 唯一调用窗口 | `0x08089B70..0x08089B86`；调用点 `0x08089B7E` | `31c4b54165a9a0f2dd4ccf9468b49035ab2c8aada673fdae6df6831429341368` |
| 动作定义表字面量 | `0x08089AD8` | `0x0854241C` |
| 章节状态字面量 | `0x08089ADC` | `0x020311D4` |

专属分支读取章节状态 `+0x16` 和 `+0x19`，依次比较 `31` 与 `0`，再比较角色 ID
`2` 和动作 ID `0x13`。匹配时绕过普通 `unlock_level` 非零门，把槽状态写成 0。
普通路径仍只处理带等级阈值的锁定槽。

公开攻略只作为玩家可见身份的交叉校验：佐助“Lion Combo”列为
10×3、80 stamina、95% success；通用技能卷轴清单没有佐助。
控制流和状态转换仍以 ROM 为唯一实现依据：
<https://gamefaqs.gamespot.com/gba/918717-naruto-konoha-senki/faqs/25752>。

## Butano 领域接线

唯一写入口为
`synchronize_scenario_action_unlocks(character_progression_record, unit_definition, battle_id, variant)`。
`battle_scene_controller::load` 在普通等级同步之后调用它，再把同一 progression 投影给
scenario loader。scene、renderer、动作菜单都没有第二份解锁状态。

集成边界：

- battle 30 / variant 0：零写；
- battle 31 / variant 1（Arena）：零写；
- battle 31 / variant 0 + 非佐助：零写；
- battle 31 / variant 0 + 佐助动作 19：只做 `0xFF→0`；
- 随后 `train_primary_action(slot 10)` 才做 `0→1 / TP 1→0`；
- controller 的真实 battle 31 / variant 0 load 必须观察到同一个 state 0。

## 可复现审计

`tools/analyze_battle_action_reachability.py` 对完整 ROM、函数、专属分支、调用窗口和两个
字面量 fail-closed，并把动作 19 分类为
`scenario_unlock_then_training`。机读结果在
`notes/battle-action-reachability-20260726.json`。

本证据只闭合动作 19 的领域解锁条件。原版触发该同步函数时的完整剧情画面、训练页面
演出、声音和章节导航时序仍未复刻，不能把领域规则通过上调为整段剧情功能等价。

## 本轮验证

- 聚焦 C++：动作 progression 与真实 controller 两个程序由“API 不存在”的编译红测转绿；
- campaign/SRAM 集成：battle 31 controller 的 state 0 经 scene progression 合并回
  佐助档案，编码进 4096 字节存档槽并解码后仍为 0；错误 party 的原子拒绝边界不变；
- 全量宿主：84/84 程序通过，guard
  `build/resource-guard/butano-action19-full-host-20260726-01.json`；
- Python：分析器、研究文档门禁和单一战斗域共 70 项通过，guard
  `build/resource-guard/butano-action19-python-20260726-01.json`；
- 零缓存 devkitARM 构建通过，guard
  `build/resource-guard/butano-action19-arm-clean-build-20260726-01.json`；
- 新 ELF 的遥测符号为 `0x0201F474`。隔离静音 mGBA 回归
  `artifacts/butano-action19-b32-session-20260726-01/` 完成 41→43→9→11→32，
  battle 32 六单位 `[1,2,3]/[12,35,1]` 进入 round 2、AI 替身已观察、两类错误均为 0。
  Lua 已在 frame 1162 写出 `capture-complete`、最终快照与审计；模拟器此后不主动退出，
  所以 heavy guard 最终以 idle timeout 清理已完成的 owned process。该清理状态不能写成
  “guard completed”，但也不是 ROM 停住。

构建 ROM / ELF SHA-256 分别为
`ede64755a9b937fe6266c52105a0746d77c24fe4de7e416fcd4a4a4de2c0cea1` /
`2dddfb027fd0e0a19aeb17ab1b3b2dff606b0133ca6478273ff37c0284328ce9`。
隔离 `staged.sav` 与 `rom/base.sav` 均保持
`2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc`。
