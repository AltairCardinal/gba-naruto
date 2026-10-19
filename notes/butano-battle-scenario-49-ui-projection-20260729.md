# Scenario 49 / battle 14 战斗 UI 状态投影（2026-07-29）

## 关卡边界与纠错

本轮只验收“护送木叶丸逃离野蜂”：scenario 49、battle 14。参战编队是鸣人、佐助、
小樱和友军木叶丸对五只野蜂；scenario 41 的鸣人与木叶丸教学单挑不属于本轮 Goal。
默认验收入口已切到 scenario 49。若 SRAM 仍停在旧的 scenario 41–47，启动时只在内存
中回退到准备好的 scenario 49 检查点，不会先把旧值写回存档。

原作权威画面：

- `artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`
  （SHA-256 `a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1`）；
- `artifacts/runtime-checkpoints/scenario-49-battle-14-turn4-two-kills.ss9`
  （SHA-256 `e8b2a5ee0cc4dfbcf89086c8a5fd8fb2bc9e38b9a7bec83cfcb2e3e2a44de350`）；
- 原作完整自然路线、木叶丸受击与五只野蜂清除事实见
  `notes/scenario-49-battle-14-runtime-20260720.md`。

入口图和第四回合图共同显示：当前行动单位锚定在约 `(120, 80)` 的完整 240×160
视口中心，底部 HUD 不参与重新计算地图中心；只有到地图边界时才夹取。第四回合图还显示
青色可移动范围、橙色目的格、当前单位头顶方向标记和 8 像素级战斗 UI 字形。原作录屏
逐帧结论见 `notes/butano-battle-video-frame-analysis-20260722.md`：移动、动作范围、
目标、面向和防御是同一单位行动的连续阶段，敌方也通过相同地图/决斗规则发起攻击。

## 六项问题的当前实现

| 问题 | 状态投影与用户可见结果 | 本关实机证据 |
|---|---|---|
| 字体比例 | 剧情正文按原 ROM 的 8×16、2bpp 字形解码；行动列表、选中招式、说明和中文底栏提示使用本关原作全高行动字形；角色名、数值和英文按键提示使用独立 8×8 字体；准备/任务界面的 8×16 字源在战斗小字覆盖前冻结，互不污染 | Run97 `ui-phase-18.png`、`ui-phase-6.png`、`ui-phase-21.png`、`ui-phase-9.png`、`ui-phase-14.png` |
| 移动/攻击 UI | 移动可达格由 pathfinder 结果投影为青色；动作射程投影为橙色，合法敌方目标由 `target_legal()` 结果投影，renderer 不复制规则；网格、光标和阻挡格也使用独立实时角色 | Run97 `ui-phase-2.png`、`ui-phase-8.png`、`range-ui-element-comparison.json` |
| 目标预览与攻击确认 | 合法目标第一次 A 显示光标下黄蜂详情，第二次 A 打开“可以吗？”，第三次 A 才结算；两个中间阶段均无领域副作用并保留动作范围。无文字框体和独立光标来自本关原作 GPU | Run97 `ui-phase-22.png`、`ui-phase-20.png`、`target-confirmation-comparison.json` |
| 头顶面向 | 面向阶段的单位帧与头顶四向指示都读取 `selected_facing`；方向键只更新预览，A 才提交；指示 OBJ 按原作 16 帧周期在 2/3/0 像素三个外移相位间切换 | Run105 `ui-phase-9.png`、`entry-ui-comparison.json` |
| 佐助镜头 | 选择位于地图下方的佐助后，镜头以其格中心聚焦并在地图边缘夹取；角色不会再落入底部 HUD | `ui-sasuke-focus.png` |
| 敌方决斗朝向 | 决斗屏幕按阵营固定站位：玩家固定在左朝右，敌人固定在右朝左；敌方发起时只改变动作角色，不交换双方站位，也不继承地图相对 X 或旧面向 | Run157 `ui-enemy-initiated-duel.png` |
| 回合末面向 | 技能、忍具、补充查克拉、休息和显式行动结束在未触发胜负时统一进入 `end_confirmation → facing_selection → defense_decision` | `ui-phase-21.png`、`ui-phase-9.png` |

