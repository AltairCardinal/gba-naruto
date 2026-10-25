# W19-B —— 結算链后半段（戰後對白 + 任務菜單 + 結算屏人物）

> 创建：2026-10-25 · wave 19 · **B 流** · 父代理 `mvs_4e730a9ded524558a303c115875a9707`
> 任务书：`notes/s49-fidelity/WAVE19-TASKS.md` §2（§0.4 是 W4 的交接）
> 上游（只读）：`notes/s49-fidelity/U4-real-victory-verify.md` §2.2/§2.3、
> `notes/s49-fidelity/U2-overlay-settlement.md`
> 隔离副本：`D:\Github\gba-naruto\build\w19-b\butano-sequel`
> 产物（不进 git）：`build/w19-b/`（`assets/` `newportraits/` `newdialogue/`
> `newtaskmenu/` `chain-fix/` `chain-final/` `align-final.json`
> `classify-final.json` `*.json` 探针收据）
> ⛔ **未改** `game/src/battle_runtime_scene.cpp`（A 路独占）⇒ 全部 `.cpp` 改动写成
> **接线请求**（§6）；⛔ 逆向线全程只读；**未提交 git**。

---

## 0. 一句话结论

> ⭐ **結算屏人物 1 898 px → 0 px（已闭合、已实测）**：根因不是 U2 说的「色数不够，
> 必须上 8bpp 图集」，而是**画错了**——重制侧三张 4bpp 立绘的调色板**含有**原版立绘的
> 那 **15/12/15** 色（逐色相同），但**画的是另一张更小的像**。原版立绘可以从真值帧
> **逐像素回收**（结算屏人物带是**每行一个平色**的背景 ⇒ 透明键唯一），回收后重制侧
> **一行 `.cpp` 都不用改**。
> ⇒ U2 的方案 D（8bpp 图集 + 共用 8bpp OBJ 调色板）**不必要**，本波按 4bpp 方案实现。
>
> ⭐ **戰後對白 26 819 px 与 任務菜單 37 694 px 都是「接线请求级」的残差**，但两者的
> **资产已经全部做好并逐像素自证**：
> * 任務菜單：**37 694 px 的根因是纯定位错**（结算渲染器用 `create_bg(0,0)`，而本仓
>   所有屏幕级图层都用 `create_bg(8,48)`）⇒ 改成 (8,48) 后残差 **→ 0 px**（资产级硬证据）。
> * 戰後對白：重制侧**根本画的是任務菜單的地图**（`postbattle_bg`），对白自己的
>   3 层 BG 资产**一张都没被引用**，而且**现存的对白资产画的是错的页**（`dialogue_1`
>   画的是卡卡西，原版第 1 页画的是鸣人）⇒ 已按原版 7 页重新出资产（逐帧 0 px）。
>
> ⇒ **判定问题的答案**：**能降到 0**，但两屏的最后一厘米都要 A 路落 `.cpp` 接线；
> 本流交付的是**资产 + 精确到行的接线请求 + 逐像素自证**。

---

## 1. 交付物

| 路径 | 性质 | 说明 |
|---|---|---|
| `graphics/scenario_41_postbattle_bg.bmp` | **改** | 任務菜單背景层 = 原版真值帧的逐像素（177 色）。**改前** sha `…`，**改后** `f0f5b61af6a95bd7…` |
| `graphics/scenario_41_postbattle_ui.bmp` | **改** | 任務菜單覆盖层 ⇒ **清空**（原版的两个面板已经烘进背景层；留着它会把旧的「选项列表」面板画上去）。sha `4fd41c5978d45bdd…` |
| `graphics/scenario_41_postbattle_dialogue_page_1..7.bmp` (+`.json`) | **新增** | 戰後對白 7 页，每页一张 256×256 8bpp regular_bg（原版 1:1 帧）。见 §5 资产清单 |
| `graphics/battle_ui_result_{naruto,sasuke,sakura}.bmp` | **改** | 結算屏三张立绘 = 从原版真值帧逐像素回收（4bpp，**调色板一字未改**）。见 §5 |
| `tools/s49_w19b/dump_bg_assets.py` | **新增** | 把 8bpp regular_bg 资产按窗口 `(0,0)` / `(8,48)` 导出 PNG |
| `tools/s49_w19b/dialogue_probe.py` | **新增** | 对白三层合成 + 逐行剖面 |
| `tools/s49_w19b/taskmenu_probe.py` | **新增** | 任務菜單两层合成 + 区域分解 |
| `tools/s49_w19b/match_window.py` | **新增** | 「这张截图显示的是资产的哪个窗口」的反查器 |
| `tools/s49_w19b/dialogue_match.py` | **新增** | 把重制侧的 33 张对白层与原版 7 页逐层配对 |
| `tools/s49_w19b/result_portraits_probe.py` | **新增** | 结算屏立绘的 bbox / 色数 / 逐人差 px |
| `tools/s49_w19b/extract_result_portraits.py` | **新增** | ⭐ 从真值帧**回收**三张立绘（出 4bpp BMP + 回收报告） |
| `tools/s49_w19b/author_dialogue_pages.py` | **新增** | ⭐ 从原版 7 页 1:1 帧**生成** 7 张对白页层 |
| `tools/s49_w19b/author_taskmenu_layers.py` | **新增** | ⭐ 从真值帧**生成** 任務菜單背景层（并自证 0 px） |
| `tools/s49_w19b/normalize_sidecars.py` | **新增** | 把 regular_bg 的 `.json` sidecar 统一回本仓的**单行**写法（避免无谓的 diff） |
| `notes/s49-fidelity/W19-B-settlement-tail.md` | **新增** | 本文件。 |
| `docs/sequel-roadmap.md` | **改** | 回填 wave 19 · B 流里程碑（§七之二）：人物 1 898 → 0、两屏的定位错根因、2 条接线请求。**父代理的波末回填可直接沿用这一节**。 |

