# 本 ROM 静态重编译可行性实测（2026-10-20）

调查/实验日期：2026-10-20
性质：**实机实验**，非纸面推演。所有数字均为本机实测。
关联笔记：`notes/static-recompilation-native-port-20261020.md`（技术路线总览）

## 0. 结论速览

| 问题 | 答案 |
|---|---|
| 本 ROM 适合静态重编译吗？ | **适合**。ROM 结构标准、分析器零报错、生成代码可编译、无阻断性缺口 |
| ROM → 原生 x86-64 静态库要多久？ | **实测 21 秒**（分析 1.7s + configure 2.2s + 编译 19.6s） |
| 真正的工程量在哪？ | **不在重编译，在宿主程序**。框架已提供窗口/音频/输入/存档/联机/宽屏/mod/诊断，缺的是"卡带配置 + 符号表 + 游戏专属接线 + 稳定性" |
| 全部完成（可发布、可玩、有 mod 生态）用时 | 单人 **4–8 周**（AI 辅助）/ **3–6 个月**（纯手工）；见 §6 分解 |

## 1. ROM 本体核实

| 项 | 值 |
|---|---|
| 文件 | `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba` |
| 与 `rom/base.gba` 关系 | **SHA-1 完全相同**（`26f60795fa5e63b4f0264b84e453beffd56b9f7d`）→ base.gba 就是这份汉化版 |
| 内部标题 | `NARUTOKONOHA`（= "NARUTO"+"KONOHA" 截断，**原版日文标题**，非汉化组改的） |
| Game code | `AUEJ`（`A`=AGB，`J`=Japan 区） |
| 大小 | `0x600000` = 6 MiB / 48 Mbit |
| 头部 | 0xA0 标题、0xB2=`0x96`、0xB5=`0x00`（卡带）**均符合标准**；0xBE 补位校验 = `0x0E`，`gba_scan` 判定 `complement_valid=1`（**合法**，非零售原版值这一说法有误） |
| Logo | `gba_scan` → `logo_present=1`，任天堂 Logo 完好 |
| 存档芯片 | `gba_scan` → **`save_type=unknown`**（ROM 内无标准 SDK 签名）；本仓库 `rom/base.sav` = 32,768 字节 → 256 Kbit EEPROM |
| 指针映射 | file offset 与 ARM 地址 1:1（file `0x53D910` = ARM `0x0853D910`），见 `notes/resource-locations.md` |

**推论**：汉化是**原地打补丁**（文本 + 字模），代码布局未挪动 → 对静态重编译**有利**。
需要重新生成的是"汉化后"的那份代码，它本来就该被重编译。

> ⚠️ 陷阱：文件名含 `[熊组]`，PowerShell 的 `Get-FileHash -Path` 会把 `[]` 当通配符而**静默失败**。
> 必须用 `-LiteralPath`。本轮第一次取哈希就是这样丢了结果。

## 2. 实验环境

| 项 | 值 |
|---|---|
| 框架 | `mstan/gbarecomp` v0.2.0（`github.com/mstan/gbarecomp`），R.A.I.D. 社区（Retro AI Development） |
| 工具 | 预编译 Windows CLI `gbarecomp-cli-windows-x86_64.zip`（8.6 MB，358 次下载）——**不需要自建工具链** |
| 编译器 | MSVC 19.44.35228（VS 2022 BuildTools，`cl.exe`），C++20，`/O2 /bigobj /EHsc` |
| CMake | VS 自带 3.31.6-msvc6（`build.ps1` 会自动回退到它） |
| 机器 | 32 逻辑核 / 31.8 GB 内存（实测时空闲 8.4 GB） |
| Python | 3.14 |
| MSYS2 | **未安装**（框架官方推荐路径，但 MSVC 路径同样可编译生成库） |

## 3. 实测步骤与结果

```powershell
# 1) 取预编译 CLI
Invoke-WebRequest https://github.com/mstan/gbarecomp/releases/download/v0.2.0/gbarecomp-cli-windows-x86_64.zip -OutFile cli.zip
Expand-Archive cli.zip gbarecomp-cli

# 2) 补上框架头文件（CLI 的 _internal/framework 只有 2 个头）
Copy-Item gbarecomp-cli\_internal\framework gbarecomp-out\framework -Recurse

# 3) ROM -> C++ 源码
.\gbarecomp.exe build --rom rom\base.gba --output gbarecomp-out --force
# 4) 编译
cmake -S gbarecomp-out -B gbarecomp-out\build -A x64
cmake --build gbarecomp-out\build --config Release --parallel 8
```

### 3.1 分析阶段（1.7 秒）

```
==> loaded 0 seed symbols from (none)
==> discovered 12048 functions (arm=69 thumb=11979 indirect=2907 undefined=138 branch_targets=83722)
==> codegen shards: 8 (adaptive)
```

| 指标 | 值 |
|---|---|
| 发现函数 | **12,048**（ARM 69 / Thumb 11,979 / 间接 2,907 / 未定义 138） |
| 候选分支目标 | 83,722 |
| 静态降级指令 | **102,974** |
| 生成代码 | **61.72 MB / 1,679,482 行 / 8 个分片** |
| 附带 | `recompiled.h`（12,048 条前向声明）、`dispatch_table.cpp`（12,048 项）、`symbol_map.cpp` |

