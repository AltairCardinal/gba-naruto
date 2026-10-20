# 主机游戏"原生移植"到 PC 的技术路线调查（2026-10-20）

调查日期：2026-10-20
性质：技术路线参考。与 `notes/love2d-android-porting-20261020.md` 属同一主题族（"移植"手法），
但**未对本仓库现有 ROM 逆向结论产生任何影响**；`docs/sequel-roadmap.md` 进度未变。

> **下游笔记**：`notes/native-port-case-studies-20261020.md` —— 四个代表性仓库的一手拆解
> （`999sian/melee-pc` / `ZeldaWWHDRecomp` / `peiikai/LASRecomp` / `ly05010419/MacNativeGames`），
> 说明反编译、静态重编译、原地 ARM64 改写三条路线在真实项目里的分工与差异。


## 0. 为什么要先拆概念

中文语境里"原生移植"被混用来指四种不同的东西，做法、成本、成熟度完全不同：

| 路线 | 机器码去留 | 是否需要原版 | 典型代表 |
|---|---|---|---|
| **A. 静态重编译** | 保留原机器码，**提前**离线翻译成本机指令 | 需要 | N64Recomp / LAS Recomp / ReXGlue / PS2Recomp |
| **B. 反编译 / 源码移植** | 丢掉原机器码，**恢复成 C/C++ 源码**再重编 | 需要（当"答案本"） | zeldaret/tp、Ship of Harkinian、Golden Balloon |
| **C. 模拟器 + 预重编译** | 游戏代码预编译，但 OS/图形仍由 HLE 模拟 | 需要 | suyu 0.0.4 Recompiler Mode |
| **D. 纯模拟器** | 全部运行时翻译（JIT/解释器） | 需要 | yuzu / Ryujinx（均已 DMCA 下架） |

A 和 B 才是"原生"。C 常被误宣传成原生，实际底下还是模拟器。

## 1. 路线 A：静态重编译（static recompilation）

### 1.1 核心思想

不反编译、不重写游戏逻辑，而是**把原游戏的机器码提前翻译成目标架构的代码**，再配一个"宿主机运行时"
去替代原硬件。游戏逻辑本身仍是任天堂/厂商写的原代码，只是换了执行环境。

关键区别（用 Switch → PC 举例）：

```
模拟器:    [Switch 游戏 ARM64 代码] --JIT 运行时翻译--> [x86-64]  每次运行都翻译，CPU 一直背着开销
静态重编译: [Switch 游戏 ARM64 代码] --离线翻译--> [C 代码] --编译--> [x86-64 本机库]  只翻译一次
```

### 1.2 完整管线（以 LAS Recomp / Savage Wind Recomp 的 README 为准，一手资料）

`SavageWindRecomp`（BOTW Switch→PC）的 "How it works" 原文：

> The game's AArch64 executables are **translated to C** (`tools/gen.py`) and compiled into a library next to the app.
> The runtime **replaces the Switch underneath it**: a **kernel** and the system services (IPC), the **NVN graphics API
> on top of Vulkan with a Maxwell shader translator**, and audio. This is **not emulation** of the console; the game's own
> code runs natively.

拆开就是五步：

1. **分析器**：反汇编、跟随控制流、识别 ARM/Thumb 互操作、解析直接与间接跳转表
   - 工具：**Capstone**（反汇编）、**Unicorn**（用模拟器跑一小段代码来解析跳转表）
2. **发射器**：把识别出的函数翻译成**可移植的、分片的 C++**（`recompiled_NNN.cpp`）
3. **编译**：用普通 C++ 编译器把生成的 C++ 和共享硬件运行时链接成库
   - 编译器用 **Zig 的 `zig cc`**（Clang + LLD）；Windows 侧走 MSYS2/UCRT64
4. **运行时（替代原硬件）**：
   - 内核 + 系统服务（IPC）
   - **NVN（Switch 私有图形 API）→ Vulkan** 转换层 + **Maxwell 着色器翻译器**
     （参考物：**Ryujinx 的 shader decoder** 作为指令字段布局参考，**envytools** 提供 NVIDIA GPU 文档）
   - 音频（Switch SDK 自带渲染器，含房间混响）
5. **着色器管线**：`shaderc`（GLSL → SPIR-V）、Vulkan Memory Allocator、SDL 3、Dear ImGui、SMAA、AMD FSR 1

### 1.3 用户侧体验