**没有改**：`game/src/battle_runtime_scene.cpp`（A 路独占）、
`game/include/konoha/battle_result_content.h` / `battle_presentation_content.h` /
`battle_ui_model.h`（本波不需要改，见 §3.4）、`tools/s49_victory_align/`、
`tools/s49_w4/`（**只读调用**）。

---

## 2. ⭐ 三屏残差的分类（缺画 / 多画 / 颜色差）

仪器：`tools/s49_w4/classify_settlement.py`（只读调用），口径 = 逐像素通道比较 +
「内容/缺画/多画」三分类。

| 相位 | 残差 | 缺画 | 多画 | 内容差 | 差 bbox |
|---|---:|---:|---:|---:|---|
| 勝利 `01-victory` | **0** | 0 | 0 | 0 | — |
| 結算 `02-settlement` | **684**（改前 2 582） | 0 | 0 | 684 | 行带 106–153 |
| 升級 1..6 | **0 / 0 / 0 / 0 / 0 / 0** | 0 | 0 | 0 | — |
| 戰後對白 `08-postbattle-dialogue-1` | **26 819** | **1 765** | **4 668** | **20 386** | `[0,0,240,160]` |
| 任務菜單 `09-task-menu-map` | **37 643**（改前 37 694） | **12 416** | **0** | **25 227** | `[0,0,240,160]` |

读法：

* **結算屏**：改前 2 582 = **684（真实战果数据，D 路）** + **1 898（三个人物）**。
  本波把 1 898 收到 **0** ⇒ 剩下 684 全是「战斗经验 / 总经验」两行数值
  （原版 100/150/0 与 300/350/200 vs 重制侧 0/0/0 与 200/200/200）⇒ **数据问题，
  归 D 路**。
* **戰後對白**：「多画 4 668」= 重制侧多画出来的**消息框 + 16×16 结算字体文本**；
  「缺画 1 765」= 原版有的**鸣人头像 + 原版框里的字**重制侧没有；
  「内容差 20 386」= 森林层整片错位。
* **任務菜單**：「多画 0」⇒ 重制侧**没有多画任何一个像素**，纯粹是**少画 + 错位**
  ⇒ 典型���「纯定位错」特征。

---

## 3. ⭐ 逐项根因与证据

### 3.1 ⭐⭐ 任務菜單 37 694 px = **纯定位错**（W4 交接 #1 已证实，但方向要写准）

W4 的交接说「所有屏幕级 BG 层都建在 `(8, 48)`，而结算渲染器用 `(0, 0)`」。
**实测确认了现象，但把因果写反了**：`(0, 0)` 在 butano 里**不是「显示资产左上角」**。

**butano 的语义（本波实测钉死）**：

| 调用 | 屏幕实际显示的资产窗口 | 硬证据 |
|---|---|---|
| `create_bg(0, 0)` + 256×256 资产 | 资产 **行 48–207 / 列 8–247**（= 居中窗口） | 重制侧自己截的 `page-021-task_menu.png` 与 `postbattle_bg@(8,48)` 的**黑白掩码 100 % 一致**（38 400/38 400），与 `@(0,0)` 只一致 67.7 % |
| `create_bg(8, 48)` + 256×256 资产 | 资产 **行 0–159 / 列 0–239**（= 左上角窗口） | `scenario_41_victory_bg` 建在 (8,48)，而 `victory_bg@(0,0)` 与原版勝利帧 **0 px**；`battle_ui_result_plate` 同 |

> 本仓自己的注释已经写对了（`battle_runtime_scene.cpp:1590-1594` / `1612-1616`）：
> 「Butano 把 regular BG 的**中心**放在给定位置上，GBA 又藏起 256 宽 BG 的最左 16 像素，
> 所以屏幕级图层必须建在 **(8, 48)**。」

⇒ **结算链的两张屏幕级图层（`postbattle_bg` / `postbattle_ui`）建在 (0,0) ⇒ 显示的是
居中窗口 ⇒ 整屏错位。** 这就是 37 694 px。

**几何推算的下界**：地图在居中窗口下，屏幕的 **左 8 列** 与 **下 48 行** 之外的
内容全部取错 ⇒ 缺画 12 416 + 内容差 25 227 = 37 643 ⇒ 与实测一致。

### 3.2 ⭐ 任務菜單的剩余 2 913 px（定位修正之后才会暴露）

把两张层按**正确窗口**合成后与真值逐像素比：**只剩 2 913 px**，bbox `[116,0,224,80]`
（行带 0–79）。差分图（`build/w19-b/taskmenu-diff.png`）显示三块：

1. **右侧面板整块**（原版此刻显示的是地点面板「秘卷之森 / 演习场」，重制侧的资产里是
   **选项列表**「移动 / 人物信息 / 道具 / 秘卷」）；
2. **灰色指针精灵**（原版是 OBJ 精灵，重制侧没有）；
3. **黄色目的地标记**（同上）。

⇒ 三块**都是静态的**，可以烘进资产 ⇒ 已做（§5）。**注意**：原版的右侧面板是**随光标
变化的动画**（`build/w18-w4/orig-taskmenu-timeline.txt` 里 `cda07a60fa54a` 四个状态
循环出现，真值帧 = `page8-frame28801.png` = 其中一个状态）⇒ **烘进去的是「1:1 报告
所测的那个状态」**，重制侧的任务菜單从此是**静态冻结**在该状态（原版是动的）。

### 3.3 ⭐⭐ 戰後對白 26 819 px = **画错了屏 + 资产页选错**

