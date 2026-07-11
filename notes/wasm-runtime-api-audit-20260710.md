# WASM 运行时 API 审计（2026-07-10）

## 目的与范围

为动态验证寻找浏览器版 mGBA 已有的低成本入口，审查：

- 仓库中的 `play/_scripts/`；
- 当前公开部署 `https://sh.kibox.com.cn/gba-naruto/play/` 的 HTML、
  `main.js`、`mgba.js` 和 `mgba.wasm`；
- `play/` 的 Git 历史。

本次只读取部署内容并把临时副本放在 `/tmp`，没有修改公开部署，也没有新增工具代码。

## 部署版本证据

2026-07-10 读取到的页面加载：

- `./mgba/mgba.js?v=threaded-v16-force-cold-reset`
- `./main.js?v=threaded-v17-multi-user`

审计副本校验值：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `main.js` | 22,848 | `f9b99ca471214def6cd720fc1777374d65d3d72b80d761db34e63c8662b78edb` |
| `mgba.js` | 454,849 | `4c342e83b112f584142d03b77d1a43311ae99f77ae690f8c0b0343e59f855362` |
| `mgba.wasm` | 1,930,688 | `540ef0328b85fd220870a4f1b4c158b815cc14f1a1698d942898b29d7b9684e4` |

## 结论摘要

1. **已有 GBA 地址空间读取 API**。WASM 和 Emscripten glue 都公开了
   `_readGbaByte`、`_readGbaHalfWord`、`_readGbaWord`、`_readGbaBytes`。
2. `main.js` 在初始化后把完整 Module 暴露为 `window.__mGBA`，所以 Puppeteer
   可直接调用这些底层函数，不需要重新编译或部署。
3. **没有 PC、通用寄存器、断点或 watchpoint 导出**。二进制内部含
   `_GBACoreReadRegister` 等实现/反射字符串，但它们不在 WASM Export 表中，不能由
   `Module.ccall` 凭名字调用。内部存在不等于公开 API。
4. 当前浏览器链路适合做 WRAM/ROM 的轮询快照和变化检测，但不能单凭它捕获“谁写了该
   地址”或精确执行 PC。写入者 PC 仍需原生 mGBA debugger/Lua，或重新编译 WASM 增加导出。

## `readGba*` 的确切可用接口

`wasm-objdump -x` 确认以下 Export：

| WASM export | 页面上的调用入口 | 语义 |
|---|---|---|
| `readGbaByte` | `window.__mGBA._readGbaByte(addr)` | 读取 GBA 总线 8 位值 |
| `readGbaHalfWord` | `window.__mGBA._readGbaHalfWord(addr)` | 读取 GBA 总线 16 位值 |
| `readGbaWord` | `window.__mGBA._readGbaWord(addr)` | 读取 GBA 总线 32 位值；JS 结果按需用 `>>> 0` 转无符号 |
| `readGbaBytes` | `window.__mGBA._readGbaBytes(addr, dst, length)` | 把连续字节复制到 WASM heap |

反汇编证明三个标量函数经当前 core 的 `rawRead8/rawRead16/rawRead32` 类函数指针读取；若
core 或读函数不存在则返回 `-1`。`readGbaBytes` 逐字节调用 8 位读取并写入目标 heap。

部署中 `malloc` 也是 WASM export，但 glue 没有把 `_malloc` 挂到 Module；可通过公开的
`Module.ccall` 调用。Puppeteer 页面内批量读取可采用：

```js
const m = window.__mGBA;
const length = 0x200;
const ptr = m.ccall('malloc', 'number', ['number'], [length]);
try {
  m._readGbaBytes(0x020240c0, ptr, length);
  return Array.from(m.HEAPU8.slice(ptr, ptr + length));
} finally {
  m.ccall('free', null, ['number'], [ptr]);
}
```

对短区间也可直接循环 `_readGbaByte(address + i)`，无需分配 heap。目标动态验证的重要地址
包括单位区 `0x020240C0`（历史别名/旧区）和当前重点 `0x02024294`，以及章节 ID
`0x02026805`。ROM 地址可直接按 GBA 地址读取，例如文件偏移 `0x5461C4` 对应
`0x085461C4`。

### 并发边界

当前是 threaded build，手动 RAF 会持续调用 `_runLoopJs`。读取一组必须内部一致的快照时，
先调用 `pauseGame()`，确认暂停后读取，再 `resumeGame()`；否则多个字段可能来自不同模拟帧。
该读取 API 没有 watchpoint 语义，也没有声明对运行中 core 的原子快照保证。

## PC、寄存器和状态接口

### 不存在的公开能力

WASM 的 72 项 Export 中没有以下接口：

- `readRegister` / `getPc` / `readPc`
- breakpoint / watchpoint
- debugger attach/step/continue
- GBA memory write API

