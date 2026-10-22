# Butano 战斗 UI 状态投影修复（2026-07-29）

> 目标关卡纠错：本文最初以 scenario 41 的共享运行时路线签发通用能力，但当前 Goal
> 的关卡是 scenario 49 / battle 14“护送木叶丸逃离野蜂”。本关独立原作对照、敌方发起
> 决斗实机图和最终运行证据见
> `notes/butano-battle-scenario-49-ui-projection-20260729.md`；scenario 41 证据不再
> 代替本关验收。

## 用户可见问题

本轮处理以下同一类表现层缺口：

1. 剧情对白字形过小且实际被错误解码，战斗菜单字体又过大；
2. 移动、技能范围和合法目标没有地图 UI；
3. 角色头顶的朝向选择没有反映当前方向；
4. 地图下方单位没有按原作的行动单位镜头锚点聚焦，容易被底部 HUD 遮挡；
5. 敌方发起决斗时沿用了地图坐标方向，左右站位与原作决斗构图不一致；
6. 资源命令和行动结束没有一致进入回合末朝向选择。

## 原作证据与纠错

- `artifacts/scenario-41-combat-reference-v1/combat-dialogue/` 的原作 GPU 快照显示，对白
  字形是 8 像素宽、16 像素高，并以 8 像素列距、16 像素行距排版。
- ROM 字库表的每个条目占 32 字节。逐像素与原作 BG3 已展开字形比较后，确认其格式是
  **8×16、2bpp packed**：每行 2 字节，每字节按低位到高位保存 4 个 2bpp 像素。
  旧生成器把相同 32 字节误解为 8×8、4bpp，所以只画出错位的半高字形；放大不能修复。
- `notes/butano-battle-flow-video-review-20260722.md` 记录的原作流程在单位行动结束后明确
  进入面向选择，再进入防御准备；`notes/scenario-41-movedone-runtime-20260717.md`
  又以稳定 checkpoint 绑定了 `0x9000` 面向提示。
- 原作战斗录屏按当前行动单位切换镜头，地图边缘才限制镜头继续居中；HUD 不改变行动单位
  的镜头锚点。决斗画面按阵营固定“玩家在左、敌人在右”，发起者不会交换双方屏幕位置，
  也不继承地图上的相对 X 坐标。

## 架构修复

### 字体

- 剧情字库生成器改为解码原始 8×16 2bpp 字形，并保留四级覆盖度。
- 剧情 renderer 直接绘制 8×16 sprite，不再用 affine 放大错误的 8×8 tile。
- 地图提示、行动目录、状态数字和确认提示统一使用独立 8×8 UI 字体，避免文字溢出面板。

### 地图范围与目标

- `battle_scene_snapshot` 公开固定容量的移动/攻击范围位图和合法目标位图。
- 移动范围来自领域层 `reachable_costs()`；技能范围来自真实动作射程，合法目标继续调用
  `target_legal()`，renderer 不复制规则。
- 表现层使用 32×32 屏幕投影 BG：移动范围、攻击范围和合法目标使用不同 tile。
- scenario 41 地图是 8bpp 并占用完整 BG 调色板。范围层不再申请独立 4bpp 调色板，
  而是动态生成 8bpp tile 并复用当前地图 palette；这修复了
  `BPP4 palette create failed: There are no more available colors` 的实机中止。
- 大地图可达性计算复用 EWRAM workspace，避免把整张距离图和 pathfinder 临时量压入
  ARM 栈。

### 镜头、层级与朝向

- 镜头 Y 以所选单位格中心为锚点，按实际地图高度与 160 像素 viewport 夹取；不再减去
  固定 72 像素把下方单位推入 HUD。
- 单位层级继续按地图 Y 动态排序，位置越靠下越靠前；移动预览使用相同投影位置。
- 面向阶段的单位 sprite 和头顶光标都读取 `selected_facing`，方向键立即更新预览，
  A 才提交。
- 决斗构图固定玩家朝右、敌人朝左；敌方发起攻击时敌人仍位于右侧朝左。
- 技能、忍具、补充查克拉、休息与显式“行动结束”在目标未抢先结束战斗时都进入同一
  `facing_selection → defense_decision` 尾部。

## TDD 与验证

红测分别固定了：

- 8×16 2bpp 字库像素数、覆盖度和生成资产尺寸；
- UI 字体与剧情字体分离；
- 范围/合法目标位图来自领域状态；
- 范围 BG 复用地图 8bpp palette，不再引用独立范围 palette；
- 行动单位镜头居中和地图边缘夹取；
- 决斗玩家/敌人固定左右朝向；
- 面向预览驱动地图 sprite 与头顶指示；
- 资源命令与行动结束进入面向阶段。

通过的宿主测试：

- `test_battle_presentation_projection`
- `test_battle_ui_model`
- `test_battle_scene_controller`
- `test_battle_player_action_flow`
- `test_battle_encounter_runtime`
- `test_battle_runtime_grid`
- `test_battle_terrain_traversal`
- `tests.test_generate_butano_battle_presentation_glyphs`
- `tests.test_butano_battle_ui_runtime_wiring`
- `tests.test_butano_scenario_41_shared_runtime_script`