- 用户提供**自己主机导出的** `exefs/` + `romfs/`（`exefs` 含 `main` / `main.npdm` / `rtld` / `sdk` / `subsdk0`）
- 首次启动在**本机**执行重编译：`make gen` → 生成 C → 编译成 `build/lasgame.dll` / `swgame.dll`
  - BOTW 规模：**三个模块约 196,000 个函数**，12 线程 CPU 上首次 setup **约 40 分钟**，需要 **约 35 GB 磁盘**（romfs.bin 约 15 GB）
- 官方 release 包里**不含任何游戏代码/资源/key**，重编译在玩家自己机器上完成
- Switch 系统字体属任天堂 IP，**必须玩家自备**（可用替代字体）
- 项目定位普遍是 **"preservation / 存档保护"** 框架，工具开源（多为 MIT / GPL），游戏内容不开源

### 1.4 框架矩阵（全部经 GitHub API 核实，2026-10-20 快照）

| 框架 | 目标平台 | 语言 | star | 建仓 |
|---|---|---|---|---|
| `N64Recomp/N64Recomp` | N64 → PC | C++ | 8277 | 2022-11 |
| `Zelda64Recomp/Zelda64Recomp` | N64 莫吉拉/时之笛 → PC | C | 7482 | 2023-10 |
| `ran-j/PS2Recomp` | PS2 → PC | C++ | 3610 | 2025-04 |
| `peiikai/LASRecomp` | **Switch 织梦岛 → PC/macOS/Linux** | C + Python 生成器 | 1397 | 2026-10-08 |
| `rexglue/rexglue-sdk` | Xbox 360 → PC/Switch | C | 1131 | 2026-01-22 |
| `arcanite24/pinyon-shift` | Xbox360 极限竞速地平线 → PC | Python+ | 797 | 2026-08 |
| `snuri00/psp-web-recomp` | PSP → **WebAssembly**（HLE 内核 + WebGL2） | C++ | 367 | 2026-10-07 |
| `TeamGDB/Yakumo` | PSP → 原生 exe（Vulkan + SDL3） | C++ | 483 | 2026-09-18 |
| `bgyss/SwitchRecomp` | Switch 研究（preservation 导向） | **Rust** | 88 | 2026-01-29 |
| `kaiyao7/SwitchRecomp` | Switch 框架：decoder → typed IR → C codegen | C++ | 6 | 2026-10-08 |
| `caiocoswosk/paraglide` | Switch 静态重编译工具链 + 运行时 | C (MIT) | 0 | 2026-10-20 |
| `ioncodes/llvm8` | CHIP-8 → Win/macOS（LLVM 静态重编译**祖师爷**） | C++ | 99 | 2020-11 |
| `mstan/gbarecomp` | **GBA ROM → 原生应用** | C++ | 59 | 2026-05-25 |
| `sp00nznet/gbarecomp` | GBA 静态重编译工具包 | C (MIT) | 10 | 2026-03-17 |
| `Asphaltian/GBARecomp` | GBA ARM7TDMI → **C#** | C# | 2 | 2026-09-17 |

### 1.5 模拟器在静态重编译里到底扮演什么角色？（以 GBA 为例的实证）

**问：做 GBA ROM 的静态重编译，需要模拟器吗？**
**答：运行期不需要；硬件模型不可省；开发期的对照模拟器几乎不可替代。** 三层要分开看。

#### (1) 运行期：不需要

玩家跑的是重编译后的原生 exe，guest 指令不经过任何翻译/解释层。
框架原话（`src/runtime/runtime_arm.cpp`）："recompiled BIOS handles every SWI...
**the interpreter is NOT used in any game runner's hot path**"。

#### (2) 但"模拟器的仿真层"必须被等价实现——这才是真正的工程量

静态重编译 = **重写 guest 代码** + **重新实现硬件**。后半段本质上就是模拟器，只是去掉了翻译层。
框架的代码分布就是证据：

| 目录 | 规模 | 职责 |
|---|---|---|
| `src/armv4t/` | 17 文件 / 126 KB | ARM7TDMI 解码器、IR、分析器、**解释器**、C++ 生成 |
| `src/gba/` | 65 文件 / 530 KB | **硬件模型**：总线、PPU、音频、DMA、定时器、IRQ、BIOS、存档芯片、GPIO、陀螺仪、光照传感器、RTC |
| `src/runtime/` | 76 文件 / 1161 KB | 宿主侧调度、时钟、事件、调试、诊断回放 |

