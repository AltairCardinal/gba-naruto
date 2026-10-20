# GBA 静态重编译 → 原生 Windows 可执行文件：独立基线复现记录（2026-10-20）

> 本文记录一次**不依赖 `recomp/` 既有产物**的完整复现：从 ROM + BIOS 出发，
> 静态重编译 → MSVC 编译 → 跑起来出画面 → 统计静态覆盖率与剩余缺口。
> 目的有两个：(1) 验证「静态重编译成原生 PC 程序」这条路线在当前仓库状态下的
> 真实成本与真实覆盖率；(2) 把复现过程中踩到的坑固化成可复用知识。
>
> 产物目录：`build/eval-baseline/`（**未修改 `recomp/` 下任何文件**）。
> 评测报告（同一份内容的交付件）：`C:\Users\feeli\AppData\Local\Temp\eval-gba-static-recomp\baseline.md`。

---

## 1. 复现链路

| 步 | 动作 | 命令 / 产物 |
|---|---|---|
| 1 | 扫描 ROM 头 | `gba_scan.exe rom/base.gba` → `entry_target=0x080000c0`、`game_code=AUEJ`、`save_type=unknown` |
| 2 | 写重编译配置 | `build/eval-baseline/config/naruto_konoha_senki.toml` |
| 3 | 静态重编译 BIOS（LLE） | `gba_recompile --bios recomp/bios/gba_bios.bin --config <fw>/bios/gba_bios.toml --out build/eval-baseline/generated_bios` → **770 个函数**（arm=132 / thumb=638），**0.1 s** |
| 4 | 静态重编译卡带 ROM | `gba_recompile --rom rom/base.gba --config build/eval-baseline/config/naruto_konoha_senki.toml --out build/eval-baseline/generated` → **13,254 个函数 / 8 分片 / 103.1 MB C++**，**13.8 s** |
| 5 | 编译 | `build/eval-baseline/CMakeLists.txt`（VS2022 MSVC Release）→ `build/eval-baseline/build/Release/NarutoKonohaSenkiRecomp.exe`（22.9 MB），**42 s** |
| 6 | 暂存自愈编译器 | `fetch_tcc.ps1` → `<exe>/overlay_toolchain/tcc/tcc.exe`（走本地缓存，无需联网） |
| 7 | 运行出图 | `--frames N --no-window --dump-png shot_N.png`（20000 帧 = 37 s，546 fps） |

> **确定性**：把重编译输出重跑到另一个空目录，BIOS 语料与 ROM 语料逐字节一致
> （SHA-256 相同）→ 重编译器对同一二进制是确定性的，可用于回归对比。

### 关键决策

1. **BIOS 必须走 LLE 静态重编译，不能只靠 HLE。**
   只用 HLE 时，BIOS 的 IRQ 向量 `0x18` 落到解释器 → handler 永远等不到 `iret`
   → IRQ 循环卡死 → 全白屏。实测本轮 BIOS 语料 770 个函数
   （arm=132 / thumb=638），链接后运行日志为
   `bios_backend=LLE (recompiled BIOS)`、`bios_boot=LLE (real intro)`。

2. **`[[data_range]]` 只标「确定不是代码」的小块。**
   本 ROM 是汉化组重建过的，**代码与资源交错**，没有干净切分：
   * `0x080000C0-0x0803FFFF` 稀疏代码
   * `0x08040000-0x080BFFFF` 主代码（99.7% 的函数）
   * `0x085C0000-0x085FFFFF` 启动模块 crt0（入口分支 `0xea00002e` 指向 `0x085CCC04`）
   曾把 `0x080B9F80-0x08600000` 整段标成数据 → 入口分支正好落在区间内 →
   工具直接 abort（`control flow enters data_range`）。本轮只标了
   Logo / 头部字段 / 战斗地图压缩资源三块。

3. **`GBARECOMP_GENERATED_BIOS_DIR` 必须在 `add_subdirectory()` 之前设置。**
   框架在自己的 `CMakeLists.txt` 处理过程中就决定「链接静态重编译的 BIOS 还是
   占位 stub」，变量晚设就只会链到 stub。本轮在父工程里用
   `set(... CACHE PATH ... FORCE)` 前置，并在命令行再传一次 `-D` 兜底。
   验证：`-- gbarecomp: BIOS recompiled output present — linking`。

