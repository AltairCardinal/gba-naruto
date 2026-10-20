# 技能包：gba-static-recomp（2026-10-20）

本文档记录从本次 GBA 静态重编译实践中抽象出的**可分发技能包**。

## 1. 是什么

一个 Mavis 技能包，把"把 GBA 卡带 ROM 静态重编译成原生 PC 可执行文件"这套流程固化下来，
包含本次实战踩出来的**全部关键坑**（其中 6 个是致命级：会导致白屏、abort 或脚本自尽）。

| 项 | 值 |
|---|---|
| 技能名 | `gba-static-recomp` |
| 位置（源码） | `dist/gba-static-recomp/` |
| 位置（分发包） | `dist/gba-static-recomp.zip`（**44,151 字节，8 个条目**，SHA-256 `FD9537F1F73BE132390614A58793EFD7164D1E63C999D3417E8DF47B89D25527`） |
| SKILL.md 正文 | 264 行（限制 500） |
| references | 4 篇：排错表（§1–§23）/ TOML 配置速查 / 工具链搭建 / 验证与覆盖率 |
| scripts | 3 个：`build-recomp.ps1`（端到端流水线模板）、`patch-overlay-host-link.ps1`（框架补丁）、`summarize-run-log.mjs`（运行日志→指标表） |
| lint | 通过（解包后再次 lint 也通过） |

**不安装到本机**——用户只要分发。安装方式：把 zip 解压到任一技能根
（用户级 `skills/`、agent 级 `agents/<name>/skills/`、或项目级 `.minimax/skills/`）。
zip 内层目录名固定为 `gba-static-recomp/`，解压后直接就是 `.../gba-static-recomp/SKILL.md`。

### 分发包验证记录

1. `lint-skill.js` 对解包后的副本跑通（body 264 行、3 个 reference 链接全部解析）；
2. 两个 `.ps1` 解包后仍带 **UTF-8 BOM**（`EF BB BF`），`PSParser` 解析通过；
3. `scripts/summarize-run-log.mjs` 从解包副本直接跑真实 FULLY_STATIC 日志 → `verdict: PASS`；
4. zip 内**不含** BIOS、生成的 C++ 或任何含任天堂代码的产物。

## 2. 为什么值得做成技能

这次实战里，**决定成败的都不是"移植"本身，而是一串与环境/工具链绑定的坑**：

| 坑 | 后果 | 级别 |
|---|---|---|
| BIOS 没静态重编译（LLE），只用了 HLE | IRQ 向量走解释器 → 死循环 → **全白屏** | 致命 |
| `[[data_range]]` 圈住代码区 | `control flow enters data_range` → **直接 abort** | 致命 |
| 复位向量被 data_range 吞掉 | dispatch miss → 解释器桥接 → tcc 自愈也失败 → 卡死 | 致命 |
| 存档尺寸与芯片类型不匹配 | 运行时拒绝启动 | 致命 |
| MSVC 无 `__builtin_clz`（C++ 模式） | 框架编译不过 | 致命 |
| force-include 头里有中文注释 | GBK 误解码 → `#if` 不再是指令 → 报错行号全错 | 致命（最难查） |
| `.ps1` 无 UTF-8 BOM | ParserError，报错指向不相关行 | 高 |
| `$ErrorActionPreference='Stop'` + 原生命令 stderr | warning 被当致命错误 → 脚本自尽 | 高 |
| 生成码与框架头文件版本不一致 | `error C2440` dispatch table | 中 |
| `GBARECOMP_GENERATED_BIOS_DIR` 设晚于 `add_subdirectory` | 静默退回 BIOS stub → 白屏 | 高 |
| RAM 区自愈默认关闭 | 4 个 IWRAM 缺口一直走解释器 | 中 |
| 同一批分片被编两遍 | 构建时间翻倍 | 低 |
| 拷贝例程按 ARM 反汇编（实际是 THUMB） | 输出全是垃圾，误判"地址不对" | 高 |
| tcc 热缓存残留 | `dispatch_misses=0` 却报 `NOT_STATIC` → 误判为覆盖缺口 | 中 |

这些知识**分散在一次 6 小时的会话里**，不固化就等于没沉淀。做成技能后，
下一个要做 GBA 移植的人（或 agent）可以直接命中。

## 3. 评测（with-skill vs baseline）

同一台机器、同一份真实 ROM/BIOS、同一个任务（"做成 PC 原生版并跑出画面"），
两个后台 worker 并行跑：producer 加载技能，baseline 不加载任何技能。