**为什么硬件模型不可省**：GBA 游戏代码与硬件是紧耦合的，不是"纯逻辑"：
- **VRAM/OAM 直写**——游戏不调"绘制函数"，它直接写内存地址决定画面；PPU 必须在正确时刻扫进帧缓冲
- **DMA 搬运**——音频与 VRAM 拷贝大量依赖 DMA 通道与时序
- **定时器 + VBlank IRQ**——主循环靠中断节拍驱动
- **周期数本身就是逻辑的一部分**——`wait` 指令与软循环时序依赖精确 cycle（生成码里的 `runtime_waits.s32[8]` 就是在追踪它）
- **BIOS SWI**——除法/sqrt/ArcTan/声音/软复位都走 BIOS

没有精确到周期的硬件模型，重编译出来的代码就是花屏或卡死。

#### (3) 框架内部的三层结构

| 层 | 组件 | 角色 |
|---|---|---|
| 主路径 | 生成的 C++（13,254 函数） | guest 逻辑，原生执行 |
| **兜底** | 解释器（`src/armv4t` 的 interpreter）+ **self-heal**（`heal_gate.cpp` / `self_heal_cluster.cpp`） | 静态分析没解出来的代码先解释执行，再被编译进**持久化原生缓存**（healing tier），之后即原生 |
| **真值** | `GBA_COSIM` 首次分歧对拍（`COSIM_ORACLE.md`）+ `reference-oracle` 工具 | 重编译版与解释器版同时跑，比对状态哈希找第一处分歧 |

所以"模拟器"在框架里有三个身份：**玩家不需要** / **框架内部必须有解释器** / **开发期需要外部模拟器当标尺**。

#### (4) 开发期为什么几乎离不开 mGBA

框架 `bios/README.md` 原文：
> "The LLE configuration statically recompiles and executes the actual BIOS. Keep it buildable and functioning as
> the **accuracy reference**... **independent emulators help diagnose shared hardware-model bugs**."

而且 `src/runtime/bios_hle.cpp` 的 SWI 语义就是**从 mGBA 的 `src/gba/bios.c` 移植过来的**（MPL-2.0）。
mGBA 既是行为真值，也是 HLE 实现的来源。

#### (5) BIOS 是唯一"真的需要模拟器产物"的地方——但有免 dump 的替代

- **LLE 路线**：把真实 BIOS 静态重编译进运行时 → **需要 BIOS dump**（16 KiB，SHA-1 `300c20df…`）
- **HLE 路线**：`bios_hle.cpp` 软件实现 SWI → **不需要 BIOS dump**
- 精度不同：HLE 的 cycle 成本是近似的（"LLE remains the timing oracle"），浮点/仿射类 SWI 走宿主浮点，低位可能与真 BIOS 不同

#### (6) 本项目的实证

- 我们用 mGBA trace 定位了 3 个关键 guest 地址，最终**跑起来的是原生 exe**；
  mGBA 只留在开发工具链里（`tools/mgba_probe/`）。
- 踩的坑恰恰是"模拟器视角"问题：
  - `0x08000B4C` 的 `bx r3` 跳进 `0x08000B00` 空白区——模拟器里能看出"跑到空白区"，
    但重编译要求**静态**确定跳转目标
  - `runtime_arm_default_aborts.cpp`（50 KB 的 abort 表）覆盖 `0x0800012C` / `0x08000130` 等
    ——未实现指令直接 abort，不静默出错
  - static 覆盖断在 `0x08002118`——这就是分析器的工作边界

### 1.6 已存在的游戏移植（Switch → PC，均已核实仓库存在）

| 游戏 | 仓库 | star | 语言 | 目标 |
|---|---|---|---|---|
| 织梦岛（Switch） | `peiikai/LASRecomp` | 1397 | C | Win/macOS/Linux，beta，可玩 |
| 宝可梦 Let's Go | `raulzrrs/letsgo-recomp` | 115 | C | 原生 Windows（基于 LAS Recomp） |
| 女神异闻录2 | `K0NL/B2recomp` | 237 | C | Windows |
| 塞尔达 风之杖 HD | `AsadSi/twilight-princess-hd-recomp` | 4 | C++ | macOS Apple Silicon，**Metal** |
| 密特罗德 究极形态 | `Apolinario-coder/SkyRecomp` | 296 | C | PC |
| 旷野之息（Switch v1.8.2） | `Revivedx/SavageWindRecomp` | 3 | C | Windows/Linux，**Alpha，不可玩全流程** |
| 幻影沙漏（3DS） | `dguillot-gh/phantom-hourglass-recomp` | 3 | C++ | PC + **Android** |
| 织梦少女（Switch） | `sonsegajp/HWDER` | 54 | C++ | 原生 Windows exe |
| 候选者2（Switch） | `swaymun/AC-Recomp` | 7 | Python | macOS（实验性） |

