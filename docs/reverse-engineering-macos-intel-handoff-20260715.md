# GBA 木叶战记逆向工程：macOS Intel 迁移交接（2026-07-15）

## 1. 交接目标与当前边界

后续 runtime 实验转移到 macOS Intel，避免继续占用当前 Windows 桌面的键鼠和前台
窗口。工作分支为 `task/units-character-definitions`，Windows 最后一个已推送基线为
`4949a86`；本交接及新的 prebattle candidate 位于其后的迁移提交中。

当前结论必须保持：

- bank 调查闭合审计为 32/32，分布仍是 13 `runtime_verified` / 10
  `code_verified` / 9 `disproved`；
- scenario 41 已固化稳定 controller-entry checkpoint；活动 raw `0x0808F957` 与
  `0x0808F952 → 0x080732B4` 静态 BL 门通过，并由两次 224-frame zero-input replay 接纳；
- 玩家控制、MOVEDONE、胜利、EXP、升级与 postbattle 均为 `not-proven`；
- `levels` 仍是 `code_verified`，总逆向工程尚未完成；
- `[0x0202680C]` 只决定 controller 初始局部 `r6`，不是 controller-entry 必要条件。

## 2. Git 会带到 Mac 的内容

仓库内已持久化：

- base ROM：`rom/base.gba`，SHA-256
  `1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b`；
- accepted pre-controller state：
  `artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9`，SHA-256
  `894dddec77d56d98bc9aca4a1edae3ac4c88206930f39fe06d627fe7bcf7110f`；
- Windows Lua 运行得到的 prebattle menu candidate：
  `artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9`，SHA-256
  `b7badf1c7988f01614b92a46bcd54322d7693d120c4cdd671f0a3f56a4db7078`；
- candidate 的 `.ss9` 本身是带预览图的 PNG 容器；本文记录输入、哈希、task context
  与功能边界，现有 ledger 保持为已验收集合；
- `.ss9` 离线解析工具：`tools/inspect_mgba_savestate.py`；
- checkpoint ledger：`artifacts/runtime-checkpoints/scenario-41-checkpoints.json`。

Git 不会带走本机未跟踪的 `build/` 诊断文件、单独导出的 candidate PNG、Windows mGBA 安装目录、
`rom/base.sav`、`rom/base.ss2` 或 Windows 进程守卫摘要。这些不是 Mac 继续工作的
前置条件，不要从聊天记录重建它们。

## 3. Mac 首次检出与校验

```bash
git clone https://github.com/AltairCardinal/gba-naruto.git
cd gba-naruto
git switch --track origin/task/units-character-definitions
git pull --ff-only

shasum -a 256 rom/base.gba \
  artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9 \
  artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9

python3 -m unittest \
  tests.test_inspect_mgba_savestate \
  tests.test_runtime_checkpoint_ledger -v
python3 tools/runtime_checkpoint_ledger.py \
  artifacts/runtime-checkpoints/scenario-41-checkpoints.json
python3 tools/inspect_mgba_savestate.py \
  artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9 \
  --output build/macos-prebattle-candidate-context.json
```

使用 mGBA 0.10.5 的 macOS Intel/x86_64 构建；先记录下载来源、版本、应用包 SHA-256
和 `file /Applications/mGBA.app/Contents/MacOS/mGBA` 的架构结果。不要用另一版本产生的
存档直接升级 ledger。官方入口：<https://mgba.io/downloads.html>，Lua API：
<https://mgba.io/docs/scripting.html>。

