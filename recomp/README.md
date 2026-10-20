# recomp/ — 火影忍者：木叶战记 静态重编译移植工程

用 `mstan/gbarecomp` 框架把本仓库的 GBA ROM **静态重编译成原生 C++ / x86-64**，
产出可在 PC 上运行的原生版本（可带 mod、宽屏、联机）。

> **状态：已完成 —— 静态覆盖 100%。**
> `self_heal_coverage=FULLY_STATIC`，`dispatch_misses=0`，`interpreted_insns=0`。
> 无窗口与 SDL 窗口两条路径都能运行并正确渲染中文画面；
> 20,000 帧的输出与仓库既有参考截图 **SHA-256 逐字节相同**。

## 目录

| 路径 | 说明 |
|---|---|
| `game.toml` | **运行时配置**：ROM/BIOS 身份、入口、存档芯片、显示、音频 |
| `config/naruto_konoha_senki.toml` | **重编译器配置**：`[program]` / `[identity]` / `[[data_range]]` / `[[extra_func]]` / `[[code_copy]]` |
| `src/main.cpp` | 游戏二进制入口（声明游戏身份 → 交给 `gbarecomp::run_game()`） |
| `compat/msvc_builtin_clz.h` | MSVC 兼容 shim（**必须纯 ASCII**，见文件头说明） |
| `patch-gbarecomp-overlay.ps1` | 给框架 `overlay_compile.cpp` 打补丁（让 overlay 链接宿主 exe）。**幂等**；锚点对不上会报错 |
| `build.ps1` | **端到端构建脚本**（BIOS → ROM → 编译 → TCC → 打补丁 → 运行出图 + 落日志 + 打印指标） |
| `bios/gba_bios.bin` | 玩家自己主机导出的 BIOS（**不入库**，`.gitignore` 已挡） |
| `symbols/` | 符号导入（待建）：从本仓库 `notes/` 的地址表导出 TSV |
| `generated/` | 重编译产物（由工具生成，不入库） |
| `screenshots/` | 各帧点的画面基准（**由 100% 静态覆盖版本产出**） |

## 快速开始

```powershell
# BIOS 放到 recomp\bios\gba_bios.bin（自己主机导出，16KB，SHA-1 300c20df…d3492）
cd recomp
.\build.ps1 -Bios .\bios\gba_bios.bin -Rom ..\rom\base.gba -Frames 20000
# 产物：..\build\naruto-recomp-run\shot_20000.png
#       ..\build\naruto-recomp-run\run_20000.out（运行日志，含覆盖率指标）
```

只跑不编译：

```powershell
cd ..\build\naruto-recomp-run
..\naruto-recomp-build\Release\NarutoKonohaSenkiRecomp.exe `
    --rom roms\naruto_konoha_senki_cn.gba --bios bios\gba_bios.bin `
    --frames 20000 --no-window --dump-png shot.png
```

## 实测结果（2026-10-21 重建复核）

| 项 | 值 |
|---|---|
| 可执行文件 | `build/naruto-recomp-build/Release/NarutoKonohaSenkiRecomp.exe`（**22.9 MB**） |
| 静态库 | `gbarecomp_game.lib` 58.2 MB |
| 静态函数 | **13,271 个** / 8 分片 / 103 MB 生成 C++ |
| **静态覆盖** | **`FULLY_STATIC`——`dispatch_misses=0`、`interpreted_insns=0`、`healed_native=0`** |
| BIOS 后端 | `LLE (recompiled BIOS)`（770 个函数静态重编译） |
| 渲染 | 调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024 全部非零 |
| 中文渲染 | ✅ 汉字与像素美术均正确 |
| SDL 窗口 | ✅ 真实创建且可见 |
| guest 速度 | ≈ 540–600 fps（无窗口） |
| 确定性 | `final_pc=0x0806112c`、`cycles=62191750` 在每个帧点一致 |
| **端到端重建耗时** | **100 秒**（BIOS 重编译 → ROM 重编译 → 8 分片编译 → 链接 → 跑 20,000 帧） |

