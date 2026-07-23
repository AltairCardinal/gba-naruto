# Butano Scenario 41 战斗关卡复刻设计

> **已由 2026-07-22 规格取代。** 本文明确只追求功能等价，并排除逐像素、逐帧、
> 原文与原音频一致，因此不再能作为当前 1:1 Goal 的验收依据。新权威规格见
> `docs/superpowers/specs/2026-07-22-butano-scenario-41-one-to-one-design.md`。

## 目标

在现有 `butano-sequel` 工程中复刻木叶战记 scenario 41 的一个完整、可玩的
战斗关卡。玩家从战斗开场进入 9×22 战棋地图，控制鸣人接近伊鲁卡，以组合技完成
胜利条件，看到胜利和结果页，并能重新开始。

本设计追求运行规则和用户流程的功能等价，不追求逐像素、逐帧或原始日文文本完全
一致。原 ROM 的权威边界来自 `notes/scenario-41-battle-entry-runtime-20260713.md`、
`notes/scenario-41-movedone-runtime-20260717.md`、
`notes/scenario-41-completion-runtime-20260718.md` 和对应机器证据。

## 选型

### 采用：关卡纵切片加可测试领域核心

- 独立 C++ 领域核心负责网格、单位、移动、行动阶段、AI、攻击、回合、胜负和重开。
- Butano 显示层只把按键转换为领域命令，再把领域快照渲染为地图、单位、光标、
  菜单、提示和结果页。
- 将现有 benchmark 中已经验证的定长网格、寻路和效果链能力提升为生产能力，避免
  复制第二套规则；benchmark 保留兼容入口和原测试。
- 关卡数据固定在一个 scenario 41 定义中，不提前建设多关卡编辑器或脚本 VM。

### 未采用：先建设通用战棋引擎

它会在首个关卡前引入多角色编队、任意技能表、通用剧情 VM 和跨关卡存档，超出本
目标。当前纵切片的接口仍为后续扩展保留数据驱动边界。

### 未采用：全脚本战斗演示

脚本演示无法证明移动合法性、取消回退、目标选择、敌方 AI 和自然胜负，不满足
“可玩的功能等价关卡”。

## 权威关卡事实

- battle ID：41。
- 地图：36×44 原始 tile，对应 9×22 战棋格。
- 初始单位：鸣人位于 `(4,10)`，伊鲁卡位于 `(4,4)`。
- 原作自然完成链在第 4 回合由鸣人从 `(5,6)` 移动到 `(6,4)`，对 `(6,3)` 的
  伊鲁卡提交相邻组合技并得到胜利结果。
- 原作包含单位选择、移动、行动菜单、朝向/行动结束、敌方阶段、组合技、胜利、
  结果页和战后交接。

复刻版保留这些事实。为避免依赖尚未完全证明的原始伤害公式，伊鲁卡的关卡胜负由
“鸣人在相邻格成功提交组合技”这一已经运行验证的脚本条件决定；普通非法提交不会
造成伤害或推进阶段。

## 用户流程

### 入口与教学

ROM 启动后直接显示森林战场、双方单位、当前回合和简短目标：
`DEFEAT IRUKA / USE COMBO ADJACENT`。按 A 关闭提示并进入玩家选择阶段。

### 玩家阶段

- 方向键移动光标；相机在 9×22 地图上跟随光标。
- 光标位于鸣人时按 A，显示可移动范围。
- 在可达且未占用的格子按 A，暂存移动并打开行动菜单。
- 菜单包含 `COMBO` 和 `WAIT`：
  - `COMBO` 进入相邻目标选择；只有伊鲁卡所在相邻格可以提交。
  - `WAIT` 提交当前位置并进入敌方阶段。
- B 从目标选择回到菜单，从菜单回到移动预览，从移动预览回到单位选择；取消不得
  改变已提交位置、HP、回合或胜负状态。
- START 等价于原地 `WAIT`，避免玩家因找不到菜单入口而被困住。

### 敌方阶段

伊鲁卡沿确定性最短路径向鸣人接近，最多移动两格，不进入鸣人占用格。若已经相邻，
本回合保持位置并显示 `IRUKA ATTACKS`；该纵切片记录攻击反馈但不引入尚未证明的
原伤害公式。敌方阶段结束后回到新的玩家回合。

### 胜利与重开

组合技合法提交后显示短暂 `COMBO HIT`，再进入 `VICTORY` 页面。结果页显示
`NARUTO`, `EXP +110`, `TRAINING +1`，与后续 scenario 42 运行记录中的可见奖励边界
一致。按 A 从胜利页进入结果页，再按 A 重新初始化同一关卡。

