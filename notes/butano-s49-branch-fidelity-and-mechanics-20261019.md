# Butano S49 (木叶丸与野蜂) 分支保真度与交互时序收敛报告

**日期**: 2026-10-19  
**阶段**: S49 关卡全12分支操作遍历收束与像素级复刻进展  
**基准 ROM**: `rom/base.gba` (`1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`)  
**目标工程**: `butano-sequel/` (`butano-sequel.gba`)

---

## 1. 本轮关键机制逆向与实现成果

### 1.1 休息（Rest）与行动结束（Action End）的流向解耦
- **原版逆向发现**:
  - `行动结束`: 玩家确认面向后，**必须**进入防御/回避决策弹窗（`使用防御·回避系的 术·忍具吗？ 是 / 否`），且此时光标默认落在“否”；底部状态栏显示红色 `结束` 徽标。
  - `休息`: 玩家在菜单项按下 A 时已先弹出确认窗口（`可以吗？ 是 / 否`）。面向选择完成后，**直接结束回合进入待机**，完全跳过防御决策弹窗；底部状态栏显示紫色 `待机` 徽标，鸣人身上出现四向防御箭头。
- **Butano 修复代码**:
  - `butano-sequel/game/include/konoha/battle_scene_controller.h:819-835`:
    在 `facing_selection` 完成时判定 `_runtime.player_snapshot().selected_command == battle_command_type::rest`，若为 `rest` 则直接触发 `_finish_player(_runtime.complete_without_defense())`。
  - 默认光标修正：初始化 `_defense_confirmation_yes = false;`，使弹窗默认选中“否”，消除了第 5 分支 80~120 帧光标左右倒置的 24 像素差异。
  - 彻底消除了第 10 分支（`10_in_place_rest`）在 115..150 帧多余弹出防御框产生的 8,956 差异像素。

### 1.2 底部状态栏徽标状态机对齐
- **原版逆向发现**:
  - 在选择防御决策（`battle_scene_phase::defense_decision`）及防御忍术选择（`defense_selection`）期间，右侧单位状态标记为红色 `结束`（`battle_ui_status_end`），而非待机。
- **Butano 修复代码**:
  - `butano-sequel/game/src/battle_runtime_scene.cpp:3440-3460`:
    更新状态判定条件：
    ```cpp
    if(unit->completed || state.phase == battle_scene_phase::defense_decision || state.phase == battle_scene_phase::defense_selection)
    {
        // 渲染红色 "结束"
    }
    ```
  - 使 `05_action_end_facing_defense` 的帧 120 达成 99.64% 的像素匹配。

### 1.3 查克拉蓄积（Branch 09）原版机制与字形逆向实现
- **原版逆向发现**:
  - 鸣人第一回合查克拉已满（5/5），选择 `查克拉` 并未置灰禁用。
  - 按 A 后在屏幕 `(64, 40)` 弹出一块 112x48 像素的不透明羊皮纸弹窗（`battle_ui_large_dialog_panel`），提示：
    `不能再蓄积查克拉了`
  - 文本真实字形位置（从 `original/09_in_place_chakra/frame-050.png` 提取）：
    - 字符集：`不`、`能`、`再`、`蓄`、`积`、`查`、`克`、`拉`、`了`
    - 字模特征：8x16 2bpp 像素位图。直接从原版逐像素抓取，无损接入 `battle_ui_font.bmp`（追加 `蓄` y=7920, `积` y=7936, `了` y=7952，原位修补其余字形）。
  - 在帧 70 按 A/B 键关闭提示框后，菜单光标被重置回索引 0（`移动`）。
  - 在帧 95 再次按 A 打开移动地格（帧 98..140）。
- **已闭环工程实现**:
  - 状态流向：在 `battle_scene_controller.h:1807-1825` 判定 `unit->chakra >= unit->max_chakra`，不进入拒斥也不直接加查克拉，而是进入 `chakra_selection`（展示弹窗）；按下 A/B 键关闭提示并复位光标到 0（移动）。
  - 渲染对齐：在 `battle_ui_model.h` 设置 `show_large_dialog_panel = true`；在 `battle_runtime_scene.cpp:4030-4040` 渲染 `"不能再蓄积查克拉了"` 文本，屏幕坐标严格对齐 `(72, 48)`。
  - **成效**：分支 09 平均匹配度从 **74.12% 暴涨至 91.73%**，峰值达 **99.06%**！

### 1.4 术·忍具菜单（Branch 06）过渡时序逆向
- **原版逆向发现**:
  - 帧 10 按 A 确认 `术·忍具`。
  - 帧 12 5指令主菜单消失。
  - 帧 12~17（连续 6 帧）：全屏仅显示裸地图与底部状态栏（无菜单窗口）。
  - 帧 18：术列表窗口弹出，与 Butano 术列表像素吻合度高达 99.86%（仅 55 差异像素）。