### 3.2 编译阶段（19.6 秒，exit=0）

| 项 | 值 |
|---|---|
| 单分片（208,227 行 / 8.03 MB） | **1.5 秒**，峰值内存 88 MB，产出 5.2 MB `.obj`（MSVC /bigobj 大对象格式，magic `00 00 FF FF 02 00 64 86`） |
| 全量 8 分片 + dispatch + symbol_map | **19.6 秒**（并行 8） |
| 产物 | `gbarecomp_game.lib` **44.35 MB** |
| 警告 | 仅 2 条 C4819（框架头文件含非 GBK 字符，与本仓库无关） |

### 3.3 覆盖率关键指标（对生成代码做静态统计）

| 指标 | 值 | 含义 |
|---|---|---|
| `runtime_unimplemented_op` | **8 处** | **codegen 真缺口**，运行到会 abort。占 102,974 条指令的 **0.008%** |
| `runtime_dispatch` | 17,141 处 | 间接分支，静态无法判定目标 → 查 12,048 项 dispatch table；查不到才回落解释器自愈 |
| `runtime_dispatch` 覆盖率 | dispatch table 含全部 12,048 个函数 | 绝大多数间接分支可解析到原生代码 |

**结论：静态覆盖率极高，不存在阻断性缺口。** 框架设计上是"诚实自愈"（PRINCIPLES.md）：
dispatch miss → 解释器桥接 → 现场重编译 → 显式日志。

### 3.4 生成代码的可读性（关键发现）

生成代码带**原 ARM 地址注释**，与本仓库 `notes/` 的地址体系完全对齐：

```cpp
/* 0x08068304  mode=thumb end=0x08068310 branches=2 */
void gf_tfunc_08068304(void) {
    ...
    g_cpu.R[15] = 0x08068306u;
    runtime_tick(_cyc_08068304);
    /* 08068306  08068306 T bne 0x08068314 */
    if (arm_cond_passes(0x1u)) { g_cpu.R[15] = 0x08068314u; gf_tfunc_08068314(); return; }
```

即：**每条 ARM 指令 → 一个 void C 函数内的 C 语句**，寄存器/条件码/周期计数都被建模。
本仓库已有的逆向结论（`notes/addresses.md`、`notes/battle-tables.md`、`notes/text-regions.md`）
可以直接对照到生成代码的每一行——这是本项目相对其他游戏移植的**最大优势**。

## 4. 框架已免费提供的部分（本地克隆实测规模）

`build/gbarecomp-src/`（含 submodule `rbengine` / `recomp-net` / SDL）：

| 目录 | 文件 | 行数 | 内容 |
|---|---|---|---|
| `src/armv4t` | 17 | 2,438 | ARM7TDMI 解码器 / IR / 分析器 / 解释器 / C++ 代码生成 |
| `src/gba` | 65 | 11,481 | 总线 / PPU / 音频 / DMA / 定时器 / IRQ / BIOS / 存档芯片 / GPIO / 陀螺仪 / 光照传感器 / RTC |
| `src/runtime` | 78 | 29,493 | 原生调度 + 持久化自愈缓存 + 宿主窗口/音频/输入 + 启动器 + mod + 存档点 + 回滚联机 |
| `src/debug` | 20 | 4,175 | 诊断回放（输入/检查点/帧指纹）、差分状态、宽屏验证 |
| `src/recompile` | 11 | 5,327 | 重编译/符号导入/参考 oracle |
| **合计** | **191** | **≈ 52,914 行** | 另有 71 个测试文件 |

**已内置能力**：自适应宽屏（最高 896×160，逐游戏设定上限）、版本化 `.gbamod` mod 包、
Link Cable / Wireless Adapter 联机（延迟同步 + 整局回滚）、5 种 GBA 屏幕色彩档案、
存档点、宿主同步 RTC、运动控制、**Android arm64**、**WebAssembly 浏览器版**。

## 5. 还差什么（每个游戏要自己写的）

以框架的参考游戏 `MinishCapRecomp` 的 `src/` 为标尺（实测文件大小）：

| 产物 | 大小 | 说明 |
|---|---|---|
| `src/main.cpp` | 3,861 B | 真正的入口：创建窗口、加载 ROM、跑主循环 |
| `src/game_config.cpp/.h` | 1,020 B | 游戏专属配置接线 |
| `src/game_launcher_boot.cpp/.h` | 1,360 B | 启动器 / 引导流程 |
| `src/minish_extended_view.cpp` | 27,620 B | 宽屏扩展（**可选**） |
| `game.toml` | 4,825 B | 卡带配置：ROM 校验、内存映射、入口、外设、存档芯片 |
| `symbols/*.tsv` | — | Ghidra 导出的符号表（喂给 `--symbols`） |
| `ghidra/` | — | Ghidra 脚本/工程 |
| `ISSUES.md` | **89 KB** | ← **"最后 10%" 的真实体量** |
| `mods/`, `tests/`, `tools/`, `docs/`, `recomp-ui/` | — | mod 生态、验证、工具、文档、启动 UI |

框架自己的 `docs/WINDOWS_GAME_SETUP.md` 明确写：
> "For a brand-new game, the next work is still developer work: make a game repo; add a real `main.cpp`;
> link the generated library to the GBARecomp runtime; add `game.toml` settings when the automatic scan is
> not enough; verify the exact ROM hash; test boot, input, sound, saves, and crashes.
> **Today, GBARecomp does not have a one-command 'make a full playable new game repo' tool.**"

