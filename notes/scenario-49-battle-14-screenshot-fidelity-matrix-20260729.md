# Scenario 49 / battle 14 截图等价矩阵（2026-07-29）

## 范围

本矩阵只覆盖“护送木叶丸逃离野蜂”（scenario 49 / battle 14），不把 scenario 41
教学战当作本关证据。状态必须由同一运行时真实推进；截图只能签发它实际捕获的边界。

## 原作直接证据与当前状态

| 边界 | 原作直接证据 | Butano 同态证据 | 当前结论 |
|---|---|---|---|
| 战前任务根菜单 | Run106 `original-s49-task-menu-sequence-20260730-106/frame-00.png` | Run342 `prebattle-task-menu-root.png`、`prebattle-comparison.json` | 无文字框体、当前任务正文、四项菜单和独立深色光标均由运行时分层组合；**240×160、38,400/38,400 像素一致，PNG SHA-256 相同** |
| 战前开始任务确认 | Run107 `original-s49-task-start-20260730-107/step-03-A.png` | Run342 `prebattle-task-confirmation.png`、`prebattle-comparison.json` | 确认态按原作移除根菜单，显示无文字确认框、动态提问/是/否和独立选择箭头；**240×160、38,400/38,400 像素一致，PNG SHA-256 相同** |
| 战斗入口 | `scenario-49-battle-14-entry.ss9`，Run103 连续 32 帧 | Run105 `ui-phase-1-frame-00..31.png`、`entry-ui-comparison.json` | 原作 frame 00 与当前 frame 23 的 **240×160、38,400/38,400 像素一致，PNG SHA-256 相同**；选中轮廓为 RGB5 `(0,23,23)`，四向光标按原作 16 帧周期脉冲 |
| 战斗对白 | battle 14 selector 1，原 ROM 文本地址 `0x08052A98`；`original-s49-facing-sequence-tail-20260730-114/step-06-A.png` | Run218 `ui-phase-18.png` | 原版与 Butano 的 **240×160、38,400/38,400 像素完全一致**；PNG SHA-256 相同，背景、8×16 正文、两侧立绘和消息窗均为运行时独立层 |
| 技能/忍具菜单 | 本关原作 `scenario-49-battle-14-original-ui-boundaries-v1/turn4-skill-menu/frame.png` 及同目录 GPU dump | Run105 `ui-phase-6.png`、`action-menu-comparison.json` | 窗口 12,992 像素、8 个图标和 14 个动态文字/控件区域均为 0 差异；排除真实当前 HP 值的 24×8 框后，全屏其余 **38,208 像素 0 差异** |
| 移动后指令菜单 | 本关原作 `scenario-49-battle-14-original-ui-boundaries-v1/turn4-command-menu/frame.png` 及同目录 GPU dump | Run66 `ui-command-after-move.png`、`command-menu-comparison.json` | 真实移动后只显示“术・忍具／行动结束”；1,152 个无状态框体像素、两行各 512 个动态字形像素及 128 个可移动选择箭头像素均为 0 差异 |
| 移动/目标/面向 | `scenario-49-battle-14-turn4-two-kills.ss9`、`turn4-target-selection/`、Run103 入口序列、Run182 `step-01-A.png` | Run204 `ui-phase-2.png`、`ui-phase-8.png`、`ui-phase-9.png` | 六类范围格的 3,072 像素及 11 个 RGB5 调色板项均为 0 差异；方向指示读取当前朝向并按 4/7/5 帧三相位动态脉冲；面向提示栏 240×24、5,760/5,760 像素一致 |
| 目标预览与攻击确认 | `turn4-target-up-a-01/step-02-A.png`、`turn4-target-confirmation/frame.png` 及 GPU dump | Run105 `ui-target-status-homologous.png`、`ui-phase-20.png` | 第一次 A 预览、第二次 A 确认、第三次 A 执行；底部目标详情 11,520/11,520 像素、确认框 5,120/5,120 像素均为 0 差异 |
| 下方单位镜头 | 同一原作地图/镜头规则 | Run72 `ui-sasuke-focus.png` | 攻击结算后光标恢复到行动者实际落点；佐助聚焦在可视区中央并避开底部 HUD，功能签发 |
| 敌方发起决斗 | Run188 `frame-400.png`；Run190 `io/pram/vram/oam` | Run218 `ui-enemy-initiated-duel.png` | 原作按阵营固定玩家左朝右、敌人右朝左；当前野蜂仍在右侧朝左攻击左侧友军。顶部“蜂刺”及框体 **240×32、7,680/7,680 像素一致**；同为野蜂 25/25 HP、0/0 查克拉的右侧动态状态面板 **120×48、5,760/5,760 像素一致**。左侧单位不同，不扩写为整屏同态 |
| 战斗结算 | Run322 自然胜利页；Run323 `io/pram/vram/oam/frame.png` | Run336 `ui-phase-14.png`、`result-comparison.json` | 原作 BG0 舞台、BG3 无状态框体、三名动态姓名、三套原作 OAM 结算姿势、紧凑分数字形和大号合计字形均按运行时层重建。页眉 7,680/7,680、角色 6,144/6,144、同态任务分 768/768、其余无状态区域 26,880/26,880 像素一致。两次自然路线的击杀归属/回合数不同，其余分数保持各自真实值，不伪造整屏哈希 |
| 战后下一任务概览 | `scenario-49-battle-14-postbattle-task-menu.ss9` | `postbattle-task-menu.png` | **240×160 解码 RGB 38,400/38,400 像素一致** |
| 战后下一任务根菜单 | `scenario-49-battle-14-postbattle-root-menu-v1/after-a.png` | `postbattle-task-menu-root.png` | **按 A 后 240×160 解码 RGB 38,400/38,400 像素一致；光标是可移动 OBJ，不是截图烘焙** |

