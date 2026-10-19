# Butano 活动战斗资产与截图路径审计（2026-07-26）

## 结论

用户否决的旧 scenario 41 实现确实曾把整屏参考帧、固定选项和黄金路线组合成“可运行
战斗”。本次对当前生产树重新审计后确认：活动战斗入口已经没有可加载预制整屏战斗截图
的代码或资产路径。当前可见内容由领域 snapshot/event 和独立 BG/OBJ 组件生成。

这项结论只针对“活动战斗是否仍由截图拼装”。它不表示全部角色动作、技能演出、音频、
章节入口或 47 场关卡已经功能等价。

## 生产入口

`butano-sequel/src/main.cpp` 只进入：

- `run_battle_preparation_scene(campaign)`；
- `run_battle_41_scene(campaign)`；
- `run_scenario_43_scene()`，后者继续调用共享 `run_battle_scene(request)`。

所有可见战斗最终进入
`butano-sequel/game/src/battle_runtime_scene.cpp::run_visible_battle_scene`，使用同一个
`battle_runtime_controller`。不存在 `scenario_41_scene.cpp`、旧 presenter 或第二套
固定伤害 facade。

## BG 审计

活动 runtime 唯一直引的 regular BG header 是：

```text
bn_regular_bg_items_battle_duel_forest.h
```

战场地图不由 runtime 按关卡名硬编码；47 场只通过
`generated_battle_background_content.h` 的 `battle_background_definition` 目录选择
ROM 派生 map chunk。决斗时同一个 `regular_bg_ptr` 原位切到
`battle_duel_forest`，结束后恢复原 map item、origin 和 camera。

生产 runtime 不包含：

- `regular_bg_items::scenario_*`；
- `reference_frame`；
- `screenshot`；
- `golden_route`；
- prebattle/attack/result/confirmation 的整屏 BG 名称。

## OBJ 审计

当前 `scenario_41_*` 图形资产只剩：

- `scenario_41_cursor.bmp/.json`；
- `scenario_41_cursor_shadow.bmp/.json`。

二者是地图光标组件，不是状态截图。下列旧整屏族在
`butano-sequel/graphics/` 中均为零：

- `scenario_*frame*`；
- `scenario_*screen*`；
- `scenario_*prebattle*`；
- `scenario_*confirmation*`；
- `scenario_*attack*`；
- `scenario_*result*`。

单位由 62×9 原 ROM 视觉目录的独立 sprite item 创建；文字由 glyph/font 组件创建；
type-2 对象到期和动作 5 命中分别使用独立结构化 effect sequence。OBJ renderer 只读
领域快照和 presentation event，不拥有 HP、坐标、回合或胜负写入口。

## 自动门禁

`tests/test_butano_single_battle_domain.py::
test_interactive_battle_cannot_load_precomposed_screen_assets` 固定以下契约：

1. runtime 的直引 regular BG 白名单只有 `battle_duel_forest`；
2. runtime 不得重新出现 scenario BG、截图、参考帧、黄金路线和三层 confirmation 名称；
3. graphics 目录不得重新出现上述六类 scenario 整屏资产。

同文件原有门禁继续要求：

- 旧 scenario 41 facade/header/source 不存在；
- 旧 `battle_abilities` / `battle_effects` 第二套 resolver 不存在；
- scenario 41 图形只允许光标及阴影。

2026-07-26 验证：

- `python3 -m unittest tests.test_butano_single_battle_domain`：11/11 通过；
- 全量 game host：91/91 通过，证据
  `build/resource-guard/butano-action05-full-host-20260726-40.json`；
- battle 9 动作 5 ARM 自然路线：round 3 返回 unit selection，证据
  `build/butano-action05-effect-runtime-20260726-41/`。

## 明确边界

- `main.cpp` 目前仍是少数战斗 fixture 的顺序入口，不是完整章节/存档导航 UI；
- 决斗 HUD、动作 5 扬尘/攻击者完整动作、火遁真实效果以及其余技能专属时间线仍未全部
  ROM 化；
- 静音 mGBA 只签发状态机、资源安全和可见帧，不签发音频听感；
- 因此当前可以确认“活动战斗已不再加载预制整屏截图”，但不能确认“整个战斗系统或全游戏
  已功能等价”。
