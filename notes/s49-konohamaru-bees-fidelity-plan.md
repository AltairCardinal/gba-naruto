# S49 木叶丸与野蜂 全分支操作录屏、差分核对与 100% 复刻方案

## 1. 目标与验收规格

根据用户指令：
基于逆向成果，使用 Butano 对《木叶战记》进行完全复刻。首先完善已制作的“木叶丸与野蜂”关卡（Scenario 49 / Battle 14）：
1. 在原版 ROM 中使用 mGBA 模拟器遍历所有会产生不同结果的操作并录屏（全帧逐像素截图与录制）。
2. 在 Butano 版中完全重复相同操作并同样录屏。
3. 基于录屏比对总结差异点（包括战斗机制数值与视效表现，如招式特写、攻击动画等）。
4. 修改 Butano 引擎代码与资产，使 Butano 版与原版表现完全一致。
5. 重复上述操作直到 100% 完全复刻原版战斗。
6. 为节约操作开销，在所有会产生差异的操作分支建立快速存档（`.ss9`），便于随时回溯测试其他分支。

---

## 2. 权威基准环境与资产拓扑

- **原版基准 ROM**：`rom/base.gba`
  - SHA-256: `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`
  - 关卡入口存档：`artifacts/runtime-checkpoints/scenario-49-battle-14-entry.ss9`
- **mGBA 权威执行环境**：
  - 二进制：`/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`
  - 脚本驱动支持：Lua API (`callbacks:add("frame", ...)`, `emu:loadStateFile`, `emu:saveStateFile`, `emu:screenshot`, `emu:addKey`, `emu:clearKey`)
- **Butano 工程源码与构建**：
  - 源码根目录：`butano-sequel/`
  - 核心运行时：`butano-sequel/game/src/battle_runtime_scene.cpp`
  - 构建镜像：`devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`
  - 当前交付版本：`butano-sequel/butano-s49-menu-motion-20261013-v5.gba` (SHA-256: `73e534a656c12eaeaf8c12b48327240eb1169c6935be3c42448ea8a2c71ee789`)

---

## 3. S49 战斗全操作分支树与快速存档规划

### 阶段 0：战前任务菜单 (Pre-battle Task Menu)
- 快照：`s49_branch_00_task_menu.ss9`
- 操作选项：
  - 选项 1：队伍·装备
  - 选项 2：查看地图
  - 选项 3：开始任务（推进到部署预览与对白）
  - 选项 4：保存

### 阶段 1：部署与开场对白 (Deployment & Opening Dialogue)
- 快照：`s49_branch_01_dialogue.ss9`
- 触发：按 A 开启对白。
- 演出：鸣人、木叶丸、佐助、小樱对白。

### 阶段 2：第一回合开始（友军移动后玩家回合）
- 原版行为：开场 AI 木叶丸从 `(8,7)` 自动移动至 `(10,7)` 并行动结束，转入灰度色调。
- 快照：`s49_branch_02_turn1_player_start.ss9`（鸣人处于当前激活状态）。

### 阶段 3：角色行动分支 (Unit Action Tree)

#### 分支 A：鸣人 (Naruto)
- 快照：`s49_branch_naruto_start.ss9`
- 移动分支：
  - 选格向右移动至 `(11,7)`（接近野蜂）：快照 `s49_branch_naruto_move_right.ss9`
  - 选格向右移动至宝箱 `(13,5)`（毒草）：快照 `s49_branch_naruto_chest_poison.ss9`
  - 原格待机或移动取消 (B)：快照 `s49_branch_naruto_move_cancel.ss9`
- 行动指令分支（落点确认后）：
  - 指令 1：术·忍具 -> 技能列表
    - 技能 1 (Action 2)：影分身术 (Shadow Clone)
    - 技能 2 (Action 5)：普通体术攻击野蜂 -> 决斗演出、伤害跳字
    - 忍具：十字手里剑攻击野蜂 -> 投掷飞行物、击中结算
  - 指令 2：查克拉 (Chakra Charge)
  - 指令 3：休息 (Rest)
  - 指令 4：行动结束 (Action End)
- 回合末面向与防御：
  - 面向选择（上/下/左/右）
  - 防御确认（是/否）
  - 结算：鸣人完成行动，变为灰度色调。

#### 分支 B：佐助 (Sasuke)
- 切换至佐助：快照 `s49_branch_sasuke_start.ss9`
- 移动与站位：移动至攻击范围。
- 技能分支：
  - 技能：豪火球术 (Fireball / Action 16) -> 特写立绘 Cut-in、火球粒子动画与全屏特效！
  - 体术 / 忍具 / 查克拉 / 休息 / 结束。

#### 分支 C：小樱 (Sakura)
- 切换至小樱：快照 `s49_branch_sakura_start.ss9`
- 技能分支：医疗忍术（给受伤队友回复） / 攻击 / 道具。

#### 分支 D：地图宝箱交互
- 宝箱 1 `(4,4)`：钢材
- 宝箱 2 `(13,5)`：毒草
- 交互流：踩格提示 -> 获取弹窗 -> 道具数量 98->99 -> 宝箱消失。

#### 分支 E：敌方回合（5 只野蜂 AI 行动）
- 野蜂接近与攻击：
  - 野蜂攻击木叶丸 / 鸣人 / 佐助 / 小樱。
  - 决斗画面：固定玩家在左朝右、敌人在右朝左，野蜂使用“蜂刺”攻击。

#### 分支 F：战斗结算分支
- 胜利分支：击杀 5 只野蜂 -> 胜利通告 -> 得分结算（任务分 125 + 战斗分 100 = 225）-> 升级与修行点 -> 推进至 Scenario 50。
- 失败分支：木叶丸死亡或全员阵亡 -> 失败画面 -> 重试/返回。

---

## 4. 当前已定位的差距与修复方向

1. **单位行动完成灰度 (Completed Unit Grayscale Palette)**:
   - 原版：单位（包括木叶丸与玩家角色）行动完成后，调色板通过 ROM `0x13E030` 查找表转化为加权灰度 `(299*R + 587*G + 114*B)/1000`。
   - Butano 当前：行动后依然保持彩色，缺少灰度调色板挂载。
2. **目的格光标与地格动画 (Destination Cursor Animation)**:
   - 原版：4 个距离阶段、44 帧循环的独立 OBJ 角标呼吸动画。
3. **多格移动到达补间 (Multi-tile Movement Tween)**:
   - 原版在多格移动刹车到达时具有细微的像素级反冲补间。
4. **行动菜单与 UI 文字 (Action Menu & HUD Typography)**:
   - SELECT 提示、空格 HUD 显隐、状态详情对齐。
