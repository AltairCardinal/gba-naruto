# Butano Scenario 41 1:1 复刻设计

## 目标与验收口径

在 Butano 21.7.1 中重建原 ROM 的 scenario 41，从“开始任务”确认后的战斗入场，经过
教程对白、玩家与敌方回合、单位选择、移动、行动菜单、朝向、防御提示、技能选择与演出，
自然到达胜利、经验/成长结果和战后交接。现有 `DEFEAT IRUKA / COMBO / WAIT` 纵切片只
作为可编译骨架，不再是视觉、流程或音频规格。

“1:1”按以下可机器验证口径解释，不用“风格相近”或“功能差不多”代替：

- 稳定 UI 与场景：相同输入边界的 240×160 RGB 像素 SHA-256 必须与原 ROM 相同。
- 动画：从同一前置 checkpoint 和输入开始，逐帧 RGB 序列、持续帧数、镜头/图层变化与
  原 ROM 相同；允许 mGBA 容器元数据不同，不允许归一化 RGB 不同。
- 战斗与回合流程：输入接受/拒绝、菜单层级、坐标、单位状态、回合交接、胜负与结果字段
  必须与原 ROM 的权威 trace 相同。
- 音频：播放 cue ID、触发帧、优先级、循环/停止边界和最终 GBA 输出采样序列必须相同。
  若 Butano 自带 Maxmod 后端不能得到相同采样，则为本关卡实现 MP2K 兼容播放路径；不能
  以相似音效或静音作为完成状态。
- 文本与字形：复用原 ROM 编码文本、字体 tile、窗口和调色板，屏幕结果以像素一致为准；
  OCR 文本只用于索引，不作为渲染输入。

## 权威输入与已确认事实

