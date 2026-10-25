# S49「木叶丸 vs 野蜂」三天复刻 —— 共享工作简报

**所有子代理都先读这份文件。** 它是事实基线，不是猜测。
口径、目标、排期见 `docs/s49-three-day-plan.md`。

## 0. 三棵树（不要搞混）

| 树 | 路径 | 角色 | 谁能改 |
|---|---|---|---|
| **master** | `D:\Github\gba-naruto` | 决策线 / 工具 / 报告 | 工具与报告写这里 |
| **重制线** | `D:\Shell\Github\gba-naruto-butano` | **产品代码在这里** | 只有被指派的 stream 能改 |
| **逆向线** | `D:\Shell\Github\gba-naruto-reverse` | 逆向证据 | **只读** |

> `D:\Github\gba-naruto-butano` 与 `D:\Github\gba-naruto-reverse` 是 junction，
> 和 `D:\Shell\Github\...` 是同一份。**用 `D:\Shell\Github\...` 路径写文件**
> （`git worktree` 记录的是它）。

## 1. 已有的工具（都能直接用，别重造）

| 工具 | 位置 | 作用 |
|---|---|---|
| 无头 mGBA 探针 | `D:\Github\gba-naruto\build\mgba-probe\mgba-probe.exe` | 读命令、写命令、跑帧、截图、dump 内存、跑 Lua |
| 探针客户端 | `tools\mgba_probe\probe_client.py` | `--rom` `--bios` `--cmd` `--out` |
| 逐像素比对 | `tools\compare_frame_dirs.py` | 两目录同名 PNG 逐像素比（可 `--field-area`） |
| 交叉对齐 | `tools\align_frame_dirs.py` | 距离矩阵，找最佳匹配帧 |
| 审计 | `tools\butano_feasibility_probe.py` | 8 个子系统的可行性实测 |

**探针是 core-only 的**（只链 libmgba core）：**没有窗口、没有音频设备**。
探针支持 `script <path>` 跑 mGBA 的 Lua 脚本。

### 1.1 重制线自己的 Lua 探针脚本（73 个，原样可用）

`D:\Shell\Github\gba-naruto-butano\tools\butano\*.lua`

常用的两个，各自有**不同的环境变量契约**：

* `mgba_original_s49_ui_boundaries.lua` —— 从 **savestate** 起步，`MGBA_ORIGINAL_S49_*`
* `mgba_boot_input_sequence.lua` —— 从 **上电** 起步，`MGBA_BOOT_SEQUENCE_*`

**先读脚本头部确认契约**，不要凭猜传环境变量。
**输出目录必须先 `mkdir`**，否则脚本 `saveStateFile` 失败（会刷几百行同一条错）。

### 1.2 已知可用的录制参数（本机实测过）

