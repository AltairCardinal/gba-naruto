# S49 被选中单位的 visual slot / frame（2026-10-20）

## 1. 问题

原版在战场上把一个单位画成「被选中 / 活动单位」时，用的是 `character-battle-visuals-v1`
导出表里的哪个 **visual slot**、哪个 **frame**？重制版同一时刻画的是哪一个？要让两边一致，
最小改动是什么？重制版缺的「红白条纹（绳/腰带）」在原版选中的那一帧里到底存不存在？

对照输入：

- 原版帧：`artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-18-A.png`（240x160）
- 重制版帧：`artifacts/s49-fidelity-20261019-v1/walk-remake-dd-a30-final/step-19-A.png`
- 导出：`/Users/altair/github/gba-naruto-reverse/artifacts/character-battle-visuals-v1/`
  （`manifest.json` + `resource-000/` … `resource-249/`）
- ROM：`rom/base.gba`，SHA-256 `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`

## 2. 先修正任务前提（实测）

1. **「左侧单位面板」不成立。** 这两帧左侧 (x<109) 是命令菜单
   （移動 / 本・忍具 / **查克拉** / 休息 / 行動結束），原版与重制版在 x<109 **逐像素相同**。
   ⚠️ **第 15 轮更正**：本行原先转录成「本・道具 / 查敵台 / 替身 / 行動結果」，是把原版帧放大 4 倍后重读的结果（`artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-18-A.png`）；**第 3 项是「查克拉」**（补查克拉）而不是「查敵台」，第 4 项是「休息」而不是「替身」。
2. **差异全在战场上那个单位精灵上**：两帧整幅差分 = 655 像素，
   bbox = **x 109..144, y 34..88**（不含任何面板像素）。
3. 该单位是**角色 1（鳴人）**，朝左，身上叠了两个光标：
   红色命令光标（x 111..117, y 36..43，8x16，对应重制版 `battle_ui_command_cursor.bmp`）
   和蓝色朝向光标（锥形，色 (0,107,189)，不属于角色 1 调色板）。

## 3. 方法（可复现）

全部只用 `/usr/local/bin/python3`（3.14.3）+ Pillow 12.2.0，**未跑模拟器**。

1. **取分母**：`manifest.json` 的 `slots`（558 行）→ 角色 1 = 9 个 slot，
   `visual_slot` 0..8 → `resource_id` 0..8，`semantic` 0=`field_idle_and_movement`，
   1=`cast_facing_right` … 8=`hit_facing_left`。角色 1 九个 slot 共 62 帧。
2. **建 RGB→index 查找表（与调色板无关的索引空间）**：
   `resource-000/palette-bgr555.bin`（0x0813E070，32 字节 = 16 色 BGR555），
   5bit→8bit 用 `(c<<3)|(c>>2)`。验证：`resource-000/frame-000.png` 的 PNG 调色板
   与该换算**逐项相等**（16/16），所以屏幕 RGB → index 是精确映射，不是近似最近邻。
3. **截屏 index map**：对每张 PNG 按该 LUT 把每个像素换成 0..15（不在表内 = `-1`）。
4. **判别式模板匹配**（对 62 个角色 1 帧 × 位置网格）：
   - `true mismatch` = 帧的非透明像素落在**调色板内**的屏幕像素上但 index 不等 → 必须为 0；
   - 落在调色板外的屏幕像素（被光标/背景覆盖）不计入 mismatch，但要单独统计；
   - 再要求「匹配上的帧像素 ≥ 帧不透明像素的 55%」，以排除整帧落在背景里的退化位置。
5. **交叉验证**：`butano-sequel/graphics/battle_unit_01_idle.bmp` 与
   `resource-000/frame-000.png` 逐像素比较；重制版生成头
   `butano-sequel/game/include/konoha/generated_battle_unit_visual_content.h`
   里 `battle_unit_01_slot_0_frames[i].components[0].graphics_index == i`
   （帧号与导出 `frame-NNN.png` 一一对应）。

关键脚本（可直接重跑）：