当前同一 ROM 截图、遥测与比较结果来自
`artifacts/butano-battle-s49-fidelity-20260730-97/`。其中敌方决斗图只在遥测同时满足
敌方阶段和 `duel_setup..technique_title` 时采集，避免把敌方地图移动误记成决斗。
佐助面向图可见佐助位于屏幕中央、四向指示在头顶、底部显示
“请选择人物面对的方向”。对白图由 selector 1、原 ROM 文本地址 `0x08052A98` 触发，
采集时消息窗和两侧立绘遥测均为可见、演出不忙；捕获器等待八个视频帧越过 OBJ 资源
切换中间帧后才签发截图。

结算页最初虽已分离大小字体生成器，但从原作结算页提取“任务分/战斗分/回合分/合计”
字形时仍按 8×16 裁切。原作统计行的基线间距只有 8 像素，因此该裁切会把下一行同时
写入同一个 glyph，形成纵向叠字。生成器现把这八个统计字形的原作 8×8 可见区域放入
8×16 透明 OBJ 单元；这保留 Butano 合法 sprite 高度，同时不再捕获下一行。对应红测会
逐字断言下半 8 行全透明。

## 架构约束

- 字体、地图范围、合法目标、镜头、单位层级和决斗站位都是共享战斗表现投影，不按
  battle 14 写死截图或坐标。
- 字体按用途分成剧情字形、战斗小字、准备/任务字形和结算标题/身份大字四个消费者；
  原作紧凑统计行的可见高度属于字形资产契约，不由运行时缩放或负行距补偿。准备字形
  从覆盖前的全高源表生成，不能继承战斗 UI 的 8×8 紧凑字形；这是避免一种修复破坏
  另一种字号的长期边界。
- 范围层使用预留的原始 OBJ palette 区间，面板使用另一段预留区间，避免字体、范围和
  面板动态争抢 4bpp palette；六类格子角色均由 controller snapshot 实时生成。
- 移动/目标/面向均读取 controller snapshot；UI 不直接改 session，不把预览当提交。
  battle 14 的目标流程显式经过共享 `target_preview → target_confirmation`；第三次 A
  才调用现有 resolver。预览/确认的状态栏读取 `battle_ui_unit_at_cursor()`，并继续
  投影同一组动作范围 rows；退出目标流程时才清除，避免事务中途丢失选择上下文。
- 单位 z-order 按视觉 y 动态排序，位置越靠下越靠前；移动预览使用同一规则。
- 玩家与 AI 共用 `battle_turn_flow` 的效果、面向和防御尾部。
- 技能/忍具菜单复用共享 action catalog、controller snapshot 和 campaign inventory；
  原作 BG3 只提供无状态窗口 tile/map，原作 OBJ 只提供六种独立类型/效果图标。动作名、
  当前资源、消耗、数量、距离、范围、成功率和说明均由运行时状态投影，不使用整屏截图。
- 移动后指令菜单复用同一 BG tile 拓扑，菜单高度与可用命令来自 controller snapshot；
  两行文字由原作 8×16 字形动态生成，选择箭头是从原作 GPU 状态提取后按
  `command_index` 移动的独立 8×16 OBJ，不把选中状态烘焙进框体。
- 新 campaign 的默认装备属于 route 初始化事务，`main.cpp` 不得再次覆盖；route 只在
  `chapter_id == 0` 时写入 battle 14 的初始“十字手里剑”，因此加载存档和玩家换装
  不会被复位。

## TDD 与运行时验证

红测先固定 scenario 49 默认入口、旧 SRAM 回退、battle 14 完整 UI 流程、镜头和左右
投影。技能菜单补充红测固定原作窗口像素、图标帧、动作分组顺序以及 route 所有的
默认十字手里剑；入口红测证据为
`build/resource-guard/s49-acceptance-entry-red-20260729-01.json`；ARM 产物构建证据为
`build/resource-guard/s49-six-issue-arm-build-20260729-01.json`。最新相关验证：

- 11 个聚焦 C++ 宿主/集成程序通过，覆盖 catalog、loadout、player flow、
  combination flow、controller、AI turn、action-menu map projection 和 campaign
  route；