## 6. 用时估算（全部完成 = 可玩 + 稳定 + 可发布）

| 阶段 | 内容 | 估时（AI 辅助） | 估时（纯手工） | 风险 |
|---|---|---|---|---|
| **0. 可行性验证** | 分析 + 编译出原生库 | ✅ **已完成（21 秒）** | ✅ | 无 |
| **1. 打通到出画面** | 建 game repo、main.cpp、链接框架、ROM 校验、入口、启动画面 | 3–7 天 | 2–3 周 | 低 |
| **2. 覆盖率补齐** | 8 处 codegen 缺口、17,141 个 dispatch 目标校正、符号导入 | 5–15 天 | 3–6 周 | **中**（间接分支表需逐个核对） |
| **3. 输入/音频/存档/演出** | 手柄映射、音频混音、SRAM 存档（`base.sav` 32 KB）、对话演出 | 5–10 天 | 2–4 周 | 中 |
| **4. 稳定性** | 崩溃、软锁、非法状态、边界、长时间挂机 | 10–30 天 | 2–3 个月 | **高**（对应 89 KB 的 ISSUES.md） |
| **5. 打磨与发布** | 宽屏、倍速、mod 生态、启动器、打包分发 | 5–10 天 | 3–6 周 | 低 |
| **合计** | | **约 28–72 人日 ≈ 4–10 周** | **约 4–8 个月** | |

**取中位建议**：**单人全职 6–8 周**（AI 辅助），**3–4 个月**（纯手工）。
若只求"能启动、能玩主线、存档能用"，**约 2–3 周**可交付。

### 影响估算的三个变量

1. **本仓库的逆向成果 = 巨大加速器**。`notes/` 里的地址表、场景表结构、战斗表、文本区、
   资源指针，恰好是阶段 2（符号导入 + dispatch 目标核对）最费时的输入。别的游戏项目这一步基本从零开始。
2. **汉化版的特殊风险**：需要确认汉化组是否**插入了代码**（如自造 CJK 文本渲染例程）。
   若只是替换文本+字模 → 零额外工作；若插了代码 → 那段代码也在 12,048 个函数里，照样被重编译，
   但要确认它依赖的数据（字模、码表）在 ROM 里且指针正确。**这是阶段 1 就要验的第一件事。**
3. **ROM 哈希会变**。本仓库 `rom/experiment-00076d.gba` 已被 writeback 实验改过（SHA-1 `383ADF1B…`）。
   任何一次 ROM 改动后都要**重跑一次生成**——但成本只有 21 秒，可忽略。

## 7. 对续作规划的实际含义（重要）

静态重编译产出的是**"原版的原生复活"**，**不是续作内容本身**。它与本仓库现有路线是**互补**：

| 路线 | 产出 | 现状 |
|---|---|---|
| 现有：mod 工具链（`tools/build_mod.py` + 文本写回） | 在原 ROM 里替换中文文本/对话/资源 → **续作内容** | 已跑通，是主线 |
| 新增：静态重编译 | 原版逻辑的**原生 x86-64/ARM64 实现** | 21 秒出静态库，尚缺宿主 |

静态重编译能提供的**具体增益**：

1. **一个现成的原生宿主**（窗口/音频/输入/存档/联机/回滚/宽屏/mod 框架），
   省掉续作在 PC/移动端重建引擎的成本。
2. **原版逻辑的可读 C++ 形态**（带地址注释），可与 `notes/` 逐条对照，
   为"把原版逻辑读懂再重写"提供**可执行的参考实现**。
3. **`tools/replay_diagnostic.py` 诊断回放**（输入 + 检查点 + 逐帧状态指纹，
   首次分叉帧即停）——比当前 mGBA 探针快一个量级，适合做续作的回归测试基座。
4. **mod 生态容器**（`.gbamod`）——若续作要走"官方安装 + 社区 mod"的形态，框架现成。

**建议的最小可行下一步**（约 1–2 天，可立刻验证）：

1. 建 `build/naruto-recomp/`（game repo 骨架：CMakeLists + main.cpp + game.toml）
2. 用框架运行时链接 `gbarecomp_game.lib`，跑最小 `main.cpp` → 看能否进启动画面
3. 同步验证汉化组是否插入了代码：对比 `base.gba` 与零售 JP 版的函数分布，
   或直接看生成代码里与文本渲染相关的函数行为

## 8. 重要文件位置

| 路径 | 内容 |
|---|---|
| `build/gbarecomp-cli/` | 预编译 CLI（`gbarecomp.exe` + `_internal/framework`） |
| `build/gbarecomp-out/` | **本 ROM 的生成工程**：`generated/`（8 分片 61.7 MB）+ `framework/` + `CMakeLists.txt` + `build/Release/gbarecomp_game.lib`（44.35 MB） |
| `build/gbarecomp-src/` | 框架源码 clone（含 submodule） |
| `build/gbarecomp-run.log` | 分析日志 |
| `build/gbarecomp-obj2/` | 单分片编译产物（5.2 MB obj） |

> `build/` 目录内容不入库（可由 §3 的命令完全重建）。

## 9. 复现命令（完整）

