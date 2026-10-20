# 无头 mGBA 宿主：构建、崩溃根因与实测证据（2026-10-20）

## 0. 结论先行

- **无头 mGBA 宿主已跑通**：`build/mgba-probe/mgba-probe.exe` 能加载 `rom/base.gba`，
  响应 `status` / `x/4` / `frames` / `dump` / `save` / `load`，退出码 0。
- **按键注入实测生效**：模拟内 KEYINPUT（`0x04000130`）由 `FF 03`（空闲）变为
  `F7 03`（按住 START），`keyoff` 后回到 `FF 03`。
- **savestate 实测可存可读**：397412 字节，`save` / `load` 均返回 OK。
- **"启动即崩"的根因不是 mGBA 本身**，而是宿主 C 代码里的
  `setvbuf(stdout, NULL, _IOLBF, 0)`：MSVC 只在 `_IONBF` 下允许 NULL 缓冲区，
  其余模式走 CRT 非法参数处理器 → Watson → 非交互会话无法弹窗 →
  `__fastfail` → **0xC0000409**，且发生在 `main()` 第一条语句之前，所以 stdout/stderr 全空。

背景方案见 `notes/mgba-c-api-probe-plan-20261020.md`。

---

## 1. 环境与构建

| 组件 | 位置 |
|---|---|
| MSVC Build Tools 2022 | `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`（MSVC 14.44.35207，Windows SDK 10.0.26100.0） |
| 便携 CMake | `D:\Shell\toolchain\cmake-3.31.7-windows-x86_64\bin\cmake.exe` |
| mGBA 源码 | `D:\Shell\toolchain\mgba-0.10.5`（上游，**未改动**） |
| mGBA 构建树 | `D:\Shell\toolchain\mgba-build` |
| mGBA 静态库 | `D:\Shell\toolchain\mgba-build\Release\mgba.lib`（2.4 MB） |

构建命令：

```powershell
python tools/mgba_probe/build.py                # 宿主（必要时先建 mGBA 静态库）
python tools/mgba_probe/build.py --rebuild-mgba  # 强制重建 mGBA 静态库
```

可选的"并入 mGBA 自己的 CMake 工程"路径（保证宏与对象选择完全一致）：

```powershell
cmake -S tools/mgba_probe -B build/mgba-probe/cmake -DCMAKE_BUILD_TYPE=Release
cmake --build build/mgba-probe/cmake --config Release --target mgba-probe
```

这条路径有两个坑（都已在 `tools/mgba_probe/CMakeLists.txt` 里修掉）：

1. mGBA 的 `M_CORE_GBA` 是**目录级** `add_definitions(-DM_CORE_GBA)`
   （`CMakeLists.txt:818`），只对 mGBA 自己的目录作用域生效，**不会**传给父目录里的
   宿主 target；`USE_DEBUGGERS` 则在 `mgba` target 的 `COMPILE_DEFINITIONS` 属性里
   （可被 `get_target_property` 取到）。所以宿主必须自己再补一遍 `M_CORE_GBA`。
2. `_Static_assert` 需要 `set(CMAKE_C_STANDARD 11)`，否则 MSVC 默认 C 标准下不认。

实测这条路径产出的 `build/mgba-probe/cmake/Release/mgba-probe.exe` 与
`build.py` 产出的 exe 行为一致（同样 exit 0、KEYINPUT `F703`、savestate 397412 字节）。

产物：`build/mgba-probe/mgba-probe.exe`（705024 字节）+ `build/mgba-probe/mgba-probe.map`。

### 1.1 ABI：宿主必须与库用同一套宏（重要）

`struct mCore`（`include/mgba/core/core.h:40`）中间嵌了一整段
`#ifdef USE_DEBUGGERS` 成员：

```c
#ifdef USE_DEBUGGERS
	bool (*supportsDebuggerType)(struct mCore*, enum mDebuggerType);
	struct mDebuggerPlatform* (*debuggerPlatform)(struct mCore*);
	struct CLIDebuggerSystem* (*cliDebuggerSystem)(struct mCore*);
	void (*attachDebugger)(struct mCore*, struct mDebugger*);
	void (*detachDebugger)(struct mCore*);
	void (*loadSymbols)(struct mCore*, struct VFile*);
	bool (*lookupIdentifier)(struct mCore*, const char* name, int32_t* value, int* segment);
#endif
```

实测：不定义 `USE_DEBUGGERS` 时 `sizeof(struct mCore)` = **1592**，
定义后 = **1648**（差 56 字节 = 7 个函数指针），其后所有成员的偏移全部平移。

`build.py` 因此**不手抄宏**，而是解析 CMake 生成的 `mgba.vcxproj`，取
Release 配置的 `PreprocessorDefinitions` 原样传给 `cl.exe`：

