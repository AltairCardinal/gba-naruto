# S49 战场单位「逐帧重绘」的真实机制（2026-10-20）

## 0. 一句话结论

原版待机时**每帧**变的不是「帧序号」，而是**该单位 OBJ 调色板第 15 项（1 像素描边色）的取值**；
帧序号本身严格遵循 ROM 的 hold 表（实测 `9 → 10 → 11 → 10`，每帧 hold 8）。

所以「32 帧内 31/30 幅互不相同的图像」是**调色板渐变**的产物，不是 30 个不同姿态。
既有门禁 `tests/test_s49_rule_idle_sequence.py` 里「roughly one pixel silhouette shift」
这句定性是错的：没有发生任何位移（见 §2.1）。

---

## 1. 证据源

| 用途 | 路径 |
| --- | --- |
| 原版 1800 帧零输入扫描 | 主树 `artifacts/s49-fidelity-20261019-v1/original-idle-sweep/`（`audit.json`：`input_state_sha256=a3628723ac595f41b87d329f49d5422a7b9b397a8491379abb8c9620568a0aa1`，`frame_count=1800`，`hold_frames=6`） |
| 既有门禁 | 主树 `tests/test_s49_rule_idle_sequence.py`（`changed_transitions=183/191`，精灵区 `distinct_images_in_32_frames=30`，整区 31） |
| 既有测量器 | 主树 `tools/butano/measure_s49_rule_idle_sequence.py`（`SWEEP` 行 40、`BRACKET_COLUMNS=9` 行 62） |
| 逆向导出（**只读**） | 逆向树 `artifacts/character-battle-visuals-v1/`（`manifest.json` + `resource-000/`） |
| 导出器（只读，用于二进制布局） | 逆向树 `tools/export_character_battle_visuals.py` |
| 已签的帧选择证明 | 逆向树 `notes/character-battle-visual-resource-matrix-20260801.md` |
| 导出语义与 scope | 逆向树 `notes/character-battle-visuals-export-20260729.md` |
| 调色板/图形回编链 | 逆向树 `notes/character-battle-palette-writeback-20260731.md` |
| GPU copy queue 清单 | 逆向树 `notes/rom-gpu-copy-queue-inventory-20260730.md` |
| sprite 运行时链 | 逆向树 `notes/sprite-definition-runtime-chain-20260729.md` |
| 既有 open item 记录 | 主树 `notes/s49-reverse-open-items-20261020.md` §2「待机 31 姿态」 |

逆向树 HEAD = `f054f4c1`，本轮**只读**，未写入任何文件；mGBA 未启动。

---

## 2. 决定性测量

以下三个测量全部只读，输入只有上面的扫描 PNG 与逆向树导出的 `resource-000`。

### 2.1 整块平移检验 —— 排除「1 px 剪影平移」

对 191 次跃迁，在 ±2 px 范围内搜索「把上一帧整体平移后与本帧重合」的最佳位移：

- 最佳位移**恒为 `(0,0)`**（191/191 次）；
- 191 次跃迁中 **109 次**的剪影掩码（非草地像素集合）完全不变，8 次整帧无变化；
- 精灵区（`(118,32)-(147,91)`）变化像素数中位数 = 126，最大 651。

⇒ 单位**没有**发生任何几何位移；变化像素是「原地换色」。

### 2.2 颜色集合检验 —— 变化像素 = 单一调色板索引的像素集合

跃迁 `t=0 → 1`：变化像素 **137 个**，颜色对**只有一种**：`(0,189,189) → (0,206,206)`；
而该区域内颜色恰为 `(0,189,189)` 的像素**正好 137 个**（`changed ∩ same_colour = 137`，
`same_colour \ changed = 0`）。

⇒ 变化的不是几何，而是**某一个调色板索引覆盖到的全部像素**。

### 2.3 帧序号复原 —— 帧序就是 ROM 的 hold 表

把屏幕像素按 `resource-000/palette-bgr555.bin`（GBA 5bit→8bit 展开 `(x<<3)|(x>>2)`）反查成调色板索引，
再与 `resource-000/frame-000.png … frame-015.png` 的索引图逐像素比对（评分 = 匹配数 − 冲突数），
对全部 96 帧取最佳匹配：

```
t =  0.. 2  -> frame 11
t =  3..10  -> frame 10
t = 11..18  -> frame  9
t = 19..26  -> frame 10
t = 27..34  -> frame 11
t = 35..42  -> frame 10
t = 43..50  -> frame  9
t = 51..58  -> frame 10
t = 59..66  -> frame 11        （周期 32 帧，与 ROM 的 hold=8 完全一致）
```