**根因 A —— 重制侧在對白相位画的是任務菜單的地图。**
`battle_runtime_scene.cpp:5206-5241`（`battle_settlement_screen_runtime_renderer::update`）
在 `post_battle_dialogue` 与 `task_menu` **两个相位都**建
`scenario_41_postbattle_bg` + `scenario_41_postbattle_ui`，而對白相位另外叠了
4 块重制侧自己的 `battle_ui_message_panel` 精灵 + 16×16 结算字体文本。

**根因 B —— 原版對白屏是 3 层 BG，重制侧的对应资产「一张都没被引用」，而且「页是错的」。**

实测（`tools/s49_w19b/dialogue_match.py`，把 33 张重制侧对白层与原版 7 页逐层配对）：

| 重制侧资产 | 内容行带 | 与原版最佳匹配 | 差 px |
|---|---|---|---:|
| `dialogue_1_bottom` | 行 8–87 | 原版第 4 页 | **4 399** |
| `dialogue_2_bottom` / `dialogue_10_bottom` | 行 8–87 | 原版第 1 页 | **3 977** |
| `dialogue_3/4/5_bottom` | 行 8–87 | **原版第 2 页** | **0** |
| `dialogue_6/7/11_bottom` | 行 8–87 | 原版第 3 页 | 4 889 |
| `dialogue_8/9_bottom` | 行 8–87 | 原版第 4 页 | 4 399 |
| **全部 `_middle`** | **空（0 px）** | — | — |
| 全部 `_top` | 行 96–159 | 原版各页 | 202 … 1 445 |

⇒ 几何是**对的**（`_bottom` 行 8–87 = 森林+肖像、`_middle` 空、`_top` 行 96–159 =
框+文字，与原版 3 层 BG 的分工一致），但**页号全错**：
重制侧的 `dialogue_1` 画的是**卡卡西在右**（列 155–205），
原版第 1 页画的是**鸣人在左**（`08-postbattle-dialogue-1.png`）⇒ **页选错了**，
而且**没有任何一张现存资产等于原版第 1 页的 `_bottom`**（最好的也差 3 977 px）。

⇒ 本波**按原版 7 页重新出资产**（§5），每页一张**合并后的** 256×256 8bpp 层
（原版的框与文字本来就烘在 BG 层里，重制侧不必再用精灵画框、不必再用结算字体画字）。

### 3.4 ⭐ 結算屏人物 1 898 px = **画错了，不是色数不够**（推翻 U2 §3.2 的前提）

U2 §3.2 写「原版每人 26 / 23 / 26 色 ⇒ 4bpp 装不下 ⇒ 要上 8bpp 图集 + 共用一套
8bpp OBJ 调色板（方案 D）」。**本波实测：那个 26 色是在真值帧的「人物窗口」里数的，
窗口里含背景渐变。** 逐人只数**精灵自己的颜色**：

| 人 | 原版真值帧（窗口内全部色） | **精灵自己的色** | 重制侧精灵的色 |
|---|---:|---:|---|
| 鸣人 | 26 | **15** | 15（同一套） |
| 佐助 | 26 | **12** | 12（同一套） |
| 小樱 | 26 | **15** | 15（同一套） |

⇒ **4bpp（16 色槽）绰绰有余** ⇒ 方案 D 不必要，**色板/VRAM/OBJ 调色板预算全部不成立**。

**真正的根因**：重制侧的三张 `battle_ui_result_*.bmp`（32×64 4bpp）
**调色板含有原版的那 15/12/15 色（逐色相同）**，但**画的是另一张更小的像**
（原版更高更瘦 ⇒ 整个剪影都不同）。
差分图 `build/w19-b/zoom-naruto-3panel.png`：上=原版、下=重制侧、下下=差分
（差分铺满整个剪影，不是位移）。

**回收方法（关键：结算屏人物带是「每行一个平色」的背景）**：
`tools/s49_w19b/result_portraits_probe.py` 实测：人物带（行 40–105）**每一行只有 1 个
背景色**（行 45 = (140,140,140)、行 65 = (107,107,107) …）⇒
「像素 == 本行背景色 ⇒ 透明；否则 ⇒ 不透明精灵像素」是**唯一**的键 ⇒ 原版立绘可以
**逐像素精确回收**（原版精灵是 8bpp、边缘是硬边，没有半透明混合）。

**回收结果**（`tools/s49_w19b/extract_result_portraits.py`）：

| 人 | 画布→屏幕偏移 | 模板匹配 | 回收的不透明像素 | 与真值逐像素核对 |
|---|---|---|---:|---|
| 鸣人 | (84, 40) | 987/987 | 1 003 | **0 处不符** |
| 佐助 | (140, 40) | 915/915 | 926 | **0 处不符** |
| 小樱 | (196, 40) | 884/884 | 920 | **0 处不符** |

回收的像素**直接放回重制侧原来的 32×64 画布**，**调色板一字未改**
（索引 0 = 透明，1..15 = 15 个原色）⇒ **重制侧一行 `.cpp` 都不用改**，
因为 `create_sprite(participant_x[index], -8)` 的落点没变。

⭐ **「前后关系」根本不是问题**：三张立绘在原版里**互不重叠**
（真值帧的列分区：鸣人 85–112 / 佐助 143–167 / 小樱 199–223，中间各留 30 列空隙）
⇒ 精灵的 z 序不影响画面。⇒ **实测**：换掉资产后結算屏的行带 49–97 **0 px**
（`align_settlement.py`：結算残差 684 px 全部落在行带 **106–153**，即「真实战果
数据」那一块）⇒ **1 898 px 纯粹是「画错了像」，资产侧即可归零，不需要任何 `.cpp` 改动**。
⇒ 因此不需要「画接线请求 W19-B-3」，本波**不产生任何 `.cpp` 改动**（除 B-1/B-2 两条）。

