# 对敌爆弹忍具表现事务证据（2026-07-27）

## 目的

确认动画族 5、目标为敌方单位的忍具是否应在地图上直接结算，还是进入和主动术相同的
双角色战斗舞台。结论只约束场景事务和运行时分类；伤害、状态、命中率、持续时间和库存
消费仍由现有领域层负责。

## 输入与可复现边界

- 原 ROM：`rom/base.gba`
  - SHA-256：
    `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
- 起始存档：
  `artifacts/runtime-checkpoints/scenario-50-battle-15-round3-frontline-assembled.ss9`
  - SHA-256：
    `9ce9973360b8636952b0cbd44b44104b1a8ded15f52a07c11e284157831b420e`
  - battle 15 第三回合，鸣人 `(4,5)` 与敌人 `(4,6)` 相邻。
- 追踪脚本：`tools/mgba_trace_action_presentation.lua`
  - 新增忍具初始化器 `0x0806D910`，并记录
    `tool_initializer_hits`。
  - 输入使用显式帧序列
    `MGBA_ACTION_PRESENTATION_KEY_SEQUENCE`；捕获包括 360、480、720、960、1200
    后续状态，避免只看开头而误判返回流程。
- 全部 mGBA 进程通过 `tools/run_guarded.py`，原始截图、savestate、
  I/O/OAM/PRAM/VRAM 和 trace 均使用唯一 run 目录，没有覆盖历史产物。

## 被推翻的旧结论

早先从 `build/type2-capture-menu-tool39.ss9` 只修改单位装备字节
`0x02024345: 0x27 → 0x31`，再观察 tool 49。该状态的动作组件表
`0x02026A8D` 已在修改前缓存，第四行仍是 tool 39，因此后续相同截图和 trace
只证明再次执行了 tool 39，不能证明 tool 49 的表现。

控制 run 与该错误 patched run 逐字节相同。旧“tool 49 与 tool 39 同为地图表现”
结论由本记录明确取代。

## 自然目录构造

从 battle 15 的未缓存状态只把鸣人首个忍具槽改为 tool 49：

```text
0x02024345: 0x01 → 0x31
```

随后等待自动阶段完成，自然选择鸣人并进入 `术・忍具`。动作列表构造命中
`0x0806D910` 两次，均有 `r0=0x31`；运行时 6 字节动作行的第四项为 `0xB1`
（高位表示忍具，低 7 位为 49）。菜单显示 `猛烈弹`，攻击 `28×1`、距离 2、
范围 1、命中 100%。证据目录：

- `build/battle-presentation-original-probes-20260727-11/tool49-list/`
- `build/battle-presentation-original-probes-20260727-12/tool49-confirm/`
- guards：
  `build/resource-guard/original-tool49-natural-list-20260727-01.json`、
  `build/resource-guard/original-tool49-natural-confirm-20260727-01.json`

这条路线证明 ID 不是在已缓存的 tool 39 行上伪造出来的。

## 样本 A：tool 49 猛烈弹（伤害）

执行 run：
`build/battle-presentation-original-probes-20260727-13/tool49-execution/`

输入从确认状态只按一次 A。guard：
`build/resource-guard/original-tool49-natural-execution-20260727-01.json`。
audit：

```json
{"frame":1200,"initializer_hits":81,"tool_initializer_hits":3,"event_builder_hits":1,"hit_presentation_hits":1,"sequence_hits":5}
```

关键调用顺序：

```text
frame 32   0x0806D910 ninja_tool_initializer, r0=0x31
frame 32   0x080754A8 action_event_builder
frame 97   0x0807FDCC effect_resource_builder
frame 97   0x0807FE2C effect_sequence_selector, sequence=4
frame 123  0x08080108 visual_object_create
frame 133  0x0807B8B8 hit_presentation
frame 133  0x0807C5E8 bind_effect_sequence
frame 133  0x0807FE2C selector sequence=5/6
frame 321  0x0807FE2C final selector
```

可见阶段：

```text
地图确认
  → 擦除转场
  → 黑场
  → 鸣人与目标同屏的森林决斗舞台 + 双方 HUD + 忍具标题
  → 命中星芒
  → 投射/爆炸接触
  → 扩散烟雾
  → 返回擦除
  → 原地图目标格残留烟雾
