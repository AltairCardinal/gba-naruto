# Butano scenario 46 捕获任务领域纵切证据（2026-07-27）

## 结论

scenario 46 / battle 9 已不再把“猫消失”“抓住猫了”或胜利画面当作预制截图结果。
捕获现由共享动作解析、任务规则、单位生命周期、胜负条件和结算管线共同产生：

```text
玩家命令
  → 技能/忍具目录
  → 任务级动作投影
  → 目标预览与共享 action resolver
  → damage step 击倒猫
  → capture policy 清空当前角色身份
  → generated condition interpreter
  → 最后一只猫直接进入 victory
  → result / progression / campaign 46→47
```

Lua 只发送 GBA 按键并读取 telemetry；静态测试禁止 `emu:write`。截图只是运行结果的
可见佐证，不参与规则、伤害、捕获、胜负或奖励计算。

## 原版规则边界

原版逐步运行证据位于 `notes/scenario-46-entry-runtime-20260719.md`：

- battle 9 variant 0 是 16×32 地图，玩家为鸣人、佐助、小樱，敌方为五只角色 41 的猫；
- 五只猫当前 HP 均为 1，捕获后的槽位 `character_id` 从 41 变为 0；
- “直接攻击”是独立主命令；本任务中确认后即时拒绝，不能用普通近战捕获；
- 佐助动作 16、鸣人动作 7、小樱动作 5 都能经正常伤害结算捕获猫；
- 动作 7 在普通关卡是召唤影分身，在本任务则显示伤害预览并以敌方单位为目标；
- 最后一只猫捕获后直接进入胜利，不再要求攻击者完成朝向和防御尾部；
- 三名参与者各得 125 mission EXP，round 47 不得回合奖励。

原版低分辨率结果画面曾被人工转写为鸣人/佐助 `59` battle EXP，但
`notes/battle-result-progression-runtime-20260725.md` 的结果结构和前后角色经验闭合为
`60/60/30`。当前领域使用内部数据证据的 `60/60/30`，并保留这项视觉转写差异，不把
它静默改写成“已无争议”。

## 共享架构

### 捕获是任务策略，不是 renderer 特效

`battle_mission_rules` 持有 `battle_capture_policy`。battle 9 variant 0 的策略只接受：

- 敌方阵营；
- 原角色 ID 41；
- 主动技能或忍具造成的有效击倒；
- 禁止 `direct_attack` 来源。

`battle_capture_system` 读取 resolver 产出的真实 `damage_steps`，只处理本次动作实际击倒
的目标。成功捕获后：

- `captured=true`；
- 当前 `character_id=0`，与原版槽位清空语义一致；
- `original_character_id=41` 保留来源身份；
- 单位继续保持 inactive；
- 捕获数量进入 presentation event，但 presentation 不反向改变 session。

捕获发生在 `battle_turn_flow::after_effects` 之前。这样 generated condition interpreter
读取的已经是提交后的真实单位状态；第五只猫清空时自然产生 outcome，controller 直接转入
胜利，不需要场景按 battle ID 强制跳转。

### 组合技保留每个输入来源

捕获许可不再把组合技统一标记为 `active_action`。`battle_capture_source` 按顺序保留至多
两个组件的来源，策略采用“全部组件均获许可”语义：`主动术 + 忍具` 只有在任务同时允许
主动术和忍具时才可捕获；只允许任一来源都会拒绝捕获，但动作本身仍按正常 resolver
结算。

生产流测试用佐助的动作 16 与十字手里剑组成动作 18，锁定了
browser → 组合确认 → 双组件成本 → resolver → capture 的完整路径。旧实现下，“仅允许
主动术”的策略错误捕获并使测试失败；修复后该策略保持目标未捕获，而同时允许两类来源时
成功捕获并消费忍具。捕获系统测试还用同一目标的重复 damage step 和第二个目标的 damage
step 验证：同一单位只捕获一次，多目标则分别捕获。

### 直接攻击是独立命令

`battle_command_type::direct_attack`、`battle_action_source_kind::direct_attack` 和
`direct_attack_definition` 共同建立独立身份。它不是动作 5 的别名，也不占角色技能槽：

- 命令顺序为移动、术/忍具、直接攻击、查克拉、休息、结束行动；
- 移动后隐藏，符合原版“移动后只剩术/忍具与结束行动”的证据；
- 目标、命中、伤害和反应继续复用统一 resolver；
- scenario 46 的 mission access policy 在确认边界返回 `mission_restricted`；
- presentation 可复用近战资源，但事件仍保留 `direct_attack=true` 和动作 ID `0xFE`。