> ⚠️ **2026-10-23 23:5x 订正（wave 1 实测）**：
> ① **基线录像用的是 HLE BIOS，不是真 BIOS**（带 `--bios` 时重制侧**连上电流程都不同**）。
>    ⇒ **一律不加 `--bios`**。
> ② **`ZERO_INPUT_FRAMES` 必须是 600**（不是 240）——
>    240 在当前构建上**进不了战斗**（停在准备场景），会拿到一份无效 walk。
> ③ **重制 ROM 的 sha 与基线钉的 `02bf3573…` 不同**（本机构建非字节可复现），
>    ⇒ 基线录像的 savestate **load 不了**（mGBA 校验 ROM）⇒ **一律本机重录**。
> ④ **重制侧覆盖层 map 的 VRAM 地址随构建变**（本机构建实测 `0x11800`）
>    ⇒ 用 `tools/find_overlay_map_signature.py` **现算**，不要写死。
> ⑤ ⭐ **订正（wave 2 H 流**证伪**，原 ⑤ 作废）**：「本机慢一倍」**不成立** ——
>    实为**采集重复**（探针 Lua `frame` 回调每 GBA 帧触发两次，相邻偶/奇对 12/12 逐字节相同）。
>    ⇒ macOS 门禁里的绝对计数（183/191、30 张）**现在可以直接比**（本机采集帧数 ÷2）。
>    但**仍一律按内容定位**（`grid16` 只有 1 帧瞬态）。
>    证据：`notes/s49-fidelity/H-idle.md` §1。
> ⑥ ⭐ **订正（wave 3 G 流证伪）**：**原版的战斗格 = 32×16 px**，
>    16×16 px 只是**逻辑格**（**1 战斗列 = 2 逻辑列，1 战斗行 = 1 逻辑行**）。
>    ⇒ 「一格 = 16×16 px、把 `tiles_per_cell_x` 4→2」是**错的**（会把 32 px 格线画成 16 px）。
>    ⇒ 覆盖层的真根因是**没做地图空间锚定**（不是粒度、不是调色板 bank）；
>    「多画 310–420 格 / 缺 96–129 格」这个口径也是错的 ⇒ 换算后**多画 42 / 缺 24**。
>    ⇒ **battle-14 = 逆向线 map id 14**（15×19 战斗格，可走 **147** / 不可走 **138**），
>    坐标 `(bx,by)` = 碰撞网格列行、**无偏移**；**移动范围 = 曼哈顿半径 3**。
>    证据：`G-overlay-alignment.md`、`M-original-victory-truth.md`。

**原版 25 帧**（从 savestate 起步）：

```
状态：D:\Shell\Github\gba-naruto-butano\artifacts\runtime-checkpoints\scenario-49-battle-14-entry.ss9
      （sha256 a3628723…，与记录一致）
ROM ：D:\Shell\Github\gba-naruto-butano\rom\base.gba （sha256 1198ece7…）
脚本：…\tools\butano\mgba_original_s49_ui_boundaries.lua
env ：MGBA_ORIGINAL_S49_INPUT_STATE / _INPUT_STATE_SHA256 / _OUTPUT_DIR / _DONE_MARKER
      / _KEY_SEQUENCE="A,A,…"（24 个）/ _ZERO_INPUT_FRAMES=90 / _SETTLE_FRAMES=90 / _HOLD_FRAMES=4
```

**重制 35 帧**（从上电起步，`Down,Down,A×32`）：

```
ROM ：D:\Shell\Github\gba-naruto-butano\butano-sequel\butano-sequel.gba
脚本：…\tools\butano\mgba_boot_input_sequence.lua
env ：MGBA_BOOT_SEQUENCE_OUTPUT_DIR / _DONE_MARKER / _ROM_SHA256=1198ece7…
      / _KEY_SEQUENCE="Down,Down,A,A,…"（32 个 A）/ _HOLD_FRAMES=4 / _SETTLE_FRAMES=90
      / _ZERO_INPUT_FRAMES=600     ← 订正
```

探针调用形态（注意 `--cmd` 可重复）：

```
python tools/mgba_probe/probe_client.py --rom <rom> --bios <真实BIOS，可选>
    --cmd "script <lua>" --cmd "frames 3000 0x000" --out <result.json>
```

**真实 BIOS**：`D:\Github\gba-naruto\recomp\bios\gba_bios.bin`
（探针用 `core->opts.bios` + `useBios`；**不要**用 `loadBIOS()`，那会让游戏跑飞）。

## 2. 本机实测基线（2026-10-23）

原版 25 帧 ↔ 重制 35 帧，**交叉对齐**后逐帧取战场区（0,0,240,128 = 30,720 px）最小差：

| 原版帧 | 最佳重制帧 | 残差 |
|---|---|---:|
| step-14-A | step-14-A | **0 px** |
| step-15-A | step-15-A | **0 px** |
| step-17-A | step-16-A | **0 px** |
| step-13-A | step-14-A | 28 px |
| step-16-A | step-16-A | 344 px |
| 其余多数 | — | 1,000–2,500 px |
| step-22/23 | — | 21k–27k px |