```

关键帧 SHA-256：

- frame 100 决斗舞台：
  `e68e6d94a76e81e5a6e5bb6d7e792764f347f498bb0037d5110bbf48a1460bd9`
- frame 140 命中：
  `e86e23c8095caf74db2cc1b42ad967cd4822678c5f6b28a57b8c8384f164483d`
- frame 180 烟雾：
  `65a6f10a22ec965b1159bb6942b83f1a17d273aa935e1d3cc02401b2f99c9f56`
- frame 300 返回转场：
  `ea2558c4546c74a00185a8fdcee4facfd2944d873e38a403e6e9e0034903e09d`
- frame 360 地图恢复：
  `ed258c191f470e240fdb76efa6d0f7e060affdb6e16ebb42913be602a41f2b72`

## 样本 B：tool 55 软气弹（状态）

为验证分类不是“只有伤害弹进入决斗”，从已经构造好的 tool 49 列表状态同步修改两个
权威语义镜像：

```text
unit equipped slot  0x02024345: 0x31 → 0x37
cached action row    0x02026A9F: 0xB1 → 0xB7
```

第二处不是伪造场景，而是把已缓存目录行与装备槽同步为同一 tool 55 身份；追踪中选择、
目标、确认和执行阶段的 `0x0806D910` 均再次收到 `r0=0x37`。

执行 run：
`build/battle-presentation-original-probes-20260727-14/tool55-execution/`；
guard：
`build/resource-guard/original-tool55-natural-execution-20260727-01.json`。
audit：

```json
{"frame":1200,"initializer_hits":2,"tool_initializer_hits":7,"event_builder_hits":2,"hit_presentation_hits":0,"sequence_hits":2}
```

frame 407 进入 effect resource/sequence 4，frame 443 进入状态 sequence 9。
frame 480 明确显示双角色森林舞台、忍具标题 `软气弹` 和目标结果 `-25%`，frame 720
已回到地图及面向选择。两帧 SHA-256：

- `adeb5a5e57bf1c8ce45711eae9f081ddc3e48fccc2b712a36d50f9ea3e0b5375`
- `3f25f9134afc7f96df6e92ecf90107475cac0f85eafbe6ff3b62c5cf7d1e2d68`

## 架构结论

伤害样本 49 与状态样本 55 都满足同一外层事务：

```text
ActionResolved
  → transition_in
  → duel_setup(actor + target + HUD)
  → actor_prep
  → technique_title(tool identity)
  → action_movie
  → impact/domain-result projection
  → result
  → transition_out/map restore
```

因此 Butano 的生产分类采用语义规则：

```text
ninja tool
  + animation_family == 5
  + target.kind == opponent_unit
  → bomb_tool (8-stage combat transaction)