**Xbox 360 → PC**（ReXGlue 家族）：`pinyon-shift`(797★) / `SpeedBreaker`(418★) / `DownpourRecomp`（寂静岭，v1.0 稳定版，60FPS 解锁）/
`fm4-recomp` / `wwe-svr2011-pc` / `OpenTricky`（SSX Tricky）/ `DefJamFFNY-recomp` / `Dead_Rising_2_Case_Zero_Xenon_Recomp`
**Xbox 360 → Switch**：`prototype-switch` / `the-simpsons-game-nx` / `project8-sw` / `goon-nx`（都用 ReXGlue + 原生 Vulkan 渲染器）

### 1.7 静态重编译是怎么进行的（GBA 实例逐层拆解）

> 本节用 `mstan/gbarecomp` + 本仓库 `火影忍者 - 木叶战记` 的实测数据讲。

#### 1.7.0 总览：三阶段，一句话

**把「别人机器上的机器码」提前翻译成「我机器上的机器码」，并用自己写的「硬件模型」替代原硬件。**

```
[离线 · 一次]  ① 分析：反汇编 → 找函数边界 → 解控制流/跳转表 → 中间表示(IR)
[离线 · 一次]  ② 生成：IR → C/C++ 源码
[在线 · 零翻译] ③ 运行：编译成原生库 + 宿主程序 + 硬件模型
```

与模拟器的**唯一本质差别**：翻译发生在**运行前**还是**运行中**。
模拟器 = 运行时翻译（JIT/解释器），每帧都在付成本；静态重编译 = 产物已经是 x86 机器码，运行期翻译成本为零。

#### 1.7.1 阶段①：分析——最关键的一步

核心问题：**哪里是函数边界？哪里是跳转目标？**

**函数发现**（`src/armv4t/function_finder`）
- GBA 的调用约定：4 字节对齐 → ARM 状态；2 字节对齐且 bit0=1 → THUMB 状态
- 从**入口点**（向量表 `0x08000000`）出发做可达性分析：
  - `BL`（函数调用）→ 递归进入被调函数，成为新函数根
  - `B`（无条件跳转）→ 继续当前函数的下一个块
  - `BX/BLX`（间接跳转）→ **难点**：目标是寄存器值，静态不可知
- 框架按 `(addr, mode)` 给函数建键，所以 ARM 与 THUMB 可以同址共存

**跳转表（switch/jump table）**——GBA 上的头号大坑
- C 的 `switch` 编译成 ARM 后是「`cmp` + 一串条件分支 + 一张地址表」
- 框架用 TOML 描述表，本仓库 ROM 共发现 **51 张**：
  ```toml
  [[jump_table]]
  addr     = 0x08061C0C
  stride   = 4
  count    = 20
  ```
  框架据此读出表项，反推每个 case 块的入口地址，把它们并入所属函数

**RAM 拷贝模板（IWRAM/EWRAM copy）**——第二个大坑
- GBA 很多函数被从 ROM **拷贝到 IWRAM 再执行**（ROM 读太慢）
- 框架为此建了 **1,328 个"拷贝模板"**，描述「ROM 的哪段 → 按什么变换 → RAM 的哪段」
- 静态重编译必须**两处都生成**（ROM 原址 + RAM 目标址），且跳转目标要指向 RAM 那份
- 框架还自动发现并归并了 **98,861 条"中缀别名"→ 12,304 个宿主函数**（同一语义被编译器复制多份）

#### 1.7.2 阶段②：生成——每条指令降级成 1~3 条 C 语句

本项目生成码的真实样例（`recompiled_003.cpp`，一条 ARM 指令）：

