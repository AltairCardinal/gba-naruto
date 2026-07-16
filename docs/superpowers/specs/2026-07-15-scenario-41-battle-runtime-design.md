---
comet_change: close-scenario-41-battle-runtime
role: technical-design
canonical_spec: openspec
---

# Scenario 41 玩家控制、胜利与 Postbattle 运行时设计

## 1. 目标与证据边界

本设计把 scenario 41 从“稳定显示 battle 41”推进到可复验的自然控制链：玩家选择、正常行动提交、两回合教程胜利、result 写入、battle controller 退出和 `0xF400` postbattle。OpenSpec delta spec 是需求事实源；本文只定义实现结构、数据流和测试顺序。

本 change 不证明 EXP、level 2、训练点或 levels record 消费，也不升级任何 bank。它交付的是后续 `verify-levels-runtime` 可直接加载的自然 victory/postbattle checkpoint 与紧凑证据。

## 2. 已确认基线

- `artifacts/runtime-checkpoints/tutorial-ui-save.sav` 是自然存档根。
- `build/natural-s41-menu-index2.ss9` 是当前最可靠、最接近 player hook 的候选：自然 scenario 41 终止后到达任务准备菜单，“开始任务”行已选，尚未出现 battle/map/formation；在被接纳前仍需零输入稳定性、来源和 WRAM 复核。
- `build/natural-s41-start-prompt.ss9` 实际位于队伍/装备页，名称误导，不得作为 canonical prompt。
- `artifacts/runtime-checkpoints/actionable-move-grid.ss9` 已位于玩家选择 hook 之后，只能复用为后续行动导航或负对照。
- 双 observer builder 已覆盖 `0x08073946 → 0x0806F718` 与 `0x080739D8 → 0x08069DB8`，但现有运行 scratch 为零，不能宣称玩家控制。
- Windows mGBA 0.10.5 的 GDB 读取可用，单 packet 超过 256 字节返回 `E06`；最小化窗口的 `PostMessage` 输入没有形成可靠 KEYINPUT 证据。

## 3. 方案选择

### 3.1 采用混合通道

浏览器模拟器只负责实例内 `buttonPress/buttonUnpress` 输入、前台截图和 `.ss9` 导出；原生 Windows mGBA 只负责 savestate 复放、GDB breakpoint、寄存器与只读内存；诊断 ROM observer 负责把自然调用边界发布为持久结构化样本。

未采用的方案：

- mGBA-only 需要尚未证明可靠的 Windows 定向输入，会引入焦点或全局按键风险；
- browser-only 虽能可靠输入，但缺少独立 stop/PC 检查且 Chromium 进程树更重；
- 单个全链 observer ROM 会集中 code cave、scratch 和调用约定风险，不利于定位行为扰动。

### 3.2 分阶段 observer ROM

每个 ROM 只观察最近一段自然控制链：

1. `player-control`：玩家选择与当前单位；
2. `action-submit`：行动菜单与 MOVEDONE；
3. `victory-result`：`0x0807444E → 0x080777FC → 0x08073068`；
4. `battle-exit`：`0x08074FDA` 与 `0x08074EE6`/`0xF400`。

新增 hook 前必须先确认它是可安全包装的直接调用点或有明确定义的函数入口。每个 builder 校验 immutable base ROM、原始指令、zero-filled cave、scratch/cave 不重叠和 confined byte diff。wrapper 不得改变返回值、寄存器、SP、LR 或用户可见状态。

## 4. 组件设计

### 4.1 Checkpoint ledger

新增机器可读 checkpoint 清单，记录：名称、状态、SHA-256、父 checkpoint、基础/observer ROM SHA-256、自然输入列表、保存边界、屏幕摘要、关键 WRAM、不允许验证的边界和零输入复放结果。

只有满足以下条件的 checkpoint 才迁入 `artifacts/runtime-checkpoints/`：

