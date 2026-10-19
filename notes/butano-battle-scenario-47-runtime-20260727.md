# Butano scenario 47 / Battle 13 真实战斗纵切（2026-07-27）

## 结论

scenario 47 已由共享战斗架构在 Butano ROM 中完成，不再是截图、选项或固定结果的拼接：

```text
scenario 47 campaign state
  → generated battle 13 / map 13 / formation / rewards / conditions
  → BattleSession（单位、位置、HP、查克拉、状态、回合）
  → BattleController（玩家公开输入与敌方 AI）
  → pathfinder / action catalog / resolver / summon / rest
  → presentation event FIFO
  → generated condition victory
  → per-participant result / progression / SRAM
  → scenario 49
```

宿主纵切和 mGBA 路线都只通过 controller 的公开输入推进。Lua 禁止 `emu:write`，没有写
HP、坐标、回合、敌人退场、胜负、经验或后继场景。最终截图只记录领域运行的可见结果，
不参与战斗计算。

## 原版真值

原版运行记录在 `notes/scenario-47-entry-runtime-20260720.md`：

- scenario 47 对应 battle ID 13，variant 0，地图为 13×21；
- 玩家为 Naruto、Sasuke、Sakura，初始位置分别为
  `(6,3)`、`(4,3)`、`(8,3)`；
- 敌方为五名 character 33 / LV3 / HP80，初始位置分别为
  `(1,10)`、`(3,14)`、`(6,16)`、`(9,14)`、`(11,10)`；
- 原版可持续路线使用“低 HP 角色休息、健康角色攻击”的轮换，并用影分身吸收火力；
- 第 33 回合自然击倒最后一敌，三名参与者各得 125 mission EXP；
- scenario 48 是学院纯剧情，下一战斗节点为 scenario 49 / battle 14。

Butano 内容装载器使用同一 generated battle row、map row、formation 和 condition，
没有为 scenario 47 复制第二份手写关卡数据。战役 RNG 也已纠正为 scenario ID 47，
与宿主纵切的确定性 seed 一致；旧 GBA adapter 错用 battle ID 13，会使宿主和 ARM
敌方决策分叉。

## 宿主领域纵切

`butano-sequel/game/tests/test_battle_campaign_scenario_47.cpp` 从 scenario 46 的真实战后
角色状态开始：

- Naruto LV4 / EXP180 / TP3；
- Sasuke LV3 / EXP185 / TP2；
- Sakura LV4 / EXP35 / TP3。

测试加载真实 13×21 地图和八个原始站位，测试侧 BFS 只根据地图通行与公开 snapshot
选择合法按键。生产 controller 负责移动预览/提交、行动目录、查克拉、休息、影分身、
敌方 AI、伤害、击倒、回合、条件和结果。该纵切明确验证：

- 休息命令确实恢复受伤单位 HP；
- 动作 7 创建可行动的影分身单位，而不是显示一张分身图片；
- 五名敌人都由 resolver 的真实伤害结果击倒；
- 三名角色合计获得 375 battle EXP，每人获得 125 mission EXP；
- 三人均经 progression 升至 LV5；
- campaign 从 47 原子推进到 49。

休息验证与最终 ROM 的最快路线是两个互补证据：宿主路线主动制造了需要休息的局面，
最终 mGBA 路线没有受伤到需要休息，故不能为了“打勾”而提交无效休息。ROM 审计中的
`scenario_47_rest_verified=0` 表示本次输入路线未执行，不表示休息系统缺失。

## “对话后冻结/黑屏”根因与修复

早期 ARM 路线在第 3–4 回合的战斗对白确认后停止推进。输入遥测与 GDB 证明 A 已经送达并
被脚本消费；CPU 随后进入 Butano assert，而不是等待第二次 A。断言为：

```text
bn_sprite_tiles_manager.cpp:921
Sprite tiles allocate failed. Tiles count: 8
```

GDB 同时记录：

- battle 13、phase 18、scene frame 1244、render stage 5；
- OBJ tiles manager 有 400 tiles 等待延迟回收；
- 当前只剩 start tile 960 / 64 tiles 的空闲块；
- 脚本肖像和文字刚释放，地图 HUD 在同一 `bn::core::update()` 之前立即申请 8 tiles。

因此旧表现层把两组互斥资源的生命周期重叠了一帧：

```text
脚本肖像/文字 cohort 释放（deferred）
  ╳ 同帧申请地图单位/HUD cohort
  → OBJ VRAM 分配断言
  → 画面停在上一帧，telemetry 也不再刷新
```

`run_visible_battle_scene` 现在以 `script_visuals_active` /
`script_visuals_visible` 建立表现模式边界。离开脚本模式时，它先释放肖像、单位 sprite、
HUD 文字和脚本 glyph，执行一次 `bn::core::update()` 完成延迟回收，再允许地图 cohort
分配。该修复只改变资源所有权和切换顺序，不改变领域 phase，也不吞掉玩家输入。