```cpp
    /* 08000234  08000234 A orr r1,r1,r2 */
    {
    g_cpu.R[15] = 0x08000234u;                      // ① 显式写 PC
    if (runtime_should_yield()) return;             // ② 协作式让出点
    if (g_runtime_insn_trace) runtime_insn_fp();    // ③ 单指令追踪探针
    uint32_t _cyc_08000234 = 1u + (uint32_t)g_runtime_waits.s32[8];
                                                       // ④ 周期计数（含等待态）
    uint32_t _rm_08000234 = g_cpu.R[2];
    uint32_t _op2_08000234; uint32_t _co_08000234;
    _op2_08000234 = _rm_08000234;
    _co_08000234 = cpsr_c();                        // ⑤ 读 ARM 条件标志 CPSR
    uint32_t _rn_08000234 = g_cpu.R[1];
    uint32_t _r_08000234;
    _r_08000234 = _rn_08000234 | _op2_08000234;      // ⑥ 真正的运算
    ...
```

生成码**忠实保留**了这些东西，所以它才"跑得对"：
① **PC 显式赋值**——分支是"改 R15 + 跳过下一条"实现的，不是 C 的 `if/else`
② **yield 检查**——每条指令边界给宿主一个抢占点（帧切换、输入、存档）
③ **trace 探针**——可打开单指令级追踪，用于与模拟器对拍
④ **周期计数**——`runtime_waits.s32[8]` 追踪 EWRAM 等待态；`runtime_tick()` 推进全局时钟
⑤ **条件标志显式读写**——ARM 的 CPSR 标志位被建模成显式变量
⑥ **中间表示（IR）保真**——"decoder → typed IR → C codegen"，让同一语义的不同编码归一

**所以生成的 C++ 是"降级后的汇编"**，不是结构化源码：
函数名 `gf_afunc_080000C8`、局部变量 `_r_08000234`——**能看懂每条指令，但不好改**。

#### 1.7.3 阶段③：运行——硬件模型替代真机

1. 生成的 C++ 编译成静态库（本项目：**44.35 MB**）
2. 宿主程序链接：生成库 + 硬件模型 + 运行时
3. 启动：读 ROM → 装进总线的 ROM 区 → 读向量表 → 从 `0x08000000` 跳 entry
4. 每个时钟：CPU 原生执行 → 写 VRAM/OAM → PPU 扫描合成 → 帧缓冲 → 宿主窗口
5. 硬件模型（`src/gba/`，65 文件 530 KB）提供：PPU 扫描/混合/DMA 抓取、四声道音频、DMA 通道、定时器、IRQ、总线等待态、存档芯片、卡带外设（陀螺仪/光照/RTC）
6. 模拟器原本提供的一切，现在由这套模型提供——**唯一少了的是"翻译"**

#### 1.7.4 让它在工程上可行的关键：self-heal（自愈）

**不追求 100% 静态覆盖**：
- 静态分析没解出来的块 → 解释器（interpreter）执行
- 同时被**编译进持久化原生缓存**（healing tier）→ 下次就是原生速度
- `GBARECOMP_STRICT_STATIC=1` 可开启严格模式：第一个缺失的静态 PC 立即报错，不静默降级

这正是"静态重编译"能规模化的原因：**覆盖率不足不阻塞发布，只降级速度。**

#### 1.7.5 与相邻路线的取舍

| | 模拟器 | **静态重编译** | 反编译 |
|---|---|---|---|
| 保留什么 | 运行时翻译一切 | 保留机器码，**离线**翻译 | 丢弃机器码，还原源码 |
| 前期成本 | 最低 | 中 | 最高（以年计） |
| 后期可改性 | 低 | 中（改生成码 / mod hook） | 最高 |
| 运行性能 | 有翻译开销 | 原生 | 原生 |
| 覆盖 | 100% | 高但非 100%（self-heal 兜底） | 需人工补全 |
| 典型代表 | mGBA / yuzu | N64Recomp / LAS Recomp / gbarecomp | Ship of Harkinian / tp |


## 2. 路线 B：反编译 / 源码移植

把原游戏**还原成可读源码**再重新编译到现代平台。与静态重编译的取舍正好相反：
**前期极慢（要人工/AI 逆向出能匹配的源码），后期无限可改**。

- `zeldaret/tp` — **黄昏公主反编译**，C++，**CC0-1.0**，2097★，2020-08-29 建仓（对应 TakaRikka_ 2020-09 起步的说法）
  - 2025-12 宣布 100% 反编译完成；PC 移植版《Twilight Princess: Courage Reborn》进行中：60fps、Windows/Mac/Linux、键鼠+手柄、主菜单加图形设置
