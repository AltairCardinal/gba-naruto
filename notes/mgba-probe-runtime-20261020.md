# mGBA 无头探针：运行时取证能力与导航结论（2026-10-20）

**工具**: `tools/mgba_probe/`（宿主 C + Python 驱动）
**新工具**: `tools/mgba_probe/runtime_probe.py`（运行时证据采集器）
**关联**: `notes/runtime-verification-gates-20260710.md`（四级证据）、
`notes/story-vm-opcodes-20261020.md`（VM 解释器）、
`notes/legacy-table-base-correction-20261020.md`（原生消费者定位）、
`notes/completion-audit-20261020.md`（完成度审计）

---

## 0. 结论摘要

- 探针宿主之前只用了 mGBA CLI 调试器命令的**一小部分**。实际上
  `mgba-0.10.5/src/debugger/cli-debugger.c` 提供了 **30+ 条命令**，
  包括 **写监视点（watchpoint）**、**删除断点**、**单步**、
  **读写内存/寄存器**、**表达式打印**、**指令跟踪**。
  这些命令之前完全没被用上，导致「导航不动」这个现象一直查不清。
- 之前「导航卡住」的**根因有两个**，都已定位并修掉：
  1. `frames` / `run` 走的是 **fast path**（`core->runFrame`），
     **永远不会检查断点** —— 所以断点根本抓不到；
  2. 断点**命中后会把 CPU 停在原地**，且断点仍然挂着，
     下一次 `cont` 立刻再次报同一个地址 —— 看起来像「导航完全不动」。
- **按键注入一直是好的**：游戏自己的 WRAM 里能看到按键状态
  （`0x0300000C` = 当前按住，`0x0300000E` = 本帧新按下）。
- **两条旧结论被证伪**（详见 §4）：
  `0x020311EA` **不是场景号**；`0x0808F698` **不是起始场景数据字节**。
- 剧情 VM 解释器入口 = **`0x080977B8`**（本会话独立定位，
  并被 `notes/story-vm-opcodes-20261020.md` 独立复核）。

---

## 1. mGBA CLI 调试器完整命令面

`D:\Shell\toolchain\mgba-0.10.5\src\debugger\cli-debugger.c` 的
`_debuggerCommands[]`（本仓库 `tools/mgba_probe/host_main.c` 通过
`_mergeCommands()` 合并进去）：

| 命令 | 参数 | 用途 |
|---|---|---|
| `break` / `b` | `Is` | 设断点 |
| `delete` | `I` | **按 id 删除断点/监视点** |
| `continue` | — | 继续执行 |
| `next` | — | **执行下一条指令** |
| `finish` | — | 执行到当前栈帧返回 |
| `listb` / `listw` | — | 列出断点/监视点 |
| `watch` | `Is` | 读写监视点 |
| `watch/r` `watch/w` `watch/c` | `Is` | 读 / 写 / 变化监视点 |
| `r/1` `r/2` `r/4` | `I` | 读 1/2/4 字节 |
| `w/1` `w/2` `w/4` | `II` | 写 1/2/4 字节 |
| `w/r` | `SI` | **写寄存器** |
| `print` `print/x` `print/t` | `S+` | 表达式求值（支持内存解引用） |
| `trace` | `Is` | 跟踪 N 条指令 |
| `backtrace` | `i` | 栈回溯 |
| `status` | — | 打印寄存器状态 |
| `disassemble` | `Ii` | 反汇编 |
| `events` | — | 打印调度事件 |
| `reset` / `quit` | — | 重置 / 退出 |

宿主自己额外合并的命令：`key` `keyoff` `frames` `run` `cont` `dump`
`save` `load` `shot` `echo`。

---

## 2. 两个坑（都踩过、都已修）

### 2.1 fast path 不看断点

mGBA 的 `mDebuggerRun()`：