```powershell
$cli = 'build\gbarecomp-cli\gbarecomp.exe'
& $cli build --rom 'rom\base.gba' --output 'build\gbarecomp-out' --force
Copy-Item 'build\gbarecomp-cli\_internal\framework' 'build\gbarecomp-out\framework' -Recurse -Force
$cmake = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
& $cmake -S 'build\gbarecomp-out' -B 'build\gbarecomp-out\build' -A x64
& $cmake --build 'build\gbarecomp-out\build' --config Release --parallel 8
# -> build\gbarecomp-out\build\Release\gbarecomp_game.lib
```

## 10. 二次推进（2026-10-20 晚）：自建工具链 + 宿主接口 + 阶段 1 骨架

### 10.1 框架可从源码自建（17.9 **分钟**，墙钟实测）

> ⚠️ 本节标题原写作「17.9 **秒**」，是单位笔误。墙钟实测：`gbarecomp-src` 的
> `.git` 落盘 18:39:20 → `gba_recompile.exe` / `gba_scan.exe` 产出 18:57:14，
> 即 **17 分 54 秒**（含 clone + submodule + configure + 编译）。
> 其中 `cmake --build` 单独一段约 20 秒，其余是 clone/submodule 的网络与磁盘开销。

```powershell
git clone --depth 1 https://github.com/mstan/gbarecomp.git build\gbarecomp-src
git -C build\gbarecomp-src submodule update --init --depth 1 --recursive
$cmake -S build\gbarecomp-src -B build\gbarecomp-src\build-vs -A x64
& $cmake --build build\gbarecomp-src\build-vs --config Release --target gba_recompile gba_scan --parallel 16
# -> gba_recompile.exe (0.6 MB) + gba_scan.exe
```

### 10.2 两个工具版本的实测对比

| | 预编译 CLI v0.2.0 | 源码自建（main 分支） |
|---|---|---|
| 发现函数 | 12,048 | **12,978**（多 930） |
| 生成码体积 | 61.72 MB | **101.89 MB** |
| 静态库 | 44.35 MB | **54.14 MB** |
| 编译耗时 | 19.6 s | 32.1 s |
| RAM 拷贝模板 | 未提及 | **自动发现 1,350 条** |
| 分析耗时 | 1.7 s | 0.9 s |

→ **建议用源码自建的 main 分支**：函数覆盖更全，且支持「ROM→RAM 代码拷贝」自动识别。
预编译 CLI 只适合快速验证。

### 10.3 踩到的三个真坑（已修）

1. **生成码与框架头文件必须同版本**。
   用 v0.2.0 的 `framework/include/runtime_arm.h` 去编 main 分支的生成码 →
   `error C2440: "初始化": 无法从 "initializer list" 转换为 "int"`（dispatch table 结构体字段数不匹配）。
2. **main 分支头文件用相对路径引用子模块**：
   `src/armv4t/runtime_arm_types.h` 内含 `#include "../../external/arm-recomp-core/profiles/armv4t_gba/runtime_arm_types.h"`，
   所以头文件必须位于「根/src/armv4t/」这一层，且「根/external/」需存在。
3. **两个工具的输出布局不同**：
   * CLI `gbarecomp.exe build` → `out/generated/recompiled_*.cpp` + `out/CMakeLists.txt` + `out/build.ps1`（完整工程）
   * 自建 `gba_recompile.exe --out` → 文件**直接落在 out 根目录**，无 CMake 脚手架（需自备）

### 10.4 宿主程序接口（决定了阶段 1 怎么写）

框架**不提供**桌面游戏壳，那个在每个游戏仓库里。游戏二进制的形态是：

```cpp
// src/main.cpp
gbarecomp::RunOptions opts;
opts.builtin_game_name = "Naruto: Konoha Senki";
opts.builtin_rom_sha1  = "26f60795fa5e63b4f0264b84e453beffd56b9f7d";
opts.launcher_region   = "CN";
opts.launcher_game_config = "game.toml";
return gbarecomp::run_game(argc, argv, opts);
```

命令行约定：`Game [--bios <path>] [--rom <path>] [game.toml]`；
无窗口/脚本化运行用 `--no-window --frames N`（跳过启动器）。

### 10.5 ⚠️ BIOS 是硬门槛（无法绕过）

框架 `bios/README.md` 原文：

> The runtime **refuses to start** with a BIOS whose hash isn't recognized.
> This is the same gate the cartridge ROM goes through; both must verify.

所需：`gba_bios.bin`，16 KB，SHA-1 `300c20df6731a33952ded8c436f7f186d25d3492`。
这是任天堂版权代码，**只能由玩家从自己的主机导出**，不可代取。

候选路径：框架有 `src/runtime/bios_hle.cpp`（23.1 KB，从 mGBA `src/gba/bios.c` 移植的
SWI 软件实现，opt-in），理论上可替代 LLE BIOS；但**本轮未验证**本游戏在其下的启动表现。

### 10.6 已交付的阶段 1 骨架（`recomp/`）

| 文件 | 内容 |
|---|---|
| `recomp/README.md` | 现状、阻塞项、复现命令、五个坑 |
| `recomp/game.toml` | 运行时配置（ROM/BIOS 身份、入口 `0x080000C0`、存档 `eeprom`、显示、音频） |
| `recomp/config/naruto_konoha_senki.toml` | 重编译器配置（`[program]`/`[identity]`/`[[data_range]]`） |
| `recomp/src/main.cpp` | 游戏二进制入口（`run_game` 包装） |
| `recomp/CMakeLists.txt` | 链接框架 + 生成库 |
| `recomp/symbols/README.md` | 本仓库 `notes/` → 符号表/数据段的映射方案 |