## 战后概览的实现边界

- 外框只提取原作标题框、正文框和菜单框的八像素无状态边缘；没有复制正文或选项。
- 内部填充、标题、正文、红色敌方名、蓝色保护对象与菜单均由运行时状态动态组合。
- 准备界面使用独立 8×16 字体与三种语义调色板。字体保留原作前景、阴影和中间色，
  不再通过缩放剧情字体或复用战斗小字凑尺寸。
- 原作文案经像素边界复核：第三行是“所以不要让他去接近危险品。”；末行动态片段
  必须无空格连接。
- battle complete 后不显示额外英文 `A EXIT` 页；运行时释放地图、单位、光标和 UI
  资源，保存并进入 scenario 50 概览。概览按原作先无菜单显示，A 才打开根菜单。
- 根菜单使用四块无文字 OBJ 框体遮挡后方任务文字；菜单选项与 8×8 光标分别由当前
  `root_option` 动态生成。原作单次 A 输入证据固化于
  `artifacts/scenario-49-battle-14-postbattle-root-menu-v1/`，不再误用前一任务菜单
  作为 scenario 50 的状态对照。

## 技能/忍具菜单的实现边界

- 原作稳定边界来自 battle 14 第四回合真实输入链：
  `turn4-two-kills → A 选择鸣人 → A 打开技能/忍具菜单`。输入后状态、画面和
  `io/pram/oam/vram` 均以 SHA-256 固化在
  `artifacts/scenario-49-battle-14-original-ui-boundaries-v1/manifest.json`。
- 窗口不是整屏截图。运行时使用从原作 BG3 解出的九种 8×8 窗口 tile 和原作
  20×30 map 拓扑构造 regular BG；角色状态、动作列表、详情和底部说明继续由
  controller、action catalog 和 campaign inventory 动态绘制。
- 六种 16×16 图标“忍、体、具、移、效、攻”是独立 OBJ 帧。运行时按动作 kind、
  resource 和 effect code 投影每一行，不在背景中烘焙当前选择。
- 原作菜单先列查克拉动作，再列体力动作，最后列忍具；共享 catalog 采用稳定分组，
  不按本关硬编码四个字符串。新存档的 battle 14 默认装备 ID 1“十字手里剑”；此前
  `main.cpp` 把首槽覆盖为 ID 67“引爆牌”，导致第四行错误显示“具／效”，现已由关卡
  路由统一初始化，已有存档和玩家后续换装不会被覆盖。
- 比对工具 `tools/butano/compare_s49_action_menu.py` 分别核对 12,992 个静态框体像素、
  8 个完整图标和角色名、详情标签、动作列表、说明、`START/B`、返回提示、选择箭头等
  14 个动态区域。Run105 全部为 0 差异；整屏比较只排除当前 HP 值所在的 24×8 框，
  其余 38,208 像素为 0 差异。HP 保持真实运行时状态，不用伪造数值追求截图哈希。

## 移动后指令菜单的实现边界

- 原作稳定边界来自第四回合动作菜单前的真实指令状态；Butano 捕获则要求
  `phase=command_selection` 且 `move_preview != selected_unit`，因此不是用初始五项
  菜单冒充移动后的两项过滤状态。
- 两项框体复用技能菜单同一套九宫 BG tile，并由 `command_count` 动态决定高度。
  “术・忍具／行动结束”从原作 battle 14 指令菜单的 8×16 字形源生成，不在背景中
  烘焙文字。