**残差分两类，必须分开**：
* **产品差**（1,000–2,500 px）＝ 覆盖层 2,304 + 描边粒度 600 ⇒ **要改代码**
* **配对差**（21k–27k px）＝ 两侧处在**不同游戏时刻** ⇒ **不许改代码**

已知的具体差异项：
* 覆盖层「受阻区漏画」2,304 px —— 原版逐单元答案**已经导出**：
  `D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1\`
  （`*.bg2-layer.png` 可直接当门禁期望值；`bg2-tiles-4bpp.bin`、`bg2-palette.bin`、
  `bg2-tilemap.json` 同目录）
* 覆盖层「描边粒度」600 px —— 原版 16×16 单元 vs 重制 32×16（8×8 状态格被扩成 4×2 块）
* idle 相位 —— 原版 frame 010 vs 重制 frame 011。**"整体平移 8 帧"方案已被实测推翻，不要再用**
* 每帧调色板描边 —— 原版是 OBJ 调色板 index 15 逐帧改写（32 帧三角波）
* 4bpp/8bpp —— **4bpp 是存储格式不是输出格式**；覆盖层图砖在 tile 区（char base `0x8000`），
  改 8bpp 只多占 1 KB ⇒ **可能整块绕过引擎改动**（待 VRAM 预算实验证实）
* 逻辑状态 —— 原版 battle 14 名册、战后经验规则**已闭合**
  （`s49-battle-14-roster` 门禁 10 项全绿）
* 音频 —— **完全未覆盖**；原版是 MP2K（软件 PSG 合成），重制侧是 Maxmod

## 3. 工作纪律（项目既有规矩，必须遵守）

1. **一次只改一处，跑一次，记一行。**
2. **结论落进假设台账**：一行一个假设（判定方法 / 结果 / 状态 = 未验·已证伪·已确认）。
3. **连续 3 次同样结果 ⇒ 停**，换方法。
4. **不要信自述**：每个结论都要有可复跑的验收命令 + 落盘产物。
5. **自指排除**：写"清单"的文件不能算作"消费"证据。
6. **改一行尾符会毁掉 SHA-256 证据身份** ⇒ 新写文件一律 **LF、无 BOM**。

## 4. 产出与归属（**不要越界改别人的文件**）

| 目录 | 谁写 |
|---|---|
| `D:\Github\gba-naruto\notes\s49-fidelity\<stream>.md` | 对应 stream 独占 |
| `D:\Github\gba-naruto\tools\<本 stream 专属文件名>` | 对应 stream 独占 |
| `D:\Shell\Github\gba-naruto-butano\butano-sequel\game\**` | **只有产品代码 stream 能改**，且按文件分区 |
| `D:\Shell\Github\gba-naruto-reverse\**` | **只读** |

**报告格式**：每个 stream 写一份 `notes/s49-fidelity/<stream>.md`，
含「做了什么 / 改了什么（路径）/ 跑了什么验收 / 观察到的结果 / 假设台账 / 剩下什么 / 卡在哪」。

## 5. 环境

* WSL：`wsl -d Ubuntu-24.04 -- bash -lc "…"`（有 devkitARM 15.2.0、make 4.3、python3.12）
* 构建重制 ROM：WSL 里 `cd /mnt/d/Shell/Github/gba-naruto-butano/butano-sequel &&
  source /opt/devkitpro/devkitarm.sh &&
  export LIBBUTANOABS=/mnt/d/Shell/Github/gba-naruto-butano/third_party/butano/butano && make -j4`
  （**`LIBBUTANOABS` 必须显式导出**）
* CPU 长期只有 6% 占用 ⇒ **可以放心并行跑重活**

---

## 6. ⚠️ 2026-10-23 23:2x 新增：探针的**逐帧内存导出**能力（状态对拍用）

### 6.1 探针新增命令 `framedump`

```
framedump <count> <addr> <len> <keymask> <prefix>
```

跑 `count` 帧，**每帧之后**用 `core->busRead8()` 读一段内存并写成
`<prefix>-NNNN.bin`。这就是"状态对拍"要的仪器：
**像素差分只能说"这些像素不一样"，逐帧区域导出能说"第 412 帧这个 tilemap 项变了"**。

```powershell
# 从某个 walk 的存档起步，逐帧导出整块 VRAM
python tools/mgba_probe/probe_client.py --exe <probe.exe> `
    --rom <remake.gba> `
    --cmd "load build/s49-remake/step-14-A.ss9" `
    --cmd "framedump 24 0x06000000 98304 0x000 build/bg2full/v" `
    --out build/bg2full/result.json