| 指标 | with-skill | baseline | 差异 |
|---|---|---|---|
| 是否产出可运行 exe | ✅ 22.9 MB | ✅ 22.9 MB | 平 |
| 是否出画面 | ✅ | ✅ | 平 |
| 截图 | 4 个帧点与参考图 **SHA-256 逐字节相同** | 与参考图 SHA-256 相同 | 平 |
| 静态函数数 | **13,271** | 13,254 | **技能胜** |
| **dispatch_misses** | **0** | 4 | **技能胜** |
| **interpreted_insns** | **0** | 3,516,074 | **技能胜（100% 静态）** |
| **self_heal_coverage** | **FULLY_STATIC** | NOT_STATIC | **技能胜** |
| guest_fps | 603.8 | 547 | 技能胜（+10%） |
| BIOS 后端 | LLE | LLE | 平 |

**结论：技能没有引入回归，且在"覆盖率收敛"这一步明显更强——把残留解释器桥接从
4 个清到 0，达到 100% 静态覆盖。**

差异来源可追溯到技能里的具体规定：

1. SKILL.md §9（RAM 地址要走 `[[code_copy]]` + 逆向找源地址，**不是** `[[extra_func]]`）
   → with-skill 据此自写了 5 个 IWRAM 分析脚本（`find-iwram-source.mjs` / `iwram-map.mjs` /
   `block-extent.mjs` / `disasm_arm.py` / `rom-inspect.mjs`），把 4 张拷贝表全部逆向出来，
   最终 0 miss；baseline 停在 4 个缺口并把根因归到 overlay ABI
2. `references/troubleshooting.md` §18（overlay ABI 版本漂移）
   → with-skill 据此确认 tcc 失败是 `g_runtime_resume_pc` 未声明，**不是**覆盖问题
3. `scripts/summarize-run-log.mjs` → with-skill 直接复用了技能自带的日志解析器做指标判定

**baseline 也很强**（它是能读框架源码的模型），独立复现了全部关键结论，
甚至额外挖出 `GBARECOMP_RAM_OVERLAY_HEAL` 开关、`GBARECOMP_GENERATED_BIOS_DIR` 的时序要求、
以及宿主 exe 无导出表导致 overlay 无法解析符号——这三条已回填进技能的 references。

### 3.1 with-skill 覆盖率收敛轨迹

| 轮次 | 静态函数 | dispatch_misses | interpreted_insns | 说明 |
|---|---|---|---|---|
| 第 1 轮 | 13,151 | 13 | 12,710,612 | 只写了复位向量（与 baseline 起点一致） |
| 第 2 轮 | 13,262 | 1 | 496,128 | +9 个 ROM `[[extra_func]]`、4 张 `[[code_copy]]`、4 个 IWRAM `[[extra_func]]` |
| 第 3 轮 | **13,271** | **0** | **0** | +模块内全部函数头（含上一轮漏掉的 `0x03000694`） |

四帧点（3k / 10k / 20k / 60k）全部 `FULLY_STATIC`，四张 PNG 与参考图逐字节相同，
且 `cycles=62191750`、`final_pc=0x0806112c` 每帧点一致 → 重编译是**确定性**的。

## 4. 评测驱动的技能改进（已落地）

| 来源 | 新增内容 |
|---|---|
| baseline | `troubleshooting.md` §16 `GBARECOMP_GENERATED_BIOS_DIR` 时序 |
| baseline | `troubleshooting.md` §17 `GBARECOMP_RAM_OVERLAY_HEAL` 开关 |
| baseline | `troubleshooting.md` §18 overlay ABI 与 emitter 版本漂移（宿主无导出表） |
| baseline | `troubleshooting.md` §19 `Tee-Object` 无 `-Encoding` |
| baseline | `troubleshooting.md` §20 分片被编两遍导致构建翻倍 |
| baseline | `build-setup.md` CMakeLists 模板加 BIOS 目录时序 + "别编两遍" |
| with-skill | **§21 RAM 地址残留 PC 的四步定位法**（RAM 快照 → 字面量池 → 实测 size → 反汇编读函数头）+ 完整 `[[code_copy]]` 配置示例 + capstone 在 Windows 需 `pip install` |
| with-skill | **§22 `dispatch_misses=0` 但 `NOT_STATIC`**（tcc 热缓存残留，用 `GBARECOMP_HEAL_CACHE` 冷跑） |
| with-skill | **§23 Stage-2 自愈层在 Windows 上是断的**——三件套修法（shim 声明打 `__declspec(dllimport)` 补丁 / exe `/EXPORT:g_runtime_resume_pc` / 框架 `overlay_compile.cpp` 打补丁把宿主 exe 加进命令行）+ 实测边界矩阵 + 收益数据（failed 4→0、interpreted_insns 3.5M→0、native_calls 0→602,065） |
| with-skill | **新增 `scripts/patch-overlay-host-link.ps1`**（框架补丁脚本，幂等，锚点对不上就抛错） |
| with-skill | `scripts/build-recomp.ps1` 模板补上：框架补丁调用、shim dllimport 补丁、按配置内容哈希隔离的 heal cache、`GBARECOMP_NO_LAUNCHER` / `GBARECOMP_HEAL_BACKEND`、运行日志落盘 |
| with-skill | SKILL.md §9 改写为"残留 PC 按地址性质分三类处理"，并给出 FULLY_STATIC 实测收益 |
| with-skill | `config-schema.md` `[[code_copy]]` 补"三个值怎么定"对照表 |
| with-skill | `verification.md` 补 `self_heal_coverage` 判据、`FULLY_STATIC` 含义、热缓存误判提示，刷新性能参照表 |
| with-skill | `summarize-run-log.mjs` 文本输出补 `self_heal_coverage` 状态 |
| 自查 | `summarize-run-log.mjs` 的解析 bug（key 冲突 / 前缀吃掉 key）已修并用真实日志回归 |

