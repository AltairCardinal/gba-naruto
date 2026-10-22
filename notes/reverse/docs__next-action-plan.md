# 下一步行动计划

## 目标

稳定 mGBA runtime 调试环境，作为所有格式逆向（P0）工作的人口。

## 现状

- mGBA 系统包已安装（Debian 12）：`mgba-qt` v0.10.1 at `/usr/games/mgba-qt`，`mgba-sdl` at `/usr/games/mgba`
- Xvfb 已安装（`/usr/bin/Xvfb`）
- ⚠️ 系统包**未编译 Lua scripting 支持**（`--script` 不可用）
- ✅ **调试器模式 `-d` 完全可用**：支持 `watch/w`、`frame`、`x/4` 等命令
- 已有的调试资产：
  - `notes/dialogue-watch-wram.done` / `notes/dialogue-watch-wram.md`（WRAM watchpoint 已成功）
  - `notes/headless-workflow.md`
  - `notes/local-mgba-build.md`
  - `notes/mgba-newgame-walk.done`
  - `notes/mgba-dialogue-diff.done`
- 现有 mGBA 自动化脚本：`/root/gba-naruto/tools/` 下有一批 Lua 脚本和 Python 工具

## 任务

按顺序尝试以下方案，直到找到稳定的调试环境：

### 方案 A｜mGBA Qt 命令行版（headless）

1. 检查系统是否可安装 mGBA（`apt install mgba` 或从源码编译）
2. 检查 `Xvfb`（虚拟显示服务器）是否可用
3. 写一个 headless 脚本：在无显示环境下用 mGBA Qt 加载 ROM，执行指定帧数，保存 RAM/VRAM 快照
4. 参考 `notes/headless-workflow.md` 的经验

交付物：`tools/mgba-headless-snapshot.py`（可在无显示器环境下生成 RAM/VRAM 快照）

#### 方案 A 执行结果 ✅ 成功

**日期**：2026-03-29

**发现**：
1. `mgba-qt` 和 `mgba-sdl` 都支持 `-d`（调试器）模式，无需 Lua scripting
2. 调试器命令：`watch/w`（写入 watchpoint）、`watch/c`（变化 watchpoint）、`frame`（帧推进）、`x/4`（读4字内存）
3. `x/` 命令限制：每个 `x/4` 只能读 4 个 word（16字节），不能读更大块。需要多次调用
4. 无需 Xvfb：使用 `SDL_VIDEODRIVER=dummy` + `QT_QPA_PLATFORM=offscreen` 即可 headless 运行
5. watchpoint 命中时输出格式：`Hit watchpoint N at 0xADDR: (new value = 0xNEW, old value = 0xOLD)`
6. 命中后紧跟寄存器状态（r0-r15, cpsr, cycle, PC/disasm）

**已修复**：
- `tools/mgba-headless-snapshot.py`：修复 `x/` 命令限制（改为多 `x/4` 调用），修复寄存器解析正则，增强 watchpoint 命中提取 PC/LR/SP
- `tools/run_headless_mgba.sh`：更新为跨平台（Linux + macOS），检测 `--script` 支持

**验证通过**：
- snapshot 模式：`python3 tools/mgba-headless-snapshot.py --rom ROM --mode snapshot --dump 0x0200A900:64 --frames 10` → 输出 16 word 的 JSON
- watchpoint 模式：`python3 tools/mgba-headless-snapshot.py --rom ROM --mode watch --watch 0x0200A900 --frames 5` → 命中 1 次，PC=0x08060FD2，cycle=182801696
- diff 模式：`python3 tools/mgba-headless-snapshot.py --rom ROM --mode diff --diff-region 0x0200A900:0x50 --frames 10` → 输出帧间变化
- savestate 支持：`--savestate FILE` 参数正常工作

**已知限制**：
- 调试器模式不支持发送按键输入（需要 Lua 脚本或 savestate 跳过 title screen）
- `x/4` 每次只能读 16 字节，读大区域需要多次调用（脚本已自动处理）
- 系统包无 `--script` 支持，Lua 脚本需要自编译 mGBA

### 方案 B｜修复 mGBA WASM 版

1. 检查当前 WASM 版 mGBA 的 watchpoint API 支持情况
2. 写一个 node.js 封装，调用 WASM 版 mGBA 的 watchpoint 功能
3. 参考 `tools/run-headless-probe.*` 的历史尝试

交付物：`tools/mgba-wasm-watchpoint.js`（WASM 版的稳定 watchpoint 接口）

### 方案 C｜用 mGBA Lua 脚本替代原生 watchpoint

1. mGBA 内置 Lua 支持，可以用 Lua 脚本监控内存写入
2. 参考 mGBA Lua API：可用的 memory watch API

交付物：`tools/mgba-lua-watchpoint.lua`（Lua 脚本形式的内存监控）

## 验证标准

稳定的调试流程必须满足：
- 可以重复执行（同一 ROM → 同一结果）
- 可以设置任意 WRAM/VRAM 区域的写入监控
- 输出结构化日志（JSON）包含：写入者 PC、写入值、帧号

## 完成后

调试环境稳定后，立即用以下任务验证：
1. 重新触发 `WRAM 0x0A900+` 写入 watchpoint（已知的成功案例）
2. 在 battle 场景中抓 tilemap 数据候选区域的写入者
3. 在 battle 初始化时抓 WRAM 0x020000 区域的 diff

---

## 背景：为什么这是第一步

| P0 任务 | 需要的调试能力 |
|---------|--------------|
| tilemap 定位 | battle 加载时 VRAM 写入 watchpoint |
| 战斗配置定位 | battle 前后 WRAM snapshot diff |
| 章节流程入口 | trace 从文本渲染到流程跳转的控制流 |

这些都需要稳定的 mGBA runtime 调试环境。没有这个，所有 P0 任务都卡在原地。

## 当前推荐顺序

1. ~~方案 A（mGBA Qt headless）~~ ✅ 已稳定 — 调试器 `-d` 模式 + `mgba-headless-snapshot.py` 可用
2. 下一步：用 savestate 跳过 title screen，结合 watchpoint 模式抓 dialogue/battle WRAM/VRAM 写入
3. 方案 C（mGBA Lua）— 如果需要按键输入自动化，可编译支持 scripting 的 mGBA
4. 方案 B（WASM 修复）— 作为备选