- 来源链从 `tutorial-ui-save.sav` 或已接纳父状态可追溯；
- 相同 ROM 下零输入 settle 后保持相同 UI/控制边界；
- 文件名与真实 UI 一致；
- 没有越过其声明可验证的目标 hook；
- 至少一次 base ROM 复放和一次诊断 ROM 复放的关键非目标状态一致。

计划保留最小阶梯：`scenario-41-start-row`、`scenario-41-start-confirm`、`scenario-41-player-turn`、`scenario-41-turn-1-complete`、`scenario-41-victory`、`scenario-41-postbattle`。导航失败或转场快照留在忽略的 `build/`，不进入持久证据。

### 4.2 严格 mGBA GDB 会话

`mgba_gdb_probe.py` 保留 RSP packet、寄存器和 256-byte 分块读取，重做运行所有权与停止判定：

- 启动前确认固定端口未监听；端口冲突直接 fail closed；
- 启动后要求子进程仍存活，并通过 GDB 读取 ROM 固定区间与请求 ROM 比对；
- 解析 `S/T/W/X` stop packet，读取 PC，按 ARM/Thumb 停止语义验证目标地址；watchpoint 还校验访问地址；
- 不发送 GDB `k`，只关闭 socket 并终止本次 `Popen`/Job Object 拥有的树；
- 持续排水 stdout/stderr，结果仅保留有界尾部，避免 PIPE 堵塞；
- 成功或失败 JSON 都包含 emulator/ROM/savestate 哈希、命令、stop packet、实际/期望 PC、读取区间和诊断尾部。

macOS Intel 复用同一 RSP 协议、ROM 指纹、stop 校验和分块读取。Windows 继续通过 TCP owner
table 证明 listener/connection 都属于启动的 child PID；Darwin 通过系统 `lsof -nP -FpnT`
解析精确的 LISTEN 与 ESTABLISHED endpoint，并要求唯一 owner 等于 child PID。查询工具缺失、
输出异常、owner 为空/多义/不匹配都 fail closed。macOS 会话仍必须由 `run_guarded.py` 的 owned
process group 与 heavy lock 包裹；GDB 只负责断点和只读证据，不负责输入。

Windows 键盘注入、窗口枚举和 KEYINPUT write-watch 不进入正式探针接口。自然输入由浏览器实例 API 完成。

### 4.3 Published observer protocol

每个 observer slot 使用 publish-last 协议：先清 magic，写 hit count、参数、共享事件序号，再最后写 magic。runtime driver 在加载 checkpoint 后先读取 baseline；只有相同 magic、`final_count > baseline_count` 且事件序号单调的新样本可被接受。

现有双 hook scratch 需要加入共享序号或等价顺序字段，并保留独立 slot。decoder 由固定 16-byte 解析器升级为显式 schema/version 解析器；未知 schema、短读或 magic 不匹配都返回无效样本，不静默猜测。

### 4.4 Runtime driver 与 evidence evaluator

浏览器 driver 把“输入计划”和“只读 settle”彻底分开：

- 正证据计划逐项列出 key、hold、gap 和预期边界；
- settle 阶段绝不发送 adaptive A/B/back/recovery key；
- 每一步同时采集 observer、battle control、map、formation、当前单位、屏幕摘要和截图；
- evaluator 只接受 checkpoint 后新鲜 observer、scenario 41、正确玩家单位、稳定前台战斗画面和预期状态变化共同成立；
- strict battle arrival 只能证明战斗表现，不能替代玩家控制。

driver 生成紧凑 evidence JSON，并把原始大内存、临时截图和调试 ROM 保留在忽略目录。持久 JSON 引用 checkpoint/ROM 哈希、最小截图或帧摘要、复现命令和资源守卫摘要。

## 5. 自然控制链执行

### 5.1 玩家控制

从接纳后的 `scenario-41-start-row` 开始，先读取 observer baseline，只发送一次 A。若只出现“开始任务？”确认框，则立即保存并接纳 `scenario-41-start-confirm`；从该状态再次只发送一次 A。验收必须包含 `0x08073946` 的新鲜 observer 命中或严格 native breakpoint PC，同时参数与当次捕获的可控单位、阵营和当前单位状态一致，不在运行前猜定角色。