- `zeldaret/soh` — Ship of Harkinian（时之笛）
- Golden Balloon（DKR 反编译 → 源码移植）→ `boraeskicioglu/goldenballoon_nx` 反向移植回 **Switch 原生 ARM64**（libnx/devkitA64 + SDL2 + Mesa/OpenGL），
  社区评价："有源码的话移植只需几天"

## 3. 路线 C：模拟器 + 预重编译（**不是原生**）

`suyu` 0.0.4（Yuzu 分支的最后一版，已停更）加入 **Recompiler Mode**：
把 Switch AArch64 游戏代码**提前静态重编译**成原生 x86-64，配合 suyu 自己的 HLE 后端。

**但**：Switch 操作系统和图形 API 仍由翻译层处理——游戏代码不模拟了，底座还是模拟器。
开放世界受益最大（旷野之息、王国之泪、异度系列）。这条路对 PC 玩家是"门槛降低"，不是"原生移植"。

## 4. 塞尔达专项现状（2026-10-20 快照）

用户问的"NS 上的塞尔达"要分清楚代际——**Switch 世代的塞尔达原生 PC 移植基本都还没完成**：

| 游戏 | 原平台 | 方案 | 状态 |
|---|---|---|---|
| 莫吉拉的面具 / 时之笛 | N64 | 静态重编译 | ✅ **最成熟**（7482★） |
| 塞尔达传说 三角力量英雄 / 四 swords | GBA | 静态重编译 | ✅ 已有原生 Windows |
| 幻影沙漏 | 3DS | 静态重编译 | ✅ PC + Android |
| 贤者之息 | GBA | 静态重编译 | ✅（`MinishCapRecomp`） |
| 风之杖 HD | **Wii U** | 静态重编译 | ✅ → macOS(Metal) / → Switch(deko3d) |
| 织梦岛 | **Switch** | 静态重编译 | ✅ beta，可玩 |
| 黄昏公主 | **GameCube** | 反编译 | 🔄 Courage Reborn 进行中 |
| 密特罗德 究极形态 | **Switch** | 静态重编译 | 🔄 早期（`SkyRecomp`） |
| 旷野之息 | **Switch v1.8.2** | 静态重编译 | ⚠️ Alpha 1，**只能到主菜单+初始台地**，30fps，无 DLC |
| 王国之泪 | **Switch** | — | ❌ 未见静态重编译项目；只能 suyu/yuzu 模拟 + mod（如 TOTK Master Mode、Ultracam） |

## 5. 法律现实（不能忽略）

- 2024：任天堂就 **Yuzu** 达成 **240 万美元**和解（DMCA 反规避条款）
- 2026-02：任天堂再提 DMCA，下架剩余 Yuzu 仓库及至少 12 个 Switch 模拟器项目
- 2026-08：任天堂一天内用 **7 份 DMCA 通知清除 401 个 Switch 模拟器相关仓库**
- 所有重编译项目的统一法律姿态：
  - 仓库**不含**游戏文件 / 游戏代码 / 资源 / 字体 / key / BIOS / 解密工具
  - 用户**必须自带**合法导出的自己游戏
  - 重编译在**玩家自己机器上**完成；生成的代码"仅供自用，不要分享"
  - 框架本身开源（MIT/GPL），**游戏专属补丁不公开**
  - 定位多写作 "game preservation / archival"，而非 "commercial port"
- 但"自备 ROM"这套说辞 Yuzu 当年也用过，仍然被诉讼并和解。**技术上可行 ≠ 法律上安全。**

## 6. ⚠️ 对本仓库（GBA 火影忍者）直接相关的发现

`mstan/gbarecomp`（**R.A.I.D. — Retro AI Development** 社区，AI 辅助逆向）已经做出
**GBA ROM → 原生 C++ 应用**的通用静态重编译框架：

- `src/armv4t/` — ARM7TDMI 解码器、IR、分析器、解释器、C++ 代码生成
- `src/gba/` — 总线、PPU、音频、DMA、定时器、中断、BIOS、存档芯片、GPIO、陀螺仪、光照传感器、RTC
- `src/runtime/` — 原生调度、**持久化 self-healing 缓存**、宿主窗口/音频/输入、启动器接缝、mod、存档点
- 特性：**自适应宽屏**（最高 896×160，逐游戏自定义）、版本化 `.gbamod` mod 包、
  **Link Cable / Wireless Adapter 联机**（`recomp-net`，延迟同步 + 整局回滚）、
  5 种 GBA 屏幕色彩档案、存档点、宿主同步 RTC、运动控制、**Android arm64**、**WebAssembly 浏览器版**