```c
case DEBUGGER_RUNNING:
    if (!debugger->platform->hasBreakpoints(debugger->platform)) {
        debugger->core->runLoop(debugger->core);   // fast
    } else {
        debugger->core->step(debugger->core);      // 单指令
        debugger->platform->checkBreakpoints(debugger->platform);
    }
```

宿主原来的 `frames` / `run` 直接调 `core->runFrame()`，**完全绕过断点表**。
所以「先 `frames` 按键、再 `cont` 抓断点」的写法里，按键窗口内发生的断点命中
会被漏掉。

**修法**：`tools/mgba_probe/host_main.c` 的 `_cmdFrames` / `_cmdRun`
改调 `_runFramesDbg()`（它内部：没有断点时走 fast，有断点时走 debugger）。
→ 按键与断点命中现在发生在**同一个窗口**里。

### 2.2 断点命中后 CPU 停在原地

`ARMDebuggerCheckBreakpoints()` 只在 PC 等于断点地址时触发，
命中后 `mDebuggerEnter()` 把 `d->state` 置成 `DEBUGGER_PAUSED`，
但**断点仍然挂着**。下一次 `cont` 重新 `step` 一次，
PC 还在原地 → 立刻再次命中同一个断点 → 看起来像「游戏完全不动」。

**修法**（`tools/mgba_probe/runtime_probe.py` 的做法）：

```
delete <id>   ->   next   ->   b <addr>
```

先删断点、单步越过那条指令、再重新挂上。

> 早先的 `build/_dbg_hunt3.py` 就是被这个坑坑了：它一次挂 5 个断点，
> 只要有一个命中，后面全部重复报同一个地址，于是结论是「一个都没命中」。

### 2.3 监视点命中后同样会卡住

监视点通过 `ARMDebuggerInstallMemoryShim()` 挂钩内存写入，
命中时同样 `mDebuggerEnter()`。所以监视点也要 `delete` + `next` + 重挂。
**已实测**：`watch/w 0x0300067C` 命中时输出

```
Hit watchpoint 1 at 0x0300067C: (new value = 0x00000000, old value = 0x00000001)
 r0: 0300067C  r1: 0300067D  r2: 04000208 ...
 r14: 080614E9 r15: 080612AC
```

即：标志字节由 `r2 = 0x04000208`（**IF 中断标志寄存器**）那一侧的代码清零。

---

## 3. 游戏自己的按键状态（WRAM）

按键读取函数在 **`0x080615E4`**（`push {r4,r5,lr}` 开头）：

```
080615E6  ldr  r0, [pc, #0x2c]   ; 0x04000130 = KEYINPUT
080615E8  ldrh r1, [r0]
080615EA  mvns r1, r1             ; ~KEYINPUT -> 按下位 = 1
080615EC  lsls r1, r1, #0x10
080615EE  lsrs r1, r1, #0x10     ; r1 = 10 位按键掩码
080615F0  ldr  r2, [pc, #0x24]   ; 0x030009F0  历史
080615F2  ldrh r5, [r2, #2]
080615F4  strh r5, [r2]
080615F6  ldr  r4, [pc, #0x24]   ; 0x0300000E  本帧新按下
080615F8  ldrh r0, [r4]
080615FA  strh r0, [r2, #2]
080615FC  ldr  r3, [pc, #0x20]   ; 0x0300000C  当前按住
080615FE  ldrh r2, [r3]
08061600  adds r0, r1, #0        ; r0 = 当前按住
08061602  bics r0, r2             ; 去掉上一帧就按住的
08061604  bics r0, r5             ; 去掉更早按住的
08061606  strh r0, [r4]           ; 存成「本帧新按下」
08061608  strh r1, [r3]           ; 存成「当前按住」
0806160A  bl   #0x8065398         ; 分派
```

于是有：

| 地址 | 含义 | 读法 |
|---|---|---|
| `0x0300000C` | 当前按住的键 | u16，bit set = 按下；**高位 0xFC00 是取反后的常量**，只有低 10 位有意义 |
| `0x0300000E` | 本帧**新**按下的键 | u16 |
| `0x030009F0` | 上一帧按住 / 两帧前按住 | u16 ×2 |