- 69 项聚焦 Python/Lua 契约通过，包含 campaign route、UI wiring、剧情字形、UI
  字形/资源生成、原作边界捕获与动作/指令菜单像素对比；
- devkitARM 构建通过，guard：
  `build/resource-guard/s49-target-preview-arm-20260729-45.json`；
- mGBA 从 scenario 49 冷启动完整打完 battle 14，round 13 清除五只野蜂，
  木叶丸存活，结果经验 `125 + 50 = 175`，鸣人变为 LV2 / 25 经验 / 1 修炼点，
  保存 generation 1 并推进到 scenario 50；`last_control_error=0`、
  `last_player_error=0`；
- mGBA guard 由 success marker 正常结束，峰值 owned-tree RSS
  `122.7265625 MiB`。

当前 ROM SHA-256：
`43077273dfd16cdf4398c108c3c15f672bce691d50b72ca2189b3d76ad0555c4`。
ELF SHA-256：
`1fc86e46c0e349c37ed258f49c9b51ae86bac996fa842c4fe10df729cd4e881a`。

技能/忍具菜单的原作稳定截图与 GPU dump 位于
`artifacts/scenario-49-battle-14-original-ui-boundaries-v1/`。Run66 对其中不受
动态内容覆盖的 12,992 个框体像素比较为 0 差异，四行共 8 个 16×16 类型/效果图标
也全部为 0 差异。这里签发的是动态结构和图标，不把原作 HP99 等状态值与当前路线
HP80 的非同态文字区域混为整屏等价。

同一 Run66 还捕获了鸣人真实移动后、命令已过滤为“术・忍具／行动结束”的状态。
该状态的 1,152 个无状态框体像素、两行各 512 个动态文字像素和 128 个独立 OBJ
选择箭头像素与原作均为 0 差异；比较结果见 `command-menu-comparison.json`。这一
结论只签发两项过滤状态，不外推到未逐项捕获的其他命令组合。

Run69 新增 battle 14 的独立目标预览并保留攻击确认。原作 GPU 状态证明 BG3 框体使用
`0x1C1..0x1C9`，选择光标为 OAM entry 0 的 `0x3F6..0x3F7`。Butano 将框体、动态
文字与光标保持为三个独立层，`(80,24)..(159,87)` 共 5,120 个不透明像素与原作
差异为 0。预览和确认底栏都读取光标下 25 HP 黄蜂且像素互相一致；不过与原作底栏
直接比较仍有 6,509/10,560 像素差异，因此 HUD 视觉仍未签发。

## 边界

- 自动路线静音，不签发音频质量。
- scenario 49 的当前冷路线不自然重放更早章节剧情；本关 selector 1 实机图已签发
  8×16 对白可读性，但缺少同状态原作稳定截图时不宣称整屏像素等价。
- 技能菜单的紧凑字号、行距、动态装饰框、动作顺序与类型/效果图标，以及移动后两项
  指令菜单的框体、文字与光标已闭合；非同态状态下的文字和数值不宣称整屏逐像素等价。
- 目标预览/确认的三步交互、目标状态和范围清除已闭合；底部状态栏的高度、纹理与文字
  布局仍有直接量化差异，是后续优先项。
- 本轮闭合六项功能缺口，不宣称所有框体编织纹、范围纹理、调色和全关卡逐帧时序已经
  与原作像素等价；总 Goal 继续保持 active。

## 战后任务概览补充签发

Run30 将 battle 14 胜利后的出口从额外英文 `BATTLE COMPLETE / A EXIT` 页面改为
原作流程：完成态先释放战斗地图、单位、光标和 UI 资源，保存 campaign 并进入
scenario 50 任务概览；概览初始不显示根菜单，按 A 后才打开菜单。

概览不是截图回放。生成器分别从
`scenario-49-battle-14-postbattle-task-menu.ss9` 和
`scenario-49-post-training-task-menu.ss9` 提取标题框、正文框与菜单框的八像素
无状态边缘，运行时根据 campaign 动态绘制标题、正文、红色敌方名、蓝色保护对象和
菜单。独立 8×16 准备界面字体保留原作前景、阴影与中间色；逐像素复核同时纠正了
第三行“所以不要让他去接近危险品。”以及末行片段连接位置。