base ROM 使用同一 checkpoint/输入复放，要求可见行为与关键 WRAM 一致。通过后固化 `scenario-41-player-turn`。

### 5.2 第一回合与 MOVEDONE

从 player-turn checkpoint 按教程路线把当次捕获的可控单位移动到 `(4,7)`，完成教程对话、朝向与防御选择；起点以 player-turn 的实际单位状态为准，不沿用旧文档中的角色假设。输入拆成短步骤，每个稳定边界保存候选状态。正证据要求 MOVEDONE 新鲜命中以及单位坐标、回合/行动状态的前后变化一致；随后固化 turn-1-complete。

### 5.3 第二回合、胜利与退出

从 turn-1-complete 移动到宝箱上方 `(4,10)` 并自然结束行动。按顺序接受胜负检查、Iruka 有效存活条件变化、result 从未决写为胜利、controller 退出和 postbattle state `0xF400`。每一级都记录自己的地址证据，不用最终 `F400` 倒推前面调用已发生。

victory 与 postbattle 分别保存 checkpoint；最终 postbattle 在 base ROM 上零输入复放，且不得依赖强制 WRAM 写入。

## 6. 错误处理与资源边界

- 端口占用、ROM 指纹错误、非目标 stop、陈旧 observer、越过 hook、转场残片、屏幕/WRAM 不一致都产生明确 `not-proven` 原因并保留下一步，不升级结论。
- 所有 mGBA、Chromium 和高开销静态命令经 `tools/run_guarded.py` 的同一 heavy lock 运行，记录准入内存、owned-tree 峰值、wall/idle/RSS 结束原因。
- 清理只针对本次 Windows Job Object/POSIX process group；禁止按进程名结束 Python、Chrome、Node 或 mGBA。
- 每次重任务前后记录系统可用内存。达到门槛时保存诊断并停止本次运行，不启动并行重任务。

## 7. TDD 与验证策略

### 7.1 单元测试

- GDB：端口占用、ROM 指纹、stop parser、PC/watch 地址不匹配、checksum/NACK、分块拼接/子块失败、日志排水和精确清理；
- builder：两个现有 hook 的完整机器码、错误原指令/occupied cave、第二 hook 负例、所有范围不重叠、执行级寄存器/SP/LR 等价；
- decoder/evaluator：baseline delta、共享顺序、陈旧样本、错误 battle/map/unit、转场假画面和清单外输入拒绝；
- checkpoint ledger：父链、哈希、命名、允许用途和稳定性门禁。

所有功能变化执行红—绿—重构，并保留正确原因的首次失败输出。

### 7.2 集成与运行时验收

- fake RSP server 覆盖完整 request/ack/packet/stop 流；
- 原生 mGBA 对一个已知必达 PC 做受守卫 smoke，证明会话、stop 和读取链；
- driver wiring 测试注入 memory reader，验证 plan/settle 两循环读取正确地址/长度；
- 每个阶段运行 base ROM control 与 observer ROM，使用同 checkpoint、同输入和同采样窗口；
- 最终运行相关 Python/Node/集成测试、OpenSpec strict validate、`git diff --check`，并由独立子代理审查 ABI、checkpoint 来源、正负证据和资源清理。

## 8. 阶段本地提交

按可独立审查的证据闭环创建范围明确的本地 commit：

1. 严格 mGBA GDB + 双 observer 工具与测试；
2. canonical start-row/start-confirm + 玩家控制证据；
3. MOVEDONE + turn-1 checkpoint；
4. victory/postbattle checkpoint、交接与路线图。

每个提交只暂存本阶段文件，排除临时 `build/` 产物和用户既有修改。只有第四阶段通过后，本 change 才进入 Comet Verify；levels 仍保持 `code_verified`。