实测（`tools/mgba_probe/runtime_probe.py`）：

```
after boot      held=0xFC00 new=0x0000
A held          held=0xFC01 new=0x0001     <- bit0 = A
A released      held=0xFC00 new=0x0000
START held      held=0xFC08 new=0x0008     <- bit3 = START
```

→ **按键注入是好的**，游戏确实收到了 A 与 START。

---

## 4. 两条被证伪的旧结论

### 4.1 `0x020311EA` 不是场景号

之前的导航脚本把 `0x020311EA` 当「当前场景号」读，
于是报出「54 → 50 → 40 后停滞」。用原生消费者定位器查：

```
0x020311EA  consumers=0     (没有任何原生读者)
```

相邻的 `0x020311D4` 有 **87 个**原生读者。结合
`notes/story-vm-opcodes-20261020.md`（指令 `0x37`/`0x38` 用
`0x020311D4` 这个 word/bitfield 存剧情 flag），
`0x020311EA` 落在**剧情 flag 位域块内部**，读它读到的是 flag 的位，
不是场景号。

→ 「54 → 50 → 40」这条轨迹**没有意义**，导航的停滞判据也是错的。

### 4.2 `0x0808F698` 不是起始场景数据字节

`notes/external-konoha-workshop-gap-20261020.md` §12 曾把它记成
「起始场景字节」。实际字节是：

```
08F690  19 4E       ldr  r6, [pc, #0x19]
08F692  00 25       movs r5, #0
08F694  00 24       movs r4, #0
08F696  34 82       adds r2, r4, #0x34
08F698  36 20       movs r0, #0x36      <- 0x36 是「立即数操作数」
08F69A  B0 75       strb r0, [r5, #0xB0] <- 把 54 存进 [r5+0xB0]
```

`0x0808F698` 是 `movs r0, #0x36` 这条指令的**第二个半字**，
不是数据表里的一个字节。定位器查 `0x0808F698` 的原生读者也是 0。

→ 那条笔记里的一行已更正（见该文件 §12 的表格）。

### 4.3 战斗相关的真实基址

| 地址 | 原生读者 | 说明 |
|---|---:|---|
| `0x02026804` | **24** | 战斗控制块的真实基址（`0x02026805` 只是它的 +1 字段，没有自己的读者） |
| `0x020240C0` | **24** | 战斗单位数组（12 槽），消费者用 `muls` 推出步长 |
| `0x02022E34` | **15** | 角色实例池（stride `0xBC` = 188，工具自动推出） |

---

## 5. 剧情 VM 入口

`0x0808F544`（剧情脚本状态机）里：

```
0808F594  ldr r7, [pc, #0x1c]
0808F598  ldr r0, [pc, #0x1c]   ; 0x08060C74 = before 根表
0808F59A  mov sb, r0
0808F59C  ldr r2, [pc, #0x1c]   ; 0x08060D54 = after 根表
0808F59E  mov r8, r2
0808F5A0  ldrb r1, [r6, #0x18]  ; 当前在 before 还是 after
0808F5A6  lsls r0, r4, #0x10
0808F5A8  asrs r0, r0, #0xe     ; r0 = scene_id * 4
0808F5AA  add  r0, sb
0808F5AC  ldr  r0, [r0]         ; 取该场景的脚本指针
...
0808F5D0  bl   #0x80977b8       ; <- VM 解释器入口
```

→ **VM 解释器入口 `0x080977B8`**，`r0` = 脚本指针。
`notes/story-vm-opcodes-20261020.md` 独立复核了同一入口、
跳转表 `0x080977F4`（58 个 u32）和 `cmp r0, #0x39` 的分派。

由此得到一条**可用的导航判据**：在 `0x080977B8` 下断点，
命中时的 `r0` 就是正在执行的剧情脚本指针；把四个根表的所有条目
建成「指针 → (表名, 场景号)」的反查表，就能知道游戏跑到哪一场戏。
反查表由 `tools/decode_story_script.py` 的 `ROOT_TABLES` 生成，
本 ROM 实测 **190 个不同脚本指针**。