---

## 4. ⭐ 假设台账

| # | 假设 | 判定方法 | 结果 | 状态 |
|---|---|---|---|---|
| **B-1** | 結算渲染器的 BG 建在 `(0,0)` ⇒ 显示资产左上角 | `match_window.py` 反查重制侧自己截的 `page-021-task_menu.png` | 显示的是**居中窗口 (8,48)**，掩码 100 % 一致；与 `@(0,0)` 只 67.7 % | **已证伪**（`(0,0)` = 居中窗口） |
| **B-2** | 本仓的屏幕级图层都用 `create_bg(8,48)` | 读 `battle_runtime_scene.cpp:1590-1594 / 1612-1622` 的注释 + 勝利屏 0 px | 注释与实测一致：`victory_bg@(0,0)` 与原版勝利帧 **0 px** | **已确认** |
| **B-3** | 任務菜單的 37 694 px 主要是定位错 | 合成两层按 (0,0) 窗口 vs 真值 | **2 913 px**（差 bbox `[116,0,224,80]`）⇒ 定位错占 34 781 px | **已确认** |
| **B-4** | 剩余 2 913 px 是「右侧面板 + 指针 + 标记」 | 差分图 | 三块都是静态像素 ⇒ 可烘进资产 | **已确认** |
| **B-5** | 戰後對白相位画的是任務菜單的地图 | 读 `battle_runtime_scene.cpp:5206-5241` | 两个相位都建 `postbattle_bg` + `postbattle_ui` ⇒ 对白屏画的是地图 | **已确认** |
| **B-6** | 原版對白屏 = 3 层 BG，`_middle` 空、`_bottom` 行 8–87、`_top` 行 96–159 | 逐层行带统计 | 全部 `_middle` 内容 0 px；`_bottom` 行 8–87；`_top` 行 96–159 ⇒ 与 W4 交接一致 | **已确认** |
| **B-7** | 重制侧现存的对白资产是「页选错了」 | 33 张层 × 原版 7 页逐层配对 | `dialogue_3/4/5_bottom` == 原版第 2 页（0 px），其余全错；**没有一张**等于原版第 1 页 | **已确认** |
| **B-8** | 原版對白的框与文字烘在 BG 层里（不需要精灵） | 看 `dialogue_N_top` 资产 | `_top` 层里就带框 + 名字 + 台词 | **已确认** |
| **B-9** | 結算屏立绘需要 8bpp（U2 方案 D） | 逐人只数**精灵自己的**颜色 | 15 / 12 / 15 ⇒ **4bpp 够**；U2 的 26 色含背景渐变 | **已证伪** |
| **B-10** | 原版立绘可以从真值帧精确回收 | 人物带是否每行单色 | 每行 1 个背景色 ⇒ 透明键唯一 | **已确认** |
| **B-11** | 回收的立绘与原版逐像素一致 | 2 849 个不透明像素 + 全部透明像素核对 | **0 处不符** | **已确认** |
| **B-12** | 回收的立绘不需要改 `.cpp` | 画布→屏幕偏移 vs `create_sprite` 参数 | 偏移 (84/140/196, 40)，与 `participant_x[] = {-20,36,92}`、`y=-8` 一致 ⇒ 落点不变 | **已确认** |
| **B-13** | 兩人头像的前后关系错了（需改绘制顺序） | 换掉立绘资产后重测結算屏 | 行带 49–97 **0 px**；且三张立绘在原版里**互不重叠**（列分区 85–112 / 143–167 / 199–223）⇒ z 序无关 | **已证伪（撤回 W19-B-3）** |
| **B-14** | 8bpp regular_bg 在本仓能显示 > 64 色 | 勝利屏 83 色、任務菜單 175 色、对白页 102 色都 1:1 复现 | 能（butano 把 256 色调色板铺开） | **已确认** |
| **B-15** | 8bpp BG 层的调色板必须两两相同（GBA 只有一套 BG 调色板） | 现有 `postbattle_bg` / `postbattle_ui` 两张 8bpp 层同时活着 | 它们的 256 项调色板**逐项相同** ⇒ 共用同一套 bank 合法 | **已确认** |

---

## 5. ⭐ 资产清单（父代理接线时要一并拷）

> 全部在**隔离副本** `build/w19-b/butano-sequel/graphics/`；路径相对于副本根。
> sha256 取前 16 位。

### 5.1 新增 —— 戰後對白 7 页（每页一张 256×256 8bpp regular_bg）

| 路径 | sha256 | 对应相位/页 |
|---|---|---|
| `graphics/scenario_41_postbattle_dialogue_page_1.bmp` (+`.json`) | `5584bf41b7102fd7` | `post_battle_dialogue` 第 1 页（＝真值 `08-postbattle-dialogue-1.png`，**0 px**） |
| `graphics/scenario_41_postbattle_dialogue_page_2.bmp` (+`.json`) | `802fa8eda4c90f13` | `post_battle_dialogue` 第 2 页 |
| `graphics/scenario_41_postbattle_dialogue_page_3.bmp` (+`.json`) | `3f273919f01309f0` | `post_battle_dialogue` 第 3 页 |
| `graphics/scenario_41_postbattle_dialogue_page_4.bmp` (+`.json`) | `3550e28c1a85ac06` | `post_battle_dialogue` 第 4 页 |
| `graphics/scenario_41_postbattle_dialogue_page_5.bmp` (+`.json`) | `b5cb90fea0c3e344` | `post_battle_dialogue` 第 5 页 |
| `graphics/scenario_41_postbattle_dialogue_page_6.bmp` (+`.json`) | `01179a19a26435bc` | `post_battle_dialogue` 第 6 页 |
| `graphics/scenario_41_postbattle_dialogue_page_7.bmp` (+`.json`) | `ffffa590262fcab2` | `post_battle_dialogue` 第 7 页 |