`config/naruto_konoha_senki.toml` 的 `aot_scan_end = 0x080B9F80`
取自本仓库 `notes/resource-locations.md`：file `0x0B9F80` 是首个压缩资源
（battle map tileset gfx）的起始 offset，也是代码区与资源区的天然分界。

### 10.7 对用时估算的修正

阶段 1 的工作量**上调**，因为实测发现：
* BIOS 必须玩家提供（不影响工期，但影响可交付时点）
* 存档芯片自动识别失败 → 尺寸需人工确认
* 要用 main 分支就得自建工具链 + 手工补头文件依赖链
* 反过来，**`game.toml` 与重编译配置已由本仓库的逆向成果直接写好**，
  这是阶段 1 最费时的两块之一（其他游戏项目要从零做），可以显著压缩工期。

**修订后的建议：阶段 1 从 3–7 天调整为 4–8 天；总工期维持 4–10 周（AI 辅助）/ 4–8 个月（纯手工）。**

---

## 11. 突破：跑起来了（2026-10-20 20:00）

### 11.1 BIOS 到位

用户提供了自己主机导出的 `gba_bios.bin`（附件 `gba_bios.zip`），
校验通过：SHA-1 `300C20DF6731A33952DED8C436F7F186D25D3492`、MD5 `A860E8C0B6D573D191E4EC7DB1B1E4F6`、16,384 字节
——与框架 `bios/README.md` 要求的值**完全一致**。

### 11.2 最终可运行产物

| 项 | 值 |
|---|---|
| 可执行文件 | `build/naruto-recomp-build/Release/NarutoKonohaSenkiRecomp.exe`（20.9 MB） |
| 静态覆盖 | **13,254 个函数**（ARM 75 / Thumb 13,179 / 间接 3,519） |
| 静态函数占比 | 99.97%（仅 4 个 PC 仍走解释器） |
| 运行速度 | guest_fps ≈ 560（无窗口），≈ 600（窗口） |
| 渲染结果 | 调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024 **全部非零** |
| 中文渲染 | ✅ 汉字与像素美术均正确（见 §11.5 截图） |
| SDL 窗口 | ✅ 真实创建且可见（EnumWindows 确认 `[visible]`） |

**画面序列**（`--frames N --dump-png`）：

| 帧数 | 画面 | 文件 |
|---|---|---|
| 3,000 | 蓝色渐变（加载） | `shot_3000.png` |
| 10,000 | **鸣人手印立绘** | `shot_10000.png` |
| 20,000 | 立绘 + 中文名牌 | `frame20k.png` |
| 60,000 | 菜单按钮「发动」 | `shot_60000.png` |
| 150,000 | 渐隐回蓝 | `shot_150000.png` |

### 11.3 关键修复（按发现顺序）

1. **框架 main 分支不兼容 MSVC**：`bios_hle.cpp` 用 GCC 的 `__builtin_clz`。
   实测发现 **MSVC 19.44 的 `__builtin_clz` 只在 C 模式（.c）可用，C++ 模式（.cpp）不可用**。
   最终修法：`recomp/compat/msvc_builtin_clz.h` 用 **宏替换**而非同名函数。
   踩坑记录：
   * 定义同名函数 → 与 C 模式 intrin.h 的声明冲突 → 函数体被当成文件作用域裸块 → 一堆误导性错误
   * 用 `inline` → C89 模式下不是关键字 → 同样炸
   * 用 `static_cast` → C89 模式没有 → 同样炸
   * **头文件里放中文注释 → MSVC 按 GBK 码页读，破坏预处理器状态**（`#if` 不再是指令）
     → **force-include 的头文件必须纯 ASCII**（这条是最隐蔽的，错误行号完全对不上）
2. **必须静态重编译 BIOS（LLE），不能只靠 HLE**：
   只用 HLE BIOS 时，BIOS 的 IRQ 向量 `0x18` 落到解释器 → `runtime_irq: handler did not iret after 4000000 dispatches` → IRQ 循环卡死 → 画面全白。
   `gba_recompile --bios` 产出 770 个 BIOS 函数后链接进去，IRQ 正常，画面立刻出现。
   → **这是「白屏」的真凶，也是「原生移植必须连 BIOS 一起重编译」的实证。**
3. **复位向量必须进 `[[extra_func]]`**：BIOS 复位时跳到 `0x08000000`（ROM 里的 `b 0x080000C0`），
   之前把 `0x08000000-0x080000C0` 整段标成 data_range → finder 拒绝进入 → dispatch miss。
   修法：data_range 拆成 Logo(`0x04-0xA0`) + 头部字段(`0xA0-0xC0`)，复位向量单独用 `[[extra_func]]`。
4. **存档芯片是 SRAM 32 KB，不是 EEPROM**：
   框架各类型的有效尺寸是固定的（SRAM=32768 / EEPROM=512 或 8192 / Flash512=65536 / Flash1M=131072）。
   之前按 `base.sav` 大小推成 EEPROM 被拒：`save size 32768 is incompatible with EEPROM (expected 512 or 8192)`。
   `base.sav` 恰为 32768 字节 → **SRAM**。