- 选择箭头是从该 checkpoint 的 OAM entry 0、OBJ tile `0x3F4..0x3F5` 和 palette
  bank 15 提取的独立 8×16 OBJ；运行时根据 `command_index` 移动，不属于字体。
- `tools/butano/compare_s49_command_menu.py` 分别签发 1,152 个静态框体像素、两行
  各 512 个文字像素和 128 个选择箭头像素。Run66 四项差异均为 0；此结论只覆盖
  已捕获的移动后两项状态，不外推到其他命令组合。

## 攻击目标确认的实现边界

- 原作输入链为“忍者组合拳目标选择 → 上移到合法黄蜂 → A 打开目标预览 → A 打开
  `可以吗？/是/否`”。状态、画面和 `io/pram/oam/vram` 已加入原作 manifest。
- battle 14 现在显式启用共享 `target_preview → target_confirmation` 两个阶段。第一次
  A 只调用 `preview_target()` 并切换底栏到光标下的黄蜂；第二次 A 才打开确认框；
  第三次 A 才复用 `_confirm_target()` 原子结算。两个中间阶段都断言攻击者与目标单位
  快照完全不变、presentation queue 为空，并继续投影与目标选择相同的范围 rows。
- B 会逐层从确认返回预览、再从预览返回范围选择；确认框选择“否”也返回预览，不会
  越层回到技能菜单。行动者的移动预览位置在两个阶段保持不变，不会视觉瞬移回原格。
- 80×64 框体不是截图回放：生成器从签名 GPU 状态的 BG3 tile
  `0x1C1..0x1C9` 重组无文字框体；“可以吗？/是/否”继续由实时 UI 字形生成；选择光标
  从 OAM entry 0、OBJ tile `0x3F6..0x3F7`、palette bank 15 提取为独立 8×16 OBJ。
- `tools/butano/compare_s49_target_confirmation.py` 比较完全不透明、与地图状态隔离的
  `(80,24)..(159,87)`，Run105 的 5,120 个像素差异为 0。
  `tools/butano/compare_s49_target_status.py` 对同态目标详情底栏核对 11,520 个像素，
  Run105 同样为 0 差异；旧 Run69 的状态栏差异结论已被取代。

## 最新证据

2026-07-30 的当前可玩 ROM 证据为 Run342：

- 当前证据目录：
  `artifacts/butano-battle-s49-prebattle-exact-20260730-342/`
- 当前 ROM SHA-256：
  `1c6e7967fd2ac3c924c1a47887b83caad368864a0d5a7164cd1a8e2a4ffe640b`
- Run342 从冷启动完成 battle 14 并推进 scenario 49→50，无断言；同一次运行重新捕获
  移动范围、攻击/目标范围、佐助镜头、动态四向、回合末面向和敌方发起决斗。
- Run106 原作战前根菜单与 Run342 当前根菜单、Run107 原作开始任务确认与 Run342
  当前确认态，两组均为 **38,400/38,400 像素一致且 PNG SHA-256 相同**。任务正文、
  菜单、光标、确认框与确认箭头仍是独立运行时层，不是整屏图片。
- 决斗 HUD 继续由无状态 BG3 壳加实时文字、数值和资源条组成。专用数字字体只保留
  94 个 ASCII 槽；顶部 7,680 像素和同态敌方状态面板 5,760 像素均为 0 差异。
- 原作 Run114 与当前 `ui-phase-18.png` 的整屏 38,400 像素、原作 Run182 与当前
  `ui-phase-9.png` 的底部提示栏 5,760 像素均为 0 差异。
- 100 项 Python/Lua/资源契约和 8 个核心 C++ 测试通过；范围验证器再次确认六类
  格子 3,072/3,072 像素和 11/11 个调色板项为 0 差异。
- 当前重置档装备“毒手里剑”，与原作动作页的“十字手里剑”不是同态内容；336 像素
  文本差异被归因为存档装备，不是字体回归。Run204 的十字手里剑同态证据继续有效。
- 原作 Run103 与当前 Run105 各取 32 个入口连续帧，存在一对全屏 38,400 像素
  0 差异且 PNG 哈希相同的动画相位。选中单位轮廓色和方向箭头 16 帧脉冲均已闭合。
- 行动菜单除真实当前 HP 值框外的 38,208 像素为 0 差异；移动后指令菜单、目标确认、
  目标详情、六类范围格元素及 11 个调色板项也均为 0 差异。
- 原作自然胜利 Run322/323 取代“结算页没有稳定原作截图”的旧结论。Run336 结算页
  无状态舞台/框体、姓名、角色姿势和同态任务分均为 0 差异；非同态经验值仍由真实
  `battle_result` 生成，不为像素对照改写领域状态。