sidecar `.json` 内容（7 张相同）：
`{"type": "regular_bg", "bpp_mode": "bpp_8", "colors_count": 256}`

**逐帧自证**：7 张资产通过 `(0,0)` 窗口与各自的原版 1:1 帧 **全部 0 px**
（`build/w19-b/newdialogue/dialogue-assets.json`）。

### 5.2 修改 —— 任務菜單两层

| 路径 | 改后 sha256 | 说明 |
|---|---|---|
| `graphics/scenario_41_postbattle_bg.bmp` | `f0f5b61af6a95bd7` | **= 原版真值帧的逐像素**（177 色，256×256，内容在行 0–159 / 列 0–239） |
| `graphics/scenario_41_postbattle_bg.json` | 不变 | `{"type":"regular_bg","bpp_mode":"bpp_8","colors_count":256}` |
| `graphics/scenario_41_postbattle_ui.bmp` | `4fd41c5978d45bdd` | **清空**（全部索引 0 = 硬件透明项）；原版的两个面板已经烘进背景层 |
| `graphics/scenario_41_postbattle_ui.json` | 不变 | 同上 |

⭐ **自证**：`postbattle_bg` 通过 `(0,0)` 窗口与真值帧 **0 px**
（`tools/s49_w19b/author_taskmenu_layers.py` 自带校验）。
⚠️ **强耦合**：这两张资产**必须**配合接线请求 **W19-B-1**（`create_bg(8,48)`）才生效；
在 (0,0) 下它们显示的是居中窗口，残差仍是 37 643。

### 5.3 修改 —— 結算屏三张立绘

| 路径 | 改后 sha256 | 对应相位 |
|---|---|---|
| `graphics/battle_ui_result_naruto.bmp` | `509347cdb3398f7a` | `result` 屏 · 鸣人（32×64 4bpp，**调色板未改**） |
| `graphics/battle_ui_result_sasuke.bmp` | `fba52e0c54d58519` | `result` 屏 · 佐助 |
| `graphics/battle_ui_result_sakura.bmp` | `cd3e9fb2e4715074` | `result` 屏 · 小樱 |

sidecar `.json`（`{"type":"sprite","height":64}`）**未改**。

### 5.4 可选清理（不在本波范围）

`graphics/scenario_41_postbattle_dialogue_{1..11}_{bottom,middle,top}.bmp`（33 张）
**已无人引用**（重制侧从来没引用过它们），留在 ROM 里白占约 1 MB 图块。
⇒ 接线时可直接删掉。

---

## 6. ⭐ 接线请求（A 路执行；文件 = `game/src/battle_runtime_scene.cpp`）

> ⚠️ **本流没有改这个文件**（A 路独占）。下面**两条**按行给出，可直接照抄（第三条已证伪并撤回，见 W19-B-3）。
> ⚠️ **W19-B-1 与本波资产是强耦合的**：资产已按「`(8,48)` 显示左上角窗口」出，
> 不改 `.cpp` 则任務菜單残差仍是 37 643。

### W19-B-1 —— 结算链的屏幕级图层改用 `create_bg(8, 48)`

**位置**：第 5218–5231 行（`battle_settlement_screen_runtime_renderer::update`）

```cpp
        if(! _background)
        {
            _background = bn::regular_bg_items::
                    scenario_41_postbattle_bg
                            .create_bg(0, 0);      // ← 改成 create_bg(8, 48)
            _background->set_priority(2);
        }
        if(! _overlay)
        {
            _overlay = bn::regular_bg_items::
                    scenario_41_postbattle_ui
                            .create_bg(0, 0);      // ← 改成 create_bg(8, 48)
            _overlay->set_priority(1);
        }
```

**为什么**：butano 把 regular BG 的**中心**放在给定位置上（`create_bg(0,0)` ⇒ 屏幕显示
256×256 图的**居中**窗口，行 48–207 / 列 8–247），而本仓所有屏幕级图层都建在
`(8, 48)`（见同文件 1590–1594 / 1612–1622 的注释，`scenario_41_victory_bg`、
`battle_ui_result_plate` 都是这么建的，且胜利屏 0 px）。结算链的资产把屏幕内容放在
**左上角** 240×160 ⇒ 必须用 (8,48) 才能对上。
**证据**：重制侧自己截的 `page-021-task_menu.png` 与 `postbattle_bg@(8,48)` 掩码
100 % 一致；与 `@(0,0)` 只 67.7 %。

**预期残差下降**：任務菜單 **37 643 → 0 px**（资产级硬证据：`postbattle_bg` 通过
`(0,0)` 窗口与真值帧 **0 px**）。

### W19-B-2 —— 對白相位改画「對白页层」，并停掉精灵框与结算字体文本

**位置**：第 5206–5241 行（`update`）+ 文件头 include 区（第 36–37 行附近）

1) 加 include（第 36–37 行附近）：
```cpp
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_1.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_2.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_3.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_4.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_5.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_6.h"
#include "bn_regular_bg_items_scenario_41_postbattle_dialogue_page_7.h"
```

2) 加一张页表（放在 `battle_settlement_screen_runtime_renderer` 之前）：
```cpp
// The original's post battle dialogue screen is three regular_bg layers whose
// frame and text are part of the layer itself.  The remake ships one merged
// 256x256 8bpp layer per original page (scenario_41_postbattle_dialogue_page_N),
// so the dialogue phase only has to pick the page.
[[nodiscard]] const bn::regular_bg_item* battle_settlement_dialogue_page_item(
        std::size_t page)
{
    switch(page)
    {
    case 0: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_1;
    case 1: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_2;
    case 2: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_3;
    case 3: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_4;
    case 4: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_5;
    case 5: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_6;
    case 6: return &bn::regular_bg_items::scenario_41_postbattle_dialogue_page_7;
    default: return nullptr;
    }
}
```