```python
ART='/Users/altair/github/gba-naruto-reverse/artifacts/character-battle-visuals-v1'
PAL=[(198,132,255),(33,33,33),(222,222,82),(214,140,74),(255,0,0),(239,189,165),
     (181,132,107),(132,82,49),(255,156,66),(222,107,41),(66,99,255),(33,8,181),
     (255,255,255),(206,206,206),(165,165,165),(8,8,8)]          # 由 palette-bgr555.bin 换算
lut={c:i for i,c in enumerate(PAL)}
S=[[lut.get(px[x,y],-1) for x in range(W)] for y in range(H)]      # 屏幕 index map
d=list(Image.open(f'{ART}/resource-000/frame-{fi:03d}.png').getdata())
for i,v in enumerate(d):
    if v==0: continue
    dx,dy=i%32,i//32; s=S[Y0+dy][X0+dx]
    m += (s==v); o += (s==-1); b += (s!=-1 and s!=v)
```

## 4. 结论

### (a) 原版用哪个 slot / frame

**visual slot 0（`field_idle_and_movement`），frame index 10**
（导出文件 `resource-000/frame-010.png`），精灵格 32x64，格原点在屏幕 **(112, 24)**。

判别表（原版 `step-18-A.png`，格原点 112,24，统计全部 20 个 slot-0 帧）：

| frame | matched | 被覆盖(调色板外) | **true mismatch** |
|---|---|---|---|
| **010** | **694** | 227 | **0** |
| 009 | 304 | 259 | 383 |
| 011 | 322 | 225 | 371 |
| 其它 17 帧 | 2..190 | 241..783 | 414..500 |

只有 frame 010 的 mismatch 为 0；下一名（frame 011）差 371 个像素。判别力充足。

### (b) 重制版用哪个 slot / frame

- `walk-remake-dd-a30-final/step-19-A.png`：**visual slot 0，frame index 11**
  （`resource-000/frame-011.png`），格原点同样是 **(112, 24)**；
  20 帧里同样只有 frame 011 的 mismatch = 0（704 matched / 214 被覆盖 / 0 mismatch）。
- `walk-remake-dd-a30-final/step-18-A.png`：**visual slot 0，frame index 10**
  （694 / 227 / 0）——**与原版 step-18 的单位美术逐像素一致**。

**即：两边 slot 相同（都是 slot 0），差的是 idle 时间线上相邻的一步（8 帧）。**
不是「重制版挑错了 slot」。

### (c) 最小改动

重制版的选帧路径（`butano-sequel/game/src/battle_runtime_scene.cpp`）：

- `unit_visual_sample()`：`sample.sequence = idle_sequence(facing)`；
  `sample.elapsed_frames = scene_frame + idle_phase_offset(unit.id)`；idle 时 `sample.slot = 0`。
- `frame_at()`（`butano-sequel/game/include/konoha/battle_unit_visual_animation.h`）按 steps 展开。
- 该单位朝左 → `idle_sequence(left)=3` → `battle_unit_01_slot_0_sequences[3]`
  （`first_step=12, step_count=4`）→ steps 12..15 = 帧 **9, 10, 11, 10**，每步 8 帧。

当前重制版落在 **step2 → frame 11**（elapsed ∈ [16,23] mod 32）；
原版落在 **frame 10**（elapsed ∈ [8,15] 或 [24,31] mod 32）。

**最小改动 = 把该单位的 idle 相位挪一个 step（8 帧）**，使 `frame_at()` 落到 frame 010
而不是 011。落点候选是 `battle_unit_visual_animation::idle_phase_offset()`：
它现在对**奇数 unit_id 返回 0、偶数 unit_id 返回 16**（`battle_unit_visual_animation.h:30-40`），
对该单位改成 8（或 24）即可命中 frame 10。

**注意（重要）**：这只能让**这一帧**一致。要全局对齐必须用同一份输入脚本重录后逐帧复核，
见 §6。

### (d) 原版选中的那一帧里，红白条纹（绳/腰带）存不存在

**存在，而且重制版那帧里同样存在**——不是「重制版缺这块美术」。

| | 红 (255,0,0) 在格内 | 屏幕坐标 | 紧邻浅灰 (206,206,206) |
|---|---|---|---|
| 原版 frame 010 | (25,39)、(25,42) | **(137,63)、(137,66)** | (137,64)、(137,65) |
| 重制版 frame 011 | (24,39)、(24,42) | **(136,63)、(136,66)** | (136,64)、(136,65) |

即 x=137 这一列是 **红 / 白 / 白 / 深 / 红** 交替的竖向细带（原作的绳/腰带），
重制版里整条带子**左移 1 px**（x=136），所以红与白的配对关系变了，
1x 画面下肉眼看就像「重制版那条红白条纹不见了」。素材在两边都在。