新增命令曾使 mGBA Lua 的 `COMMAND_END_ACTION=4` 失真。新增跨语言协议测试从 C++ 枚举
推导实际值，并发现六个脚本应更新为 5；红测均报告 `4 != 5`，修复后相关 16 项脚本测试
通过。

### 同一动作可由任务投影改变语义

动作 7 的普通定义仍是召唤，不影响 scenario 43 的影分身链。scenario 46 的 capture
policy 只在动作目录副本中把动作 7 投影为：

- effect code 1（damage）；
- potency 10、1 hit、98%；
- opponent-unit target；
- range 1；
- 保留动作 ID、查克拉成本和表现绑定。

因此角色内容不需要复制第二份“捕猫影分身”，controller 也不包含 scenario 46 分支。
同一目录、成本、目标预览和 resolver 根据 mission data 得到本关语义。

## 宿主完整纵切

`butano-sequel/game/tests/test_battle_campaign_scenario_46.cpp` 直接装载真实 generated
battle 9：16×32 地图、三名玩家的原始坐标、五个角色 41 / HP 1 的敌方槽及生产 AI
全部保持不变。测试侧 BFS 只从公开 snapshot、move preview 和地图通行成本选择下一次
合法输入；移动提交、敌方逃逸、动作解析、捕获、胜负和结算全部仍由生产 controller 执行。
此前用于纵切的限制移动地图已删除，不能再作为本关完成证据。

测试只调用 controller 公开输入，完成：

- 佐助动作 16 捕获两只；
- 鸣人经任务投影后的动作 7 捕获两只，并在查克拉不足时走正式补充命令；
- 小樱动作 5 捕获最后一只；
- 五次 capture presentation；
- 槽位角色 ID 全部清零；
- 最后一只捕获后立即 outcome；
- 三人 mission EXP 125，battle EXP 60/60/30，bonus 0；
- 最终鸣人 LV4/EXP180/TP3、佐助 LV3/EXP185/TP2、
  小樱 LV4/EXP35/TP3；
- progression commit 与 campaign 46→47。

这条测试在固定 seed 下于第 162 回合完成，签发真实地图上的领域闭环。回合数不是对原版
录像 47 回合的人类路线复刻；它只证明在相同地图、单位和规则下，公开输入可以通过完整
生产状态机达成目标。

## 生产 ROM 运行证据

ARM 构建：

- guard：
  `build/resource-guard/butano-s46-capture-review-arm-build-20260727-01.json`；
- exit 0，峰值 21.5547 MiB；
- ROM SHA-256：
  `bf1b27291d5ccf6d5ce5fa1728f4b90532b460d2af5f8f5bed71e0fb1f48542e`；
- ELF SHA-256：
  `e39bad8676e3a2c56daed16ad8568fb158c9f0f511e23febe952e17f662e0574`。

独立 mGBA 进程复制 scenario 45 真实胜利生成的 generation 6 SAV 冷启动：

- audit：
  `artifacts/butano-battle-scenario-46-rule-probe-20260727-03/audit.json`；
- scenario 46 / battle 9 / round 1 / 8 active units；
- frame 302；
- 直接攻击确认产生任务拒绝，探针记录 `direct_attack_rejected=1`；
- 随后动作 7 的生产目录记录
  `kind=active, effect_code=1, target_kind=2`；
- `shadow_clone_transformed=1`；
- load generation 6，default 0；
- 最终 controller/player error 均为 0；
- guard 由 success marker 正常结束，无 mGBA 残留。

为证明 telemetry 观察的是动作目录中的最终领域值，结构尾部新增
`selected_action_effect_code` 和 `selected_action_target_kind`，保持此前 0–396 的 ABI
偏移不变。对应 gate 测试锁定新偏移 400/404。

### 真实地图完整 ROM 签发

为了让 mGBA 路线能在不写内存的前提下规划合法输入，telemetry 在既有字段之后追加：

- 当前角色查克拉；
- 公开移动预览坐标；
- 12 个稳定单位槽的角色 ID、活动状态与坐标。

旧偏移保持不变，总尺寸为 612 字节；结构 gate 和跨语言协议测试锁定这些偏移。Lua 中的
16×32 通行表与 generated battle 9 一致，BFS 只决定光标和按键，不写 HP、坐标、角色、
胜负或结果，静态测试继续禁止 `emu:write`。

第一次真实 ARM 捕获在第 26 回合触发 Butano mode 3 断言：

```text
ERROR in battle_runtime_scene.cpp
update_unit_sprites::3544
Missing battle unit visual: 0 slot 0
```

