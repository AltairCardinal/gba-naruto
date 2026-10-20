---
name: gba-static-recomp
description: |
  Turn a GBA (Game Boy Advance) cartridge ROM into a native, runnable PC build by
  static recompilation with mstan/gbarecomp, and close the remaining coverage gaps
  so it actually boots and renders. Load this skill when the user says
  "静态重编译 GBA ROM"、"把 GBA 游戏搬到 PC"、"GBA ROM 转原生"、"GBARecomp"、
  "native PC port of a GBA cartridge"、"recompile this .gba"、"LÖVE/脚本游戏移植到安卓",
  or is stuck on a white screen / "did not iret" / dispatch-miss / IRQ hang while
  porting a .gba. Do NOT use it for emulator setup (yuzu/Ryujinx/suyu), for
  non-GBA consoles, for decompiling a game back into readable original source,
  or for editing ROM text/data when no native build is wanted.
---

# GBA 静态重编译（GBARecomp）

把 GBA 卡带 ROM 翻译成原生 C++，链接成可运行的 PC 可执行文件——**不走模拟器**。
产物是"原版逻辑的原生复活"，**不是**可读的原始源码（那是反编译，成本高一到两个数量级）。

## Inputs to collect

| 输入 | 为什么需要 | 缺了怎么办 |
|---|---|---|
| 合法持有的 `.gba` + SHA-1 | 重编译输入；`[identity].sha1` 硬校验，错了直接 abort | 问用户要 |
| 自己主机导出的 `gba_bios.bin`（16 KB，SHA-1 `300c20df6731a33952ded8c436f7f186d25d3492`） | 运行时拒绝无哈希校验的 BIOS | 问用户要，**不要自己去找 BIOS**（任天堂版权） |
| 目标平台 | 决定编译器 / SDL2 / 打包方式 | 默认 Windows x64 |
| 已有逆向成果（地址表 / 符号表 / 数据区边界） | 直接决定 `[[data_range]]` 与 `[[extra_func]]` 的质量，通常省掉数天 | 没有就靠 `gba_scan` + 运行日志反推 |
| 想要的产出范围 | 只要"能出画面" vs 要宽屏 / 要 mod 包，工作量差几倍 | 默认"能跑出画面" |

## Procedure

### 0. 选路：先确认"反编译"不是你要的东西

用户说"想改游戏源码/想看懂逻辑"时，先分清三条路：

| 目标 | 手段 | 反编译？ |
|---|---|---|
| 改文本/数值/图块 | 改 ROM（数据注入） | 否 |
| 改单个行为（伤害公式、掉落率） | `[[mod_function_hook]]` + native plugin | 否 |
| 搬到 PC/手机跑 | **静态重编译**（本 skill） | 否 |
| 读懂某段逻辑 | 逆向：定位地址 → 局部反编译 → 验证 | 局部要 |
| 1:1 复刻原版 | 全量反编译 + matching | 是，成本最高 |

静态重编译**只翻译不理解**，所以能自动化、能保真；反编译**必须理解**，成本是全游戏量级。
除非用户明确要"可读的原始源码"，否则不要开反编译这条路。

### 1. 装工具链

优先**从源码自建框架**（main 分支比预编译 CLI 多识别约 1000 个函数，还支持 RAM 拷贝模板）：

```powershell
git clone --depth 1 https://github.com/mstan/gbarecomp.git build\gbarecomp-src
git -C build\gbarecomp-src submodule update --init --depth 1 --recursive
cmake -S build\gbarecomp-src -B build\gbarecomp-src\build-vs -A x64
cmake --build build\gbarecomp-src\build-vs --config Release --target gba_recompile gba_scan --parallel 16
```

同时备齐：SDL2 开发库、OpenJDK 不需要（框架只要 C++ 编译器）、Windows SDK。
工具链细节与 MSVC 兼容 shim 见 `references/build-setup.md`。

### 2. 探测 ROM

```powershell
.\build\gbarecomp-src\build-vs\Release\gba_scan.exe <rom.gba>
```

拿到 `entry_target`（入口）、`save_type`（存档芯片，通常 `unknown`）、`complement_valid`、
`logo_present`。**入口地址和存档芯片类型是后面写配置的硬输入**。

### 3. 写重编译配置（决定成败的一步）

新建 `config/<game>.toml`，至少四段：