（另：原版画面上 x=111..117, y=36..43 那块红色**不是**单位美术，是红色命令光标；
重制版把它画在 x=110..116，同样左移 1 px。）

## 5. 原始像素 / 索引证据（数字与偏移）

1. **整帧差分**：原版 step-18 vs 重制版 step-19 = 655 像素，bbox x109..144, y34..88。
   颜色对全是单位美术互换，例如
   `(222,107,41)->(33,33,33) x17`、`(33,33,33)->(132,82,49) x30`、
   `(132,82,49)->(222,107,41) x14`、`(255,156,66)->(222,107,41) x9`。
2. **原版 step-18 vs 重制版 step-18** = 区域 x100..149,y24..89 内 294 像素，
   颜色对全部是光标/灰阶描边：
   `(57,57,57)->(255,0,0) x6` 与 `(255,0,0)->(57,57,57) x6`（红光标平移 1 px）、
   `(181,189,165)->(247,255,222) x36`、`(115,123,107)->(181,189,165) x32`、
   `(107,107,107)->(107,115,99) x10`。
   **单位美术本身已 0 差异**（见 (b)）。
3. **逐帧 slot-0 识别**（同一判据，20 帧全扫）：
   - 原版：step-00=10, step-17=10, **step-18=10**, step-20=11, step-22=9
   - 重制版：step-04=10, step-18=10, **step-19=11**, step-24=10, step-25=11, step-29/30/31=9
4. **重制版 idle 资产血缘**：`butano-sequel/graphics/battle_unit_01_idle.bmp` 与
   `resource-000/frame-000.png` 逐像素 **2048/2048 相同**（其余 19 帧 870..1454）。
   即重制版 `battle_unit_01_idle` 就是 slot 0 的第 0 帧
   （`generated_battle_unit_visual_content.h:12741` 的 `battle_unit_idle_visual_for`）。
5. **像素同体的跨 slot 重复**：`resource-000/frame-010.png` 与 `resource-005/frame-001.png`
   逐像素相同；`resource-000/frame-011.png` 与 `resource-005/frame-002.png` 逐像素相同。
   → 纯像素判据无法区分「slot 0 frame 10」与「slot 5 frame 1」；
   语义上战场 idle 只能是 slot 0，且重制版运行时 idle 分支固定 `sample.slot = 0`。
6. **调色板**：角色 1 九个 slot 共用 0x0813E070；index 4 = (255,0,0) 纯红，
   index 12 = (255,255,255) 白，index 13 = (206,206,206) 浅灰。
   蓝色 (0,107,189) **不在**该表内 → 证明它是另一个光标对象，不是单位美术。

## 6. 未确立（not established）

1. **两条录像的步号不可直接对齐**：`walk-original-a24/inputs.json` = savestate 起 24 个 `A`；
   `walk-remake-dd-a30-final/inputs.json` = power-on 起 `Down,Down` + 30 个 `A`。
   「原版 step-18 ↔ 重制版 step-19」并**不是同一次输入事件**。
   「重制版快一步」这个结论是在各自录像内部成立的（重制版 step-18 本身就是 frame 010），
   跨录像的绝对相位必须用同一份输入脚本重录才能判定。
2. **原版这一帧的绝对 elapsed 未知**：像素只能给出 frame 号 10，无法区分
   elapsed ∈ [8,15] 还是 [24,31]（mod 32）。
3. **重制版该单位的 unit_id 未确立**，所以 (c) 里 `idle_phase_offset()` 该改成 8 还是 24
   取决于 id 是奇是偶；未跑模拟器，无法从截图反推 id。
4. **全局 idle 相位未验证**：本次只核对了 slot 0 / sequence 3（朝左）。
   sequence 0/1/2（朝下/上/右）与其它单位的相位是否同样偏一步，未查。
5. **灰阶描边与光标的 1 px 偏移未定位到代码路径**：原版 step-18 vs 重制版 step-18
   残留的 294 像素里，含红光标平移 1 px 与灰阶描边色差，原因未追到具体函数。
6. **「selected unit 走哪条 slot」在导出侧仍未闭合**：`character-battle-visuals-v1` 的
   `scope` 明确写着 `runtime_slot_selection: false`、`screen_space_position: false`。
   本笔记只证明「这一帧的像素等于 slot 0 的第 10/11 帧」，没有证明原版运行时
   在任意时刻都选 slot 0。
7. 未运行 mGBA（任务禁止），全部结论来自静态像素 + 已签导出表 + 重制版源码。