```
WIN32 _WINDOWS _CRT_SECURE_NO_WARNINGS NDEBUG BUILD_STATIC USE_DEBUGGERS
HAVE_STRDUP HAVE_SETLOCALE _WIN32_WINNT=0x0600 NOMINMAX WIN32_LEAN_AND_MEAN
_UNICODE UNICODE M_CORE_GBA
```

`host_main.c` 里另有 `_Static_assert` 指纹（`sizeof(struct mCore) == 1648`、
`offsetof(struct mCore, init) == 1016` 等），宏一旦漂移就是**编译错误**，
而不是运行期神秘崩溃。

---

## 2. 崩溃根因（四个，逐个定位）

### 2.1 启动即崩 0xC0000409，stdout/stderr 全空

**根因**：`host_main.c` 的

```c
setvbuf(stdout, NULL, _IOLBF, 0);
setvbuf(stderr, NULL, _IONBF, 0);
```

MSVC 的 `setvbuf` 只有在 `_IONBF` 下才允许 `buf == NULL`；带缓冲的模式会触发
CRT 的**非法参数处理器**（`_invalid_parameter` → `_invoke_watson`）。在无交互
终端的会话里 Watson 弹不出对话框，于是走 `__fastfail(FAST_FAIL_FATAL_APP_EXIT)`
→ 进程以 **0xC0000409** 结束。这两行位于 `main()` 的**最前面**，
所以连 `fprintf(stderr, "[probe] open rom")` 都没机会输出——这正好解释了
"退出码 0xC0000409 且一行输出都没有"的现象。

**证据**：删掉这两行后，同一份代码立刻正常启动（`READY` → 全部命令 → `BYE`，退出码 0）。
宿主改为**每次写完显式 `fflush`**，不再依赖 `setvbuf`。

**同时排除的猜想**：此前怀疑"库里同时存在 POSIX / Win32 两套 VFile 后端，
MSVC 选错了符号"。实测 mGBA 的 CMake 只编译
`src/util/vfs/vfs-fd.c` + `src/platform/windows/vfs-w32.c`
（`CMakeLists.txt:222`），`src/util/vfs/` 下**没有** `vfs-posix.c`，
该猜想不成立。

### 2.2 跑第一帧时 0xC0000005（崩在 `ARMRunLoop`）

**根因**：加载 ROM 后漏了 `core->reset(core)`。
mGBA 自己的前端都做这一步——`src/platform/example/client-server/server.c:126`：

```c
// Reset the core. This is needed before it can run.
core->reset(core);
```

不 reset 时 CPU 的内存映射无效，第一次 `runFrame` 取指即崩。

**定位方法（可复用）**：宿主装 `SetUnhandledExceptionFilter` + `CaptureStackBackTrace`
打印回溯，再用链接器 `/MAP` 输出 + 一个 RVA→符号解析脚本定位：

```
EXCEPTION code=C0000005 address=... exe=...
  #07 ...   → ARMRunLoop+0xB4      （崩在这里）
  #08 ...   → _GBACoreRunFrame+0x5E
  #09 ...   → _cmdFrames+0xA0
```

回溯里 `#08` 之前缺 `mDebuggerAttach` 一帧，是因为 MSVC `/O2` 把
`mDebuggerAttach` 的最后一句 `core->attachDebugger(core, debugger)` 编成了
尾调用（`jmp`），栈帧被 `_GBACoreAttachDebugger` 顶替——解析时按"最近的
前一个符号"匹配才不会误判。

修法：`loadROM` 之后加 `g_core->reset(g_core);`。

### 2.3 savestate 写盘失败（`mCoreSaveStateNamed` 返回 false）

**根因**：文件打开标志不对。`mCoreSaveStateNamed()`（`src/core/serialize.c:443`）
用 `vf->map(vf, stateSize, MAP_WRITE)` 写状态；Windows 的
`CreateFileMapping` 需要**读权限**，文件以 `O_WRONLY` 打开时映射失败 →
函数直接 `return false`（文件里只有 `ftruncate` 出来的空洞）。

mGBA 自己的 `mCoreGetState()`（`src/core/core.c:331`）用的是
`O_CREAT | O_TRUNC | O_RDWR`——照抄即可。改成 `O_RDWR` 后 `save` 返回 OK。

### 2.4 宿主自身的三个逻辑 bug（非崩溃，但会让证据失真）

| 问题 | mGBA 实现 | 修法 |
|---|---|---|
| "释放按键"没生效 | `clearKeys(core, keys)` 是 `keysActive &= ~keys`，传 0 等于什么都没清 | 改用 `setKeys(core, 0)` |
| `save`/`load` 只能存**槽号**，且 `"*"` 参数格式解析不了路径（先试整数解析 → `Parse error`） | GBA 平台的 `_save` 读 `dv->intValue` 当槽号 | 宿主自建 `save <path>` / `load <path>`（基于 `mCoreSaveStateNamed`/`mCoreLoadStateNamed`，参数格式用 `"S"`） |
| 崩在 `_cliDebuggerInit` | 该函数无条件解引用 `cliDebugger->backend->init` | **backend 必须在 `mDebuggerAttach()` 之前挂上**（上一轮 bisect 崩的就是这里） |