`artifacts/butano-battle-s49-fidelity-20260729-30/postbattle-task-menu.png`
与原作 checkpoint 的 240×160 解码 RGB 比较为 0 个差异像素。Run30 的 ROM/ELF
SHA-256 为
`d30ec43276632873c05f7593d993f7c81f59d45ea0432f7feec9068b914208ea` /
`03d7bfe13349113668c81d695c78062ec18ba4706c9f74fb41362688ca9ff5e5`；
完整哈希、遥测、守卫与边界声明见
`artifacts/butano-battle-s49-fidelity-20260729-30/manifest.json` 和
`notes/scenario-49-battle-14-screenshot-fidelity-matrix-20260729.md`。

## 战后根菜单补充签发

原作从 scenario 50 概览只输入一次 A 的复现证据已固化在
`artifacts/scenario-49-battle-14-postbattle-root-menu-v1/`。最初实现把菜单框烘焙在
背景层，而任务正文是 OBJ，导致后方文字穿透菜单；之后虽改为独立菜单 OBJ，字体生成的
黑色箭头仍覆盖了原作多阶灰白光标。

Run33 将菜单拆成四块无文字 OBJ，任务正文置于其后，选项置于其前；选中光标则成为读取
`root_option` 的独立 8×8 OBJ，可在四个选项间移动。框体不再含状态，确认弹窗继续位于
菜单和光标之前。`postbattle-task-menu.png` 与概览原证据、以及
`postbattle-task-menu-root.png` 与原作单 A 根菜单证据，两组 240×160 解码 RGB 比较
均为 0 个差异像素。

Run33 ROM/ELF SHA-256 为
`eadd37c03f98337f7270b20c2ff525f6899fa28975dfe4c5620666250045d941` /
`6be7dc47d4d9b33e8fe0f3875bd163fce9a03e9a4ee89e72532c97e168aaa0bf`；
完整路线、存档遥测、逐像素结果和守卫见
`artifacts/butano-battle-s49-fidelity-20260729-33/manifest.json`。

## 结算页运行时投影补充签发

Run322/323 证明原作结算页由 BG0 灰色舞台、BG3 页眉/页脚、三名 OBJ 角色和动态
文字组成。生成器分别保存无状态 BG 层、三套 32×64 角色姿势、结算页紧凑数字字形和
全高姓名/合计字形；运行时仍从 `battle_result` 读取参与者和四类经验值。

Run336 与原作逐区比较结果为：页眉 7,680/7,680、三名角色 6,144/6,144、同态任务分
768/768、其余无状态舞台/框体 26,880/26,880 像素一致。原作自然路线与当前自动路线的
击杀归属和回合数不同，所以战斗分、回合分、合计不做整屏同态声明；这些值没有为截图
比较被改写。完整证据见
`artifacts/butano-battle-s49-result-exact-position-20260730-336/result-comparison.json`。

## 战前根菜单与确认态补充签发

Run337 将 scenario 49 战前根菜单和开始任务确认态加入完整路线截图。差异审计证明，
根菜单框体与选项本已正确，主要缺口是蜜蜂任务专用 8×16 字形和光标相位；确认态则还
错误地保留了后方根菜单，并用通用文字箭头代替原作独立 OBJ。

当前准备界面继续按状态投影：`root` 组合任务正文、四块无文字菜单框、四项文字和可移动
光标；`start_confirmation` 清除根菜单，只组合任务正文、五块无文字确认框、动态
“开始任务吗？/是/否”和独立选择箭头。确认框内部不包含任何文字或选择状态。

Run342 的 `prebattle-task-menu-root.png` 与原作 Run106、`prebattle-task-confirmation.png`
与原作 Run107 均为 240×160、38,400/38,400 像素一致，PNG SHA-256 相同。比较与完整
路线证据见
`artifacts/butano-battle-s49-prebattle-exact-20260730-342/prebattle-comparison.json`。
后续可用 `tools/butano/compare_s49_prebattle.py` 对两组同态截图重算差异边界和
SHA-256，避免手工区域判断。