```

规则不读取 action ID、角色 ID、battle ID 或截图。tool 49–66 的生成定义都满足该契约；
其 effect code 仍分别走伤害或属性状态 resolver。family 1 对敌忍具继续使用
`thrown_tool`；family 5 的空格对象、友方药丸以及其他目标策略不会被误并入。

## tool 49 组件资源闭环

在上述自然执行状态上继续追踪 OAM/VRAM/PRAM，而不是把 240×160 合成帧导入 ROM。
`build/battle-presentation-original-probes-20260727-15/tool49-component-trace/`
把 tool 49 的两个独立对象序列闭合为：

- 投射物：原作 frame 125–131，共 7 帧、4 个独立 OBJ 资产、4 个 keyframe、每帧最多
  1 个组件；
- 爆炸烟雾：原作 frame 148–258，共 111 帧、25 个独立 OBJ 资产、70 个 keyframe、
  每帧最多 14 个组件，并保留半透明 OAM 属性；
- 两个序列都绑定原 ROM SHA-256 和 trace SHA-256，逐帧保存 OAM 构型及活动
  tiles/palette 匹配结果。生成器不读取屏幕截图。

持久 manifest：

- `notes/evidence/battle_ninja_tool_bomb_projectile_sequence_manifest.json`
  SHA-256
  `ba2d91da9ba0497c874a86b4934dfc4bfb01a15d460bda4689322f08a8579d93`；
- `notes/evidence/battle_ninja_tool_bomb_smoke_sequence_manifest.json`
  SHA-256
  `1b2c40c48ee972e72f3ec565d1006f496778de30e73790bf6b8c97c6f1f703df`。

生产 `bomb_tool` 事务现在把投射物、既有 impact 和烟雾作为三个连续资源阶段消费；
HP、死亡、库存和回合仍只由 resolver/session 提交，组件 renderer 没有领域写入口。

## 运行时发现：动作身份不能只用数值 ID

首次走 battle 9 正式忍具路线时，目标确认返回
`action_requirement_not_met`。这不是射程或 mGBA 问题，而是领域建模错误：
主动技与忍具拥有各自独立的数值 ID 空间；主动技 43–49 是八门相关技能，旧 resolver
却只按裸 `action.id` 调用资格查询，因而把忍具 49 错当成主动技 49，要求状态 `0x13`。

生产身份与资格查询已改为至少携带 `(source_kind, id)`：

```text
active action 49 → 应用主动技 49 的八门资格
ninja tool 49   → 不应用主动技资格；仍应用忍具槽、目标、射程和库存规则
```

玩家 browser 原本已经保留来源类型；本轮把相同约束补到 resolver 与 AI candidate field。
测试同时覆盖“主动技 49 无状态时拒绝”和“忍具 49 无状态时可执行”，防止两个命名空间
再次碰撞。目标选择阶段的 telemetry 也改为报告 `target_preview.error`，不再把目标拒绝
误报成动作列表错误。

## Butano 正式路线验收

最终路线：
`artifacts/butano-bomb-tool49-runtime-b09-20260727-07/`；guard：
`build/resource-guard/butano-bomb-tool49-runtime-mgba-20260727-07.json`。
它不是直接跳到演出帧，而是从 battle 9 三人部署开始，经正式的移动、单位命令、
术/忍具目录、目标、面向、防御和回合推进，在第三回合由佐助装备槽执行 tool 49。

`audit.json`（SHA-256
`28dc4e5969d03c57ea25c994a241932080e9d06947f7d0ea4edfe39e7f034cb9`）
记录：

```json
{
  "battle_id": 9,
  "actual_active_units": 8,
  "actual_round": 3,
  "actual_phase": 1,
  "last_resolved_action_id": 49,
  "sasuke_bomb_executed": true,
  "status": "capture-complete"
}
```

可见锚点包括 `sasuke-bomb-projectile-01/07.png`、
`sasuke-bomb-impact-08.png`、`sasuke-bomb-smoke-01/40/80/110.png` 和
`sasuke-bomb-map-restored.png`。人工检查确认投射物逐帧变化、impact 星芒、烟雾从单个
半透明组件扩散为大面积复合云团后消散，目标 HP 为 0，最后恢复 battle 9 地图并显示
`2/12 SELECT UNIT`；不存在“黑屏后再按一次 A”。execution trap 与 memory-write trap
均为 0 字节。

`-01` 是射程诊断，`-02` 是回合站位诊断，`-03` 暴露上述 source-kind 资格碰撞，
`-04` 已完成领域结算但末帧抓取使用了 1-based 名称作为 0-based counter；这些 run
保留为被取代的诊断证据。`-05` 是首次成功路线；显式 `source_kind` 字段重构后的
`-06` 已完整生成 audit，但 guard 调用遗漏 success marker，因而在进程完成后仍被
idle-timeout 终止；只有相同 ROM、带 success marker 正常退出的 `-07` 作为最终签发。

## TDD 与验证

- 红灯：
  `build/resource-guard/butano-bomb-tool-transaction-cpp-red-20260727-01.json`
  - 新枚举和事务尚不存在，聚焦 C++ 测试按预期失败。
- 绿灯：
  `build/resource-guard/butano-bomb-tool-transaction-cpp-green-20260727-01.json`
  - `test_battle_combat_presentation`
  - `test_battle_scene_presentation`
- 运行时接线与追踪工具：10/10 Python 通过。
- 完整宿主战斗套件：95/95，通过
  `build/resource-guard/butano-bomb-tool49-full-host-final-20260727-02.json`。
- devkitARM 构建通过：
  `build/resource-guard/butano-bomb-tool49-final-arm-build-20260727-02.json`。
- 资源分析、生成、运行时接线和 mGBA 路线相关 Python：22/22 通过。
- 静音 mGBA battle 9 全路线回归通过：
  `build/resource-guard/butano-bomb-tool49-runtime-mgba-20260727-07.json`。
  frame 3785 完成 tool 49，活动单位 `9 → 8`，回到 round 3
  `unit_selection`；execution trap 与 memory-write trap 均为 0 字节。
- 当前 ROM/ELF SHA-256：
  - ROM：
    `89d732022b73fdde26797f2a55be69e6b11e8bf2998be6d29ce72f3c2343508f`
  - ELF：
    `e9345eec02af2e2b6bc3f9b7ac64cabe9cea5be6082016aad4eca802a3e9eb33`

## 边界与后续

- tool 49 的投射物与烟雾组件、时长和自然运行路线已闭合；不把这项证据外推成
  tool 50–66 的逐项资源等价。标题字形和 sound cue 也尚未签发。
- 最终 mGBA 回归使用 `mute=1`，不重复签发音质；非静音事件骨架仍以
  `notes/butano-battle-audio-runtime-20260727.md` 的独立证据为准。
- Butano 当前 `bomb_tool` 使用通用双角色舞台和领域结果投影；tool 49 已消费独立
  投射/烟雾 sequence，其他同族工具仍只能共享事务结构，不能共享“逐项视觉等价”结论。
- tool 56–66 的 resolver 语义已有生成定义与领域测试，但逐项专属表现仍需自然路线取证。
- 这只是全战斗表现覆盖的一族，不代表完整战斗 Goal、全技能或后续关卡制作已完成。