另外：`mDebuggerCreate(DEBUGGER_CLI, core)` 已经通过
`core->cliDebuggerSystem()` 挂好了 GBA 平台系统，**不要再 new 一个
`GBACLIDebugger`**——那会泄漏第一个系统，且 `CLIDebuggerAttachSystem()`
会把旧的系统 `free()` 掉。

### 2.5 按键掩码（已核对）

`core->setKeys()` 用的是 GBA KEYINPUT 位序，与任务书给的掩码一致：

```
A=0x001 B=0x002 SELECT=0x004 START=0x008
RIGHT=0x010 LEFT=0x020 UP=0x040 DOWN=0x080 R=0x100 L=0x200
```

证据：`_GBACoreSetKeys` → `gba->keysActive = keys`，
`GBAIORead(REG_KEYINPUT)` 返回 `0x3FF ^ keysActive`；
方向位掩码 `input & 0x030`（RIGHT/LEFT）与 `input & 0x0C0`（UP/DOWN）
也印证了位序。

---

## 3. 最终用法

```powershell
python tools/mgba_probe/build.py
python tools/mgba_probe/probe_client.py --rom rom/base.gba --script run.txt
```

脚本一行一条命令；客户端在每条命令后追加 `echo` 哨兵以准确切分输出，
最终输出结构化 JSON（`steps[]` 每项含 `command` / `status` / `output` /
`dump`）。

宿主命令表见 `tools/mgba_probe/README.md` §4。

---

## 4. 实测输出（`rom/base.gba`）

### 4.1 完整脚本与输出

脚本：

```
status
x/4 0x02026804 2
frames 30 0x000
dump 0x02026804 8
frames 60 0x008
dump 0x02026804 8
key 0x008
run 60
dump 0x04000130 2
keyoff
run 30
dump 0x04000130 2
save <路径>\final.ss9
dump 0x02026804 8
load <路径>\final.ss9
dump 0x02026804 8
```

输出（exit code = 0）：

```
status
 r0: 00000000   r1: 00000000   r2: 00000000   r3: 00000000
 r4: 00000000   r5: 00000000   r6: 00000000   r7: 00000000
 r8: 00000000   r9: 00000000  r10: 00000000  r11: 00000000
r12: 00000000  r13: 03007F00  r14: 00000000  r15: 00000004
cpsr: 0000001F [-------]
Cycle: 0
00000000:  GBA Memory: Bad BIOS Load32: 0x00000000
00000000	andeq r0, r0, r0

x/4 0x02026804 2
0x02026804: 00000000 00000000

frames 30 0x000
GBA DMA: Starting DMA 3 0x085BA000 -> 0x06000000 (8400:4B00)
OK frames 30 0x00000000

dump 0x02026804 8
DUMP 02026804 8
0000000000000000
ENDDUMP

frames 60 0x008
OK frames 60 0x00000008

dump 0x02026804 8
DUMP 02026804 8
0000000000000000
ENDDUMP

key 0x008
OK key 0x00000008
run 60
OK run 60 keys=0x00000008
dump 0x04000130 2
DUMP 04000130 2
F703
ENDDUMP

keyoff
OK keyoff
run 30
OK run 30 keys=0x00000000
dump 0x04000130 2
DUMP 04000130 2
FF03
ENDDUMP

save <路径>\final.ss9
OK save <路径>\final.ss9 397412
dump 0x02026804 8
DUMP 02026804 8
0000000000000000
ENDDUMP
load <路径>\final.ss9
OK load <路径>\final.ss9
dump 0x02026804 8
DUMP 02026804 8
0000000000000000
ENDDUMP
```

### 4.2 关键读数解释

| 观测 | 读数 | 含义 |
|---|---|---|
| KEYINPUT `0x04000130` 空闲 | `FF 03` | 0x03FF（全 1 = 没按任何键） |
| KEYINPUT 按住 START | `F7 03` | 0x03F7，bit3 清零 → START 生效 |
| KEYINPUT `keyoff` 之后 | `FF 03` | 键已释放 |
| `0x02026804`（battle control 8 字节）按键前后 | 两次都是 `00 00 00 00 00 00 00 00` | 该块只在**战斗/章节开始**时由 `0x0808F618` 写入（见 `notes/chapter-flow-format.md` §"WRAM Battle Control Area"）；此刻还在标题/启动流程，**本来就该是 0**，因此"按键前后无变化"是**符合预期**的，不是读错 |
| savestate 大小 | **397412 字节** | 状态本体 397312 + 100 字节扩展数据（savedata / RTC / metadata） |
| `x/4 0x02026804 2` | `0x02026804: 00000000 00000000` | 与 `dump` 交叉验证一致 |