96 帧内无一次例外；`score` = 匹配 694–704 / 冲突 0–6。

这正是逆向树 manifest `resources[resource_id=0].animations[3]`：

- `timeline_pointer = 0x08142AFC`
- `keyframes = [(9,8),(10,8),(11,8),(10,8)]`
- `resource-000/timeline-region.bin` 对应字节：
  `09 00 08 00 0a 00 08 00 0b 00 08 00 0a 00 08 00 ff ff 00 00`
  （`0x08142AFC` 偏移 `0x3C`）

⇒ **原版帧序 = ROM 的 hold 表**。不存在「另一个运行期帧计数器」。

### 2.4 逐帧变的是什么 —— 描边色的三角波

`resource-000/frame-010.png` 的索引直方图里 `index 15` 有 160 个像素，正是单位的 1 px 描边；
屏上这批像素逐帧变色，而其余索引（1..14）的屏上颜色**全部落在 ROM 调色板取值集合内**
（逐帧索引比对时冲突数 0–6，冲突点全部是被第二个精灵覆盖的位置，见 §5）。

ROM 调色板在 `0x0813E070`（16×BGR555），其中索引 15 = BGR555 `0x0421` = `(8,8,8)`（近黑描边）。
该单位描边像素的屏上颜色逐帧为 `(0,g,g)`（少数被第二精灵覆盖的描边点例外），
`g` 的 5 bit 取值（t=0..31）：

```
23 25 27 29 31 31 29 27 25 23 21 19 17 15 13 11  9  7  5  3  1  1  3  5  7  9 11 13 15 17 19 21
```

即 **v = 1,3,5,…,31 的 16 个奇数，顶点（1 与 31）各停 2 帧，周期 32 帧的三角波**；
BGR555 写值 = `(v<<10)|(v<<5)`（r=0，g=b=v）。
`v(t) = 1 + 2*min(m, 31-m)`，`m = (t-21) mod 32`。

⇒ **运行期每帧改写该单位 OBJ 调色板 bank 的第 15 项**（PRAM 目标地址
`0x05000200 + bank*32 + 0x1E`）。本轮没有拿到该单位的 OAM attr2，**bank 号未知**。

### 2.5 「30 幅不同图像」的完整分解

把 32 帧按 `(frame_id, 描边色)` 分组：

- 不同 `(frame_id, 描边色)` 组合 = **28**；
- 其中 `(10,29)` 与 `(10,31)` 两组各裂成 2 幅 → 合计 **30**；
- 与门禁实测的 `distinct_images_in_32_frames = 30` **逐项吻合**。

多出的 2 幅来自区域里**第二个精灵**（见 §5）。因此：**「31/30 幅互不相同」完全由调色板渐变 +
第二个精灵解释，不需要 30 个姿态，也不需要 ROM 之外的帧序。**

---

## 3. 候选机制逐条判定

| 候选 | 判定 | 依据 |
| --- | --- | --- |
| (a) 1 像素剪影抖动（某个部件的逐帧偏移 / 翻转） | **否证** | §2.1 最佳平移恒 `(0,0)`、109/191 次剪影不变；且 §2.4 变化像素位置与该帧美术的 `index 15` 像素集合**完全重合**，位置从未移动 |
| (b) 非 hold 表的运行期帧计数器 | **否证** | §2.3 帧序逐帧等于 `0x08142AFC` 的 `[(9,8),(10,8),(11,8),(10,8)]` |
| (c) 动画表 hold 字节从 RAM 读 | **无支持** | 观测 hold 恒为 8，与 ROM 字节一致；没有任何 RAM 侧 hold 来源的证据 |
| (d) 复合精灵各部件独立运动 | **否证** | 逆向导出里 `resource-000`（character 1 / 鸣人 / `visual_slot 0`）的 20 帧**每一帧只有 1 个 component**：`resource-000/component-region.bin` 中 frame 0/9/10/11 的组件记录分别为 `0x08142890` / `0x08142968` / `0x08142980` / `0x08142998`，全部是 `x=-16, y=-56, 32x64, orient=0x00, scale=0x0100/0x0100`，**只有 tile_offset 变**（0/288/320/352）。重制侧同源：`butano-sequel/game/include/konoha/generated_battle_unit_visual_content.h:666-687` 的 `battle_unit_01_slot_0_frames` 里 frame 0..11 的 pose 恒为 `{0,-24,true,0,N}`，只有最后一个字段（tile）变 |
| (e) **单位 OBJ 调色板某一项被运行期逐帧改写（描边色渐变）** | **支持** | §2.2、§2.4、§2.5 |