5. **自愈重编译需要 TCC**：`gba_recomp` 的自愈层用 TinyCC 现场编译被桥接的函数；
   框架的 `tools/fetch_tcc.ps1` 负责拉取并暂存到 `<exe>/overlay_toolchain/`。
   缺 TCC → `tcc exit -1`；暂存后 → `tcc exit 1`（真编译错误）。
   又发现：暂存的 `overlay_toolchain/include/runtime_arm_types.h`（main 分支版）用相对路径引用子模块
   `../../external/arm-recomp-core/...`，在暂存目录下解析不到 → 需手动还原该目录结构。
6. **`[[data_range]]` 不能覆盖代码区**：曾把 `0x080B9F80-0x08600000` 整段标为数据，
   结果入口分支指向 `0x085CCC04`（crt0 启动模块）正好落在区间内 → 直接 abort。
   实测本 ROM 的布局是**代码与资源交错**的：
   * `0x080000C0-0x0803FFFF`：稀疏（146 函数）
   * `0x08040000-0x080BFFFF`：**主代码（12,789 函数，占 99.7%）**
   * `0x085C0000-0x085FFFFF`：**启动模块（crt0，入口分支目标 0x085CCC04）**
   * 其余为大块资源/数据

### 11.4 覆盖率演进

| 阶段 | dispatch miss | 解释执行指令数 |
|---|---|---|
| 初始（无 config） | 13 | 12,710,612 |
| 加 data_range + 复位向量 | 13 | 38,921,680（更慢，因多跑了 20k 帧） |
| **静态重编译 BIOS** | 13 | 12,710,612 → 画面出现 |
| **补入 8 个 ROM 侧 extra_func** | **4** | **3,516,074（-72%）** |

剩下 4 个 PC 全是 **IWRAM 运行时拷贝地址**（非 ROM 地址），
需要 `[[code_copy]]` 给 runtime_start → source_start 映射才能静态编译：

```
0x030006A4 (arm) x124032
0x030006B4 (arm) x124032
0x03000930 (arm) x18897
0x03005CE8 (arm) x124032
```

本仓库逆向笔记已证明该机制存在（`notes/dialogue-mapping-blocker-20260702.md`：
「0x0300007C-0x7F = 常量 0xE3A03301（ARM `MOV r3, #0xCC00` 指令）——这看起来像内嵌的 ARM 代码，不是数据」）。
→ **这是阶段 2 的主战场，且本仓库的既有逆向成果正好是破局钥匙。**

### 11.5 复现

```powershell
# 端到端（BIOS + ROM + 编译 + TCC 暂存 + 跑 + 出图）
cd recomp
.\build.ps1 -Bios .\bios\gba_bios.bin -Rom ..\rom\base.gba -Frames 20000
```

产物：`build\naruto-recomp-run\shot_20000.png`

### 11.6 结论修正

上一节估的「阶段 1 = 4–8 天」**偏保守**。实际从「零进度」到「画面正确」，
本轮实打实用掉的是：**BIOS 校验 → 工具链自建 → 3 轮配置修正 → 5 轮编译 → 3 轮运行定位**，
核心难点全在**框架与本 ROM 的适配**（BIOS LLE、向量表、SRAM 尺寸、IWRAM 拷贝），而非移植本身。
→ 阶段 1 修正为 **2–4 天**（有本仓库逆向成果兜底时）。

### 11.7 后续

产物可改性（改数据 / 改函数 / 发 mod 包）的完整分析见
`notes/recomp-modification-surfaces-20261020.md`。

---

## 12. 实测工期锚点（2026-10-20 深夜，用技能包评测实测）

§6 与 §11.6 的估时是"排期级"的。技能包评测提供了一组**墙钟级**的实测锚点，
可以用来校准"再做一个 ROM 要多久"。

### 12.1 三段实际墙钟

| 段落 | 起止（2026-10-20） | 墙钟 | 干了什么 |
|---|---|---|---|
| 主线实战 | 10:21 → 19:24 | **≈ 9 h** | 从零探索到第一张画面正确（大量试错 + 反复重跑） |
| 框架自建 | 18:39 → 18:57 | **18 min** | clone `gbarecomp-src` + 补头文件依赖链 + CMake + 编出 `gba_recompile.exe` |
| baseline 评测（**无技能**） | 22:30:49 → 22:55:39 | **25 min** | 从零做到「出画面 + 像素一致」，但停在 **4 个 dispatch miss** |
| with-skill 评测（**有技能**） | 22:30:49 → ≈23:20 | **≈ 49 min** | 同样出画面，**并做到 100% 静态覆盖（0 miss / 0 解释指令）** |

两个评测 agent **同时启动、同一台机器、同一份 ROM/BIOS、同一个任务**，
所以差异（25 min vs 49 min）就是"技能 + 逆向方法论"带来的净增量：
多花 24 分钟，换来覆盖缺口从 4 清到 0。

### 12.2 机器时间 vs 判断时间（with-skill 那 49 分钟的分解）

机器执行部分（3 轮迭代 + 4 个帧点验证）：

