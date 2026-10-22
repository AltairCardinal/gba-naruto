# Butano 连续战斗场景资源生命周期修复（2026-07-26）

## 用户可见故障

冷启动路线依次进入 battle 43、battle 9、battle 11 时，battle 11 的部署画面在确认第二个
单位后停住。遥测固定在：

- `battle_id=11`
- `phase=0xFFFFFFFE`（部署单位确认）
- `scene_frame=6`
- `selected_unit=2`
- `render_stage=0`

Lua 注入的 A 键已经反映在 GBA `KEYINPUT`，所以这不是“再按一次 A”或 mGBA 默认按键映射
问题。CPU 停在第一次后续 `bn::core::update()`，与用户报告的进入战斗后无响应属于同一类
运行时故障。

## 根因

`run_visible_battle_scene()` 为降低 GBA IWRAM 栈压力，把以下容器迁到了 EWRAM 静态存储：

- 12 个单位的多组件精灵缓存；
- 战场对象精灵缓存；
- HUD 文本精灵缓存；
- ROM 对话字形精灵缓存。

静态存储避免了大栈帧，但函数返回时不会析构这些容器。原实现直到“下一场部署结束、
controller 已加载”之后才清空它们，因此下一场部署会同时持有上一场战斗和当前部署的
精灵/tiles。battle 43→9 尚能通过，battle 11 在第二个部署单位后的第一次图形提交处稳定
停帧。

## 修复

进入任何新部署前先清空四组 EWRAM 静态缓存，再执行一次 `bn::core::update()`，让 Butano
在当前部署创建地图、单位和文本前回收已经释放的 VRAM blocks。部署完成后原有的第二次
`bn::core::update()` 继续负责回收部署自身资源，再创建共享战斗 controller 的画面资源。

这个顺序保留“静态缓存降低栈占用”的目的，同时补齐跨场景所有权边界：

`上一场 battle resources → release/update → deployment resources → release/update → 当前 battle resources`

## TDD 与运行证据

红测 `tests/test_butano_battle_scene_resource_lifetime.py` 首先证明四组释放均发生在
`run_deployment_confirmation()` 之后；修复后它要求四组释放以及回收用
`bn::core::update()` 全部位于部署之前。

清洁 devkitARM 构建：

- guard：`build/resource-guard/butano-b11-scene-resource-arm-build-20260726-01.json`
- 结果：exit 0，owned tree peak 21.586 MiB

静音 mGBA 冷启动路线：

- guard：`build/resource-guard/butano-b11-scene-resource-mgba-20260726-02.json`
- artifacts：`artifacts/butano-b11-scene-resource-runtime-20260726-02/`
- battle 11 部署帧从 `1→6→15→24→33→42→55` 持续推进；
- 五个单位确认后进入 round 1、共享 `unit_selection` 和 `move_selection`；
- 地图 streaming 实际观察 `chunk 0→1→0`；
- 最终 `scene_frame=136`、`phase=move_selection`、控制器/玩家错误均为 0。

本次 ROM/ELF SHA-256：

- ROM：`35d9710517dcc2b1caa7ef1edf08ebbeef1533916efc6ad6a81789272019fa5a`
- ELF：`5486f6b8538d67313ea57e371db69de484cd08c2932e99e2da57a297854ed3bf`

第一次 `20260726-01` mGBA guard 没有预建输出目录，Lua 无法创建日志并被 idle guard
终止；它不属于 ROM 运行证据，已由 `20260726-02` 取代。

## 边界

这次修复证明连续场景能进入同一个真实 controller 并移动，不证明 battle 11 的全部敌我
行动、专属被动动画或非静音音频已经还原。完整战斗 Goal 仍保持 active。

## 2026-07-28：动态战斗 UI 与 8bpp 立绘的统一资源所有权

### 复发症状与排除项

scenario 49 / battle 14 加入动态 HUD、指令菜单、技能菜单和结果面板后，路线先后出现两类
故障：

- OBJ tile 分配失败，停在指令菜单切换到技能菜单；
- `create_bpp_8` 无法申请 128 色立绘调色板，或演出开始后停在
  `presentation_busy=1`。

这些故障并非立绘压缩数据或 mGBA 调色板实现错误。诊断探针在失败边界读到的 OBJ 已用
颜色依次从 32 降到 16，但 128 色申请仍失败，说明问题不是颜色总量不足，而是 0 号
palette slot 被 4bpp 所有者占用。Butano 的 8bpp OBJ palette 必须从 slot 0 连续分配；
仅统计 OAM 数量或“可用颜色总数”无法发现该冲突。

### 根因

原场景没有统一的 OBJ 所有权。部署单位、地图单位、常驻光标、动态文字、地图 UI、脚本
字形、脚本消息窗、战斗演出层和 8bpp 立绘分别在自己的更新函数里申请/释放资源。

光标是在部署画面仍持有多套 4bpp palette 时创建的，因此会被挤到低编号甚至 slot 0。
随后即使单位和 UI 已释放，常驻光标仍永久阻塞 8bpp 立绘。继续把光标纳入地图释放后，
还剩一个 slot 0 所有者：上一段战斗演出层的 palette。它同样不在旧的脚本/地图清理
边界中。这解释了故障为什么随此前画面和分配顺序变化而频繁复发。

### 架构修复

新增 `battle_visual_resource_coordinator`，把可见资源定义为互斥 cohort：

- `deployment`：部署单位和部署文字；
- `map`：地图单位、光标、动态 HUD/文字和战斗演出层；
- `script_dialogue`：脚本字形、消息窗和脚本立绘；
- `combat_portrait`：128 色战斗立绘。

场景循环只允许协调器执行 cohort 切换。每次切换严格执行：

`释放旧 cohort 的全部所有者 → 一次 bn::core::update() → 分配新 cohort`

同一逻辑迭代最多提交一次核心更新，避免资源交接提交与帧尾提交重叠。立绘与脚本立绘
renderer 不再释放地图单位或自行调用 `bn::core::update()`；光标改为地图 cohort 持有的
可选资源；脚本消息窗和战斗演出层提供显式 reset，由协调器统一回收。UI 面板与数值条
通过同一个 `sprite_palette_ptr` 创建，固定只占一套 16 色 palette。

### 防回归契约

- `test_battle_visual_resource_coordinator.cpp` 固定各 cohort 的所有者与切换提交语义；
- `test_butano_battle_ui_runtime_wiring.py` 禁止 portrait helper 管理地图生命周期，并固定
  光标、脚本消息窗、演出层都由协调器释放；
- scenario 49 完整路线必须经过真实技能立绘演出、结果结算并推进到 scenario 50，不能只
  验证战斗入口。

最终运行证据与 ROM 哈希记录在 `docs/sequel-roadmap.md` 的 2026-07-28 条目。