补充：逆向导出的 `scope` 已经把 `blend_and_palette_transform` 标为 `false`
（`artifacts/character-battle-visuals-v1/manifest.json`），即**调色板变换本来就是导出侧声明未闭合的部分**——
本轮把「哪个索引、被改成什么、什么周期」测了出来，但**改写者是谁仍是未知**。

---

## 4. 判别测量（可复现的判别式）

「1 px 抖动」与「新帧序号」的判别式只有一条，但很干净：

> **把「每次跃迁的变化像素集合」与「该帧美术中同一调色板索引的像素集合」求包含关系。**
>
> * 若变化是几何位移 / 剪影抖动：变化像素集合**不会**落在单一调色板索引内，而且剪影掩码会变、最佳整体位移 ≠ `(0,0)`；
> * 若变化是新帧序号：剪影或索引分布会整块换掉（会出现大量「旧索引 → 新索引」的成对变化）；
> * 若变化是调色板改写：变化像素集合 ⊆ 某单一索引的像素集合，且该索引的颜色**只在这一个索引上**变。

实测结果：**变化像素 ⊆ `index 15` 像素集合**（例如 `t=0→1`：137/137 完全重合），
剪影不变、最佳平移 `(0,0)` ⇒ 判别结果是 (e)，不是 (a)、也不是 (b)。

复现方式（只读）：

1. 取 `artifacts/s49-fidelity-20261019-v1/original-idle-sweep/frame-000.png`…`frame-031.png`；
2. 用 `tools/butano/compare_s49_unit_silhouette.py` 里的 `GRASS` 颜色集合取「非草地」掩码；
3. 逐跃迁算变化像素集合、算 ±2 px 最佳整体位移、算 `变化像素 ∩ {同色像素}`；
4. 用逆向树 `resource-000/palette-bgr555.bin` + `frame-000..015.png` 反查帧序号。

---

## 5. 残余：区域里的第二个精灵

变化区域 `(109,32)-(146,90)` 里**不止一个精灵**：

- 主角单位（character 1 / 鸣人 / `resource-000`）占据 `x=112..143`、对齐点 `(112,24)`，
  1 px 描边 = 调色板 `index 15`；
- 在 `x≈138..146, y≈70..90` 还有第二个精灵压在主角脚下，96 帧里有 **23/95** 次跃迁的变化落在它身上
  （颜色不属于 `resource-000` 的调色板：`(247,255,222)`、`(181,189,165)`、`(115,123,107)` 等）。

该第二精灵的**身份未知**（`unknown`）：既不属于 `resource-000` 的调色板，也没有证据指向
`character 30`（木叶丸）的任何 slot；它自身也在动（`t=4,5,10,14,16,20,26` 等）。

---

## 6. 下一步（逆向侧该攻哪一处）

### 6.1 主攻：每帧改写单位 OBJ 调色板第 15 项的那条代码

- 已知源：ROM 调色板 `0x0813E070`（16×BGR555，索引 15 = `0x0421` → `(8,8,8)`）。
- 已知目标：`0x05000200 + bank*32 + 0x1E`；写入值 = `(v<<10)|(v<<5)`，`v` 为奇数 1..31 的三角波。
- **为什么不在既有 copy queue 上**：逆向树 `notes/rom-gpu-copy-queue-inventory-20260730.md` 已证
  共享队列 `0x03005BBC..0x03005CBC` 的 14 个直接 `BL 0x080635B8` caller **全部是整块拷贝**
  （416 / 352 / 128 / 32 字节或动态源，见该 note 的「RAM 与动态来源」表），
  **没有 2 字节的单项写入** ⇒ 描边色的逐项改写不可能走这条链，只能是直接 `STRH`。
- **建议动作**：对 PRAM OBJ 区 `0x05000200..0x050003FF` 做一次「直接半字写入」全 ROM 清单
  （与逆向树 `tools/export_rom_gpu_copy_queue_inventory.py` 同形），筛出「目标落在
  `…+bank*32+0x1E`」且「值形如 `(v<<10)|(v<<5)`、v 奇数」的写入点。