同时，脚本确认 A 在同帧拥有高于地图控制的优先级，并有 latch 防止同一次按压穿透到
下一层 UI。只读复审随后发现，旧循环虽然先处理脚本分支，却在判断前已经从 presentation
FIFO 弹出事件；对白等待期间该事件不会播放也不会回队。新增红测先复现该所有权错误，
生产循环现在只有在“非脚本等待且非活动演出”时才调用 `take_presentation_event()`，
排队的动作、对象和 side-start 表现会保留到对白结束。资源生命周期、输入优先级和 FIFO
所有权都有先失败后通过的 wiring 测试。

GDB 原始证据保留在：

- `artifacts/butano-battle-scenario-47-assert-gdb-20260727-03/evidence.json`
- `artifacts/butano-battle-scenario-47-assert-gdb-20260727-04/evidence.json`
- `artifacts/butano-battle-scenario-47-assert-gdb-20260727-05/evidence.json`

此前 `-01` 至 `-21` 的运行用于定位冻结、自动路线、断言和 FIFO 差异，均由最终 `-22`
取代；
原始失败产物不删除。

## 最终 mGBA 运行证据

最终运行：

- artifact：
  `artifacts/butano-battle-scenario-47-real-map-20260727-22/`
- guard：
  `build/resource-guard/butano-s47-real-map-mgba-20260727-22.json`
- machine-readable manifest：
  `notes/evidence/butano-scenario-47-real-map-runtime-20260727.json`

输入是 scenario 46 完整胜利生成的 generation 7 verified SAV，SHA-256：
`a75c7955eb35ce484c88dc6bc163efeff1ab3681471b42009cc3271bba50c738`。
路线在真实 mGBA 中得到：

- frame 24898 / round 31 / battle 13 complete；
- 五次击倒发生于 round 10、12、17、20、31；
- `shadow_clone_verified=1`，完成时 4 个活动玩家单位，说明分身仍在 session；
- 三名参与者，首名结果为 mission 125 + battle 75 + bonus 0 = 200；
- Naruto LV5 / EXP85 / TP4；
- save generation 8 / verified 1；
- scenario 49；
- controller/player error 均为 0；
- 无 `failure.txt`，guard 由 success marker 正常结束，峰值 122.08203125 MiB。

哈希：

- ROM：
  `36497840f4c636b39f9495ae5a2429ccda45e2ff1eb5e2c6fc0ae21202216a1a`
- ELF：
  `aefaa2d3786a1d42e88cb83d2c43254348ddfdff61d165494eb61c036b7c0869`
- route script：
  `743c51ea1794c2c985501f84dcc19a60ca38db069f59b9239a3827d67ec69943`
- output SAV：
  `3f473ececd31485800c1d907ca7a9b97350fc74f354ffb5a9032ce349a9dbc88`
- signed mGBA：
  `151ecb68819df5b6756ab96c8ff0eb4659e70cdafb98273109ad6d3f3cb75ccb`

运行时 telemetry 地址为 campaign `0x02008138`、battle `0x02022628`。Lua 只读这些字段并
发送按键；最终目录没有临时 PC/寄存器采样文件。

## TDD 与验证边界

本轮红绿覆盖：

- scenario 47 精确地图、站位、单位、奖励、休息、影分身、五次击倒和 47→49；
- GBA campaign RNG 与宿主 seed 不一致；
- 脚本确认输入可能穿透到地图控制；
- 脚本与地图 sprite cohort 同帧重叠分配；
- telemetry 尾部 HP 字段和 Lua/C++ 协议；
- Lua 路线禁止写内存并核对 generated map。

最终静态与集成验证见本记录关联的 guard、宿主测试和 Python/Lua 测试输出。

- 107/107 个 `butano-sequel/game` 宿主 C++ 测试通过；guard：
  `build/resource-guard/butano-s47-presentation-fifo-full-host-20260727-02.json`；
- scenario 46、scenario 47 与 runtime telemetry 三个定向宿主测试单独复跑通过；
- 27 个 campaign route、RNG wiring、资源生命周期、FIFO 所有权和输入优先级
  Python 测试通过；
- Lua `luac -p`、manifest JSON 解析与本轮 `git diff --check` 通过；
- ARM 构建 guard：
  `build/resource-guard/scenario-47-presentation-fifo-arm-build-20260727-07.json`；
- 最终 mGBA guard：
  `build/resource-guard/butano-s47-real-map-mgba-20260727-22.json`。

## 未完成边界

- 本次 mGBA 路线显式 `mute=1`、`audioSync=0`，不能据此签发音频撕裂已修复；历史非静音
  S3M 回归也不能替代本 ROM / 本关的主观音频验收。
- scenario 48 的学院剧情尚未实现；battle-only 路由只按证据跳到 scenario 49。
- scenario 49/50 的护送、目标 AI、占位、替身和失败谓词仍需完整 ROM 纵切。
- 五名敌人的逐角色专属 sprite、每个动作的精确 OAM 时序、文字和专属 cue 尚未全部签发。
- 因此 scenario 47 证明共享架构能承载真实 3v5 关卡，不代表 47 场和全部音画已功能等价。