devkitARM 构建在
`artifacts/butano-battle-ui-projection-20260729-27/` 完成，guard exit 0。
最终静音 mGBA 路线位于
`artifacts/butano-battle-ui-projection-20260729-29/`：

- `dialogue.png`：真实 8×16 剧情字形；
- `move-ui.png`：移动可达范围；
- `target.png`：动作范围与目标选择；
- `facing.png`：行动结束后的朝向阶段；
- `combat-impact.png`：玩家在左朝右、敌人在右朝左；
- `audit.json`：battle 41、round 4、action 5、控制器错误 0、玩家错误 0；
- guard 由 success marker 正常结束，峰值 owned-tree RSS 118.6484375 MiB。

行动详情页后续曾因 12 个独立 64×64 OBJ 帧占用 768 个 4bpp tile，在当前单位、字体与
光标同时存在时触发 `Sprite tiles create failed`。红测先把唯一资源帧上限固定为 6；
实现再改为每行一个公共帧和一个分隔线帧，12 个屏幕 sprite 只引用 6 个资源帧。没有改用
第二套 BG palette，也没有把动作状态烘焙进图片。

行动详情页随后不再使用上述 12 个 OBJ。当前实现把它并入已有 32×32 动态 BG
投影：菜单矩形、分隔线和编织色边框由 8 个逻辑 8bpp tile 按状态拼装，动作文字继续
由实时动作模型绘制。进入页面时只暂借地图 8bpp palette 的 240..255，退出页面立即恢复，
既不申请第二套 palette，也不占用战斗单位所需的 OBJ/OAM。

运行时红测还暴露出一个容量错误：`bn::tile` 是 32 字节，而 8bpp 逻辑 tile 是 64 字节。
初版仍按 8 个 `bn::tile` 分配却写入 8 个 8bpp tile，导致越界覆盖地图引用并在移动阶段
报 `Map cells are not aligned`。最终缓冲区固定为 16 个 `bn::tile`，Python wiring
测试持续约束这一 8bpp 存储契约。

修复后的当前交互证据为
`artifacts/scenario-41-screenshot-comparison-20260729-24/butano/`：

- `actions.png` 是由当前动作状态和 BG tile 结构绘制的整屏菜单，不再使用静态整页/分片
  截图或 12 个背景 OBJ；
- `target.png` 改在光标真正到达活动敌人、`cursor_unit_active == 1` 后采集，不再把进入
  目标阶段的初始空状态误作目标选择证据；
- `move-ui.png`、`target.png`、`facing.png` 仍由同一 ROM 的真实状态生成；
- `audit.json` 为 battle 41、round 4、action 5，控制器/玩家错误均为 0；
- `combat-trace.json` 记录每个 combat stage；本路线的敌方阶段只有地图移动，没有实际
  进入敌方决斗，因此敌方发起构图仍以共享投影测试签发，不能宣称已有本关实机截图；
- ARM 与 mGBA guard 均以 exit 0 完成，mGBA 峰值 owned-tree RSS 115.875 MiB。
- 最终回归为 7 项相关 C++ 宿主测试全部通过，93 项
  Python/Lua/文档契约通过（1 项需 `RUN_BUTANO_INTEGRATION=1` 的重复 ROM 构建显式跳过）。

当前 ROM SHA-256：
`5be39a71ed2c521e4b12fb8315de625424f64e413476cc7286caa0914a9fcb67`。
ELF SHA-256：
`ca6c4d955b9826c8161fab227636b5249388315cff9941c4018ff5a8bead39ca`。

## 边界

- 本轮签发的是通用战斗 UI 的状态投影和 scenario 41 完整战斗路线，不代表每个关卡的
  专属 UI 皮肤或每个技能的专属范围纹理已经还原。
- 自动路线静音，只验证控制流、图形、资源与错误状态，不签发音频质量。
- scenario 41 的确定性路线没有让敌方实际触发决斗；敌方发起时的左右规则由共享
  决斗投影函数和宿主集成测试固定，后续含敌方攻击的实机路线可继续复用该断言。
- scenario 49 / battle 14 的最终路线已经补到敌方实际攻击木叶丸。旧 Run17/Run97
  曾错误签发“发起者在左”；Run157 已按原作录像绑定的 manifest 纠正为“玩家左朝右、
  敌人右朝左”，实机画面在
  `artifacts/butano-battle-s49-six-ui-faction-duel-20260730-157/ui-enemy-initiated-duel.png`。
  这不会改变 scenario 41 自身没有敌方决斗的证据边界。
- 结算页不能简单复用同一种字体：标题和角色身份使用 16×16 身份字形，统计行使用
  8×8 可见 UI 字形。原作统计行每 8 像素一行；从截图提取时若按 8×16 裁切，会把下一
  行并入当前 glyph。当前生成器对“任务分/战斗分/回合分/合计”字形只取原作上半
  8 行，再补 8 行透明像素以满足 GBA OBJ 高度。最新同 ROM 结果页与完整 scenario 49
  路线见 `artifacts/butano-battle-s49-fidelity-20260729-17/manifest.json`。