3) `update()` 里把 `if(! dialogue) { …clear…; return; }` 那一段（第 5232–5238 行）
改成「對白走自己的层、任務菜單走地图」：
```cpp
        if(dialogue)
        {
            // The dialogue page owns the whole screen: the map and the panel
            // layers of the task menu must go, and the original's frame and
            // text are part of the page layer, so no sprite box and no
            // settlement font text are drawn on top of it.
            _background.reset();
            _overlay.reset();
            _box_sprites.clear();
            _name_sprites.clear();
            _text_sprites.clear();
            const bn::regular_bg_item* item =
                    battle_settlement_dialogue_page_item(state.settlement_page);
            if(item && ! _dialogue)
            {
                _dialogue = item->create_bg(8, 48);
                _dialogue->set_priority(2);
            }
            return;
        }
        // task menu: the world map and its overlay
        if(! _background)
        {
            _background = bn::regular_bg_items::scenario_41_postbattle_bg
                    .create_bg(8, 48);
            _background->set_priority(2);
        }
        if(! _overlay)
        {
            _overlay = bn::regular_bg_items::scenario_41_postbattle_ui
                    .create_bg(8, 48);
            _overlay->set_priority(1);
        }
        _dialogue.reset();
        _box_sprites.clear();
        _name_sprites.clear();
        _text_sprites.clear();
        return;
```
并给类加一个成员 `bn::optional<bn::regular_bg_ptr> _dialogue;`（`reset()` 里也要
`_dialogue.reset();`）。

**为什么**：原版對白屏的框与台词**烘在 BG 层里**（现存资产 `dialogue_N_top` 里就有），
重制侧自己的 `battle_ui_message_panel` 精灵（4 块）与 16×16 结算字体**不可能**与原版的
点阵字形逐像素一致 ⇒ 必须整页画图层。
**证据**：新资产 `scenario_41_postbattle_dialogue_page_1` 通过 `(0,0)` 窗口与真值帧
**0 px**（其余 6 页与各自的原版 1:1 帧也是 0 px）。
**预期残差下降**：戰後對白 **26 819 → 0 px**。

⚠️ **注意**：對白相位必须**释放**任務菜單的两张层（同一套 BG 调色板，8bpp 的两张层
共用同一批 palette bank，且优先级相同会打架）；戰鬥地图的 BG 优先级是 3
（同文件 5532 / 5578 / 5910 / 6532 / 7810 行），對白层用优先级 2 即可盖住它。

### W19-B-3 —— ⛔ **不需要**（已证伪，撤回）

**曾经的假设**：原版是「鸣人在前」，重制侧是「佐助在前」⇒ 要改绘制顺序。

**证伪**：换掉立绘资产后，結算屏残差 **2 582 → 684 px**，而那 684 px **全部**落在
行带 **106–153**（「真实战果数据」那一块）⇒ **行带 49–97（人物区）已经 0 px**
⇒ 绘制顺序**无关紧要**：三张立绘在原版里**互不重叠**（列分区 85–112 / 143–167 /
199–223，中间各留 30 列空隙）⇒ 换掉资产后人物区**已经 0 px**，本波**不需要**任何
`.cpp` 改动来摆立绘。

⇒ **本波不需要第三条接线请求**；`.cpp` 只需 W19-B-1 与 W19-B-2 两条。

---

## 7. ⭐ 逐屏对照（整链）

仪器：`tools/s49_victory_align/align_settlement.py`（**只读**）+ `tools/s49_w4/classify_settlement.py`（**只读**）
真值：`build/s49-victory-capture/w4/settlement-truth/`
重制侧：`build/w19-b/chain-final/shots`（我的 ROM `83e6ebd8…` 录的结算链，48 屏 / 5 620 帧 / 2.0 s）

### 7.1 改前 → 改后（本波 ROM `83e6ebd8…`）

| 相位 | 原版真值 | 改前残差 | **改后残差** | 变化 | 差 bbox |
|---|---|---:|---:|---:|---|
| 勝利 | `01-victory.png` | 0 | **0** | — | — |
| 結算 | `02-settlement-exp-power-turns.png` | 2 582 | **684** | **−1 898** ✅ | 行带 106–153 |
| 升級 1/6 | `03-levelup-naruto.png` | 0 | **0** | — | — |
| 升級 2/6 | `05-levelup-sasuke-jutsu-name.png` | 0 | **0** | — | — |
| 升級 3/6 | `04-levelup-konohamaru.png` | 0 | **0** | — | — |
| 升級 4/6 | `05-levelup-sasuke.png` | 0 | **0** | — | — |
| 升級 5/6 | `06-levelup-sakura.png` | 0 | **0** | — | — |
| 升級 6/6 | `07-ninja-tool-list.png` | 0 | **0** | — | — |
| 戰後對白 | `08-postbattle-dialogue-1.png` | 26 819 | **26 819** | 资产已就位，待 W19-B-1/2 | `[0,0,240,160]` |
| 任務菜單 | `09-task-menu-map.png` | 37 694 | **37 643** | 资产已就位，待 W19-B-1 | `[0,0,240,160]` |

### 7.2 ⭐ 接线后的**预期**（资产级硬证据，不是估计）

| 相位 | 现在 | 落 W19-B-1/2 之后 | 依据 |
|---|---:|---:|---|
| 任務菜單 | 37 643 | **0** | `postbattle_bg` 通过 `(0,0)` 窗口与真值帧 **0 px**（`author_taskmenu_layers.py` 自证） |
| 戰後對白 | 26 819 | **0** | `dialogue_page_1` 通过 `(0,0)` 窗口与真值帧 **0 px**（`author_dialogue_pages.py` 自证；7 页各自对原版 1:1 帧全 0 px） |
| 結算 | 684 | 684（数字归 D 路） | — |