```toml
[program]
name         = "<ROM 文件名>"
id           = "<slug>"
load_address = 0x08000000
size         = 0x00XXXXXX      # 必须等于文件字节数
entry_pc     = 0x08XXXXXX      # gba_scan 给的 entry_target
aot_scan_start = 0x08XXXXXX
aot_scan_end   = 0x08XXXXXX

[identity]
sha1 = "<ROM 的 SHA-1>"

[[data_range]]                  # 只标"确定不是代码"的小块
start = 0x08000000
end   = 0x080000C0

[[extra_func]]
addr = 0x08000000
mode = "arm"
```

**两条硬约束**（违反会直接 abort，不是 warning）：

- `[[data_range]]` 不得覆盖任何控制流会到达的地址。**GBA 常见布局是代码与资源交错**，
  不要按"前面代码后面数据"一刀切。宁可少标。
- `[[extra_func]]` 与 `[[data_range]]` 不得重叠。

`[[program]]` / `[[identity]]` / `[[data_range]]` / `[[extra_func]]` / `[[code_copy]]` /
`[[jump_table]]` / `[[exclude_func]]` 的完整字段见 `references/config-schema.md`。

### 4. 静态重编译 BIOS（**最容易被跳过、也最致命的一步**）

```powershell
Copy-Item <user_bios.bin> build\gbarecomp-src\bios\gba_bios.bin -Force
.\gba_recompile.exe --bios build\gbarecomp-src\bios\gba_bios.bin `
  --config build\gbarecomp-src\bios\gba_bios.toml `
  --out build\gbarecomp-src\src\runtime\generated_bios
```

**为什么必须做**：只用框架自带的 HLE BIOS 时，BIOS 的 IRQ 向量（`0x18`）会落到解释器，
游戏等不到 `iret` → `runtime_irq: handler did not iret after N dispatches` → 死循环 → **全白屏**。
静态重编译 BIOS 后它变成原生代码，IRQ 正常，屏幕才有内容。产出约 770 个 BIOS 函数。

### 5. 静态重编译卡带 ROM

```powershell
.\gba_recompile.exe --rom <rom.gba> --config config\<game>.toml --out build\gen
```

看输出里的 `discovered N functions` 与 `data_ranges_honored`。
若报 `control flow enters data_range`，说明 `[[data_range]]` 盖住了代码——**缩小区间**而不是删掉配置。

### 6. 编译游戏可执行文件

建一个 game repo（`CMakeLists.txt` + `src/main.cpp`），`add_subdirectory` 引框架，
把生成的 C++ 编成静态库再链成 exe。接线的完整模板见 `scripts/build-recomp.ps1` 与
`references/build-setup.md`。

`src/main.cpp` 的核心只有几行：

```cpp
gbarecomp::RunOptions opts;
opts.builtin_game_name = "<游戏名>";
opts.builtin_rom_sha1  = "<ROM SHA-1>";
opts.mod_game_id       = "<slug>";
opts.launcher_game_config = "game.toml";
return gbarecomp::run_game(argc, argv, opts);
```

再写一份 `game.toml`（运行时配置）：`[bios]` / `[rom]` 填 SHA-1，`[recompiler]` 填入口，
`[save]` 填存档芯片类型与尺寸，`[runtime]` 填 debug 端口与窗口标题。

### 7. 暂存自愈编译器（TCC）与子模块头

```powershell
.\build\gbarecomp-src\tools\fetch_tcc.ps1 -Toolchain <exe_dir>\overlay_toolchain
```

自愈层用 TinyCC 现场编译被桥接的函数；缺 TCC 会看到 `tcc exit -1`。
暂存后还要手动还原子模块目录结构（main 分支的头文件用相对路径引用子模块），
否则 tcc 报 `include file not found`——见 `references/build-setup.md`。

### 8. 运行验证

```powershell
<exe> --rom <rom> --bios <bios> --frames 20000 --no-window --dump-png shot.png
```

- `--frames N` 跑 N 帧后退出；**帧数换算**：宿主 guest_fps 通常 500~900，
  20000 帧 ≈ 22~40 秒游戏时间。开局画面通常要 10000 帧以上才出现。
- `--dump-png <path>` 导出最终帧缓冲——**这是最快的"有没有画面"判据**，比截图窗口可靠。
- 去掉 `--no-window` 就是真实 SDL 窗口模式。
- 用 `scripts/summarize-run-log.mjs` 把运行日志解析成指标表。