- **起点链**（逆向树已签地址）：
  - sprite task 分配 `0x080625A4..0x080626B0`（`artifacts/character-battle-visuals-v1/manifest.json` → `consumer.sprite_task_allocator`）；
  - 按当前帧选 component list `0x0806298C`、attr2 组装 `0x08063108`、组件渲染 `0x080629FC`（`notes/sprite-definition-runtime-chain-20260729.md:60-61,133-137`）；
  - sprite renderer `0x08062924`，由 dispatcher `0x080612BC..0x080614E4` 的 `0x08061320` 调用（`notes/rom-gpu-copy-queue-inventory-20260730.md:64-68`）；
  - 动画状态（animation id / keyframe index / hold timer / frame 指针）在全局 task 数组，**槽 127 = `0x0300597C`**（`notes/character-battle-visual-resource-matrix-20260801.md:65-71`）；
  - 单位池 `0x020240C0`，13 条 × 468 B，`character_id@+0x00`、`grid_x@+0xC4`、`grid_y@+0xC5`（`artifacts/character-runtime-unit-oam-bindings-v1/bindings.json` → `unit_pool_contract`）。
- 附带需要的运行期事实：该单位 OAM `attr2` 的 palette bank 号（本轮 `unknown`），
  拿到后即可把写入点收敛成一个确定地址。

### 6.2 附带（重制侧零逆向成本就能做）

帧序已经闭合：**原版这场战斗的待机用的是 `resource-000` 的动画 3（`0x08142AFC`，
`[(9,8),(10,8),(11,8),(10,8)]`）**。

重制侧当前 `butano-sequel/game/include/konoha/battle_unit_visual_animation.h:117-133` 的
`idle_sequence(facing)` 返回 0/1/2/3（down/up/right/left），对应 `generated_battle_unit_visual_content.h`
里 slot 0 的 `battle_unit_01_slot_0_sequences[0..3]`；其中 `sequences[3]` = `steps[12..15]`
= `[(9,8),(10,8),(11,8),(10,8)]`，**正好是原版在用的一条**。
⇒ 重制只要在朝向选择上对齐，就能拿到同样的 4 姿态；剩下的「每帧不同」由 §2.4 的描边色渐变补齐。

---

## 7. 仍未确立（`unknown`）

1. 改写调色板第 15 项的**代码位置** —— `unknown`（本轮只测出值与周期，未定位写入者）。
2. 该单位 OBJ 调色板的 **PRAM bank 号** —— `unknown`（本轮无 OAM attr2 收据）。
3. 运行期选用**动画 3**（而不是动画 0/1/2）的判据 —— `unknown`
   （导出 `slot_semantics[0]` 的 `facing` 为 `null`；`consumer.selector` `0x0807AE04..0x0807B284` 只记到 slot 选择）。
4. 主角单位在原版这一场**面朝哪边** —— `unknown`（本轮只从美术反查帧序号，未查朝向）。
5. 第二个精灵的身份 —— `unknown`（见 §5）。
6. 描边色渐变是否**对所有单位**都成立、是否与「当前行动者」绑定 —— `unknown`
   （本轮只测了带选择框的这一只；场景里另一只没有逐帧变化）。
7. 这条渐变是调色板**写入**还是另一层效果（例如半透明叠加）—— 证据强烈指向写入
   （其余 15 个索引的屏上颜色全部落在 ROM 调色板取值集合内，且只有索引 15 变色），
   但**未拿到 PRAM 收据**。
8. 原版**战场外**（地图/移动）是否用同一条描边渐变 —— `unknown`（本轮只测了 battle-14 入口扫描）。

---

## 8. 对既有结论的更正（需要 owner 处理，本轮未改任何文件）

- `tests/test_s49_rule_idle_sequence.py:8` 与 `tools/butano/measure_s49_rule_idle_sequence.py:8`
  文档串里的「The change is a roughly one pixel silhouette shift」**与实测不符**：
  实测是「1 像素宽的描边**换色**，位置不动」。测量器本身的数字（183/191、30、31）仍然有效，
  失效的是「shift」这个定性。
- `notes/s49-reverse-open-items-20261020.md:91`（§2「缺什么」第 3 条）里
  「运行期 30 幅互不相同的图 > resource 0 的 20 帧总量 ⇒ 运行期显示的不可能是 field slot 那 32 帧动画集合里的帧」
  **不成立**：这 30 幅里有 28 幅就是 field slot 的 3 个 `frame_id` 配上 28 个不同的描边色。
  「帧序未知」这一条也随之更正为「帧序 = ROM 的动画 3」。