- 原 ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`。
- Butano：21.7.1，提交 `112a1827c9c6d9e6041a7e93e66f04c4561a6415`。
- battle ID 41；原地图为 36×44 个 8×8 tile，逻辑 grid 为 9×22，因此一个逻辑格对应
  4×2 tile，即 32×16 像素，而不是现版的 16×16。
- 初始 slot 1 为角色 1（鸣人）`(4,10)`，slot 2 为角色 30 `(4,4)`。原任务标题、
  战斗 HUD 与战后对白均显示“木叶丸”；旧 prose 把角色 30 标成“伊鲁卡”的说法与原 UI
  冲突，不能再作为规格。已验收自然路线在第4回合从
  `(5,6)` 移到 `(6,4)`，对 `(6,3)` 的敌人提交相邻技能，结果字节
  `0x02026807=1`。
- 权威 checkpoint 包括 `scenario-41-player-turn.ss9`、
  `scenario-41-first-movedone-facing.ss9`、`scenario-41-turn-1-complete.ss9`、
  `scenario-41-victory.ss9` 与 `scenario-41-postbattle.ss9`；其哈希和来源由
  `artifacts/runtime-checkpoints/scenario-41-*-evidence.json` 固定。
- 原 UI 由背景图层、对象层、窗口/文字和底部 32 像素状态栏共同组成。现版手绘绿色
  checkerboard、英文 Butano 字体、橙/灰 16×16 方块和自定义结果页都必须被替换。
- scenario 41 原结算页三项为 `100 / 50 / 0`、合计 `150`，随后鸣人升至 LV2（体力
  `+14`，多项属性 `+1`）。现版 `EXP +110 / TRAINING +1` 来自错误的跨关卡推断，
  不属于本关规格。

## 方案选择

### 采用：权威捕获优先的 Butano 原生重建

先从已验收 save-state 离线导出 I/O、PRAM、OAM、VRAM、IWRAM、EWRAM 和归一化截图，
再用固定输入运行补齐动画与音频 trace。导出的 manifest 是每个子系统的验收规格；Butano
场景按原始图层、资源和时序重建，最后用同一输入计划做原 ROM/Butano 双运行比较。

该方法保留真实交互与可维护源码，同时允许逐项证明差异已经归零。

### 不采用：截图或视频回放

把原画面作为全屏 bitmap 按预设输入切换，无法复刻任意光标、取消、移动、目标选择和
状态组合，也无法证明回合与战斗规则，属于伪交互。

### 不采用：继续改良近似纵切片

在现有 16×16 格、英文 presenter 和手绘资源上追加动画/音效，会固化错误坐标、布局和
流程，无法收敛到像素与采样一致。

## 分阶段架构

### 1. 原 ROM 参考捕获层

`tools/inspect_mgba_savestate.py` 扩展为只读访问序列化状态中的 I/O、PRAM、OAM、VRAM、
IWRAM 和 EWRAM。`tools/butano/export_scenario_41_reference.py` 校验 ROM/checkpoint 哈希，
导出每个边界的 GPU 内存、业务字段、截图指纹和 manifest。动态演出由受资源守卫保护的
mGBA Lua trace 补齐逐帧截图、按键、sound wrapper cue 和采样输出。

所有运行使用唯一 run ID，不覆盖旧证据；原始 dump 不在提取后删除。导出器遇到哈希、
尺寸、PNG、状态版本或边界字段不符时失败关闭。

### 2. 原始场景与 UI 资产层

根据 PRAM/VRAM/OAM/I/O 重建各稳定边界的 BG/OBJ 资源、tilemap、窗口和优先级，并与
原截图逐层合成校验。地图使用 32×16 逻辑格和原相机滚动量；底部状态栏、选择框、移动
范围、菜单、提示、对话框、头像、结果与成长页使用原 tile、调色板和字形。

Butano 资产生成器只接受经过 manifest 哈希固定的原始 dump，不再绘制替代素材。

### 3. 精确战斗与回合模型

把当前 `scenario_41_battle` 拆为关卡数据、战斗控制器、教程/对话控制器和渲染快照。
状态与原控制器边界对齐：入场、玩家单位选择、移动预览、移动提交、行动菜单、朝向、
防御、术菜单、目标、确认、MOVEDONE、敌方行动、教程对白、胜负检查、胜利、结果、
升级和战后交接。START 不再自定义为快捷 WAIT，除非原 trace 在对应状态接受它。

领域测试使用从原 route 提取的逐命令 golden trace；非法输入必须同时匹配状态不变性和
原 cue/反馈。

### 4. 角色、动画与特效层

从原 OBJ tile、palette、OAM 属性和 79×0x44 battle visual descriptor 中提取鸣人、
角色 30（原 UI 显示木叶丸）、光标、移动、朝向、受击、技能和胜利演出所需资源。每段动画以帧索引、持续帧、
位置、翻转、priority、palette、BG/OBJ blend 和镜头偏移描述，不把稳定截图当动画。

Butano 运行时使用固定容量 animation timeline；逐帧对照发现的任何额外对象、窗口或
调色板变化都进入 timeline，而不是用延时常量掩盖。

### 5. 音频兼容层

从 sound ID 表、MP2K track/voicegroup/tone 和运行时 wrapper trace 得到 scenario 41
实际使用的 BGM、UI cue、移动/攻击/技能/胜利/结果音效。首先验证 Butano 导入后的 GBA
采样是否一致；若不一致，使用现有 `m4a_*` 解码/调度模块生成兼容事件数据，并在 Butano
中实现本关卡所需的最小 MP2K 命令、ADSR、pitch、PSG/noise 和 DirectSound 混音子集。

静态候选名不是 cue 身份证据；只有在同一可见事件边界捕获的 ID 和输出采样可进入关卡
manifest。

### 6. 双运行验收层

同一输入计划分别作用于 `rom/base.gba` 和 `butano-sequel.gba`。比较器校验：

- 每个稳定边界的 RGB 哈希；
- 每个动画区间的逐帧 RGB 哈希与长度；
- 输入、菜单/阶段、单位坐标、HP/资源、回合、结果与奖励 trace；
- cue ID/帧/生命周期和左右声道 PCM；
- 冷启动到战后交接的完整连续路线。

任何缺少原始证据的区间判为“未验收”，不能用现有测试通过推断完成。

## TDD 与集成测试

- 参考捕获：先测试 save-state 地址映射、区域尺寸、哈希失败和确定性 bundle，再实现导出。
- 资产：先以原截图 RGB 哈希写失败测试，再生成/接入 tile、palette、map、OBJ 和字体。
- 流程：每个状态转换先写原 trace golden test；UI wiring、按键、音频事件各有能在断线时
  失败的集成测试。
- 动画/音频：先固定原 ROM 帧/采样 manifest，再让 Butano 输出从差异变为一致。
- 每个里程碑均执行宿主测试、Docker 干净 ROM 构建和受守卫 mGBA 运行；只有最终连续
  双运行全通过才可完成 Goal。

## 用户可见行为与边界

入口是原作“开始任务”确认后的 scenario 41，而不是自定义英文提示。玩家看到原森林
战场、角色、选择框、状态栏、菜单、头像与文本；每次方向/A/B/START 输入按原状态给出
相同画面和音效，敌方回合与教程对白按原时序推进，胜利后显示原经验/成长页并进入原战后
交接。

加载中、空状态、错误或数据缺失不使用替代素材继续运行：开发构建以断言和 manifest
错误停止，证据记录缺失边界。该关卡 1:1 目标不自动扩张为其他关卡、旧存档兼容或全游戏
引擎，但 scenario 41 实际经过的所有 UI、场景、角色、动画、音效、战斗与回合状态均在
范围内。