---

## 6. 当前的导航阻塞点（部分解决）

### 6.1 已解决：游戏确实能走到剧情

用「按键 + 断点」两条腿走通了：

```
START → A → A → A          <- 第 3 次 A 触发剧情调度器
```

- 断点 `0x0808F544`（剧情调度器）命中：**r0 = 0x36 = 54**（场景号）。
- 断点 `0x080977B8`（VM 解释器入口）命中：**r0 = 0x08049E76**（场景 54 的脚本指针）。

完整证据与判死检验见 `notes/evidence/story-vm-l2-20261020.md`。

> **触发时机敏感**：挂着的断点集合不同 → 帧时序不同 → 同一串按键落到不同代码路径。
> 复现必须用证据文件里写的那条完整命令。

### 6.2 已解决：画面能看了，而且剧情对白对得上

**根因（探针侧）**：宿主原来先 `core->reset()` 再 `setVideoBuffer()`。
mGBA 的 GBA core 只在 `_GBACoreReset()` 里把软件渲染器挂到 board 上，
而且**只在 `renderer.outputBuffer` 已经设置时**才挂
（`src/gba/core.c`）。顺序反了 → core 一直用 dummy 渲染器 →
视频缓冲里只有 `GBAVideoSoftwareRendererInit()` 填的纯白。

**修法**：把 `setVideoBuffer()` 挪到 `reset()` **之前**。
修完之后 `shot`（PNG）仍然不可用（本机 mGBA 没开 `USE_PNG`），
但**不需要 PNG**：新增宿主命令 `rawshot <path>` 直接导出
**mGBA 自己的视频缓冲**（240×160 的 `color_t`，
字节序 R,G,B,A，见 `mgba/core/interface.h` 的
`M_COLOR_RED 0x000000FF` / `M_COLOR_GREEN 0x0000FF00` / `M_COLOR_BLUE 0x00FF0000`）。
`tools/mgba_probe/render_screen.py --live` 走的就是这条路径。

**结果**：`START` + `A`×4 之后，画面上出现对白框：

- 名牌「**伊鲁卡**」
- 对白「**“是啊，是我这个班主任所承认的嘛！”**」

与 `tools/decode_story_script.py --scene 54` 解出的场景 54 剧本**第 5 句一字不差**
（说话人也是伊鲁卡）。这是剧情脚本根表的 **L3（模拟器正常按键复现）** 证据，
画面冻结在 `notes/evidence/story-scene-l3.png`，
说明见 `notes/evidence/story-scene-l3-20261020.md`。

> 附带结论：对话里的汉字是 **16×16**，而 `0x53D644` 那张字形段表是 **8×8**
> （渲染器 `0x08065EF4` 的 `lsls r0, r0, #5` = 32 字节/字形）。
> **存在两套字形**，`notes/font-encoding.md` 已相应更正；
> 16×16 对话字形表**尚未定位**（全 ROM 无第二张同构段表）。

### 6.3 仍未解决：16×16 对话字形表

见 `notes/evidence/story-scene-l3-20261020.md` §6：
屏幕像素与 ROM 字形的**逐位比对**还差最后一步 ——
需要先找到 16×16 字形数据在 ROM 里的位置。

---

## 7. 复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'

# 运行时证据采集器
python tools/mgba_probe/runtime_probe.py rom/base.gba --press START --press A
python tools/mgba_probe/runtime_probe.py rom/base.gba \
    --breakpoint 0x080977B8 --watch 0x0300067C --json build/runtime-trace.json

# 原生消费者定位器（本轮的通用取证器）
python tools/consumer_locate.py rom/base.gba --all --evidence notes/evidence/consumer-evidence.json
```

宿主改动（`frames`/`run` 走 debugger 路径、`close()` 不会挂死）后要重建：

```powershell
python tools/mgba_probe/build.py
```
