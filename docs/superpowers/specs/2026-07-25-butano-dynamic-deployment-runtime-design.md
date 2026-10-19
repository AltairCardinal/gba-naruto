# Butano 动态部署运行时设计

## 目标

让 `battle_content_entry_kind::deployment_required` 的非空变体进入与固定编队完全相同的
可见战斗运行时。章节层必须显式提供 `0xFF..0xFA` 六个 placeholder 对应的角色、等级和
scripted control；renderer 不猜队伍，也不为所有关卡默认填入鸣人小队。

## 现状与问题

领域加载器、部署预览和通用 controller 已经共享 `battle_scenario_load_policy`，宿主测试也已
证明 85 个非空变体都能在提供策略后装载。但 `battle_runtime_scene.cpp` 在 UI 入口额外要求
`fixed_roster`，并在函数内部创建空 policy，因此 41 个需要部署的变体必然在显示部署画面前
被拒绝。这是 wiring 缺口，不需要第二套 loader、controller 或战斗 FSM。

## 接口

公开 `battle_runtime_scene_request`：

- battle ID、variant、RNG seed；
- 章节/开发入口标题与是否允许进入下一场；
- 完整 `battle_scenario_load_policy`。

`run_battle_scene(request)` 负责查询逻辑内容和视觉背景、验证非空内容、运行部署确认，再把
同一个 policy 传给最终 controller load。固定编队 wrapper 传空 placeholder，但仍可传等级、
scripted control 和空槽保留策略；动态编队 wrapper 必须显式绑定所有实际出现的 placeholder。

## 集成样本与边界

battle 32 variant 0 用作“章节注入策略”的 ARM/mGBA 集成夹具：入口明确命名为 fixture，
绑定 `{1,2,3,35,35,35}`，只证明六个 placeholder 从请求贯穿部署预览和最终 session。
该映射不宣称是原作某一章节的真实队伍，也不能被正式章节入口复用；正式关卡必须由逆向出的
章节状态或真实选人 UI 构造 request。

固定和动态入口都复用：

- `generated_battle_content_entry()`；
- `generated_battle_background_entry()`；
- `battle_deployment_flow`；
- `battle_runtime_controller`；
- 同一玩家命令、resolver、AI、condition 和 presentation 链。

## 失败处理

- empty variant：进入部署前返回；
- 任一使用中的 placeholder 未绑定、角色无效或 inactive：部署 `prepare()` 失败并返回；
- 背景/逻辑尺寸不一致：进入部署前返回；
- 不允许把 unresolved placeholder 静默替换为角色 1。

## 验收

- source RED/GREEN 证明运行时不再固定 roster-only，并只从 request 取得 policy；
- 宿主全量控制器测试继续覆盖 85 个非空变体；
- ARM 构建通过；
- 静音 mGBA 动态夹具逐条显示 6 个解析后的角色，进入玩家回合并完成到 round 2；
- battle 9/11/43 和 scenario 41 不回归。

## 实施结果

公开 request、非空内容门禁和同 policy preview/load 已落地。首次 ARM/mGBA 集成还暴露并
修复了一项独立回合缺陷：empty-tile 动作原本只排除单位占用，没有排除 ROM 碰撞墙，导致
AI 传送进全封闭格后下一单位永久失败。现在 AI 候选与玩家确认都拒绝 cost 0、全封闭和已占用
目标。动态夹具的六条部署身份在遥测中逐条匹配，并完成三名玩家、三名 AI 到 round 2；
固定 battle 9/11/43 与 scenario 41 仍通过。