**验收线**：`pal_nonzero` / `vram_nonzero` / `oam_nonzero` 三项明显大于 0
（说明 PPU 真在画），且 `dispatch_misses` 尽可能小。

### 9. 收敛覆盖率

运行日志会给出 `recomp_master_misses_<code>.toml.frag`——运行时自动生成的
`[[extra_func]]` 提案（**框架从不自动合并，必须人工审核**）。

- 卡带地址（`0x08xxxxxx`）→ 直接进 `[[extra_func]]`
- IWRAM/EWRAM 地址（`0x03xxxxxx` / `0x02xxxxxx`）→ **不是 ROM 地址**，
  是运行期从 ROM 拷进去的代码，需要 `[[code_copy]]` 给出 runtime→source 映射。
  定位源地址要靠逆向：反汇编启动期的拷贝例程，看它把哪个 ROM 区段搬到了哪个 RAM 地址。
  不要用 `[[extra_func]]`——按 ROM 地址解码会拿到错误字节。
- 反复出现的同模式地址序列 → 很可能是 switch 跳转表，用一条 `[[jump_table]]` 覆盖整个表，
  比逐个 `[[extra_func]]` 好。

调试时设 `GBARECOMP_RAM_OVERLAY_HEAL=1` 再跑一轮，RAM 区的缺口可能自己收敛。

**收敛到 0 miss 是可达的**，但要先分清每个残留 PC 的性质：

| 残留 PC 地址 | 性质 | 处理 |
|---|---|---|
| `0x08xxxxxx` | ROM 里的函数没被自动发现 | 直接进 `[[extra_func]]`，一次一个，成本低 |
| `0x02`/`0x03xxxxxx` | **根本不是 ROM 地址**——游戏启动时把 ROM 代码重定位到 IWRAM 再间接调用 | 先逆向找出 `(ROM 源, RAM 目标)` 对 → `[[code_copy]]` 声明映射 → `[[extra_func]]` + `source_addr` 声明入口。**定位方法见 `references/troubleshooting.md` §21** |

**不要**为了 RAM 类 miss 去改 overlay ABI 或给 exe 加 `/EXPORT`——
这类 PC 不是"找不到静态实现"，而是"按卡带地址取不到字节"，改 ABI 解决不了。

实测（同一 ROM、同一框架）：13 个 miss → 4 个 → **0**；
解释执行指令数 12,710,612 → 3,516,074 → **0**；
最终 `self_heal_coverage=FULLY_STATIC`，guest_fps 547 → 603。

**画面正常就收工**是合理的取舍——残留桥接 PC 可以接受，但要写进交付说明；
只有当要做到"原生性能等价"或"产物可长期维护"时，才值得继续啃 RAM 拷贝那一类。

## Output contract

交付给用户的东西：

1. **可运行的原生可执行文件**（不是只有静态库）——能双击运行出画面
2. **重编译配置** `config/<game>.toml` 与 **运行时配置** `game.toml`（可复现）
3. **框架工具**（`gba_recompile.exe` / `gba_scan.exe`）与端到端构建脚本
4. **验证截图**（`--dump-png` 产物）与**指标表**（函数数 / dispatch miss / 渲染非零计数）
5. **剩余缺口清单**：哪些 PC 仍走解释器、为什么、下一步怎么补

不要把 BIOS 打进包；不要把生成的 C++ 或含任天堂代码的产物公开发布。

## Failure handling