## 领域模型

### 值类型

- `grid_point { int x; int y; }`
- `battle_unit { unit_id, team, position, hp, max_hp, move_range, active }`
- `battle_phase { intro, unit_select, move_select, action_menu, target_select,
  enemy_turn, combo_feedback, victory, result }`
- `battle_command { dismiss_intro, move_cursor, confirm, cancel, wait, tick }`
- `battle_event { none, invalid, cursor_moved, unit_selected, move_previewed,
  move_committed, combo_selected, combo_hit, waited, enemy_moved, enemy_attacked,
  victory_shown, result_shown, restarted }`

### `scenario_41_battle`

该对象拥有全部可序列化战斗状态，并暴露：

- `snapshot() const`：只读渲染数据；
- `dispatch(command)`：唯一状态修改入口，返回 `battle_event`；
- `reachable(point) const`：移动范围查询；
- `restart()`：恢复权威初始状态。

领域层不包含 Butano 类型、动态分配、异常、文件 IO 或测试专用分支。所有数组使用
编译期容量，适配 GBA 内存边界。

## 复用与边界

1. 直接复用现有定长寻路、战斗效果链和行动阶段测试所证明的算法语义。
2. 将通用能力放入 `butano-sequel/game/include/konoha/`；benchmark 头只保留兼容
   include/alias，避免生产代码依赖 `konoha_bench` 命名空间。
3. `scenario_41_battle` 在这些公共能力上增加关卡规则，不另写第二套寻路或伤害链。
4. 本关卡独立维护的数据只有地图阻挡、初始单位、移动力、目标和可见文案；这些是
   scenario 41 特有内容，不能抽成无语义的全局常量。

## 显示架构

- 使用 Butano regular background 表示森林战场；采用少量重复地面、草丛、树木和
  岩石 tile，保持原作绿色森林和黑色地图边界的辨识度。
- 每个战棋格按 16×16 像素呈现，可见窗口为 15×8 格；纵向相机覆盖 22 行。
- 鸣人、伊鲁卡、光标和移动范围使用 sprite；单位至少以不同配色和姓名清晰区分。
- 底部状态栏显示选中单位、HP、回合和当前操作；菜单与提示使用已有 Butano
  `common::variable_8x16_sprite_font`。
- 文本 sprite 数必须受固定容量约束；每次页面切换先清理旧文本，避免 OAM 泄漏。

视觉素材属于本关卡实现的一部分，但不把原 ROM 资源自动转换器扩张为本目标的
前置条件。若原始 tile 能由既有提取器无损导入则复用；否则使用项目内明确标记为
复刻版的手工 tile，不能冒充逐像素原版。

## 错误、空状态与边界

- 地图外移动、阻挡格、被占用格和超移动力目标均返回 `invalid`，显示短提示并保持
  原状态。
- 非相邻组合技、对空格使用组合技、在错误阶段输入均不修改关卡状态。
- 领域状态始终包含两名已定义单位，不存在单位列表空状态。
- 关卡不实现旧存档、装备、角色详情、任意编队、多技能、失败结算或战后世界地图；
  这些不是“复刻一个战斗关卡”完成所必需的用户流程。

## 测试与验收

### 宿主 C++ 单元测试

- 初始事实与 intro 关闭；
- 光标边界、障碍和确定性可达范围；
- 选择、移动暂存、三级取消回退与提交；
- WAIT 后敌人两格确定性寻路；
- 非法组合技不变性；
- 相邻组合技自然胜利；
- 胜利→结果→重开完整链；
- 多次重开得到逐字段一致快照。

### Butano 集成测试

- Makefile 编入 production/game 和 scene 源码、图形资源；
- ROM 标头保持 `KONOHA BASE` / `KNBT`；
- ELF 包含 `scenario_41_battle`、`DEFEAT IRUKA`、`COMBO`、`VICTORY`、
  `EXP +110`；
- Docker 固定工具链从干净目录构建成功且无警告。

### 运行时验收

在受资源守卫保护的 mGBA 中从冷启动完成：关闭目标提示、选择鸣人、至少一次移动与
取消、多个 WAIT/敌方阶段、移动到伊鲁卡相邻格、提交 COMBO、进入 VICTORY、进入
结果页并重开。运行证据必须包含唯一 run ID、ROM 哈希、输入序列和关键画面；若当前
mGBA 构建不能可靠自动注入输入，则保留构建及领域集成证据，并把图形运行验收明确
标为未完成，不能据此宣称 Goal 完成。