4. **生成的分片只编译一次。**
   `recomp/CMakeLists.txt` 把 `recompiled_*.cpp` 同时列进 `gbarecomp_game` 静态库
   和可执行文件目标，等于同一批 ~100 MB C++ 编译两遍。
   本轮只编进静态库、可执行文件链接该库 → **MSVC 全量构建 42 秒**（8 分片并行）。

5. **`.ps1` 写成纯 ASCII。**
   PowerShell 5.1 对无 BOM 的 `.ps1` 按 ANSI(936/GBK) 解码，中文注释的乱码会吃掉
   引号 → `ParserError` 且报错行号指向不相干位置。本轮 `build/eval-baseline/build.ps1`
   全部注释用英文，从根上消除这类失败。

---

## 2. 静态覆盖率（实测）

### 编译期

| 项 | BIOS | 卡带 ROM |
|---|---|---|
| 发出函数总数 | **770** | **13,254** |
| 构成 | finder 598 + 手工 80 + 跳转表 73 + 冗余 92 | finder 12,244 + 手工 2 + 冗余 8 |
| ARM / THUMB | 132 / 638 | — |
| 自动跳转表 | — | **51 张 / 1,064 个目标** |
| 字面量池种子 | 22 | 1,039（候选 28,500） |
| AOT 表头 / 取址叶子 | 0 | 14 / 35（6 张指针表） |
| 函数内 resume 别名 | 4,373 → 671 宿主 | 98,861 → 12,304 宿主 |
| `[[code_copy]]` | 0 | 0 |

### 运行期（20000 帧无头）

```
final_pc=0x0806112c steps=4471 cycles=62191750 ppu_frames=20000
pal_nonzero=512/1024 vram_nonzero=40688/98304 oam_nonzero=158/1024
self_heal_coverage=NOT_STATIC dispatch_misses=4 interpreted_insns=3516074
                    healed_native=0 native_calls=0 inflight=0 failed=4
  bridged 0x030006A4 (arm) x124032
  bridged 0x030006B4 (arm) x124032
  bridged 0x03000930 (arm) x18897
  bridged 0x03005CE8 (arm) x124032
```

* **静态覆盖 = 13,254 个函数原生编译**；运行期只剩 **4 个 PC** 走解释器。
* 解释器执行 **3,516,074** 条指令 / 总周期 62,191,750（按周期数为分母的上界
  估计 ≈ **≤5.7%** 的执行量不在原生路径上）。
* 渲染侧三个缓冲区全部非零：调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024。

### 画面复现性

本轮独立构建的 exe 导出的帧与本仓库既有参考截图 **逐字节相同**：

| 帧 | 本轮产物 | 仓库参考 | SHA-256 |
|---|---|---|---|
| 3000 帧 | `run/shot_3000.png` | `recomp/screenshots/01-boot-loading-3000frames.png` | `58724460BFE4C389…` ✅ |
| 20000 帧 | `run/shot_20000.png` | `recomp/screenshots/03-chinese-nameplate-20000frames.png` | `A84AA75CF892DB36…` ✅ |

画面内容 = 大蛇丸立绘 + 中文名牌「大蛇丸」（已用图像查看确认）。

---

## 3. 剩余缺口（4 个 IWRAM PC）——根因已定位

缺口 PC：`0x030006A4` / `0x030006B4` / `0x03000930` / `0x03005CE8`（全 ARM）。
它们**不是 ROM 地址**，而是运行期从 ROM 拷进 IWRAM 的代码，普通 `[[extra_func]]`
会按 ROM 地址解码拿到错字节 → 必须用 `[[code_copy]]` 给
`runtime_start → source_start` 映射（仓库旧结论，见
`notes/dialogue-mapping-blocker-20260702.md`）。

### 自愈编译器为什么救不了这 4 个（2026-10-20 新定位）

