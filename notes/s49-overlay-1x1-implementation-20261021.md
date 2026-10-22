# 覆盖层 1:1 接线：第 ①② 步的**实测否证**（2026-10-21 第 26 轮末）

日期：2026-10-21
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
基线 ROM `02bf3573118f4b43d58189db6816a5d0d2d47190f23e0f1d3c6abd5dbb217803`（残差 **2,917**）
实验 ROM `d589ad34c0b9ced973a3e5d0082db99cb45c709e589962b415c1405bcf1409e4`（残差 **16,533**）

## 0. 结论

**第 ①② 步按施工单实施后实测变差 ⇒ 已回滚。**
源码回到基线（`git checkout-index -f`），ROM 逐字节回到 `02bf3573…`，
失败实验的收据保留在 `artifacts/s49-remake-walk-20261021-v2/`（含 `baseline.json`）。

**但否证本身有价值**：它把「装原版烘焙窗口」这条路线的失败点**定位到了具体位置**，
下一轮不必再从头试。

## 1. 做了什么（三处改动，全部按 `artifacts/s49-overlay-plan-20261021-v1/patch-plan.md` §5）

1. `battle_range_ui_style.h`
   - 块预算 77 → **101** 逻辑块（154 → 202 存储块）；原版的 24 块放在 **77..100**，
     **菜单字形 25..52 与既有程序化图块 1..24、53..76 全部不动**（不碰状态面板与动作菜单）；
   - 新增 `battle_range_ui_original_slot(original_tile)`：原版 258..281 → 77..100，
     其余（256/257/282..287 全透明）→ 0；
   - 新增滚动常量（原版 hoff=240/8=30、voff=24/8=3）。
2. `_prepare_tiles`：把**已生成并逐块复核过的** 8bpp 展开图块
   （`generated_battle_battlefield_overlay_tiles.h`）拷进 77..100。
3. `update()` 的移动相位：在规则化绘制之后，把原版烘焙窗口按
   `map[row*32+col] ← 原版 tilemap[((row+3)%32)*32 + ((col+30)%32)%32]` 装进去。

## 2. 实测

```
capture_s49_advance.py → artifacts/s49-remake-walk-20261021-v2/（35 步）
measure_s49_movegrid_baseline.py --walk artifacts/s49-remake-walk-20261021-v2
```

| 帧 | 基线 | 实验 | 差 |
| --- | ---: | ---: | ---: |
| **step-20-A**（移动网格帧） | **2,917** | **16,533** | **+13,616 ⬅ 变差** |
| step-21-A | 23,635 | 23,635 | 0 |
| step-33-A | 13,032 | 12,935 | −97 |
| 其余 32 帧 | — | — | 全部 0 |

⇒ 只有移动网格帧变了（符合预期：装窗只在该相位生效），
但**变差了 13,616 像素**，且**没有任何一帧变好**（除 step-33 的 −97 噪声级）。

## 3. 症状与定位

看实验帧的画���：**整个战场被一层 16 px 间距的青色网格覆盖**，
而原版只有稀疏的网格网 + 中间的青色透镜。
青色 = (65,106,139) = 原版 bank 12 的**调色板 1** = **网格网族的描边色**。

⇒ **症状 = 网格网族被画到了所有格上**（原版只画在稀疏的格上）。

### 已排除的可能

- **install 公式错**？**不是**。用 Python 复算同一公式，得到的 slot 分布与
  `artifacts/s49-original-overlay-screentruth-v1/screen-truth.json` 的族分布图**逐行吻合**
  （r0/r1/r2 全是受阻族 97..100；r3 是 `0 77 97 97 97 98 0 0 0 77 0 0 0 77 81 81 81 82 …`，
  与期望的 `ngbbbbnnngnnngmmmmnnngbbbbbbbb` 一一对应）。
- **8bpp 展开数据错**？**不是**。生成头逐块复核过：
  块 258 = `0×7 + 225`（右边缘）、块 262 = 全 226（透镜）、块 279 = 234 填充 + x=7 处 235。
- **滚动折进索引错**？**不是**（同上，公式复算吻合）。

### 剩下的两个嫌疑（下一轮要查的就是这两个）

1. **VRAM 里 77..100 号槽的图块数据没写进去或写串了**
   —— 但 `_tiles` 数组按 `logical_tile_count*2 = 202` 个 32 字节单元分配（6,464 B），
   槽 100 的偏移 6,400..6,463 **在界内**。
   ⇒ 仍需**读一次重制侧 VRAM**（`tools/butano/capture_s49_gpu_state.py`），
   核对 `0x06010000` 起的图块区里 77..100 号槽的真实字节，以及 `0x06013000` 起的
   地图区里 30×20 可见窗口的真实 tile index。**这一步没做，所以不能下结论。**
2. **Butano 8bpp 模式下的 map cell tile index 语义**
   —— 程序化路径用 1..76 且 154 个存储单元（=77 个逻辑块）⇒ 既有路径证明
   **map cell 的 tile index 是逻辑块号**（Butano 内部 ×2）。
   ⇒ 理论上新槽 77..100 也应成立；**但 202 个存储单元的数组分配是否真被
   `regular_bg_tiles_item` 完整上传**，以及 `bn::bg_tiles::set_allow_offset(false)`
   之下 8bpp 的块基址对齐，**都没验证过**。

## 4. 下一步（精确）

1. **先读 VRAM**，不要改代码：
   ```bash
   /usr/local/bin/python3 tools/butano/capture_s49_gpu_state.py \
       --state artifacts/s49-remake-walk-20261021-v2/step-20-A.ss9 \
       --rom butano-sequel/butano-sequel.gba --out-dir <新目录> --settle-frames 3
   ```
   核对三件事：
   (a) `0x06010000 + 77*64` 起 64 字节是否 == 展开表里原版块 258 的 8bpp 像素；
   (b) `0x06013000` 起 30×20 可见窗口的 tile index 是否 == 第 2 节复算出的 slot 分布；
   (c) `0x06010000` 起的**整块**是否被别的图块占用（8bpp 的块基址对齐/上传长度）。
2. 按 (a)(b)(c) 的结果决定是修上传还是修槽位。
3. **重测门槛不变**：必须 ≤ 2,917，且**任何一帧都不得变差**；
   仍用 `tools/butano/measure_s49_movegrid_baseline.py` 的逐帧报告当护栏。

## 5. 这一轮留下的**正向**成果（未被回滚）

| 项 | 状态 |
| --- | --- |
| 原版 32 块的 **8bpp 展开产物**（`generated_battle_battlefield_overlay_tiles.h`） | ✅ 保留，逐块复核过 |
| `tools/butano/measure_s49_movegrid_baseline.py`（逐帧基线测量器） | ✅ 保留 |
| 施工单 §5 的可执行级规格 | ✅ 保留（本次按它实施，规格本身没错） |
| 失败实验收据 | ✅ `artifacts/s49-remake-walk-20261021-v2/`（含 `baseline.json` 逐帧数） |
| 基线 | ✅ 已回滚验证：ROM `02bf3573…`，残差 **2,917** @ step-20 |