GDB 读取 `DISPCNT=0x0403` 并导出 VRAM，证明这不是 mGBA 黑屏或 Lua 停止。根因是捕获已按
领域规则把目标当前 `character_id` 清为 0，而该动作的受击表现仍引用相同 UnitId。修复后
player 与 AI 产生表现事件时都冻结每个 affected unit 的结算前角色身份；renderer 只在
进行中的表现事务内使用该身份，领域 snapshot 仍保持捕获槽为 0，多目标数组也有边界测试。

最终签发：

- guard：`build/resource-guard/butano-s46-exact-map-mgba-20260727-10.json`；
- artifact：`artifacts/butano-battle-scenario-46-exact-map-20260727-10/`；
- manifest：`notes/evidence/butano-scenario-46-exact-map-runtime-20260727.json`；
- frame 32616 / round 92；
- 捕获分配：佐助 2、鸣人 2、小樱 1，五份 `capture-*.json`；
- 结果：mission 125、battle 60/60/30、round bonus 0；
- 鸣人：LV4 / EXP180 / TP3；
- SRAM generation 7、verified 1，并进入 scenario 47；
- controller/player error 均为 0；
- guard 因 success marker 正常退出，峰值 122.04296875 MiB。

最终 ROM SHA-256 为
`c0eba827fac440bef0a9d44e5740270da96c2b93c05d6b266fc567b4eb0a80da`，
ELF 为
`e23e85b1a50937325adc1611940fa7205d725b9ddb9e9015ce9ed6fffef15b6e`。
ARM 构建 guard 为
`build/resource-guard/scenario-46-capture-visual-arm-docker-20260727.json`。

### 已取代的贪心自动玩家实验

规则探针之后又进行了三次不写内存的完整地图自动玩家实验：

- `artifacts/butano-battle-scenario-46-complete-20260727-01/progress.json`：
  固定追单位表首只猫，frame 39992 / round 57 未完成；
- `artifacts/butano-battle-scenario-46-complete-20260727-02/progress.json`：
  三人都追各自最近目标，frame 39997 / round 45 未完成；
- `artifacts/butano-battle-scenario-46-complete-20260727-03/progress.json`：
  鸣人追最近目标、佐助/小樱从首槽收口，frame 59999 / round 77 未完成。

三次都停在合法的移动选择阶段，没有领域崩溃或黑屏。失败原因是贪心自动玩家无法对逃逸
AI 形成桥位夹击，不能据此判定捕获系统失败。它们已被上述 topology-aware BFS 和第 92
回合完整 ROM 路线取代；三个失败产物继续保留为“Manhattan/最近目标不等于合法战术规划”
的反证，不得再引用为本关未签发。所有自有 mGBA 进程均已终止且无残留。

## TDD 与验证

红灯包括：

- 捕获策略头文件/生产调用不存在；
- mission rules 没有 battle 9 捕获策略；
- scenario 46 完整 controller 纵切不能捕获或推进；
- 直接攻击命令不存在；
- `battle_action_menu_view.kind` 一位位域截断新 source kind；
- telemetry 没有最终 effect/target；
- 六个 Lua 路由仍使用旧 end-action 数值。
- 组合技被统一标记为主动术，使“仅允许主动术”的策略错误接受
  `动作 16 + 忍具 1`；失败断言精确落在 `capture_count == 0`。

绿灯：

- 106/106 个 game host C++ 测试通过；
- guard：
  `build/resource-guard/butano-s46-exact-map-full-host-20260727-01.json`；
- 峰值 150.59765625 MiB；
- 12 个 route/telemetry Python 协议测试、Lua 语法和 runtime telemetry gate 通过；
- 忍具单动作生产链、主动术＋忍具组合许可、重复 damage step 去重和多目标捕获均通过；
- ARM 构建、受守卫 mGBA 规则探针与真实地图完整路线通过；
- `git diff --check` 对本轮代码、测试与脚本无错误。

先前独立只读复审对组合来源、忍具生产链、重复 step 和多目标覆盖均给出
Critical 0 / Important 0 / Ready；其“真实 16×32 地图未签发”边界已由本节新证据闭合。

仓库级 Python 全量测试另跑了 1204 项，结果为 2 failure、16 error、18 skipped。失败集中于
既有 Web 编辑器镜像字段语义和已删除的 scenario 41 图片资源，记录在
`build/resource-guard/butano-s46-capture-python-tests-20260727-01.log`；本轮未修改这些
无关模块，也不把仓库全量 Python 标成通过。

## 未完成边界

- “抓住猫了”专属对话、每种技能的专属镜头/音效仍未逐项还原；当前 capture presentation
  只传递真实领域事件。
- scenario 47 及后续关卡仍需继续以同一共享架构做纵切，不能因 battle 9 通过就宣称
  全部 47 场完成。
- 完整 Goal 保持 active。