以下 Run72/97 信息保留为历史证据：

- manifest：`artifacts/butano-battle-s49-fidelity-20260729-72/manifest.json`
- ROM SHA-256：
  `5ade0a18fb903295899cd5b9acbc971b71d22b3aab3226cb6e89167b478a74c3`
- ELF SHA-256：
  `306b486329c1424ea920c2e515bed4cbd2b0ba6c8421e915b7e3c4ee61cd4121`
- mGBA：冷启动路线在 round 13 真实清除五只野蜂、木叶丸存活、推进 49→50；
  结果经验为 `125 + 50 = 175`，鸣人变为 LV2 / 25 经验 / 1 修炼点，存档
  generation 1 验证成功，首槽忍具为 ID 1，`last_control_error=0`、
  `last_player_error=0`。
- 对白截图只在 `script_phase=wait_for_input`、消息窗可见、`presentation_busy=0`
  后再等待八个视频帧采集，避免把视觉 cohort 资源切换的中间空帧误签为对白。
- 自动路线补充 `luac -p` 回归检查；Run67 曾因主 chunk 新增一个局部常量超过 Lua
  200-local 上限而在脚本加载阶段被拒绝，该常量改为模块级后 Run69 正常完成。Run68
  虽通关但误抓了影分身空格目标，已由“敌方目标类型 + 光标下活动敌军”的截图条件取代。

## 未签发边界

- 自动路线静音，不能据此签发音频。
- 移动、技能范围和敌方决斗仍缺少与所有 Butano 动态单位状态一一配对的原作截图；
  结算页已有稳定原作 GPU 证据，并已签发所有同态区域。
- 入口、技能菜单、移动后两项指令菜单、目标详情和目标确认的同态区域均已闭合。
  技能菜单唯一排除项是两边状态不同导致的当前 HP 数字，不属于 UI 结构差异。
- 总 Goal 继续保持 active，后续只应补齐缺失的原作状态边界并逐项对照，不能把
  scenario 41 截图或在线录像截图冒充本关像素权威。

## 2026-07-30 Run363 战后升级与新术汇总闭合

- Run349/351/352 的原作 GPU dump 证明升级页由 BG 面板、两块标题 OBJ、七项实时
  成长值、六块角色立绘 OBJ 和眼睛图标组成。Butano 按
  `result_participant_index + level_up_detail_page` 投影鸣人、佐助、小樱各两页，
  成长值继续读取 `battle_result.stat_growth`，没有用整屏截图替换状态。
- 首次运行在结算页进入升级页时停住，根因是 8bpp 立绘占满 OBJ 调色板后，标题和
  眼睛又申请独立 4bpp palette。当前所有升级页 OBJ 统一使用一套 8bpp palette；
  专门的失败测试会检查七类 OBJ 资源的位深和 256 色 palette 完全相同。
- 原作 battle 14 的后续流程不是英文自由加点菜单，而是六页“新术提示/累计列表”。
  controller 仅在 `battle_id=14, variant=0` 启用该摘要状态机，A 逐页推进，其他战斗
  继续保留共享训练系统。运行时按 `training_detail_page` 选择原作 BG 文本层，眼睛
  仍是独立 OBJ；遥测和 mGBA 路线按实际页码等待稳定帧后逐页截图。
- Run363 的升级首屏和修行六页均与对应原作 240×160 帧达到
  **38,400/38,400 像素一致，差异像素为 0**。生成器还对升级的 3 名角色×2 页全部
  做分层重组 0 差异测试；controller 宿主测试验证六个升级页和六个修行页的 A 键顺序。
- 同一 Run363 从冷启动在第 9 回合清除五只野蜂、木叶丸存活，保存并推进
  scenario 49→50；任务分/战斗分/合计为 125/100/225，控制器和玩家错误均为 0。
  83 项相关 Python/Lua/资源测试、4 个核心 C++ 宿主测试、受守卫 ARM 构建和完整
  mGBA 路线通过。证据目录：
  `artifacts/butano-battle-s49-complete-ui-runtime-20260730-363/`。
- 当前 ROM/ELF SHA-256：
  `785757697b9d0e4b657c644ccf38fbca289afa93fca30b1301f7f2c4ae2f5e26` /
  `07a2734f463cc7936705404186d822b70bc22a627dc50a71c2ebfbcaff4e3650`。
  自动路线静音，因此音频仍不在本 UI 签发范围。本节取代上方“总 Goal 继续保持
  active”的历史状态：battle 14 的完整玩家 UI 循环现已闭合，可进入人工验收。