改完重新 lint 通过（264 行），并做了**解包后二次 lint + 脚本回归**。

### 4.1 技能包之外的实战收获（已回填 `recomp/` 正式工程）

同一轮还修掉了三个「能跑但不对」的问题，它们属于**工程**而非技能，但同样值得记录：

| 问题 | 症状 | 修法 |
|---|---|---|
| 分片被编两遍 | 构建时间翻倍 | `CMakeLists.txt` 的 exe 只编 `src/main.cpp`；另加 `/bigobj` |
| tcc 热缓存污染覆盖标签 | 明明 0 miss 却报 `NOT_STATIC` | `build.ps1` 把 `GBARECOMP_HEAL_CACHE` 指到独立目录，且**按配置内容哈希**再分一层 |
| 运行日志不落盘 | 指标只能靠肉眼看 | `build.ps1` 把 stdout 写成 `run_<frames>.out` 并自动打印覆盖率指标 |

## 5. 关键纠正：仓库里原有的归因是错的

`notes/gba-static-recomp-baseline-eval-20261020.md` 与 `docs/sequel-roadmap.md` 曾写：

> 这 4 个缺口自愈编译器救不了，原因是 overlay ABI v6 的 `GbaOverlayCallbacks`
> 没有 resume_pc 访问口；要闭合需要给回调结构体加 resume_pc 通道并升 ABI 版本，
> 或给 exe 加 `/EXPORT`。

**这个归因是错的。** 这 4 个 PC（`0x030006A4` / `0x030006B4` / `0x03000930` / `0x03005CE8`）
**根本不是 ROM 地址**，而是游戏启动时从 ROM **重定位到 IWRAM** 的代码：
重编译器按卡带地址取字节当然取不到 → 退化成解释器桥接；
自愈编译器（tcc overlay）同样没有"运行期地址 → ROM 源地址"的概念，所以也救不了。

正解是**配置层面**的 `[[code_copy]]`（运行期→源映射）+ `[[extra_func]].source_addr`，
**既不用动 overlay ABI，也不用动 exe 导出表**。

四张拷贝表（实测逐字节相同长度即 `size`）：

| 运行期 | ROM 源 | size | 内容 |
|---|---|---|---|
| `0x03000680` | `0x080004C8` | `0x200` | stub 跳板模块 |
| `0x0300088C` | `0x08000520` | `0x0A4` | 同一模块的第二份拷贝 |
| `0x03000930` | `0x080005AC` | `0x060` | 算术 helper |
| `0x03005CE8` | `0x08000638` | `0x05C` | 表查找 helper |

详细方法学见 `notes/static-recomp-iwram-code-copies-20261020.md`。

## 6. 相关笔记

* `notes/gba-static-recomp-feasibility-20261020.md` —— 本次可行性实测全记录（技能的知识来源）
* `notes/static-recomp-iwram-code-copies-20261020.md` —— IWRAM 拷贝代码的定位方法与结论
* `notes/gba-static-recomp-baseline-eval-20261020.md` —— baseline 评测报告（归因错误已在上文纠正）
* `notes/recomp-modification-surfaces-20261020.md` —— 产物可改性分析（改数据/改函数/发 mod 包）
* `notes/static-recompilation-native-port-20261020.md` —— 技术路线总览