```

### 6.2 ⚠️ mGBA 的 Lua 内存域**在游戏开始渲染后会失效**

实测（`tools/mgba_probe/probe_domains.lua`、`probe_vram_read.lua`）：

* 域清单：`bios / cart0..2 / io / iwram / oam / palette / vram / wram`
  （**没有 `ewram`**，EWRAM 叫 `wram`）
* `emu.memory["vram"]:readRange(...)` 在**脚本加载时**（还没跑帧）返回全 0，正常；
  **一旦游戏开始渲染，任何 `vram` 读取都抛 `Invalid object`**（256 / 4096 / 16384 /
  65536 / 98304 全部失败）。
* ⇒ **不要用 Lua 域读 VRAM**。用探针的 `framedump`（走总线读，实测可用）。

### 6.3 Lua 内存 API 的形状（踩过的坑）

* `readRange(offset, length)` 返回**字符串**，不是表 ⇒ 用 `string.byte(s, 1)` 取字节，
  直接 `file:write(s)` 落盘。
* 域是 **userdata**，`pairs(emu.memory)` 能列出域名。

### 6.4 探针构建：别和别人抢同一个 exe

子代理可能正在用 `build/mgba-probe/mgba-probe.exe`（链接会报 LNK1104 文件被占用）。
⇒ 用 `KONOHA_PROBE_OUT` 指向别的目录另建一份：

```powershell
$env:KONOHA_PROBE_OUT='D:\Github\gba-naruto\build\mgba-probe2'
python tools/mgba_probe/build.py
```

### 6.5 已建好的分析工具（master 仓，直接用）

| 工具 | 作用 |
|---|---|
| `tools/compare_frame_dirs.py` | 两目录同名 PNG 逐像素比（可 `--field-area` 裁剪战场区） |
| `tools/align_frame_dirs.py` | 交叉对齐距离矩阵（避免"按序号配对"的错位陷阱） |
| `tools/inspect_overlay_ground_truth.py` | 打印原版 BG2 地面真相的结构 |
| `tools/overlay_rule_vocabulary.py` | 打印原版覆盖层的**族词表**（六族 + 各自图砖号 + 四时刻计数） |
| `tools/find_overlay_map.py` | 在整块 VRAM dump 里按**图案相关**定位重制侧的覆盖层 map |
| `tools/compare_bg2_dump.py` | 逐格比较重制侧覆盖层与原版地面真相 |
| `tools/find_io_registers.py` | 在 dump 的 I/O 块里找显示寄存器 |

### 6.6 覆盖层地面真相（已提取，见 `F-overlay-ground-truth.md`）

原版 BG2：**4bpp · 独立 palette bank 12 · 32 块图砖 · 16×16 px 为一格**；
六个族 `blank / solid / edge / hatch / line_alt / band`，每族 4 个变体；
四个时刻的地面真相已导出（field / movegrid / grid16 / banner）。
重制侧：**8bpp · 与地图共用调色板 · 32×16 px 为一格 · 自造 6 类图砖**。
⇒ **形状不同，这就是 2,304 px + 600 px 残差的根因。**

**仍未决**（导出器自己记的 `overlay_semantics`）：
点亮的格到底是「可达范围高亮」还是「不可达范围压暗」，**从收据里判不出来**。
⇒ 谁把这四个时刻的族分布与重制侧当时的游戏状态对上，谁就拿到了规则。