| 动作 | 墙钟 |
|---|---|
| BIOS 静态重编译（770 函数） | 0.1 s |
| ROM 静态重编译（13,271 函数 / 103 MB C++） | 13.8 s（冷启动） |
| MSVC 编译 + 链接（8 分片 → 22.9 MB exe） | 42 s |
| 跑 20,000 帧 | 33–37 s |
| 4 个帧点验证（3k/10k/20k/60k） | 158 s |
| **机器时间合计** | **≈ 8–10 min** |

**判断时间 ≈ 39 min**：写 TOML 配置、定位 4 张 IWRAM 拷贝表、反汇编读函数头、
判断"这个残留 PC 是 ROM 地址还是 RAM 重定位地址"。

→ **瓶颈是逆向判断，不是算力。** 一轮完整迭代的机器成本只有 ~91 s，
任何"多跑几轮试试"的策略都是廉价的；真正贵的是"这一轮该改什么"。

### 12.3 由锚点外推的工期（以木叶战记为参照）

| 起点条件 | 到「出画面」 | 到「100% 静态覆盖」 |
|---|---|---|
| 框架/技能/配置全就绪（换个 ROM，逆向结论已有） | **15–30 min** | **1–2 h**（若该 ROM 也有 RAM 重定位代码，需重做一次逆向） |
| 框架在位、无技能包（= baseline 的处境） | **≈ 25 min**（实测） | **数小时–1 天**，且极易把根因归错 |
| 框架也要自建（= 18:39 那次的处境） | **0.5–1 天** | **1–2 天** |
| 陌生 ROM、无任何前置逆向 | 1–3 天 | 2–5 天 |

### 12.4 但要分清两个完全不同的"完成"

- **静态重编译本体**（ROM → 原生可执行文件 + 100% 静态覆盖 + 像素级一致出图）
  → **木叶战记已达成**，剩余缺口 **0**，再投入是 0。
- **可发布的产品**（稳定、可玩、存档往返、音频保真、输入回放、mod 生态）
  → 仍是 §6 的 **4–8 周（AI 辅助）/ 4–8 个月（纯手工）**，与上面无关。

不要把这两个数混用：静态重编译只解决了"把原版逻辑变成原生机器码"这一步，
产品化的工作量在宿主层与内容层。

### 12.5 这批数据的出处

- baseline 报告：`C:\Users\feeli\AppData\Local\Temp\eval-gba-static-recomp\baseline.md`
- with-skill 报告：同目录 `with-skill.md`
- 产物：`build/eval-baseline/`、`build/eval-with-skill/`（含 5 个 IWRAM 探针脚本）
- 技能包：`dist/gba-static-recomp/` + `dist/gba-static-recomp.zip`




---

## 13. 正式工程收口（2026-10-21）：`recomp/` 达到 100% 静态覆盖 + Stage-2 自愈层修复

前面 §11 的产物停在「13,254 函数 / 4 个解释器桥接」，
§12.1 记录的两个评测 agent 把覆盖补到了 0——但成果当时只在**评测 scratch 目录**里，
正式工程 `recomp/` 本身没跟上。这一节是收口记录。

### 13.1 对象确认

`rom/base.gba` 与用户那份 `火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba`
**SHA-1 完全相同**（`26f60795fa5e63b4f0264b84e453beffd56b9f7d`，6,291,456 字节），
确认编译对象就是这份汉化 ROM，没有编译错版本。

### 13.2 配置归位

`recomp/config/naruto_konoha_senki.toml` 从 9 个 `[[extra_func]]`
扩到 **22 个 `[[extra_func]]` + 4 张 `[[code_copy]]` + 3 块 `[[data_range]]`**，
把 §12 的 IWRAM 重定位映射（含 `source_addr`）正式写进工程配置，
并在文件里写清了机制与定位方法。

### 13.3 最终指标（`recomp/` 端到端重建实测）

| 项 | 值 |
|---|---|
| 静态函数 | **13,271** / 8 分片 / 103 MB 生成 C++ |
| 静态覆盖 | **`FULLY_STATIC`**：`dispatch_misses=0`、`interpreted_insns=0`、`healed_native=0` |
| BIOS 后端 | `LLE (recompiled BIOS)`（770 函数） |
| 渲染 | 调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024 |
| exe / 静态库 | 22.9 MB / 58.2 MB |
| **画面一致性** | 20,000 帧 PNG 与 `recomp/screenshots/03-chinese-nameplate-20000frames.png` **SHA-256 逐字节相同**（`A84AA75C…E7BC25`） |
| 确定性 | `final_pc=0x0806112c`、`cycles=62191750` 每个帧点一致 |
| 端到端重建 | **100 秒**（BIOS 重编译 → ROM 重编译 → 8 分片编译 → 链接 → 跑 20,000 帧） |

两条运行路径都验证：
- 无窗口 `--no-window --dump-png` → `FULLY_STATIC`
- SDL 窗口 `--window` → `renderer=direct3d11`、`frames_presented=900`、真实 720x480 窗口、`FULLY_STATIC`

### 13.4 流水线修缮（三处「能跑但不对」）

1. **`recomp/CMakeLists.txt` 分片被编两遍**
   `add_executable` 里重复列了 `${GENERATED_SOURCES}`，同一批 11–14 MB 分片
   在静态库和 exe 里各编一次 → 构建时间翻倍。exe 只需链接 `gbarecomp_game`
   （dispatch table 引用了全部函数，链接器会自己拉进来）。同时补上 `/bigobj`
   （否则 COFF 段数超限 C1128）。