### 4.3 游戏确实在跑（不是卡死）

跑 600 帧后再看：

```
status
 r0: 0000009F   r1: 04000054   r2: 0000008B   r3: 00000484
 r4: 00000002   r5: 00000000   r6: 00000000   r7: 00000000
 r8: 00000000   r9: 04000006  r10: 0000000C  r11: 00000000
r12: 00000000  r13: 03007F00  r14: 085DFABC  r15: 085DFB34
cpsr: 8000001F [N------]
Cycle: 168297709
085DFB30:  E0D900B0	ldrh r0, [r9], #0
```

- PC = `0x085DFB34`（在 ROM 内）、LR = `0x085DFABC`，周期数 1.68 亿 → CPU 在跑游戏代码；
- VRAM `0x06000000` 读出 `9C77` 重复 → 画面在绘制；
- EWRAM `0x020311E4` 仍为全 0 → 还没进到会写该区的主流程。

---

## 5. 离 L2/L3 动态证据还差什么

宿主本身不再是瓶颈（L2 = 原生定点 / L3 = 模拟器按键两级的"跑得起来 + 按得到"前提
已具备）。剩下的缺口是**导航**与**取证方式**：

1. **导航到目标场景**：现在只能把游戏推进到标题/启动后的 UI 循环
   （`0x085DFBxx` 一带），还没有"START → 新游戏 → 战斗"的确定性路径。
   之前的 WASM 探针（`play/_scripts/runtime-formation-probe.js`）已经证明
   "同样的按键计数重放"进不去战斗，**必须改成画面/内存状态驱动**。
   现在有了 KEYINPUT 可读 + 可注入，这条路可以重做。
2. **断点式采样**：宿主目前是"跑 N 帧 + dump"。`b`/`c` 是 mGBA CLI 的交互命令，
   客户端还没有"设断点 → 跑到命中 → 停下 → 采 PC/LR/寄存器/ROM/WRAM → 继续"的
   脚本化流程，而这正是 `notes/runtime-verification-gates-20260710.md`
   要求的"联合断点组"。
3. **BIOS**：当前没有加载 GBA BIOS（`status` 里会显示 `GBA Memory: Bad BIOS`）。
   游戏仍能跑（卡带 0x00000000 处是跳转到入口的 branch），但启动动画/IRQ 时序
   与真机不完全一致。若后续要采"进战斗时刻"的精确帧，需要补一份 BIOS。
4. **截图/OCR**：宿主只分配了 video buffer，没有把帧导出成 PNG；
   画面判据仍需另接 `tools/` 下的截图链路。

---

## 6. 复现用的辅助手法（以后还会用到）

1. **崩溃回溯**：`SetUnhandledExceptionFilter` + `CaptureStackBackTrace` 打印帧地址，
   配合链接器 `/MAP` 与一个 RVA→符号脚本定位。
   注意 MSVC `/O2` 会把尾调用编成 `jmp`，栈帧会**少一层**。
2. **分阶段落地标记**：在关键步骤往文件里追加一行，比往 stderr 打更可靠
   （fastfail 时 stdout/stderr 可能一个字都留不下）。
3. **不要用 `setvbuf` 改行缓冲**（MSVC：只有 `_IONBF` 允许 NULL 缓冲区）。
4. **mGBA 的 VFile 语义**：`clearKeys` 是"清除掩码里的位"不是"全部清除"；
   `mCoreSaveStateNamed` 要求文件以 `O_RDWR` 打开（要内存映射写）。
5. **本仓库写文件一律用 `tools.lib.io.write_text`**（强制 LF）；
   本次新增的 `host_main.c` / `build.py` / `probe_client.py` /
   `README.md` / `CMakeLists.txt` 与本笔记均为 LF、无 BOM。

---

## 7. 交付物

| 文件 | 说明 |
|---|---|
| `tools/mgba_probe/host_main.c` | 宿主源码（新增 `run`/`echo` 命令、崩溃回溯、ABI 指纹断言） |
| `tools/mgba_probe/build.py` | 构建脚本（从 vcxproj 读宏） |
| `tools/mgba_probe/probe_client.py` | Python 客户端（JSON 输出） |
| `tools/mgba_probe/README.md` | 用法说明 |
| `tools/mgba_probe/CMakeLists.txt` | 并入 mGBA 工程的构建路径（可选） |
| `notes/mgba-probe-build-20261020.md` | 本文件 |
| `docs/sequel-roadmap.md` | "当前关键路径"条目更新（阻塞已解除） |