如需运行 `tools/disasm_thumb.py`，不要使用 Windows vendored Capstone 动态库。Mac 建议：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'capstone==5.0.7'
export CAPSTONE_PYTHON_PATH="$(python -c 'import site; print(site.getsitepackages()[0])')"
```

## 4. Windows 最后一项有效实验

普通窗口键盘 tap 太短：它能被内层读取，却不能稳定跨过紧邻的外层按键检查。mGBA
Lua 改为按帧保持后成功：

```lua
local root = "/absolute/path/to/gba-naruto"
emu:loadStateFile(root .. "/artifacts/runtime-checkpoints/scenario-41-pre-controller-lineup.ss9")
local frame0 = emu:currentFrame()
local callback_id
callback_id = callbacks:add("frame", function()
    local delta = emu:currentFrame() - frame0
    if delta == 5 then
        emu:addKey(C.GBA_KEY.B)
        console:log("B down frame 5")
    elseif delta == 13 then
        emu:clearKey(C.GBA_KEY.B)
        console:log("B up frame 13")
    elseif delta == 80 then
        emu:saveStateFile(root .. "/build/macos-prebattle-replay.ss9")
        emu:screenshot(root .. "/build/macos-prebattle-replay.png")
        callbacks:remove(callback_id)
        console:log("saved frame 80")
    end
end)
```

输入审计是 relative frame 5 B-down、frame 13 B-up，即保持 8 帧；frame 80 捕获。
Windows 输出的当前 task 2：

- saved PC `0x0806112A`，`[0x0202680C]=0`；
- SP `0x030011D8`；
- LR `0x08067D03`，resume PC `0x08067D02`；
- 活动 unwind raw words：`0x080885C1 → 0x08088F9F → 0x0808F92D`；
- 截图是战前菜单，不再是白框 lineup；
- 活动 unwind 不含 `0x0808F957`，所以仍不能声称 controller entry。

这纠正了旧的 `B → B → Down+A` 计划：从 accepted 白框 state 到战前菜单，已知有效
输入是一次跨帧 B hold，不是两个短 tap。

## 5. Mac 第一轮必须先做的验收

先对仓库中的 prebattle candidate 做零输入复放，不要立刻继续按键：

```lua
local root = "/absolute/path/to/gba-naruto"
emu:loadStateFile(root .. "/artifacts/runtime-checkpoints/scenario-41-prebattle-menu-candidate.ss9")
local frame0 = emu:currentFrame()
local callback_id
callback_id = callbacks:add("frame", function()
    if emu:currentFrame() - frame0 == 80 then
        emu:saveStateFile(root .. "/build/macos-prebattle-zero.ss9")
        emu:screenshot(root .. "/build/macos-prebattle-zero.png")
        callbacks:remove(callback_id)
    end
end)
```

只有同时满足以下条件，才把 candidate 作为 accepted 新增到 ledger：

1. input audit 为零输入；
2. 截图仍是同一战前菜单；
3. task 2 仍位于 `0x08067D02` 对应菜单链，活动 unwind 保留
   `0x080885C1/0x08088F9F/0x0808F92D`；
4. base ROM hash 正确、mGBA 版本与架构已记录；
5. 运行后没有遗留 mGBA 子进程或监听端口。

`.ss9` 输出哈希可能包含捕获时状态差异，Mac 复放不要求与 Windows candidate 全文件
哈希相同；验收依据是输入、截图、task context、活动 unwind 与 ROM/模拟器来源共同成立。

## 6. candidate 后的唯一主线

当前菜单函数是 `0x080884DC`，由 `0x08088F98` 调用，raw return 为
`0x08088F9F`。`0x08088FDE..0x08088FE6` 的静态 result-2 路径会设置
`r7=0,r5=2` 并退出菜单；外层随后在 `0x0808F952` 调用 `0x080732B4`。

旧的 “Down+A 得到 result 2” 仍只是待验证假设。Mac 上应先固化零输入 baseline，
再把 Down 与 A 分段成独立 candidate；任何一步不清楚就停止，不自动补键。真实 controller
checkpoint 的验收只接受：

- 当前活动 task unwind 出现 raw return `0x0808F957`；或
- entry observer fresh 命中 `0x0808F952 → 0x080732B4`；
- 输入日志、base ROM、无 observer 行为对照和进程清理同时成立。

达到该门后才观察局部 dispatcher `r6=0x2000/0x3000`，再推进玩家控制、MOVEDONE、
胜负、result、postbattle 和 levels。旧 screen/battle-map classifier 不再能单独接纳入口。

## 7. 2026-07-17 controller-entry 持久化补记

旧 B → B → Down 分支已标为 superseded：Down 发生在 `0x08088628` message-box yield，
并不改变 selection。纠正后的分段输入为 B → B → A → Down → Down → A → inner B →
outer A → inner A；outer B 是 cancel，outer A 只进入 nested loop，最后的 inner A 才
捕获 raw `0x0808F957`。accepted p1 已复制为
`artifacts/runtime-checkpoints/scenario-41-controller-entry.ss9`，其 SHA-256 为
`4569846c1bf2cfcc2b6ad8848266bd02d2ada332eeca7acf74456f7a762e7cd6`。

维护边界：controller entry 现在 runtime-proven 且 zero-input stable；玩家控制、第一回合、
MOVEDONE、胜利和 postbattle 仍是 `not-proven`。本变化不修改 32/32 bank 验证数量或
13/10/9 状态分布。

## 8. macOS 资源与进程约束

不要照搬 Windows Job Object。Mac runner 应使用独立进程组，并记录父子 PID、峰值 RSS、
wall/idle timeout、退出码与最终残留；只清理本轮 owned process group，禁止按 `mGBA`、
`Chrome` 或 `python` 进程名全局结束。

全 ROM Capstone 对象扫描曾在 Windows 膨胀到 3 GiB 以上；Mac 同样禁止恢复该路径。
继续使用有界反汇编、固定窗口读取和 checkpoint 驱动实验。每次有效结果必须在同一工作周期
更新 `notes/` 或 `docs/`、checkpoint ledger、`docs/sequel-roadmap.md`，并运行相关测试后
再提交。

本交接记录了：Windows mGBA UI tap 失败原因、Lua 8-frame B hold 成功结果、关键地址、
可迁移 candidate、Mac 首轮零输入验收和 controller-entry 停止门。它不宣称逆向完成。

## 9. 2026-07-18 自然胜利与 postbattle 补记

交接中的 player control / MOVEDONE / victory / postbattle `not-proven` 已部分取代：

- 玩家接管与第一回合 secondary MOVEDONE 已有 accepted checkpoint；
- 后续自然回合在第 4 回合以相邻技能结束，`0x02026807=1`，随后经过结果、升级和战后对白
  回到木叶世界地图；
- `artifacts/runtime-checkpoints/scenario-41-victory.ss9` 与
  `scenario-41-postbattle.ss9` 均为 immutable base ROM 的零输入可恢复状态；
- `0x08074F2C` natural-save observer 仍未形成正命中，因此不得把瞬态 `0xF400` 或自然
  保存调用写成已证明；下一主线直接从 postbattle checkpoint 做 levels `+6` A/B。

机器证据和输入边界以 `artifacts/runtime-checkpoints/scenario-41-completion-evidence.json`
与 `notes/scenario-41-completion-runtime-20260718.md` 为准。