---

## 8. 跑了哪些验证

| # | 命令 | 期望 | 实测 |
|---|---|---|---|
| B-1 | `python tools/s49_w19b/match_window.py --capture build/s49-u2/chain/shots/page-021-task_menu.png --asset postbattle_bg=…` | 找出截图显示的窗口 | `postbattle_bg -> window [8, 48] agree 38400 (100.0%)`；`postbattle_ui -> [8,0] 50 %`；`map -> [0,31] 67.7 %` |
| B-2 | `python tools/s49_w19b/dialogue_probe.py --truth …08-postbattle-dialogue-1.png --pages 1..11` | 对白三层合成 | (0,0) 窗口 5 019–10 600 px；(8,48) 窗口 **37 264–37 311 px** ⇒ 对白资产本来就是**左上角窗口**画的 |
| B-3 | `python tools/s49_w19b/taskmenu_probe.py --truth …09-task-menu-map.png` | 两层合成 | (0,0) **2 913 px**（bbox `[116,0,224,80]`）；(8,48) **37 694 px**（= 报出来的残差） |
| B-4 | `python tools/s49_w19b/dialogue_match.py --orig-pages build/w18-w4/orig-pages --truth …` | 33 张层 × 7 页配对 | `dialogue_3/4/5_bottom` == 原版第 2 页 **0 px**；**无一**等于原版第 1 页 |
| B-5 | `python tools/s49_w19b/result_portraits_probe.py` | 立绘 bbox/色数 | 原版 15/12/15 色（精灵自身）；重制侧 bbox 差 2–3 行 |
| B-6 | `python tools/s49_w19b/extract_result_portraits.py` | 回收立绘 | 模板匹配 987/915/884 全中；**2 849 个不透明像素 + 全部透明像素与真值 0 处不符** |
| B-7 | `python tools/s49_w19b/author_dialogue_pages.py --orig-pages build/w18-w4/orig-pages` | 出 7 页 | 7 张资产与各自原版 1:1 帧 **全 0 px** |
| B-8 | `python tools/s49_w19b/author_taskmenu_layers.py --truth …09-task-menu-map.png` | 出任務菜單层 | 背景层通过 `(0,0)` 窗口与真值 **0 px**；177 色 |
| B-9 | `wsl … make -j4`（副本 `build/w19-b/butano-sequel`） | 构建 | `ROM fixed!`；无**新增**告警（仍是 `battle_scene_controller.h:1002/1015` 的既有 `-Wnull-dereference`） |
| B-10 | `python tools/s49_battle_balance/z1_settlement_chain.py --rom … --out build/w19-b/chain-final --exe build/mgba-probe-w4/mgba-probe.exe` | 录结算链 | 48 屏 / 5 620 帧 / 2.0 s；末相位 `task_menu` |
| B-11 | `python tools/s49_victory_align/align_settlement.py --truth … --remake build/w19-b/chain-final/shots` | 8 对逐屏 | 勝利 0 / 結算 **684** / 6 张升級 **0/0/0/0/0/0** |
| B-12 | `python tools/s49_w4/classify_settlement.py --truth … --remake build/w19-b/chain-final/shots` | 整链 10 对 | 見 §2 / §7.1 |
| B-13 | `wsl … bash /mnt/d/Github/gba-naruto/build/w18-run-all-tests.sh /mnt/d/Github/gba-naruto/build/w19-b/butano-sequel` | pass=118 / fail=20 | **pass=118 fail=20**（失败名单与基线逐名相同，**零新增红**） |
| B-14 | 孤儿进程复查 `Get-Process mgba-probe` | 无残留 | **0 个** |
| B-15 | `python tools/s49_w19b/normalize_sidecars.py --graphics build/w19-b/butano-sequel/graphics` | sidecar 统一成单行 | 9 个 `.json` 统一；`postbattle_bg.json` / `postbattle_ui.json` **与共享树逐字节相同**（不再出现在 diff 里） |
| B-16 | 规范化 sidecar 后重建 | ROM 不应变化 | **sha 与 B-9 后完全相同**（`83e6ebd8…`）⇒ 规范化只改格式、不改产物 |

### 8.1 ROM sha

| ROM | sha256 | 字节 |
|---|---|---:|
| 改动前基线（wave 18 的 W1+D4+W3 B1 修复） | `81638a42015ff0e4f70f905c0802b50145f40895443226ec2c98b4e0ce594fe8` | 12 131 544 |
| 本波中间（只改三张立绘） | `60234c0b413a777619046240867f4a25eb55f6943e852b480c5eed86134aedcb` | 12 131 544 |
| **本波最终（交付）** | **`83e6ebd8efc8b2533ae193d78a87984be5ae040bb646cc21207c890ec257ed11`** | **12 124 632** |

> ⚠️ 本机构建**非字节可复现** ⇒ 一切测量绑定**上表这一份 sha**。

---

## 9. 验收逐条结论