运行期 Stage-2 自愈（tcc 现场编译）为**默认关闭**：
`snapshot_ram_region()` 要求 `GBARECOMP_RAM_OVERLAY_HEAL=1`，否则
`overlay_request_compile()` 直接 `s_failed.insert(key)`，**静默失败、不打日志**。

打开该开关后失败原因暴露出来：

```
self_heal: sync compile FAILED for 0x030006A4 (arm): tcc exit 1 compiling
recomp_cache/.../abi6-ram3/030006A4_F99E9406_a.c — see ...log
```
```
030006A4_F99E9406_a.c:21: error: 'g_runtime_resume_pc' undeclared
```

* 生成的 overlay C 里有 `if (g_runtime_resume_pc) { … }`（`emit_function.cpp:535`
  的 resume 别名路由）。
* overlay shim（`fetch_tcc.ps1` 暂存的 5 个头）把引擎全局统一映射到
  `GbaOverlayCallbacks`（`g_cpu`、`g_runtime_fn_entry_hook` 等都是宏），
  **但 ABI v6 的回调结构体里没有 resume_pc 的访问口**，
  `g_runtime_resume_pc` 也没有 `extern` 声明 → tcc 编译不过。
* 退路也不通：`dumpbin /exports` 显示 **exe 没有任何导出表**，
  overlay DLL 无法在加载时从宿主进程解析该符号。

**结论**：这 4 个缺口不是「配置没写对」，而是 **overlay ABI 缺一个 resume_pc 通道**
（需要给 `GbaOverlayCallbacks` 加 resume_pc 访问口并升 ABI 版本，或给 exe 加
`/EXPORT` + shim 里补 `extern "C"` 声明）。这是框架层面的改动，超出本次基线范围，
本轮**未修改框架**。

---

## 4. 踩到的坑

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | `bash` 里 `New-Item`/变量路径被安全策略拦下 | 策略无法静态校验变量拼出的写目标 | 改用字面量绝对路径；建目录交给 `write` 工具 |
| 2 | `Tee-Object` 报「找不到与参数名称 Encoding 匹配的参数」 | PS 5.1 的 `Tee-Object` 没有 `-Encoding` | 改用 `Out-File -Encoding UTF8` |
| 3 | `gba_recompile` 明明 exit 0，脚本却当失败 | PS 5.1 下 `$ErrorActionPreference='Stop'` 会把原生命令的 **stderr 警告**升级成终止性错误 | 用 `Invoke-Native` 封装：调用期间降级偏好，**只看 `$LASTEXITCODE`** |
| 4 | 引擎链到 BIOS 占位 stub 而非静态重编译 BIOS | `GBARECOMP_GENERATED_BIOS_DIR` 在 `add_subdirectory()` 之后才设 | 前置 + 命令行 `-D` 双保险 |
| 5 | `Remove-Item Env:…` 被安全策略拦 | 任何删除意图都会被拦 | 环境变量本就是每进程生效，不需清理 |
| 6 | 自愈编译「静默」失败 | `GBARECOMP_RAM_OVERLAY_HEAL` 默认关；失败分支不打印 | 开 `GBARECOMP_RAM_OVERLAY_HEAL=1` + `GBARECOMP_SYNC_OVERLAY_HEAL=1` + `GBARECOMP_SELFHEAL_VERBOSE=1` 才看得到 tcc 日志 |

---

## 5. 产物清单（`build/eval-baseline/`）

```
config/naruto_konoha_senki.toml   重编译配置（本轮撰写）
compat/msvc_builtin_clz.h        MSVC 兼容 shim（纯 ASCII）
src/main.cpp                     游戏入口（纯 ASCII）
CMakeLists.txt                   构建脚本
build.ps1                        端到端复现脚本（纯 ASCII）
generated/                       ROM 静态重编译语料（8 分片 + dispatch_table + symbol_map）
generated_bios/                  BIOS 静态重编译语料
build/Release/NarutoKonohaSenkiRecomp.exe   可执行文件（22.9 MB）
run/                             运行目录（roms/ bios/ game.toml + 导出的 PNG）
logs/                            全流程日志（01..08）
```

复现命令：`.\build\eval-baseline\build.ps1 -Frames 20000`