- **时序差距分析与待接入修复方案**:
  - Butano 术列表弹出未包含这 6 帧空白地图过渡。
  - 修复逻辑：在 `battle_runtime_scene.cpp` 的 `action_menu_delay_frames` 设置为 6，并在倒计时结束时触发重绘。

---

## 2. 自动化比对最新评测数据 (2026-10-19)

基于极速无头回放器 `tools/butano/record_s49_butano_tree.py` 与 `tools/butano/compare_all_s49_branches.py`：

| 分支编号与名称 | 总帧数 | 平均匹配度 | 峰值匹配度 | 最低帧匹配度 | 状态与关键突破 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `01_naruto_menu` | 64 | **97.12%** | **99.15%** | 85.99% | 主菜单 5 指令框与底部面板 **100.00% 零差异** (全屏仅60差异像素) |
| `01_menu_cancel_b` | 50 | **97.58%** | **99.06%** | 87.57% | B 键丝滑取消回退地图 |
| `02_move_selection` | 64 | **91.46%** | **99.06%** | 37.94% | 移动高亮范围展现 |
| `03_move_right_11_7` | 64 | **84.96%** | **92.67%** | 82.02% | 角色单格右移位移与补间 |
| `04_confirm_move_11_7` | 80 | **90.77%** | **99.38%** | 82.36% | 到达新地格并再次呼出行动菜单 |
| `04_cancel_move_to_menu` | 50 | **93.48%** | **98.66%** | 82.36% | B 键取消移动复位 |
| `05_action_end_facing_defense`| 130 | **96.66%** | **99.64%** | 76.60% | 修正默认“否”与红色“结束”状态后大幅提升 |
| `06_jutsu_menu` | 60 | **74.95%** | **98.15%** | 20.00% | 术·忍具列表窗口完美命中，待接入 6 帧过渡空白 |
| `07_shadow_clone` | 140 | **83.61%** | **95.64%** | 20.00% | 影分身特写画面 |
| `08_normal_attack` | 200 | **88.18%** | **98.08%** | 9.51% | 普通攻击决斗动画 |
| `09_in_place_chakra` | 140 | **91.73%** | **99.06%** | 35.31% | **已实现满查克拉弹窗与光标复位，均值自 74.12% 跃升至 91.73%** |
| `10_in_place_rest` | 150 | **79.60%** | **99.90%** | 26.39% | 彻底剔除多余防御弹窗，峰值达 99.90% (全屏仅38差异像素) |

---

## 3. 关键资产与可复现工具链

- **极速全分支录制工具**:
  - `tools/butano/record_s49_butano_tree.py`: 11秒内全量执行 1,292 帧无头录屏，并在所有 12 个关键分叉点生成 `.ss9` 快速存档。
- **全分支像素比较工具**:
  - `tools/butano/compare_all_s49_branches.py`: 逐帧无遮罩 240x160 RGB 差异比对，输出峰值/均值指标与 `artifacts/s49-branches/reports/summary.json`。
- **重构构建与启动脚本**:
  - `./tools/butano/build.sh butano-sequel`: Docker 容器内高效增量编译。
  - `python3 tools/butano/boot_butano_to_turn1.py`: 自动跳过开场剧情，生成严格对齐原版镜头稳定态的 `turn1_start.ss9`。
- **关键头文件与实现**:
  - `butano-sequel/game/include/konoha/battle_scene_controller.h`: 控制器状态机流向解耦。
  - `butano-sequel/game/src/battle_runtime_scene.cpp`: 渲染层徽标与 HUD 刷新。
  - `butano-sequel/game/include/konoha/battle_ui_sprite_font.h`: 8px 格点标点修正。
  - `butano-sequel/graphics/battle_ui_status_labels.bmp`: 零差异 32x16 属性标签图集。
  - `butano-sequel/graphics/battle_ui_font.bmp`: 8x16 真实字形图集（已补充 `不能再蓄积查克拉了` 原版采样字模）。

---

## 4. 下一步行动项建议

1. **分支 06 6帧过渡空白期接入**:
   - 在主菜单消失后至子菜单弹出前，增加 6 帧的纯地图过渡延迟，彻底解决前 18 帧的时序偏差。
2. **鸣人护额调色板索引对齐**:
   - 确保 `battle_ui_font.bmp` 与角色 OBJ 调色板不产生动态索引冲突，消除主菜单第 28 帧护额 `(0, 173, 173)` 与 `(0, 189, 189)` 的 60 像素差异。
3. **分支 03 角色位移与补间**:
   - 精细对齐鸣人向右移动 1 格（(10, 7) -> (11, 7)）过程中 16px 位移的步进速度与动画帧节奏。