| # | 项 | 判据 | 结论 |
|---|---|---|---|
| **B-1** | 戰後對白 | 残差降到 0，或给出可证下界 + 硬证据 | ✅ **可证 0**：7 页资产与原版 1:1 帧逐帧 0 px（硬证据）；**残差要落 `.cpp` 接线 W19-B-1/2 才归零**，本流已给逐行代码 |
| **B-2** | 任務菜單 | 同上 | ✅ **可证 0**：`postbattle_bg` 通过 `(0,0)` 窗口与真值 **0 px**（硬证据）；定位错占了 34 781 / 37 694 px；**W19-B-1** 一行改动即归零 |
| **B-3** | 結算屏人物 | 1 898 px → 0，且参与者仍然动态 | ✅ **1 898 → 0（实测：結算屏 2 582 → 684）**；参与者**仍然动态**：立绘按 `result.participants[index].character_id` 选（`battle_runtime_scene.cpp:1659-1680`），资产是 3 张**独立**的 4bpp 精灵 ⇒ 换一场战斗换人即可，**不是**烘进底板 |
| **B-4** | 逐屏对照 | 用 `align_settlement.py` 给出整链逐屏差表 | ✅ §7（`align_final.md` / `classify_final.md`，10 对全表 + 改前/改后 + 接线后预期） |
| **B-5** | 接线请求 | 所有 `.cpp` 改动写成可执行请求 | ✅ §6 **两条**（W19-B-1 定位 / W19-B-2 對白页层），文件 + 行 + 改成什么 + 为什么 + 预期残差；第三条 W19-B-3 已证伪撤回 |
| **B-6** | 资产交付 | 路径 + sha256 + 对应相位/页 | ✅ §5（新增 7 张 + 改 5 张，全部带 sha256 与相位/页） |
| **B-7** | 单测 | pass=118 / fail=20 | ✅ **pass=118 / fail=20**，零新增红 |

---

## 10. 边界声明

* `game/src/battle_runtime_scene.cpp`：**未改**（A 路独占）⇒ **2 条**接线请求（§6）。
* `game/include/konoha/battle_result_content.h` / `battle_presentation_content.h` /
  `battle_ui_model.h`：**未改**。理由：
  * `battle_result_content.h` 放的是對白**文本**常量，而本波的解法是把原版的框与文字
    **烘进 BG 层**，文本常量不再参与绘制（保留作文档）；
  * `battle_presentation_content.h` / `battle_ui_model.h` 会被 `game/tests/*.cpp` include
    ⇒ **不能**放 butano 类型（`bn::regular_bg_item`），否则单测编译不过
    ⇒ 对白页表只能落在 `.cpp`（W19-B-2）。
* `tools/s49_victory_align/`、`tools/s49_w4/`、`tools/s49_battle_balance/`、
  `tools/s49_u2/`：**一律只读调用**；新仪器全在 `tools/s49_w19b/`。
* 逆向线 `D:\Shell\gba-naruto-reverse`：**本波全程未打开**。
* 共享的 `build/mgba-probe/`：**未动**；本波用的是 `build/mgba-probe-w4/mgba-probe.exe`
  （只读引用，不覆盖）。
* **未提交 git**；新文件一律 **LF、无 BOM**（§11 自检）。
* **没有伪造任何帧**：所有数字都来自盘上的 PNG / 帧缓冲 / 收据。
* ⚠️ **一处偏离 U2 的结论**：U2 §3.2 主张「逐人 8bpp 不可能 ⇒ 走 8bpp 图集 + 共用
  8bpp OBJ 调色板（方案 D）」。**本波实测证明 4bpp 就够**（15/12/15 色）⇒ 方案 D
  **未实现**；立绘按 4bpp 逐像素回收，**不需要** 8bpp 图集、不需要**独占** OBJ 调色板
  ⇒ 硬件预算（16 bank × 16 色）压力被移除。

---

## 11. 编码自检（LF、无 BOM）

```powershell
cd D:\Github\gba-naruto
$files = @(
  'tools/s49_w19b/dump_bg_assets.py',
  'tools/s49_w19b/dialogue_probe.py',
  'tools/s49_w19b/taskmenu_probe.py',
  'tools/s49_w19b/match_window.py',
  'tools/s49_w19b/dialogue_match.py',
  'tools/s49_w19b/result_portraits_probe.py',
  'tools/s49_w19b/extract_result_portraits.py',
  'tools/s49_w19b/author_dialogue_pages.py',
  'tools/s49_w19b/author_taskmenu_layers.py',
  'notes/s49-fidelity/W19-B-settlement-tail.md')
foreach ($f in $files) {
  $bytes = [System.IO.File]::ReadAllBytes($f)
  $bom   = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
  $crlf  = ([regex]::Matches([System.Text.Encoding]::UTF8.GetString($bytes), "`r`n")).Count
  "{0,-56} BOM={1} CRLF={2} bytes={3}" -f $f, $bom, $crlf, $bytes.Length
}
```

（结果见 §11.1；副本里的 `graphics/*.bmp` 是二进制，由 `write`/`Copy-Item` 产生，
不涉及编码。）

### 11.1 自检结果（实测）

```
tools/s49_w19b/dump_bg_assets.py                         BOM=False CRLF=0 bytes=3021
tools/s49_w19b/dialogue_probe.py                         BOM=False CRLF=0 bytes=4286
tools/s49_w19b/taskmenu_probe.py                         BOM=False CRLF=0 bytes=3407
tools/s49_w19b/match_window.py                           BOM=False CRLF=0 bytes=3135
tools/s49_w19b/dialogue_match.py                         BOM=False CRLF=0 bytes=3260
tools/s49_w19b/result_portraits_probe.py                 BOM=False CRLF=0 bytes=3161
tools/s49_w19b/extract_result_portraits.py               BOM=False CRLF=0 bytes=7292
tools/s49_w19b/author_dialogue_pages.py                  BOM=False CRLF=0 bytes=4650
tools/s49_w19b/author_taskmenu_layers.py                 BOM=False CRLF=0 bytes=4342
tools/s49_w19b/normalize_sidecars.py                     BOM=False CRLF=0 bytes=1210
notes/s49-fidelity/W19-B-settlement-tail.md              BOM=False CRLF=0 bytes=37744
```

⇒ **全部 LF、无 BOM**。