画面序列：3,000 帧＝蓝色渐变（加载）→ 10,000 帧＝**鸣人手印立绘** → 20,000 帧＝立绘+中文名牌
→ 60,000 帧＝菜单「发动」→ 150,000 帧＝渐隐回蓝。

**画面正确性的最强证据**：20,000 帧导出的 PNG 与 `screenshots/03-chinese-nameplate-20000frames.png`
**SHA-256 完全相同**（`A84AA75CF892DB36E4EA3DEAA6073CE9987A4625D57E48305F0522E519E7BC25`）。
这同时证明画面正确**且重编译是确定性的**——同一份 ROM 每次生成同样的机器码。

## 覆盖率是怎么补齐的（阶段 2 已完成）

早期版本卡在 4 个解释器桥接 PC：

```
0x030006A4 (arm) x124032      0x030006B4 (arm) x124032
0x03000930 (arm) x18897       0x03005CE8 (arm) x124032
```

**它们不是 ROM 地址。** 游戏在启动时把 ROM 里的一段热代码**重定位到 IWRAM**
（GBA 上 IWRAM 比卡带快），再通过 IWRAM 里的函数指针表间接调用。例如 ROM `0x080004C8`
的跳板做的是「从 IWRAM 指针槽取出目标地址再跳过去」，所以运行期出现的 `0x03000680`、
`0x03005CE8` 是**重定位后的地址**。重编译器按卡带地址去取字节当然取不到 →
`runtime_dispatch` miss → 退化成解释器桥接。

正确解法是**配置层面**给映射（不需要动 overlay ABI，也不需要给 exe 加 `/EXPORT`）：

| 运行期 | ROM 源 | size | 内容 |
|---|---|---|---|
| `0x03000680` | `0x080004C8` | `0x200` | stub 跳板模块 |
| `0x0300088C` | `0x08000520` | `0x0A4` | 同一模块的第二份拷贝 |
| `0x03000930` | `0x080005AC` | `0x060` | 算术 helper |
| `0x03005CE8` | `0x08000638` | `0x05C` | 表查找 helper |

配 `[[code_copy]]`（区间映射）**加上** `[[extra_func]]` + `source_addr`（函数入口）：
生成代码保留**运行期 PC**，却从 **ROM 源**取字节。两者必须配套，缺一个都会继续报 miss。

定位方法（四步法）与可复现工具见
`notes/static-recomp-iwram-code-copies-20261020.md` 与 `build/eval-with-skill/tools/`。

> ⚠ 曾经的错误归因：「这 4 个 PC 是 overlay ABI v6 缺 resume_pc 访问口导致的，自愈编译器救不了，
> 要升 ABI 或给 exe 加 `/EXPORT`」。**这是错的**——那是「ABI 缺通道」的解法，不适用于本症状。

## 踩过的坑（务必记录）

1. **必须静态重编译 BIOS（LLE），不能只靠 HLE**。只用 HLE 时 BIOS 的 IRQ 向量 `0x18`
   落到解释器 → `runtime_irq: handler did not iret` → IRQ 循环卡死 → 全白屏。
2. **force-include 的头文件必须纯 ASCII**。MSVC 按系统码页（936/GBK）读源文件，
   头文件里的中文注释会被误解码，破坏预处理器状态（`#if` 不再是指令），
   报错行号完全对不上，极难定位。
3. **不能定义同名 `__builtin_clz` 函数**（与 C 模式 intrin.h 的声明冲突 → 函数体被当成裸块），
   也不能用 `inline` / `static_cast`（C89 模式下不存在）。最终用宏替换。
4. **`[[data_range]]` 不能覆盖代码区**。本 ROM 是**代码与资源交错**布局：
   主代码 `0x08040000-0x080BFFFF`，启动模块在 `0x085C0000+`。
   曾把 `0x080B9F80-0x08600000` 标为数据 → 入口分支指向 crt0 正好落在区间内 → 直接 abort。
5. **复位向量 `0x08000000` 必须 `[[extra_func]]`**，且 data_range 要避开它
   （Logo `0x04-0xA0`、头部字段 `0xA0-0xC0` 分开标）。