2. **tcc 热缓存把覆盖标签搞脏**
   框架判 `FULLY_STATIC` 的条件是 `misses==0 && healed==0 && interp==0`，
   而上一轮留下的 overlay 热缓存会被加载成 `healed=1` → 明明 0 miss 却报 `NOT_STATIC`。
   **活证据**：运行目录 `recomp_cache/` 里躺着 10-20 19:17–19:27 的旧 overlay 残留。
   `build.ps1` 现在把 `GBARECOMP_HEAL_CACHE` 指到独立目录，
   且**按配置内容哈希**再分一层（框架的缓存子路径只按 ROM sha1 分，
   同一 ROM 的不同配置会共用同一批 overlay，用对照配置做实验会污染正式构建）。
3. **运行日志不落盘**
   `build.ps1` 现在把 stdout 写成 `run_<frames>.out`，构建结束自动打印覆盖率指标。

### 13.5 Stage-2 自愈层修复（上游框架缺陷，本工程绕过并修复）

§11.6 把残留 4 个 PC 的根因归到「overlay ABI 缺 resume_pc 通道」，
§12 又证明那个归因是错的（真实原因是 IWRAM 重定位）。
但**另一条独立的缺陷**确实存在：**Stage-2 自愈层在框架原版是断的**。

根因是三件事凑不齐：

| # | 缺口 | 症状 |
|---|---|---|
| 1 | overlay 的 shim `overlay_runtime_arm.h` 没声明 `g_runtime_resume_pc`（静态语料有 `runtime_arm.h` 声明，overlay 没有） | `tcc: error: 'g_runtime_resume_pc' undeclared` |
| 2 | overlay 是 DLL，要访问宿主符号只能走导入表；框架的 tcc 命令行既不带宿主 exe，声明也没有 `__declspec(dllimport)` | `undefined symbol 'g_runtime_resume_pc'` / `… missing __declspec(dllimport)?` |
| 3 | 宿主 exe 默认没有导出表 | DLL 加载时也解析不到该符号 |

**定位方法**（可复现）：把框架生成的 overlay `.c` 和编译日志从自愈缓存里捞出来，
逐个错误信息试边界。实测矩阵：

| 声明 | 命令行带宿主 exe | 结果 |
|---|---|---|
| 无 | 否 | `'g_runtime_resume_pc' undeclared`（编译期） |
| 有（无 dllimport） | 否 | `undefined symbol 'g_runtime_resume_pc'` |
| 有（无 dllimport） | 是 | `undefined symbol 'g_runtime_resume_pc', missing __declspec(dllimport)?` |
| 有（`__declspec(dllimport)`） | 是 | **链接成功**；`dumpbin /imports` 显示 `NarutoKonohaSenkiRecomp.exe` / `g_runtime_resume_pc` |

**修法与归属**（本工程承担两件，框架只占一件）：

| 环节 | 归属 | 做法 |
|---|---|---|
| shim 的 `__declspec(dllimport)` 声明 | 本工程 | `build.ps1` 在**暂存副本**（`overlay_toolchain/include/`）上打补丁——框架本来就提供摊平机制，运行时在 `GBARECOMP_HEAL_BACKEND=auto-no-gcc` 下用这份副本。对上游零侵入、可随构建重新生成、幂等 |
| 宿主 exe 导出符号 | 本工程 | `CMakeLists.txt` 的 `/EXPORT:g_runtime_resume_pc`（链接时产出 `.exp`） |
| tcc/gcc 命令行带宿主 exe | 框架 | `recomp/patch-gbarecomp-overlay.ps1` 给 `overlay_compile.cpp` 打补丁。**幂等**；三个锚点任一对不上就直接抛错，不会静默跳过 |

**实测效果**（用去掉 `[[code_copy]]` 的对照配置强制制造 4 个缺口，
`GBARECOMP_RAM_OVERLAY_HEAL=1` 开启 RAM 自愈）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `failed`（overlay 编译失败） | 4 | **0** |
| `healed_native` | 0 | **6** |
| `interpreted_insns` | 3,516,074 | **0** |
| `native_calls` | 0 | **602,065** |
| guest_fps | 547 | 573 |
| 产出的 overlay DLL | 0 | 6 个（4,096–8,192 字节） |

→ 修复后即使静态覆盖有缺口，自愈层也能把缺口**全部原生化**，
解释器一条指令都不执行。正式配置 0 缺口，这条路不会被触发，
但它是工程对未来新缺口的兜底。

### 13.6 还剩什么

| 项 | 状态 |
|---|---|
| 静态覆盖缺口 | **0** |
| 解释器参与 | **0 条指令** |
| Stage-2 自愈兜底 | **可用**（实测 6 个缺口全部原生化） |
| `unmapped=1` | boot 阶段一次未映射访问，固定位置，无实际后果 |
| `frames_presented=0`（无窗口） | 正常值；窗口模式为 900 |
| MP2K 影子混音 DEGRADED（相关性 0.39） | 框架自动回退硬件混音，只影响音频保真度 |
| 16 字节步长的跳转表（`0x08063696/B4/C0`） | 已用 3 条 `[[extra_func]]` 覆盖，无 miss；可进一步合并成一条 `[[jump_table]]` |
| 存档存读往返 / 输入回放 / 长时间稳定性 | 未测（属产品化范畴，见 §6） |