`strings` 能找到 `_GBACoreReadRegister`、`struct::mCore.readRegister`、
`mScriptMemoryDomain.read*` 等符号文本，是 mGBA 内部代码或脚本绑定元数据；因为它们没有
导出，当前页面不能可靠调用。不可把这些字符串当作已具备寄存器读取的证据。

### 已有状态能力

页面 Module 已包装：

- `saveState(slot)` / `loadState(slot)`；
- `saveStateSlot(slot, flags)` / `loadStateSlot(slot, flags)`；
- `forceAutoSaveState()` / `loadAutoSaveState()` / `getAutoSaveState()`；
- `FS`、`HEAPU8`、`filePaths()`；
- `pauseGame()` / `resumeGame()` / `forceColdReset()` / `quickReload()`；
- `addCoreCallbacks(...)`，其中包括 frame started/ended 和 keys-read callback。

这些能力可用于保存导航到战斗后的可复现入口，以及在 frame-ended callback 或 Puppeteer
轮询中抓 WRAM。savestate 文件本身可能包含 CPU 状态，但解析文件不能替代运行时 PC API；
除非先建立并验证对应格式解析器，否则不应据此宣称命中某 PC。

## 按键映射

部署 `main.js` 的 DOM 键盘映射：

| 浏览器 `KeyboardEvent.code` | GBA 键 |
|---|---|
| `ArrowUp/Down/Left/Right` | Up/Down/Left/Right |
| `KeyZ` | A |
| `KeyX` | B |
| `Enter` | Start |
| `ShiftLeft` / `ShiftRight` | Select |
| `KeyA` | L |
| `KeyS` | R |
| `F2` | 页面暂停/继续（不是 GBA 键） |

底层 `mgba.js` 枚举为 A=0、B=1、Select=2、Start=3、Right=4、Left=5、Up=6、
Down=7、R=8、L=9。`buttonPress(name)` / `buttonUnpress(name)` 可绕开 DOM 直接调用，
适合自动导航；窗口失焦时页面会释放所有 held 键。

现有 `play/_scripts/t7-puppeteer-e2e.js` 使用 `Enter` 和 `KeyZ`，与部署映射一致，但它只按
固定延迟导航和截图，没有读取内存、PC 或保存即时状态。新出现的
`runtime-formation-probe-lib.js` 只提供导航计划、快照分类和编成坐标匹配纯函数，也尚未包含
浏览器执行器。

## Git 历史结论

`git log --all -- play` 只显示：

- `a18a23d verify(T7): complete dialogue visual verification via puppeteer e2e`
- `d48aa8a test(smoke): add API URL regression guard + refresh dist`

提交树中仅有 `_scripts` 和截图；部署的 `play/main.js`、`mgba/mgba.js`、
`mgba/mgba.wasm` 从未纳入此仓库历史。因此无法从本仓库 commit 还原 `readGba*` 的引入版本
或 C 源实现。当前最强证据是上述部署文件哈希、WASM Export 表和函数反汇编。

## 对后续动态验证的建议

最低成本路径是不改部署，新增本地 Puppeteer runner：

1. 启动页面并等待 `window.__mGBA`、游戏加载完成；
2. 通过 `buttonPress/buttonUnpress` 执行确定性的导航计划；
3. 每次读取前暂停，批量读取 `0x02024294` 等目标区，再继续；
4. 发现有效战斗状态时调用 `saveState(1..8)`，并通过 FS 取出状态文件与截图；
5. 记录输入序列、帧/时间、章节 ID、WRAM 快照和 ROM 候选表匹配结果。

若验收条件必须包含 PC 或写入者，需选择原生 mGBA debugger/Lua，或在可重建的 WASM C
源码中导出只读 `readGbaRegister`/`getGbaPc`。不要试图依据 Emscripten heap 地址猜测 core
结构；布局随构建变化，且 threaded build 下会产生竞态。

## 重要文件与地址

- `play/_scripts/t7-puppeteer-e2e.js`：现有浏览器导航基线。
- `play/_scripts/runtime-formation-probe-lib.js`：现有快照分类/编成匹配能力，可复用。
- 部署 `main.js`：`window.__mGBA` 暴露点与 DOM 键映射。
- 部署 `mgba.js`：`readGba*` glue 和 Module API。
- `0x02024294`：当前战斗单位/位置动态观察重点。
- `0x02026805`：章节 ID。
- `0x085461C4`：positions ROM 表的 GBA 总线地址。

## 本轮边界

已确认的是“可以读取 GBA 地址空间并驱动按键/状态”；尚未确认的是“已到达战斗状态”或
“已命中地图/编成加载 PC”。本审计不能提升任何结构的 dynamic verification 等级。