6. **存档芯片是 SRAM 32 KB**，不是 EEPROM。框架各类型尺寸固定：
   SRAM=32768 / EEPROM=512 或 8192 / Flash512=65536 / Flash1M=131072。
   `base.sav` 恰为 32768 字节。
7. **自愈重编译需要 TinyCC**：`tools/fetch_tcc.ps1` 拉到 `<exe>/overlay_toolchain/`；
   暂存后还要手动还原 `external/arm-recomp-core/profiles/armv4t_gba/runtime_arm_types.h`
   的目录结构（main 分支头文件用相对路径引用子模块）。
8. **两个工具的输出布局不同**：CLI `gbarecomp.exe build` 给完整工程（`generated/` + CMake + build.ps1）；
   自建 `gba_recompile.exe --out` 把文件直接放根目录，**无 CMake 脚手架**。
9. **生成码与框架头文件必须同版本**（混用 → `error C2440` dispatch table 结构体字段不匹配）。
10. **PowerShell 的 `[]` 是通配符**：`Get-FileHash -Path '火影忍者 - 木叶战记[熊组]...gba'` 会**静默返回空**，
    必须用 `-LiteralPath`。
11. `D:\Github` 是指向 `D:\Shell\Github` 的 **Junction**，日志里会出现 `D:\Shell\Github\...` 路径，属正常。
12. VS 多配置生成器把可执行文件放在 `<build>/Release/`，不是 `<build>/`。
13. **`.ps1` 必须是 UTF-8 with BOM**。PowerShell 5.1 读无 BOM 的 `.ps1` 会按 ANSI(GBK) 解码，
    中文注释的乱码会吃掉引号，直接报 `ParserError`（报错位置还指向不相干的行）。
    本仓库的 `build.ps1` / `src/main.cpp` 均已带 BOM；
    改这两个文件时若用工具重写，**务必保留 BOM**（否则脚本会挂、C++ 源会被误读成 GBK）。
    这与坑 #2 是同一个根因：**非 ASCII 内容 + 错误的解码假设 = 静默的结构破坏**。
14. **PowerShell 5.1 下 `$ErrorActionPreference='Stop'` 会把原生命令的 stderr 变成终止性错误**。
    `gba_recompile` 会把 `[finder] callback byte-domain call-site analysis budget exhausted`
    这类**警告**写进 stderr（退出码仍是 0，产物正常），脚本却会误判为失败而中断。
    正确做法：用 `Invoke-Native` 封装，调用期间把错误偏好降为 `Continue`，
    **只看 `$LASTEXITCODE` 判断成败**。（`build.ps1` 已按此实现。）
15. **同一批分片被编两遍会让构建时间整整翻倍**。若 `add_executable` 里也列了
    `${GENERATED_SOURCES}`，那 8 个 11–14 MB 的分片就会在静态库和 exe 里各编一次。
    exe 只需要链接 `gbarecomp_game`——dispatch table 引用了全部函数，链接器会自己拉进来。
16. **MSVC 必须开 `/bigobj`**。分片每个 11–14 MB，COFF 段数超限会报 `C1128`。
17. **`dispatch_misses=0` 却报 `NOT_STATIC` 往往只是 tcc 热缓存残留**，不是覆盖缺口。
    框架判 `FULLY_STATIC` 的条件是 `misses==0 && healed==0 && interpreted_insns==0`，
    而上一轮留下的 overlay 热缓存会被加载成 `healed=1`。
    `build.ps1` 现在把 `GBARECOMP_HEAL_CACHE` 指向运行目录下的独立缓存，保证每次都是冷启动。
    判据：看 `healed_native`——`healed_native=1` 且 `dispatch_misses=0` 就是缓存问题。
18. **拷贝例程多半是 THUMB 而不是 ARM**。按 ARM 反汇编会得到 `movweq` / `strhi` 之类的垃圾，
    看起来像「地址不对」，其实是**指令集选错了**。判据：函数指针最低位为 1 = THUMB。
    两个模式都试一遍。
19. **全零 IWRAM 会让字节搜索命中上百万个位置**（实测 1,155,115 个命中）。
    搜源地址前必须先判零。另有「IWRAM 的零 == ROM 的零」的假阳性拷贝，要逐条人工复核。
