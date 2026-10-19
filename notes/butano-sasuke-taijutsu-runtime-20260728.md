# scenario 49 佐助动作 5 对黄蜂运行时复核（2026-07-28）

## 复核目标

针对人工反馈“佐助对黄蜂使用忍者组合拳后没有进入战斗并卡死”，只复核这一条输入链：

1. 从 generation 8 的 scenario 49 / battle 14 存档冷启动；
2. 非佐助玩家角色只结束行动；
3. 佐助移动到 character 55 黄蜂敌军相邻格；
4. 选择主动动作 5（忍者组合拳）并确认敌军目标；
5. 要求真实 ROM 演出从 transition in 走到 transition out，而不是只检查领域伤害。

## 复核结果

当前人工验收 ROM 未复现卡死。使用人工验收包原文件名、原 SAV 和默认 mGBA 配置时：

- ROM SHA-256：
  `d50d06e81194328b803ca7b4f4a944fddfddb59263bb787cd394e8fe4de210c1`
- 输入 SAV SHA-256：
  `3f473ececd31485800c1d907ca7a9b97350fc74f354ffb5a9032ce349a9dbc88`
- mGBA：
  `/Users/altair/github/gba-naruto/build/signed-tooling/mGBA.app`
- 佐助为 `selected_character_id=2`；
- 最后结算动作为 `last_resolved_action_id=5`；
- 演出持续 268 帧；
- combat stage 实际到达 7（transition out）；
- `last_control_error=0`、`last_player_error=0`；
- 演出结束后进入正常的朝向选择，画面显示 `FACING A OK B BACK`，不是死循环。

默认音频/默认同步运行耗时约 24 秒并由 success marker 正常结束；另一次静音、关闭同步的
运行也通过。逐阶段截图确认森林决斗背景、佐助、黄蜂、动作标题、命中画面和返回地图都
真实可见。

证据目录：

- `artifacts/butano-battle-ui-20260728-01/sasuke-taijutsu-exact-basename-01/`
- `artifacts/butano-battle-ui-20260728-01/sasuke-taijutsu-visual-stages-01/`
- `artifacts/butano-battle-ui-20260728-01/sasuke-taijutsu-facing-settle-01/`

## 回归保护

`tools/butano/mgba_battle_campaign_route.lua` 新增只读
`MGBA_BATTLE_CAMPAIGN_ROUTE_SASUKE_TAIJUTSU_PROBE=1` 模式。它不写内存，只通过合法
按键驱动，并断言目标确认、演出开始、transition out、动作 ID、角色 ID 和错误码。
`tests/test_butano_battle_campaign_route_runtime_script.py` 固定该探针及 telemetry 接线。

现有 `test_battle_scene_character_actions.cpp` 也已重新编译运行；该集成测试精确覆盖佐助
移动到黄蜂相邻格、选择动作 5、确认目标、生成表现事件、造成伤害并结束行动。

## 当前结论与诊断边界

不能依据现有证据宣称修复了一个生产逻辑 bug：当前交付 ROM 的同一路径在宿主和真实
mGBA 中均通过。若人工环境再次出现停住，必须在停住画面保存 mGBA 状态文件，而不是只
提供战前 SRAM；即时状态需要保留 PC、场景 phase、presentation queue、演出 stage 和
VRAM/OAM 现场，才能区分输入未确认、旧进程/旧 ROM、表现资源断言或模拟器暂停。