- 未静态解析的代码**回落到解释器**，并被编译进持久化原生缓存（"healing tier"）——不成为正确性漏洞
- 硬件外设按原 GPIO/内存接口建模：Boktai 光照传感器、WarioWare 陀螺仪、S-3511A RTC、Shrek 的 64MiB Matrix Memory mapper
- 已集成游戏：Minish Cap / 超级马里奥 Advance 2、4 / 洛克人 Zero / 马车卡 / 精灵宝可梦 火红·叶绿·红宝石·蓝宝石·绿宝石 / WarioWare Twisted / 三款龙珠Z / Shrek GBA 影片
- 官方 CLI 用法：
  ```
  .\gbarecomp.exe build --rom "C:\Games\MyGame.gba" --output "C:\Projects\MyGameRecomp"
  ```
  生成物是**分片 C++ + 运行时头文件 + CMake**，**不是**可玩的 exe；还需要宿主程序、卡带配置、函数覆盖率验证、游戏专属适配。
- 重要原则（README 原文）："**Generated C++ is evidence, not authority**: if output is wrong, fix the analyzer/emitter and
  regenerate rather than editing generated files."——生成代码是证据不是权威，出错要改分析器而不是手改生成物。

**对续作规划的三点含义**：
1. GBA 原作若要"复活到 PC/移动端"，**不必手写重制**——把 ROM 静态重编译成原生 C++ 是一条已被验证的捷径，
   而且 `gbarecomp` 的 GBA 硬件运行时（PPU/音频/DMA/定时器/IRQ/存档芯片）就是现成的"目标平台抽象"。
2. 本仓库已做的 ROM 逆向（`notes/addresses.md`、`notes/battle-tables.md` 等符号与地址知识）正好是
   `gbarecomp` 的**符号导入（symbol import）工具链**需要喂进去的东西——逆向成果与移植工具是互补而非重复的。
3. 续作若是"原创重制"而非"移植"，`gbarecomp` 的 **adaptive widescreen** 与 **.gbamod mod 生态**是可直接借鉴的产品形态。

## 7. 调查方法与信息源

> **本项目实测**：`notes/gba-static-recomp-feasibility-20261020.md` —— 在本仓库的 GBA ROM 上
> 实跑 `mstan/gbarecomp`，实测 ROM→原生 x86-64 静态库全流程 **21 秒**（12,048 函数 / 61.7 MB 生成码 / 44.35 MB lib）。

- **GitHub API 是唯一可靠的一手来源**：`/search/repositories?q=topic:static-recompilation&sort=stars`、
  `/search/repositories?q=...in:name`、`/repos/{owner}/{repo}`、`/repos/{owner}/{repo}/readme`（raw 更省 token）
- **中文科技媒体（二次元快讯/腾讯新闻/游侠网等）在这题上大量出错**：
  例如某站称"Belmante 的 SMB 惊奇移植版在 `github.com/wonder-recompiled/wonder-pc`"——该仓库 API 返回 **404 Not Found**，
  且 GitHub 用户搜索显示 `Belmante` 账号只有 `Desafios-Sites` 和 `belmante.github.io` 两个仓库，
  **不含任何重编译项目**。这类"48 小时 3200 star"、"MIT 框架已开源"等具体数字**无法核实**。
  → 结论：**新闻稿只能当线索，仓库元数据才是证据。**
- 判别"某游戏是否有原生移植"的快查路径：
  1. GitHub 搜 `游戏名 + recomp` / `topic:static-recompilation` / `topic:game-port`
  2. 看 repo 的 `description`（社区惯例会写清 "static recompilation of X (Switch) to native Windows"）
  3. 看 `topics`（`recompilation` / `native-port` / `game-preservation` / `vulkan` / `x86-64`）
  4. 读 README 的 "How it works" 段——这���段最能说明是不是真静态重编译
- **AI 参与已成常态**：LAS Recomp 与 Savage Wind Recomp 的 README 顶部都明确写着
  "This project was made almost exclusively with AI... written by Anthropic's Claude, through Claude Code, directed, tested and reviewed by a human."
  塞尔达 TP 反编译（2020-09 起 5 年）与 R.A.I.D. 社区的 GBA 项目同属此趋势。