20. **外部模拟器的快照不代表全部拷贝点**。`0x03005CE8` 在所有 mGBA IWRAM 快照里都是全零
    （那一帧那次拷贝还没发生）。用重编译器自己的 `--dump-state` 才是正解。
21. **框架 vendored 的 capstone 只有 macOS 的 dylib**，Windows 上 `import capstone` 直接
    `ImportError`。`pip install capstone` 即可；反汇编脚本建议「优先用已安装的 capstone，
    失败再回退 vendor 目录」。
22. **Stage-2 自愈层（tcc overlay）在框架原版是断的**（上游缺陷，非本工程问题），
    本工程已修复。根因是三件事凑不齐：
    - `src/recompile/emit_function.cpp` 给「带函数内续执行点」的函数生成 alias 路由前导码，
      其中引用宿主全局 `g_runtime_resume_pc`；静态语料有 `runtime_arm.h` 的声明，
      **overlay 的 shim `overlay_runtime_arm.h` 没有** → tcc 报
      `'g_runtime_resume_pc' undeclared`；
    - overlay 是 DLL，要访问宿主符号只能走**导入表**，而导入表需要 (模块名, 符号名)；
      框架的 tcc 命令行既不带宿主 exe，声明也没有 `__declspec(dllimport)`
      → `undefined symbol 'g_runtime_resume_pc'` /
      `undefined symbol 'g_runtime_resume_pc', missing __declspec(dllimport)?`；
    - 宿主 exe 默认**没有导出表**，overlay DLL 加载时也解析不到该符号。

    **三件套的归属**（本工程自己承担两件，框架只占一件）：

    | 环节 | 由谁做 | 做法 |
    |---|---|---|
    | shim 声明 `__declspec(dllimport)` | 本工程 | `build.ps1` 在暂存进 `overlay_toolchain/include` 的 shim 副本上打补丁（对上游零侵入，可随构建重新生成，幂等） |
    | 宿主 exe 导出该符号 | 本工程 | `CMakeLists.txt` 的 `/EXPORT:g_runtime_resume_pc` |
    | tcc 命令行带上宿主 exe | 框架 | `patch-gbarecomp-overlay.ps1` 给 `overlay_compile.cpp` 打补丁（幂等；锚点对不上会直接报错，不会静默跳过） |

    **实测修复效果**（用去掉 `[[code_copy]]` 的对照配置，强制制造 4 个缺口）：

    | 指标 | 修复前 | 修复后 |
    |---|---|---|
    | `failed`（overlay 编译失败） | 4 | **0** |
    | `healed_native`（原生化的缺口） | 0 | **6** |
    | `interpreted_insns`（解释器执行指令） | 3,516,074 | **0** |
    | `native_calls`（原生调用次数） | 0 | **602,065** |
    | guest_fps | 547 | 573 |

    → 修复后即使静态覆盖有缺口，自愈层也能把缺口**全部原生化**，
    解释器一条指令都不执行。正式配置下 0 缺口，这条路根本不会被触发，
    但它是工程对未来新缺口的兜底。

    > 顺带一提：`GBARECOMP_RAM_OVERLAY_HEAL=1` 必须显式打开，
    > 否则 RAM 区的缺口**默认不自动自愈**（框架会静默走解释器桥接且不打印错误）。

## 相关笔记

* `notes/gba-static-recomp-feasibility-20261020.md` —— 可行性实测全记录（数据、覆盖率、缺口、用时估算、突破过程）
* `notes/static-recomp-iwram-code-copies-20261020.md` —— **IWRAM 运行期拷贝代码的定位方法**（四步法 + 实测映射表）
* `notes/gba-static-recomp-skill-package-20261020.md` —— 本流程沉淀成的可分发技能包
* `notes/static-recompilation-native-port-20261020.md` —— 技术路线总览（静态重编译 / 反编译 / 模拟器+预重编译）
* `notes/recomp-modification-surfaces-20261020.md` —— **产物可改性分析**：改数据 / 改函数 / 发 `.gbamod` 包的四层路线与法律边界