| 症状 | 处理 |
|---|---|
| 全白屏 / `did not iret` | 多半是 **BIOS 没静态重编译**（步骤 4 没做或没链接）→ 回步骤 4，确认日志里 `bios_backend=LLE` |
| `control flow enters data_range` | `[[data_range]]` 盖住代码 → 缩小区间；确认入口分支目标不在任何 data_range 内 |
| `dispatch miss` 持续增长 | 看 `.frag` 提案：卡带地址进 `[[extra_func]]`，IWRAM 地址进 `[[code_copy]]` |
| `tcc exit -1` | TCC 没暂存 → 跑步骤 7 |
| `tcc exit 1` + `include file not found` | 暂存目录缺 `external/arm-recomp-core/...` 子模块结构 → 见 `references/build-setup.md` |
| `tcc exit 1` + `'g_runtime_resume_pc' undeclared` | overlay ABI 与 emitter 版本漂移 → 见 `references/troubleshooting.md` §18（**不是 tcc 的问题**） |
| `tcc exit 1` + `'g_runtime_resume_pc' undeclared` | overlay shim 缺宿主符号声明 → 见 `references/troubleshooting.md` §23 的三件套 |
| `tcc exit 1` + `undefined symbol 'g_runtime_resume_pc'` | overlay DLL 解析不到宿主符号（PE 导入表问题）→ 同上，§23 |
| BIOS 明明编译了但日志仍是 `bios_backend=HLE` | `GBARECOMP_GENERATED_BIOS_DIR` 设得晚于 `add_subdirectory()` → 见 `references/troubleshooting.md` §16 |
| 构建时间突然翻倍 | 同一批分片被编了两次（静态库 + exe 源文件）→ 二选一，见 `references/build-setup.md` |
| `save size N is incompatible with ...` | 存档尺寸与芯片类型不匹配 → 按 `references/config-schema.md` 的尺寸表改 |
| `complement_valid=0` | ROM 头被改过 → 确认这是用户持有的版本，不要自行修头 |
| 画面全白但 `vram_nonzero>0` | 可能只是还没到出画面的时间点 → 加大 `--frames` |
| 编译报 `error C2440`（dispatch table 初始化） | 生成码与框架头文件**不是同一版本** → 两者都用同一份框架检出 |
| 编译报 `__builtin_clz` 找不到 | 框架 main 分支用了 GCC 内建 → 见 `references/build-setup.md` 的 MSVC shim |

完整症状表见 `references/troubleshooting.md`。

## Windows (win32) platform notes

Windows 是本流程最容易翻车的地方，两条硬规则：

1. **`.ps1` 必须是 UTF-8 with BOM。** PowerShell 5.1 读无 BOM 的脚本按 ANSI(936/GBK) 解码，
   中文注释的乱码会吃掉引号 → `ParserError`，且报错行号指向不相干的位置。
2. **`$ErrorActionPreference='Stop'` 会把原生命令的 stderr 变成终止性错误。**
   框架工具把 `[finder] ... budget exhausted` 这类 **warning** 写进 stderr（退出码仍是 0），
   脚本会误判失败而中断。**只看 `$LASTEXITCODE`**，并在调用期间把错误偏好降为 `Continue`。

`scripts/build-recomp.ps1` 已经把这两点处理好了，直接复制改参数即可。

其它 Windows 注意：
- VS 多配置生成器把 exe 放在 `<build>/Release/`，不是 `<build>/`
- 取文件哈希用 `Get-FileHash -LiteralPath`——文件名含 `[` `]` 时 `-Path` 会当通配符**静默返回空**
- MSYS2 不是必须；MSVC 路径可行，但需要 `references/build-setup.md` 里的 shim
- **Stage-2 自愈层（tcc overlay）在框架原版是断的**，会报
  `undefined symbol 'g_runtime_resume_pc'`。
  三件套修法见 `references/troubleshooting.md` §23：
  shim 声明打 `__declspec(dllimport)` 补丁（打在暂存副本上）、
  exe 加 `/EXPORT:g_runtime_resume_pc`、
  用 `scripts/patch-overlay-host-link.ps1` 给框架的 `overlay_compile.cpp` 打补丁。
  `scripts/build-recomp.ps1` 已把这三步都串好，直接复制改参数即可。

## Examples

**Input**: "这是我的 GBA ROM 火影忍者 - 木叶战记(汉化版).gba，能不能做成 PC 上原生跑的版本？"

**Output**:
- `config/naruto_konoha_senki.toml`：`[identity].sha1` = ROM 实际 SHA-1；
  `[[data_range]]` 只标 Logo 与头部字段；`[[extra_func]]` 标复位向量
- `game.toml`：`[bios]`/`[rom]` 双 SHA-1、`[recompiler].entry_point` = `gba_scan` 的 entry_target、
  `[save]` 按实际 `.sav` 字节数选 SRAM/EEPROM/Flash
- `build/gbarecomp-out/Release/<Game>Recomp.exe`：能跑出画面
- `build/naruto-recomp-run/shot_20000.png`：验证截图
- 指标：13,271 个静态函数 / 8 分片 / 103 MB 生成 C++ / exe 22.9 MB；
  20000 帧运行 `self_heal_coverage=FULLY_STATIC dispatch_misses=0 interpreted_insns=0`
  （补完 4 条 `[[code_copy]]` 之后）；渲染侧调色板 512/1024、VRAM 40,688/98,304、OAM 158/1024
  全部非零；`--dump-png` 出的 PNG 与参考图逐字节相同
